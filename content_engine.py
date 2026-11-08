#!/usr/bin/env python3
"""
Faz 2 - Görev 2: İçerik Üretim Motoru (content_engine.py)
---------------------------------------------------------
Sıfır maliyetli, halüsinasyon korumalı ve çok katmanlı hata toleransına sahip
YouTube Shorts senaryo + seslendirme motoru.

Mimari Katmanlar ("Sadece ücretsiz katmanlar & her aracın bir alternatifi"):
  1. LLM Senaryo Katmanı (60-80 kelime / 30-45 sn Shorts Senaryosu):
     - Birincil  : Groq Cloud Free API (`llama-3.3-70b-versatile` - GROQ_API_KEY)
     - İkincil   : Google Gemini Free API (`gemini-2.0-flash-lite` - GEMINI_API_KEY)
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
import math
import os
import random
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

try:
    import edge_tts
except ImportError:  # pragma: no cover
    edge_tts = None  # type: ignore[assignment]
import requests

DEFAULT_AUDIO_OUT = Path("voiceover.mp3")
DEFAULT_TXT_OUT = Path("script.txt")
DEFAULT_JSON_OUT = Path("script.json")
DEFAULT_SRT_OUT = Path("voiceover.srt")
HISTORY_FILE = Path(__file__).parent / ".used_topics.json"
ANALYTICS_FEEDBACK_FILE = Path("analytics_feedback.json")
DEFAULT_AFFILIATE_FALLBACK_URL = os.environ.get("AFFILIATE_URL_DEFAULT", "https://www.youtube.com/@mentansiytas?sub_confirmation=1")

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

# --- FAZ 13.2: dogrulanmis kurumsal kaynak haritasi -------------------------
# Tum URL'ler 2026-11-04'te canli HTTP 200 ile dogrulanmistir.
KNOWLEDGE_SOURCES: dict[str, str] = {
    "zanzibar": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/İngiliz-Zanzibar_Savaşı",
    "venus": "NASA Science — https://science.nasa.gov/venus/",
    "jellyfish": "Smithsonian Magazine — https://www.smithsonianmag.com/smart-news/immortal-jellyfish-could-spur-discoveries-about-human-aging-180980702/",
    "napoleon": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Napolyon_Bonaparte",
    "gobeklitepe": "UNESCO — https://whc.unesco.org/en/list/1572/",
    "mariana": "NOAA — https://oceanservice.noaa.gov/facts/oceandepth.html",
    "iss": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Uzay_istasyonu",
    "emu": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Emu_Savaşı",
    "neutron": "NASA — https://svs.gsfc.nasa.gov/11260/",
    "octopus": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Ahtapot",
    "cleopatra": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Kleopatra",
    "honey": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Bal",
    "neptune": "NASA Science — https://science.nasa.gov/neptune/",
    "antikythera": "Smithsonian Magazine — https://www.smithsonianmag.com/smart-news/ancient-astronomical-calculator-even-older-we-thought-180953472/",
    "vacuum": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Vakum",
    "banana": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Muz",
    "tunguska": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Tunguska_olayı",
    "tardigrade": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Su_ayısı",
    "voyager": "NASA — https://science.nasa.gov/mission/voyager-1/",
    "sunlight": "NASA Science — https://science.nasa.gov/sun/facts/",
    "pompeii": "UNESCO — https://whc.unesco.org/en/list/829/",
    "trees": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Ağaç",
    "krakatoa": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Krakatoa",
}

# Konu metninden kaynak anahtar kelimesini bulur (basit, sirali eslesme).
_SOURCE_KEY_HINTS: tuple[tuple[str, str], ...] = (
    ("zanzibar", "zanzibar"), ("38 dakika", "zanzibar"),
    ("venus", "venus"), ("venüs", "venus"),
    ("denizanası", "jellyfish"), ("turritopsis", "jellyfish"), ("ölümsüz", "jellyfish"),
    ("napolyon", "napoleon"), ("tavşan", "napoleon"),
    ("göbeklitepe", "gobeklitepe"), ("gobeklitepe", "gobeklitepe"),
    ("mariana", "mariana"),
    ("uzay istasyonu", "iss"), ("gözyaş", "iss"), ("ağlarsanız", "iss"),
    ("emu", "emu"), ("devekuşu", "emu"),
    ("nötron", "neutron"), ("neutron", "neutron"),
    ("ahtapot", "octopus"),
    ("kleopatra", "cleopatra"),
    ("mısır balı", "honey"), ("balı", "honey"),
    ("neptün", "neptune"), ("uranüs", "neptune"), ("elmas yağmuru", "neptune"),
    ("antikythera", "antikythera"),
    ("metal", "vacuum"), ("kayn", "vacuum"),
    ("muz", "banana"),
    ("tunguska", "tunguska"),
    ("su ayısı", "tardigrade"), ("tardigrade", "tardigrade"),
    ("voyager", "voyager"), ("altın plak", "voyager"), ("altın plak", "voyager"),
    ("güneş ışığı", "sunlight"), ("8 dakika", "sunlight"),
    ("pompeii", "pompeii"),
    ("ağaç", "trees"),
    ("krakatoa", "krakatoa"),
)


def match_source_by_topic(topic: str = "", title: str = "") -> str:
    """Konu/baslik metninden dogrulanmis kaynak satiri bulur (bos = kaynak yok)."""
    combined = f"{topic} {title}".lower()
    for hint, key in _SOURCE_KEY_HINTS:
        if hint in combined and key in KNOWLEDGE_SOURCES:
            return KNOWLEDGE_SOURCES[key]
    return ""


# API kesintisi, kota aşımı veya anahtar bulunmaması durumunda devreye giren yedek senaryo havuzu
FALLBACK_SCENARIOS: list[dict[str, Any]] = [
    {
        "topic": "Tarih",
        "title": "Tarihin En Kısa Savaşı Sadece 38 Dakika Sürdü! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/İngiliz-Zanzibar_Savaşı",
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
        "source": "NASA Science — https://science.nasa.gov/venus/",
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
        "title": "Yaşlanmayı Geri Alan Denizanası: Turritopsis! #Shorts",
        "source": "Smithsonian Magazine — https://www.smithsonianmag.com/smart-news/immortal-jellyfish-could-spur-discoveries-about-human-aging-180980702/",
        "description": "Biyolojik olarak yaşlanmayı geri alabilen Turritopsis dohrnii nasıl yeniden doğuyor? #bilim #doğa #ilginçbilgiler #shorts",
        "hook": "Biyolojik olarak yaşlanmayı geri alabilen gerçek bir canlı olduğunu biliyor muydunuz?",
        "script_text": (
            "Biyolojik olarak yaşlanmayı geri alabilen gerçek bir canlı olduğunu biliyor muydunuz? "
            "Akdeniz sularında da yaşayan ve serçe parmağınızın tırnağından bile küçük olan bu özel denizanası, yaşlandığında ya da yaralandığında ölmek yerine zamanı geriye sarar. "
            "Hücrelerini tamamen dönüştürerek tıpkı bir kelebeğin tekrar tırtıla dönüşmesi gibi bebeklik evresine geri döner. "
            "Fiziksel olarak ölümsüz değildir; yaşlanmayı biyolojik anlamda geri alabilir ve bir avcı tarafından yenmediği sürece bu döngüyü tekrarlayabilir. "
            "Bilim insanları bu minik canlının genetik şifresini inceleyerek insan yaşlanmasına karşı tedavi umudu arıyor; şu an için doğrulanmış bir tedavi yok."
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
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Napolyon_Bonaparte",
        "description": "Avrupa'yı titreten Napolyon Bonapart yüzlerce tavşandan neden kaçmak zorunda kaldı? #tarih #ilginçbilgiler #shorts",
        "hook": "Avrupa'yı dize getiren Napolyon Bonapart'ın, hayatının en tuhaf yenilgisini bir tavşan sürüsünden aldığını duymuş muydunuz?",
        "script_text": (
            "Avrupa'yı dize getiren Napolyon Bonapart'ın, hayatının en tuhaf yenilgisini bir tavşan sürüsünden aldığını duymuş muydunuz? "
            "Bin sekiz yüz yedi yılında imzalanan barış antlaşmasını kutlamak isteyen Napolyon, görkemli bir tavşan avı düzenletti. "
            "Ancak kurmayları yabani tavşan yerine çiftliklerde insan elinde büyümüş binlerce evcil tavşan toplamıştı. "
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
        "source": "UNESCO — https://whc.unesco.org/en/list/1572/",
        "description": "Şanlıurfa'daki Göbeklitepe insanlık tarihini nasıl baştan yazdı? #göbeklitepe #tarih #ilginçbilgiler #shorts",
        "hook": "Mısır piramitlerinden bile tam yedi bin yıl daha eski dev bir tapınağın Türkiye topraklarında olduğunu biliyor muydunuz?",
        "script_text": (
            "Mısır piramitlerinden bile tam yedi bin yıl daha eski dev bir tapınağın Türkiye topraklarında olduğunu biliyor muydunuz? "
            "Şanlıurfa yakınlarındaki Göbeklitepe, günümüzden yaklaşık on bir bin yıl önce (UNESCO'ya göre MÖ 9600–8200), insanlar henüz yerleşik tarıma bile geçmemişken inşa edildi. "
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
        "source": "NOAA — https://oceanservice.noaa.gov/facts/oceandepth.html",
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
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Uzay_istasyonu",
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
        "title": "Avustralya Ordusunun Emularına Karşı Başarısız Operasyonu! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Emu_Savaşı",
        "description": "1932'deki 'Büyük Emu Savaşı' (resmî bir savaş değil, popüler bir lakap) neden başarısız oldu? #tarih #ilginçbilgiler #shorts",
        "hook": "Modern makineli tüfeklerle donatılmış gerçek bir ordunun, uçamayan kuşlara karşı başarısız bir operasyona girmesini duymuş muydunuz?",
        "script_text": (
            "Modern makineli tüfeklerle donatılmış gerçek bir ordunun, uçamayan kuşlara karşı başarısız bir operasyona girmesini duymuş muydunuz? "
            "Bin dokuz yüz otuz iki yılında Avustralya'da yirmi bin emu kuşu tarım arazilerini istila edince hükümet bölgeye makineli tüfekli askerler gönderdi. "
            "Ancak saatte elli kilometre hızla koşabilen emular, ateş açıldığı anda küçük gruplara ayrılarak tam bir gerilla taktiği uyguladı. "
            "Binlerce mermi harcanmasına rağmen sürüler durdurulamadı ve ordu geri çekildi. Bu harekât resmî bir savaş değildi; 'Büyük Emu Savaşı' diye popüler bir lakap aldı."
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
        "title": "Bir Çay Kaşığı Nötron Yıldızı 1 Milyar Ton Çeker! #Shorts",
        "source": "NASA — https://svs.gsfc.nasa.gov/11260/",
        "description": "Evrenin en yoğun cisimleri olan nötron yıldızları nasıl oluşur? #evren #uzay #bilim #shorts",
        "hook": "Sadece bir çay kaşığı nötron yıldızı maddesinin Dünya'da yaklaşık bir milyar ton ağırlığında olabileceğini hayal edebilir misiniz?",
        "script_text": (
            "Sadece bir çay kaşığı nötron yıldızı maddesinin Dünya'da yaklaşık bir milyar ton ağırlığında olabileceğini hayal edebilir misiniz? "
            "Dev bir yıldız ömrünü tamamlayıp süpernova olarak patladığında çekirdeği kendi içine o kadar korkunç bir kuvvetle çöker ki atomların içindeki boşluk bile yok olur. "
            "Ortaya çıkan nötron yıldızı sadece yirmi kilometre çapındadır ama Güneş'ten bile daha fazla kütleye sahiptir. "
            "Öyle ki bu yıldızdan alacağınız tek bir çay kaşığı madde, NASA'nın aktardığına göre Dünya üzerinde yaklaşık bir milyar ton ağırlığında olurdu."
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
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Ahtapot",
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
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Kleopatra",
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
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Bal",
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
        "source": "NASA Science — https://science.nasa.gov/neptune/",
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
        "source": "Smithsonian Magazine — https://www.smithsonianmag.com/smart-news/ancient-astronomical-calculator-even-older-we-thought-180953472/",
        "description": "Deniz dibindeki batıktan çıkan 2000 yıllık bronz bilgisayar bilim dünyasını nasıl şaşkına çevirdi? #tarih #bilim #arkeoloji #shorts",
        "hook": "Günümüzden tam iki bin yıl önce Antik Yunan'da gökyüzünü hesaplayan mekanik bir bilgisayar yapıldığını biliyor muydunuz?",
        "script_text": (
            "Günümüzden tam iki bin yıl önce Antik Yunan'da gökyüzünü hesaplayan mekanik bir bilgisayar yapıldığını biliyor muydunuz? "
            "Bin dokuz yüz bir yılında sünger avcıları Ege Denizi'ndeki bir Roma batığında paslanmış bronz dişlilerden oluşan gizemli bir kutu buldu. "
            "Röntgen taramalarıyla incelenen Antikythera Düzeneği'nin içinde otuzdan fazla hassas dişli çark olduğu ortaya çıktı. "
            "Bu inanılmaz cihaz Güneş ve Ay tutulmalarını on yıllar öncesinden günü gününe hesaplayabiliyordu ve Smithsonian'ın aktardığına göre benzer bir mekanizma en az bin yıl daha üretilmedi."
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
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Vakum",
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
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Muz",
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
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Tunguska_olayı",
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
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Su_ayısı",
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
        "source": "NASA — https://science.nasa.gov/mission/voyager-1/",
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
        "source": "NASA Science — https://science.nasa.gov/sun/facts/",
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
        "source": "UNESCO — https://whc.unesco.org/en/list/829/",
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
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Ağaç",
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
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Krakatoa",
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
    # ── YENİ SENARYOLAR (23→80) ─────────────────────────────────────────────
    {
        "topic": "Tarih",
        "title": "İskenderiye Kütüphanesi Tek Bir Gecede Yanmadı! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/İskenderiye_Kütüphanesi",
        "description": "Antik dünyanın en büyük bilgi hazinesi nasıl yok oldu? #tarih #bilim #shorts",
        "hook": "İskenderiye Kütüphanesi tek bir gecede yanmadı; asıl gerçek çok daha karmaşık.",
        "script_text": (
            "İskenderiye Kütüphanesi tek bir gecede yanmadı; asıl gerçek çok daha karmaşık. "
            "Milattan önce üçüncü yüzyılda Mısır'da kurulan bu kütüphane yarım milyona kadar papirüs rulonu barındırıyordu. "
            "Sezar'ın MÖ 48'deki yangını, Aurelianus'un MS 270'deki saldırısı, "
            "Theophilus'un MS 391'deki tahribatı ve Arap fethinin 641'deki etkileri bir araya geldi. "
            "Kütüphane tek bir felaketle değil, yüzyıllar içinde yaşanan bir dizi ihmal ve saldırıyla tarihe karıştı."
        ),
        "visual_keywords": ["ancient library scrolls egypt", "papyrus manuscript fire", "alexandria ruins ancient", "burning books history"],
    },
    {
        "topic": "Bilim",
        "title": "İnsan Vücudunda Bakteri Hücreden Fazladır! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Mikrobiyom",
        "description": "Vücudumuzda biz mi daha çoğuz, yoksa bakteriler mi? #bilim #sağlık #shorts",
        "hook": "Şu an sizi oluşturan hücrelerin yarısından fazlası aslında sizin değil.",
        "script_text": (
            "Şu an sizi oluşturan hücrelerin yarısından fazlası aslında sizin değil. "
            "Güncel araştırmalara göre insan vücudunda yaklaşık 38 trilyon bakteri yaşarken "
            "insan hücresi sayısı yalnızca 30 trilyondur. "
            "Bu bakterilerin büyük çoğunluğu bağırsaklarda yaşar ve "
            "sindirimden bağışıklık sistemine, hatta ruh halinize kadar her şeyi etkiler. "
            "Biyolojik açıdan bakıldığında siz aslında bir insan-bakteri süper organizmasısınız."
        ),
        "visual_keywords": ["bacteria microscope science", "human gut microbiome", "biology laboratory cells", "immune system visualization"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Oxford Üniversitesi Azteklerden 300 Yıl Daha Eski! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Oxford_Üniversitesi",
        "description": "Dünyanın en eski üniversitesi Aztek İmparatorluğu'ndan mı önce kuruldu? #tarih #shorts",
        "hook": "Azteklerin başkenti kurulmadan önce Oxford'da öğrenciler ders alıyordu.",
        "script_text": (
            "Azteklerin başkenti kurulmadan önce Oxford'da öğrenciler ders alıyordu. "
            "Oxford Üniversitesi'nde öğretimin 1096 yılında başladığı bilinmektedir. "
            "Aztek İmparatorluğu ise ancak 1428 yılında kuruldu. "
            "Yani Oxford, Aztek uygarlığından en az üç yüz yıl daha eskidir. "
            "Bugün hâlâ aktif olan bu üniversite, kesintisiz eğitim veren dünyanın en köklü kurumları arasındadır."
        ),
        "visual_keywords": ["oxford university historic building", "medieval university hall", "aztec pyramid ruins mexico", "ancient books manuscripts"],
    },
    {
        "topic": "Bilim",
        "title": "Her Yıl 40.000 Ton Uzay Tozu Dünya'ya Yağıyor! #Shorts",
        "source": "NASA — https://science.nasa.gov/solar-system/meteors-meteorites/",
        "description": "Dünyanın yüzeyine her gün ne kadar uzay maddesi düşüyor? #uzay #bilim #shorts",
        "hook": "Tam bu an dünyanın üzerine uzaydan toz yağıyor ve siz bunu hiç fark etmiyorsunuz.",
        "script_text": (
            "Tam bu an dünyanın üzerine uzaydan toz yağıyor ve siz bunu hiç fark etmiyorsunuz. "
            "NASA verilerine göre Dünya her yıl yaklaşık kırk bin ton kozmik toz ve mikro meteorit alıyor. "
            "Bu partiküllerin çoğu bir tane tuzdan bile küçük olduğu için atmosferde tamamen yanıyor. "
            "Ancak bir kısmı yüzeye ulaşıyor; bilim insanları bu kozmik tozu buzullardan ve okyanuslardan toplayarak "
            "güneş sistemimizin doğuşunu anlamak için inceliyorlar."
        ),
        "visual_keywords": ["meteor shower night sky", "cosmic dust particle microscope", "earth atmosphere glow space", "meteorite sample science"],
    },
    {
        "topic": "Tarih",
        "title": "Vikingler Kolomb'dan 500 Yıl Önce Amerika'ya Gitti! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Leif_Eriksson",
        "description": "Amerika'yı ilk keşfeden Kolomb değil miydi? #tarih #keşifler #shorts",
        "hook": "Kristof Kolomb Amerika'ya adım atmadan tam beş yüz yıl önce başka insanlar o kıyılardaydı.",
        "script_text": (
            "Kristof Kolomb Amerika'ya adım atmadan tam beş yüz yıl önce başka insanlar o kıyılardaydı. "
            "Viking kaşifi Leif Eriksson, MS 1000 yılı civarında Newfoundland adasına ulaşarak "
            "Vinland adını verdiği bir yerleşim kurdu. "
            "Kanada'daki L'Anse aux Meadows kazılarında bulunan Viking artefaktları bunu kesin olarak kanıtladı. "
            "Kolomb ise ancak 1492'de Amerika kıtasına ulaşabildi."
        ),
        "visual_keywords": ["viking ship ocean waves", "norse warrior exploration", "newfoundland coast canada", "medieval longboat sailing"],
    },
    {
        "topic": "Bilim",
        "title": "Balarıları Çiçekleri Elektrik Alanıyla Buluyor! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Balarısı",
        "description": "Balarılarının gizli süper gücü ne? #doğa #bilim #shorts",
        "hook": "Balarılarının çiçekleri bulmak için kullandığı gizli bir duyusu daha var: elektrik.",
        "script_text": (
            "Balarılarının çiçekleri bulmak için kullandığı gizli bir duyusu daha var: elektrik. "
            "Çiçekler, arılar yaklaştığında hafif bir negatif elektrik yük taşır. "
            "Araştırmalar, balarılarının bu zayıf elektrik alanlarını özel tüyleriyle algılayabildiğini gösteriyor. "
            "Bir arı çiçeği ziyaret ettiğinde yük değişir ve bu diğer arılara "
            "o çiçeğin yakın zamanda ziyaret edildiğini bildiren doğal bir işaret görevi görür."
        ),
        "visual_keywords": ["bee flower pollination closeup", "electric field visualization", "bumblebee macro nature", "honeybee pollen"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Dünyanın En Soğuk Köyünde 500 Kişi Yaşıyor! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Oymyakon",
        "description": "Dünyanın en soğuk kalıcı yerleşim yeri neresi? #coğrafya #ilginçbilgiler #shorts",
        "hook": "Dünyanın en soğuk kalıcı yerleşim yerinde yazın çocuklar dışarıda oynuyor.",
        "script_text": (
            "Dünyanın en soğuk kalıcı yerleşim yerinde yazın çocuklar dışarıda oynuyor. "
            "Rusya'nın Sibirya bölgesindeki Oymyakon köyünde 1924'te eksi 71,2 derece Celsius ölçüldü; "
            "bu, Kuzey Kutbu dışında kaydedilen en düşük sıcaklık rekorudur. "
            "Şaşırtıcı olan şu: Bu köyde 500 kişi hâlâ yaşıyor. "
            "Yazın sıcaklık 30 dereceye çıkabiliyor ve insanlar bahçelerinde sebze yetiştiriyor."
        ),
        "visual_keywords": ["siberia frozen village winter", "extreme cold russia landscape", "snow covered houses tundra", "frozen river siberia"],
    },
    {
        "topic": "Bilim",
        "title": "Ahtapotlar Renk Körü Olmalarına Rağmen Renkleri Görüyor! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Ahtapot",
        "description": "Renk körü ahtapotlar nasıl renk değiştirebiliyor? #doğa #bilim #okyanus #shorts",
        "hook": "Ahtapotların gözleri renk körü olduğu hâlde nasıl mükemmel renk değiştirebiliyorlar?",
        "script_text": (
            "Ahtapotların gözleri renk körü olduğu hâlde nasıl mükemmel renk değiştirebiliyorlar? "
            "Bilim insanları yıllarca bu soruyla boğuştu. "
            "2015'te Harvard araştırmacıları çarpıcı bir öneride bulundu: "
            "Ahtapotların derilerindeki fotoreseptörler ışığa duyarlı olabilir "
            "ve ahtapotlar rengi gözleriyle değil, tüm deriyle algılıyor olabilir. "
            "Yani bu canlılar dünyayı tam anlamıyla hissederek görüyor olabilir."
        ),
        "visual_keywords": ["octopus camouflage color change", "cephalopod underwater", "skin texture color ocean", "marine biology deep sea"],
    },
    {
        "topic": "Tarih",
        "title": "Roma'yı Bitiren Son İmparator Sadece 16 Yaşındaydı! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Romulus_Augustulus",
        "description": "Batı Roma İmparatorluğu'nun sonunu kim getirdi? #tarih #roma #shorts",
        "hook": "Bin yıllık bir imparatorluğu bitiren son imparator henüz lise çağındaydı.",
        "script_text": (
            "Bin yıllık bir imparatorluğu bitiren son imparator henüz lise çağındaydı. "
            "Batı Roma İmparatorluğu'nun son hükümdarı Romulus Augustulus, "
            "MS 475'te yalnızca 15-16 yaşında tahta çıktı. "
            "Sadece on ay sonra, 476'da Germen komutan Odoacer tarafından tahttan indirildi. "
            "İlginç olan şu ki Odoacer onu idam etmedi; "
            "genci Campania'da küçük bir kaleye sürgün ederek maaş bağladı. "
            "Böylece Batı Roma, ölümle değil bir sürgünle sona erdi."
        ),
        "visual_keywords": ["roman emperor throne ancient", "rome colosseum ruins", "roman soldier armor", "empire fall history"],
    },
    {
        "topic": "Bilim",
        "title": "Karınca Kolonisi Merkezi Komutan Olmadan Karar Alır! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Karınca",
        "description": "Karıncalar nasıl bu kadar akıllıca davranıyor? #bilim #doğa #shorts",
        "hook": "Karınca kolonisinde hiçbir karınca komuta etmez ama koloni mükemmel kararlar alır.",
        "script_text": (
            "Karınca kolonisinde hiçbir karınca komuta etmez ama koloni mükemmel kararlar alır. "
            "Her karınca yalnızca basit kimyasal sinyallere yani feromonlara tepki verir. "
            "Ancak milyonlarca karıncanın bu basit kuralları uygulaması; "
            "trafik yönetiminden tarıma, karmaşık mimari yapılara kadar akıllı davranışlar ortaya çıkarır. "
            "Bilim insanları bu fenomeni sürü zekâsı olarak tanımlıyor ve "
            "robot sürülerinden yapay zekâ algoritmalarına kadar pek çok alanda ilham olarak kullanıyor."
        ),
        "visual_keywords": ["ant colony swarm macro", "insect behavior nature", "ants carrying food", "underground colony tunnel"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Hawaii Her Yıl Japonya'ya Biraz Daha Yaklaşıyor! #Shorts",
        "source": "USGS — https://www.usgs.gov/faqs/how-fast-are-tectonic-plates-moving",
        "description": "Kıtalar hâlâ hareket ediyor mu? #coğrafya #bilim #shorts",
        "hook": "Hawaii adaları her yıl birkaç santimetre Japonya'ya doğru kayıyor.",
        "script_text": (
            "Hawaii adaları her yıl birkaç santimetre Japonya'ya doğru kayıyor. "
            "Pasifik levhası, yılda yaklaşık 5-10 santimetre hızla kuzeybatıya hareket ediyor. "
            "Bu hareket insan ölçeğinde çok yavaş görünse de "
            "milyonlarca yıl sonunda kıtaları tamamen yeniden şekillendirecek. "
            "Şu andan itibaren 50 milyon yıl sonra Los Angeles, "
            "bugünkü San Francisco'nun bulunduğu yere geçmiş olacak."
        ),
        "visual_keywords": ["hawaii volcanic island aerial", "tectonic plates earth map", "pacific ocean waves", "volcano magma eruption"],
    },
    {
        "topic": "Tarih",
        "title": "Dünyanın İlk Programcısı Bir Kadındı! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Ada_Lovelace",
        "description": "Ada Lovelace bilgisayar icat edilmeden programı mı yazdı? #tarih #teknoloji #shorts",
        "hook": "Bilgisayar yokken bile bir kadın onun için program yazmıştı.",
        "script_text": (
            "Bilgisayar yokken bile bir kadın onun için program yazmıştı. "
            "Ada Lovelace, 1843 yılında Charles Babbage'ın hiç yapılamamış analitik motoru için "
            "Bernoulli sayılarını hesaplayacak bir algoritma yazdı. "
            "Bu algoritma, tarihte bilgisayar programı olarak kabul edilen ilk örnektir. "
            "Lovelace aynı zamanda bu makinenin yalnızca hesap değil, "
            "müzik besteleme de dahil olmak üzere çok daha geniş amaçlarla kullanılabileceğini öngördü."
        ),
        "visual_keywords": ["ada lovelace portrait vintage", "vintage computing mechanical gears", "19th century mathematics", "historical woman scientist"],
    },
    {
        "topic": "Bilim",
        "title": "Işık Hızında Giderseniz Zaman Durur! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Özel_görelilik",
        "description": "Einstein'ın izafiyet teorisi zamanı nasıl açıklıyor? #fizik #uzay #shorts",
        "hook": "Bir fotonun bakış açısından doğduğu andan hedefe vardığı ana kadar hiç zaman geçmez.",
        "script_text": (
            "Bir fotonun bakış açısından doğduğu andan hedefe vardığı ana kadar hiç zaman geçmez. "
            "Einstein'ın özel görelilik teorisine göre, "
            "bir nesne ışık hızına ne kadar yaklaşırsa zamanı o kadar yavaş geçer. "
            "Işık hızına tam olarak ulaşılsaydı zaman tamamen durmuş olurdu. "
            "Bu yüzden Güneş'ten çıkan bir foton sekiz dakika uzaktaki Dünya'ya vardığında "
            "kendi referans çerçevesinde sıfır yaşındadır; yani hiç yaşlanmamıştır."
        ),
        "visual_keywords": ["speed of light beam cosmos", "spacetime relativity visualization", "photon travel space stars", "einstein theory physics"],
    },
    {
        "topic": "Tarih",
        "title": "Çin Seddi Uzaydan Görünmez, Bu Bir Efsane! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Çin_Seddi",
        "description": "Çin Seddi hakkındaki en büyük yanlış inanç nedir? #tarih #coğrafya #shorts",
        "hook": "Hayatınız boyunca yanlış öğrendiğiniz bir gerçek: Çin Seddi uzaydan görünmez.",
        "script_text": (
            "Hayatınız boyunca yanlış öğrendiğiniz bir gerçek: Çin Seddi uzaydan görünmez. "
            "Ortalama 5-8 metre genişliğindeki bu yapı, "
            "düşük yörüngedeki astronotların çıplak gözle göremeyeceği kadar dardır. "
            "Çin'in ilk uzay insanı Yang Liwei, 2003'te bu efsaneyi bizzat çürüttü: "
            "Uzaydan seddi göremediğini açıkladı. "
            "NASA da bu efsanenin yanlış olduğunu resmi olarak teyit etmiştir."
        ),
        "visual_keywords": ["great wall china aerial view", "chinese landmark mountains", "satellite earth view", "china ancient architecture"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "En Az Bilen En Çok Bildiğini Zanneder: Dunning-Kruger! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Dunning–Kruger_etkisi",
        "description": "Dunning-Kruger etkisi nedir? #psikoloji #bilim #shorts",
        "hook": "Konuyu az bilen insanlar neden daha çok güvenir?",
        "script_text": (
            "Konuyu az bilen insanlar neden daha çok güvenir? "
            "1999'da psikologlar Dunning ve Kruger, bir konu hakkında az bilgisi olanların "
            "kendi yeterliliklerini abartma eğiliminde olduğunu keşfetti. "
            "Bunun nedeni şu: Bir konuyu gerçekten öğrenebilmek için önce "
            "o konunun ne kadar karmaşık olduğunu anlamak gerekir. "
            "Az bilen kişi bu karmaşıklığı henüz fark etmemiştir; "
            "dolayısıyla ne bilmediğini de bilmez ve kendine aşırı güvenir."
        ),
        "visual_keywords": ["brain thinking confidence", "psychology experiment graph", "overconfidence concept", "learning knowledge"],
    },
    {
        "topic": "Bilim",
        "title": "Deniz Atlarında Yavruyu Erkek Taşır! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Denizatı",
        "description": "Deniz atlarının ilginç aile hayatı nasıl? #doğa #deniz #shorts",
        "hook": "Okyanusta yavruları erkek doğuran tek omurgalı canlı deniz atıdır.",
        "script_text": (
            "Okyanusta yavruları erkek doğuran tek omurgalı canlı deniz atıdır. "
            "Dişi yumurtaları erkeğin kesesine bırakır; "
            "erkek hamileliği boyunca yavruları besler ve doğurur. "
            "Üstelik deniz atları çiftleşme sezonunda tek bir eşle birlikte kalır "
            "ve bazı türlerde bu bağ ömür boyu sürer. "
            "Her sabah birbirini selamlamak için büyülü bir dans ederler "
            "ve partner değiştirmezler."
        ),
        "visual_keywords": ["seahorse underwater coral reef", "marine animal birth", "tropical ocean seahorse", "seahorse macro closeup"],
    },
    {
        "topic": "Tarih",
        "title": "Tesla'ya Söz Verilen Parayı Edison Vermedi! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Nikola_Tesla",
        "description": "Tesla ve Edison arasındaki ihanet hikâyesi! #tarih #bilim #shorts",
        "hook": "Nikola Tesla ile Thomas Edison'ın savaşı icat rekabetinden çok bir ihanet hikâyesiydi.",
        "script_text": (
            "Nikola Tesla ile Thomas Edison'ın savaşı icat rekabetinden çok bir ihanet hikâyesiydi. "
            "Tesla 1884'te Edison'ın şirketinde çalışmaya başladı. "
            "Edison, Tesla'ya DC motorlarını iyileştirirse elli bin dolar vereceğini söyledi. "
            "Tesla sorunu çözdü; Edison ise parayı vermeyi reddetti: "
            "'Amerikan şakalarını anlayamamışsın' dedi. "
            "Tesla istifa etti; ardından AC akımı icat ederek Edison'ın teknolojisini "
            "tarihsel olarak geride bırakan sistemi dünyaya sundu."
        ),
        "visual_keywords": ["nikola tesla laboratory portrait", "electricity experiment vintage", "ac dc current science", "inventor 1900 laboratory"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Ölü Deniz'de Batmak İmkânsız! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Ölü_Deniz",
        "description": "Ölü Deniz neden bu kadar yoğun? #coğrafya #bilim #shorts",
        "hook": "Ölü Deniz'e girdiğinizde batmaya çalışsanız bile başaramazsınız.",
        "script_text": (
            "Ölü Deniz'e girdiğinizde batmaya çalışsanız bile başaramazsınız. "
            "Normal deniz suyunun tuz yoğunluğu yüzde 3-4'tür. "
            "Ölü Deniz'de bu oran yüzde 34'e ulaşır; okyanus suyundan yaklaşık on kat daha tuzlu. "
            "Bu aşırı yoğunluk insan vücudunu otomatik olarak yüzeyde tutar; "
            "istesen bile dibe inemezsin. "
            "Ancak bu yoğun tuz nedeniyle Ölü Deniz, yüzyıllar içinde yüzde kırk küçülmüş durumda."
        ),
        "visual_keywords": ["dead sea floating salt water", "salt lake mineral shore", "middle east geography aerial", "dead sea crystals"],
    },
    {
        "topic": "Bilim",
        "title": "Evrenin Yüzde 95'i Karanlık Madde ve Enerji! #Shorts",
        "source": "NASA — https://science.nasa.gov/universe/dark-matter-dark-energy/",
        "description": "Evrendeki maddenin yalnızca ne kadarını görebiliyoruz? #uzay #bilim #shorts",
        "hook": "Teleskoplarla gördüğümüz her şey, tüm yıldızlar ve galaksiler, evrenin yalnızca yüzde beşidir.",
        "script_text": (
            "Teleskoplarla gördüğümüz her şey, tüm yıldızlar ve galaksiler, evrenin yalnızca yüzde beşidir. "
            "Geri kalan yüzde 95'in yüzde 27'si karanlık madde, yüzde 68'i ise karanlık enerjidir. "
            "Karanlık madde ışık yaymaz, yansıtmaz veya emmez; "
            "yalnızca çekimsel etkisiyle varlığını hissettirir. "
            "Karanlık enerji ise evrenin genişlemesini giderek hızlandıran "
            "ve henüz tam olarak anlaşılamamış bir kuvvettir."
        ),
        "visual_keywords": ["dark matter cosmos visualization", "universe deep space", "galaxy formation dark energy", "cosmic web space"],
    },
    {
        "topic": "Tarih",
        "title": "Fransız İhtilali Ekmek Kıtlığıyla Başladı! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Fransız_Devrimi",
        "description": "Fransız Devrimi'nin gerçek tetikleyicisi ne? #tarih #fransız #shorts",
        "hook": "Tarihte bir imparatorluğu yıkan şey bazen bir somun ekmektir.",
        "script_text": (
            "Tarihte bir imparatorluğu yıkan şey bazen bir somun ekmektir. "
            "1788-1789 yıllarında Fransa'yı etkileyen büyük kıtlık, "
            "işçilerin aylık gelirinin yüzde doksanını ekmeğe harcamasına yol açtı. "
            "Kral XVI. Louis ise bu dönemde sarayında büyük şölenler düzenlemeye devam ediyordu. "
            "Halk arasındaki bu öfke, 1789'da devrime fitili ateşledi "
            "ve yüzyıllarca süren krallık düzeni altı ay içinde çöktü."
        ),
        "visual_keywords": ["french revolution crowd paris", "18th century france street", "bread wheat famine poverty", "versailles palace history"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "İnternet'in Toplam Ağırlığı Bir Çilek Kadar! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/İnternet",
        "description": "İnternet fiziksel olarak ne kadar ağır? #bilim #teknoloji #shorts",
        "hook": "İnternet'teki tüm veriler fiziksel olarak tartılsaydı, bir çilek kadar olurdu.",
        "script_text": (
            "İnternet'teki tüm veriler fiziksel olarak tartılsaydı, bir çilek kadar olurdu. "
            "Fizikçi Russel Seitz'ın hesabına göre, "
            "dünyadaki tüm veri merkezlerinde dolaşan elektronların toplam kütlesi "
            "yaklaşık 50 gramdır. "
            "Elektronlar inanılmaz derecede hafif olduğundan, "
            "milyarlarca web sayfasını, videoyu ve mesajı taşıyan bu devasa altyapı "
            "maddesel olarak neredeyse ağırlıksızdır."
        ),
        "visual_keywords": ["internet data center servers", "fiber optic cables digital", "data flow technology", "server room blue light"],
    },
    {
        "topic": "Bilim",
        "title": "Yunuslar Uyurken Beyninin Yarısı Uyanık Kalır! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Yunus",
        "description": "Yunuslar nasıl uyuyor? #doğa #deniz #bilim #shorts",
        "hook": "Yunusların beyni uyurken ikiye bölünür; yarısı dinlenirken diğer yarısı dünyayı izler.",
        "script_text": (
            "Yunusların beyni uyurken ikiye bölünür; yarısı dinlenirken diğer yarısı dünyayı izler. "
            "Bu fenomen tek yarıküre uykusu olarak bilinir ve yunuslar için hayati öneme sahiptir: "
            "Nefes almak için yüzeye çıkmaları gerekir. "
            "Tam bilinçsiz uyusalar boğulabilirler. "
            "Bu yüzden beyin yarılarını sırayla uyutarak "
            "hem dinlenmeyi hem de canlı kalmayı başarıyorlar. "
            "Bazı yunus türleri bu sırada gözün birini açık tutarak çevreyi de izliyor."
        ),
        "visual_keywords": ["dolphin ocean swimming", "marine mammal underwater", "dolphin group ocean blue", "brain neuroscience"],
    },
    {
        "topic": "Tarih",
        "title": "Moğol İmparatorluğu Tarihin En Büyük Kara İmparatorluğuydu! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Moğol_İmparatorluğu",
        "description": "Cengiz Han'ın kurduğu imparatorluk ne kadar büyüktü? #tarih #moğol #shorts",
        "hook": "Tarihin en büyük kara imparatorluğu, bugün 16 ülkenin topraklarını kapsıyordu.",
        "script_text": (
            "Tarihin en büyük kara imparatorluğu, bugün 16 ülkenin topraklarını kapsıyordu. "
            "Cengiz Han liderliğindeki Moğol İmparatorluğu, "
            "13. ve 14. yüzyıllarda yaklaşık 24 milyon km kare alana yayıldı. "
            "Bu, Avrupa kıtasının neredeyse iki katından büyük. "
            "İlginç olan şu: Moğollar bu devasa alanı sadece elli yılda fethetti; "
            "sonraki nesiller ise imparatorluğu yönetmekte zorlandı."
        ),
        "visual_keywords": ["mongol horseman steppe grass", "chinghis khan conquest", "central asia landscape mountains", "medieval army battle"],
    },
    {
        "topic": "Bilim",
        "title": "Tamamen Karanlıkta Kalırsanız Beyin Halüsinasyon Üretir! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Duyusal_yoksunluk",
        "description": "Duyusal yoksunluk beyne ne yapar? #psikoloji #bilim #shorts",
        "hook": "Birkaç saat tamamen karanlık ve sessiz bir odada kalırsanız beyin kendi görüntülerini üretir.",
        "script_text": (
            "Birkaç saat tamamen karanlık ve sessiz bir odada kalırsanız beyin kendi görüntülerini üretir. "
            "Beyin, sürekli duyusal giriş almayı bekler. "
            "Bu giriş kesildiğinde boşluğu doldurmak için kendi sinyallerini üretir "
            "ve bu da gerçekmiş gibi hissedilen görüntü ve seslere yol açar. "
            "Duyusal yoksunluk tankları bu etkiyi kullanarak "
            "meditasyon ve terapi amacıyla uygulanıyor. "
            "Ancak uzun süreli yoksunluk ciddi psikolojik bozukluklara neden olabiliyor."
        ),
        "visual_keywords": ["dark room isolation float tank", "sensory deprivation therapy", "brain hallucination visualization", "psychology mind"],
    },
    {
        "topic": "Bilim",
        "title": "Göz Renginiz Gerçekte Yalnızca Kahverengi Pigmentten Oluşuyor! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Göz_rengi",
        "description": "Mavi veya yeşil gözler gerçekten o renk mi? #bilim #ilginçbilgiler #shorts",
        "hook": "Aslında hiç kimsenin mavi ya da yeşil gözü yoktur; hepsinde yalnızca kahverengi pigment bulunur.",
        "script_text": (
            "Aslında hiç kimsenin mavi ya da yeşil gözü yoktur; hepsinde yalnızca kahverengi pigment bulunur. "
            "Göz rengi, irisin melanin miktarına bağlıdır. "
            "Çok az melanin olan gözlerde Tyndall saçılması denilen fizik olayı gerçekleşir: "
            "Kısa dalga boylu mavi ışık daha fazla saçılır ve gözümüz o irisi mavi algılar. "
            "Bu tıpkı gökyüzünün mavi görünmesiyle aynı mekanizmadır. "
            "Yani mavi gözler aslında yapısal bir optik yanılsama, gerçek bir mavi pigment değildir."
        ),
        "visual_keywords": ["blue eye iris macro closeup", "eye color photography", "light scattering optics", "eye pigment science"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Japonya'da 1400 Yıldır Aynı Şirketi Faaliyet Gösteriyor! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Kongo_Gumi",
        "description": "Dünyanın en eski şirketi ne zaman kuruldu? #tarih #japonya #shorts",
        "hook": "Dünyanın en eski şirketi, Bizans İmparatorluğu kurulurken Japonya'da tapınak inşa ediyordu.",
        "script_text": (
            "Dünyanın en eski şirketi, Bizans İmparatorluğu kurulurken Japonya'da tapınak inşa ediyordu. "
            "Kongo Gumi, MS 578 yılında Japonya'da kurulmuş bir tapınak inşaat şirketidir. "
            "2006'ya kadar bağımsız faaliyet gösteren şirket, "
            "tam 1.428 yıl boyunca Budist tapınakları inşa etti. "
            "Şirket bugün bir büyük müteahhit bünyesinde faaliyet gösterse de "
            "kurulduğu günden bu yana hiç kapanmamıştır."
        ),
        "visual_keywords": ["japanese temple ancient wood", "traditional architecture japan", "buddhist pagoda historic", "japanese craftsman traditional"],
    },
    {
        "topic": "Bilim",
        "title": "İnsan Beyninin Kapasitesi 2.5 Milyon Gigabayt! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/İnsan_beyni",
        "description": "İnsan beyni ne kadar veri saklayabilir? #bilim #beyin #shorts",
        "hook": "Beyniniz yaklaşık 2,5 milyon gigabayt veri saklayabilir.",
        "script_text": (
            "Beyniniz yaklaşık 2,5 milyon gigabayt veri saklayabilir. "
            "2016 yılında Salk Enstitüsü araştırmacıları, "
            "insan hipokampüsündeki sinaptik bağlantıların kapasitesini ölçtü. "
            "Sonuç 2,5 petabyte yani 2,5 milyon gigabayttı. "
            "Bu kapasite bir bilgisayarın sabit diskinden yaklaşık 3 milyon kat daha büyük. "
            "Üstelik beyin bu devasa kapasiteyi sadece 20 watt enerjiyle, "
            "bir ampulden bile az güçle çalıştırıyor."
        ),
        "visual_keywords": ["human brain neuron network", "neural connection visualization", "brain mri scan", "memory storage capacity"],
    },
    {
        "topic": "Tarih",
        "title": "Orta Çağ'da İnsanlar Gece Ortasında Kalkıp Kitap Okurdu! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Uyku",
        "description": "Orta Çağ insanları nasıl uyurdu? #tarih #ilginçbilgiler #shorts",
        "hook": "Sanayi devrimi öncesinde insanlar iki ayrı uyku döneminde uyuyor, arada kalkıp işler yapıyordu.",
        "script_text": (
            "Sanayi devrimi öncesinde insanlar iki ayrı uyku döneminde uyuyor, arada kalkıp işler yapıyordu. "
            "Tarihçi Roger Ekirch'in araştırmaları, "
            "Orta Çağ Avrupa'sında 'ilk uyku' ve 'ikinci uyku' olarak adlandırılan "
            "iki ayrı uyku döneminin yaygın olduğunu ortaya koydu. "
            "Gece yarısı ile sabah 2 arasında uyandıktan sonra insanlar okur, dua eder, "
            "komşuyla sohbet eder, hatta ziyarete giderlerdi. "
            "Elektrik ampulünün yaygınlaşmasıyla bu doğal ritim ortadan kalktı."
        ),
        "visual_keywords": ["medieval night candle reading", "old house interior night", "historical manuscript book", "sleep medieval history"],
    },
    {
        "topic": "Bilim",
        "title": "Karadelikler Gerçekten Her Şeyi Yutmuyor! #Shorts",
        "source": "NASA — https://science.nasa.gov/universe/black-holes/",
        "description": "Karadelikler hakkındaki en büyük yanlış inanç nedir? #uzay #bilim #shorts",
        "hook": "Karadelikler sürekli her şeyi yutan kozmik süpürgeler değildir.",
        "script_text": (
            "Karadelikler sürekli her şeyi yutan kozmik süpürgeler değildir. "
            "Bir karadelik, çekim alanı dışındaki nesneleri aktif olarak çekmez. "
            "Örneğin Güneş aniden bir karadeliğe dönüşseydi, "
            "Dünya yörüngesinde kalmaya devam ederdi çünkü çekim kuvveti değişmezdi. "
            "Sadece olay ufku adı verilen sınırın içine giren madde geri dönemez. "
            "Karadelikler tehlikelidir ama aktif olarak avlanmaz."
        ),
        "visual_keywords": ["black hole space visualization", "event horizon cosmos dark", "galaxy center space telescope", "gravitational pull stars"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Kuzey Kore ile Finlandiya'nın Arasında Tek Bir Ülke Var! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Rusya",
        "description": "Rusya'nın inanılmaz coğrafi boyutu! #coğrafya #ilginçbilgiler #shorts",
        "hook": "Haritaya baktığınızda inanılmaz görünecek ama Kuzey Kore ile Finlandiya arasında tek bir ülke var.",
        "script_text": (
            "Haritaya baktığınızda inanılmaz görünecek ama Kuzey Kore ile Finlandiya arasında tek bir ülke var: Rusya. "
            "Rusya hem Asya'da Kuzey Kore ile hem de Avrupa'da Finlandiya ile sınır paylaşıyor. "
            "Bu, Rusya'nın ne kadar devasa bir coğrafyayı kapladığının en çarpıcı örneğidir. "
            "Ülkenin doğudan batıya genişliği 11 zaman dilimini kapsıyor; "
            "yani Rusya'da bir uçtan öbür uca geçerken saatinizi 11 kez ileri almanız gerekiyor."
        ),
        "visual_keywords": ["russia vast map territory", "world geography borders", "finland winter europe", "korea peninsula asia map"],
    },
    {
        "topic": "Tarih",
        "title": "İnsan Hakları Bildirisi'ni Kaleme Alan Köle Sahipleriydi! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Thomas_Jefferson",
        "description": "Amerikan bağımsızlık bildirisinin yazarları hakkında ne biliyoruz? #tarih #shorts",
        "hook": "\"Tüm insanlar eşit yaratılmıştır\" diyen metnin yazarı, o gün kölelerinin sahibiydi.",
        "script_text": (
            "'Tüm insanlar eşit yaratılmıştır' diyen metnin yazarı, o gün kölelerinin sahibiydi. "
            "Thomas Jefferson, 1776'da Amerikan Bağımsızlık Bildirisi'ni kaleme aldığında "
            "yaklaşık 130 köle sahibiydi. "
            "Bildiri'nin ilk taslağında köleliği suçlayan bir bölüm yer alıyordu "
            "ancak güney eyaletlerinin baskısıyla bu bölüm çıkarıldı. "
            "Jefferson bu çelişkiyi hayatı boyunca tam olarak çözemedi."
        ),
        "visual_keywords": ["american independence declaration", "thomas jefferson portrait", "colonial america history", "18th century document"],
    },
    {
        "topic": "Bilim",
        "title": "Titanyum Vücutta Paslanmaz ve MRI'dan Geçer! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Titanyum",
        "description": "Titanyum neden bu kadar özel bir metal? #bilim #tıp #shorts",
        "hook": "Vücudunuzda titanyum implant olsa da MRI makinesine girebilirsiniz çünkü titanyum manyetik değildir.",
        "script_text": (
            "Vücudunuzda titanyum implant olsa da MRI makinesine girebilirsiniz çünkü titanyum manyetik değildir. "
            "MRI makineleri son derece güçlü manyetik alanlar kullanır; "
            "çelik implantlar bu alanda çekilip vücuda zarar verebilir. "
            "Titanyum ise manyetik olmayan bir metal olduğu için MRI'dan etkilenmez, "
            "korozyona dayanıklıdır, vücut tarafından reddedilmez "
            "ve kemik dokusuna entegre olabilir. "
            "Bu yüzden modern kalça protezlerinden diş implantlarına kadar her şeyde kullanılır."
        ),
        "visual_keywords": ["titanium medical implant xray", "mri machine hospital", "metal bone structure", "titanium material science"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Posta Pulları Balın Yapışkanlığını Kullanırdı! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Posta_pulu",
        "description": "İlk posta pulları nasıl yapışıyordu? #tarih #ilginçbilgiler #shorts",
        "hook": "İlk posta pullarında yapışkan olarak hayvan jelatini ve nişasta kullanılırdı.",
        "script_text": (
            "İlk posta pullarında yapışkan olarak hayvan jelatini ve nişasta kullanılırdı. "
            "1840'ta İngiltere'de icat edilen posta pulunun arkasındaki yapışkan, "
            "kemik jelatini ve nişastanın karışımından oluşuyordu. "
            "Sonraki yüzyılda bu formül çeşitlendi; "
            "bazı ülkeler bal bazlı yapışkanları bile denedi. "
            "Modern kendinden yapışkanlı pullara geçiş ancak 1960'larda başladı "
            "ve dünyaya tamamen yayılması 1990'ları buldu."
        ),
        "visual_keywords": ["vintage postage stamp collection", "mail history letter", "postal service antique", "stamp collecting philately"],
    },
    {
        "topic": "Bilim",
        "title": "Güneş Dünyanın Yüzde 99.8'ini Oluşturuyor! #Shorts",
        "source": "NASA Science — https://science.nasa.gov/sun/facts/",
        "description": "Güneş sistemi ne kadar büyük? #uzay #güneş #shorts",
        "hook": "Güneş sistemimizdeki toplam maddenin yüzde 99,8'i tek bir yerde toplanmış: Güneş'te.",
        "script_text": (
            "Güneş sistemimizdeki toplam maddenin yüzde 99,8'i tek bir yerde toplanmış: Güneş'te. "
            "Tüm gezegenler, asteroidler, kuyruklu yıldızlar ve diğer her şey "
            "geriye kalan yüzde 0,2'yi paylaşıyor. "
            "Jüpiter bu payın büyük çoğunluğunu alıyor; "
            "Dünya ise bu yüzde 0,2'nin yalnızca küçük bir kırığını oluşturuyor. "
            "Bu yüzden Güneş olmasa güneş sistemimiz neredeyse boş bir uzay olurdu."
        ),
        "visual_keywords": ["sun solar flare close", "solar system size comparison", "planets orbit sun", "star mass gravity space"],
    },
    {
        "topic": "Tarih",
        "title": "İlk Olimpiyat Oyunları'nda Atletler Çıplak Koştu! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Antik_Olimpiyat_Oyunları",
        "description": "Antik Olimpiyatlar modern oyunlardan ne kadar farklıydı? #tarih #spor #shorts",
        "hook": "Antik Yunan'da olimpiyat oyunları tamamen çıplak olarak yapılırdı.",
        "script_text": (
            "Antik Yunan'da olimpiyat oyunları tamamen çıplak olarak yapılırdı. "
            "MÖ 776'da başlayan antik Olimpiyatlar'da 'gymnos' yani çıplak anlamına gelen kelimeden gelen "
            "jimnastik geleneğine uyularak atletler giysi giymeden yarışırdı. "
            "Kadınların izleyici olarak katılması bile yasaktı; "
            "sadece bakire rahibelere izin verilirdi. "
            "Galiplere altın veya para değil, "
            "Olimpos dağı'nın kutsal zeytininden yapılmış taç verilirdi."
        ),
        "visual_keywords": ["ancient greek olympic ruins", "greece parthenon columns", "athletic competition ancient", "olive wreath crown"],
    },
    {
        "topic": "Bilim",
        "title": "Yıldırım Düşmesi Sırasında Hava 30.000 Derece Isınır! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Yıldırım",
        "description": "Yıldırım ne kadar güçlüdür? #bilim #doğa #shorts",
        "hook": "Bir yıldırımın çevresindeki hava, Güneş'in yüzeyinden beş kat daha sıcak olur.",
        "script_text": (
            "Bir yıldırımın çevresindeki hava, Güneş'in yüzeyinden beş kat daha sıcak olur. "
            "Yıldırım çarpması sırasında çevredeki hava 30.000 Kelvin'e kadar ısınabilir. "
            "Güneş'in yüzey sıcaklığı ise yaklaşık 5.778 Kelvin'dir. "
            "Bu ani genişleme ses dalgasına yol açar ve gök gürültüsünü oluşturur. "
            "Tüm bu enerji sadece birkaç mikrosaniyede serbest bırakılır; "
            "bu yüzden yıldırım gözle neredeyse görülmez."
        ),
        "visual_keywords": ["lightning strike storm dramatic", "thunder lightning sky", "electric bolt nature", "storm weather power"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Bir Kardan Adam Güneşin Altında Daha Yavaş Erir! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Yansıtabilirlik",
        "description": "Karın güneş ışığını yansıtması onu nasıl korur? #bilim #ilginçbilgiler #shorts",
        "hook": "Beyaz kıyafet giyince daha serin hissedersiniz; peki kar için bu neden daha karmaşık?",
        "script_text": (
            "Beyaz kıyafet giyince daha serin hissedersiniz; peki kar için bu neden daha karmaşık? "
            "Kar, güneş ışığının yüzde 80-90'ını yansıtır; bu ona çok yüksek albedo sağlar. "
            "Bu yüzden karlı bir gün gözlerinizi kamaştırır. "
            "Ancak karın üzerine atılan siyah is ya da kömür tozu bu yansıtma özelliğini bozar "
            "ve kar çok daha hızlı erir. "
            "Bilim insanları iklim değişikliğini engellemek için "
            "buz tabakalarını beyaz boyayla kaplamayı bile araştırdı."
        ),
        "visual_keywords": ["snow white reflective surface", "sunlight reflection ice", "snowman winter sun", "arctic ice albedo"],
    },
    {
        "topic": "Tarih",
        "title": "Mona Lisa 1911'de Çalındı ve 2 Yıl Kayıp Kaldı! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Mona_Lisa",
        "description": "Mona Lisa'nın büyük hırsızlık hikâyesi! #tarih #sanat #shorts",
        "hook": "Dünyanın en ünlü tablosu Louvre'dan çalındıktan sonra iki yıl boyunca kayıp kaldı.",
        "script_text": (
            "Dünyanın en ünlü tablosu Louvre'dan çalındıktan sonra iki yıl boyunca kayıp kaldı. "
            "1911'de Vincenzo Peruggia adlı İtalyan bir Louvre çalışanı, "
            "tabloyu paltosunun altında gizleyerek müzeden çıkardı. "
            "Fransız polisi başlangıçta ressam Picasso'yu bile şüpheli saydı. "
            "Tablo ancak 1913'te İtalya'da bulundu; "
            "Peruggia, eseri İtalya'ya geri kazandırmak için çaldığını söyledi. "
            "Bu hırsızlık Mona Lisa'yı bugünkü efsanevi şöhretine taşıdı."
        ),
        "visual_keywords": ["mona lisa painting louvre", "paris art museum", "famous painting theft", "renaissance artwork"],
    },
    {
        "topic": "Bilim",
        "title": "Dünyanın En Derin Noktasında Plastik Torba Bulundu! #Shorts",
        "source": "NOAA — https://oceanservice.noaa.gov/facts/oceandepth.html",
        "description": "İnsan etkisi okyanusun dibine kadar ulaştı mı? #bilim #çevre #shorts",
        "hook": "Güneş ışığının hiç ulaşamadığı, okyanusun 11 kilometre derinliğinde plastik torba bulundu.",
        "script_text": (
            "Güneş ışığının hiç ulaşamadığı, okyanusun 11 kilometre derinliğinde plastik torba bulundu. "
            "2018'de Beşinci Büyük Dalış Ekspedisyonu, "
            "Mariana Çukuru'nun en derin noktası olan Challenger Deep'te "
            "tek kullanımlık plastik torba ve şeker ambalajı buldu. "
            "Bu keşif, insanlığın etkisinin dünyanın en erişilmez noktalarına bile ulaştığını kanıtladı. "
            "Araştırmacılar ayrıca bu derinlikte yaşayan canlılarda da plastik parçacıkları tespit etti."
        ),
        "visual_keywords": ["mariana trench deep ocean", "plastic pollution ocean", "underwater dark abyss", "ocean research submarine"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "İki Atom Birbirine Dokunmaz, Hiçbir Şey Dokunmaz! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Pauli_dışlama_ilkesi",
        "description": "Nesneler gerçekte birbirine değiyor mu? #fizik #bilim #shorts",
        "hook": "Bir masaya elinizi bastırdığınızda eliniz masaya değmiyor; elektromanyetik kuvvetler itişiyor.",
        "script_text": (
            "Bir masaya elinizi bastırdığınızda eliniz masaya değmiyor; elektromanyetik kuvvetler itişiyor. "
            "Atomlar büyük ölçüde boşluktan oluşur; "
            "çekirdek ile elektronlar arasındaki mesafe devasa boyuttadır. "
            "İki atom gerçek anlamda birbirine temas etmez; "
            "negatif yüklü elektron bulutları birbirini iterek katı his verir. "
            "Yani hayatınız boyunca hiçbir şeye gerçekten dokunmadınız; "
            "yalnızca elektromanyetik kuvvetleri hissettiniz."
        ),
        "visual_keywords": ["atom structure visualization", "quantum physics particle", "electron cloud science", "electromagnetic force abstract"],
    },
    {
        "topic": "Tarih",
        "title": "İlk Uçuş Sadece 12 Saniye Sürdü! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Wright_Kardeşler",
        "description": "Wright Kardeşler'in tarihi ilk uçuşu nasıldı? #tarih #teknoloji #shorts",
        "hook": "İnsanlığın ilk motorlu uçuşu yalnızca 12 saniye sürdü ama dünyayı sonsuza kadar değiştirdi.",
        "script_text": (
            "İnsanlığın ilk motorlu uçuşu yalnızca 12 saniye sürdü ama dünyayı sonsuza kadar değiştirdi. "
            "17 Aralık 1903'te Orville Wright, Kuzey Carolina'daki Kitty Hawk'ta "
            "Flyer adlı uçağıyla 12 saniye havada kaldı ve 36 metre ilerledi. "
            "Aynı gün dört uçuş yaptılar; en uzunu 59 saniye sürdü. "
            "Yerel bir gazeteci haberi küçümseyerek geri çevirdi. "
            "Sadece 66 yıl sonra insanlar Ay'a gidecekti."
        ),
        "visual_keywords": ["wright brothers airplane historic", "first flight kitty hawk", "biplane vintage aviation", "early aircraft 1903"],
    },
    {
        "topic": "Bilim",
        "title": "Domuzlar İnsanlardan Daha Zeki Olabilir! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Domuz",
        "description": "Domuzların zekâsı hakkında ne biliyoruz? #doğa #bilim #shorts",
        "hook": "Domuzlar ayna testini geçebilen, kendi görüntülerini tanıyabilen sayılı hayvanlardan biridir.",
        "script_text": (
            "Domuzlar ayna testini geçebilen, kendi görüntülerini tanıyabilen sayılı hayvanlardan biridir. "
            "Araştırmalar, domuzların video oyunlarını oynamayı öğrenebildiğini, "
            "adlarını tanıdığını, basit sembolik dili kavrayabildiğini "
            "ve sosyal manipülasyon uygulayabildiğini ortaya koydu. "
            "Beyin yapısı açısından primatlarla benzerlikler taşıyan domuzlar, "
            "birçok zekâ testinde şempanzelere yakın performans gösteriyor."
        ),
        "visual_keywords": ["pig farm intelligent animal", "animal cognition test", "smart animal behavior", "pig close up nature"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Dünya'nın Nüfusu Bir Anda Azalmadan Önce Artıyordu! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Kara_Ölüm",
        "description": "Kara Ölüm Avrupa nüfusunu nasıl etkiledi? #tarih #ilginçbilgiler #shorts",
        "hook": "14. yüzyılda Avrupa nüfusunun üçte biri ile yarısı arasındaki kısmı yalnızca birkaç yılda yok oldu.",
        "script_text": (
            "14. yüzyılda Avrupa nüfusunun üçte biri ile yarısı arasındaki kısmı yalnızca birkaç yılda yok oldu. "
            "1347-1351 yılları arasında Avrupa'yı kasıp kavuran Kara Ölüm yani veba salgını, "
            "tahminlere göre 50 milyon kişinin hayatını kaybetmesine yol açtı. "
            "Bu kayıp o kadar büyüktü ki bazı Avrupa ülkeleri "
            "nüfusunu salgın öncesi seviyeye ancak 200 yıl sonra çıkarabildi. "
            "İlginç olan şu: Bu kaos ücretlerin yükselmesine ve serfliğin sona ermeye başlamasına yol açtı."
        ),
        "visual_keywords": ["black death plague medieval", "14th century europe history", "medieval village disease", "historic cemetery"],
    },
    {
        "topic": "Bilim",
        "title": "Çikolata Yer Çekiminin Olmadığı Yerde Farklı Erir! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Çikolata",
        "description": "Uzayda yemek nasıl değişir? #bilim #uzay #ilginçbilgiler #shorts",
        "hook": "Uzayda çikolata yerseniz farklı bir tat alırsınız çünkü koku reseptörleri yer çekimine duyarlıdır.",
        "script_text": (
            "Uzayda çikolata yerseniz farklı bir tat alırsınız çünkü koku reseptörleri yer çekimine duyarlıdır. "
            "Mikro yerçekimi ortamında burun mukusunu hareket ettiren yerçekimi yoktur; "
            "bu da koku alma duyusunun kısmen körelmesine yol açar. "
            "Astronotlar yiyeceklerin daha yavan tatlandığını sıklıkla bildiriyor. "
            "Tat alma duyusunun yüzde 80'i aslında koku duyusudur; "
            "bu yüzden uzaydaki yemekler Dünya'dakinden çok daha az lezzetli hissettiriyor."
        ),
        "visual_keywords": ["astronaut food space station", "chocolate melting closeup", "zero gravity food", "space snack science"],
    },
    {
        "topic": "Tarih",
        "title": "Şeker Bir Zamanlar Altından Daha Değerliydi! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Şeker",
        "description": "Şeker tarihte neden bu kadar değerliydi? #tarih #ilginçbilgiler #shorts",
        "hook": "Orta Çağ Avrupa'sında şeker o kadar değerliydi ki kilogram fiyatı bir işçinin aylık ücretini geçerdi.",
        "script_text": (
            "Orta Çağ Avrupa'sında şeker o kadar değerliydi ki kilogram fiyatı bir işçinin aylık ücretini geçerdi. "
            "Şeker kamışı yalnızca tropikal iklimde yetişirdi "
            "ve Avrupa'ya uzun deniz yolculuklarıyla taşınırdı. "
            "Kraliyet sofrasında şeker süslemeleri yapılır ve bunlar saatler geçtikten sonra yenirdi. "
            "16. yüzyılda Avrupa soylularının çürük dişleri bir zenginlik göstergesi sayılırdı; "
            "çünkü yalnızca şekeri çok yiyenler bu hale geliyordu."
        ),
        "visual_keywords": ["sugar cane tropical field", "medieval feast royal table", "sweet luxury history", "sugar trade colonial"],
    },
    {
        "topic": "Bilim",
        "title": "Beyin Ağrıyı Hissedemez, Ağrıyı Siz Hissedersiniz! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Beyin",
        "description": "Beyin nasıl çalışır? #bilim #beyin #sağlık #shorts",
        "hook": "Beyin tüm ağrılarınızı işler ama kendisi hiçbir ağrı hissedemez.",
        "script_text": (
            "Beyin tüm ağrılarınızı işler ama kendisi hiçbir ağrı hissedemez. "
            "Beynin ağrı reseptörü yoktur; bu yüzden beyin cerrahisi "
            "lokal anesteziyle yapılabilir ve hasta uyanık olabilir. "
            "Bir nörolog ameliyat sırasında hastaya soru sorar, hasta yanıt verir, "
            "müzik söyler ve el hareketleri yapar; "
            "çünkü beyin kesilip biçilirken ağrı duymaz. "
            "Bu teknik hassas beyin tümörü operasyonlarında büyük avantaj sağlar."
        ),
        "visual_keywords": ["brain surgery operation", "neuroscience brain scan", "brain anatomy visualization", "medical science hospital"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Hollanda Bir Zamanlar Manhattan'ı 24 Dolara Sattı! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Manhattan",
        "description": "Manhattan'ın tarihi satışı nasıl gerçekleşti? #tarih #ilginçbilgiler #shorts",
        "hook": "New York'un kalbi Manhattan, bir zamanlar yalnızca 24 dolarlık ticaret malları karşılığında el değiştirdi.",
        "script_text": (
            "New York'un kalbi Manhattan, bir zamanlar yalnızca 24 dolarlık ticaret malları karşılığında el değiştirdi. "
            "1626'da Hollandalı Peter Minuit, Lenape yerlilerinden "
            "60 florin, yani günümüz değeriyle yaklaşık 24 dolar değerinde boncuk ve bez karşılığında "
            "Manhattan adasını satın aldı. "
            "Ancak tarihçiler bu işlemin gerçekten bir 'satış' mı yoksa bir kira anlaşması mı olduğunu hâlâ tartışıyor. "
            "Ayrıca Lenape'nin bu arazinin kendi toprağı olduğunu da düşünmediği öne sürülüyor."
        ),
        "visual_keywords": ["manhattan new york historic", "native american colonial trade", "new york island aerial", "17th century dutch colony"],
    },
    {
        "topic": "Bilim",
        "title": "Galaksimiz Saniyede 600 Kilometre Hareket Ediyor! #Shorts",
        "source": "NASA Science — https://science.nasa.gov/universe/galaxies/",
        "description": "Samanyolu galaksisi ne kadar hızlı hareket ediyor? #uzay #bilim #shorts",
        "hook": "Şu an hareketsiz oturuyorsunuz ama aslında saniyede 600 kilometre hızla uçuyorsunuz.",
        "script_text": (
            "Şu an hareketsiz oturuyorsunuz ama aslında saniyede 600 kilometre hızla uçuyorsunuz. "
            "Dünya kendi ekseni etrafında dönerken Güneş'in etrafında da yörünge izliyor. "
            "Güneş, Samanyolu galaksisinin merkezini saniyede 220 kilometre hızla dolaşıyor. "
            "Samanyolu ise büyük evren yapısı içinde saniyede yaklaşık 600 kilometre hızla hareket ediyor. "
            "Tüm bu hızlar birleşince siz aslında evrenin içinde muazzam bir hızla süzülüyorsunuz."
        ),
        "visual_keywords": ["milky way galaxy night sky", "space galaxy spiral", "cosmos movement visualization", "universe speed motion"],
    },
    {
        "topic": "Tarih",
        "title": "Osmanlı Padişahı Hüküm Sürdüğü Ülkelerin Hiçbirini Görmedi! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/II._Abdülhamid",
        "description": "Osmanlı İmparatorluğu'nun son döneminin ilginç gerçekleri! #tarih #osmanlı #shorts",
        "hook": "33 yıl hüküm süren Osmanlı padişahı II. Abdülhamid, tahta çıktıktan sonra hiç yurt dışına çıkmadı.",
        "script_text": (
            "33 yıl hüküm süren Osmanlı padişahı II. Abdülhamid, tahta çıktıktan sonra hiç yurt dışına çıkmadı. "
            "1876-1909 yılları arasında hüküm süren padişah, "
            "dünya genelinde kalan Osmanlı topraklarını ve gelen elçileri "
            "yalnızca İstanbul'dan yönetiyor, "
            "dünyanın değişen siyasi dengesini sarayından takip ediyordu. "
            "Suikast korkusuyla şehre çıkmayı bile çok nadiren tercih etti "
            "ve son derece güvenlik odaklı bir yaşam sürdürdü."
        ),
        "visual_keywords": ["ottoman palace istanbul", "sultan throne historic", "topkapi palace turkey", "ottoman empire history"],
    },
    {
        "topic": "Bilim",
        "title": "Örümcek İpeği Çelikten Daha Güçlüdür! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Örümcek_ipeği",
        "description": "Örümcek ipeğinin inanılmaz özellikleri! #doğa #bilim #shorts",
        "hook": "Aynı kalınlıktaki çelikle karşılaştırıldığında örümcek ipeği çok daha güçlüdür.",
        "script_text": (
            "Aynı kalınlıktaki çelikle karşılaştırıldığında örümcek ipeği çok daha güçlüdür. "
            "Örümcek ipeği birim kütleye göre çelikten beş kat daha dayanıklı "
            "ve Kevlar'dan üç kat daha güçlüdür. "
            "Hem esnek hem de sağlamdır; esneyebilir, deformasyona uğruyabilir ama kolay kolay kopmaz. "
            "Bu yüzden bilim insanları onu yapay olarak üretmeye çalışıyor: "
            "Mermi geçirmez yelek, cerrahi iplik ve hatta uzay aracı parçalarında kullanılabilir."
        ),
        "visual_keywords": ["spider web closeup dew", "spider silk macro", "spiderweb morning light", "nature engineering biology"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Alaska ABD'nin Doğusuna Batısına Olduğundan Daha Yakın! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Alaska",
        "description": "Alaska'nın coğrafi konumu hakkında şaşırtıcı bir gerçek! #coğrafya #shorts",
        "hook": "Alaska, Amerika'nın en batı eyaleti olduğu kadar en doğu eyaleti olarak da sayılabilir.",
        "script_text": (
            "Alaska, Amerika'nın en batı eyaleti olduğu kadar en doğu eyaleti olarak da sayılabilir. "
            "Alaska'nın Aleutian adaları 180. meridyeni geçerek Doğu Yarıküre'ye uzanır. "
            "Bu teknik olarak Alaska'yı hem ABD'nin en batı hem de en doğu eyaleti yapar. "
            "Aynı zamanda Alaska, ABD'nin en kuzey eyaletiyken "
            "Florida'dan 5 kat daha büyük bir alana sahip olmasına rağmen "
            "nüfusu Florida'nın yüzde beşinden bile az."
        ),
        "visual_keywords": ["alaska wilderness landscape", "arctic tundra mountains", "aleutian islands map", "alaska coast panorama"],
    },
    {
        "topic": "Bilim",
        "title": "Antarktika Dünyanın En Büyük Çölüdür! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Antarktika",
        "description": "Çöl buzlu olabilir mi? #coğrafya #bilim #shorts",
        "hook": "Dünyanın en büyük çölü Sahra değil, Antarktika'dır.",
        "script_text": (
            "Dünyanın en büyük çölü Sahra değil, Antarktika'dır. "
            "Çöl, yağış miktarının çok az olduğu bölge anlamına gelir; "
            "sıcaklıkla ilgisi yoktur. "
            "Antarktika yılda ortalama yalnızca 166 milimetre yağış alır "
            "ve bu onu dünyanın en kuru kıtası yapar. "
            "Sahra Çölü ise 9,2 milyon km kare ile ancak ikinci sıraya oturur; "
            "Antarktika 14,2 milyon km kare ile açık ara öndedir."
        ),
        "visual_keywords": ["antarctica ice desert polar", "south pole frozen landscape", "polar expedition ice", "sahara desert comparison"],
    },
    {
        "topic": "Tarih",
        "title": "Orta Çağ Şövalyelerinin Miğferleri Çok Tehlikeliydi! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Şövalye",
        "description": "Orta Çağ savaş zırhları ne kadar işlevseldi? #tarih #shorts",
        "hook": "Orta Çağ şövalyelerinin dev miğferleri onları düşmandan değil, kendi sıcaklarından öldürüyordu.",
        "script_text": (
            "Orta Çağ şövalyelerinin dev miğferleri onları düşmandan değil, kendi sıcaklarından öldürüyordu. "
            "14-15. yüzyıl tam plaka zırhları mükemmel koruma sağlasa da "
            "yaz sıcaklarında içi gerçek bir fırına dönüşürdü. "
            "Tarihsel kayıtlar, savaş meydanında ısı bitkinliğinden düşen şövalyelerin "
            "ok veya kılıçtan daha fazla hayat kaybettiğini gösteriyor. "
            "Üstelik yere düşen tam zırhlı bir şövalyenin kendi başına kalkması neredeyse imkânsızdı."
        ),
        "visual_keywords": ["medieval knight armor", "plate armor historical", "castle sword battle", "knight tournament jousting"],
    },
    {
        "topic": "Bilim",
        "title": "Işık Yavaşlayabilir, Sıfır Hıza Bile Düşebilir! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Bose-Einstein_yoğuşması",
        "description": "Işığın hızı sabit midir? #fizik #kuantum #shorts",
        "hook": "Fizik dersinde ışık hızının sabit olduğunu öğrendiniz ama bu yalnızca vakumda geçerli.",
        "script_text": (
            "Fizik dersinde ışık hızının sabit olduğunu öğrendiniz ama bu yalnızca vakumda geçerli. "
            "1999'da Harvard fizikçisi Lene Hau, ışığı Bose-Einstein yoğuşması adlı süper soğuk bir gaz içinden geçirerek "
            "hızını saatte 60 kilometreye indirmeyi başardı. "
            "Daha sonra ekibi ışığı tamamen durdurdu; "
            "fotonlar gazın içinde donarak yerinde bekledi. "
            "Bu deney kuantum bilgisayarlar ve iletişim teknolojisi için devrimsel sonuçlar doğurabilir."
        ),
        "visual_keywords": ["light beam slow down", "quantum physics laboratory", "laser experiment science", "photon physics visualization"],
    },
    {
        "topic": "Tarih",
        "title": "Fatih Sultan Mehmet Gemileri Karadan Nasıl Yürüttü? #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/İstanbul%27un_Fethi",
        "description": "1453 Haliç zinciri ve kızaklarla taşınan Osmanlı donanması #tarih #shorts",
        "hook": "Bizans Haliç'in girişine dev bir zincir gerdiğinde Osmanlı donanmasının geçmesi imkânsız görünüyordu.",
        "script_text": (
            "Bizans Haliç'in girişine dev bir zincir gerdiğinde Osmanlı donanmasının geçmesi imkânsız görünüyordu. "
            "Ancak 22 Nisan 1453 gecesi Fatih Sultan Mehmet tarihin en cüretkâr askeri manevralarından birini başlattı. "
            "Tophane kıyısından Kasımpaşa sırtlarına kadar döşenen yağlanmış ahşap kızaklar üzerinden "
            "yetmişe yakın savaş gemisi öküzler ve binlerce asker yardımıyla karadan çekildi. "
            "Sabah olduğunda Haliç'te Osmanlı yelkenlilerini gören Bizans savunması iki cepheye bölündü ve kuşatmanın kaderi değişti."
        ),
        "visual_keywords": ["ottoman ship sailing", "constantinople medieval walls", "wooden ship ropes", "golden horn istanbul"],
    },
    {
        "topic": "Tarih",
        "title": "1518'de Yüzlerce İnsanı Durmadan Dans Ettiren Salgın! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/1518_Dans_Salgını",
        "description": "Strazburg'da 1518 yılında yaşanan gizemli dans vebası #tarih #shorts",
        "hook": "1518 yazında Strazburg sokaklarında bir kadın aniden dans etmeye başladı ve günlerce duramadı.",
        "script_text": (
            "1518 yazında Strazburg sokaklarında bir kadın aniden dans etmeye başladı ve günlerce duramadı. "
            "Bir hafta içinde otuz dört kişi, bir ay içinde ise yaklaşık dört yüz kişi bu tuhaf harekete katıldı. "
            "İnsanlar ayakları kanayana ve yorgunluktan yere yığılana kadar kontrolsüzce zıplıyordu. "
            "Dönemin belediye meclisi ve hekimleri çavdar küfü zehirlenmesi ile kitlesel psikojenik hastalık arasında kalan bu olayı "
            "ancak müzikleri yasaklayıp hastaları şifahaneye taşıyarak durdurabildi."
        ),
        "visual_keywords": ["strasbourg medieval street", "historical crowd dancing", "old european town", "medieval manuscript art"],
    },
    {
        "topic": "Tarih",
        "title": "Babil'in Asma Bahçeleri Gerçekte Ninova'da mıydı? #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Babil%27in_Asma_Bahçeleri",
        "description": "Antik dünyanın yedi harikasından yeri hâlâ tartışılan tek eser #tarih #shorts",
        "hook": "Antik dünyanın yedi harikasından biri olan Babil'in Asma Bahçeleri aslında Babil'de olmayabilir.",
        "script_text": (
            "Antik dünyanın yedi harikasından biri olan Babil'in Asma Bahçeleri aslında Babil'de olmayabilir. "
            "Arkeologlar Babil kalıntılarında bu devasa teraslara dair hiçbir çivi yazısı kaydı bulamadı. "
            "Oxford Üniversitesi'nden Stephanie Dalley'nin araştırması, bahçelerin gerçekte Asur Kralı Sanherib tarafından "
            "üç yüz kilometre kuzeydeki Ninova şehrinde kurulduğunu gösteriyor. "
            "Arşimet vidası benzeri bronz su pompalarıyla sulanan bu mühendislik harikası yüzyıllar boyunca Babil ile karıştırıldı."
        ),
        "visual_keywords": ["ancient mesopotamia temple", "hanging gardens waterfall", "cuneiform clay tablet", "ancient ruins desert"],
    },
    {
        "topic": "Tarih",
        "title": "Çin İmparatorunu Korumak İçin Yapılan 8 Bin Toprak Asker! #Shorts",
        "source": "UNESCO — https://whc.unesco.org/en/list/441/",
        "description": "Toprak Askerler ordusunda neden hiçbir yüz birbirine benzemiyor? #tarih #shorts",
        "hook": "1974 yılında Çin'de su kuyusu kazan köylüler yerin altında koca bir imparatorluk ordusuyla karşılaştı.",
        "script_text": (
            "1974 yılında Çin'de su kuyusu kazan köylüler yerin altında koca bir imparatorluk ordusuyla karşılaştı. "
            "İlk Çin İmparatoru Çin Şi Huang'ın mezarını korumak için milattan önce üçüncü yüzyılda yapılan "
            "sekiz binden fazla gerçek boyutlu pişmiş toprak asker tek tek işlenmişti. "
            "En çarpıcı ayrıntı ise askerlerin bıyıklarından kulak kıvrımlarına kadar her birinin yüz ifadesinin benzersiz olmasıdır; "
            "üstelik imparatorun asıl mezar odası cıva nehirleri şüphesiyle hâlâ açılmadı."
        ),
        "visual_keywords": ["terracotta warriors china", "ancient chinese sculptures", "archaeological excavation pit", "imperial tomb museum"],
    },
    {
        "topic": "Tarih",
        "title": "Bir Denizaltıyı Tuvalet Arızası Yüzünden Kaybetmek: U-1206! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/U-1206",
        "description": "İkinci Dünya Savaşı'nda yüksek basınçlı valf hatasıyla batan denizaltı #tarih #shorts",
        "hook": "İkinci Dünya Savaşı'nın en gelişmiş Alman denizaltılarından biri düşman torpidosuyla değil, tuvalet arızasıyla battı.",
        "script_text": (
            "İkinci Dünya Savaşı'nın en gelişmiş Alman denizaltılarından biri düşman torpidosuyla değil, tuvalet arızasıyla battı. "
            "Nisan 1945'te Kuzey Denizi'nde seyreden U-1206 denizaltısında derin su basıncına dayanıklı karmaşık bir sifon sistemi vardı. "
            "Valfler yanlış sırayla açılınca deniz suyu hızla içeri doldu ve zemindeki dev bataryalara ulaştı. "
            "Ortaya çıkan ölümcül klor gazı yüzünden komutan yüzeye çıkmak zorunda kaldı "
            "ve İngiliz devriye uçaklarına yakalanan mürettebat gemiyi terk etti."
        ),
        "visual_keywords": ["submarine underwater ocean", "vintage naval control room", "north sea waves", "periscope water surface"],
    },
    {
        "topic": "Tarih",
        "title": "Piri Reis Haritası 1513'te Güney Amerika'yı Nasıl Çizdi? #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Pîrî_Reis_Haritası",
        "description": "Topkapı Sarayı'nda bulunan 1513 tarihli ceylan derisi dünya haritası #tarih #shorts",
        "hook": "1929'da Topkapı Sarayı arşivinde bulunan ceylan derisi bir harita kartografi tarihini sarstı.",
        "script_text": (
            "1929'da Topkapı Sarayı arşivinde bulunan ceylan derisi bir harita kartografi tarihini sarstı. "
            "Osmanlı denizcisi Piri Reis'in 1513 yılında Gelibolu'da çizdiği bu harita, "
            "Avrupa ve Afrika kıyılarının yanı sıra yeni keşfedilen Güney Amerika sahillerini şaşırtıcı bir doğrulukla gösteriyordu. "
            "Piri Reis harita kenarındaki notlarında Arap, Portekiz ve Kristof Kolomb'a ait yirmi farklı eski haritayı "
            "tek bir ölçekte birleştirerek bu eşsiz eseri oluşturduğunu bizzat kaydetmiştir."
        ),
        "visual_keywords": ["antique world map", "compass old parchment", "sailing ship ocean", "istanbul palace archive"],
    },
    {
        "topic": "Tarih",
        "title": "Antik Mısır dilini Çözen Üç Dilli Şifre: Rosetta Taşı! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Rosetta_Taşı",
        "description": "1400 yıl boyunca kimsenin okuyamadığı hiyeroglifler nasıl çözüldü? #tarih #shorts",
        "hook": "Bin dört yüz yıl boyunca yeryüzündeki hiç kimse Mısır tapınaklarındaki hiyerogliflerin ne anlattığını okuyamadı.",
        "script_text": (
            "Bin dört yüz yıl boyunca yeryüzündeki hiç kimse Mısır tapınaklarındaki hiyerogliflerin ne anlattığını okuyamadı. "
            "Ta ki 1799'da Reşid kasabasında siyah granodiyorit bir dikilitaş bulunana kadar. "
            "Rosetta Taşı'nın üzerinde aynı kraliyet kararnamesi hem hiyeroglif hem Demotik hem de Antik Yunanca olarak yazılmıştı. "
            "Fransız dilbilimci Jean-François Champollion 1822'de Yunanca metni anahtar olarak kullanıp firavun isimlerini eşleştirdi "
            "ve binlerce yıllık Mısır kayıtlarının kilidini tamamen açtı."
        ),
        "visual_keywords": ["rosetta stone hieroglyphs", "ancient egyptian carvings", "museum stone artifact", "pharaoh temple wall"],
    },
    {
        "topic": "Tarih",
        "title": "Yazısız İmparatorluk İnkalar Düğümlerle Nasıl Hesap Yaptı? #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Kipu",
        "description": "İnka İmparatorluğu'nun renkli ipler ve düğümlerden oluşan Kipu sistemi #tarih #shorts",
        "hook": "Güney Amerika'nın en büyük imparatorluğunu kuran İnkalar tek bir harf veya tekerlek kullanmadan milyonları yönetti.",
        "script_text": (
            "Güney Amerika'nın en büyük imparatorluğunu kuran İnkalar tek bir harf veya tekerlek kullanmadan milyonları yönetti. "
            "Bunun yerine Kipu adı verilen renkli lama ve pamuk iplerine atılmış özel düğüm dizilerini kullandılar. "
            "Her düğümün şekli, ip üzerindeki konumu ve büküm yönü onluk tabanda nüfus sayımlarını, "
            "vergi kayıtlarını ve erzak depolarındaki stokları hatasız biçimde kodluyordu. "
            "Koşucu haberciler bu düğümlü kayıtları And Dağları'nın taş yollarında elden ele taşıyordu."
        ),
        "visual_keywords": ["machu picchu andes", "knotted ropes textile", "ancient inca ruins", "mountain stone trail"],
    },
    {
        "topic": "Tarih",
        "title": "Roma Betonları 2 Bin Yıldır Deniz Suyunda Neden Çökmüyor? #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Roma_betonu",
        "description": "Modern beton 50 yılda aşınırken Antik Roma limanlarının sırrı neydi? #tarih #shorts",
        "hook": "Modern deniz betonları birkaç on yılda çatlamaya başlarken Antik Roma dalgakıranları iki bin yıldır ayakta duruyor.",
        "script_text": (
            "Modern deniz betonları birkaç on yılda çatlamaya başlarken Antik Roma dalgakıranları iki bin yıldır ayakta duruyor. "
            "MIT ve Berkeley araştırmacıları Roma harcının sırrını volkanik kül ve sönmemiş kireç karışımında buldu. "
            "Sıcak karıştırma tekniğiyle harcın içinde kalan küçük kireç parçacıkları, "
            "betonda mikro çatlak oluştuğunda yağmur veya deniz suyuyla tepkimeye girerek çatlağı kendi kendine yeniden dolduruyor. "
            "Yani Roma betonu zaman geçtikçe zayıflamak yerine kendi kendini onarıyor."
        ),
        "visual_keywords": ["pantheon rome dome", "roman aqueduct stone", "mediterranean sea waves", "ancient harbor ruins"],
    },
    {
        "topic": "Tarih",
        "title": "1816 Yazsız Yıl: Haziran Ayında Neden Kar Yağdı? #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Yazsız_Yıl",
        "description": "Tambora Yanardağı patlamasının dünyayı dondurduğu 1816 yılı #tarih #shorts",
        "hook": "1816 yılında Avrupa ve Kuzey Amerika'da yaz mevsimi hiç gelmedi; haziran ayında göller dondu.",
        "script_text": (
            "1816 yılında Avrupa ve Kuzey Amerika'da yaz mevsimi hiç gelmedi; haziran ayında göller dondu. "
            "Bu küresel soğumanın nedeni bir yıl önce Endonezya'daki Tambora Yanardağı'nın son on bin yılın en şiddetli patlamasını yaşamasıydı. "
            "Stratosfere yükselen milyonlarca ton kükürt dioksit güneş ışığını perdeleyerek küresel sıcaklığı düşürdü. "
            "Hasatlar yandı, kıtlık başladı ve İsviçre'de fırtınadan eve kapanan Mary Shelley bu karanlık yazda Frankenstein romanını yazdı."
        ),
        "visual_keywords": ["volcano ash eruption", "snow storm forest", "dark stormy clouds", "vintage nineteenth century"],
    },
    {
        "topic": "Tarih",
        "title": "1919'da Boston Sokaklarını Basan Dev Melas Dalgası! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Büyük_Boston_Melas_Felaketi",
        "description": "Saatte 56 kilometre hızla şehri yutan 8 milyon litrelik şurup seli #tarih #shorts",
        "hook": "1919 yılında Boston şehrinde sekiz buçuk milyon litrelik dev bir şeker pekmezi tankı aniden patladı.",
        "script_text": (
            "1919 yılında Boston şehrinde sekiz buçuk milyon litrelik dev bir şeker pekmezi tankı aniden patladı. "
            "Yüksekliği yedi metreyi bulan yoğun melas dalgası saatte elli altı kilometre hızla sokaklara yayıldı. "
            "Soğuk kış havasında hızla katılaşan yapışkan sıvı binaları temelinden söktü ve tren raylarını büktü. "
            "Fizikçiler melasın kayma incelmesi özelliği nedeniyle ilk anda tahmin edilenden çok daha hızlı aktığını "
            "ancak soğudukça ölümcül bir tuzağa dönüştüğünü ortaya koydu."
        ),
        "visual_keywords": ["industrial steel tank", "historical city street", "dark thick liquid", "winter harbor port"],
    },
    {
        "topic": "Tarih",
        "title": "1325'te Tek Bir Tahta Kova Yüzünden Çıkan Gerçek Savaş! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Kova_Savaşı",
        "description": "Modena ve Bologna şehir devletleri arasındaki Kova Savaşı #tarih #shorts",
        "hook": "1325 yılında İtalya'daki iki şehir arasında kuyu başından çalınan meşe bir kova yüzünden meydan savaşı çıktı.",
        "script_text": (
            "1325 yılında İtalya'daki iki şehir arasında kuyu başından çalınan meşe bir kova yüzünden meydan savaşı çıktı. "
            "Modena askerleri rakip Bologna şehrine gizlice girip merkez kuyusunun tahta kovasını ganimet olarak kaçırdı. "
            "Gururu kırılan Bologna kovayı geri almak için otuz iki bin kişilik bir ordu topladı. "
            "Zapolino Muharebesi'nde iki bin kişi hayatını kaybetti ama Modena savaşı kazandı "
            "ve o meşe kova bugün hâlâ Modena belediye binasında sergileniyor."
        ),
        "visual_keywords": ["medieval italian tower", "wooden well bucket", "medieval soldiers battle", "historic bologna street"],
    },
    {
        "topic": "Tarih",
        "title": "Çölün Ortasında 2 Bin Yıllık Kaya Şehri: Petra! #Shorts",
        "source": "UNESCO — https://whc.unesco.org/en/list/326/",
        "description": "Nebatilerin pembe kumtaşı kayalara oyduğu su mühendisliği harikası Petra #tarih #shorts",
        "hook": "Ürdün çölünün ortasında dar bir kanyonun sonunda kayalara tek parça halinde oyulmuş kırk metrelik bir tapınak yükselir.",
        "script_text": (
            "Ürdün çölünün ortasında dar bir kanyonun sonunda kayalara tek parça halinde oyulmuş kırk metrelik bir tapınak yükselir. "
            "Nebatiler milattan önce dördüncü yüzyılda kurdukları Petra şehrini pembe kumtaşı uçurumları yukarıdan aşağıya doğru yontarak inşa etti. "
            "Yılda yalnızca birkaç kez yağmur alan bu kurak vadide pişmiş toprak borular, barajlar ve yeraltı sarnıçları kurarak "
            "otuz bin kişinin yaşadığı yemyeşil bir ticaret vahası yarattılar."
        ),
        "visual_keywords": ["petra jordan canyon", "desert sandstone monument", "ancient rock carving", "middle east caravan"],
    },
    {
        "topic": "Tarih",
        "title": "1637'de Tek Bir Lale Soğanı Bir Ev Fiyatına Satıldı! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Lale_çılgınlığı",
        "description": "Hollanda Altın Çağı'nda tarihin ilk ekonomik balonu: Lale Çılgınlığı #tarih #shorts",
        "hook": "1637 yılında Hollanda'da nadir bir lale soğanı Amsterdam'da kanal kıyısındaki bir malikâneyle aynı fiyata satılıyordu.",
        "script_text": (
            "1637 yılında Hollanda'da nadir bir lale soğanı Amsterdam'da kanal kıyısındaki bir malikâneyle aynı fiyata satılıyordu. "
            "Osmanlı topraklarından Avrupa'ya ulaşan laleler, yapraklarında alacalı desenler oluşturan bir bitki virüsü sayesinde "
            "statü sembolüne dönüştü. "
            "Tüccarlar henüz topraktan çıkmamış soğanlar üzerine vadeli sözleşmeler imzaladı "
            "ancak şubat 1637'de alıcılar müzayedeye gelmeyince fiyatlar bir gecede çöktü ve tarihin ilk finansal balonlarından biri patladı."
        ),
        "visual_keywords": ["tulip field netherlands", "amsterdam canal houses", "gold coins trade", "colorful tulip flower"],
    },
    {
        "topic": "Tarih",
        "title": "224 Metre Boyunda Dev Heykel: Rodos Heykeli Nasıldı? #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Rodos_Heykeli",
        "description": "Antik dünyanın en yüksek bronz heykeli depremde yıkılınca neden 800 yıl yerde kaldı? #tarih #shorts",
        "hook": "Antik Rodos limanında yükselen otuz üç metrelik bronz Güneş Tanrısı heykeli Özgürlük Anıtı'nın gövdesiyle aynı boydaydı.",
        "script_text": (
            "Antik Rodos limanında yükselen otuz üç metrelik bronz Güneş Tanrısı heykeli Özgürlük Anıtı'nın gövdesiyle aynı boydaydı. "
            "MÖ 280 yılında kuşatmadan kalan bronz silahların eritilmesiyle on iki yılda tamamlandı. "
            "Ancak sadece elli dört yıl sonra şiddetli bir depremde dizlerinden kırılarak devrildi. "
            "Kâhinler heykelin yeniden dikilmesini uğursuz sayınca devasa bronz parçalar sekiz yüz yıl boyunca olduğu yerde kaldı."
        ),
        "visual_keywords": ["ancient greek harbor", "bronze statue monument", "aegean sea island", "ancient columns ruins"],
    },
    {
        "topic": "Tarih",
        "title": "600 Yıldır Kimsenin Okuyamadığı Gizemli Kitap: Voynich! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Voynich_el_yazması",
        "description": "Karbon testiyle 15. yüzyıla tarihlenen ve kriptologların çözemediği el yazması #tarih #shorts",
        "hook": "Yale Üniversitesi kasasında saklanan iki yüz kırk sayfalık bir kitabın tek bir cümlesi bile altı yüz yıldır okunamadı.",
        "script_text": (
            "Yale Üniversitesi kasasında saklanan iki yüz kırk sayfalık bir kitabın tek bir cümlesi bile altı yüz yıldır okunamadı. "
            "Radyokarbon testiyle 1404 ile 1438 yılları arasına tarihlenen Voynich El Yazması, "
            "dünyada var olmayan bitkilerin çizimleri, astronomik diyagramlar ve bilinmeyen bir alfabeyle dolu. "
            "İkinci Dünya Savaşı'nın en usta şifre çözücüleri ve modern yapay zekâ modelleri "
            "metnin doğal dil istatistiklerine uyduğunu doğrulasa da anlamını hâlâ çözemedi."
        ),
        "visual_keywords": ["ancient manuscript book", "mysterious botanical drawing", "medieval parchment calligraphy", "old library archive"],
    },
    {
        "topic": "Bilim",
        "title": "Nötron Yıldızlarının Çekirdeğinde 'Nükleer Makarna' Var! #Shorts",
        "source": "NASA — https://science.nasa.gov/universe/stars/neutron-stars/",
        "description": "Evrendeki en sağlam madde: çelikten 10 milyar kat güçlü nükleer makarna #bilim #uzay #shorts",
        "hook": "Evrendeki en güçlü maddenin adı astrofizikçiler tarafından resmen nükleer makarna olarak konuldu.",
        "script_text": (
            "Evrendeki en güçlü maddenin adı astrofizikçiler tarafından resmen nükleer makarna olarak konuldu. "
            "Ömrünü tamamlayan dev yıldızların çökmüş çekirdeği olan nötron yıldızlarının kabuğunun altında, "
            "proton ve nötronlar korkunç kütleçekim basıncıyla spagetti ve lazanya katmanlarına benzer şekillerde sıkışır. "
            "Süper bilgisayar simülasyonlarına göre bu nükleer makarna yapısını kırmak için "
            "çeliği kırmaktan tam on milyar kat daha fazla kuvvet gerekir."
        ),
        "visual_keywords": ["neutron star cosmos", "supernova explosion space", "astrophysics simulation glow", "deep space pulsar"],
    },
    {
        "topic": "Bilim",
        "title": "Güneş Sisteminin En Yüksek Dağı Everest'in 3 Katı: Olympus Mons! #Shorts",
        "source": "NASA — https://science.nasa.gov/mars/facts/",
        "description": "Mars'taki 21,9 kilometrelik dev kalkan yanardağı Olympus Mons #uzay #bilim #shorts",
        "hook": "Mars yüzeyinde yükselen Olympus Mons yanardağı o kadar büyüktür ki zirvesi gezegenin atmosferinin dışına taşar.",
        "script_text": (
            "Mars yüzeyinde yükselen Olympus Mons yanardağı o kadar büyüktür ki zirvesi gezegenin atmosferinin dışına taşar. "
            "Yirmi bir virgül dokuz kilometre yüksekliğe ulaşan bu dev kalkan yanardağı Everest Dağı'nın neredeyse üç katıdır "
            "ve taban alanı tüm Fransa topraklarını kaplayacak genişliktedir. "
            "Mars'ta Dünya'daki gibi hareketli tektonik plakalar olmadığı için "
            "lavlar milyarlarca yıl boyunca hep aynı noktadan üst üste birikerek bu devi oluşturdu."
        ),
        "visual_keywords": ["mars planet surface", "volcano crater space", "red planet landscape", "space probe orbit"],
    },
    {
        "topic": "Bilim",
        "title": "Jüpiter'in Kırmızı Leke Fırtınası Dünya'dan Daha Büyük! #Shorts",
        "source": "NASA — https://science.nasa.gov/jupiter/jupiter-facts/",
        "description": "En az 300 yıldır durmadan dönen dev antisiklon fırtınası #uzay #bilim #shorts",
        "hook": "Jüpiter'in üzerindeki Büyük Kırmızı Leke, içine tüm Dünya gezegenini yutabilecek büyüklükte bir fırtınadır.",
        "script_text": (
            "Jüpiter'in üzerindeki Büyük Kırmızı Leke, içine tüm Dünya gezegenini yutabilecek büyüklükte bir fırtınadır. "
            "En az üç yüz yıldır kesintisiz dönen bu dev antisiklonun rüzgâr hızları saatte dört yüz otuz kilometreyi aşar. "
            "Dünya'daki kasırgalar karaya çarptığında sürtünmeyle dağılırken "
            "gaz devi Jüpiter'de katı bir yüzey bulunmadığı için fırtına yüzyıllar boyunca enerjisini kaybetmeden dönmeye devam eder."
        ),
        "visual_keywords": ["jupiter planet storm", "great red spot", "gas giant clouds", "space telescope planet"],
    },
    {
        "topic": "Bilim",
        "title": "Satürn'ün Uydusu Titan'da Su Yerine Sıvı Metan Yağmuru Yağar! #Shorts",
        "source": "NASA — https://science.nasa.gov/saturn/moons/titan/",
        "description": "Güneş sisteminde Dünya dışında yüzeyinde nehir ve deniz bulunan tek gök cismi #uzay #shorts",
        "hook": "Güneş sisteminde Dünya dışında yüzeyinde akarsular, göller ve denizler bulunan tek bir yer var: Satürn'ün uydusu Titan.",
        "script_text": (
            "Güneş sisteminde Dünya dışında yüzeyinde akarsular, göller ve denizler bulunan tek bir yer var: Satürn'ün uydusu Titan. "
            "Ancak eksi yüz yetmiş dokuz derece sıcaklıktaki bu uyduda su kaya kadar sert bir buza dönüşmüştür. "
            "Titan'daki bulutlardan yağmur olarak yağan ve nehirleri dolduran sıvı aslında sıvı metan ve etandır. "
            "Yoğun atmosferi ve düşük yer çekimi sayesinde bir insan Titan'da kollarına kanat taksa uçabilirdi."
        ),
        "visual_keywords": ["saturn rings space", "titan moon atmosphere", "alien planet lake", "cassini spacecraft orbit"],
    },
    {
        "topic": "Bilim",
        "title": "Ay'daki Astronot Ayak İzleri Milyonlarca Yıl Silinmeyecek! #Shorts",
        "source": "NASA — https://science.nasa.gov/moon/facts/",
        "description": "Apollo astronotlarının bıraktığı ayak izleri neden hiç bozulmuyor? #uzay #bilim #shorts",
        "hook": "1969 yılında Ay toprağına basılan ilk ayak izleri aradan geçen on yıllara rağmen ilk günkü kadar net duruyor.",
        "script_text": (
            "1969 yılında Ay toprağına basılan ilk ayak izleri aradan geçen on yıllara rağmen ilk günkü kadar net duruyor. "
            "Çünkü Ay'da rüzgâr, yağmur, akarsu veya volkanik hareketlilik yaratan bir atmosfer yoktur. "
            "Yüzeydeki regolit tozunu yalnızca çok yavaş gerçekleşen mikro göktaşı çarpmaları aşındırabilir. "
            "NASA hesaplamalarına göre Apollo astronotlarının bıraktığı izler on ila yüz milyon yıl boyunca silinmeden kalacak."
        ),
        "visual_keywords": ["astronaut footprint moon", "lunar surface crater", "apollo moonwalk space", "earthrise from moon"],
    },
    {
        "topic": "Bilim",
        "title": "Güneş Her Saniye 4 Milyon Ton Kütlesini Işığa Dönüştürür! #Shorts",
        "source": "NASA — https://science.nasa.gov/sun/facts/",
        "description": "Güneş çekirdeğindeki nükleer füzyon ve E=mc² dönüşümü #uzay #fizik #shorts",
        "hook": "Güneş her bir saniyede dört milyon ton kütlesini doğrudan saf enerjiye ve ışığa dönüştürerek uzaya saçar.",
        "script_text": (
            "Güneş her bir saniyede dört milyon ton kütlesini doğrudan saf enerjiye ve ışığa dönüştürerek uzaya saçar. "
            "On beş milyon derece sıcaklıktaki çekirdekte her saniye altı yüz milyon ton hidrojen helyuma dönüşürken "
            "aradaki dört milyon tonluk kütle farkı Einstein'ın ünlü denklemi uyarınca ışınıma dönüşür. "
            "Buna rağmen Güneş o kadar devasadır ki beş milyar yıllık ömrü boyunca toplam kütlesinin yalnızca binde üçünü kaybedecektir."
        ),
        "visual_keywords": ["sun solar flare", "burning star plasma", "solar eclipse corona", "space sunspot close"],
    },
    {
        "topic": "Bilim",
        "title": "Merkür Güneş'e En Yakın Gezegen Ama En Sıcağı Değil! #Shorts",
        "source": "NASA — https://science.nasa.gov/mercury/facts/",
        "description": "Merkür Güneş'in dibindeyken neden Venüs ondan daha sıcaktır? #uzay #bilim #shorts",
        "hook": "Güneş'e en yakın gezegen Merkür olmasına rağmen Güneş sisteminin en sıcak gezegeni o değildir.",
        "script_text": (
            "Güneş'e en yakın gezegen Merkür olmasına rağmen Güneş sisteminin en sıcak gezegeni o değildir. "
            "Merkür'ün ısıyı hapsedecek kalın bir atmosferi olmadığı için gündüzleri dört yüz otuz dereceye çıkan yüzey sıcaklığı "
            "geceleri eksi yüz seksen dereceye kadar düşer. "
            "Güneş'e ikinci sıradaki Venüs ise yoğun karbondioksit bulutlarının yarattığı kontrolsüz sera etkisi yüzünden "
            "gece gündüz dört yüz altmış beş derecede kurşunu eritecek kadar sıcak kalır."
        ),
        "visual_keywords": ["mercury planet craters", "solar system planets", "venus thick clouds", "sun heat space"],
    },
    {
        "topic": "Bilim",
        "title": "Dünya'nın İç Çekirdeği Güneş Yüzeyi Kadar Sıcak! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Yer%27in_iç_çekirdeği",
        "description": "Ayaklarımızın 5 bin kilometre altındaki katı demir-nikel küre neden erimiyor? #bilim #shorts",
        "hook": "Ayaklarımızın beş bin kilometre altında Güneş'in yüzeyiyle aynı sıcaklıkta dev bir demir küre dönüyor.",
        "script_text": (
            "Ayaklarımızın beş bin kilometre altında Güneş'in yüzeyiyle aynı sıcaklıkta dev bir demir küre dönüyor. "
            "Dünya'nın iç çekirdeğinin sıcaklığı yaklaşık beş bin dört yüz santigrat derecedir. "
            "Normalde demir bu sıcaklıkta çoktan buharlaşması gerekirken, "
            "üzerindeki üç buçuk milyon atmosferlik muazzam basınç atomları birbirine kenetleyerek çekirdeği katı halde tutar "
            "ve gezegenimizi kozmik radyasyondan koruyan manyetik kalkanı besler."
        ),
        "visual_keywords": ["earth core layers", "molten lava magma", "planet magnetic field", "geology earth cross"],
    },
    {
        "topic": "Bilim",
        "title": "Tek Bir İnsanın DNA'sını Uç Uca Ekleseniz Plüton'a Ulaşır! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/DNA",
        "description": "Hücre çekirdeğine sığan 2 metrelik DNA zincirinin toplam uzunluğu #bilim #biyoloji #shorts",
        "hook": "Vücudunuzdaki tek bir hücrenin içinde bulunan DNA sarmalını açıp düzleştirseniz boyu yaklaşık iki metre olur.",
        "script_text": (
            "Vücudunuzdaki tek bir hücrenin içinde bulunan DNA sarmalını açıp düzleştirseniz boyu yaklaşık iki metre olur. "
            "İnsan vücudunda bulunan trilyonlarca çekirdekli hücredeki tüm DNA ipliklerini uç uca eklediğinizde ise "
            "toplam uzunluk on milyarlarca kilometreye ulaşır. "
            "Bu mesafe Dünya'dan Güneş sisteminin sınırındaki cüce gezegen Plüton'a gidip geri dönmeye yetecek kadar uzundur."
        ),
        "visual_keywords": ["dna double helix", "microscope cell biology", "genetic code strand", "deep space pluto"],
    },
    {
        "topic": "Bilim",
        "title": "Mide Asidiniz Jileti Eritir Ama Midenizi Neden Eritmez? #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Mide_öz_suyu",
        "description": "pH değeri 1,5 olan hidroklorik asit ve kendini 3 günde bir yenileyen mukoza #bilim #shorts",
        "hook": "İnsan midesindeki hidroklorik asit o kadar güçlüdür ki paslanmaz çelik bir jileti bile aşındırabilir.",
        "script_text": (
            "İnsan midesindeki hidroklorik asit o kadar güçlüdür ki paslanmaz çelik bir jileti bile aşındırabilir. "
            "pH değeri bir buçuk ile iki arasında olan bu güçlü asit midenin kendi duvarını yakmaz; "
            "çünkü mide yüzeyi bikarbonat açısından zengin yoğun bir mukus kalkanıyla kaplıdır. "
            "Ayrıca mide iç yüzeyindeki epitel hücreleri her üç ila beş günde bir tamamen yenilenerek olası hasarı anında kapatır."
        ),
        "visual_keywords": ["science chemistry acid", "microscope cells biology", "laboratory glass beaker", "human anatomy medical"],
    },
    {
        "topic": "Bilim",
        "title": "Mantis Karidesi Kaynar Su Çıkaran Yumruk Atar! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Mantis_karidesi",
        "description": "22 kalibrelik mermi hızıyla vuran ve kavitasyon kabarcığı üreten deniz canlısı #bilim #shorts",
        "hook": "Okyanus tabanında yaşayan on santimetrelik mantis karidesi, yirmi iki kalibrelik mermi hızıyla yumruk atar.",
        "script_text": (
            "Okyanus tabanında yaşayan on santimetrelik mantis karidesi, yirmi iki kalibrelik mermi hızıyla yumruk atar. "
            "Saniyede yirmi üç metre hıza ulaşan bu darbe o kadar hızlıdır ki önündeki suyu buharlaştırarak kavitasyon kabarcıkları oluşturur. "
            "Bu mikro kabarcıklar çöktüğünde ikinci bir şok dalgası ve anlık ışık parlaması üretir; "
            "böylece karidesin yumruğu hedefi ıskalasa bile oluşan basınç dalgası yengeç kabuğunu parçalar."
        ),
        "visual_keywords": ["mantis shrimp coral", "underwater ocean reef", "colorful marine life", "water bubble shockwave"],
    },
    {
        "topic": "Bilim",
        "title": "Kalbi ve Beyni Olmadan Labirent Çözen Canlı: Cıvık Mantar! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Physarum_polycephalum",
        "description": "Tokyo metro ağını mühendislerle aynı verimlilikte yeniden çizen tek hücreli #bilim #shorts",
        "hook": "Beyni, sinir sistemi veya gözü olmayan sarı bir cıvık mantar, Tokyo demiryolu ağını mühendisler kadar kusursuz tasarladı.",
        "script_text": (
            "Beyni, sinir sistemi veya gözü olmayan sarı bir cıvık mantar, Tokyo demiryolu ağını mühendisler kadar kusursuz tasarladı. "
            "Physarum polycephalum adlı bu tek hücreli organizma, yulaf ezmesi parçalarının Tokyo çevresindeki şehirler gibi dizildiği deneyde "
            "yirmi altı saat içinde tüm noktaları en kısa ve en güvenli tüplerle birbirine bağladı. "
            "Biyologlar bu canlının kimyasal titreşimlerle hafıza benzeri kararlar alabildiğini kanıtladı."
        ),
        "visual_keywords": ["yellow slime mold", "petri dish laboratory", "tokyo train network", "microscope biological growth"],
    },
    {
        "topic": "Bilim",
        "title": "Grönland Köpekbalığı 400 Yıl Yaşayıp Tarihe Tanıklık Ediyor! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Grönland_köpek_balığı",
        "description": "Omurgalılar dünyasının en uzun ömürlü canlısı nasıl 400 yıl yaşıyor? #bilim #doğa #shorts",
        "hook": "Kuzey Atlantik'in buzlu sularında bugün yüzmekte olan bazı Grönland köpekbalıkları Osmanlı'nın yükseliş döneminde doğdu.",
        "script_text": (
            "Kuzey Atlantik'in buzlu sularında bugün yüzmekte olan bazı Grönland köpekbalıkları Osmanlı'nın yükseliş döneminde doğdu. "
            "Kopenhag Üniversitesi'nin göz merceği radyokarbon analizleri, bu omurgalıların dört yüz yıla kadar yaşayabildiğini gösterdi. "
            "Sıfır derecenin altındaki sularda yılda yalnızca bir santimetre büyüyen bu canlılar, "
            "aşırı yavaş metabolizmaları sayesinde erişkinliğe bile ancak yüz elli yaşında ulaşıyor."
        ),
        "visual_keywords": ["shark underwater ocean", "arctic ice water", "deep sea creature", "cold ocean diving"],
    },
    {
        "topic": "Bilim",
        "title": "Mavi Balinanın Kalbi Küçük Bir Otomobil Boyutundadır! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Mavi_balina",
        "description": "Dünya tarihinde yaşamış en büyük hayvan olan mavi balinanın anatomisi #bilim #doğa #shorts",
        "hook": "Yeryüzünde yaşamış en büyük dinozordan bile daha ağır olan mavi balinanın yalnızca kalbi yüz seksen kilogramdır.",
        "script_text": (
            "Yeryüzünde yaşamış en büyük dinozordan bile daha ağır olan mavi balinanın yalnızca kalbi yüz seksen kilogramdır. "
            "Küçük bir otomobil boyutundaki bu dev kalp, balina derine daldığında dakikada yalnızca dört ila sekiz kez atar "
            "ve her atışta iki yüzยirmi litre kan pompalar. "
            "Aort damarı o kadar geniştir ki bir su borusu gibi içinden bir çocuk rahatlıkla geçebilir."
        ),
        "visual_keywords": ["blue whale ocean", "giant whale swimming", "deep blue sea", "marine mammal nature"],
    },
    {
        "topic": "Bilim",
        "title": "Sıfırın Altında 271 Derecede Kavanozdan Tırmanıp Kaçan Sıvı Helyum! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Süperakışkanlık",
        "description": "Sürtünmesi tamamen sıfırlanan süperakışkan helyumun yer çekimine meydan okuması #fizik #shorts",
        "hook": "Helyum gazını mutlak sıfırın iki derece üstüne kadar soğuttuğunuzda fizik kurallarına meydan okuyan bir süperakışkana dönüşür.",
        "script_text": (
            "Helyum gazını mutlak sıfırın iki derece üstüne kadar soğuttuğunuzda fizik kurallarına meydan okuyan bir süperakışkana dönüşür. "
            "Eksi iki yüz yetmiş bir derecede iç sürtünmesi tamamen sıfırlanan sıvı helyum, "
            "içine konulduğu cam kabın duvarlarından ince bir film halinde yukarı doğru tırmanarak dışarı taşar. "
            "Kuantum mekaniğinin gözle görülebilen bu halinde sıvıyı bir kez döndürdüğünüzde sonsuza dek durmadan dönebilir."
        ),
        "visual_keywords": ["liquid nitrogen cryogenics", "physics laboratory experiment", "cold vapor glass", "quantum science lab"],
    },
    {
        "topic": "Bilim",
        "title": "Sezyum Atom Saati 100 Milyon Yılda Sadece 1 Saniye Şaşar! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Atom_saati",
        "description": "Modern dünyada 1 saniye nasıl tanımlanır ve GPS uyduları atom saati olmadan neden çalışmaz? #bilim #shorts",
        "hook": "Kolunuzdaki saat ayda birkaç saniye şaşarken modern atom saatleri yüz milyon yılda bir saniye bile geri kalmaz.",
        "script_text": (
            "Kolunuzdaki saat ayda birkaç saniye şaşarken modern atom saatleri yüz milyon yılda bir saniye bile geri kalmaz. "
            "Uluslararası birim sisteminde bir saniye, Sezyum-133 atomunun tam dokuz milyar yüz doksan iki milyon kez titreşmesiyle tanımlanır. "
            "Telefonunuzdaki GPS navigasyon sistemi uydulardaki bu atom saatlerinin milyarda bir saniyelik zaman farkını ölçerek "
            "dünya üzerindeki konumunuzu birkaç metre hassasiyetle bulur."
        ),
        "visual_keywords": ["atomic clock laser", "satellite orbit earth", "precision physics lab", "time gears technology"],
    },
    {
        "topic": "Bilim",
        "title": "Kıtalar Tırnaklarımızın Uzama Hızıyla Hareket Ediyor! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Levha_tektoniği",
        "description": "Avrupa ile Amerika her yıl birbirinden kaç santimetre uzaklaşıyor? #bilim #coğrafya #shorts",
        "hook": "Üzerinde yaşadığımız kıtalar aslında dev manto tabakasının üzerinde parmak tırnaklarımızın uzama hızıyla yüzüyor.",
        "script_text": (
            "Üzerinde yaşadığımız kıtalar aslında dev manto tabakasının üzerinde parmak tırnaklarımızın uzama hızıyla yüzüyor. "
            "Levha tektoniği ölçümlerine göre Kuzey Amerika ile Avrupa kıtası her yıl birbirinden yaklaşık iki buçuk santimetre uzaklaşır. "
            "Bu küçük hareket milyonlarca yıl boyunca biriktiğinde okyanusları açar, "
            "Hindistan levhasının Avrasya'ya çarpmasıyla olduğu gibi Himalaya Dağları'nı gökyüzüne doğru yükseltmeye devam eder."
        ),
        "visual_keywords": ["himalaya mountains peak", "earth continents globe", "tectonic rift iceland", "ocean ridge geology"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Dünyanın Tüm Tohumlarını Saklayan Kıyamet Ambarı: Svalbard! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Svalbard_Küresel_Tohum_Deposu",
        "description": "Kuzey Kutbu'na 1300 km uzaklıkta dağın 120 metre içine oyulan tohum kasası #bilim #shorts",
        "hook": "Kuzey Kutbu yakınlarındaki buzlu bir dağın yüz yirmi metre derinliğinde insanlığın tarım sigortası saklanıyor.",
        "script_text": (
            "Kuzey Kutbu yakınlarındaki buzlu bir dağın yüz yirmi metre derinliğinde insanlığın tarım sigortası saklanıyor. "
            "Norveç'e bağlı Svalbard takımadalarında kurulan Küresel Tohum Deposu, "
            "dünyanın dört bir yanından gelen bir milyondan fazla bitki tohumu örneğini eksi on sekiz derecede koruyor. "
            "Elektrik tamamen kesilse bile çevredeki kalıcı donmuş toprak sayesinde tohumlar yüzyıllar boyunca bozulmadan kalabiliyor."
        ),
        "visual_keywords": ["arctic snow mountain", "seed vault storage", "frozen tundra norway", "plant seeds agriculture"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Okulda Öğretilen Dil Tat Haritası 100 Yıllık Bir Çeviri Hatası! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Dil_haritası",
        "description": "Dilimizin ucu tatlıyı, yanları ekşiyi mi alır? Gerçek bilimsel açıklama #bilim #shorts",
        "hook": "Okul kitaplarında dilin ucunun yalnızca tatlıyı, arkasının acıyı aldığı söylenen şema aslında yanlış bir çeviriydi.",
        "script_text": (
            "Okul kitaplarında dilin ucunun yalnızca tatlıyı, arkasının acıyı aldığı söylenen şema aslında yanlış bir çeviriydi. "
            "1901 tarihli bir Alman makalesindeki küçük duyarlılık farkları 1942'de İngilizceye aktarılırken "
            "sanki her bölge tek bir tadı algılıyormuş gibi yanlış yorumlandı. "
            "Modern nörobiyoloji, tatlı, tuzlu, ekşi, acı ve umami olmak üzere beş temel tadın "
            "dil üzerindeki tüm tat tomurcukları tarafından algılanabildiğini kanıtlamıştır."
        ),
        "visual_keywords": ["Culinary tasting food", "science microscope receptor", "fresh lemon citrus", "neuroscience brain taste"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Dünya'nın En Sessiz Odasında Kendi Kan Akışınızı Duyarsınız! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Yankısız_oda",
        "description": "Eksi 20 desibel ses seviyesine sahip yankısız odaların akustik sırrı #bilim #shorts",
        "hook": "Dünyanın en sessiz odasında arka plan gürültüsü sıfırın bile altındadır; içeride duyduğunuz tek ses kendi vücudunuzdur.",
        "script_text": (
            "Dünyanın en sessiz odasında arka plan gürültüsü sıfırın bile altındadır; içeride duyduğunuz tek ses kendi vücudunuzdur. "
            "Microsoft ve Orfield laboratuvarlarındaki yankısız odalar, fiberglas kamalar ve çelik yaylar üzerinde yüzen duvarlarla "
            "ses dalgalarının yüzde doksan dokuz virgül dokuzunu emer. "
            "Eksi yirmi desibele inen bu ortamda birkaç dakika sonra kalp atışınızı, "
            "akciğerlerinizdeki havayı ve damarlarınızdaki kanın uğultusunu net biçimde işitirsiniz."
        ),
        "visual_keywords": ["acoustic foam studio", "sound wave visualization", "quiet dark room", "audio engineering lab"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Bambu Bitkisi Tek Bir Günde 90 Santimetre Uzayabilir! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Bambu",
        "description": "Saatte neredeyse 4 santimetre büyüyen dünyanın en hızlı bitkisi #doğa #bilim #shorts",
        "hook": "Bazı bambu türleri o kadar hızlı büyür ki sabırlıysanız uzamasını neredeyse gözünüzle takip edebilirsiniz.",
        "script_text": (
            "Bazı bambu türleri o kadar hızlı büyür ki sabırlıysanız uzamasını neredeyse gözünüzle takip edebilirsiniz. "
            "Buğdaygiller ailesinden olan dev bambu türleri uygun yağış ve sıcaklıkta yirmi dört saat içinde doksan santimetreye kadar boy atar. "
            "Üstelik çelikten daha yüksek çekme dayanımına sahip lifli gövdesi sayesinde "
            "Asya'da gökdelen iskelelerinden depreme dayanıklı köprülere kadar pek çok yapıda kullanılır."
        ),
        "visual_keywords": ["green bamboo forest", "tall bamboo stalks", "tropical rainforest nature", "plant growth timelapse"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Pasifik Okyanusu Tüm Kıtaların Toplamından DahaBüyüktür! #Shorts".replace("DahaBüyüktür", "Daha Büyüktür"),
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Büyük_Okyanus",
        "description": "165 milyon kilometrekarelik Büyük Okyanus'un inanılmaz ölçeği #coğrafya #bilim #shorts",
        "hook": "Büyük Okyanus o kadar devasadır ki dünyadaki tüm kıtaları ve adaları birleştirip içine koysanız yine de boş yer kalır.",
        "script_text": (
            "Büyük Okyanus o kadar devasadır ki dünyadaki tüm kıtaları ve adaları birleştirip içine koysanız yine de boş yer kalır. "
            "Yüz altmış beş milyon kilometrekarelik alanıyla Dünya yüzeyinin yaklaşık üçte birini tek başına kaplar. "
            "Hatta Güney Amerika'daki Kolombiya kıyısından Asya'daki Malay Yarımadası'na uzanan en geniş noktasında "
            "yan yana beş tane Ay sığacak kadar büyük bir su kütlesi uzanır."
        ),
        "visual_keywords": ["pacific ocean waves", "planet earth blue", "deep ocean horizon", "satellite view ocean"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Kargalar Kendilerine Kötü Davranan Yüzleri Yıllarca Unutmaz! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Karga",
        "description": "Seattle Üniversitesi'nin maskeli karga hafızası deneyi #bilim #doğa #shorts",
        "hook": "Bir kargaya kötü davranırsanız yalnızca o karga değil, mahalledeki diğer kargalar da yüzünüzü yıllarca hatırlar.",
        "script_text": (
            "Bir kargaya kötü davranırsanız yalnızca o karga değil, mahalledeki diğer kargalar da yüzünüzü yıllarca hatırlar. "
            "Washington Üniversitesi'nde yapılan ünlü deneyde araştırmacılar özel bir maske takarak kargaları yakalayıp bıraktı. "
            "Yıllar sonra aynı maskeyle kampüste yürüyen kişilere, o gün orada olmayan genç kargalar bile "
            "alarm çığlıkları atarak tepki gösterdi; çünkü yetişkin kargalar tehlikeli yüz bilgisini sürüye öğretmişti."
        ),
        "visual_keywords": ["black crow bird", "intelligent bird tree", "raven flying sky", "wildlife nature observation"],
    },
    {
        "topic": "İlginç Bilgiler",
        "title": "Eyfel Kulesi Yaz Aylarında Sıcaktan 15 Santimetre Uzar! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Eyfel_Kulesi",
        "description": "Isıl genleşme nedeniyle yazın boyu uzayan ve güneşe göre eğilen demir kule #bilim #shorts",
        "hook": "Paris'in simgesi Eyfel Kulesi kışın ve yazın aynı boyda değildir; sıcak havalarda on beş santimetreye kadar uzar.",
        "script_text": (
            "Paris'in simgesi Eyfel Kulesi kışın ve yazın aynı boyda değildir; sıcak havalarda on beş santimetreye kadar uzar. "
            "Yedi bin üç yüz ton dövme demirden inşa edilen kafes yapı, güneş altında ısındığında "
            "metal atomlarının titreşimi artar ve ısıl genleşme meydana gelir. "
            "Ayrıca güneş kulenin yalnızca bir cephesini ısıttığında tepe noktası güneşten uzağa doğru birkaç santimetre eğilir."
        ),
        "visual_keywords": ["eiffel tower paris", "iron structure architecture", "sunny paris skyline", "steel beams engineering"],
    },
    {
        "topic": "Tarih",
        "title": "Mimar Sinan Süleymaniye'de Devekuşu Yumurtasını Neden Kullandı? #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Süleymaniye_Camii",
        "description": "Süleymaniye Camii'ndeki akustik küpler, is odası ve örümcek kovucu yumurtalar #tarih #shorts",
        "hook": "Mimar Sinan, Süleymaniye Camii'nin avizelerinin arasına süs olsun diye değil, örümcekleri uzak tutmak için devekuşu yumurtaları astı.",
        "script_text": (
            "Mimar Sinan, Süleymaniye Camii'nin avizelerinin arasına süs olsun diye değil, örümcekleri uzak tutmak için devekuşu yumurtaları astı. "
            "Yüzyıllar boyunca kurudukça yaydığı özel koku sayesinde yüksek kubbelerde örümcek ağı oluşmasını engelledi. "
            "Bununla da yetinmeyen Sinan, kandillerden çıkan siyah dumanı hava akımıyla tek bir is odasında topladı "
            "ve bu isten en kaliteli hat mürekkebini üreterek sıfır atıklı bir mühendislik kurdu."
        ),
        "visual_keywords": ["suleymaniye mosque istanbul", "ottoman dome architecture", "calligraphy ink art", "historic chandelier mosque"],
    },
    {
        "topic": "Tarih",
        "title": "1349'da Altın Değerinde Tutulan Baharat: Karabiber! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Baharat_Yolu",
        "description": "Orta Çağ Avrupa'sında vergi ve kira ödemekte kullanılan karabiber taneleri #tarih #shorts",
        "hook": "Bugün her yemek masasında duran karabiber, Orta Çağ Avrupa'sında gramı gramına altınla takas edilen bir servetti.",
        "script_text": (
            "Bugün her yemek masasında duran karabiber, Orta Çağ Avrupa'sında gramı gramına altınla takas edilen bir servetti. "
            "Hindistan'ın Malabar kıyılarından binlerce kilometrelik Baharat Yolu'nu aşarak gelen karabiber taneleri "
            "vergi ödemelerinde, çeyizlerde ve ev kiralarında nakit para yerine geçiyordu. "
            "Hatta Londra limanındaki rıhtım işçilerinin ceplerine tek bir tane bile saklamaması için kıyafetlerinin cepleri dikilirdi."
        ),
        "visual_keywords": ["black pepper spices", "medieval trade ship", "gold coins scale", "spice market bazaar"],
    },
    {
        "topic": "Tarih",
        "title": "Birinci Dünya Savaşı'nda Cephede Noel Ateşkesi: 1914! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Noel_Ateşkesi",
        "description": "1914 Aralık ayında siperlerden çıkıp hediyeleşen askerlerin gerçek hikâyesi #tarih #shorts",
        "hook": "1914 yılının dondurucu aralık gecesinde Batı Cephesi'ndeki siperlerde silahlar komutanların emri olmadan aniden sustu.",
        "script_text": (
            "1914 yılının dondurucu aralık gecesinde Batı Cephesi'ndeki siperlerde silahlar komutanların emri olmadan aniden sustu. "
            "Alman ve İngiliz askerleri siperlerinden çıkıp tarafsız bölgede buluştu, düğme ve çikolata takas etti. "
            "Yüz bin kadar askerin katıldığı bu gayriresmî ateşkeste donmuş toprakta futbol maçları bile oynandı; "
            "ancak üst komutanlık bu kardeşlik görüntüsünden korkarak sonraki yıllarda benzer buluşmaları kesin emirle yasakladı."
        ),
        "visual_keywords": ["winter snow trench", "vintage world war", "soldiers historic photo", "frosty field winter"],
    },
    {
        "topic": "Tarih",
        "title": "Çatalhöyük'te Sokak ve Kapı Yoktu, Evlere Çatıdan Girilirdi! #Shorts",
        "source": "UNESCO — https://whc.unesco.org/en/list/1405/",
        "description": "Konya Ovası'ndaki 9 bin yıllık Neolitik kent Çatalhöyük'ün mimarisi #tarih #arkeoloji #shorts",
        "hook": "Dokuz bin yıl önce Konya Ovası'nda kurulan Çatalhöyük'te ne tek bir sokak ne de evlerin önünde kapı vardı.",
        "script_text": (
            "Dokuz bin yıl önce Konya Ovası'nda kurulan Çatalhöyük'te ne tek bir sokak ne de evlerin önünde kapı vardı. "
            "Sekiz bine yakın insanın yaşadığı bu Neolitik yerleşimde kerpiç evler aralarında hiç boşluk bırakılmadan bitişik inşa edilmişti. "
            "İnsanlar günlük hayatlarını düz damların üzerinde sürdürüyor, evlerinin içine ise tavandaki delikten ahşap merdivenle iniyordu; "
            "bu tasarım kenti hem yırtıcı hayvanlara hem de dış saldırılara karşı doğal bir kaleye dönüştürüyordu."
        ),
        "visual_keywords": ["neolithic mudbrick houses", "archaeological site anatolia", "ancient pottery artifact", "rooftop ladder village"],
    },
    {
        "topic": "Tarih",
        "title": " İskender'in Feneri Geceleri 50 Kilometre Öteden Görülüyordu! #Shorts".strip(),
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/İskenderiye_Feneri",
        "description": "Yüzyıllar boyunca insan yapımı en yüksek kulelerden biri olan Pharos Feneri #tarih #shorts",
        "hook": "Akdeniz'deki gemicilere yol gösteren İskenderiye Feneri, yüz metreyi aşan boyuyla antik dünyanın gökdeleniydi.",
        "script_text": (
            "Akdeniz'deki gemicilere yol gösteren İskenderiye Feneri, yüz metreyi aşan boyuyla antik dünyanın gökdeleniydi. "
            "Pharos Adası üzerine beyaz taş bloklar ve erimiş kurşun kenetlerle inşa edilen kulenin tepesinde "
            "gündüzleri güneş ışığını yansıtan dev cilalı bronz aynalar, geceleri ise hiç sönmeyen büyük bir ateş yanıyordu. "
            "Üç büyük depreme kadar bin altı yüz yıl ayakta kalan fenerin taşları daha sonra Kayıtbay Kalesi'nin yapımında kullanıldı."
        ),
        "visual_keywords": ["ancient lighthouse sea", "mediterranean harbor night", "stone fortress coast", "ocean waves beacon"],
    },
    {
        "topic": "Bilim",
        "title": "Dünya'nın En Derin Sondajı 12 Kilometrede Neden Durduruldu? #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Kola_Süperderin_Sondajı",
        "description": "Kola Yarımadası'nda 20 yıl süren ve 12.262 metreye inen bilimsel sondaj #bilim #shorts",
        "hook": "İnsanlığın yerin altına kazdığı en derin delik olan Kola Süperderin Sondajı on iki bin iki yüz altmış iki metreye ulaştı.",
        "script_text": (
            "İnsanlığın yerin altına kazdığı en derin delik olan Kola Süperderin Sondajı on iki bin iki yüz altmış iki metreye ulaştı. "
            "1970'te başlayan projede bilim insanları yedi kilometre derinlikte iki milyar yıllık mikroskobik plankton fosilleriyle karşılaştı. "
            "Ancak on iki kilometreyi geçtiklerinde sıcaklık beklenen yüz derece yerine yüz seksen dereceye fırladı; "
            "kayalar erimiş plastik gibi davranıp matkap uçlarını sıkıştırınca sondaj 1992'de durduruldu."
        ),
        "visual_keywords": ["drilling rig industrial", "deep earth core", "geology rock samples", "arctic tundra russia"],
    },
    {
        "topic": "Bilim",
        "title": "Halley Kuyruklu Yıldızı 2061 Yılında Geri Dönecek! #Shorts",
        "source": "NASA — https://science.nasa.gov/solar-system/comets/1p-halley/",
        "description": "İnsan ömründe iki kez görülebilen tek parlak kuyruklu yıldız #uzay #bilim #shorts",
        "hook": "Güneş etrafındaki turunu yaklaşık yetmiş beş yılda tamamlayan Halley Kuyruklu Yıldızı şimdi geri dönüş yolunda.",
        "script_text": (
            "Güneş etrafındaki turunu yaklaşık yetmiş beş yılda tamamlayan Halley Kuyruklu Yıldızı şimdi geri dönüş yolunda. "
            "En son 1986 yılında iç Güneş sisteminden geçen on beş kilometre uzunluğundaki bu buz ve toz çekirdeği, "
            "Aralık 2023'te Neptün yörüngesinin ötesindeki en uzak noktasına ulaştı ve yeniden Güneş'e doğru hızlanmaya başladı. "
            "Takvimler 2061 yazını gösterdiğinde gökyüzünde bir kez daha çıplak gözle parlayacak."
        ),
        "visual_keywords": ["bright comet night", "starry sky galaxy", "solar system orbit", "deep space ice"],
    },
    {
        "topic": "Bilim",
        "title": "Uluslararası Uzay İstasyonu Günde 16 Kez Gün Doğumu Görür! #Shorts",
        "source": "NASA — https://www.nasa.gov/international-space-station/",
        "description": "Saatte 28 bin kilometre hızla Dünya etrafında dönen uzay laboratuvarı #uzay #bilim #shorts",
        "hook": "Başımızın dört yüz kilometre üzerindeki Uluslararası Uzay İstasyonu'nda yaşayan astronotlar her doksan dakikada bir dünyayı turlar.",
        "script_text": (
            "Başımızın dört yüz kilometre üzerindeki Uluslararası Uzay İstasyonu'nda yaşayan astronotlar her doksan dakikada bir dünyayı turlar. "
            "Saatte yirmi sekiz bin kilometre hızla uçan bu dev yörünge laboratuvarında "
            "yirmi dört saat içinde tam on altı kez güneş doğar ve on altı kez güneş batar. "
            "Futbol sahası büyüklüğündeki istasyon, biyolojiden malzeme fiziğine kadar binlerce mikro yer çekimi deneyine ev sahipliği yapıyor."
        ),
        "visual_keywords": ["international space station", "earth orbit sunrise", "astronaut cupola window", "planet earth night"],
    },
    {
        "topic": "Bilim",
        "title": "Bukalemunlar Kamuflaj İçin Değil, Duygularını Anlatmak İçin Renk Değiştirir! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Bukalemun",
        "description": "Bukalemun derisindeki nano kristaller ışığı nasıl kırar? #bilim #doğa #shorts",
        "hook": "Bukalemunların bulunduğu dalın rengine uyum sağlamak için renk değiştirdiği düşüncesi yaygın bir yanılgıdır.",
        "script_text": (
            "Bukalemunların bulunduğu dalın rengine uyum sağlamak için renk değiştirdiği düşüncesi yaygın bir yanılgıdır. "
            "Cenevre Üniversitesi araştırmacıları, bukalemunların asıl olarak vücut sıcaklığını ayarlamak ve diğer bukalemunlara mesaj vermek için renk değiştirdiğini gösterdi. "
            "Derilerinin altındaki iridofor hücrelerinde bulunan mikroskobik kristallerin arasındaki mesafeyi kasılıp gevşeyerek değiştirirler; "
            "böylece pigment boyası üretmeden tıpkı bir prizma gibi yansıyan ışığın dalga boyunu saniyeler içinde kaydırırlar."
        ),
        "visual_keywords": ["colorful chameleon lizard", "tropical green leaf", "reptile eye macro", "prism light rainbow"],
    },
    {
        "topic": "Bilim",
        "title": "Ağaçlar Yer Altındaki Mantar Ağıyla Birbirine Haber Gönderir! #Shorts",
        "source": "Wikipedia (tr) — https://tr.wikipedia.org/wiki/Mikoriza",
        "description": "Orman tabanındaki mikoriza mantar ağı ve ağaçların besin paylaşımı #bilim #doğa #shorts",
        "hook": "Bir ormanda yürürken gördüğünüz ağaçlar aslında toprağın altında devasa bir biyolojik iletişim ağıyla birbirine bağlıdır.",
        "script_text": (
            "Bir ormanda yürürken gördüğünüz ağaçlar aslında toprağın altında devasa bir biyolojik iletişim ağıyla birbirine bağlıdır. "
            "Mikoriza adı verilen ince mantar iplikçikleri ağaç köklerini birbirine bağlayarak karbon, su ve azot alışverişi sağlar. "
            "Böcek saldırısına uğrayan bir ağaç bu mantar ağı üzerinden komşu ağaçlara kimyasal uyarı sinyalleri gönderir "
            "ve komşu ağaçlar henüz böcekler kendilerine ulaşmadan yapraklarında savunma salgıları üretmeye başlar."
        ),
        "visual_keywords": ["ancient forest trees", "mushroom mycelium roots", "sunlight through forest", "tree roots soil"],
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
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[UYARI] HISTORY_FILE okunamadı ({HISTORY_FILE}): {exc}", file=sys.stderr)
        return []


def save_recent_title(title: str) -> None:
    history = load_recent_titles()
    if title not in history:
        history.append(title)
    HISTORY_FILE.write_text(
        json.dumps(history[-25:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


PRUNE_STATE_FILE = Path(__file__).parent / "prune_state.json"


def load_channel_live_titles() -> list[str]:
    """prune_state.json içindeki aktif kanal videolarının başlıklarını döndürür (mükerrer yayın kilidi)."""
    if not PRUNE_STATE_FILE.exists():
        return []
    try:
        data = json.loads(PRUNE_STATE_FILE.read_text(encoding="utf-8"))
        videos = data.get("videos", {}) if isinstance(data, dict) else {}
        return [
            str(v.get("title", "")).strip()
            for v in videos.values()
            if isinstance(v, dict) and str(v.get("title", "")).strip()
        ]
    except Exception:
        return []


# --- FAZ 13.4: baslik benzerlik kontrolu (tekrar korumasi uretili) -----------
# Turkce title'larda ekler, baglaclar ve genel kelimeler konu eslesmesini
# sisirmemeli. Noktalama ve turkce karakterler normalize edilir.
_TITLE_STOPWORDS = frozenset(
    "bir daha kadar sonra sadece tarihin gercek gercegi shorts neden nasil oldu "
    "hangi dunyanin uzayda antik yillik milyar olan var yok degil ile icin mi m u"
    .split()
)


def title_tokens(text: str) -> set[str]:
    """Baslik metninden >=4 harfli, stopword olmayan kelime tokenleri cikarir.

    audit_repeat_candidates.py'deki tokens() ile ayni mantik; content_engine
    icinde yerel olarak tanimlandi ki modul bagimliligi olmasin.
    """
    s = str(text or "")
    s = s.replace("I", "ı").replace("İ", "i").lower().replace("ı", "i")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return {w for w in re.findall(r"[a-z]+", s) if len(w) >= 4 and w not in _TITLE_STOPWORDS}


def is_similar_to_recent(title: str, recent_titles: list[str], threshold: float = 0.30) -> bool:
    """Yeni baslik, onceki basliklarla %esik'den fazla benzerse True dondurur.

    Jaccard token overlap kullanilir: |kesisim| / |birlestirme|.
    Ornek: "Gobeklitepe! #Shorts" ve "Piramitlerden 7 Bin Yil Daha Eski Tapinak:
    Gobeklitepe! #Shorts" ortak token = {gobeklitepe}, birlestirme ~ 12, jaccard ~ 0.08
    (farkli baslik, gecmez). Ayni konu, farkli kelimeleme -> dusuk skor, gecmez.
    Ayni baslik tamamiyle ayni -> jaccard = 1.0, engellenir.
    """
    new_tokens = title_tokens(title)
    if not new_tokens:
        return False
    for old in recent_titles:
        old_tokens = title_tokens(old)
        if not old_tokens:
            continue
        common = new_tokens & old_tokens
        union = new_tokens | old_tokens
        jaccard = len(common) / len(union) if union else 0.0
        if jaccard >= threshold:
            return True
    return False


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


# --- FAZ 13.1: aciklama guvenligi (urun iddiasi vs gercek link) ----------------
CHANNEL_INTERNAL_URL_MARKERS = ("youtube.com", "youtu.be", "sub_confirmation")
# Turkce ek toleransi: "teleskobu", "kitabı", "kitipleri", "bilim setini" gibi
# yazimlari da yakalar (basit alt dizgi eslesmesi YETMEZDI).
PRODUCT_CLAIM_PATTERNS = (
    r"\btelesko\w*",
    r"\bkit(?:ab|ap|ip)\w*",
    r"\bbilim\s*set\w*",
    r"\bsat[ıi]n\s*al\b",
    r"\bindir\w*",
    r"\bka[şs]if\w*",
    r"\bk[âa]ğıt\w*",
    r"\b[üu]r[üu]n\w*",
    r"\bhediye\w*",
    r"\bsipari[şs]\w*",
    r"\bkampanya\w*",
    r"\bf[ıi]rsat\w*",
    r"\bal[ıi]şveri[şs]\w*",
    r"\b(?:shop|store)\w*",
    r"\bsaat\w*",
    r"\bkamera\w*",
    r"\btelefon\w*",
    r"\bmikrosko\w*",
)
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
HONEST_SUBSCRIBE_CTA = "Benzer videolar için abone ol"


def is_channel_internal_url(url: str) -> bool:
    """Link gercek bir URUN sayfasi mi, yoksa kanalin kendi abone linki mi?

    FAZ 13.1 denetim bulgusu: "Bu teleskobu incele" metni abone linkine
    baglaninca aciklama yaniltici oluyor. Urun linki yokken urun iddiasi
    uretilmez.
    """
    u = (url or "").strip().lower()
    if not u:
        return True
    return any(marker in u for marker in CHANNEL_INTERNAL_URL_MARKERS)


def sanitize_affiliate_hook(hook: str, affiliate_link: str) -> tuple[str, str]:
    """LLM'in yazdigi ilk satiri guvenli hale getirir.

    - Hook icindeki HER URL gercek affiliate linkiyle degistirilir (uydurma link).
    - Link kanalin kendi abone linkiyse ve metin urun iddiasi iceriyorsa
      durust CTA'ya ("Benzer videolar için abone ol") cevrilir.
    Doner: (temiz_hook, uygulanan_duzeltmeler)
    """
    raw = (hook or "").strip()
    notes: list[str] = []
    if not raw:
        return "", ""
    if affiliate_link:
        for found in URL_RE.findall(raw):
            if found.strip() != affiliate_link.strip():
                notes.append("uydurma_link")
                raw = raw.replace(found, affiliate_link)
    if is_channel_internal_url(affiliate_link):
        low = raw.lower()
        hits = [pat for pat in PRODUCT_CLAIM_PATTERNS if re.search(pat, low)]
        if hits:
            notes.append("urun_iddiasi")
            raw = f"{HONEST_SUBSCRIBE_CTA}: {affiliate_link}"
    return raw.strip(), ",".join(sorted(set(notes)))


# --- FAZ 13.2: kaynak satiri (her aciklamada en az bir dogrulanabilir kaynak) ---
def build_source_line(explicit_source: str = "", topic: str = "", title: str = "") -> str:
    """Aciklamaya eklenecek 'Kaynak: <kurum> — <URL>' satiri."""
    src_text = (explicit_source or "").strip()
    if not src_text:
        src_text = match_source_by_topic(topic, title)
    if not src_text:
        return ""
    return f"Kaynak: {src_text}"


def resolve_affiliate_offer(topic: str, title: str, script_text: str = "") -> tuple[str, str]:
    """
    Faz 9 Monetizasyon Tuzağı: Videonun konusuna göre tıklanma oranı yüksek
    affiliate linkini ve açıklamanın en üstüne yerleşecek harekete geçirici metni (CTA) üretir.
    """
    niche = classify_content_niche(topic, title, script_text)
    default_url = os.environ.get("AFFILIATE_URL_DEFAULT", "").strip() or DEFAULT_AFFILIATE_FALLBACK_URL

    if niche == "Uzay":
        url = os.environ.get("AFFILIATE_URL_SPACE", "").strip() or default_url
        product_label = "Bu teleskobu incele"
    elif niche == "Tarih":
        url = os.environ.get("AFFILIATE_URL_HISTORY", "").strip() or default_url
        product_label = "Bu kitabı oku"
    else:
        url = os.environ.get("AFFILIATE_URL_SCIENCE", "").strip() or default_url
        product_label = "Bu bilim setini incele"

    # FAZ 13.1: link kanalin kendi abone linkiyse URUN IDDIASI uretilmez.
    if is_channel_internal_url(url):
        return url, f"{HONEST_SUBSCRIBE_CTA}: {url}"
    # Gercek urun/affiliate linki varsa urun metni + acik affiliate beyani.
    return url, f"{product_label}: {url} (Bu bir affiliate bağlantısıdır.)"


def load_analytics_feedback(feedback_path: Path = ANALYTICS_FEEDBACK_FILE) -> dict[str, Any]:
    """Faz 9 Analitik Geri Bildirim Döngüsü: analytics_scraper.js tarafından üretilen veriyi okur."""
    if not feedback_path.exists():
        return {}
    try:
        data = json.loads(feedback_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[UYARI] analytics_feedback.json okunamadı: {exc}", file=sys.stderr)
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
    except (requests.RequestException, ValueError, KeyError) as exc:
        print(f"[UYARI] Wikipedia grounding başarısız: {exc}", file=sys.stderr)
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

    # --- FAZ 12: SİLAHLANDIRILMIŞ PROMPT (algoritma manipülasyon motoru) ---
    system_prompt = (
        "Sen YouTube algoritmasını hackleyen, milyonlarca izlenen Türkçe Shorts kanallarının "
        "acımasız baş stratejistsin. "
        "Amacın: İzleyiciyi ilk 3 saniyede dondurmak (scroll stop), 40 saniye boyunca ekrana "
        "çivilemek (retention) ve video biter bitmez yorum yapmaya veya linke tıklamaya ZORLAMAK "
        "(engagement).\n\n"
        "KESİN VE TARTIŞILMAZ KURALLAR:\n"
        "1. HOOK: Asla 'Merhaba', 'Biliyor muydunuz' deme. Doğrudan beyni sarsan, absürt veya "
        "şok edici bir iddia/soru ile başla.\n"
        "2. UZUNLUK: `script_text` TAM OLARAK 60-80 kelime olmalı. (35-45 saniye). Daha kısa ise "
        "reddedilir.\n"
        "3. CTA (Call to Action): Metnin son cümlesi, izleyiciyi kışkırtarak yorum yapmaya zorlamalı. "
        "(Örn: 'Sence bu bir tesadüf mü yoksa planlı mı? Yorumlara yaz, tartışalım!')\n"
        "4. THUMBNAIL PROMPT: Bu videonun kapağı olacak. İngilizce yaz. MUTLAKA şunları içermeli: "
        "'YouTube Shorts thumbnail, vertical 9:16, hyper-dramatic lighting, high contrast, vibrant "
        "colors, glowing elements, mysterious or shocking focal point, 8k resolution, cinematic, "
        "highly detailed'.\n"
        "5. HASHTAGLAR: Sadece 3 adet, çok spesifik ve o videoya özel hashtag. (#shorts hariç, o "
        "sistemde var; genel etiket de yazma.)\n"
        "6. GÖRSELLER: `visual_keywords` alanında konu nesnesini veya olayı içeren, her biri "
        "2-3 İngilizce kelimelik 4 spesifik sahne araması üret. Örnek: 'rabbits running forest', "
        "'napoleon historical portrait'. Tek kelime, genel atmosfer veya ilgisiz stok terimi kullanma. "
        "Arama terimi görsel uyumu garanti etmez; yayın öncesi görüntüyü kontrol et.\n"
        "7. DİL: Çok doğal, akıcı ve vurucu bir belgesel Türkçesi. Emoji, hashtag, markdown veya "
        "sahne notu YAZMA.\n"
        "8. SADECE GEÇERLİ, BOZUK OLMAYAN BİR JSON NESNESİ DÖNDÜR."
    )

    user_prompt = (
        f"Konsept: {concept}.\n"
        f"{avoid_clause}\n"
        f"{feedback_clause}"
        f"{fact_block}\n"
        "Lütfen tam olarak aşağıdaki JSON şemasında üretim yap:\n"
        "{\n"
        '  "topic": "Tarih / Bilim / İlginç Bilgiler",\n'
        '  "title": "Şok edici, 60 karakteri geçmeyen, merak uyandıran başlık #Shorts",\n'
        '  "description": "Kısa, merak uyandıran Türkçe açıklama gövdesi",\n'
        '  "hook": "İlk 3 saniyede izleyiciyi donduran soru/iddia",\n'
        '  "script_text": "Hook ile başlayan, 60-80 kelimelik, tempolu metin",\n'
        '  "cta_line": "İzleyiciyi yorum yapmaya ZORLAYAN kışkırtıcı son cümle",\n'
        '  "thumbnail_prompt": "İngilizce, yukarıdaki kurallara uygun, yüksek tıklama oranlı (CTR) '
        'kapak görseli promptu",\n'
        '  "viral_hashtags": ["#spesifikkonu1", "#spesifikkonu2", "#spesifikkonu3"],\n'
        '  "affiliate_hook": "Açıklamanın en üstüne gelecek, tıklamaya zorlayan 1 satırlık link '
        'çağrısı (Örn: 🔗 Bu deney setini incele: [LINK])",\n'
        '  "visual_keywords": ["english keyword 1", "english keyword 2", "english keyword 3", '
        '"english keyword 4"]\n'
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
    """Faz 11 + FAZ 13.3: Kapak icin INGILIZCE, dikey, yuksek kontrastli prompt.
    FAZ 13.3: konu nesnesi cerceveyi doldurur; metin/son karti olmaz."""
    keywords = [str(k).strip() for k in (visual_keywords or []) if str(k).strip()]
    subject = ", ".join(keywords[:2]) if keywords else "dramatic cinematic historical scene"
    niche = str(topic or "documentary").lower()
    return (
        f"Cinematic vertical 9:16 shot of {subject}, hyper-realistic, dramatic lighting, "
        f"high contrast, vivid saturated colors, ultra detailed, 8k, {niche} documentary style, "
        f"the single main subject fills the frame, large, bright and instantly recognizable, "
        f"no text, no watermark, no logo, no end card, no split screen"
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

    if word_count < 45 or word_count > 110:
        raise ValueError(
            f"{provider_name} hedef kelime aralığı (45-110) dışında metin üretti ({word_count} kelime)."
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

    # --- FAZ 12: affiliate_hook (LLM'in yazdigi tiklama zorlayan ilk satir) ---
    affiliate_hook = str(raw_data.get("affiliate_hook", "") or "").strip()
    trust_notes: list[str] = []
    if affiliate_hook:
        # "[LINK]" placeholder'ini gercek affiliate linki ile degistir
        affiliate_hook = affiliate_hook.replace("[LINK]", affiliate_link).replace("[link]", affiliate_link)
        if affiliate_link and affiliate_link not in affiliate_hook:
            affiliate_hook = f"{affiliate_hook} {affiliate_link}".strip()
        # FAZ 13.1: urun iddialari + uydurma linkler temizlenir
        affiliate_hook, hook_notes = sanitize_affiliate_hook(affiliate_hook, affiliate_link)
        if hook_notes:
            trust_notes.append(f"cta:{hook_notes}")
            print(f"[GUVENLIK] CTA guvenlik duzeltmesi uygulandi ({hook_notes})")
        affiliate_hook = affiliate_hook[:300].strip()
    else:
        affiliate_hook = ""

    # SIRA: [1] Affiliate hook (Faz 12) -> [2] Affiliate CTA+link (Faz 9) -> [3] Viral CTA
    #        -> [4] Govde -> [5] Tam 3 hashtag
    # Tekrari onlemek icin: hook linki iceriyorsa ayri affiliate CTA satiri eklenmez.
    if affiliate_hook:
        aff_block = affiliate_hook
    elif affiliate_cta:
        aff_block = affiliate_cta
    else:
        aff_block = ""

    # --- FAZ 13.2: kaynak satiri (dogrulanabilir, aciklamada gorunur) ---
    source_line = build_source_line(
        str(raw_data.get("source", "") or ""), topic_val, title
    )
    if source_line:
        print(f"[KAYNAK] Kaynak satiri eklendi: {source_line}")
    else:
        trust_notes.append("kaynak_yok")
        print("[GUVENLIK] UYARI: kaynak satiri bulunamadi (aciklama kaynagsiz kalabilir)")

    # SIRA: [1] Affiliate/abone hook -> [2] Etkileşim CTA -> [3] Govde
    #       -> [4] Kaynak -> [5] Tam 3 hashtag
    blocks = [aff_block, cta_line, base_desc, source_line, " ".join(viral_hashtags)]
    enriched_desc = "\n\n".join([b for b in blocks if b]).strip()

    return {
        "provider": provider_name,
        "topic": topic_val,
        "title": title[:100],
        "description": enriched_desc,
        "affiliate_link": affiliate_link,
        "affiliate_cta": affiliate_cta,
        "affiliate_hook": affiliate_hook,
        "source_line": source_line,
        "trust_notes": trust_notes,
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
    """Text model: only free-tier project use; key stays in a header, never the URL."""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent"
    resp = requests.post(
        url,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        allow_redirects=False,
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
    parts = candidates[0]["content"]["parts"]
    content = "".join(p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought"))
    return validate_and_normalize_scenario(extract_json_object(content), "gemini:gemini-2.0-flash-lite")


def validate_fallback_scenario(raw_data: dict[str, Any], provider_name: str) -> dict[str, Any]:
    """Yerel yedek metinleri 45 kelimelik alt sınıra tamamlar; LLM doğrulamasını gevşetmez."""
    candidate = dict(raw_data)
    script_text = sanitize_for_tts(str(candidate.get("script_text", "")))
    additions = (
        "Bu olayın ayrıntıları, dönemin koşullarıyla birlikte değerlendirildiğinde daha anlamlı hale geliyor.",
        "Kaynaklarda aktarılan bilgiler, bu hikâyenin neden bugün bile ilgi çektiğini anlamamıza yardımcı oluyor.",
        "Bazen küçük bir ayrıntı, geçmişte yaşanan büyük bir olayın bütününü daha iyi açıklıyor.",
    )
    for sentence in additions:
        if len(script_text.split()) >= 45:
            break
        script_text = f"{script_text.rstrip()} {sentence}".strip()
    candidate["script_text"] = script_text
    return validate_and_normalize_scenario(candidate, provider_name)


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

        # History + Canlı Kanal Envanteri filtresi: hem .used_topics.json hem prune_state.json içindeki
        # aktif kanal videoları havuzdan çıkarılır (aynı videonun 2-4 kez yüklenmesini engeller).
        live_channel_titles = load_channel_live_titles()
        combined_recent = list(dict.fromkeys(list(recent_titles) + live_channel_titles))
        filtered_pool = [
            item for item in pool
            if item["title"] not in combined_recent
            and not is_similar_to_recent(item["title"], combined_recent)
        ]
        if len(filtered_pool) < 10:
            # Yedek: yalnızca son 25 (.used_topics.json) ile filtrele
            filtered_pool = [
                item for item in pool
                if item["title"] not in recent_titles
                and not is_similar_to_recent(item["title"], recent_titles)
            ]
        if len(filtered_pool) >= 10:
            pool = filtered_pool
            print(f"[INFO] History filtresi: {len(FALLBACK_SCENARIOS) - len(pool)} senaryo atlandi, "
                  f"{len(pool)} senaryo kaldi.")
        else:
            print(f"[INFO] History filtresi: tum senaryolar kullanilmis, havuz sifirlaniyor.")

        # Analitik boost aktifse 5 zaman diliminin 4'ünde (%80) kazanan niş havuzuna öncelik ver
        if boost_active and winning_topic and (slot_15m % 5 != 4):
            winners = [
                item for item in pool
                if classify_content_niche(item["topic"], item["title"], item["script_text"]) == winning_topic
            ]
            if winners:
                w_step = _coprime_step(len(winners))
                w_slot = (slot_15m * w_step + (int(effective_ch) - 1) * w_step) % len(winners)
                return validate_fallback_scenario(
                    winners[w_slot], f"local-fallback-analytics-boost-{winning_topic.lower()}-{effective_ch}"
                )

        step = _coprime_step(len(pool))
        slot = (slot_15m * step + (int(effective_ch) - 1) * step) % len(pool)
        return validate_fallback_scenario(pool[slot], f"local-fallback-matrix-{effective_ch}")

    unused = [item for item in pool if item["title"] not in recent_titles]
    chosen = random.choice(unused if unused else pool)
    return validate_fallback_scenario(chosen, "local-fallback-pool")


def _coprime_step(size: int) -> int:
    """Havuz boyutuyla aralarinda asal adim dondurur.

    Neden: (slot * CARPAN) % len(pool) formulu, CARPAN ile len(pool) aralarinda
    asal degilse sabit sonuc verir (orn. len=3, CARPAN=3 -> hep 0) ve ayni konu
    arka arkaya secilir. gcd(step, size)==1 olan adim, slot ilerledikce konuyu
    dondurerek (round-robin) farkli konulara dagitir.
    """
    if size <= 1:
        return 1
    step = 1
    while math.gcd(step, size) != 1:
        step += 1
    return step


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
                print("[LLM] İkincil sağlayıcı deneniyor: Google Gemini API (gemini-2.0-flash-lite)...")
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
    except (subprocess.SubprocessError, ValueError) as exc:
        print(f"[UYARI] Ses süresi okunamadı: {exc}", file=sys.stderr)
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

    async def consume_stream() -> None:
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

    # Akış hiç ilerlemezse TTS fazını sınırsız bekletme.
    await asyncio.wait_for(consume_stream(), timeout=90)

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

    try:
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
            timeout=120,
        )
    finally:
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
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                word_timestamps = loop.run_until_complete(_edge_tts_generate(text, voice, rate, audio_out))
            else:
                word_timestamps = asyncio.run(_edge_tts_generate(text, voice, rate, audio_out))
        except ImportError:
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
    try:
        from dotenv import load_dotenv
        load_dotenv(override=False)
    except ImportError:
        pass  # python-dotenv kurulu değilse env değişkenleri zaten yüklenmiş sayılır
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
