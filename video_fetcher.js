/**
 * video_fetcher.js  —  Cookie-tabanlı Playwright Video Çekici
 *
 * API key gerektirmez. Mevcut Pixabay/Pexels oturumu (cookies.json /
 * storage_state.json) üzerinden çalışır.
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
    await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: TIMEOUT_MS });
    await page.waitForTimeout(4000);
  } catch(e) {
    console.error('[Pexels] Sayfa yükleme timeout, alternatif deneniyor...');
    return null;
  }

  // __NEXT_DATA__ veya vids.pexels.com URL'leri
  const pexelsUrls = await page.evaluate(() => {
    const urls = [];
    if (window.__NEXT_DATA__) {
      const str = JSON.stringify(window.__NEXT_DATA__);
      const m = str.match(/https:\/\/[^"\\]+vids\.pexels\.com[^"\\]+\.mp4[^"\\]*/g);
      if (m) urls.push(...m);
    }
    // Video elementleri
    document.querySelectorAll('video source').forEach(s => {
      if (s.src && s.src.includes('.mp4')) urls.push(s.src);
    });
    return [...new Set(urls)].slice(0, 5);
  });

  if (pexelsUrls.length > 0) {
    // SD (640p) yerine HD tercih et
    const hd = pexelsUrls.find(u => u.includes('hd')) || pexelsUrls[0];
    console.error(`[Pexels] ✅ URL: ${hd.substring(0,80)}`);
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
  if (!fs.existsSync(COOKIES_PATH) && !fs.existsSync(STORAGE_PATH)) {
    console.error('HATA: cookies.json veya storage_state.json bulunamadı!');
    process.exit(1);
  }

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox','--disable-dev-shm-usage','--disable-blink-features=AutomationControlled']
  });

  let ctxOpts = {
    viewport: { width: 1280, height: 800 },
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
  };
  if (fs.existsSync(STORAGE_PATH)) ctxOpts.storageState = STORAGE_PATH;
  
  const context = await browser.newContext(ctxOpts);
  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  });

  if (fs.existsSync(COOKIES_PATH)) {
    const cookies = JSON.parse(fs.readFileSync(COOKIES_PATH, 'utf8'));
    if (Array.isArray(cookies) && cookies.length > 0) await context.addCookies(cookies);
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

main().catch(e => { console.error('KRİTİK HATA:', e.message); process.exit(1); });
