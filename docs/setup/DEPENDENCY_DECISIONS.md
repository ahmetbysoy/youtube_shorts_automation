# Bağımlılık kararları — 2026-11-03

## Ortam

- Debian GNU/Linux 13 (trixie), Debian 13.7, x86_64
- Python 3.13.16
- Kurulum yeri: `/home/user/youtube_shorts_automation/.venv`
- Sistem Python ortamına bu projenin paketleri kurulmadı.

## İstenen eski liste neden değiştirildi?

İstenen 17 satırlık liste aynen `requirements.requested.txt` dosyasına kaydedildi ve kurulmaya çalışıldı. Kurulum `Pillow==10.0.0` için kaynak dağıtımını derlerken `KeyError: '__version__'` ile durdu. Tam çıktı `../../setup_reports/01-pip-requested.log` dosyasındadır. Çözüm başarısız olduğu için istenen eski paket kümesi kurulmuş değildir.

Python 3.13 uyumlu doğrudan bağımlılıklar seçildi. Pillow, MoviePy 2.2.1'in `pillow>=9.2.0,<12.0` kısıtıyla uyumlu 11.3.0 sürümünde tutuldu. OpenCV, 4 serisinin kontrol tarihindeki son kararlı sürümü olan 4.14.0.94 olarak seçildi. Ayrıntılı sürüm listesi ve tamamlayıcı bağımlılıklar `../../requirements.lock.txt` içindedir.

`asyncio==3.4.3` kaldırıldı: asyncio Python 3.4'ten beri standart kütüphanededir; PyPI'daki bu eski dağıtım Python 3.3 içindir. [Resmî paket açıklaması](https://pypi.org/project/asyncio/3.4.3/).

MoviePy 2.x kullanılmaktadır. Eski 1.x eğitimlerindeki `moviepy.editor` ve bazı metod adları doğrudan taşınmayacaktır. Sonraki modüller kurulu 2.2.1 API'sine göre yazılmalıdır.

## Araçlar

Başlangıç kontrolünde FFmpeg, ffprobe ve tree PATH üzerinde yoktu. Debian paketlerinden `ffmpeg 7.1.5-0+deb13u1` ve `tree 2.2.1` kuruldu. OpenCV sistemde 4.11.0.86 olarak bulunuyordu; projenin izole ortamında 4.14.0.94 kullanılmaktadır.

## Kapsam ve güvenlik

- Playwright ve Selenium genel amaçlı araçlardır; kota/rate-limit aşmak için kullanılmaz.
- Stok medya sağlayıcısının kotası biterse izinli başka kaynak, önbellek veya yeniden zamanlama kullanılır. Tarayıcı üzerinden kota atlatma yedeği yoktur.
- API anahtarları, OAuth client secret dosyaları ve tokenlar kaynak koduna veya Drive/GitHub yedeğine konmaz.
- Bu aşamada YouTube/Google hesabına bağlanılmadı, video yüklenmedi ve ücretli servis çağrısı yapılmadı.
- Kurulum ve import doğrulaması, harici servislerin kullanılabilirliğini veya hesabınızın API kotasını garanti etmez.
- Bağımlılıkların ayrıca güvenlik açığı taraması bu görevde yapılmadı.

## Paket kaynakları

- https://pypi.org/project/opencv-python/
- https://pypi.org/project/moviepy/2.2.1/
- https://pypi.org/project/Pillow/11.3.0/
- https://pypi.org/project/asyncio/3.4.3/

Kontrol tarihinde PyPI JSON metadata'sından alınan sürümler `../../setup_reports/03-pypi-metadata.json` dosyasındadır.