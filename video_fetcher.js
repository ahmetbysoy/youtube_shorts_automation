/**
 * video_fetcher.js  —  Cookie-tabanlı Playwright Video Çekici
 *
 * API key gerektirmez. Pixabay/Pexels oturumu üzerinden stok video arar ve indirir.
 *
 * Cookie kaynakları (öncelik sırasıyla):
 *   1. PEXELS_COOK / PIXABAY_COOK ortam değişkenleri (GitHub Secrets için).
 *      İçerik şu formatlardan biri olabilir:
 *        - Playwright storage_state.json içindeki "cookies" JSON dizisi
 *        - Netscape/Mozilla cookie-jar JSON dizisi (name,value,domain,...)
 *        - "name=value; name2=value2" string formatı
 *   2. storage_state.json (tam Playwright context durumu)
 *   3. cookies.json (yalnızca cookie dizisi)
 *
 * Kullanım:
 *   node video_fetcher.js <keyword> <output_path> [--portrait]
 *
 * Çıktı: 0 = başarılı, 1 = hata
 * stdout son satır: indirilen dosyanın tam yolu
 */

'use strict';
const { chromium } = require('playwright');
const fs   = require('fs');
const path = require('path');
const https = require('https');
const http  = require('http');
const url   = require('url');

const BASE_DIR       = __dirname;
const COOKIES_PATH   = path.join(BASE_DIR, 'cookies.json');
const STORAGE_PATH   = path.join(BASE_DIR, 'storage_state.json');
const TIMEOUT_MS     = 25000;
const DOWNLOAD_TIMEOUT = 60000;

// ── Cookie çözümleme ──────────────────────────────────────────
function normalizeCookie(c, defaultDomain) {
  if (!c || !c.name || !c.value) return null;
  return {
    name: String(c.name),
    value: String(c.value),
    domain: c.domain || defaultDomain,
    path: c.path || '/',
    secure: !!c.secure,
    httpOnly: !!c.httpOnly,
    sameSite: (c.sameSite && ['Strict', 'Lax', 'None'].includes(c.sameSite)) ? c.sameSite : 'Lax',
    expires: typeof c.expires === 'number' && c.expires > 0 ? c.expires : -1,
  };
}

function parseCookieString(raw, defaultDomain) {
  const out = [];
  // Ham "k=v; k2=v2" formatı
  for (const part of String(raw).split(';')) {
    const i = part.indexOf('=');
    if (i > 0) {
      const n = normalizeCookie({
        name: part.slice(0, i).trim(),
        value: part.slice(i + 1).trim(),
        domain: defaultDomain, path: '/'
      }, defaultDomain);
      if (n) out.push(n);
    }
  }
  return out;
}

function loadCookiesFromEnv(envName, defaultDomain) {
  const raw = process.env[envName];
  if (!raw) return [];
  try {
    const data = JSON.parse(raw);
    if (Array.isArray(data)) {
      return data.map(c => normalizeCookie(c, defaultDomain)).filter(Boolean);
    }
    if (typeof data === 'object' && data !== null) {
      // storage_state -> {cookies:[...], origins:[...]}
      if (Array.isArray(data.cookies)) {
        return data.cookies.map(c => normalizeCookie(c, defaultDomain)).filter(Boolean);
      }
      // {name:value,...} dict
      return Object.entries(data).map(([name, value]) =>
        normalizeCookie({ name, value, domain: defaultDomain, path: '/' }, defaultDomain)
      ).filter(Boolean);
    }
  } catch (_) { /* JSON değil, string formatını dene */ }
  return parseCookieString(raw, defaultDomain);
}

function loadCookiesFromFile(filePath, defaultDomain) {
  if (!fs.existsSync(filePath)) return [];
  try {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    if (Array.isArray(data)) {
      return data.map(c => normalizeCookie(c, defaultDomain)).filter(Boolean);
    }
    if (data && Array.isArray(data.cookies)) {
      return data.cookies.map(c => normalizeCookie(c, defaultDomain)).filter(Boolean);
    }
  } catch (e) {
    console.error(`[Cookie] ${filePath} okunamadi: ${e.message}`);
  }
  return [];
}

// ── CLI ────────────────────────────────────────────────────────
const args    = process.argv.slice(2);
const keyword = args[0] || 'nature cinematic';
const outPath = args[1] || path.join(BASE_DIR, 'output', 'fetched_video.mp4');
const PORTRAIT = args.includes('--portrait');

// ── Yardımcı: dosya indir ──────────────────────────────────────
function downloadFile(fileUrl, destPath) {
  return new Promise((resolve, reject) => {
    const parsed  = url.parse(fileUrl);
    const proto   = parsed.protocol === 'https:' ? https : http;
    const timeout = setTimeout(() => reject(new Error('Download timeout')), DOWNLOAD_TIMEOUT);

    const req = proto.get(fileUrl, {
      headers: { 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36' }
    }, res => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        clearTimeout(timeout);
        return downloadFile(res.headers.location, destPath).then(resolve).catch(reject);
      }
      if (res.statusCode !== 200) {
        clearTimeout(timeout);
        return reject(new Error(`HTTP ${res.statusCode} for ${fileUrl}`));
      }
      const file = fs.createWriteStream(destPath);
      res.pipe(file);
      file.on('finish', () => { clearTimeout(timeout); file.close(); resolve(destPath); });
      file.on('error', err => { clearTimeout(timeout); reject(err); });
    });
    req.on('error', err => { clearTimeout(timeout); reject(err); });
  });
}

// ── Pixabay scraper ────────────────────────────────────────────
async function fetchFromPixabay(page, kw) {
  const searchUrl = `https://pixabay.com/videos/search/${encodeURIComponent(kw)}/?order=popular`;
  console.error(`[Pixabay] Arama: ${searchUrl}`);
  
  await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: TIMEOUT_MS });
  await page.waitForTimeout(3000);

  const tinyUrls = await page.evaluate(() => {
    const urls = new Set();
    document.querySelectorAll('script').forEach(s => {
      const text = s.textContent || '';
      const m = text.match(/https:\/\/cdn\.pixabay\.com\/video\/[^"'\\]+_tiny\.mp4/g);
      if (m) m.forEach(u => urls.add(u));
    });
    return [...urls];
  });

  if (tinyUrls.length === 0) {
    console.error(`[Pixabay] "${kw}" için tiny URL bulunamadı`);
    return null;
  }

  // İlk geçerli _large URL'yi bul
  for (const tiny of tinyUrls) {
    const largeUrl = tiny.replace('_tiny.mp4', '_large.mp4');
    // HEAD isteği ile varlığını doğrula
    try {
      const ok = await page.evaluate(async (u) => {
        const r = await fetch(u, { method: 'HEAD' });
        return r.ok;
      }, largeUrl);
      if (ok) {
        console.error(`[Pixabay] ✅ large URL: ${largeUrl.substring(0,80)}`);
        return largeUrl;
      }
    } catch(e) { /* devam */ }
  }
  
  // _large yoksa _medium dene
  for (const tiny of tinyUrls) {
    const medUrl = tiny.replace('_tiny.mp4', '_medium.mp4');
    try {
      const ok = await page.evaluate(async (u) => {
        const r = await fetch(u, { method: 'HEAD' });
        return r.ok;
      }, medUrl);
      if (ok) {
        console.error(`[Pixabay] ✅ medium URL: ${medUrl.substring(0,80)}`);
        return medUrl;
      }
    } catch(e) { /* devam */ }
  }

  // Fallback: tiny kullan
  console.error(`[Pixabay] ⚠️  Yalnızca tiny mevcut: ${tinyUrls[0].substring(0,80)}`);
  return tinyUrls[0];
}

// ── Pexels scraper ─────────────────────────────────────────────
async function fetchFromPexels(page, kw) {
  const searchUrl = `https://www.pexels.com/search/videos/${encodeURIComponent(kw)}/`;
  console.error(`[Pexels] Arama: ${searchUrl}`);

  try {
    // Cloudflare ve Next.js hydration icin networkidle + ekstra bekleme
    await page.goto(searchUrl, { waitUntil: 'networkidle', timeout: Math.max(60000, TIMEOUT_MS * 2) });
    await page.waitForTimeout(3000);
  } catch(e) {
    console.error('[Pexels] Sayfa yükleme hatasi, domcontentloaded ile tekrar deneniyor: ' + e.message);
    try {
      await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: TIMEOUT_MS });
      await page.waitForTimeout(5000);
    } catch(e2) {
      console.error('[Pexels] Ikinci yükleme de basarisiz: ' + e2.message);
      return null;
    }
  }

  // __NEXT_DATA__ / __APOLLO_STATE__ / <script> ve <video> taglerinden mp4 cikar
  const pexelsUrls = await page.evaluate(() => {
    const urls = new Set();
    // window uzerindeki data objeleri
    [window.__NEXT_DATA__, window.__APOLLO_STATE__].forEach(obj => {
      if (!obj) return;
      const str = JSON.stringify(obj);
      const m = str.match(/https:\/\/[^"'\\]+vids\.pexels\.com[^"'\\]+\.mp4[^"'\\]*/g);
      if (m) m.forEach(u => urls.add(u));
    });
    // Tum <script> bloklari (Next.js statik props, __NEXT_DATA__ satirici)
    document.querySelectorAll('script').forEach(s => {
      const t = s.textContent || '';
      const m = t.match(/https:\/\/[^"'\\]+vids\.pexels\.com[^"'\\]+\.mp4[^"'\\]*/g);
      if (m) m.forEach(u => urls.add(u));
    });
    // Video elementleri
    document.querySelectorAll('video, video source').forEach(s => {
      const src = s.src || s.currentSrc;
      if (src && src.includes('.mp4')) urls.add(src);
    });
    return [...urls];
  });
  console.error(`[Pexels] ${pexelsUrls.length} adet mp4 URL bulundu`);

  if (pexelsUrls.length > 0) {
    // Tercih sirasi:
    // 1) Gercek kullanici videolari: vids.pexels.com/video-files/...-hd_1920_1080_*.mp4 (tam HD landscape)
    // 2) vids.pexels.com/video-files/...-uhd_2560_1440_*.mp4 (4K)
    // 3) video-files icinde -hd_ (dikey HD dahil)
    // 4) Diger vids.pexels.com (AI UGC degil)
    // 5) AI UGC (aigc-bundle) — ancak hicbiri yoksa son care
    // Kucuk preview/thumb/tiny her zaman elenir.
    const byPriority = [
      urls => urls.find(u => /video-files\/.*hd_1920_1080/i.test(u)),
      urls => urls.find(u => /video-files\/.*uhd_2560_1440/i.test(u)),
      urls => urls.find(u => /video-files\/.*-hd_/i.test(u)),
      urls => urls.find(u => /vids\.pexels\.com\/video-files\//i.test(u)),
      urls => urls.find(u => /vids\.pexels\.com/i.test(u) && !/aigc|preview|thumb|tiny/i.test(u)),
      urls => urls.find(u => !/preview|thumb|tiny/i.test(u)),
      urls => urls[0],
    ];
    let hd = null;
    for (const pick of byPriority) { hd = pick(pexelsUrls); if (hd) break; }
    console.error(`[Pexels] ✅ URL: ${hd.substring(0,120)}`);
    return hd;
  }

  // Video ID üzerinden deneme
  const videoIds = await page.evaluate(() => {
    const ids = [];
    document.querySelectorAll('article[class*="video"]').forEach(el => {
      const a = el.querySelector('a[href*="/video/"]');
      if (a) {
        const m = a.href.match(/\/video\/(\d+)\//);
        if (m) ids.push(m[1]);
      }
    });
    // data-id attribute
    document.querySelectorAll('[data-video-id], [data-id]').forEach(el => {
      const id = el.getAttribute('data-video-id') || el.getAttribute('data-id');
      if (id && /^\d{6,}$/.test(id)) ids.push(id);
    });
    return [...new Set(ids)].slice(0,3);
  });

  for (const id of videoIds) {
    try {
      const resp = await page.goto(
        `https://www.pexels.com/video/${id}/download/`,
        { waitUntil: 'domcontentloaded', timeout: 15000 }
      );
      const dlUrl = page.url();
      if (dlUrl.includes('.mp4') || dlUrl.includes('pexels.com/video')) {
        console.error(`[Pexels] ✅ Download URL: ${dlUrl.substring(0,80)}`);
        return dlUrl;
      }
    } catch(e) { /* devam */ }
  }

  console.error('[Pexels] Video URL bulunamadı');
  return null;
}

// ── Ana fonksiyon ──────────────────────────────────────────────
async function main() {
  // Cookie'leri env > dosya önceliğiyle topla
  const envCookies = [
    ...loadCookiesFromEnv('PEXELS_COOK', '.pexels.com'),
    ...loadCookiesFromEnv('PIXABAY_COOK', '.pixabay.com'),
  ];
  const fileCookies = [
    ...loadCookiesFromFile(COOKIES_PATH, '.pexels.com'),
  ];
  const storageStateExists = fs.existsSync(STORAGE_PATH);
  const hasAnyCookie = envCookies.length > 0 || fileCookies.length > 0 || storageStateExists;

  if (!hasAnyCookie) {
    console.error('HATA: PEXELS_COOK/PIXABAY_COOK env yok ve cookies.json/storage_state.json da bulunamadi!');
    process.exit(1);
  }
  if (envCookies.length > 0) {
    console.error(`[Cookie] Ortam degiskenlerinden ${envCookies.length} adet cookie yuklendi` +
      (process.env.PEXELS_COOK ? ' (PEXELS_COOK)' : '') +
      (process.env.PIXABAY_COOK ? ' (PIXABAY_COOK)' : ''));
  }
  if (fileCookies.length > 0) {
    console.error(`[Cookie] cookies.json'dan ${fileCookies.length} adet cookie yuklendi`);
  }

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox','--disable-dev-shm-usage','--disable-blink-features=AutomationControlled']
  });

  const ctxOpts = {
    viewport: { width: 1280, height: 800 },
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
  };
  if (storageStateExists && envCookies.length === 0) {
    // storage_state.json yalnizca env cookie yoksa kullan (env cookie'leri daha guncel)
    ctxOpts.storageState = STORAGE_PATH;
  }

  const context = await browser.newContext(ctxOpts);
  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  });

  // Env + dosya cookie'lerini context'e ekle (zaten normalize edildi)
  const allCookies = [...envCookies, ...fileCookies];
  // Aynı (domain,path,name) için tekilleştir (env öncelikli)
  const seen = new Set();
  const deduped = [];
  for (const c of allCookies) {
    const key = `${c.domain}|${c.path}|${c.name}`;
    if (!seen.has(key)) { seen.add(key); deduped.push(c); }
  }
  if (deduped.length > 0) {
    await context.addCookies(deduped);
    console.error(`[Cookie] Context'e ${deduped.length} adet cookie yuklendi`);
  }

  const page = await context.newPage();
  let videoUrl = null;

  // 1. Pixabay dene (daha güvenilir)
  videoUrl = await fetchFromPixabay(page, keyword);

  // 2. Başarısız → Pexels dene
  if (!videoUrl) {
    videoUrl = await fetchFromPexels(page, keyword);
  }

  // 3. Her ikisi de başarısız
  if (!videoUrl) {
    console.error(`[HATA] "${keyword}" için hiçbir siteden video URL alınamadı`);
    await browser.close();
    process.exit(1);
  }

  // İndir
  console.error(`[İndirme] ${videoUrl.substring(0,80)}...`);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  
  try {
    await downloadFile(videoUrl, outPath);
    const size = fs.statSync(outPath).size;
    if (size < 50000) throw new Error(`Dosya çok küçük: ${size} bytes`);
    console.error(`[✅] İndirildi: ${outPath} (${(size/1024/1024).toFixed(1)} MB)`);
    console.log(outPath); // Ana çıktı — Python tarafından okunur
  } catch(e) {
    console.error(`[HATA] İndirme başarısız: ${e.message}`);
    await browser.close();
    process.exit(1);
  }

  await browser.close();
}

if (args.includes('--metadata')) {
  // Strict scene mode is a catalog only. Legacy download CLI below is unchanged.
  require('./scripts/stock_media_catalog.cjs').main(args).catch(() => {
    console.error('STOCK_CATALOG_FAILED'); process.exitCode = 1;
  });
} else {
  main().catch(e => { console.error('KRİTİK HATA:', e.message); process.exit(1); });
}
