# Mimari sınırlar ve sonraki aşamalar

Bu dosya kurulu özellik listesi değil, sonraki uygulama için taslaktır. Şu an yalnızca proje iskeleti ve yerel doğrulama vardır.

## İçerik

1. İzinli bir LLM sağlayıcısı veya yerel modelle senaryo.
2. Kullanım koşulları uygun bir TTS sağlayıcısıyla ses.
3. Lisansı doğrulanmış stok medya veya kullanıcının kendi medyaları.
4. FFmpeg / MoviePy 2.2.1 ile 1080×1920 çıktı ve altyazı.

Stok API kotası dolarsa tarayıcıyla kota atlatılmaz. Önbellek, izinli alternatif sağlayıcı veya yeniden zamanlama kullanılır. Sağlayıcı anahtarları ayrı hesaplara bölerek limit aşılmaz.

## YouTube

- OAuth 2.0, kullanıcının açık yetkilendirmesiyle.
- Yükleme isteğinde `status.privacyStatus=private` açıkça gönderilir; Google'ın güncel belgesine göre bu alan verilmezse varsayılan public olabilir.
- Public'e geçiş ayrı onay adımıdır.
- İşlem kimlikleri ve durum SQLite'ta tutulacak; aynı işin tekrar yüklenmesi engellenecek.
- Kota hatasında üstel bekleme ve ertesi güne kuyruk; kota aşma yedeği yok.

## Güncel kota notu — 2026-11-03

Google'ın kontrol edilen güncel `videos.insert` belgesi, varsayılan Video Uploads kotasını günde 100 çağrı ve çağrı başına 1 birim olarak veriyor. Eski `1.600 birim / 10.000 ortak birim` hesabı bu belgeye göre güncel değil. Kendi projenin gerçek kotası Cloud Console'dan doğrulanmalıdır; varsayılanlar değişebilir.

Kaynaklar: [1](https://developers.google.com/youtube/v3/docs/videos/insert), [YouTube Data API genel belgesi](https://developers.google.com/youtube/data/getting-started#quota).

## Otomasyon ve yedek

GitHub Actions ve systemd birbirinin yerine geçebilecek çalıştırma ortamlarıdır; ikisinin aynı anda aynı işi yapmasını engelleyen iş kilidi/kimliği gerekir. Actions üzerinde çalışacak uzun video işlerinin süresi ve depolama ihtiyacı ayrıca ölçülmalıdır.

Drive yedeği kod ve dokümantasyon içindir; OAuth sırları ve tokenlar yedeklenmez. Üretilen medya yedeği ayrıca kota, maliyet ve kullanıcı onayıyla tasarlanmalıdır.

## Henüz uygulanmayanlar

SQLite şeması, gerçek iş kuyruğu, API istemcileri, OAuth, Telegram/e-posta bildirimi, video üretimi, Drive senkronizasyonu, GitHub Actions ve systemd zamanlayıcıları.