# Faz 3 — Yerel doğrulama kanıtı (2026-11-18)

## Sınır

Bu not yalnızca çalışma ağacındaki kod, sandbox HTTP kontrolü ve yerel testler içindir. **GitHub Actions CI veya Actions koşuları arası kalıcılık kanıtı değildir.** Kod henüz commit/push edilmedi. `daily_shorts.yml`, `hourly_pruner.yml`, `draft_publisher.yml` ve YouTube yayın hattı tetiklenmedi.

## Kurulum ve yerel testler

- `python -m pip install -r requirements.txt -r requirements-test.txt` — başarılı; repository Python bağımlılıkları kuruldu.
- `npm install` — başarılı; 15 paket denetlendi, 0 güvenlik açığı raporlandı; lock dosyası değişmedi.
- Sistem araçları kuruldu: FFmpeg, Xvfb, Montserrat/Liberation/DejaVu fontları ve libass.
- `python -m playwright install --with-deps chromium` — Chromium, headless shell, Playwright FFmpeg ve browser system dependencies başarıyla kuruldu.
- Python Playwright headless Chromium smoke check, `ffmpeg -version`, fontconfig ve `xvfb-run` kontrolleri başarılı.
- `python -m pytest -q tests` — **165 passed, 16 subtests passed**, 1 mevcut asyncio event-loop DeprecationWarning.
- `npm test` — **7 passed**.
- `npm run test:syntax` — başarılı.
- `git diff --check` — başarılı.

Faz 3 focused suite: `python -m pytest -q tests/test_phase3_fact_checks.py tests/test_topic_history.py tests/test_gemini_web_story.py tests/test_script_json_schema.py` — **35 passed**. Geniş alt küme (fallback + Faz 3) — **40 passed**. HTTP/Contents API birim testleri mock'tur.

Kapsam: exact quote, semantik ilişki var/yok, sayı/tarih/birim uyuşmazlığı, source erişim/boş/bozuk/yanlış canonical URL, farklı başlıkla aynı konu, farklı sözlerle aynı claim, eşzamanlı rezervasyon, Contents API SHA çatışması, fail-closed geçmiş okuma ve başarısız koşu rezervasyonunu bırakma. Mock testler canlı HTTP/Actions proof diye sunulmaz.

## Ayrı gerçek HTTP kanıtı

`fetch_topic_research("Venus")` bir gerçek sandbox HTTP isteğiyle başarıyla tamamlandı: Wikipedia REST summary ve kanonik makale isteği `HTTP 200` döndürdü; final URL, canonical link, makale başlığı ve `content_matches_page=true` eşleşti. Credential/secret kullanılmadı. Bu yalnız kaynak erişim/kimlik doğrulamasıdır; Gemini model üretim testi değildir.

Ayrı bir canlı HTTP + önceden kaydedilmiş fixture denemesinde fixture'ın exact evidence quote'u güncel Wikipedia summary'sinde bulunmadı; validator doğru olarak `quote_not_found` ile reddetti. Eski Gemini Web başarılı run'ı **44262444017** korunur ve yeni Faz 3 code path'e canlı kanıt sayılmaz.

## Kalan kabul kapısı

1. Push sonrası `.github/workflows/ubuntu_26_test.yml` success.
2. `.github/workflows/topic_history_persistence_probe.yml` için iki ayrı Actions run: önce `reserve`, sonra aynı `probe_id` ile `verify`; ikinci koşu ilk koşunun pending reservation'ını görüp güvenli biçimde release etmeli.

Her iki Actions kanıtı bağlanana kadar Faz 3 **kabul edilmedi**.
