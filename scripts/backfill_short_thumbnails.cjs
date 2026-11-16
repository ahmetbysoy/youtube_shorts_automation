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
const DELAY_MS = Math.max(5000, Number(process.env.DELAY_MS || 12000));
const BASE = process.cwd();
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = m => console.log('[' + new Date().toISOString() + '] ' + m);

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

async function makeCover(title, outPath) {
  const prompt = encodeURIComponent(buildPrompt(title));
  const seed = Math.floor(Math.random() * 1e9);
  const url = 'https://image.pollinations.ai/prompt/' + prompt +
    '?width=1080&height=1920&nologo=true&model=flux&seed=' + seed;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const response = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' }, signal: AbortSignal.timeout(90000) });
      if (!response.ok) throw new Error('image endpoint HTTP ' + response.status);
      const bytes = Buffer.from(await response.arrayBuffer());
      const type = response.headers.get('content-type') || '';
      if (!type.includes('image') || bytes.length < 20000) throw new Error('invalid image response (' + type + ', ' + bytes.length + ' bytes)');
      fs.writeFileSync(outPath, bytes);
      return;
    } catch (e) {
      log('AI kapak denemesi ' + attempt + '/3 basarisiz: ' + e.message);
      if (attempt < 3) await sleep(attempt * 7000);
    }
  }
  throw new Error('AI kapak olusturulamadi; bu video atlandi.');
}

async function collectVideos(page) {
  const url = 'https://studio.youtube.com/channel/' + CHANNEL_ID +
    '/videos/short?filter=%5B%5D&sort=%7B%22columnType%22%3A%22date%22%2C%22sortOrder%22%3A%22DESCENDING%22%7D';
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await sleep(7000);
  if (/accounts\.google\.com|ServiceLogin/i.test(page.url())) throw new Error('Studio oturumu gecersiz.');
  const pageSize = page.locator('ytcp-dropdown-trigger#page-size').first();
  if (await pageSize.isVisible().catch(() => false)) {
    await pageSize.click().catch(() => {});
    await page.locator('tp-yt-paper-item:has-text("50")').first().click({ timeout: 3000 }).catch(() => {});
    await sleep(3500);
  }
  const all = new Map();
  for (let pageNo = 0; pageNo < 100; pageNo++) {
    const rows = await page.locator('ytcp-video-row').evaluateAll(els => els.map(e => {
      const a = e.querySelector('a#video-title, a.ytcp-video-row');
      const href = a ? a.getAttribute('href') || '' : '';
      const id = (href.match(/video\/([^/]+)\//) || [])[1] || '';
      const title = (e.querySelector('#video-title')?.textContent || '').trim();
      const status = (e.querySelector('.tablecell-visibility, #visibility-cell, ytcp-video-visibility-cell')?.innerText || '').trim();
      const img = e.querySelector('img')?.currentSrc || e.querySelector('img')?.src || '';
      return { id, title, status, oldThumbnail: img };
    }).filter(x => x.id && x.title));
    for (const row of rows) all.set(row.id, row);
    const next = page.locator('ytcp-icon-button#navigate-after, #navigate-after').first();
    if (!(await next.isVisible().catch(() => false))) break;
    const disabled = await next.evaluate(el => el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true').catch(() => true);
    if (disabled) break;
    await next.click();
    await sleep(3000);
  }
  return [...all.values()];
}

async function backupOldThumb(page, video, index) {
  if (!video.oldThumbnail || !/^https?:/i.test(video.oldThumbnail)) return '';
  try {
    const res = await page.request.get(video.oldThumbnail, { timeout: 15000 });
    if (!res.ok()) return '';
    const dest = path.join(OUT, 'originals', video.id + '.img');
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(dest, await res.body());
    return dest;
  } catch (_) { return ''; }
}

async function applyOne(page, video, index) {
  const safeTitle = video.title.replace(/\s+/g, ' ').trim().slice(0, 100);
  const cover = path.join(OUT, 'generated', video.id + '.jpg');
  fs.mkdirSync(path.dirname(cover), { recursive: true });
  const originalBackup = await backupOldThumb(page, video, index);
  await makeCover(safeTitle, cover);

  await page.goto('https://studio.youtube.com/video/' + video.id + '/edit', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await sleep(6500);
  if (/accounts\.google\.com|ServiceLogin/i.test(page.url())) throw new Error('Studio oturumu gecersiz.');
  const body = await page.locator('body').innerText().catch(() => '');
  if (/Kimliğinizi doğrulayın|Verify it.s you/i.test(body)) throw new Error('Google ek kimlik dogrulamasi istiyor; guvenlik adimi atlanmadi.');
  const input = page.locator(
    'ytcp-thumbnail-uploader input[type="file"], ytcp-video-thumbnail-editor input[type="file"], ' +
    'ytcp-video-custom-still-editor input[type="file"], input#file-loader'
  ).first();
  if (!(await input.count())) throw new Error('Bu videonun Studio sayfasinda ozel kucuk resim yukleme alani yok.');
  if (DRY_RUN) return { id: video.id, title: safeTitle, dryRun: true, originalBackup, cover };

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
  if (await save.isDisabled().catch(() => false)) throw new Error('Kaydet dugmesi etkin degil.');
  await save.click({ timeout: 10000 });
  await sleep(5000);
  const toast = await page.locator('ytcp-toast, #toast').allInnerTexts().catch(() => []);
  const result = { id: video.id, title: safeTitle, updated: true, originalBackup, cover, toast: toast.join(' ').slice(0, 200) };
  return result;
}

(async () => {
  const state = loadState();
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'] });
  const context = await browser.newContext({ storageState: state, viewport: { width: 1440, height: 1000 }, locale: 'tr-TR', timezoneId: 'Europe/Istanbul' });
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
    let processed = 0;\n    for (let i = 0; i < candidates.length && processed < LIMIT; i++) {
      const video = candidates[i];
      try {
        log('Kapak hazirlaniyor: ' + video.id + ' | ' + video.title);
        const r = await applyOne(page, video, i);
        if (r.dryRun) results.skipped.push({ ...r, reason: 'dry_run' });
        else results.updated.push(r);
        log((r.updated ? 'KAPAK KAYDEDILDI: ' : 'DRY RUN: ') + video.id);
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
