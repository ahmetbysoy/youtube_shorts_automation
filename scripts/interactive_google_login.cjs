// Etkileşimli Google/YouTube Studio girişi: oturum (storage_state + cookies + HAR) yakalar.
// Sır yazdırmaz. Komutlar: session_capture/cmd.txt dosyasına tek satır yazılır:
//   code:123456 | click:<görünen metin> | goto:<url> | type:<metin> | enter | save | quit
require('dotenv').config({ path: require('path').join(__dirname, '..', '.env') });
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const OUT = path.join(__dirname, '..', 'session_capture');
fs.mkdirSync(OUT, { recursive: true });
const CMD = path.join(OUT, 'cmd.txt');
const STATUS = path.join(OUT, 'status.log');
const SHOT = path.join(OUT, 'current.png');
const EMAIL = process.env.YT_EMAIL || '';
const PASS = process.env.YT_PASSWORD || '';
if (!EMAIL || !PASS) { console.error('YT_EMAIL/YT_PASSWORD yok'); process.exit(2); }

function redact(s) {
  if (!s) return s;
  let r = String(s);
  if (EMAIL) r = r.split(EMAIL).join('<EMAIL>');
  if (PASS) r = r.split(PASS).join('<PASS>');
  const local = EMAIL.split('@')[0];
  if (local && local.length > 3) r = r.split(local).join('<EMAIL_LOCAL>');
  return r;
}
function log(msg) {
  const line = `[${new Date().toISOString()}] ${redact(msg)}`;
  console.log(line);
  fs.appendFileSync(STATUS, line + '\n');
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch({
    headless: false,
    args: ['--disable-blink-features=AutomationControlled', '--no-first-run', '--no-default-browser-check', '--lang=tr-TR'],
  });
  const REUSE = process.env.REUSE_STORAGE_STATE || '';
  const START_URL = process.env.START_URL || '';
  const context = await browser.newContext({
    ...(REUSE && fs.existsSync(REUSE) ? { storageState: REUSE } : {}),
    viewport: { width: 1366, height: 860 },
    locale: 'tr-TR',
    timezoneId: 'Europe/Istanbul',
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    recordHar: { path: path.join(OUT, 'session.har'), content: 'omit' },
  });
  await context.addInitScript(() => { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); });
  let page = await context.newPage();
  context.on('page', (np) => { log('YENİ SAYFA/POPUP açıldı: ' + np.url().slice(0, 120)); });
  let saved = false;

  async function saveAll(tag) {
    const state = await context.storageState();
    fs.writeFileSync(path.join(OUT, 'storage_state.json'), JSON.stringify(state, null, 2));
    const cookies = await context.cookies();
    fs.writeFileSync(path.join(OUT, 'cookies.json'), JSON.stringify(cookies, null, 2));
    const yt = cookies.filter((c) => /youtube|google/.test(c.domain));
    const names = yt.map((c) => c.name);
    log(`SAVED(${tag}): cookies=${cookies.length} google/yt=${yt.length} SID=${names.includes('SID')} SAPISID=${names.includes('SAPISID')} LOGIN_INFO=${names.includes('LOGIN_INFO')}`);
    saved = true;
  }

  async function snapshot(note) {
    try {
      await page.screenshot({ path: SHOT, fullPage: false });
      const title = await page.title().catch(() => '');
      const body = await page.evaluate(() => document.body ? document.body.innerText.slice(0, 600) : '').catch(() => '');
      log(`${note || 'STATE'} url=${page.url()} title=${title}\n--- text ---\n${body.replace(/\s+/g, ' ').slice(0, 500)}`);
    } catch (e) { log('snapshot hata: ' + e.message); }
  }

  if (REUSE) {
    log('Mevcut oturum yeniden kullanılıyor (şifreli giriş atlanır)');
    await page.goto(START_URL || 'https://studio.youtube.com/', { waitUntil: 'domcontentloaded', timeout: 60000 }).catch((e) => log('goto hata: ' + e.message));
    await sleep(5000); await snapshot('ACILIS');
  } else try {
    await page.goto('https://accounts.google.com/ServiceLogin?service=youtube&continue=https%3A%2F%2Fstudio.youtube.com%2F&hl=tr', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await sleep(2000);
    const emailBox = page.locator('input[type="email"]');
    if (await emailBox.count()) {
      await emailBox.first().fill(EMAIL);
      await page.locator('#identifierNext, button:has-text("İleri"), button:has-text("Next")').first().click();
      log('E-posta girildi');
      await sleep(3000);
    }
    const passBox = page.locator('input[type="password"]');
    try {
      await passBox.first().waitFor({ state: 'visible', timeout: 20000 });
      await passBox.first().fill(PASS);
      await page.locator('#passwordNext, button:has-text("İleri"), button:has-text("Next")').first().click();
      log('Şifre girildi');
      await sleep(4000);
    } catch (e) { log('Şifre alanı görünmedi: ' + e.message); }
    await snapshot('GIRIS_SONRASI');
  } catch (e) { log('Giriş akışı hatası: ' + e.message); await snapshot('HATA'); }

  // Komut döngüsü
  let lastUrl = '';
  let studioSaved = false;
  for (let i = 0; i < 1800; i++) { // ~ 2.5 saat
    await sleep(5000);
    try {
      const url = page.url();
      if (url !== lastUrl) { lastUrl = url; await snapshot('URL_DEGISTI'); }
      if (!studioSaved && /studio\.youtube\.com\/(channel|$)/.test(url)) {
        await sleep(4000); await saveAll('studio_ilk'); studioSaved = true; await snapshot('STUDIO');
      }
      if (fs.existsSync(CMD)) {
        const cmd = fs.readFileSync(CMD, 'utf8').trim();
        fs.unlinkSync(CMD);
        log('CMD: ' + (cmd.startsWith('code:') ? 'code:<gizli>' : cmd));
        if (cmd.startsWith('code:')) {
          const code = cmd.slice(5).trim();
          const inp = page.locator('input[type="tel"], input[name="Pin"], input[name="idvPin"], input[name="totpPin"], input[type="text"]:visible').first();
          await inp.fill(code); await sleep(500); await page.keyboard.press('Enter');
        } else if (cmd.startsWith('click:')) {
          await page.getByText(cmd.slice(6).trim(), { exact: false }).first().click({ timeout: 10000 });
        } else if (cmd.startsWith('fclick:')) {
          // Tüm frame'lerde (iframe dahil) görünen metne tıkla
          const txt = cmd.slice(7).trim(); let done = false;
          for (const f of page.frames()) {
            const loc = f.getByText(txt, { exact: false }).first();
            if (await loc.count().catch(() => 0)) {
              try { await loc.click({ timeout: 8000 }); done = true; log(`fclick OK frame=${f.url().slice(0, 80)}`); break; } catch (e) { log('fclick deneme: ' + e.message.slice(0, 80)); }
            }
          }
          if (!done) log('fclick: metin hiçbir frame\'de tıklanamadı: ' + txt);
        } else if (cmd === 'pages') {
          const ps = context.pages();
          for (let k = 0; k < ps.length; k++) log(`PAGE[${k}] ${ps[k] === page ? '*' : ' '} ${ps[k].url().slice(0, 140)}`);
        } else if (cmd.startsWith('use:')) {
          const k = parseInt(cmd.slice(4).trim(), 10); const ps = context.pages();
          if (ps[k]) { page = ps[k]; await page.bringToFront().catch(() => {}); log(`Aktif sayfa -> [${k}] ${page.url().slice(0, 120)}`); } else log('use: sayfa yok');
        } else if (cmd === 'frames') {
          for (const f of page.frames()) { const t = await f.evaluate(() => document.body ? document.body.innerText.replace(/\s+/g, ' ').slice(0, 300) : '').catch(() => '?'); log(`FRAME ${f.url().slice(0, 100)} :: ${t}`); }
        } else if (cmd.startsWith('css:')) {
          await page.locator(cmd.slice(4).trim()).first().click({ timeout: 10000 });
        } else if (cmd.startsWith('role:')) {
          await page.getByRole('button', { name: cmd.slice(5).trim() }).first().click({ timeout: 10000 });
        } else if (cmd.startsWith('goto:')) {
          await page.goto(cmd.slice(5).trim(), { waitUntil: 'domcontentloaded', timeout: 60000 });
        } else if (cmd.startsWith('type:')) {
          await page.keyboard.type(cmd.slice(5));
        } else if (cmd === 'enter') {
          await page.keyboard.press('Enter');
        } else if (cmd === 'shot') {
          // sadece ekran
        } else if (cmd === 'save') {
          await saveAll('manuel');
        } else if (cmd === 'quit') {
          if (!saved) await saveAll('quit');
          break;
        }
        await sleep(3000); await snapshot('CMD_SONRASI');
      }
    } catch (e) { log('döngü hata: ' + e.message); }
  }
  await context.close(); // HAR flush
  await browser.close();
  log('KAPANDI');
})();
