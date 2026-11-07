// Studio içerik listesi + video düzenleme sayfası incelemesi (salt okunur).
// Kullanım: STATE=<storage_state.json> node scripts/studio_inspect.cjs list
//           STATE=... node scripts/studio_inspect.cjs edit <videoId>
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const CH = 'UCBZVbwc7s7TeUCcOaN58oHQ';
const OUT = path.join(__dirname, '..', 'session_capture');
const STATE = process.env.STATE || path.join(OUT, 'storage_state.json');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const [mode, arg] = process.argv.slice(2);
  const browser = await chromium.launch({ headless: false, args: ['--disable-blink-features=AutomationControlled', '--no-first-run', '--lang=tr-TR'] });
  const context = await browser.newContext({
    storageState: STATE, viewport: { width: 1366, height: 900 }, locale: 'tr-TR', timezoneId: 'Europe/Istanbul',
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  });
  await context.addInitScript(() => { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); });
  const page = await context.newPage();
  try {
    if (mode === 'list') {
      await page.goto(`https://studio.youtube.com/channel/${CH}/videos/short?filter=%5B%5D&sort=%7B%22columnType%22%3A%22date%22%2C%22sortOrder%22%3A%22DESCENDING%22%7D`, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await sleep(8000);
      // sayfa boyutu 50
      try {
        await page.locator('ytcp-dropdown-trigger#page-size').click({ timeout: 5000 });
        await page.locator('tp-yt-paper-item:has-text("50")').first().click({ timeout: 5000 });
        await sleep(5000);
      } catch (_) {}
      const rows = await page.locator('ytcp-video-row').evaluateAll((els) => els.map((e) => {
        const a = e.querySelector('a#video-title, a.ytcp-video-row');
        const href = a ? a.getAttribute('href') : '';
        const id = (href || '').match(/video\/([^/]+)\//)?.[1] || '';
        const title = (e.querySelector('#video-title')?.textContent || '').trim();
        const vis = (e.querySelector('.tablecell-visibility, #visibility-cell, ytcp-video-visibility-cell')?.innerText || '').trim().replace(/\s+/g, ' ');
        const date = (e.querySelector('.tablecell-date, #date-cell, .date-cell')?.innerText || '').trim().replace(/\s+/g, ' ');
        const views = (e.querySelector('.tablecell-views, #views-cell')?.innerText || '').trim();
        return { id, title, vis, date, views };
      }));
      console.log(`URL: ${page.url()}`);
      console.log(JSON.stringify(rows, null, 1));
      fs.writeFileSync(path.join(OUT, 'studio_list.json'), JSON.stringify(rows, null, 1));
      await page.screenshot({ path: path.join(OUT, 'list.png'), fullPage: true });
    } else if (mode === 'edit') {
      await page.goto(`https://studio.youtube.com/video/${arg}/edit`, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await sleep(9000);
      console.log(`URL: ${page.url()}`);
      const info = await page.evaluate(() => {
        const q = (s) => document.querySelector(s);
        const ed = q('ytcp-video-thumbnail-editor, ytcp-thumbnail-editor, ytcp-video-custom-still-editor');
        const stills = [...document.querySelectorAll('ytcp-still-cell')].map((c) => ({
          cls: c.className, sel: c.getAttribute('aria-checked') || c.getAttribute('selected') || c.getAttribute('aria-pressed'),
          img: (c.querySelector('img')?.src || '').slice(0, 120), text: (c.innerText || '').trim().slice(0, 60),
        }));
        return {
          title: (q('#title-textarea #textbox')?.innerText || '').trim(),
          editorTag: ed ? ed.tagName : null,
          editorText: ed ? (ed.innerText || '').replace(/\s+/g, ' ').slice(0, 400) : null,
          stills,
          imgs: ed ? [...ed.querySelectorAll('img')].map((i) => i.src.slice(0, 140)) : [],
          visibility: (q('ytcp-video-metadata-visibility, #visibility-select, ytcp-text-dropdown-trigger')?.innerText || '').trim().slice(0, 80),
        };
      });
      console.log(JSON.stringify(info, null, 1));
      const ed = page.locator('ytcp-video-thumbnail-editor, ytcp-thumbnail-editor, ytcp-video-custom-still-editor').first();
      if (await ed.count()) { await ed.scrollIntoViewIfNeeded().catch(() => {}); await sleep(1000); }
      await page.screenshot({ path: path.join(OUT, `edit_${arg}.png`), fullPage: true });
    }
  } catch (e) {
    console.log('HATA: ' + e.message.slice(0, 300));
    await page.screenshot({ path: path.join(OUT, 'error.png') }).catch(() => {});
  } finally {
    await browser.close();
  }
})();
