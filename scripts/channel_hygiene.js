/**
 * FAZ 12.5 - KANAL HIJYENI OTOMASYONU (canli DOM ile dogrulanmis seciciler)
 * ======================================================================
 * 1) Kanal banneri   -> Studio > Ozellestirme (/editing/profile) > ytcp-banner-upload
 * 2) Kanal "Hakkinda" -> #description-textbox (contenteditable) > Yayinla
 * 3) Sabitlenmis yorum -> video izleme sayfasi > ytd-comment-simplebox-renderer > Sabitle
 *
 * Kullanim:
 *   node scripts/channel_hygiene.js --banner assets/banner.png \
 *        --about "Kanal aciklamasi..." --pin VIDEO_ID
 *
 * ONEMLI: hicbir adim yayinlama akisini BOZMAZ; hata olursa loglanir, script 0 ile biter.
 */
const fs = require('fs');
const path = require('path');

const { chromium } = require('playwright');

const BASE_DIR = path.resolve(__dirname, '..');
const STORAGE_STATE = path.join(BASE_DIR, 'storage_state.json');
const COOKIES_FILE = path.join(BASE_DIR, 'cookies.json');
const CHANNEL_ID = (process.env.YT_CHANNEL_ID || 'UCBZVbwc7s7TeUCcOaN58oHQ').trim();
const STUDIO = `https://studio.youtube.com/channel/${CHANNEL_ID}`;

const args = process.argv.slice(2);
function argValue(flag) {
  const i = args.indexOf(flag);
  return i >= 0 && args[i + 1] ? args[i + 1] : '';
}
const BANNER_PATH = argValue('--banner');
const ABOUT_TEXT = argValue('--about');
const PIN_VIDEO_ID = argValue('--pin');
const AFFILIATE_LINK = (process.env.AFFILIATE_URL_DEFAULT || '').trim() || 'https://www.youtube.com/@mentansiytas';

const log = (m) => console.log(m);
const ok = (m) => console.log(`[+] ${m}`);
const warn = (m) => console.log(`[!] ${m}`);
const err = (m) => console.log(`[-] ${m}`);

function buildContextOptions() {
  const opts = { viewport: { width: 1660, height: 950 }, locale: 'tr-TR', timezoneId: 'Europe/Istanbul' };
  if (fs.existsSync(STORAGE_STATE)) {
    opts.storageState = STORAGE_STATE;
  } else if (fs.existsSync(COOKIES_FILE)) {
    try {
      opts.storageState = { cookies: JSON.parse(fs.readFileSync(COOKIES_FILE, 'utf8')), origins: [] };
    } catch (_) {
      opts.storageState = { cookies: [], origins: [] };
    }
  }
  return opts;
}

/** Metin iceren butonu bul ve tikla (TR/EN). */
async function clickButtonByText(page, texts, timeout = 8000) {
  for (const t of texts) {
    const btn = page.locator(
      `button:has-text("${t}"), ytcp-button:has-text("${t}"), ` +
      `tp-yt-paper-item:has-text("${t}"), [aria-label="${t}"]`
    ).first();
    if (await btn.count() > 0) {
      const visible = await btn.isVisible().catch(() => false);
      if (visible) {
        await btn.click({ timeout }).catch(() => {});
        return true;
      }
    }
  }
  return false;
}

async function dumpCandidates(page, label) {
  const dump = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('input[type="file"], textarea, [contenteditable="true"], ytcp-button, button').forEach((el) => {
      const t = (el.getAttribute('aria-label') || el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 45);
      if (t) out.push(`${el.tagName}#${el.id} :: ${t}`);
    });
    return out.slice(0, 30);
  }).catch(() => []);
  warn(`[${label}] aday öğeler:`);
  dump.forEach((d) => console.log('    ' + d));
}

/** 1) Kanal banneri (ytcp-banner-upload) */
async function uploadBanner(page, bannerFile) {
  if (!bannerFile || !fs.existsSync(bannerFile)) {
    warn('Banner dosyası yok, banner adımı atlandı.');
    return false;
  }
  log('[*] Kanal banneri yükleniyor...');
  await page.goto(`${STUDIO}/editing/profile`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(7000);

  const bannerInput = page.locator('ytcp-banner-upload input#file-selector, ytcp-banner-upload input[type="file"]').first();
  if (await bannerInput.count() === 0) {
    await dumpCandidates(page, 'banner');
    warn('Banner dosya alanı bulunamadı.');
    return false;
  }

  await bannerInput.setInputFiles(bannerFile);
  await page.waitForTimeout(7000);
  const saved = await clickButtonByText(page, ['Yayınla', 'Kaydet', 'Publish', 'Save']);
  await page.waitForTimeout(5000);
  ok(saved
    ? 'Kanal banneri yüklendi ve "Yayınla" ile kaydedildi.'
    : 'Kanal banneri yüklendi (Yayınla butonu bulunamadı).');
  return true;
}

/** 2) Kanal "Hakkında" açıklaması (#description-textbox) */
async function updateAbout(page, aboutText) {
  if (!aboutText) {
    warn('Açıklama metni yok, About adımı atlandı.');
    return false;
  }
  log('[*] Kanal açıklaması (Hakkında) güncelleniyor...');
  await page.goto(`${STUDIO}/editing/profile`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(7000);

  const box = page.locator('#description-textbox, ytcp-social-suggestions-textbox#description-textbox').first();
  if (await box.count() === 0) {
    await dumpCandidates(page, 'about');
    warn('Açıklama alanı bulunamadı.');
    return false;
  }

  await box.click({ timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(600);
  await page.keyboard.press('Control+A').catch(() => {});
  await page.keyboard.press('Backspace').catch(() => {});
  await box.type(aboutText, { delay: 4 }).catch(async () => {
    await box.fill(aboutText).catch(() => {});
  });
  await page.waitForTimeout(1200);
  const saved = await clickButtonByText(page, ['Yayınla', 'Kaydet', 'Publish', 'Save']);
  await page.waitForTimeout(4000);
  ok(saved ? 'Kanal açıklaması güncellendi ve yayınlandı.' : 'Kanal açıklaması yazıldı (Yayınla bulunamadı).');
  return true;
}

/** 3) Sabitlenmiş yorum (video izleme sayfasindan) */
async function pinComment(page, videoId) {
  if (!videoId) {
    warn('Video ID yok, sabitlenmiş yorum adımı atlandı.');
    return false;
  }
  const commentText =
    `🔥 Bu konu hakkında ne düşünüyorsun? Yorumlara yaz! 👇\n🔗 ${AFFILIATE_LINK}`;

  log('[*] Sabitlenmiş yorum yazılıyor...');
  await page.goto(`https://www.youtube.com/watch?v=${videoId}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(8000);
  await page.evaluate(() => window.scrollTo(0, 500));
  await page.waitForTimeout(5000);

  // Daha once ayni yorum yazildiysa tekrar yazma -> sadece sabitle
  const existing = page.locator('ytd-comment-view-model').filter({ hasText: 'Bu konu hakkında ne düşünüyorsun' }).first();
  const existingCount = await existing.count();
  if (existingCount > 0) {
    log('[*] Yorum zaten mevcut, yeni yorum yazılmadan sabitlemeye geçiliyor...');
  } else {
  // "Yorum ekleyin..." alanina tikla -> gercek input acilir
  const placeholder = page.locator('ytd-comment-simplebox-renderer #placeholder-area').first();
  if (await placeholder.count() === 0) {
    await dumpCandidates(page, 'comment');
    warn('Yorum kutusu bulunamadı (yorumlar kapalı olabilir).');
    return false;
  }
  await placeholder.click({ timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(1500);

  const input = page.locator('ytd-comment-simplebox-renderer #input, ytd-comment-simplebox-renderer [contenteditable="true"]').first();
  if (await input.count() === 0) {
    warn('Yorum input alanı bulunamadı.');
    return false;
  }
  await input.click({ timeout: 5000 }).catch(() => {});
  await input.type(commentText, { delay: 4 }).catch(() => {});
  await page.waitForTimeout(1000);

  const submit = page.locator('#submit-button, ytd-comments-header-renderer #submit-button').first();
  if (await submit.count() === 0) {
    warn('Yorum gönderme butonu bulunamadı.');
    return false;
  }
  await submit.click({ timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(6000);
  }

  // Yeni yorumun menusunden "Sabitle"
  // (Canli DOM: ytd-comment-view-model > ytd-menu-renderer > button#button "İşlem menüsü")
  const menuBtn = page.locator(
    'ytd-comment-view-model ytd-menu-renderer button#button, ' +
    'ytd-comment-view-model button[aria-label="İşlem menüsü"], ' +
    'ytd-comment-view-model button[aria-label="Actions menu"], ' +
    'ytd-comment-renderer #menu-button'
  ).first();
  if (await menuBtn.count() === 0) {
    warn('Yorum yazıldı ancak menü düğmesi bulunamadı (sabitlenmedi).');
    return false;
  }
  await menuBtn.click({ timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(2000);

  const pinItem = page.locator(
    'ytd-menu-service-item-renderer:has-text("Sabitle"), ' +
    'ytd-menu-service-item-renderer:has-text("Pin"), ' +
    'tp-yt-paper-item:has-text("Sabitle"), tp-yt-paper-item:has-text("Pin")'
  ).first();
  if (await pinItem.count() === 0) {
    warn('Yorum yazıldı ancak "Sabitle" menü öğesi bulunamadı.');
    await page.keyboard.press('Escape').catch(() => {});
    return false;
  }
  await pinItem.click({ timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(4000);
  ok('Yorum yazıldı ve SABİTLENDİ.');
  return true;
}

(async () => {
  const results = {};
  let browser = null;
  try {
    const headless = process.env.HEADLESS === 'true' || !process.env.DISPLAY;
    browser = await chromium.launch({ headless, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
    const context = await browser.newContext(buildContextOptions());
    const page = await context.newPage();

    if (BANNER_PATH) {
      results.banner = await uploadBanner(page, BANNER_PATH).catch((e) => {
        warn(`Banner hatası: ${e.message}`);
        return false;
      });
    }
    if (ABOUT_TEXT) {
      results.about = await updateAbout(page, ABOUT_TEXT).catch((e) => {
        warn(`About hatası: ${e.message}`);
        return false;
      });
    }
    if (PIN_VIDEO_ID) {
      results.pin = await pinComment(page, PIN_VIDEO_ID).catch((e) => {
        warn(`Sabitlenmiş yorum hatası: ${e.message}`);
        return false;
      });
    }

    const summary = Object.entries(results).map(([k, v]) => `${k}=${v ? 'OK' : 'FAIL'}`).join(' | ');
    console.log(`[+] KANAL HIJYENI TAMAMLANDI: ${summary || 'tek adım yok'}`);
    fs.mkdirSync(path.join(BASE_DIR, 'logs'), { recursive: true });
    fs.writeFileSync(
      path.join(BASE_DIR, 'logs', 'channel_hygiene.json'),
      JSON.stringify({ timestamp: new Date().toISOString(), results }, null, 2)
    );
    await context.close();
  } catch (e) {
    err(`Kanal hijyeni çalıştırılamadı: ${e.message}`);
  } finally {
    if (browser) await browser.close().catch(() => {});
  }
  process.exit(0);
})();
