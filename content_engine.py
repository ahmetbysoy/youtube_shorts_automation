#!/usr/bin/env python3
"""
Faz 2 - Görev 2: İçerik Üretim Motoru (content_engine.py)
---------------------------------------------------------
Sıfır maliyetli, halüsinasyon korumalı ve çok katmanlı hata toleransına sahip
YouTube Shorts senaryo + seslendirme motoru.

Mimari Katmanlar ("Sadece ücretsiz katmanlar & her aracın bir alternatifi"):
  1. LLM Senaryo Katmanı (60-80 kelime / 30-45 sn Shorts Senaryosu):
     - Birincil  : Groq Cloud Free API (`llama-3.3-70b-versatile` - GROQ_API_KEY)
     - İkincil   : Google Gemini Free API (`gemini-2.5-flash` - GEMINI_API_KEY)
     - Gerçeklik : Türkçe Wikipedia REST API üzerinden doğrulanmış kaynak özeti beslemesi
     - Tolerans  : API kesintisi, anahtar eksikliği veya kota aşımında (`try-except`)
                   devreye giren doğrulanmış 4'lü yedek (fallback) senaryo havuzu

  2. TTS & Altyazı Zaman Damgası Katmanı:
     - Birincil  : `edge-tts` (`tr-TR-AhmetNeural` / `tr-TR-EmelNeural`) +
                   `WordBoundary` üzerinden milisaniye hassasiyetli kelime zaman damgaları
     - Alternatif: `gTTS` (Google TTS Türkçe) + FFmpeg tempo optimizasyonu

Üretilen Çıktılar (Faz 3 Medya İşleme Hattına Hazır):
  - `voiceover.mp3` : Yüksek kaliteli Türkçe seslendirme
  - `script.txt`    : Saf, seslendirmeye hazır senaryo metni
  - `script.json`   : Başlık, açıklama, İngilizce stok video arama terimleri
                      (`visual_keywords`), ses süresi ve milisaniye bazlı `word_timestamps`
  - `voiceover.srt` : FFmpeg altyazı gömme işlemi için hazır 2-3 kelimelik dinamik SRT
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import edge_tts
import requests

DEFAULT_AUDIO_OUT = Path("voiceover.mp3")
DEFAULT_TXT_OUT = Path("script.txt")
DEFAULT_JSON_OUT = Path("script.json")
DEFAULT_SRT_OUT = Path("voiceover.srt")
HISTORY_FILE = Path(".used_topics.json")
ANALYTICS_FEEDBACK_FILE = Path("analytics_feedback.json")
DEFAULT_AFFILIATE_FALLBACK_URL = "https://www.youtube.com/@mentansiytas?sub_confirmation=1"

SUPPORTED_VOICES = {
    "ahmet": "tr-TR-AhmetNeural",
    "emel": "tr-TR-EmelNeural",
    "tr-TR-AhmetNeural": "tr-TR-AhmetNeural",
    "tr-TR-EmelNeural": "tr-TR-EmelNeural",
}

WIKI_SEED_TOPICS = [
    "Antikythera_düzeneği",
    "Göbeklitepe",
    "Tunguska_olayı",
    "Voyager_Altın_Plağı",
    "İskenderiye_Kütüphanesi",
    "Mariana_Çukuru",
    "Piri_Reis_Haritası",
    "Rosetta_Taşı",
    "Pompeii",
    "Halley_kuyruklu_yıldızı",
    "Ölü_Deniz_Yazmaları",
    "Krakatoa",
]

# API kesintisi, kota aşımı veya anahtar bulunmaması durumunda devreye giren yedek senaryo havuzu
FALLBACK_SCENARIOS: list[dict[str, Any]] = [
    {
        "topic": "Tarih",
        "title": "Tarihin En Kısa Savaşı Sadece 38 Dakika Sürdü! #Shorts",
        "description": "1896 yılındaki İngiliz-Zanzibar Savaşı neden sadece 38 dakika sürdü? #tarih #ilginçbilgiler #shorts",
        "hook": "Tarihte bir çay molasından bile daha kısa, sadece otuz sekiz dakika süren gerçek bir savaş olduğunu biliyor muydunuz?",
        "script_text": (
            "Tarihte bir çay molasından bile daha kısa, sadece otuz sekiz dakika süren gerçek bir savaş olduğunu biliyor muydunuz? "
            "Bin sekiz yüz doksan altı yılında Zanzibar Sultanı ölünce, yeğeni İngilizlerin onayı olmadan sarayı ele geçirdi. "
            "İngiliz donanması limana demirledi ve sabah dokuzda ültimatom süresi dolunca sarayı bombalamaya başladı. "
            "Sadece otuz sekiz dakika içinde saray harabeye döndü, sultan arka kapıdan kaçtı ve tarihin en kısa savaşı resmen sona erdi. "
            "Üstelik İngilizler attıkları mermilerin faturasını bile Zanzibar halkına ödetti."
        ),
        "visual_keywords": [
            "historic warship ocean",
            "old cannon smoke",
            "ancient palace ruins",
            "vintage pocket watch",
        ],
    },
    {
        "topic": "Bilim",
        "title": "Venüs'te Bir Gün, Bir Yıldan Daha Uzundur! #Shorts",
        "description": "Güneş sisteminin en tuhaf gezegeni Venüs'te zaman neden ters işliyor? #bilim #uzay #ilginçbilgiler #shorts",
        "hook": "Doğum gününüzü her gün kutlayabileceğiniz bir gezegen var deseydim inanır mıydınız?",
        "script_text": (
            "Doğum gününüzü her gün kutlayabileceğiniz bir gezegen var deseydim inanır mıydınız? "
            "Komşumuz Venüs, kendi ekseni etrafında o kadar inanılmaz derecede yavaş döner ki, bir tam dönüşünü Dünya süresiyle iki yüz kırk üç günde tamamlar. "
            "Ancak Güneş'in etrafındaki tam turunu sadece iki yüz yirmi beş Dünya gününde bitirir. "
            "Yani Venüs'te bir gün, bir yıldan tam on sekiz Dünya günü daha uzundur! "
            "Üstelik diğer gezegenlerin aksine ters yönde döndüğü için, orada Güneş batıdan doğup doğudan batar."
        ),
        "visual_keywords": [
            "planet venus space",
            "solar system orbit",
            "burning sun galaxy",
            "deep space stars",
        ],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Asla Yaşlanmayan Ölümsüz Denizanası! #Shorts",
        "description": "Biyolojik olarak ölümsüz olan Turritopsis dohrnii nasıl yeniden doğuyor? #bilim #doğa #ilginçbilgiler #shorts",
        "hook": "Dünya üzerinde biyolojik olarak ölümsüz olan gerçek bir canlı yaşadığını biliyor muydunuz?",
        "script_text": (
            "Dünya üzerinde biyolojik olarak ölümsüz olan gerçek bir canlı yaşadığını biliyor muydunuz? "
            "Akdeniz sularında da yaşayan ve serçe parmağınızın tırnağından bile küçük olan bu özel denizanası, yaşlandığında ya da yaralandığında ölmek yerine zamanı geriye sarar. "
            "Hücrelerini tamamen dönüştürerek tıpkı bir kelebeğin tekrar tırtıla dönüşmesi gibi bebeklik evresine geri döner. "
            "Bir avcı tarafından yenmediği sürece bu döngüyü sonsuza kadar tekrarlayabilir. "
            "Bilim insanları şimdi insan yaşlanmasını durdurmak için bu minik canlının genetik şifresini inceliyor."
        ),
        "visual_keywords": [
            "glowing jellyfish underwater",
            "deep ocean bioluminescence",
            "microscope cells dna",
            "blue sea waves",
        ],
    },
    {
        "topic": "Tarih",
        "title": "Napolyon'un Tavşan Ordusuna Karşı Tuhaf Yenilgisi! #Shorts",
        "description": "Avrupa'yı titreten Napolyon Bonapart yüzlerce tavşandan neden kaçmak zorunda kaldı? #tarih #ilginçbilgiler #shorts",
        "hook": "Avrupa'yı dize getiren Napolyon Bonapart'ın, hayatının en tuhaf yenilgisini bir tavşan sürüsünden aldığını duymuş muydunuz?",
        "script_text": (
            "Avrupa'yı dize getiren Napolyon Bonapart'ın, hayatının en tuhaf yenilgisini bir tavşan sürüsünden aldığını duymuş muydunuz? "
            "Bin sekiz yüz yedi yılında imzalanan barış antlaşmasını kutlamak isteyen Napolyon, görkemli bir tavşan avı düzenletti. "
            "Ancak kurmayları yabani tavşan yerine çiftliklerde insan elinde büyümüş üç bin evcil tavşan toplamıştı. "
            "Kafesler açıldığında tavşanlar kaçmak yerine Napolyon'u yemek getiren bakıcıları sandı ve dev bir dalga halinde imparatorun üzerine hücum etti. "
            "Koca imparator, çaresizce saltanat arabasına binip savaş alanından kaçmak zorunda kaldı."
        ),
        "visual_keywords": [
            "rabbits running field",
            "napoleon vintage painting",
            "royal horse carriage",
            "european forest autumn",
        ],
    },
    {
        "topic": "Tarih",
        "title": "Piramitlerden 7 Bin Yıl Daha Eski Tapınak: Göbeklitepe! #Shorts",
        "description": "Şanlıurfa'daki Göbeklitepe insanlık tarihini nasıl baştan yazdı? #göbeklitepe #tarih #ilginçbilgiler #shorts",
        "hook": "Mısır piramitlerinden bile tam yedi bin yıl daha eski dev bir tapınağın Türkiye topraklarında olduğunu biliyor muydunuz?",
        "script_text": (
            "Mısır piramitlerinden bile tam yedi bin yıl daha eski dev bir tapınağın Türkiye topraklarında olduğunu biliyor muydunuz? "
            "Şanlıurfa yakınlarındaki Göbeklitepe, günümüzden yaklaşık on iki bin yıl önce, insanlar henüz yerleşik tarıma bile geçmemişken inşa edildi. "
            "Ağırlığı on altı tonu bulan T biçimli dev taş sütunların üzerine tilki, yılan ve akbaba kabartmaları ustalıkla işlenmişti. "
            "Tekerleğin ve metal aletlerin olmadığı bir çağda bu dev kayaların nasıl taşındığı hâlâ arkeolojinin en büyük gizemlerinden biri olarak duruyor."
        ),
        "visual_keywords": [
            "ancient stone temple",
            "archaeology excavation desert",
            "prehistoric monolith ruins",
            "sunset ancient stones",
        ],
    },
    {
        "topic": "Bilim",
        "title": "Everest'i Yutan Karanlık Uçurum: Mariana Çukuru! #Shorts",
        "description": "Okyanusun 11 kilometre altındaki Mariana Çukuru'nda neler yaşıyor? #bilim #okyanus #ilginçbilgiler #shorts",
        "hook": "Everest Dağı'nı alıp okyanusun en derin noktasına koysaydınız, zirvesinin hâlâ iki kilometre su altında kalacağını biliyor muydunuz?",
        "script_text": (
            "Everest Dağı'nı alıp okyanusun en derin noktasına koysaydınız, zirvesinin hâlâ iki kilometre su altında kalacağını biliyor muydunuz? "
            "Pasifik Okyanusu'ndaki Mariana Çukuru yaklaşık on bir kilometre derinliğiyle Dünya'nın en karanlık uçurumudur. "
            "Güneş ışığının asla ulaşamadığı bu derinlikte basınç, yüzeydekinden tam bin kat daha fazladır. "
            "Buna rağmen bilim insanları bu dondurucu karanlıkta kendi ışığını üreten şeffaf balıklar ve dev kabuklular keşfetmeyi başardı."
        ),
        "visual_keywords": [
            "deep ocean abyss",
            "submarine underwater dark",
            "bioluminescent sea creature",
            "pacific ocean waves",
        ],
    },
    {
        "topic": "Bilim",
        "title": "Uzayda Ağlarsanız Gözyaşlarınız Düşmez! #Shorts",
        "description": "Yerçekimsiz ortamda ağlayan bir astronotun gözyaşlarına ne olur? #uzay #bilim #astronot #shorts",
        "hook": "Uluslararası Uzay İstasyonu'nda ağlamaya başlasaydınız gözyaşlarınızın yanaklarınızdan aşağı akmayacağını biliyor muydunuz?",
        "script_text": (
            "Uluslararası Uzay İstasyonu'nda ağlamaya başlasaydınız gözyaşlarınızın yanaklarınızdan aşağı akmayacağını biliyor muydunuz? "
            "Dünya'da gözyaşlarımızın süzülmesini sağlayan şey yerçekimidir; ancak yörüngedeki mikro yerçekimi ortamında sıvılar aşağı düşemez. "
            "Bunun yerine suyun yüzey gerilimi devreye girer ve gözyaşlarınız gözünüzün tam üzerinde şeffaf bir su balonu gibi büyümeye başlar. "
            "Balon yeterince büyüdüğünde ise bir havluyla silmezseniz yüzünüzden kopup kabinin içinde süzülen minik bir küreye dönüşür."
        ),
        "visual_keywords": [
            "astronaut space station",
            "water droplet zero gravity",
            "earth orbit view",
            "spacecraft interior",
        ],
    },
    {
        "topic": "Tarih",
        "title": "Avustralya Ordusunun Devekuşlarına Karşı Savaşı! #Shorts",
        "description": "1932 Büyük Emu Savaşı'nda makineli tüfekli askerler neden kaybetti? #tarih #ilginçbilgiler #shorts",
        "hook": "Modern makineli tüfeklerle donatılmış gerçek bir ordunun, uçamayan kuşlara karşı resmen savaş kaybettiğini duymuş muydunuz?",
        "script_text": (
            "Modern makineli tüfeklerle donatılmış gerçek bir ordunun, uçamayan kuşlara karşı resmen savaş kaybettiğini duymuş muydunuz? "
            "Bin dokuz yüz otuz iki yılında Avustralya'da yirmi bin emu kuşu tarım arazilerini istila edince hükümet bölgeye makineli tüfekli askerler gönderdi. "
            "Ancak saatte elli kilometre hızla koşabilen emular, ateş açıldığı anda küçük gruplara ayrılarak tam bir gerilla taktiği uyguladı. "
            "Binlerce mermi harcanmasına rağmen sürüler durdurulamadı ve ordu geri çekilince tarihe Büyük Emu Savaşı kuşların zaferiyle geçti."
        ),
        "visual_keywords": [
            "emu bird running outback",
            "australian desert landscape",
            "vintage military history",
            "wheat field sunset",
        ],
    },
    {
        "topic": "Bilim",
        "title": "Bir Çay Kaşığı Nötron Yıldızı 6 Milyar Ton Çeker! #Shorts",
        "description": "Evrenin en yoğun cisimleri olan nötron yıldızları nasıl oluşur? #evren #uzay #bilim #shorts",
        "hook": "Sadece bir küp şeker büyüklüğündeki bir maddenin Dünya'daki tüm arabaların toplamından daha ağır olabileceğini hayal edebilir misiniz?",
        "script_text": (
            "Sadece bir küp şeker büyüklüğündeki bir maddenin Dünya'daki tüm arabaların toplamından daha ağır olabileceğini hayal edebilir misiniz? "
            "Dev bir yıldız ömrünü tamamlayıp süpernova olarak patladığında çekirdeği kendi içine o kadar korkunç bir kuvvetle çöker ki atomların içindeki boşluk bile yok olur. "
            "Ortaya çıkan nötron yıldızı sadece yirmi kilometre çapındadır ama Güneş'ten bile daha fazla kütleye sahiptir. "
            "Öyle ki bu yıldızdan alacağınız tek bir çay kaşığı madde Dünya üzerinde yaklaşık altı milyar ton ağırlığında olurdu."
        ),
        "visual_keywords": [
            "supernova explosion nebula",
            "neutron star pulsar space",
            "cosmos galaxy stars",
            "astrophysics dark universe",
        ],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Üç Kalpli ve Mavi Kanlı Uzaylı Canlı: Ahtapot! #Shorts",
        "description": "Ahtapotların neden 3 kalbi, 9 beyni ve mavi kanı vardır? #doğa #bilim #okyanus #shorts",
        "hook": "Okyanuslarımızda üç kalbi, dokuz beyni ve masmavi kanı olan gerçek bir canlı yaşadığını biliyor muydunuz?",
        "script_text": (
            "Okyanuslarımızda üç kalbi, dokuz beyni ve masmavi kanı olan gerçek bir canlı yaşadığını biliyor muydunuz? "
            "Ahtapotların iki kalbi sadece solungaçlarına kan pompalarken üçüncü kalbi tüm vücuduna oksijen taşır. "
            "Kanlarında demir yerine bakır bazlı hemosiyanin bulunduğu için dondurucu derinliklerde bile hayatta kalmalarını sağlayan mavi bir kan dolaşır. "
            "Üstelik merkezi beyninin yanında sekiz kolunun her birinde bağımsız karar verebilen ayrı birer sinir merkezi vardır."
        ),
        "visual_keywords": [
            "octopus underwater coral",
            "deep sea marine life",
            "ocean reef tentacles",
            "blue underwater light",
        ],
    },
    {
        "topic": "Tarih",
        "title": "Kleopatra, Ay'a İniş'e Piramitlerden Daha Yakındı! #Shorts",
        "description": "Zaman algımızı altüst eden Kleopatra ve Mısır Piramitleri gerçeği! #tarih #mısır #ilginçbilgiler #shorts",
        "hook": "Mısır Kraliçesi Kleopatra'nın yaşadığı dönemin, piramitlerin inşasından çok Ay'a ilk insanın ayak basmasına daha yakın olduğunu biliyor muydunuz?",
        "script_text": (
            "Mısır Kraliçesi Kleopatra'nın yaşadığı dönemin, piramitlerin inşasından çok Ay'a ilk insanın ayak basmasına daha yakın olduğunu biliyor muydunuz? "
            "Büyük Gize Piramidi milattan önce yaklaşık iki bin beş yüz altmış yılında tamamlandı. "
            "Kleopatra ise bundan tam iki bin beş yüz yıl sonra, milattan önce otuz yılında hayatını kaybetti. "
            "Kleopatra'nın ölümünden bin dokuz yüz altmış dokuzdaki Apollo on bir Ay görevine kadar geçen süre ise sadece iki bin yıldır!"
        ),
        "visual_keywords": [
            "egyptian pyramids desert",
            "moon landing astronaut",
            "ancient egypt hieroglyphs",
            "starry night desert",
        ],
    },
    {
        "topic": "Bilim",
        "title": "Hiç Bozulmayan 3 Bin Yıllık Antik Mısır Balı! #Shorts",
        "description": "Firavun mezarlarından çıkan 3000 yıllık bal neden hâlâ yenilebilir durumda? #bilim #tarih #ilginçbilgiler #shorts",
        "hook": "Üç bin yıl boyunca karanlık bir mezarda bekleyen bir yiyeceğin bugün bile bozulmadan yenebileceğini duymuş muydunuz?",
        "script_text": (
            "Üç bin yıl boyunca karanlık bir mezarda bekleyen bir yiyeceğin bugün bile bozulmadan yenebileceğini duymuş muydunuz? "
            "Arkeologlar Antik Mısır firavunlarının mezarlarını açtığında mühürlü küplerin içinde binlerce yıllık doğal bal buldu ve bal hâlâ yenilebilir durumdaydı. "
            "Bunun sırrı balın neredeyse hiç su içermemesi, yüksek asidik yapısı ve arıların eklediği özel enzimlerin bakteri üremesini tamamen durdurmasıdır. "
            "Kapağı hava almayacak şekilde kapalı tutulduğunda doğal bal kimyasal olarak asla bozulmayan nadir besinlerden biridir."
        ),
        "visual_keywords": [
            "golden honey jar",
            "honeycomb bees nature",
            "ancient egyptian tomb",
            "archaeology artifacts",
        ],
    },
    {
        "topic": "Bilim",
        "title": "Elmas Yağmurları Yağan Gezegenler: Neptün ve Uranüs! #Shorts",
        "description": "Neptün ve Uranüs'ün atmosferinde gerçekten elmas yağmuru mu yağıyor? #uzay #bilim #gezegenler #shorts",
        "hook": "Güneş sistemimizde gökyüzünden su yerine gerçek elmasların yağdığı iki dev gezegen olduğunu biliyor muydunuz?",
        "script_text": (
            "Güneş sistemimizde gökyüzünden su yerine gerçek elmasların yağdığı iki dev gezegen olduğunu biliyor muydunuz? "
            "Buz devleri Uranüs ve Neptün'ün derin atmosferlerinde korkunç bir basınç ve binlerce derecelik sıcaklık hakimdir. "
            "Bu ekstrem koşullar atmosferdeki metan gazını parçalayarak saf karbon atomlarını birbirine kenetler ve milyonlarca karatlık katı elmas kristallerine dönüştürür. "
            "Laboratuvar ortamında lazer deneyleriyle de kanıtlanan bu olay sonucunda oluşan elmaslar tıpkı dolu taneleri gibi gezegenin çekirdeğine doğru yağar."
        ),
        "visual_keywords": [
            "planet neptune space",
            "sparkling diamond crystal",
            "deep cosmos nebula",
            "blue ice planet",
        ],
    },
    {
        "topic": "Tarih",
        "title": "2 Bin Yıllık Antik Bilgisayar: Antikythera Düzeneği! #Shorts",
        "description": "Deniz dibindeki batıktan çıkan 2000 yıllık bronz bilgisayar bilim dünyasını nasıl şaşkına çevirdi? #tarih #bilim #arkeoloji #shorts",
        "hook": "Günümüzden tam iki bin yıl önce Antik Yunan'da gökyüzünü hesaplayan mekanik bir bilgisayar yapıldığını biliyor muydunuz?",
        "script_text": (
            "Günümüzden tam iki bin yıl önce Antik Yunan'da gökyüzünü hesaplayan mekanik bir bilgisayar yapıldığını biliyor muydunuz? "
            "Bin dokuz yüz bir yılında sünger avcıları Ege Denizi'ndeki bir Roma batığında paslanmış bronz dişlilerden oluşan gizemli bir kutu buldu. "
            "Röntgen taramalarıyla incelenen Antikythera Düzeneği'nin içinde otuzdan fazla hassas dişli çark olduğu ortaya çıktı. "
            "Bu inanılmaz cihaz Güneş ve Ay tutulmalarını on yıllar öncesinden günü gününe hesaplayabiliyordu ve benzer karmaşıklıkta bir mekanizma ancak bin dört yüz yıl sonra tekrar yapılabildi."
        ),
        "visual_keywords": [
            "ancient bronze gears clockwork",
            "underwater shipwreck ocean",
            "solar eclipse space",
            "museum artifact history",
        ],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Uzay Boşluğunda Metaller Kendi Kendine Kaynar! #Shorts",
        "description": "Soğuk kaynak (Cold Welding) uzay araçları için neden büyük bir tehlikedir? #uzay #fizik #bilim #shorts",
        "hook": "Uzay boşluğunda iki pürüzsüz metal parçasını birbirine değdirirseniz hiçbir ısı olmadan tek parça halinde kaynayacağını biliyor muydunuz?",
        "script_text": (
            "Uzay boşluğunda iki pürüzsüz metal parçasını birbirine değdirirseniz hiçbir ısı olmadan tek parça halinde kaynayacağını biliyor muydunuz? "
            "Dünya'da metallerin yüzeyinde havadaki oksijen sayesinde gözle görülmeyen ince bir oksit tabakası bulunur ve bu tabaka metallerin birleşmesini engeller. "
            "Ancak uzay vakumunda hava olmadığı için koruyucu tabaka bulunmaz ve aynı tür iki temiz metal temas ettiği anda atomlar hangi parçaya ait olduğunu ayırt edemez. "
            "Soğuk kaynak adı verilen bu doğa olayı yüzünden uydulardaki hareketli parçalar özel kaplamalarla korunmak zorundadır."
        ),
        "visual_keywords": [
            "satellite orbit earth",
            "astronaut spacewalk repair",
            "metal sparks engineering",
            "outer space stars",
        ],
    },
    {
        "topic": "Bilim",
        "title": "Muzlar Aslında Radyoaktiftir! #Shorts",
        "description": "Her gün yediğimiz muzun içinde neden doğal radyasyon bulunur? #bilim #sağlık #ilginçbilgiler #shorts",
        "hook": "Mutfağınızdaki masum bir muzun aslında ölçülebilir düzeyde radyasyon yaydığını duymuş muydunuz?",
        "script_text": (
            "Mutfağınızdaki masum bir muzun aslında ölçülebilir düzeyde radyasyon yaydığını duymuş muydunuz? "
            "Muz potasyum açısından son derece zengin bir meyvedir ve doğadaki potasyumun çok küçük bir kısmı doğal olarak radyoaktif olan Potasyum kırk izotopundan oluşur. "
            "Hatta nükleer fizikçiler günlük hayattaki çok düşük radyasyon miktarlarını anlatmak için Muz Eşdeğer Dozu adlı gayriresmi bir ölçü birimi bile kullanır. "
            "Elbette korkmanıza hiç gerek yok çünkü tehlikeli bir radyasyon dozuna ulaşmak için tek oturuşta on milyon muz yemeniz gerekirdi."
        ),
        "visual_keywords": [
            "yellow bananas fruit",
            "science laboratory microscope",
            "atomic physics visualization",
            "tropical banana tree",
        ],
    },
    {
        "topic": "Tarih",
        "title": "1908 Tunguska Patlaması: 80 Milyon Ağaç Bir Anda Yıkıldı! #Shorts",
        "description": "Sibirya semalarında krater bile bırakmadan patlayan gizemli göktaşı! #tarih #uzay #bilim #shorts",
        "hook": "Bin dokuz yüz sekiz yılında Sibirya'da krater bile açmadan seksen milyon ağacı aynı anda dümdüz eden dev patlamayı biliyor muydunuz?",
        "script_text": (
            "Bin dokuz yüz sekiz yılında Sibirya'da krater bile açmadan seksen milyon ağacı aynı anda dümdüz eden dev patlamayı biliyor muydunuz? "
            "Otuz Haziran sabahı gökyüzünde Güneş kadar parlak mavi bir ateş topu belirdi ve yerden sekiz kilometre yüksekte korkunç bir güçle infilak etti. "
            "Tunguska Olayı olarak tarihe geçen bu hava patlaması iki bin kilometrekarelik ormanı kibrit çöpü gibi devirdi ve şok dalgası Londra'daki sismograflardan bile ölçüldü. "
            "Eğer bu göktaşı Dünya'ya sadece dört saat daha geç çarpsaydı doğrudan kalabalık bir Avrupa kentinin üzerine düşebilirdi."
        ),
        "visual_keywords": [
            "meteor fireball sky",
            "pine forest aerial siberia",
            "asteroid approaching earth",
            "shockwave clouds sunset",
        ],
    },
    {
        "topic": "Bilim",
        "title": "Uzay Boşluğunda Hayatta Kalabilen Tek Canlı: Su Ayısı! #Shorts",
        "description": "Tardigradlar kaynar suya, radyasyona ve uzay vakumuna nasıl dayanıyor? #bilim #doğa #uzay #shorts",
        "hook": "Hem kaynar suda hem mutlak sıfıra yakın dondurucu soğukta hem de uzay boşluğunda yaşayabilen mikroskobik bir süper canlı tanıyor musunuz?",
        "script_text": (
            "Hem kaynar suda hem mutlak sıfıra yakın dondurucu soğukta hem de uzay boşluğunda yaşayabilen mikroskobik bir süper canlı tanıyor musunuz? "
            "Su ayısı olarak bilinen tardigradlar ölümcül bir tehlikeyle karşılaştığında vücudundaki suyun yüzde doksan dokuzunu dışarı atıp cam benzeri bir koruma kalkanına bürünür. "
            "Avrupa Uzay Ajansı bu canlıları korumasız şekilde açık uzay boşluğuna bıraktığında ölümcül kozmik radyasyona rağmen hayatta kalıp Dünya'ya döndüklerinde üremeye devam ettiler. "
            "Otuz yıl boyunca tek damla su ve yiyecek olmadan uyku modunda bekleyip yeniden canlanabiliyorlar."
        ),
        "visual_keywords": [
            "microscopic biology cells",
            "green moss forest",
            "outer space earth view",
            "laboratory petri dish",
        ],
    },
    {
        "topic": "Tarih",
        "title": "Uzaylılara Gönderilen Altın Mektup: Voyager Plağı! #Shorts",
        "description": "Güneş sistemini terk eden Voyager uzay aracındaki Altın Plak'ta Türkçe hangi mesaj var? #uzay #tarih #bilim #shorts",
        "hook": "Şu anda yıldızlararası karanlıkta ilerleyen Voyager uzay aracında uzaylılar için kaydedilmiş Türkçe bir ses mesajı olduğunu biliyor muydunuz?",
        "script_text": (
            "Şu anda yıldızlararası karanlıkta ilerleyen Voyager uzay aracında uzaylılar için kaydedilmiş Türkçe bir ses mesajı olduğunu biliyor muydunuz? "
            "Bin dokuz yüz yetmiş yedide fırlatılan Voyager ikizlerine Dünya dışı zeki yaşamın bir gün bulması umuduyla bakır üzeri altın kaplama birer plak yerleştirildi. "
            "Bu plağın içinde yağmur sesleri, insan kalp atışı, fotoğraflar ve elli beş farklı dilde selamlama kaydı bulunuyor. "
            "Türkçe kayıtta ise uzayın sonsuzluğuna şu sıcak cümle yankılanıyor: Sabah şerifleriniz hayrolsun ey dünyanın dışındaki varlıklar!"
        ),
        "visual_keywords": [
            "space probe deep space",
            "golden vinyl record",
            "milky way stars galaxy",
            "rocket launch night",
        ],
    },
    {
        "topic": "Bilim",
        "title": "Güneş Işığı Dünya'ya Gelene Kadar 8 Dakika Geçmiş Olur! #Shorts",
        "description": "Gökyüzüne baktığımızda aslında neden sürekli geçmişi görüyoruz? #fizik #uzay #bilim #shorts",
        "hook": "Şu anda Güneş aniden yok olsaydı Dünya'da yaşayan hiç kimsenin bunu sekiz dakika yirmi saniye boyunca fark etmeyeceğini biliyor muydunuz?",
        "script_text": (
            "Şu anda Güneş aniden yok olsaydı Dünya'da yaşayan hiç kimsenin bunu sekiz dakika yirmi saniye boyunca fark etmeyeceğini biliyor muydunuz? "
            "Işık saniyede üç yüz bin kilometre gibi akılalmaz bir hızla hareket etse bile Güneş ile Dünya arasındaki yüz elli milyon kilometrelik mesafeyi aşması zaman alır. "
            "Bu yüzden yüzünüze vuran her Güneş ışığı aslında Güneş'ten sekiz dakika önce yola çıkmıştır. "
            "Gece gökyüzündeki yıldızlara baktığınızda ise binlerce yıl öncesinin görüntüsünü izleyen canlı bir zaman makinesine dönüşürsünüz."
        ),
        "visual_keywords": [
            "sunlight rays clouds",
            "glowing sun solar flare",
            "night sky milky way",
            "earth sunrise space",
        ],
    },
    {
        "topic": "Tarih",
        "title": "Pompeii'yi Saniyeler İçinde Donduran Yanardağ Felaketi! #Shorts",
        "description": "MS 79 yılında Vezüv Yanardağı Roma kenti Pompeii'yi nasıl zaman kapsülüne çevirdi? #tarih #arkeoloji #ilginçbilgiler #shorts",
        "hook": "Koca bir Roma şehrinin tek bir günde altı metre volkanik külün altına gömülüp bin yedi yüz yıl boyunca unutulduğunu biliyor muydunuz?",
        "script_text": (
            "Koca bir Roma şehrinin tek bir günde altı metre volkanik külün altına gömülüp bin yedi yüz yıl boyunca unutulduğunu biliyor muydunuz? "
            "Milattan sonra yetmiş dokuz yılında İtalya'daki Vezüv Yanardağı korkunç bir gürültüyle patladığında gökyüzüne otuz kilometre yüksekliğinde kor bir kül sütunu püskürttü. "
            "Ardından gelen kavurucu piroklastik akıntılar Pompeii kentini öylesine hızlı kapladı ki fırındaki ekmeklerden duvar yazılarına kadar her şey olduğu gibi korundu. "
            "Yüzyıllar sonra kazılar başladığında antik kentin günlük yaşamı adeta dondurulmuş bir zaman kapsülü gibi gün yüzüne çıktı."
        ),
        "visual_keywords": [
            "volcano eruption lava smoke",
            "ancient roman ruins columns",
            "archaeology stone street",
            "dramatic dark clouds",
        ],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Dünya'daki Ağaç Sayısı Samanyolu'ndaki Yıldızlardan Fazladır! #Shorts",
        "description": "Bilim insanlarının uydu verileriyle yaptığı şaşırtıcı ağaç ve yıldız karşılaştırması! #doğa #uzay #bilim #shorts",
        "hook": "Dünya üzerindeki ağaçların sayısının koca Samanyolu Galaksisi'ndeki tüm yıldızlardan katbekat fazla olduğunu söylesem inanır mıydınız?",
        "script_text": (
            "Dünya üzerindeki ağaçların sayısının koca Samanyolu Galaksisi'ndeki tüm yıldızlardan katbekat fazla olduğunu söylesem inanır mıydınız? "
            "Astronomların hesaplamalarına göre içinde yaşadığımız Samanyolu Galaksisi'nde yüz milyar ile dört yüz milyar arasında yıldız bulunuyor. "
            "Ancak uydu görüntüleri ve saha ölçümleriyle yapılan küresel doğa araştırması gezegenimizde tam üç trilyon ağaç yaşadığını ortaya koydu. "
            "Yani mavi gezegenimizde Samanyolu'ndaki her bir yıldıza karşılık neredeyse on adet gerçek ağaç kök salmış durumda."
        ),
        "visual_keywords": [
            "green forest canopy aerial",
            "milky way galaxy night",
            "tall pine trees sunlight",
            "planet earth from space",
        ],
    },
    {
        "topic": "Tarih",
        "title": "Dünya'nın En Yüksek Sesli Patlaması: 1883 Krakatoa! #Shorts",
        "description": "4800 kilometre uzaktan duyulan ve Dünya'nın çevresini 4 kez dolaşan ses dalgası! #tarih #doğa #bilim #shorts",
        "hook": "Tarihte kaydedilmiş en yüksek sesin dört bin sekiz yüz kilometre uzaktan bile top atışı gibi duyulduğunu biliyor muydunuz?",
        "script_text": (
            "Tarihte kaydedilmiş en yüksek sesin dört bin sekiz yüz kilometre uzaktan bile top atışı gibi duyulduğunu biliyor muydunuz? "
            "Bin sekiz yüz seksen üç yılında Endonezya'daki Krakatoa Yanardağı patladığında ortaya çıkan ses dalgası altmış beş kilometre uzaktaki denizcilerin kulak zarlarını patlattı. "
            "Bu korkunç gürültü Hint Okyanusu'nu aşarak Avustralya'dan bile net biçimde duyuldu. "
            "Üstelik patlamanın yarattığı atmosferik basınç dalgası o kadar güçlüydü ki Dünya'nın çevresini tam dört kez dolaşarak barometre kayıtlarına geçti."
        ),
        "visual_keywords": [
            "volcanic island ocean smoke",
            "stormy ocean giant waves",
            "lightning volcano night",
            "sunset red sky clouds",
        ],
    },
]


def load_dotenv_file(dotenv_path: Path = Path(".env")) -> None:
    """Harici kütüphane gerektirmeden yerel `.env` dosyasındaki ortam değişkenlerini yükler."""
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_recent_titles() -> list[str]:
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data[-25:] if isinstance(data, list) else []
    except Exception:
        return []


def save_recent_title(title: str) -> None:
    history = load_recent_titles()
    if title not in history:
        history.append(title)
    HISTORY_FILE.write_text(
        json.dumps(history[-25:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def classify_content_niche(topic: str, title: str, script_text: str = "") -> str:
    """Senaryonun alt nişini ('Uzay', 'Tarih', 'Bilim') anahtar kelimelerle tespit eder."""
    combined = f"{topic} {title} {script_text}".lower()
    space_tokens = (
        "uzay", "gezegen", "güneş", "venüs", "neptün", "uranüs", "yıldız",
        "nötron", "voyager", "astronot", "galaksi", "samanyolu", "ay'a", "tunguska",
    )
    history_tokens = (
        "tarih", "savaş", "antik", "napolyon", "göbeklitepe", "pompeii",
        "kleopatra", "firavun", "mısır", "antikythera", "zanzibar", "krakatoa", "emu",
    )
    if any(tok in combined for tok in space_tokens):
        return "Uzay"
    if any(tok in combined for tok in history_tokens):
        return "Tarih"
    return "Bilim"


def resolve_affiliate_offer(topic: str, title: str, script_text: str = "") -> tuple[str, str]:
    """
    Faz 9 Monetizasyon Tuzağı: Videonun konusuna göre tıklanma oranı yüksek
    affiliate linkini ve açıklamanın en üstüne yerleşecek harekete geçirici metni (CTA) üretir.
    """
    niche = classify_content_niche(topic, title, script_text)
    default_url = os.environ.get("AFFILIATE_URL_DEFAULT", "").strip() or DEFAULT_AFFILIATE_FALLBACK_URL

    if niche == "Uzay":
        url = os.environ.get("AFFILIATE_URL_SPACE", "").strip() or default_url
        return url, f"Bu teleskobu incele: {url}"
    if niche == "Tarih":
        url = os.environ.get("AFFILIATE_URL_HISTORY", "").strip() or default_url
        return url, f"Bu kitabı oku: {url}"

    url = os.environ.get("AFFILIATE_URL_SCIENCE", "").strip() or default_url
    return url, f"Bu bilim setini incele: {url}"


def load_analytics_feedback(feedback_path: Path = ANALYTICS_FEEDBACK_FILE) -> dict[str, Any]:
    """Faz 9 Analitik Geri Bildirim Döngüsü: analytics_scraper.js tarafından üretilen veriyi okur."""
    if not feedback_path.exists():
        return {}
    try:
        data = json.loads(feedback_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def fetch_wikipedia_grounding(recent_titles: list[str]) -> dict[str, str] | None:
    """Ücretsiz Türkçe Wikipedia REST API'den doğrulanmış gerçek bilgi özeti çeker."""
    candidates = [t for t in WIKI_SEED_TOPICS if not any(t[:6].lower() in r.lower() for r in recent_titles)]
    chosen_slug = random.choice(candidates if candidates else WIKI_SEED_TOPICS)
    try:
        url = f"https://tr.wikipedia.org/api/rest_v1/page/summary/{quote(chosen_slug)}"
        resp = requests.get(
            url,
            headers={"User-Agent": "AIShortsFactory/1.0 (Automated Educational Content Engine)"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            extract = data.get("extract", "").strip()
            title = data.get("title", chosen_slug)
            if len(extract) > 80:
                return {"title": title, "extract": extract}
    except Exception:
        pass
    return None


def sanitize_for_tts(text: str) -> str:
    """Metni `edge-tts` Türkçe diksiyonuna uygun, pürüzsüz okunabilir hale getirir."""
    cleaned = text.strip()
    cleaned = re.sub(r"\[[^\]]*\]", " ", cleaned)
    cleaned = re.sub(r"[*_#`~>]+", "", cleaned)
    replacements = [
        (r"\bM\.Ö\.\s*", "milattan önce "),
        (r"\bMÖ\b", "milattan önce"),
        (r"\bM\.S\.\s*", "milattan sonra "),
        (r"\bMS\b", "milattan sonra"),
        (r"\byy\.", "yüzyıl"),
        (r"%(\d+)", r"yüzde \1"),
        (r"(\d)\.(\d{3})\b", r"\1\2"),
        (r"(\d),(\d{3})\b", r"\1\2"),
        (r"(\d)\.(\d)", r"\1,\2"),
    ]
    for pattern, repl in replacements:
        cleaned = re.sub(pattern, repl, cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def build_llm_prompts(
    concept: str,
    recent_titles: list[str],
    wiki_fact: dict[str, str] | None = None,
    analytics_feedback: dict[str, Any] | None = None,
) -> tuple[str, str]:
    avoid_clause = (
        f"Daha önce işlenen şu başlıklardan KESİNLİKLE farklı olmalı: {', '.join(recent_titles[-8:])}."
        if recent_titles
        else ""
    )

    feedback_clause = ""
    if analytics_feedback:
        directive = str(analytics_feedback.get("optimization_directive", "")).strip()
        discarded = analytics_feedback.get("discarded_topics") or []
        if directive:
            feedback_clause += f"\nANALİTİK OPTİMİZASYON EMRİ: {directive}\n"
        if discarded:
            feedback_clause += f"Düşük performans nedeniyle şu konuları Tercih ETME: {', '.join(str(x) for x in discarded)}.\n"

    fact_block = ""
    if wiki_fact:
        fact_block = (
            f"\nDOĞRULANMIŞ KAYNAK BİLGİ ({wiki_fact['title']}):\n"
            f'"{wiki_fact["extract"]}"\n'
            "Senaryoyu bu doğrulanmış bilgilere dayandır; kesinlikle uydurma isim veya tarih ekleme.\n"
        )

    system_prompt = (
        "Sen milyonlarca izlenen Türkçe YouTube Shorts belgesel kanallarının baş senaristisin. "
        "Görevin 'İlginç Bilgiler / Tarih / Bilim' konseptinde %100 gerçek, doğrulanabilir, "
        "izleyiciyi ilk 3 saniyede yakalayan ve son saniyeye kadar ekranda tutan bir Shorts paketi üretmektir. "
        "Sen bir 'algoritma hacker'ısın: metnin yanında KAPAK (thumbnail) ve ETKİLEŞİM (CTA + hashtag) "
        "metadatasını da üretirsin.\n\n"
        "KESİN KURALLAR:\n"
        "1. HOOK (İlk Cümle - ilk 3 saniye): Asla 'Merhaba' deme. Doğrudan beyni sarsan bir soru veya "
        "şok edici istatistik olmalı; kaydırmayı anında durduracak merak uyandırıcı bir gerçek veya soru.\n"
        "2. UZUNLUK: `script_text` alanı TAM OLARAK 60 ile 80 Türkçe kelime arasında olmalı (yaklaşık 30-45 saniye).\n"
        "3. CTA (Call to Action): `cta_line` alanı, videonun son cümlesi gibi izleyiciyi yorum yapmaya veya "
        "abone olmaya ZORLAYAN tek bir cümle olmalı. "
        "Örnek: 'Sen olsan ne yapardın? Yorumlara yaz!' veya 'Bunu bilen var mı? Abone ol, birlikte şaşıralım!'\n"
        "4. THUMBNAIL PROMPT: `thumbnail_prompt` alanı, bu videonun YouTube KAPAĞI olacak; yüksek kontrastlı, "
        "sinematik, DIKEY (9:16) bir görsel için İNGİLİZCE bir 'image generation prompt' olmalı. "
        "Örnek: 'Cinematic vertical shot of Napoleon running from giant rabbits, hyper-realistic, dramatic lighting, 8k'. "
        "Görselde yazı/metin olmasın, odak tek bir güçlü sahnede olsun.\n"
        "5. HASHTAGLAR: `viral_hashtags` alanında SADECE 3 adet, çok spesifik ve trend hashtag üret "
        "(örn. '#göbeklitepe', '#napolyon', '#marianacukuru'). Genel etiketler ('#bilim', '#tarih') yazma; "
        "#shorts zaten sistemde var, onu da yazma.\n"
        "6. Dil ve Diksiyon: Çok doğal, akıcı ve vurucu bir belgesel Türkçesi kullan. Emoji, hashtag, markdown veya "
        "sahne notu YAZMA. Kısaltmaları ('milattan önce' gibi) açık yaz.\n"
        "7. Görsel Arama Kelimeleri: Faz 3'te Pexels/Pixabay dikey stok video aramasında kullanılmak üzere "
        "konuya uygun 4 adet İngilizce sinematik arama terimi (`visual_keywords`) üret.\n"
        "8. Yalnızca geçerli bir JSON nesnesi döndür."
    )

    user_prompt = (
        f"Konsept: {concept}.\n"
        f"{avoid_clause}\n"
        f"{feedback_clause}"
        f"{fact_block}\n"
        "Lütfen tam olarak aşağıdaki JSON şemasında üretim yap:\n"
        "{\n"
        '  "topic": "Tarih veya Bilim veya İlginç Bilgiler",\n'
        '  "title": "Merak uyandıran çarpıcı Türkçe başlık (Maks 60 karakter) #Shorts",\n'
        '  "description": "Kısa Türkçe SEO açıklaması",\n'
        '  "hook": "Metnin ilk cümlesi olan 3 saniyelik kanca",\n'
        '  "script_text": "Hook cümlesiyle başlayan, 60-80 kelimelik tam seslendirme metni",\n'
        '  "cta_line": "Videonun sonundaki etkileşim çağrısı cümlesi",\n'
        '  "thumbnail_prompt": "İngilizce, dikey, yüksek kontrastlı kapak görseli promptu",\n'
        '  "viral_hashtags": ["#spesifik1", "#spesifik2", "#spesifik3"],\n'
        '  "visual_keywords": ["english keyword 1", "english keyword 2", "english keyword 3", "english keyword 4"]\n'
        "}"
    )
    return system_prompt, user_prompt


def extract_json_object(raw_text: str) -> dict[str, Any]:
    """LLM çıktısından güvenli şekilde JSON nesnesini ayıklar."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM yanıtında geçerli JSON nesnesi bulunamadı.")

    return json.loads(cleaned[start : end + 1])


# --- FAZ 11: Viral Metadata yardimcilari (CTA, kapak promptu, trend hashtag) ---
FALLBACK_CTA_LINES = [
    "Sen olsan ne yapardın? Yorumlara yaz!",
    "Bunu bilen var mı? Abone ol, birlikte şaşıralım!",
    "Sence gerçek mi? Yorumlarda tartışalım!",
    "Daha fazlası için abone olmayı unutma!",
    "İlginç değil mi? Yorumlarda paylaş!",
]

_TR_STOPWORDS = {
    "bir", "bu", "ve", "ile", "için", "daha", "çok", "ama", "ancak", "her", "gibi",
    "değil", "olan", "oldu", "ise", "sonra", "önce", "kadar", "göre", "yerine",
    "nasıl", "neden", "kimin", "hangi", "şey", "zaman", "yıl", "yılında", "sirada",
    "tarih", "bilim", "ilginç", "bilgiler", "shorts", "video", "videosu",
    "eski", "daha", "bin", "yıl", "yıllık", "gün", "dakika", "saniye", "saat",
    "şey", "yer", "göre", "kadar", "sonra", "önce", "değil", "olan", "veya",
    "biliyor", "musunuz", "vardı", "var", "yeni", "en", "çok", "tüm",
}


def tr_lower(text: str) -> str:
    """Hibrit kucuk harf: Turkce karakter iceren kelimelerde 'I' -> 'ı', 'İ' -> 'i';
    Latin (MARIANA gibi) adlarda Python varsayilani kullanilir."""
    s = str(text or "")
    if any(ch in s for ch in "ğüşıöç"):
        return s.replace("İ", "i").replace("I", "ı").lower()
    return s.lower()


def sanitize_hashtag(raw: str) -> str:
    """'Göbeklitepe' / '#Göbeklitepe' -> '#göbeklitepe' (Türkçe karakterler korunur)."""
    text = str(raw or "").strip().lstrip("#")
    text = re.sub(r"[^0-9A-Za-zÇĞİÖŞÜçğıöşü]", "", text)
    if not text:
        return ""
    if text.isdigit():
        return ""
    return "#" + tr_lower(text)


def strip_hashtags(text: str) -> str:
    """Açıklamadaki eski hashtag'leri temizler (YouTube 3'ten fazla hashtag'i yok sayar)."""
    cleaned = re.sub(r"#[0-9A-Za-zÇĞİÖŞÜçğıöşü_]+", " ", str(text or ""))
    return re.sub(r"\s{2,}", " ", cleaned).strip()


# FAZ 11: Yedek senaryo havuzu icin elle kurulmus SPESIFIK hashtag haritasi
# (anahtar: baslikta aranan ayirt edici parca -> 3 adet trend hashtag)
FALLBACK_VIRAL_TAGS: dict[str, list[str]] = {
    "en kısa savaşı": ["#zanzibarsavaşı", "#kısasavaş", "#tarih"],
    "venüs": ["#venüs", "#gezegenler", "#uzay"],
    "denizanası": ["#denizanası", "#ölümsüzhayvan", "#turkuaz"],
    "tavşan ordusu": ["#napolyon", "#tavşanordusu", "#napoleonbonapart"],
    "göbeklitepe": ["#göbeklitepe", "#şıanlıurfa", "#antiktapınak"],
    "mariana çukuru": ["#marianacukuru", "#okyanusderinliği", "#bilim"],
    "uzayda ağlarsanız": ["#uzay", "#gözyaşı", "#astrofizik"],
    "devekuşlarına": ["#devekuşu", "#avustralya", "#tarih"],
    "nötron yıldızı": ["#nötronyıldızı", "#nükleerfizik", "#bilim"],
    "mavi kanlı": ["#ahtapot", "#derincanlıları", "#okyanus"],
    "kleopatra": ["#kleopatra", "#ay inişi", "#tarih"],
    "antik mısır balı": ["#mısırbalı", "#antikmisır", "#arkeoloji"],
    "elmas yağmurları": ["#neptün", "#uranüs", "#elmasyağmuru"],
    "antikythera": ["#antikythera", "#antikbilgisayar", "#arkeoloji"],
    "metaller kendi kendine": ["#fizik", "#metal", "#uzay"],
    "muzlar": ["#muz", "#radyoaktif", "#besin"],
    "tunguska": ["#tunguska", "#volkan", "#tarih"],
    "su ayısı": ["#suayısı", "#uzayyaşamı", "#bilim"],
    "voyager": ["#voyager", "#uzaylılara", "#altınmektup"],
    "güneş ışığı": ["#güneş", "#ışık", "#fizik"],
    "pompeii": ["#pompeii", "#yanardağ", "#arkeoloji"],
    "ağaç sayısı": ["#ağaç", "#samanyolu", "#ekoloji"],
    "krakatoa": ["#krakatoa", "#volkan", "#tarih"],
}


def lookup_curated_hashtags(title: str) -> list[str]:
    """Faz 11: Basliga gore elle secilmis spesifik hashtag seti (varsa)."""
    low = tr_lower(title)
    for key, tags in FALLBACK_VIRAL_TAGS.items():
        if key in low:
            return [sanitize_hashtag(t) for t in tags if sanitize_hashtag(t)]
    return []



def derive_viral_hashtags(
    title: str,
    topic: str,
    script_text: str = "",
    provided: Any = None,
) -> list[str]:
    """Faz 11: Tam olarak 3 adet SPESIFIK trend hashtag uretir (YouTube limiti = 3).

    Oncelik sirasi:
      1) LLM/LLM-benzeri taraftan gelen `provided` listesi (varsa temizlenerek)
      2) Baslik + metindeki OZNE (proper noun) adlari (skorlanarak)
      3) Konu (topic) ve metindeki alan kelimeleri ile tamamlama
    """
    tags: list[str] = []

    if isinstance(provided, list):
        for item in provided:
            tag = sanitize_hashtag(str(item))
            if tag and tag not in tags:
                tags.append(tag)
            if len(tags) >= 3:
                break

    if len(tags) < 3:
        curated = lookup_curated_hashtags(title)
        for tag in curated:
            if tag and tag not in tags:
                tags.append(tag)
            if len(tags) >= 3:
                break

    if len(tags) < 3:
        title_clean = str(title or "").replace("#Shorts", " ")
        script_clean = str(script_text or "")
        words = re.findall(r"[0-9A-Za-zÇĞİÖŞÜçğıöşü]+", title_clean + " " + script_clean)
        title_words = set(re.findall(r"[0-9A-Za-zÇĞİÖŞÜçğıöşü]+", title_clean))

        scored: list[tuple[float, str]] = []
        for word in words:
            if len(word) < 4 or word.lower() in _TR_STOPWORDS:
                continue
            if not word[0].isupper():
                continue
            score = 0.0
            if word in title_words:
                score += 2.0
            if len(word) >= 6:
                score += 1.0
            if len(word) >= 9:
                score += 0.5
            if word.lower() in {"tarih", "bilim", "ilginç"}:
                score -= 2.0
            scored.append((score, word))

        seen_words: set[str] = set()
        for _, word in sorted(scored, key=lambda item: -item[0]):
            key = word.lower()
            if key in seen_words:
                continue
            seen_words.add(key)
            tag = sanitize_hashtag(word)
            if tag and tag not in tags:
                tags.append(tag)
            if len(tags) >= 3:
                break

    if len(tags) < 3:
        for word in re.findall(r"[0-9A-Za-zÇĞİÖŞÜçğıöşü]+", str(title or "").replace("#Shorts", " ")):
            if len(word) < 4 or word.lower() in _TR_STOPWORDS:
                continue
            tag = sanitize_hashtag(word)
            if tag and tag not in tags:
                tags.append(tag)
            if len(tags) >= 3:
                break

    if len(tags) < 3:
        # Metindeki alan kelimeleri (uzay, gezegen, tapinak, savaş...)
        for word in re.findall(r"[0-9A-Za-zÇĞİÖŞÜçğıöşü]+", str(script_text or "")):
            if len(word) < 6 or word.lower() in _TR_STOPWORDS:
                continue
            tag = sanitize_hashtag(word)
            if tag and tag not in tags:
                tags.append(tag)
            if len(tags) >= 3:
                break

    if len(tags) < 3:
        niche = sanitize_hashtag(topic or "")
        if niche and niche not in tags:
            tags.append(niche)

    if len(tags) < 3:
        for filler in ("#tarih", "#bilim", "#ilginçbilgiler"):
            if filler not in tags:
                tags.append(filler)
            if len(tags) >= 3:
                break

    return tags[:3]


def build_thumbnail_prompt(topic: str, title: str, visual_keywords: Any = None) -> str:
    """Faz 11: Kapak icin INGILIZCE, dikey, yuksek kontrastli image-generation promptu."""
    keywords = [str(k).strip() for k in (visual_keywords or []) if str(k).strip()]
    subject = ", ".join(keywords[:2]) if keywords else "dramatic cinematic historical scene"
    niche = str(topic or "documentary").lower()
    return (
        f"Cinematic vertical 9:16 shot of {subject}, hyper-realistic, dramatic lighting, "
        f"high contrast, vivid saturated colors, ultra detailed, 8k, {niche} documentary style, "
        f"no text, no watermark"
    )


def build_fallback_cta(title: str) -> str:
    """Faz 11: LLM yokken (yedek senaryo havuzu) kullanilan deterministik CTA."""
    index = sum(ord(ch) for ch in str(title or "")) % len(FALLBACK_CTA_LINES)
    return FALLBACK_CTA_LINES[index]


def validate_and_normalize_scenario(raw_data: dict[str, Any], provider_name: str) -> dict[str, Any]:
    """LLM'den dönen JSON'u doğrular, TTS için temizler ve kelime sınırlarını kontrol eder."""
    script_text = sanitize_for_tts(str(raw_data.get("script_text", "")))
    words = script_text.split()
    word_count = len(words)

    if word_count < 55 or word_count > 95:
        raise ValueError(
            f"{provider_name} hedef kelime aralığı (60-80) dışında metin üretti ({word_count} kelime)."
        )

    title = str(raw_data.get("title", "Tarihin Gizemli Gerçeği #Shorts")).strip()
    if "#shorts" not in title.lower():
        title = f"{title[:85].rstrip()} #Shorts"

    keywords = raw_data.get("visual_keywords") or ["ancient history", "archaeology discovery", "cinematic museum"]
    if not isinstance(keywords, list) or not keywords:
        keywords = ["ancient history", "archaeology discovery", "cinematic museum"]

    topic_val = str(raw_data.get("topic", "Tarih")).strip()
    raw_desc = str(
        raw_data.get("description", f"{title} #ilginçbilgiler #tarih #bilim #shorts")
    ).strip()

    # --- FAZ 11: Viral metadata (CTA / kapak promptu / trend hashtag) ---
    cta_line = sanitize_for_tts(str(raw_data.get("cta_line", ""))).strip()
    if not cta_line:
        cta_line = build_fallback_cta(title)
    cta_line = cta_line[:180].strip()

    thumbnail_prompt = str(raw_data.get("thumbnail_prompt", "")).strip()
    if not thumbnail_prompt:
        thumbnail_prompt = build_thumbnail_prompt(topic_val, title, keywords)

    viral_hashtags = derive_viral_hashtags(
        title, topic_val, script_text, raw_data.get("viral_hashtags")
    )

    # Aciklamada eski hashtag'leri temizle (YouTube 3'ten fazla hashtag'i yok sayar)
    base_desc = strip_hashtags(raw_desc) or title

    affiliate_link, affiliate_cta = resolve_affiliate_offer(topic_val, title, script_text)

    # SIRA: [1] Affiliate CTA + link (Faz 9: en ustte) -> [2] Viral CTA -> [3] Govde -> [4] Hashtag'ler
    blocks = [affiliate_cta, cta_line, base_desc, " ".join(viral_hashtags)]
    enriched_desc = "\n\n".join([b for b in blocks if b]).strip()

    return {
        "provider": provider_name,
        "topic": topic_val,
        "title": title[:100],
        "description": enriched_desc,
        "affiliate_link": affiliate_link,
        "affiliate_cta": affiliate_cta,
        "cta_line": cta_line,
        "thumbnail_prompt": thumbnail_prompt,
        "viral_hashtags": viral_hashtags,
        "hook": sanitize_for_tts(str(raw_data.get("hook", ""))) or script_text.split(".")[0],
        "script_text": script_text,
        "word_count": word_count,
        "visual_keywords": [str(k).strip() for k in keywords[:6] if str(k).strip()],
    }


def call_groq_llm(system_prompt: str, user_prompt: str, api_key: str) -> dict[str, Any]:
    """Birincil Sağlayıcı: Groq Cloud Free API (`llama-3.3-70b-versatile`)."""
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.65,
            "max_tokens": 700,
            "response_format": {"type": "json_object"},
        },
        timeout=25,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return validate_and_normalize_scenario(extract_json_object(content), "groq:llama-3.3-70b-versatile")


def call_gemini_llm(system_prompt: str, user_prompt: str, api_key: str) -> dict[str, Any]:
    """İkincil Alternatif: Google Gemini Free API (`gemini-2.5-flash`)."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    resp = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.65,
                "responseMimeType": "application/json",
            },
        },
        timeout=25,
    )
    resp.raise_for_status()
    candidates = resp.json().get("candidates", [])
    content = candidates[0]["content"]["parts"][0]["text"]
    return validate_and_normalize_scenario(extract_json_object(content), "gemini:gemini-2.5-flash")


def pick_fallback_scenario(
    recent_titles: list[str],
    channel_id: str = "1",
    analytics_feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Yedek Senaryo Havuzu: 15dk benzersizlik garantisi + Faz 9 analitik kazanan konu (%80 ağırlık) seçimi."""
    effective_ch = str(channel_id or os.environ.get("MATRIX_CHANNEL_ID") or "1").strip() or "1"
    pool = list(FALLBACK_SCENARIOS)

    winning_topic = str((analytics_feedback or {}).get("winning_topic", "")).strip()
    discarded_topics = {str(x).strip() for x in ((analytics_feedback or {}).get("discarded_topics") or [])}
    boost_active = bool((analytics_feedback or {}).get("boost_active", False))

    if discarded_topics:
        filtered = [
            item for item in pool
            if classify_content_niche(item["topic"], item["title"], item["script_text"]) not in discarded_topics
        ]
        if len(filtered) >= 10:
            pool = filtered

    if effective_ch.isdigit():
        now_utc = datetime.now(timezone.utc)
        slot_15m = int(now_utc.timestamp()) // 900
        # Analitik boost aktifse 5 zaman diliminin 4'ünde (%80) kazanan niş havuzuna öncelik ver
        if boost_active and winning_topic and (slot_15m % 5 != 4):
            winners = [
                item for item in pool
                if classify_content_niche(item["topic"], item["title"], item["script_text"]) == winning_topic
            ]
            if winners:
                w_slot = (slot_15m * 3 + (int(effective_ch) - 1)) % len(winners)
                return validate_and_normalize_scenario(
                    winners[w_slot], f"local-fallback-analytics-boost-{winning_topic.lower()}-{effective_ch}"
                )

        slot = (slot_15m * 10 + (int(effective_ch) - 1)) % len(pool)
        return validate_and_normalize_scenario(pool[slot], f"local-fallback-matrix-{effective_ch}")

    unused = [item for item in pool if item["title"] not in recent_titles]
    chosen = random.choice(unused if unused else pool)
    return validate_and_normalize_scenario(chosen, "local-fallback-pool")


def generate_scenario(
    concept: str = "İlginç Bilgiler ve Tarih",
    force_fallback: bool = False,
    channel_id: str = "1",
) -> dict[str, Any]:
    """Çok katmanlı hata toleranslı, 15dk tohumlamalı ve Faz 9 analitik beslemeli senaryo üretim yöneticisi."""
    effective_channel_id = str(channel_id or os.environ.get("MATRIX_CHANNEL_ID") or "1").strip() or "1"
    now = datetime.now(timezone.utc)
    unique_seed_str = f"{effective_channel_id}_{now.strftime('%j_%H_%M')}"
    unique_hash = int(hashlib.md5(unique_seed_str.encode()).hexdigest(), 16)
    random.seed(unique_hash)
    print(f"[INFO] Faz 8 Benzersizlik Tohumu (Seed): {unique_seed_str} (kanal={effective_channel_id})")

    recent_titles = load_recent_titles()
    analytics_feedback = load_analytics_feedback()
    if analytics_feedback.get("optimization_directive"):
        print(f"[INFO] Faz 9 Analitik Geri Bildirim Aktif: {analytics_feedback['optimization_directive']}")

    if force_fallback:
        print("[BİLGİ] '--force-fallback' aktif: Yerel yedek senaryo havuzu kullanılıyor.")
        scenario = pick_fallback_scenario(
            recent_titles, channel_id=effective_channel_id, analytics_feedback=analytics_feedback
        )
        save_recent_title(scenario["title"])
        return scenario

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    gemini_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()

    if groq_key or gemini_key:
        wiki_fact = fetch_wikipedia_grounding(recent_titles)
        if wiki_fact:
            print(f"[KAYNAK] Doğrulanmış Wikipedia referansı alındı: {wiki_fact['title']}")
        system_prompt, user_prompt = build_llm_prompts(
            concept, recent_titles, wiki_fact=wiki_fact, analytics_feedback=analytics_feedback
        )

        # 1. Katman: Groq API (Birincil Tercih)
        if groq_key:
            try:
                print("[LLM] Birincil sağlayıcı deneniyor: Groq API (llama-3.3-70b-versatile)...")
                scenario = call_groq_llm(system_prompt, user_prompt, groq_key)
                save_recent_title(scenario["title"])
                return scenario
            except Exception as exc:
                print(f"[UYARI] Groq API hatası/kotası ({exc}); ikinci katmana geçiliyor...", file=sys.stderr)

        # 2. Katman: Google Gemini API (İkincil Alternatif)
        if gemini_key:
            try:
                print("[LLM] İkincil sağlayıcı deneniyor: Google Gemini API (gemini-2.5-flash)...")
                scenario = call_gemini_llm(system_prompt, user_prompt, gemini_key)
                save_recent_title(scenario["title"])
                return scenario
            except Exception as exc:
                print(f"[UYARI] Gemini API hatası/kotası ({exc}); yedek senaryo havuzuna geçiliyor...", file=sys.stderr)
    else:
        print(
            "[TOLERANS] GROQ_API_KEY / GEMINI_API_KEY tanımlı değil; "
            "sistem çökmeden doğrulanmış yedek (fallback) senaryo havuzunu devreye alıyor..."
        )

    # 3. Katman: Garantili Yedek Havuz (Asla çökmez)
    try:
        scenario = pick_fallback_scenario(
            recent_titles, channel_id=effective_channel_id, analytics_feedback=analytics_feedback
        )
        save_recent_title(scenario["title"])
        return scenario
    except Exception as exc:
        raise RuntimeError(f"Kritik hata: Yedek senaryo havuzu bile yüklenemedi: {exc}") from exc


def format_srt_timestamp(ms: float) -> str:
    total_ms = max(0, int(round(ms)))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def build_dynamic_shorts_srt(word_timestamps: list[dict[str, Any]], words_per_cue: int = 3) -> str:
    """Kelime bazlı zaman damgalarını Shorts temposuna uygun 2-3 kelimelik altyazı bloklarına dönüştürür."""
    if not word_timestamps:
        return ""

    cues: list[str] = []
    chunk: list[dict[str, Any]] = []

    for item in word_timestamps:
        chunk.append(item)
        ends_sentence = str(item["word"]).endswith((".", "!", "?", ",", ":", ";"))
        if len(chunk) >= words_per_cue or ends_sentence:
            start_str = format_srt_timestamp(chunk[0]["start_ms"])
            end_str = format_srt_timestamp(chunk[-1]["end_ms"])
            text_line = " ".join(w["word"] for w in chunk)
            idx = len(cues) + 1
            cues.append(f"{idx}\n{start_str} --> {end_str}\n{text_line}\n")
            chunk = []

    if chunk:
        start_str = format_srt_timestamp(chunk[0]["start_ms"])
        end_str = format_srt_timestamp(chunk[-1]["end_ms"])
        text_line = " ".join(w["word"] for w in chunk)
        idx = len(cues) + 1
        cues.append(f"{idx}\n{start_str} --> {end_str}\n{text_line}\n")

    return "\n".join(cues)


def probe_audio_duration(audio_path: Path) -> float:
    """`ffprobe` kullanarak üretilen MP3 dosyasının tam süresini saniye cinsinden ölçer."""
    try:
        res = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return round(float(res.stdout.strip()), 3)
    except Exception:
        return 0.0


async def _edge_tts_generate(
    text: str,
    voice: str,
    rate: str,
    audio_out: Path,
) -> list[dict[str, Any]]:
    """`edge-tts` ile seslendirir ve milisaniye bazlı `WordBoundary` verilerini toplar."""
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        boundary="WordBoundary",
    )

    word_timestamps: list[dict[str, Any]] = []
    raw_words = text.split()

    with audio_out.open("wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start_ms = round(chunk["offset"] / 10_000, 1)
                dur_ms = round(chunk["duration"] / 10_000, 1)
                word_timestamps.append(
                    {
                        "word": chunk["text"],
                        "start_ms": start_ms,
                        "end_ms": round(start_ms + dur_ms, 1),
                    }
                )

    if len(word_timestamps) == len(raw_words):
        for wt, orig_token in zip(word_timestamps, raw_words):
            wt["word"] = orig_token

    return word_timestamps


def _gtts_fallback_generate(text: str, audio_out: Path) -> list[dict[str, Any]]:
    """Yedek TTS: `edge-tts` erişilemezse `gTTS` + FFmpeg tempo filtresiyle ses üretir."""
    from gtts import gTTS

    tmp_raw = audio_out.with_suffix(".raw.mp3")
    tts = gTTS(text=text, lang="tr", slow=False)
    tts.save(str(tmp_raw))

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(tmp_raw),
            "-filter:a",
            "atempo=1.12",
            "-vn",
            str(audio_out),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    tmp_raw.unlink(missing_ok=True)

    duration_ms = probe_audio_duration(audio_out) * 1000.0
    words = text.split()
    total_chars = max(1, sum(len(w) for w in words))
    cursor_ms = 0.0
    word_timestamps: list[dict[str, Any]] = []
    for w in words:
        share_ms = duration_ms * (len(w) / total_chars)
        word_timestamps.append(
            {
                "word": w,
                "start_ms": round(cursor_ms, 1),
                "end_ms": round(cursor_ms + share_ms, 1),
            }
        )
        cursor_ms += share_ms
    return word_timestamps


def synthesize_voiceover(
    text: str,
    voice: str = "tr-TR-AhmetNeural",
    rate: str = "+4%",
    audio_out: Path = DEFAULT_AUDIO_OUT,
) -> tuple[str, float, list[dict[str, Any]]]:
    """Birincil `edge-tts`, hata halinde yedek `gTTS` ile seslendirme ve zaman damgası üretir."""
    try:
        print(f"[TTS] Birincil seslendirme başlatıldı: edge-tts ({voice}, hız={rate})...")
        word_timestamps = asyncio.run(_edge_tts_generate(text, voice, rate, audio_out))
        if not audio_out.exists() or audio_out.stat().st_size < 1024:
            raise RuntimeError("Üretilen ses dosyası boş veya geçersiz.")
        duration_sec = probe_audio_duration(audio_out)
        return f"edge-tts:{voice}", duration_sec, word_timestamps
    except Exception as exc:
        print(f"[UYARI] edge-tts hatası ({exc}); yedek TTS (gTTS) devreye alınıyor...", file=sys.stderr)
        word_timestamps = _gtts_fallback_generate(text, audio_out)
        duration_sec = probe_audio_duration(audio_out)
        return "gtts:tr-fallback", duration_sec, word_timestamps


def run_content_pipeline(
    concept: str = "İlginç Bilgiler ve Tarih",
    voice_choice: str = "tr-TR-AhmetNeural",
    rate: str = "+4%",
    force_fallback: bool = False,
    channel_id: str = "1",
    audio_out: Path = DEFAULT_AUDIO_OUT,
    txt_out: Path = DEFAULT_TXT_OUT,
    json_out: Path = DEFAULT_JSON_OUT,
    srt_out: Path = DEFAULT_SRT_OUT,
) -> dict[str, Any]:
    """Uçtan uca senaryo, seslendirme ve altyazı verisi üretim hattı."""
    load_dotenv_file()
    resolved_voice = SUPPORTED_VOICES.get(voice_choice, "tr-TR-AhmetNeural")

    # 1. Senaryo Üretimi
    scenario = generate_scenario(concept=concept, force_fallback=force_fallback, channel_id=channel_id)
    script_text = scenario["script_text"]

    # 2. Seslendirme & Kelime Bazlı Zaman Damgaları
    tts_engine, duration_sec, word_timestamps = synthesize_voiceover(
        text=script_text,
        voice=resolved_voice,
        rate=rate,
        audio_out=audio_out,
    )

    # 3. Saf Metin (script.txt) Kaydı
    txt_out.write_text(script_text + "\n", encoding="utf-8")

    # 4. Dinamik Shorts Altyazısı (voiceover.srt) Kaydı
    srt_content = build_dynamic_shorts_srt(word_timestamps, words_per_cue=3)
    srt_out.write_text(srt_content, encoding="utf-8")

    # 5. Zengin Faz-3/Faz-4 Paketi (script.json) Kaydı
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "llm_provider": scenario["provider"],
        "tts_engine": tts_engine,
        "topic": scenario["topic"],
        "title": scenario["title"],
        "description": scenario["description"],
        "affiliate_link": scenario["affiliate_link"],
        "affiliate_cta": scenario["affiliate_cta"],
        "cta_line": scenario["cta_line"],
        "thumbnail_prompt": scenario["thumbnail_prompt"],
        "viral_hashtags": scenario["viral_hashtags"],
        "hook": scenario["hook"],
        "script_text": script_text,
        "word_count": scenario["word_count"],
        "audio_file": str(audio_out),
        "srt_file": str(srt_out),
        "audio_duration_sec": duration_sec,
        "visual_keywords": scenario["visual_keywords"],
        "word_timestamps": word_timestamps,
    }
    json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Faz 2 - AI Shorts İçerik ve Seslendirme Motoru")
    parser.add_argument(
        "--concept",
        type=str,
        default="İlginç Bilgiler ve Tarih",
        help="Senaryo konsepti (varsayılan: 'İlginç Bilgiler ve Tarih')",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default="tr-TR-AhmetNeural",
        choices=list(SUPPORTED_VOICES.keys()),
        help="Seslendirme modeli (ahmet / emel / tr-TR-AhmetNeural / tr-TR-EmelNeural)",
    )
    parser.add_argument(
        "--rate",
        type=str,
        default="+4%",
        help="Konuşma hızı ayarı (varsayılan: +4%%)",
    )
    parser.add_argument(
        "--force-fallback",
        action="store_true",
        help="API çağrısını atlayıp çevrimdışı yedek senaryo havuzunu test eder.",
    )
    parser.add_argument(
        "--channel_id",
        type=str,
        default=os.environ.get("MATRIX_CHANNEL_ID", "1"),
        help="Matrix kanal ID'si (varsayılan: 1)",
    )
    args = parser.parse_args()

    result = run_content_pipeline(
        concept=args.concept,
        voice_choice=args.voice,
        rate=args.rate,
        force_fallback=args.force_fallback,
        channel_id=args.channel_id,
    )

    print("\n" + "=" * 74)
    print(" FAZ 2 - İÇERİK ÜRETİM MOTORU TAMAMLANDI")
    print("=" * 74)
    print(f" LLM Sağlayıcı   : {result['llm_provider']}")
    print(f" TTS Motoru      : {result['tts_engine']}")
    print(f" Konu Kategorisi : {result['topic']}")
    print(f" Başlık          : {result['title']}")
    print(f" Kelime Sayısı   : {result['word_count']} kelime")
    print(f" Ses Süresi      : {result['audio_duration_sec']} saniye")
    print(f" Görsel Anahtar  : {', '.join(result['visual_keywords'])}")
    print(f" Çıktı Dosyaları : {result['audio_file']}, script.txt, script.json, {result['srt_file']}")
    print("-" * 74)
    print(" ÜRETİLEN SENARYO METNİ:\n")
    print(f" {result['script_text']}")
    print("=" * 74)


if __name__ == "__main__":
    main()
