#!/usr/bin/env node
'use strict';
// Backfill custom Shorts thumbnails. Only edits thumbnail; title/description/visibility stay untouched.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const CHANNEL_ID = process.env.YT_CHANNEL_ID || 'UCBZVbwc7s7TeUCcOaN58oHQ';
const OUT = path.resolve(process.env.BACKFILL_OUT || 'backfill_output');
const LIMIT = Math.max(1, Number(process.env.MAX_PER_RUN || 5));
const START_AFTER = process.env.START_AFTER || '';
const DRY_RUN = process.env.DRY_RUN === '1';
const DEBUG = process.env.DEBUG === '1' || process.env.DEBUG_SCREENSHOTS === '1';
// Videolar arasi bekleme. Pollinations ucretsiz katmani IP bazli rate-limit
// uyguladigi icin 25sn altinda riskli. GitHub Actions'da da bunu kullan.
const DELAY_MS = Math.max(8000, Number(process.env.DELAY_MS || 25000));
const BASE = process.cwd();
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = m => console.log('[' + new Date().toISOString() + '] ' + m);

// Headless Chromium UA'sinda "HeadlessChrome" ibaresi gecer. YouTube Studio bunu
// gorup "desteklenmeyen tarayici" ekrani cikariyor. Gercek Chrome UA'si gibi davran.
function realChromeUserAgent(defaultUA) {
  if (!defaultUA) return defaultUA;
  return defaultUA.replace(/\s*HeadlessChrome\//g, ' Chrome/');
}

// "Deneyiminizi iyilestirin" / "YOUTUBE STUDIO'YA GEC" engel ekrani gorunurse
// baglantiya tiklayip normal Studio arayuzune gec.
async function bypassBrowserCompat(page, label) {
  try {
    // Hem Turkce hem Ingilizce metinleri dene
    const btn = page.locator(
      'a:has-text("YOUTUBE STUDIO\'YA GEÇ"),' +
      'a:has-text("YOUTUBE STUDIOYA GEC"),' +
      'a:has-text("GO TO YOUTUBE STUDIO"),' +
      'button:has-text("YOUTUBE STUDIO\'YA GEÇ"),' +
      'button:has-text("GO TO YOUTUBE STUDIO")'
    ).first();
    if (await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
      log('Uyumluluk ekrani goruldu, Studio girisi tiklaniyor (' + (label||'') + ')...');
      await btn.click({ timeout: 5000 });
      await sleep(5000);
      // Tiklamadan sonra URL halen ayni ise (JS handler ile gecis),
      // beklemeye devam; degisti ise yeni sayfanin yuklenmesini bekle.
      await page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(()=>{});
      await sleep(2000);
      return true;
    }
    // Bazi durumlarda "Continue to Studio" gibi CTA da olabilir.
    const cta = page.locator('a[href*="studio.youtube.com"], button:has-text("Continue"), button:has-text("Devam")').first();
    if (await cta.isVisible({ timeout: 1500 }).catch(() => false)) {
      const body = await page.locator('body').innerText().catch(()=>'');
      if (/Deneyiminizi|desteklenmeyen|unsupported browser|update your browser/i.test(body)) {
        log('Uyumluluk CTA bulundu, tiklaniyor...');
        await cta.click({ timeout: 5000 });
        await sleep(5000);
        return true;
      }
    }
  } catch (e) {
    log('bypassBrowserCompat hatasi: ' + e.message);
  }
  return false;
}

async function dumpPage(page, label) {
  // Hata ayiklama icin screenshot + HTML dump. DEBUG modunda her zaman,
  // yoksa sadece cagirildiginda (orn. video listesi bossa).
  try {
    const safe = String(label).replace(/[^a-zA-Z0-9._-]+/g, '_');
    const dbgDir = path.join(OUT, 'debug');
    fs.mkdirSync(dbgDir, { recursive: true });
    const url = page.url();
    const title = await page.title().catch(() => '');
    log('DUMP [' + label + '] url=' + url + ' title=' + title);
    fs.writeFileSync(path.join(dbgDir, safe + '.url.txt'), 'URL: ' + url + '\nTitle: ' + title + '\n', 'utf8');
    await page.screenshot({ path: path.join(dbgDir, safe + '.png'), fullPage: true, timeout: 15000 }).catch(e => {
      log('Screenshot alinamadi: ' + e.message);
    });
    const html = await page.content().catch(() => '');
    fs.writeFileSync(path.join(dbgDir, safe + '.html'), html, 'utf8');
    const body = await page.locator('body').innerText({ timeout: 5000 }).catch(() => '');
    fs.writeFileSync(path.join(dbgDir, safe + '.txt'), body.slice(0, 50000), 'utf8');
  } catch (e) {
    log('dumpPage hatasi: ' + e.message);
  }
}

function loadState() {
  if (process.env.STORAGE_STATE_JSON) {
    const value = JSON.parse(process.env.STORAGE_STATE_JSON);
    if (value.cookies) return value;
  }
  if (process.env.COOKIES_JSON) {
    const cookies = JSON.parse(process.env.COOKIES_JSON);
    if (Array.isArray(cookies) && cookies.length) return { cookies, origins: [] };
  }
  for (const p of ['storage_state.json', 'session_capture/storage_state.json']) {
    if (fs.existsSync(p) && fs.statSync(p).size > 100) return JSON.parse(fs.readFileSync(p, 'utf8'));
  }
  if (fs.existsSync('cookies.json')) return { cookies: JSON.parse(fs.readFileSync('cookies.json', 'utf8')), origins: [] };
  throw new Error('YouTube oturumu bulunamadi: STORAGE_STATE_JSON veya COOKIES_JSON gerekli.');
}

function buildPrompt(title) {
  const clean = String(title || 'YouTube Shorts').replace(/#Shorts/ig, '').trim().slice(0, 180);
  return 'Video title: "' + clean + '". Create an exceptionally compelling YouTube Shorts thumbnail in vertical 9:16. ' +
    'The image must accurately represent this exact title, one unmistakable large central subject, an emotionally powerful or surprising moment, ' +
    'dramatic cinematic lighting, vivid colors, crisp photorealistic detail, strong contrast, mobile-first composition, ' +
    'and a powerful curiosity gap that makes viewers want to tap. Do not invent facts. No text, letters, numbers, logos, watermark, borders, collage or split screen.';
}

// Pollinations model fallback sirasi: once ucretsiz hizli modellerle baslar,
// flux paralidaysa 402 donunce diger modele gecer. Hicbirini belirtmezsen
// 'sana' modeli kullanilir (ucretsiz, hizli, kaliteli).
const IMAGE_MODELS = (process.env.IMAGE_MODELS || 'sana,flux,turbo').split(',').map(s => s.trim()).filter(Boolean);
// Rate-limit/402 halinde modeller arasi bekleme (ms)
const MODEL_SWITCH_DELAY_MS = Math.max(3000, Number(process.env.MODEL_SWITCH_DELAY_MS || 8000));
// Ayni modelde denemeler arasi bekleme
const ATTEMPT_DELAY_MS = Math.max(3000, Number(process.env.ATTEMPT_DELAY_MS || 8000));
// Rate limit sonrasi global cooldown (ms) — ard arda 402 gelirse uzun bekle
const GLOBAL_COOLDOWN_MS = Math.max(5000, Number(process.env.GLOBAL_COOLDOWN_MS || 30000));

async function fetchPollinations(model, prompt, seed, outPath) {
  const modelParam = model ? '&model=' + encodeURIComponent(model) : '';
  const url = 'https://image.pollinations.ai/prompt/' + prompt +
    '?width=1080&height=1920&nologo=true&seed=' + seed + modelParam;
  log('  → model=' + (model || '(default)') + ' seed=' + seed);
  const t0 = Date.now();
  const response = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
      'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
      'Referer': 'https://studio.youtube.com/',
    },
    signal: AbortSignal.timeout(120000),
  });
  const dt = Date.now() - t0;
  log('    HTTP ' + response.status + ' (' + dt + 'ms) x-model-used=' + (response.headers.get('x-model-used') || '-'));
  if (response.status === 402 || response.status === 429) {
    const retry = response.headers.get('retry-after') || '';
    const err = new Error('RATE_LIMITED');
    err.status = response.status;
    err.retryAfter = retry ? Number(retry) : 0;
    throw err;
  }
  if (!response.ok) throw new Error('HTTP ' + response.status);
  const bytes = Buffer.from(await response.arrayBuffer());
  const type = response.headers.get('content-type') || '';
  if (!type.includes('image') || bytes.length < 20000) {
    throw new Error('gecersiz gorsel (type=' + type + ', ' + bytes.length + ' byte)');
  }
  fs.writeFileSync(outPath, bytes);
  return { model: response.headers.get('x-model-used') || model, size: bytes.length, ms: dt };
}

async function makeCover(title, outPath) {
  const prompt = encodeURIComponent(buildPrompt(title));
  const lastErrors = [];
  let rateLimitHits = 0;
  for (let mIdx = 0; mIdx < IMAGE_MODELS.length; mIdx++) {
    const model = IMAGE_MODELS[mIdx];
    const seed = Math.floor(Math.random() * 1e9);
    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        const res = await fetchPollinations(model, prompt, seed, outPath);
        log('✅ Kapak hazir: model=' + res.model + ' ' + res.size + ' byte (' + res.ms + 'ms) -> ' + path.basename(outPath));
        return res;
      } catch (e) {
        if (e.message === 'RATE_LIMITED') {
          rateLimitHits++;
          const wait = (e.retryAfter ? e.retryAfter * 1000 : 0) || GLOBAL_COOLDOWN_MS;
          log('  ⏳ Rate limit hit (HTTP ' + e.status + '), ' + (wait/1000) + 'sn bekleniyor...');
          await sleep(wait);
          // Bu modeli daha da deneme — sonraki modele gec
          break;
        }
        lastErrors.push(model + '/' + attempt + ': ' + e.message);
        log('  ✗ ' + e.message);
        if (attempt < 2) await sleep(ATTEMPT_DELAY_MS);
      }
    }
    if (mIdx < IMAGE_MODELS.length - 1) await sleep(MODEL_SWITCH_DELAY_MS);
  }
  // Butun modeller tukendiyse son bir sans: model parametresi olmadan (varsayilan) dene.
  try {
    log('  → son sans: modelsiz (varsayilan) deneniyor...');
    const res = await fetchPollinations('', prompt, Math.floor(Math.random()*1e9), outPath);
    log('✅ Kapak hazir (fallback default model): ' + res.size + ' byte (' + res.ms + 'ms)');
    return res;
  } catch (e) {
    lastErrors.push('default: ' + e.message);
  }
  throw new Error('AI kapak olusturulamadi (tum modeller ve fallback denendi). Son hatalar: ' +
    lastErrors.slice(-6).join(' | ') + ' (rateLimitHits=' + rateLimitHits + ')');
}

async function collectVideos(page) {
  const url = 'https://studio.youtube.com/channel/' + CHANNEL_ID +
    '/videos/short?filter=%5B%5D&sort=%7B%22columnType%22%3A%22date%22%2C%22sortOrder%22%3A%22DESCENDING%22%7D';
  log('Studio Shorts sayfasina gidiliyor: ' + url);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await sleep(4000);
  log('Son URL (nav sonrasi): ' + page.url());
  if (/accounts\.google\.com|ServiceLogin/i.test(page.url())) {
    await dumpPage(page, '01_login_redirect');
    throw new Error('Studio oturumu gecersiz (login sayfasina yonlendirildi).');
  }
  // Uyumluluk/gecis ekrani varsa as.
  for (let attempt = 0; attempt < 3; attempt++) {
    const bypassed = await bypassBrowserCompat(page, 'collectVideos#' + attempt);
    if (!bypassed) break;
    await sleep(3000);
  }
  await sleep(3000);
  log('Son URL (bypass sonrasi): ' + page.url());
  if (/accounts\.google\.com|ServiceLogin/i.test(page.url())) {
    await dumpPage(page, '01_login_after_bypass');
    throw new Error('Studio oturumu gecersiz.');
  }
  // YouTube Studio bazen kanal secim ekrani, "Get started" veya "Verify it's you"
  // ekraninda kaliyor; bunlari kontrol et.
  const body = await page.locator('body').innerText().catch(() => '');
  if (/Kimliğinizi doğrulayın|Verify it.s you|2-Step Verification|2FA/i.test(body)) {
    await dumpPage(page, '01_2fa_challenge');
    throw new Error('Google 2FA/kimlik dogrulamasi istiyor.');
  }
  if (DEBUG) await dumpPage(page, '01_after_nav');

  // Sayfa boyutu dropdown'i
  const pageSize = page.locator('ytcp-dropdown-trigger#page-size').first();
  if (await pageSize.isVisible().catch(() => false)) {
    log('Sayfa boyutu 50 olarak ayarlaniyor...');
    await pageSize.click().catch(() => {});
    await sleep(800);
    await page.locator('tp-yt-paper-item:has-text("50")').first().click({ timeout: 3000 }).catch(() => {});
    await sleep(3500);
    if (DEBUG) await dumpPage(page, '02_after_pagesize');
  } else {
    log('UYARI: page-size dropdown bulunamadi.');
  }

  const all = new Map();
  for (let pageNo = 0; pageNo < 100; pageNo++) {
    // Birden fazla olasi row selector'u dene (Studio arayuzu sik degisir).
    const rows = await page.locator('ytcp-video-row, ytcr-video-row, ytcp-video-list-row').evaluateAll(els => els.map(e => {
      const a = e.querySelector('a#video-title, a.ytcp-video-row, a[href*="/video/"]');
      const href = a ? a.getAttribute('href') || '' : '';
      const idMatch = href.match(/video\/([^/?#]+)/);
      const id = idMatch ? idMatch[1] : '';
      const title = (e.querySelector('#video-title, #video-title-text, [id*="title"]')?.textContent || '').trim();
      const status = (e.querySelector('.tablecell-visibility, #visibility-cell, ytcp-video-visibility-cell')?.innerText || '').trim();
      const img = e.querySelector('img')?.currentSrc || e.querySelector('img')?.src || '';
      return { id, title, status, oldThumbnail: img };
    }).filter(x => x.id && x.title));
    log('Sayfa ' + (pageNo+1) + ': ' + rows.length + ' video satiri bulundu.');
    for (const row of rows) all.set(row.id, row);
    if (rows.length === 0 && pageNo === 0) {
      // Ilk sayfa bossa debug dump al ki nedenini gorelim.
      await dumpPage(page, '03_no_rows_page1');
      // Hic row yoksa sayfalama da olmayacak; kir.
      break;
    }
    const next = page.locator('ytcp-icon-button#navigate-after, #navigate-after, [aria-label="Next page"], [aria-label="Sonraki sayfa"]').first();
    if (!(await next.isVisible().catch(() => false))) {
      log('"Next" butonu gorunmuyor, sayfalama sonu.');
      break;
    }
    const disabled = await next.evaluate(el => el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true').catch(() => true);
    if (disabled) { log('"Next" butonu devre disi.'); break; }
    await next.click();
    await sleep(3000);
  }

  const result = [...all.values()];
  if (result.length === 0) {
    await dumpPage(page, '04_zero_videos_final');
    log('HIC VIDEO BULUNAMADI. URL=' + page.url() + ' title=' + (await page.title().catch(()=>'')));
    // Sayfa govde metninden ilk 500 karakteri logla.
    const bodyText = await page.locator('body').innerText().catch(() => '');
    log('Govde ozeti: ' + bodyText.replace(/\s+/g,' ').slice(0,500));
  }
  return result;
}

async function backupOldThumb(page, video, index) {
  if (!video.oldThumbnail || !/^https?:/i.test(video.oldThumbnail)) return '';
  try {
    const res = await page.request.get(video.oldThumbnail, { timeout: 15000, maxRedirects: 2 });
    if (!res.ok()) return '';
    const ct = (res.headers()['content-type'] || '').toLowerCase();
    // Login/redirect donusu HTML sayfasi olursa (orn. cookie gecersizse) yedek alma.
    if (!ct.startsWith('image/')) {
      log('Eski kapak image content-type degil, yedeklenmedi (' + ct + ')');
      return '';
    }
    const ext = ct.includes('png') ? '.png' : ct.includes('webp') ? '.webp' : '.jpg';
    const dest = path.join(OUT, 'originals', video.id + ext);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    const body = await res.body();
    if (body.length < 1000) return '';
    fs.writeFileSync(dest, body);
    return dest;
  } catch (e) {
    log('Eski kapak yedeklenemedi: ' + e.message);
    return '';
  }
}

async function applyOne(page, video, index) {
  const safeTitle = video.title.replace(/\s+/g, ' ').trim().slice(0, 100);
  const cover = path.join(OUT, 'generated', video.id + '.jpg');
  fs.mkdirSync(path.dirname(cover), { recursive: true });
  const originalBackup = await backupOldThumb(page, video, index);

  // DRY_RUN'da yapay zeka ile kapak uretmeyi ve Studio sayfasina gitmeyi atla.
  // Amac sadece cookie / liste / akis sagligini test etmektir; bunu hizli yap.
  if (DRY_RUN) {
    log('[DRY-RUN] Kapak uretimi ve Studio edit sayfasi atlandi: ' + video.id);
    return { id: video.id, title: safeTitle, dryRun: true, originalBackup, cover: '' };
  }

  await makeCover(safeTitle, cover);

  await page.goto('https://studio.youtube.com/video/' + video.id + '/edit', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await sleep(3000);
  for (let attempt = 0; attempt < 2; attempt++) {
    const bypassed = await bypassBrowserCompat(page, 'applyOne#' + video.id + '#' + attempt);
    if (!bypassed) break;
    await sleep(3000);
  }
  await sleep(3500);
  if (/accounts\.google\.com|ServiceLogin/i.test(page.url())) throw new Error('Studio oturumu gecersiz.');
  const body = await page.locator('body').innerText().catch(() => '');
  if (/Kimliğinizi doğrulayın|Verify it.s you/i.test(body)) throw new Error('Google ek kimlik dogrulamasi istiyor; guvenlik adimi atlanmadi.');
  const input = page.locator(
    'ytcp-thumbnail-uploader input[type="file"], ytcp-video-thumbnail-editor input[type="file"], ' +
    'ytcp-video-custom-still-editor input[type="file"], input#file-loader'
  ).first();
  if (!(await input.count())) throw new Error('Bu videonun Studio sayfasinda ozel kucuk resim yukleme alani yok.');

  const before = await page.evaluate(() => {
    const ed = document.querySelector('ytcp-video-thumbnail-editor, ytcp-thumbnail-uploader, ytcp-video-custom-still-editor');
    return ed ? [...ed.querySelectorAll('img')].map(i => i.currentSrc || i.src).filter(Boolean).join('|') : '';
  });
  await input.setInputFiles(cover);
  await sleep(6500);
  const after = await page.evaluate(() => {
    const ed = document.querySelector('ytcp-video-thumbnail-editor, ytcp-thumbnail-uploader, ytcp-video-custom-still-editor');
    return ed ? [...ed.querySelectorAll('img')].map(i => i.currentSrc || i.src).filter(Boolean).join('|') : '';
  });
  const currentBody = await page.locator('body').innerText().catch(() => '');
  if (/günlük.*küçük resim|daily.*thumbnail.*limit|thumbnail.*limit reached/i.test(currentBody)) {
    throw new Error('YouTube gunluk ozel kucuk resim kotasi doldu; sonraki videolar icin islem durduruldu.');
  }
  if (!after || after === before) throw new Error('Studio onizlemesi degismedi; kapak yuklemesi dogrulanamadi.');

  const save = page.locator('#save-button, ytcp-button#save-button, button:has-text("Kaydet"), button:has-text("Save")').first();
  await save.waitFor({ state: 'visible', timeout: 15000 });
  if (await save.isDisabled().catch(() => false)) {
    // Dugme neden disabled? Kota/bekleyen hata kontrolu.
    const disabledBody = await page.locator('body').innerText().catch(() => '');
    if (/günlük.*küçük resim|günlük.*kapak|daily.*thumbnail.*limit|thumbnail.*limit reached|kota.*dol/i.test(disabledBody)) {
      throw new Error('YouTube gunluk ozel kucuk resim kotasi doldu; sonraki videolar icin islem durduruldu.');
    }
    throw new Error('Kaydet dugmesi etkin degil (muhtemelen yukleme hatasi veya kota).');
  }
  await save.click({ timeout: 10000 });

  // Save tıklandiktan sonra dugme once 'kaydediliyor' durumuna gecer, sonra tekrar
  // enabled olur ve "Degisiklikler kaydedildi" toast'i gorunur. En fazla 45sn bekle.
  let saveSucceeded = false;
  let lastToast = '';
  for (let tick = 0; tick < 45; tick++) {
    await sleep(1000);
    const toasts = await page.locator('ytcp-toast, #toast, tp-yt-paper-toast').allInnerTexts().catch(() => []);
    lastToast = toasts.join(' ').trim();
    const bodyNow = await page.locator('body').innerText().catch(() => '');
    if (/günlük.*küçük resim|günlük.*kapak|daily.*thumbnail.*limit|thumbnail.*limit reached|kota.*dol/i.test(bodyNow)) {
      throw new Error('YouTube gunluk ozel kucuk resim kotasi doldu; sonraki videolar icin islem durduruldu.');
    }
    if (/Changes saved|Değişiklikler kaydedildi|Degisiklikler kaydedildi|Saved/i.test(lastToast)) {
      saveSucceeded = true;
      break;
    }
    const hasErrorToast = toasts.some(t => /error|hata|başarısız|basarisiz|failed/i.test(t));
    if (hasErrorToast) throw new Error('YouTube Studio hata toast: ' + lastToast);
  }

  if (!saveSucceeded) {
    throw new Error('Kaydet dogrulanamadi: "Degisiklikler kaydedildi" toast\'i 45sn icinde gorunmedi. Son toast: ' + lastToast);
  }

  const result = { id: video.id, title: safeTitle, updated: true, originalBackup, cover, toast: lastToast.slice(0, 300) };
  return result;
}

(async () => {
  const state = loadState();
  const browser = await chromium.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-blink-features=AutomationControlled',
      '--disable-blink-features=IdleDetection',
      '--start-maximized',
    ],
  });
  // Gercek Chrome'mus gibi bir User-Agent kullan; headless ibaresini tamamen kaldir.
  // YouTube Studio "HeadlessChrome" gorurse "desteklenmeyen tarayici" ekrani veriyor.
  // Chromium major surumunu Playwright'in kurulu surumunden elde et (eger alamazsak 131'e fallback et).
  let chromiumMajor = 131;
  try {
    const browserVer = browser.version();
    const m = browserVer.match(/(\d+)\.(\d+)\.(\d+)\.(\d+)/);
    if (m) chromiumMajor = parseInt(m[1], 10);
    log('Chromium surumu: ' + browserVer + ' (major=' + chromiumMajor + ')');
  } catch (_) {}
  const ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/' + chromiumMajor + '.0.0.0 Safari/537.36';
  const context = await browser.newContext({
    storageState: state,
    viewport: { width: 1440, height: 1000 },
    locale: 'tr-TR',
    timezoneId: 'Europe/Istanbul',
    userAgent: ua,
    // webdriver flag'ini maskele, navigator.webdriver=false
    extraHTTPHeaders: {
      'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
    },
  });
  // navigator.webdriver'i maskele
  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
    // Chrome runtime var gibi goster
    if (!window.chrome) window.chrome = { runtime: {} };
    // Permissions API otomatik cikmasin
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
      parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters);
    // plugins / languages taklit
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['tr-TR', 'tr', 'en-US', 'en'] });
  });
  const page = await context.newPage();
  const results = { channelId: CHANNEL_ID, startedAt: new Date().toISOString(), dryRun: DRY_RUN, discovered: 0, updated: [], skipped: [], failed: [], stoppedReason: '' };
  try {
    const videos = await collectVideos(page);
    results.discovered = videos.length;
    fs.writeFileSync(path.join(OUT, 'video_inventory.json'), JSON.stringify(videos, null, 2));
    log('Bulunan Shorts: ' + videos.length);
    let candidates = videos;
    if (START_AFTER) {
      const pos = videos.findIndex(v => v.id === START_AFTER);
      if (pos < 0) throw new Error('START_AFTER video ID listede bulunamadi: ' + START_AFTER);
      candidates = videos.slice(pos + 1);
    }
    let processed = 0;
    for (let i = 0; i < candidates.length && processed < LIMIT; i++) {
      const video = candidates[i];
      try {
        log('Kapak hazirlaniyor: ' + video.id + ' | ' + video.title);
        const r = await applyOne(page, video, i);
        if (r.dryRun) {
          results.skipped.push({ ...r, reason: 'dry_run' });
          processed++;
          log('DRY RUN: ' + video.id);
        } else {
          results.updated.push(r);
          processed++;
          log('KAPAK KAYDEDILDI: ' + video.id);
        }
      } catch (e) {
        const item = { id: video.id, title: video.title, reason: e.message };
        results.failed.push(item);
        log('HATA ' + video.id + ': ' + e.message);
        if (/gunluk.*kucuk resim|gunluk.*kota|gunluk.*özel|oturumu gecersiz|ek kimlik/i.test(e.message)) {
          results.stoppedReason = e.message;
          break;
        }
      }
      await sleep(DELAY_MS);
    }
  } catch (e) {
    results.stoppedReason = e.message;
    log('IS AKISI DURDU: ' + e.message);
    process.exitCode = 1;
  } finally {
    results.finishedAt = new Date().toISOString();
    fs.writeFileSync(path.join(OUT, 'backfill_report.json'), JSON.stringify(results, null, 2));
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
    log('OZET: bulunan=' + results.discovered + ' kaydedilen=' + results.updated.length + ' atlanan=' + results.skipped.length + ' hata=' + results.failed.length);
  }
})();
