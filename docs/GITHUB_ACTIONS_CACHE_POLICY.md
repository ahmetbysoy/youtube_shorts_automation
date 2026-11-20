# GitHub Actions Bağımlılık Cache Politikası

**Durum:** Zorunlu repository standardı  
**Kapsam:** Bu depodaki tüm GitHub Actions workflow'ları ve composite action'ları  
**Amaç:** Her çalıştırmada aynı araçları ve bağımlılıkları gereksiz yere yeniden indirmeyi önlemek; doğruluk, güvenlik ve tekrarlanabilirliği korumak.

## 1. Zorunlu kural

Yeni veya değiştirilmiş hiçbir workflow, ortak kurulum altyapısını incelemeden kendi başına tekrar tekrar Python, Node.js, Playwright, Chromium veya APT bağımlılığı kuran paralel bir kurulum sistemi ekleyemez.

Önce `.github/actions/setup-tools/action.yml` kullanılmalıdır. Workflow'un ihtiyaçları bu composite action tarafından karşılanmıyorsa mevcut action geriye uyumlu input/output'larla genişletilmeli; workflow'lar arasında kopya kurulum mantığı oluşturulmamalıdır.

Mevcut workflow'lar değiştirilirken de aynı kural geçerlidir. Kurulum adımları, cache davranışı ve sürüm gereksinimleri kontrol edilmeden workflow tamamlandı kabul edilmez.

## 2. Mevcut ortak cache altyapısı

`.github/actions/setup-tools/action.yml` ortak kurulum noktasıdır. Mevcut uygulama şu cache alanlarını yönetir:

| Alan | Mevcut yöntem | Cache anahtarının temel girdileri |
|---|---|---|
| APT `.deb` arşivleri | `actions/cache@v4`, `~/.apt-debs` | Ubuntu sürümü, mimari, runner image bilgisi ve normalize paket listesi |
| Python/pip | `actions/setup-python@v7`, `cache: pip` | Python kurulumu ve `cache-dependency-path` olarak verilen requirements dosyaları |
| Node `node_modules` | `actions/cache@v4` | OS, Node sürümü, `package-lock.json` / `package.json` hash'i |
| Playwright Chromium | `actions/cache@v4` | OS, Node veya Python Playwright sürüm girdileri |
| Browser doğrulama | Chromium launch smoke test | Cache'ten gelen binary'nin gerçekten açılabildiği doğrulanır |

Workflow'lar mümkün olduğunda bu composite action'ı çağırmalı ve çıktılarındaki cache-hit ile setup süresi bilgilerini Step Summary'ye yazmalıdır.

## 3. Cache anahtarı ve geçersizleştirme

- Cache anahtarı işletim sistemi/mimari, runtime sürümü, bağımlılık kilit dosyaları veya normalize edilmiş paket listesi gibi cache içeriğini etkileyen girdileri kapsamalıdır.
- Python bağımlılıkları için `requirements*.txt`; Node için `package-lock.json` ve `package.json`; Playwright için kurulu Playwright sürümü ve platform anahtarın parçası olmalıdır.
- Kilit dosyası veya runtime sürümü değişince eski cache doğrudan doğru kabul edilmemeli; yeni anahtar oluşturulmalıdır.
- Restore key yalnızca uyumlu, güvenli ve doğrulama sonrasında kullanılabilecek içeriklerde tanımlanmalıdır. APT gibi paket kümesi hassas cache'lerde uyumsuz eski cache'i zorla geri yüklemeyin.
- Cache hit tek başına kurulumun sağlıklı olduğunu kanıtlamaz. Gerekli modül/binary varlığı ve mümkünse gerçek başlatma smoke testi kontrol edilmelidir.
- Cache miss, bozuk cache veya sürüm uyuşmazlığında normal, deterministik kurulum yolu çalışmaya devam etmelidir.

## 4. Güvenlik sınırları

**Aşağıdakiler hiçbir koşulda cache'e, artifact'e veya log'a yazılmaz:**

- GitHub PAT, API key, OAuth token ve diğer secret değerleri
- `.env`, `cookies.json`, `storage_state.json`, browser profilleri ve oturum dosyaları
- Kişisel/hesap verileri veya üretim çıktıları

Cache'e yalnızca yeniden üretilebilir bağımlılık dosyaları ve güvenli paket arşivleri konabilir. Cache anahtarlarına secret veya secret türevi hash eklenmez. Cache içeriği hiçbir zaman kimlik doğrulama veya yetkilendirme mekanizması olarak kullanılmaz.

## 5. Özel bağımlılıklar

- **Python/pip:** pip indirme cache'i ile kurulu sanal ortam aynı şey değildir. Runner'lar temiz geldiğinden kurulum adımı çalışır; pip cache indirme/derleme maliyetini azaltır.
- **Node:** `node_modules` cache'i kilit dosyası hash'iyle bağlanır. Cache miss veya doğrulama hatasında `npm ci` tercih edilir.
- **Playwright/Chromium:** Browser cache'i Playwright sürümü/platformla eşleşmelidir. Cache'ten sonra Chromium launch smoke test'i yapılır. Eksik/uyumsuz binary yeniden indirilir. Sistem kütüphaneleri browser cache'inin parçası değildir; gerektiğinde `install-deps` çalıştırılır.
- **APT:** Ortak action yalnız indirilen `.deb` arşivlerini cache'ler; kurulu işletim sistemi paketlerinin runner'lar arasında kalıcı olduğunu varsaymayın. Cache'ten `dpkg` kurulumu başarısızsa normal APT yolu kullanılmalıdır.
- **FFmpeg/fontlar:** APT paketleri olarak kurulur; mevcut .deb cache stratejisi kullanılabilir. Runner imajında önceden kurulu olma durumu ayrıca kontrol edilebilir.
- **HuggingFace/TTS gibi model dosyaları:** Yalnızca model/sürüm kimliği sabit, lisansı uygun, boyutu makul ve gizli kullanıcı verisi içermeyen cache'ler için ayrı tasarım yapılır. Genel amaçlı workflow cache'ine gelişigüzel eklenmez.

## 6. Yeni workflow için kontrol listesi

1. Workflow'un mevcut kurulum adımlarını ve kullandığı runtime sürümlerini belirle.
2. `setup-tools` input'larıyla aynı ihtiyacın karşılanıp karşılanmadığını kontrol et.
3. Karşılanıyorsa ortak composite action'ı kullan; karşılanmıyorsa action'ı genel ve geriye uyumlu biçimde genişlet.
4. Cache key'in tüm sürüm/lock girdilerini kapsadığını doğrula.
5. Secret, cookie, oturum, üretim çıktısı veya değişken kullanıcı verisinin cache path'ine girmediğini denetle.
6. Cache miss koşusunu ve sonraki cache hit koşusunu ayrı ayrı doğrula.
7. Cache hit'te bağımlılıkların gerçekten kullanılabildiğini smoke test ile doğrula.
8. Step Summary'de cache hit/miss ve kurulum süresini raporla.
9. Test/CI workflow'larında doğrula. Üretim, yayın, silme veya taslak yayınlama workflow'larını sırf cache testi için dispatch etme.
10. Önce/sonra sürelerini gerçek Actions loglarından karşılaştır; ölçülmemiş hızlanmayı iddia etme.

## 7. Korunacak operasyon davranışı

Cache optimizasyonu iş mantığını değiştirmez. Orchestrator, içerik üretimi, TTS, medya seçimi, FFmpeg çıktısı, uploader, görünürlük, PUBLIC yayın, kanal matrisi, concurrency, kota, pruner ve secret aktarım davranışları bu çalışma kapsamında değiştirilmez.

Cache altyapısı geçici hızlandırma katmanıdır. Cache silinse, expire olsa veya erişilemese bile workflow doğru bağımlılıkları yeniden kurarak çalışabilmelidir.

## 8. Değişiklik ve kabul kuralı

Cache ile ilgili her değişiklikte:
- Değiştirilen workflow/action ve cache path/key listesi belgelenir.
- Cache'e giren dosyaların güvenlik incelemesi yapılır.
- YAML/actionlint ve ilgili testler çalıştırılır.
- En az bir cache miss ve bir cache hit koşusu doğrulanmadan optimizasyon tamamlandı denmez.
- YouTube yükleme başarısı veya üretim başarısı cache/CI testinden çıkarılamaz.

Bu belge, sonraki tüm ajanlar ve geliştiriciler için bağlayıcıdır. Çelişki halinde secret güvenliği ve mevcut üretim davranışını koruma kuralları önceliklidir.

## 9. Başlangıç workflow denetimi (2026-11-20)

İncelenen workflow'larda bağımlılık kurulumu gerekenler mevcut ortak action'ı çağırıyor:

- `.github/workflows/daily_shorts.yml`
- `.github/workflows/ubuntu_26_test.yml`
- `.github/workflows/public_providers_probe.yml`
- `.github/workflows/stock_cookie_probe.yml`
- `.github/workflows/phase4_media_probe.yml`
- `.github/workflows/hourly_pruner.yml`

`.github/workflows/cron_probe.yml` yalnızca runner imajındaki hazır `curl` ve `python3` komutlarını kullanır; bağımlılık indirme/kurma adımı olmadığı için cache eklenmesi gerekmez.

Bu liste, README ve AI handoff belgelerinde atıf yapılan ve doğrudan okunabilen workflow dosyalarının denetimidir. GitHub bağlantısında workflow dizinini listeleyen bir uç nokta bulunmadığından, depodaki atıf yapılmayan tüm workflow dosyalarının eksiksiz envanteri bu işlemde bağımsız olarak doğrulanamadı. Yeni ajan, workflow dizinini yerel checkout veya GitHub Contents API üzerinden listeleyerek bu envanteri tamamlamalıdır; eksiksiz denetim yapılmış gibi davranmamalıdır.

Ayrıca `ubuntu_26_test.yml` artık ortak composite action dosyası değiştiğinde de tetiklenecek şekilde izlenmelidir. Bu, cache altyapısındaki gelecekteki değişikliklerin test dışı kalmasını önler.
