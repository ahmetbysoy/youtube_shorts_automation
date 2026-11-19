# GitHub / API Erişim Rehberi (KİŞİSEL NOT — her turn'da oku!)

> **ÖZET:** GitHub erişimi zaten kurulu. Tekrar kurmaya çalışma, token'ı doğrudan
> log'a basma, "erişim yok" diye varsayma. Bu dosyadaki adımları uygula, yeter.

## 1. Repo yolu

```
REPO_DIR=/home/user/youtube_shorts_automation
cd $REPO_DIR
```

Repo zaten klonlu. Remote `origin` zaten tanımlı:
- `https://github.com/ahmetbysoy/youtube_shorts_automation.git` (owner: `ahmetbysoy`, branch: `main`)

Jeton dosyaları repo İÇİNDEKİ `jeton/` klasöründedir (`/home/user/jeton` YOK, `$REPO_DIR/jeton/` var).

## 2. Git push / fetch / pull için

**Credential helper repo-yerel olarak zaten ayarlı** (`git config --local credential.helper`).
Eğer bir nedenden sıfırlanmışsa (yeni sandbox), şu komutla geri kur:

```bash
cd $REPO_DIR
git remote set-url origin https://github.com/ahmetbysoy/youtube_shorts_automation.git
git config --local credential.helper "$PWD/jeton/git-credential-jeton.sh"
git config --local user.email "agent@arena.ai"
git config --local user.name "Agent"
```

Bundan sonra normal `git pull`, `git push`, `git fetch` çalışır; PAT hiçbir yerde
açıkça görünmez (credential helper `jeton/github_erisim.json` dosyasından okur).

## 3. GitHub REST API çağrıları için

Token'ı dosyadan çek (asla doğrudan değişkene kopyala-yapıştır YAPMA):

```bash
GITHUB_TOKEN=$(grep -E '^GITHUB_TOKEN=' $REPO_DIR/jeton/github_erisim.json | cut -d= -f2- | tr -d '\r\n ')
```

Sonra `curl -H "Authorization: token $GITHUB_TOKEN" ...` kullan.
Token'ı log'larda/çıktıda tam olarak BASMA (güvenlik).

Workflow ID'leri (aktif):
- Faz4G E2E (no-upload): `423874486`
- Faz4E storyboard/cookie probe: `423098062`
- stock-cookie-probe: `422967679` (şu anda YAML bug'ı yüzünden bozuk)
- Phase4C media probe: `422456438` (şu anda YAML bug'ı yüzünden bozuk)

Dispatch örneği:
```bash
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/ahmetbysoy/youtube_shorts_automation/actions/workflows/423874486/dispatches" \
  -d '{"ref":"main"}' -w "HTTP %{http_code}\n"
# Başarı: HTTP 204
```

## 4. Rebase sırasında .used_topics.conflict

CI run'ları `.used_topics.json` dosyasını günceller; push öncesi sık sık
`git fetch origin && git rebase origin/main` gerekir. Çakışma olursa:

```bash
git checkout --theirs .used_topics.json
git add .used_topics.json
GIT_EDITOR=true git rebase --continue
```

## 5. Diğer jetonlar

| Servis | Dosya | Format |
|---|---|---|
| GitHub PAT | `jeton/github_erisim.json` | `GITHUB_TOKEN=ghp_...` |
| Gemini API | `jeton/gemini_erisim.json` | `GEMINI_API_KEY=...` |
| Gemini cookie | `jeton/gemini_cookies.json` | JSON (Playwright state) |
| HuggingFace | `jeton/huggingface_erisim.json` | `HF_TOKEN=hf_...` |

## 6. Workflow / CI takip püf noktaları

- Dispatch'ten sonra 5-10 sn bekle, sonra `.../actions/runs?per_page=5` ile en yeni
  `in_progress` run'ı bul (`workflow_runs[0].id` her zaman en yeni değil, adıyla filtrele).
- Faz4G yaklaşık 2.5-3 dk sürer.
- Log indirmek için job ID lazım: `/runs/{run_id}/jobs` → `jobs[0].id`
  (eğer fazladan job'lar varsa `build-no-upload` içeren ismi seç), sonra
  `/jobs/{job_id}/logs` (zip'lenmemiş düz metin, Accept başlığına dikkat).
- Artifact indirmek için: `/actions/artifacts/{artifact_id}/zip`

## 7. YASAKLAR

- ❌ "GitHub erişimi yok / sandbox'ta kurulu değil" diye varsayma — **var**.
- ❌ Token'ı commit'leme, log'da tam basma, komut geçmişine açıkça yazma.
- ❌ Her seferinde `git remote add` yapma (zaten var; kontrol etmeden ekleme).
- ❌ `jeton/` klasörünü `.gitignore` dışında commit'lemeye çalışma (zaten .gitignore'da olmalı, kontrol et).
- ❌ Kullanıcıya "erişim sıkıntısı var" diye uyarı verme — ilk olarak yukarıdaki adımlarla doğrula.

## 8. Eğer push/auth gerçekten bozuksa

Bunu ancak şu kontrolden SONRA söyle:
1. `cd $REPO_DIR && git remote -v` → origin var mı?
2. `ls jeton/github_erisim.json` → dosya var mı?
3. `git config --local credential.helper` → helper path doğru mu?
4. `bash jeton/git-credential-jeton.sh` test et (protocol=https host=github.com ile stdin vererek)

Ancak bunlar başarısızsa kullanıcıya haber ver. Aksi halde sessizce düzelt ve devam et.
