// Studio Shorts taslaklarını sandbox'tan tek tek yayınlar.
// Kapak: "Küçük resim → Videodan seç" ile videonun ilk karesi (kullanıcının elle yaptığı akış).
// Google "Kimliğinizi doğrulayın" modalı çıkarsa DOM ile ATLANMAZ: "Sonraki" tıklanır, telefon onayı beklenir.
// Kullanım:
//   node scripts/studio_draft_publish.cjs inspect           -> ilk taslağı aç, kare seçiciyi incele (yayınlamaz)
//   node scripts/studio_draft_publish.cjs publish [N]       -> en fazla N taslak yayınla (vars. 1); --dry = Yayınla'ya basma
// Ortam: STATE (storage_state yolu), IDENTITY_WAIT_SEC (vars. 300), YT_EMAIL/YT_PASSWORD (.env)
require('dotenv').config({ path: require('path').join(__dirname, '..', '.env') });
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const CH = 'UCBZVbwc7s7TeUCcOaN58oHQ';
const OUT = path.join(__dirname, '..', 'session_capture');
fs.mkdirSync(OUT, { recursive: true });
const STATE = process.env.STATE || path.join(OUT, 'storage_state.json');
const IDENTITY_WAIT_SEC = Number(process.env.IDENTITY_WAIT_SEC || 300);
const IDENTITY_MODAL_RE = /Kimliğinizi doğrulayın|Verify it'?s you|Kimliğinizi doğrulamamız/i;
const LIST_URL = `https://studio.youtube.com/channel/${CH}/videos/short?filter=%5B%7B%22name%22%3A%22VISIBILITY%22%2C%22value%22%3A%5B%22DRAFT%22%5D%7D%5D&sort=%7B%22columnType%22%3A%22date%22%2C%22sortOrder%22%3A%22DESCENDING%22%7D`;
const EMAIL = process.env.YT_EMAIL || '';
const PASS = process.env.YT_PASSWORD || '';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function redact(s) { let r = String(s); if (EMAIL) r = r.split(EMAIL).join('<EMAIL>'); if (PASS) r = r.split(PASS).join('<PASS>'); return r; }
const log = (m) => { const line = `[${new Date().toISOString()}] ${redact(m)}`; console.log(line); fs.appendFileSync(path.join(OUT, 'publish_status.log'), line + '\n'); };
const shot = (page, name) => page.screenshot({ path: path.join(OUT, `${name}.png`) }).catch(() => {});

// ---------------- Kimlik doğrulama (telefon onayı) ----------------
async function findIdentityModal(page) {
  for (const sel of ['tp-yt-paper-dialog', 'ytcp-dialog', 'ytcp-confirmation-dialog', '[role="dialog"]', '[role="alertdialog"]']) {
    const dialogs = page.locator(sel);
    const n = await dialogs.count().catch(() => 0);
    for (let i = 0; i < n; i++) {
      const d = dialogs.nth(i);
      if (!(await d.isVisible({ timeout: 300 }).catch(() => false))) continue;
      const txt = (await d.innerText().catch(() => '')) || '';
      if (IDENTITY_MODAL_RE.test(txt)) return d;
    }
  }
  return null;
}

async function waitForReauth(reauthPage, mainPage, startedAt) {
  let passwordAt = 0, retried = false, lastNote = '';
  while ((Date.now() - startedAt) / 1000 < IDENTITY_WAIT_SEC) {
    if (reauthPage.isClosed()) return { ok: true, how: 'popup_closed' };
    let url = ''; try { url = reauthPage.url(); } catch (_) { return { ok: true, how: 'popup_closed' }; }
    if (reauthPage !== mainPage && !mainPage.isClosed() && !(await findIdentityModal(mainPage))) return { ok: true, how: 'modal_cleared' };
    const body = ((await reauthPage.locator('body').innerText().catch(() => '')) || '').replace(/\s+/g, ' ');
    if (/Doğrulanamadı|Couldn'?t verify/i.test(body)) {
      if (!retried) { retried = true; log('[KIMLIK] "Doğrulanamadı" → bir kez Tekrar dene'); await reauthPage.locator('button:has-text("Tekrar dene"), button:has-text("Try again")').first().click({ timeout: 5000 }).catch(() => {}); passwordAt = 0; await sleep(4000); continue; }
      return { ok: false, how: 'denied_on_phone' };
    }
    const pwd = reauthPage.locator('input[type="password"]:visible').first();
    if (PASS && await pwd.isVisible({ timeout: 300 }).catch(() => false)) {
      if (passwordAt && Date.now() - passwordAt < 25000) { await sleep(3000); continue; }
      if (passwordAt) return { ok: false, how: 'password_rejected' };
      await pwd.fill(PASS).catch(() => {});
      await reauthPage.locator('#passwordNext, button:has-text("Sonraki"), button:has-text("İleri"), button:has-text("Next")').first().click({ timeout: 3000 }).catch(async () => { await reauthPage.keyboard.press('Enter').catch(() => {}); });
      passwordAt = Date.now(); log('[KIMLIK] Şifre girildi (1 kez)'); await sleep(5000); continue;
    }
    if (EMAIL) {
      const acct = reauthPage.locator(`div[data-identifier="${EMAIL}"], li:has-text("${EMAIL}")`).first();
      if (await acct.isVisible({ timeout: 300 }).catch(() => false)) { await acct.click().catch(() => {}); await sleep(3000); continue; }
    }
    const m = body.match(/telefonunuzdaki\s+(\d{1,3})\s+sayısına|tap\s+(\d{1,3})\s+on your phone|(\d{1,3})\s+sayısına dokun/i);
    const note = m ? `TELEFONDA "Evet" + ${m[1] || m[2] || m[3]} sayısına dokun` : /bildirim|notification|Check your phone|telefonunuzu kontrol/i.test(body) ? 'TELEFON bildirimini onayla' : '';
    if (note && note !== lastNote) { lastNote = note; log(`[KIMLIK] >>> ${note} (en fazla ${IDENTITY_WAIT_SEC}s) <<<`); await shot(reauthPage, 'identity_prompt'); }
    if (/Doğrulama kodu|verification code|Kodu girin|Enter the code/i.test(body) && !/bildirim/i.test(body)) { log('[KIMLIK] Kod istiyor: ' + body.slice(0, 200)); return { ok: false, how: 'code_required' }; }
    await sleep(3000);
  }
  return { ok: false, how: 'timeout' };
}

async function handleIdentityModal(page, context, attempt = 1) {
  const modal = await findIdentityModal(page);
  if (!modal) return false;
  if (attempt > 2) throw new Error('IDENTITY: modal 2 denemeden sonra hâlâ açık');
  log('[KIMLIK] "Kimliğinizi doğrulayın" modalı → Sonraki (DOM atlama yok)');
  await shot(page, 'identity_modal');
  const startedAt = Date.now();
  const popupPromise = context.waitForEvent('page', { timeout: 15000 }).catch(() => null);
  const nextBtn = modal.locator('button:has-text("Sonraki"), button:has-text("Next"), ytcp-button:has-text("Sonraki"), ytcp-button:has-text("Next")').first();
  await nextBtn.click({ timeout: 5000 }).catch((e) => log('Sonraki tıklama notu: ' + e.message.slice(0, 80)));
  const popup = await popupPromise;
  let reauthPage = popup || page;
  await sleep(3000);
  if (!popup && page.isClosed()) {
    const alive = context.pages().filter((p) => !p.isClosed());
    if (!alive.length) throw new Error('IDENTITY: sayfa kapandı, popup yok');
    reauthPage = alive[alive.length - 1];
  }
  let u = ''; try { u = reauthPage.url(); } catch (_) {}
  log(`[KIMLIK] Doğrulama sayfası: ${popup ? 'popup' : 'aynı sekme'} → ${u.split('?')[0]}`);
  await shot(reauthPage, 'identity_page');
  const result = await waitForReauth(reauthPage, page, startedAt);
  if (!result.ok) { await shot(reauthPage, 'identity_fail'); throw new Error(`IDENTITY: telefon onayı tamamlanmadı (${result.how})`); }
  log(`[KIMLIK] Doğrulama tamamlandı (${result.how}, ${Math.round((Date.now() - startedAt) / 1000)}s)`);
  await sleep(3000);
  fs.writeFileSync(STATE, JSON.stringify(await context.storageState(), null, 2));
  if (await findIdentityModal(page)) return handleIdentityModal(page, context, attempt + 1);
  return true;
}

// ---------------- Studio akışı ----------------
async function openFirstDraft(page, context) {
  await page.goto(LIST_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await sleep(4000);
  if (await handleIdentityModal(page, context)) { await page.goto(LIST_URL, { waitUntil: 'domcontentloaded', timeout: 60000 }); await sleep(4000); }
  await page.locator('ytcp-video-row').first().waitFor({ state: 'visible', timeout: 45000 }).catch(() => {});
  await sleep(2000);
  // Başlıksız ("final short") taslaklar atlanır: ilk uygun satır seçilir
  const rows = page.locator('ytcp-video-row');
  const rc = await rows.count();
  let row = null, title = '';
  for (let i = 0; i < rc; i++) {
    const t = (await rows.nth(i).locator('#video-title').innerText().catch(() => '')).trim();
    if (!/^final short$/i.test(t)) { row = rows.nth(i); title = t; break; }
  }
  if (!row) return null;
  await row.scrollIntoViewIfNeeded().catch(() => {});
  await row.hover().catch(() => {});
  await row.locator('ytcp-button:has-text("Taslağı düzenle"), ytcp-button:has-text("Edit draft")').first().click({ timeout: 15000 });
  await sleep(5000);
  if (await handleIdentityModal(page, context)) {
    await sleep(2000);
    if (!(await page.locator('ytcp-uploads-dialog #next-button').isVisible().catch(() => false))) {
      await page.goto(LIST_URL, { waitUntil: 'domcontentloaded', timeout: 60000 }); await sleep(7000);
      await page.locator('ytcp-video-row').filter({ hasText: title }).first().locator('ytcp-button:has-text("Taslağı düzenle"), ytcp-button:has-text("Edit draft")').first().click({ timeout: 15000 });
      await sleep(5000);
    }
  }
  await page.locator('ytcp-uploads-dialog #next-button').waitFor({ state: 'visible', timeout: 30000 });
  await sleep(3000);
  return title;
}

async function pickFrameFromVideo(page, tag, coverPath) {
  const dlg = page.locator('ytcp-uploads-dialog');
  const btn = dlg.locator('ytcp-video-thumbnail-editor, ytcp-thumbnail-editor').locator('text=/Videodan seç|Select from video/').first();
  await btn.scrollIntoViewIfNeeded().catch(() => {});
  if (!(await btn.isVisible({ timeout: 8000 }).catch(() => false))) { await shot(page, `${tag}_no_picker`); return { ok: false, reason: 'picker_button_missing' }; }
  await btn.click({ timeout: 10000 });
  const picker = page.locator('tp-yt-paper-dialog:visible').filter({ hasText: /Videonuzdan bir kare seçin|Select a frame/ }).last();
  await picker.waitFor({ state: 'visible', timeout: 20000 });
  // Adaylar: "Otomatik olarak oluşturulmuş küçük resim N" düğmeleri
  const cands = picker.locator('button[aria-label*="küçük resim"], button[aria-label*="thumbnail"], [role="radio"], [role="option"]');
  const deadline = Date.now() + 30000;
  let n = 0;
  while (Date.now() < deadline) { n = await cands.count().catch(() => 0); if (n > 0) break; await sleep(1000); }
  await shot(page, `${tag}_picker`);
  if (!n) { await picker.locator('ytcp-button:has-text("İptal"), button:has-text("İptal")').first().click().catch(() => {}); return { ok: false, reason: 'candidate_missing' }; }
  // Aday görsellerini indir ve seç (kapak varsa eşleştir, yoksa kalite puanı)
  const srcs = await cands.evaluateAll((els) => els.map((e) => { const i = e.querySelector('img'); return i ? (i.currentSrc || i.src || '') : (getComputedStyle(e).backgroundImage.match(/url\("?(.*?)"?\)/) || [])[1] || ''; }));
  const files = [];
  for (let i = 0; i < srcs.length; i++) {
    try {
      if (!srcs[i]) { files.push(''); continue; }
      let buf;
      if (srcs[i].startsWith('data:')) buf = Buffer.from(srcs[i].split(',')[1] || '', 'base64');
      else { const resp = await page.request.get(srcs[i], { timeout: 15000 }); buf = Buffer.from(await resp.body()); }
      const f = path.join(OUT, `${tag}_cand_${i}.jpg`); fs.writeFileSync(f, buf); files.push(f);
    } catch (_) { files.push(''); }
  }
  let idx = 0, how = 'varsayılan #1';
  const PICK_MODE = (process.env.PICK_MODE || 'first').toLowerCase(); // first | quality
  if (PICK_MODE === 'first') how = 'kullanıcı kararı: her zaman 1. aday';
  else if (files.some(Boolean)) {
    const useCover = coverPath && fs.existsSync(coverPath);
    const py = require('child_process').spawnSync('python3', [path.join(__dirname, 'pick_matching_still.py'), useCover ? coverPath : '-', ...files], { encoding: 'utf8' });
    try {
      const best = JSON.parse((py.stdout || '').trim().split('\n').pop() || '{}');
      if (typeof best.index === 'number') {
        if (useCover && best.matched === false) { how = `kapak eşleşmedi (fark ${best.distance}) → kalite puanı`; const py2 = require('child_process').spawnSync('python3', [path.join(__dirname, 'pick_matching_still.py'), '-', ...files], { encoding: 'utf8' }); const b2 = JSON.parse((py2.stdout || '').trim().split('\n').pop() || '{}'); if (typeof b2.index === 'number') idx = b2.index; }
        else { idx = best.index; how = useCover ? `kapak eşleşti (fark ${best.distance})` : `kalite puanı ${best.score}`; }
      }
    } catch (_) {}
  }
  const cell = cands.nth(idx);
  const stillCell = picker.locator('ytcp-still-cell').nth(idx);
  const isSel = async () => (await cell.getAttribute('aria-selected').catch(() => null)) === 'true';
  if (!(await isSel())) { await cell.click({ timeout: 10000 }); await sleep(1000); }
  if (!(await isSel()) && await stillCell.count()) { await stillCell.click({ timeout: 10000, force: true }); await sleep(1000); }
  if (!(await isSel())) { await cell.locator('img').first().click({ timeout: 5000, force: true }).catch(() => {}); await sleep(1000); }
  const selected = await isSel();
  const done = picker.locator('ytcp-button:has-text("Bitti"), button:has-text("Bitti"), ytcp-button:has-text("Done")').first();
  const enabled = await done.evaluate((b) => !(b.hasAttribute('disabled') || b.getAttribute('aria-disabled') === 'true')).catch(() => true);
  await shot(page, `${tag}_picker_selected`);
  log(`[KAPAK] aday #${idx + 1} aria-selected=${selected}, Bitti aktif=${enabled}`);
  if (!enabled) {
    await picker.locator('ytcp-button:has-text("İptal"), button:has-text("İptal")').first().click().catch(() => {});
    await sleep(1500);
    if (selected) return { ok: true, info: { idx, n, how: how + '; zaten seçiliydi (değişiklik yok)' } };
    return { ok: false, reason: 'Bitti pasif (seçim alınmadı)' };
  }
  await done.click({ timeout: 10000 });
  await sleep(4000);
  await shot(page, `${tag}_after_pick`);
  return { ok: true, info: { idx, n, how } };
}

async function publishOne(page, context, dry, tag) {
  const title = await openFirstDraft(page, context);
  if (title === null) { log('Taslak kalmadı.'); return { none: true }; }
  log(`Taslak açıldı: "${title}"`);
  await shot(page, `${tag}_details`);
  if (/^final short$/i.test(title)) { log('ATLANDI: başlıksız ("final short") taslak yayınlanmaz; listede kalır.'); return { skipped: true, title }; }

  // Kapak: "Videodan seç" → 3 otomatik aday → (kapak varsa eşleşen, yoksa kalite puanı en yüksek) → Bitti
  let cover = 'yok';
  try {
    const pick = await pickFrameFromVideo(page, tag, process.env.COVER_PATH || '');
    cover = pick.ok ? `videodan-seç aday #${pick.info.idx + 1}/${pick.info.n} (${pick.info.how})` : `seçilemedi: ${pick.reason}`;
  } catch (e) { cover = 'hata: ' + e.message.slice(0, 100); await page.keyboard.press('Escape').catch(() => {}); }
  log(`[KAPAK] ${cover}`);

  // Çocuklara özel değil
  const dlg = page.locator('ytcp-uploads-dialog');
  const notForKids = dlg.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').first();
  await notForKids.waitFor({ state: 'attached', timeout: 30000 });
  await notForKids.scrollIntoViewIfNeeded().catch(() => {});
  await sleep(600);
  if ((await notForKids.getAttribute('aria-checked')) !== 'true') await notForKids.click({ force: true, timeout: 10000 });
  await sleep(800);
  log(`MFK: aria-checked=${await notForKids.getAttribute('aria-checked')}`);

  // İleri → Görünürlük
  let onVis = false;
  for (let i = 0; i < 5; i++) {
    await dlg.locator('#next-button').click({ timeout: 10000 });
    await sleep(1800);
    const pub = dlg.locator('tp-yt-paper-radio-button[name="PUBLIC"]').first();
    if (await pub.isVisible().catch(() => false)) { onVis = true; break; }
  }
  if (!onVis) { await shot(page, `${tag}_stuck`); throw new Error('Görünürlük sayfasına ulaşılamadı'); }
  const pub = dlg.locator('tp-yt-paper-radio-button[name="PUBLIC"]').first();
  await pub.click({ force: true, timeout: 10000 });
  await sleep(1200);
  log(`PUBLIC: aria-checked=${await pub.getAttribute('aria-checked')}`);
  const videoId = await dlg.evaluate((d) => { const a = d.querySelector('a.ytcp-video-info, ytcp-video-info a, a[href*="youtu"]'); const m = (a?.href || '').match(/(?:youtu\.be\/|shorts\/|v=)([\w-]{11})/); return m ? m[1] : (d.getAttribute('video-id') || ''); }).catch(() => '');
  await shot(page, `${tag}_visibility`);
  if (dry) { log(`DRY: yayınlanmadı (id=${videoId})`); return { dry: true, title, videoId }; }

  await dlg.locator('#done-button').click({ timeout: 10000 });
  await sleep(6000);
  const close = page.locator('ytcp-uploads-still-processing-dialog #close-button, ytcp-uploads-dialog #close-button, tp-yt-paper-dialog:visible #close-button').first();
  if (await close.isVisible({ timeout: 3000 }).catch(() => false)) await close.click({ timeout: 10000 }).catch(() => {});
  await sleep(2000);
  await shot(page, `${tag}_done`);
  fs.appendFileSync(path.join(OUT, 'publish_log.jsonl'), JSON.stringify({ at: new Date().toISOString(), title, videoId, cover }) + '\n');
  log(`YAYINLANDI (Studio onayı; canlı doğrulama ayrı): "${title}" id=${videoId || '?'}`);
  return { done: true, title, videoId };
}

(async () => {
  const [mode, nArg] = process.argv.slice(2);
  const dry = process.argv.includes('--dry');
  const n = Math.max(1, parseInt(nArg || '1', 10) || 1);
  const browser = await chromium.launch({ headless: false, args: ['--disable-blink-features=AutomationControlled', '--no-first-run', '--lang=tr-TR'] });
  const context = await browser.newContext({
    storageState: STATE, viewport: { width: 1366, height: 900 }, locale: 'tr-TR', timezoneId: 'Europe/Istanbul',
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  });
  await context.addInitScript(() => { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); });
  context.on('page', (p) => log('Yeni sayfa/popup: ' + p.url().slice(0, 100)));
  const page = await context.newPage();
  try {
    if (mode === 'inspect') {
      const title = await openFirstDraft(page, context);
      log(`Taslak: ${title}`);
      await shot(page, 'inspect_details');
      if (title === null) throw new Error('taslak satırı bulunamadı');
      const pick = await pickFrameFromVideo(page, 'inspect', '');
      log('Seçim: ' + JSON.stringify(pick));
      await sleep(2000);
      await shot(page, 'inspect_picker_final');
    } else if (mode === 'publish') {
      for (let i = 0; i < n; i++) {
        const r = await publishOne(page, context, dry, `pub_${Date.now()}`);
        if (!r.done) break;
        await sleep(4000);
      }
    }
    fs.writeFileSync(STATE, JSON.stringify(await context.storageState(), null, 2));
  } catch (e) {
    log('HATA: ' + e.message.slice(0, 300));
    await shot(page, 'publish_error');
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
