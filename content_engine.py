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
) -> tuple[str, str]:
    avoid_clause = (
        f"Daha önce işlenen şu başlıklardan KESİNLİKLE farklı olmalı: {', '.join(recent_titles[-8:])}."
        if recent_titles
        else ""
    )

    fact_block = ""
    if wiki_fact:
        fact_block = (
            f"\nDOĞRULANMIŞ KAYNAK BİLGİ ({wiki_fact['title']}):\n"
            f'"{wiki_fact["extract"]}"\n'
            "Senaryoyu bu doğrulanmış bilgilere dayandır; kesinlikle uydurma isim veya tarih ekleme.\n"
        )

    system_prompt = (
        "Sen milyonlarca izlenen Türkçe YouTube Shorts belgesel kanallarının baş senaristisin. "
        "Görevin 'İlginç Bilgiler / Tarih / Bilim' konseptinde %100 gerçek, doğrulanabilir ve "
        "izleyiciyi son saniyeye kadar ekranda tutan bir Shorts seslendirme metni yazmaktır.\n\n"
        "KESİN KURALLAR:\n"
        "1. İlk cümle (ilk 3 saniye - Hook): Kaydırmayı anında durduracak merak uyandırıcı bir soru veya çarpıcı gerçek olmalı. "
        "Asla 'Merhaba', 'Bugün sizlere' gibi klasik girişler yapma.\n"
        "2. Uzunluk: `script_text` alanı TAM OLARAK 60 ile 80 Türkçe kelime arasında olmalı (yaklaşık 30-45 saniye).\n"
        "3. Dil ve Diksiyon: Çok doğal, akıcı ve vurucu bir belgesel Türkçesi kullan. Emoji, hashtag, markdown veya "
        "sahne notu YAZMA. Kısaltmaları ('milattan önce' gibi) açık yaz.\n"
        "4. Görsel Arama Kelimeleri: Faz 3'te Pexels/Pixabay dikey stok video aramasında kullanılmak üzere "
        "konuya uygun 4 adet İngilizce sinematik arama terimi (`visual_keywords`) üret.\n"
        "5. Yalnızca geçerli bir JSON nesnesi döndür."
    )

    user_prompt = (
        f"Konsept: {concept}.\n"
        f"{avoid_clause}\n"
        f"{fact_block}\n"
        "Lütfen tam olarak aşağıdaki JSON şemasında üretim yap:\n"
        "{\n"
        '  "topic": "Tarih veya Bilim veya İlginç Bilgiler",\n'
        '  "title": "Merak uyandıran çarpıcı Türkçe YouTube Shorts başlığı #Shorts",\n'
        '  "description": "Kısa Türkçe SEO açıklaması ve 3-4 etiket",\n'
        '  "hook": "Metnin ilk cümlesi olan 3 saniyelik kanca",\n'
        '  "script_text": "Hook cümlesiyle başlayan, toplam 60-80 kelimelik tam seslendirme metni",\n'
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

    return {
        "provider": provider_name,
        "topic": str(raw_data.get("topic", "Tarih")).strip(),
        "title": title[:100],
        "description": str(
            raw_data.get("description", f"{title} #ilginçbilgiler #tarih #bilim #shorts")
        ).strip(),
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


def pick_fallback_scenario(recent_titles: list[str]) -> dict[str, Any]:
    """Yedek Senaryo Havuzu: Paralel matris kanallarında çakışmasız ve deterministik seçim yapar."""
    matrix_ch = os.environ.get("MATRIX_CHANNEL_ID", "").strip()
    if matrix_ch.isdigit():
        day_index = datetime.now(timezone.utc).timetuple().tm_yday
        slot = (day_index * 3 + (int(matrix_ch) - 1)) % len(FALLBACK_SCENARIOS)
        return validate_and_normalize_scenario(FALLBACK_SCENARIOS[slot], f"local-fallback-matrix-{matrix_ch}")
    unused = [item for item in FALLBACK_SCENARIOS if item["title"] not in recent_titles]
    chosen = random.choice(unused if unused else FALLBACK_SCENARIOS)
    return validate_and_normalize_scenario(chosen, "local-fallback-pool")


def generate_scenario(concept: str = "İlginç Bilgiler ve Tarih", force_fallback: bool = False) -> dict[str, Any]:
    """Çok katmanlı hata toleranslı (`try-except`) senaryo üretim yöneticisi."""
    recent_titles = load_recent_titles()

    if force_fallback:
        print("[BİLGİ] '--force-fallback' aktif: Yerel yedek senaryo havuzu kullanılıyor.")
        scenario = pick_fallback_scenario(recent_titles)
        save_recent_title(scenario["title"])
        return scenario

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    gemini_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()

    if groq_key or gemini_key:
        wiki_fact = fetch_wikipedia_grounding(recent_titles)
        if wiki_fact:
            print(f"[KAYNAK] Doğrulanmış Wikipedia referansı alındı: {wiki_fact['title']}")
        system_prompt, user_prompt = build_llm_prompts(concept, recent_titles, wiki_fact=wiki_fact)

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
        scenario = pick_fallback_scenario(recent_titles)
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
    audio_out: Path = DEFAULT_AUDIO_OUT,
    txt_out: Path = DEFAULT_TXT_OUT,
    json_out: Path = DEFAULT_JSON_OUT,
    srt_out: Path = DEFAULT_SRT_OUT,
) -> dict[str, Any]:
    """Uçtan uca senaryo, seslendirme ve altyazı verisi üretim hattı."""
    load_dotenv_file()
    resolved_voice = SUPPORTED_VOICES.get(voice_choice, "tr-TR-AhmetNeural")

    # 1. Senaryo Üretimi
    scenario = generate_scenario(concept=concept, force_fallback=force_fallback)
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
    args = parser.parse_args()

    result = run_content_pipeline(
        concept=args.concept,
        voice_choice=args.voice,
        rate=args.rate,
        force_fallback=args.force_fallback,
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
