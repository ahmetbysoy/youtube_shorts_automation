# YouTube Shorts Automation — proje temeli

Python 3.13 için hazırlanmış, henüz harici servislere bağlanmayan modüler proje iskeleti.

## Bu aşamada ne var?

- `config/`: ortam değişkenlerine dayalı ayarlar ve video sabitleri.
- `src/content_generation/`: sonraki aşamada senaryo, ses ve içerik üretimi.
- `src/youtube_upload/`: sonraki aşamada OAuth ve private yükleme.
- `src/media_processing/`: sonraki aşamada FFmpeg, kadraj ve altyazı.
- `src/utils/`: sonraki aşamada günlük, durum kaydı ve yedekleme.
- `tests/`: yapılandırma, dizinler, paket importları, FFmpeg ve Chromium smoke testleri.
- `main.py --check`: API çağrısı yapmadan yerel paketleri ve araçları kontrol eder.
- `requirements.txt`: Python 3.13 için seçilmiş doğrudan bağımlılıklar.
- `requirements.lock.txt`: doğrulanan ortamın tüm paket sürümleri.
- `docs/setup/INSTALLATION_REPORT.md`: istenen komutların tam çıktıları ve ilk kurulum hataları.

**Henüz video üretim hattı, OAuth akışı, YouTube yüklemesi, GitHub Actions işi veya otomatik public yayınlama uygulanmadı.** Harici servislerin çalışırlığı bu kurulumla garanti edilmez.

## Yeniden kurulum — Debian 13 / Python 3.13

Sistem araçları için yönetici yetkisi gerekir:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg tree
```

Proje dizininde:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
playwright install chromium
# Gerekli sistem kütüphaneleri eksikse, yönetici yetkisiyle:
sudo "$(pwd)/.venv/bin/python" -m playwright install-deps chromium
```

Aynı transitif sürümleri kurmak istersen ilk kurulumda `requirements.txt` yerine `requirements.lock.txt` kullan. Lock dosyası Linux/x86_64 ve Python 3.13 ortamında üretilmiştir; başka platformlarda yeniden çözümlenmelidir.

## Doğrulama

```bash
source .venv/bin/activate
python -m pip check
python -m unittest discover -s tests -v
python main.py --check --json setup_reports/environment.json
ffmpeg -version
```

Tarayıcı testi yalnızca yerel bir HTML sayfası açar; harici HTTP/HTTPS isteklerini engeller. FFmpeg testi geçici bir H.264/AAC videosu üretir ve siler. `main.py --check` tarayıcı başlatmaz; tarayıcı çalışırlığı unittest içindedir.

## Gizli bilgiler

`.env.example` yalnızca örnektir. Gerçek anahtarlar `.env` içinde veya çalışma ortamının secret store'unda tutulmalıdır. `.env`, `secrets/`, client secret ve token dosyaları `.gitignore` kapsamındadır. Bunları Drive veya GitHub yedeğine ekleme. OAuth ve public yayınlama ayrı kullanıcı onayı gerektirir.

## Kullanım sınırları

API kotası aşılınca bekleme/ertesi güne kuyruklama veya sağlayıcının izin verdiği alternatif kullanılır. Tarayıcı otomasyonu kota atlatmak için kullanılmaz. Yalnızca kullanım hakkına sahip olunan medya işlenir.

## Sonraki iş

Google Cloud projesi, YouTube Data API v3 ve OAuth istemcisini **kullanıcının kendi hesabında** yapılandırmak. Bu kurulum görevi sırasında hiçbir Google Cloud kaynağı oluşturulmadı.