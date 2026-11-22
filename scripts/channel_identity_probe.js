/**
 * KANAL-2 TEL CEKME ONCESI GERCEK HESAP KIMLIK PROBU
 * ==================================================
 * Verilen oturum dosyasi (storage_state.json veya cookies.json) ile
 * studio.youtube.com acar; oturumun hangi YouTube KANALINA (UC...) ait
 * oldugunu cozer. channel_map.sh'in cookie-hash dedup'i ayni hesabin
 * farkli oturumlarini "ayri hesap" sanabilir (farkli hash) — bu probe
 * gercek kanal kimligiyle o hatayi kapatir.
 *
 * Cikti: yalnizca PUBLIC bilgiler (kanal ID, aday UC listesi, uzunluklar).
 * Cookie degerleri ASLA loglanmaz/yazilmaz.
 *
 * Kullanim:
 *   node scripts/channel_identity_probe.js --storage /tmp/identity/storage_1.json \
 *        --label ana --json-out /tmp/identity/ids_ana.json
 */

const fs = require('fs');
const { chromium } = require('playwright');

function argValue(flag) {
  const i = process.argv.indexOf(flag);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : '';
}

const STORAGE = argValue('--storage');
const LABEL = argValue('--label') || 'oturum';
const JSON_OUT = argValue('--json-out') || '';

const UC_RE = /UC[A-Za-z0-9_-]{22}/g;

function offlineCandidates(file) {
  try {
    const text = fs.readFileSync(file, 'utf8');
    const uniq = [...new Set(text.match(UC_RE) || [])];
    return uniq.slice(0, 8);
  } catch (_) {
    return [];
  }
}

function buildStorageState() {
  const raw = fs.readFileSync(STORAGE, 'utf8');
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    throw new Error(`oturum dosyasi JSON degil (${raw.length} char)`);
  }
  if (Array.isArray(parsed)) return { cookies: parsed, origins: [] };
  if (parsed && Array.isArray(parsed.cookies)) return parsed;
  throw new Error('oturum dosyasinda cookies dizisi yok');
}

(async () => {
  const result = { label: LABEL, channel_id: '', candidates: [], method: '', byte: 0, diag: {} };
  const candidates = offlineCandidates(STORAGE);
  result.candidates = candidates;
  result.byte = fs.existsSync(STORAGE) ? fs.statSync(STORAGE).size : 0;
  console.log(`[${LABEL}] offline adaylar: ${candidates.length ? candidates.join(',') : 'yok'} (${result.byte} byte)`);

  const storageState = buildStorageState();
  const browser = await chromium.launch({
    headless: true,
    // studio_draft_publish.cjs kanitli konfigurasyonu: UA olmadan Google
    // HeadlessChrome'u bot sayip oturumu acmiyor.
    args: ['--disable-blink-features=AutomationControlled', '--no-first-run', '--lang=tr-TR', '--no-sandbox'],
  });
  const allUC = new Set();
  try {
    const ctx = await browser.newContext({
      viewport: { width: 1366, height: 900 },
      locale: 'tr-TR',
      timezoneId: 'Europe/Istanbul',
      userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
      storageState,
    });
    const page = await ctx.newPage();

    // 0) www.youtube.com isinma + ytcfg kimlik (kendi kanalinin en guvenilir kaynagi)
    try {
      await page.goto('https://www.youtube.com/', {
        waitUntil: 'domcontentloaded',
        timeout: 45000,
      });
      const ytId = await page.evaluate(() => {
        try {
          if (window.ytcfg && typeof window.ytcfg.get === 'function') {
            return window.ytcfg.get('CHANNEL_ID') || '';
          }
        } catch (e) { /* yut */ }
        return '';
      });
      result.diag['youtube_ytcfg'] = ytId || 'bos';
      if (ytId && /^UC[A-Za-z0-9_-]{22}$/.test(ytId)) allUC.add(ytId);
    } catch (e) {
      result.diag['youtube_ytcfg'] = `hata: ${String(e).slice(0, 80)}`;
    }

    // 1) Studio ac -> /channel/UC... redirect'i bekle
    try {
      await page.goto('https://studio.youtube.com/', {
        waitUntil: 'domcontentloaded',
        timeout: 45000,
      });
      await page.waitForURL(/channel\/(UC[A-Za-z0-9_-]{22})/, { timeout: 30000 }).catch(() => {});
      result.diag['studio_final_url'] = page.url().slice(0, 120);
      const m = page.url().match(/UC[A-Za-z0-9_-]{22}/);
      if (m) {
        result.channel_id = m[0];
        result.method = 'studio-redirect';
      }
    } catch (e) {
      result.diag['studio_final_url'] = `hata: ${String(e).slice(0, 80)}`;
    }

    // 2) ytcfg fallback (studio)
    if (!result.channel_id) {
      try {
        const id = await page.evaluate(() => {
          try {
            if (window.ytcfg && typeof window.ytcfg.get === 'function') {
              return window.ytcfg.get('CHANNEL_ID') || '';
            }
            if (window.ytcfg && window.ytcfg.data_) return window.ytcfg.data_.CHANNEL_ID || '';
          } catch (e) { /* yut */ }
          return '';
        });
        if (id && /^UC[A-Za-z0-9_-]{22}$/.test(id)) {
          result.channel_id = id;
          result.method = 'ytcfg';
        }
      } catch (_) { /* sayfa kapandiysa */ }
    }

    // 3) sayfa icerigi genis tarama (picker/externalId/bootstrap; yalnizca public UC ID)
    try {
      result.diag['studio_title'] = await page.title().catch(() => '');
      const html = await page.content();
      for (const m of html.matchAll(UC_RE)) allUC.add(m[0]);
      const m2 = html.match(/"(?:externalId|channelId)"\s*:\s*"(UC[A-Za-z0-9_-]{22})"/);
      if (m2 && !result.channel_id) {
        result.channel_id = m2[1];
        result.method = 'body-regex';
      }
    } catch (_) { /* yut */ }

    await ctx.close().catch(() => {});
  } catch (e) {
    result.diag['browser'] = String(e).slice(0, 150);
  } finally {
    await browser.close().catch(() => {});
  }

  result.candidates = [...new Set([...result.candidates, ...allUC])].slice(0, 10);
  console.log(`[${LABEL}] tarama adaylari: ${result.candidates.join(',') || 'yok'}`);
  console.log(`[${LABEL}] teshis: ${JSON.stringify(result.diag)}`);
  console.log(`[${LABEL}] KIMLIK: ${result.channel_id || 'COZULEMEDI'} (yontem: ${result.method || '-'})`);
  if (JSON_OUT) {
    fs.writeFileSync(JSON_OUT, JSON.stringify(result, null, 2));
  }
  // Kimlik cozulemedi = probe sorunu, akis hatasi degil -> 0 dondur; karar wire adiminda.
  process.exit(0);
})();
