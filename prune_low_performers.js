#!/usr/bin/env node
/**
 * FAZ 10: OTONOM "ÖLÜ AĞIRLIK" TEMİZLİĞİ (AUTO-PRUNER)
 *
 * YouTube Studio'ya girer, kanalın videolarını tarar ve "ölü ağırlık" olanları
 * kalıcı olarak siler:
 *   - Video 1 saatten (PRUNE_MIN_AGE_MINUTES) eski olmalı
 *   - Video PRUNE_MIN_VIEWS (varsayılan 100) izlenmenin altında olmalı
 *
 * Yaş tespiti (3 katmanlı, en güvenilirden en muhafazakâra):
 *   1) Kanalın herkese açık RSS yayını  -> kesin ISO yayın zamanı
 *   2) prune_state.json ilk-görülme kaydı -> kesin gözlem tabanlı yaş
 *   3) Studio tarih sütunu -> göreli ("3 saat önce") veya mutlak ("3 Kas 2026")
 *      (mutlak tarihte en geç 23:59 varsayılır -> asla erken silme)
 *
 * Emniyet kilitleri:
 *   - PRUNE_MAX_DELETIONS   : tek çalıştırmada en fazla N silme (varsayılan 10)
 *   - PRUNE_MIN_REMAINING   : kanalda bırakılacak en az video sayısı (varsayılan 1)
 *   - PRUNE_DRY_RUN=true     : sadece raporlar, silmez
 *   - PRUNE_ONLY_VIDEO_IDS  : yalnızca belirtilen video ID'leri hedefler (test)
 *
 * Çıktılar:
 *   - prune_report.json  (tarama raporu, artifact + repo'ya yazılır)
 *   - prune_state.json   (video ID -> ilk görülme zamanı)
 */

const { chromium } = require('playwright');
const fs = require('fs');
const os = require('os');
const path = require('path');
require('dotenv').config();

const BASE_DIR = __dirname;
const COOKIES_PATH = path.join(BASE_DIR, 'cookies.json');
const STORAGE_STATE_PATH = path.join(BASE_DIR, 'storage_state.json');
const STATE_PATH = path.join(BASE_DIR, 'prune_state.json');
const REPORT_PATH = path.join(BASE_DIR, 'prune_report.json');
const LOG_DIR = path.join(BASE_DIR, 'logs');
const PROFILE_DIR = path.join(os.tmpdir(), 'yt_studio_pruner_profile');

const MIN_VIEWS = Number(process.env.PRUNE_MIN_VIEWS || 100);
const MIN_AGE_MINUTES = Number(process.env.PRUNE_MIN_AGE_MINUTES || 60);
const MAX_DELETIONS = Number(process.env.PRUNE_MAX_DELETIONS || 10);
const MIN_REMAINING = Number(process.env.PRUNE_MIN_REMAINING || 1);
const DRY_RUN = String(process.env.PRUNE_DRY_RUN || 'false').toLowerCase() === 'true';
// Güvenlik aşaması: ayrıntılı video bilgisi (başlık/ID) loga yazılmaz, yalnızca sayılar.
const QUIET_LOG = String(process.env.PRUNE_QUIET_LOG || 'false').toLowerCase() === 'true';
// Güvenlik aşaması: prune_state.json (ilk görülme kayıtları) diske yazılmaz.
const PERSIST_STATE = String(process.env.PRUNE_PERSIST_STATE || 'true').toLowerCase() !== 'false';
// Güvenlik kilidi: hiç satır taranamadıysa koşu BAŞARISIZ sayılır (sessiz 0/0 "success" olmasın).
const FAIL_ON_ZERO_SCAN = String(process.env.PRUNE_FAIL_ON_ZERO_SCAN || 'true').toLowerCase() !== 'false';
const ONLY_IDS = (process.env.PRUNE_ONLY_VIDEO_IDS || '')
    .split(',')
    .map(s => s.trim())
    .filter(Boolean);

const MONTHS_TR = {
    'oca': 0, 'şub': 1, 'sub': 1, 'mar': 2, 'nis': 3, 'may': 4, 'haz': 5,
    'tem': 6, 'ağu': 7, 'agu': 7, 'eyl': 8, 'eki': 9, 'kas': 10, 'ara': 11
};

function log(msg) {
    console.log(msg);
}

/** Video başlığı/ID içeren satırlar: QUIET_LOG açıkken yazılmaz. */
function logDetail(msg) {
    if (!QUIET_LOG) console.log(msg);
}

/** "1.234", "1,2 B", "3,4 Mn", "87" -> sayı */
function parseTrNumber(raw) {
    if (!raw) return 0;
    let s = String(raw).replace(/\u00a0/g, ' ').trim();
    let mult = 1;
    if (/\bMn\b|milyon/i.test(s)) { mult = 1000000; s = s.replace(/\bMn\b|milyon/gi, ''); }
    else if (/\bB\b|bin/i.test(s)) { mult = 1000; s = s.replace(/\bB\b|bin/gi, ''); }
    const m = s.match(/(\d[\d.,\s]*)/);
    if (!m) return 0;
    let num = m[1].replace(/\s/g, '');
    // Türkçe: binlik ayırıcı ".", ondalık ","
    if (num.includes(',') && num.includes('.')) {
        num = num.replace(/\./g, '').replace(',', '.');
    } else if (num.includes(',')) {
        const parts = num.split(',');
        num = parts.length === 2 && parts[1].length === 3 && num.indexOf(',') > 0 && parts[0].length <= 3
            ? num.replace(',', '')
            : num.replace(',', '.');
    } else if (num.includes('.')) {
        const parts = num.split('.');
        num = parts.length === 2 && parts[1].length === 3 && parts[0].length <= 3
            ? num.replace('.', '')
            : num.replace(/\./g, '');
    }
    const val = parseFloat(num);
    if (isNaN(val)) return 0;
    return Math.round(val * mult);
}

/**
 * Görüntülenme sütunu için SIKI ayrıştırma: sayı okunamıyorsa null döner
 * (0 DEĞİL) -> video korunur. "—", "", "Yükleniyor" gibi değerler null'dır.
 */
function parseViewsStrict(raw) {
    if (raw === null || raw === undefined) return null;
    const s = String(raw).replace(/\u00a0/g, ' ').trim();
    if (!/\d/.test(s)) return null;
    return parseTrNumber(s);
}

/** "3 saat önce", "45 dakika önce", "2 gün önce" -> dakika */
function parseRelativeMinutes(raw) {
    if (!raw) return null;
    const t = String(raw).toLowerCase();
    const m = t.match(/(\d+)\s*(saniye|dakika|saat|gün|hafta|ay|yıl)/);
    if (!m) return null;
    const n = parseInt(m[1], 10);
    switch (m[2]) {
        case 'saniye': return n / 60;
        case 'dakika': return n;
        case 'saat': return n * 60;
        case 'gün': return n * 1440;
        case 'hafta': return n * 10080;
        case 'ay': return n * 43200;
        case 'yıl': return n * 518400;
        default: return null;
    }
}

/** "3 Kas 2026" -> { ts, conservative:true } (günün 23:59'unda yayınlanmış varsayılır) */
function parseAbsoluteDateTr(raw) {
    if (!raw) return null;
    const t = String(raw).replace(/\s+/g, ' ').trim();
    const m = t.match(/(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]{3,10})\.?\s+(\d{4})/);
    if (!m) return null;
    const month = MONTHS_TR[m[2].toLowerCase().slice(0, 3)];
    if (month === undefined) return null;
    const day = parseInt(m[1], 10);
    const year = parseInt(m[3], 10);
    // Günün en geç anı (23:59:59) -> asla erken silme garantisi
    const ts = Date.UTC(year, month, day, 23, 59, 59);
    if (isNaN(ts)) return null;
    return { ts, conservative: true, raw: t };
}

/** Kanalın herkese açık RSS yayınından kesin yayın zamanlarını çeker */
async function fetchPublishedTimes(channelId) {
    const map = {};
    if (!channelId) return map;
    try {
        const res = await fetch(`https://www.youtube.com/feeds/videos.xml?channel_id=${channelId}`, {
            headers: { 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36' }
        });
        if (!res.ok) { log(`[!] RSS alınamadı (HTTP ${res.status}) - tarih çözümü RSS'e düşüyor.`); return map; }
        const xml = await res.text();
        const entries = xml.split('<entry>').slice(1);
        for (const e of entries) {
            const idM = e.match(/<yt:videoId>([^<]+)<\/yt:videoId>/);
            const pubM = e.match(/<published>([^<]+)<\/published>/);
            if (idM && pubM) {
                const ts = Date.parse(pubM[1]);
                if (!isNaN(ts)) map[idM[1]] = { ts, source: 'rss' };
            }
        }
        log(`[*] RSS yayın kaydı: ${Object.keys(map).length} video için kesin yayın zamanı alındı.`);
    } catch (err) {
        log(`[!] RSS hatası: ${err.message}`);
    }
    return map;
}

/**
 * Herkese açık izleme sayfasından kesin yayın zamanı + görüntülenme + gizlilik.
 * API anahtarı gerektirmez, ücretsizdir. RSS yalnızca son 15 videoyu kapsadığı
 * için geri kalan videoların yaşı buradan çözülür.
 */
const WATCH_META_CACHE = {};
async function fetchWatchPageMeta(videoId) {
    if (WATCH_META_CACHE[videoId]) return WATCH_META_CACHE[videoId];
    const out = { ts: null, views: null, isPrivate: null, isUnlisted: null, ok: false };
    try {
        const res = await fetch(`https://www.youtube.com/watch?v=${videoId}&hl=en`, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cookie': 'SOCS=CAI; CONSENT=YES+'
            }
        });
        if (res.ok) {
            const html = await res.text();
            const pick = (k) => (html.match(new RegExp('"' + k + '":"([^"]+)"')) || [])[1] || null;
            const pub = pick('publishDate') || pick('uploadDate');
            // Yalnızca SAAT bilgisi içeren değer kesindir ("2026-11-04T22:39:54-08:00").
            if (pub && /T\d{2}:\d{2}/.test(pub)) {
                const ts = Date.parse(pub);
                if (!isNaN(ts)) out.ts = ts;
            }
            const vc = pick('viewCount');
            if (vc && /^\d+$/.test(vc)) out.views = parseInt(vc, 10);
            const priv = html.match(/"isPrivate":(true|false)/);
            const unl = html.match(/"isUnlisted":(true|false)/);
            if (priv) out.isPrivate = priv[1] === 'true';
            if (unl) out.isUnlisted = unl[1] === 'true';
            out.ok = out.ts !== null;
        }
    } catch (_) {}
    WATCH_META_CACHE[videoId] = out;
    return out;
}

function loadState() {
    try {
        if (fs.existsSync(STATE_PATH)) {
            const s = JSON.parse(fs.readFileSync(STATE_PATH, 'utf8'));
            if (s && typeof s === 'object' && s.videos) return s;
        }
    } catch (_) {}
    return { videos: {} };
}

function saveState(state) {
    fs.writeFileSync(STATE_PATH, JSON.stringify(state, null, 2), 'utf8');
}

async function dismissModals(page) {
    const sels = [
        'ytcp-warm-welcome-dialog button:has-text("Devam")',
        'ytcp-warm-welcome-dialog button:has-text("Continue")',
        'ytcp-warm-welcome-dialog #dismiss-button',
        'ytcp-feature-discovery-callout #dismiss-button',
        'ytcp-button#dismiss-button'
    ];
    for (const sel of sels) {
        const loc = page.locator(sel).first();
        if (await loc.isVisible({ timeout: 800 }).catch(() => false)) {
            await loc.click({ force: true }).catch(() => {});
            await page.waitForTimeout(800);
        }
    }
    await page.keyboard.press('Escape').catch(() => {});
}

async function performGoogleLoginIfNeeded(page) {
    const email = (process.env.YT_EMAIL || '').trim();
    const password = (process.env.YT_PASSWORD || '').trim();
    if (!email || !password) return;
    if (!page.url().includes('accounts.google.com')) return;

    log('[*] YouTube Studio oturumu yok, Google giriş akışı tetikleniyor...');
    const tile = page.locator(`[data-identifier="${email}"], [data-email="${email}"]`).first();
    if (await tile.isVisible({ timeout: 5000 }).catch(() => false)) {
        await tile.click();
        await page.waitForTimeout(3000);
    }
    const emailInput = page.locator('input[type="email"]');
    if (await emailInput.isVisible({ timeout: 6000 }).catch(() => false)) {
        await emailInput.fill(email);
        await page.keyboard.press('Enter');
        await page.waitForTimeout(3500);
    }
    const pass = page.locator('input[type="password"]');
    if (await pass.isVisible({ timeout: 15000 }).catch(() => false)) {
        await pass.fill(password);
        await page.keyboard.press('Enter');
        await page.waitForTimeout(5000);
    }
    const deadline = Date.now() + 45000;
    while (Date.now() < deadline) {
        if (page.url().includes('studio.youtube.com')) return;
        await page.waitForTimeout(2500);
    }
}

async function collectRows(page) {
    return await page.evaluate(() => {
        const rows = Array.from(document.querySelectorAll('ytcp-video-row'));
        return rows.map(r => {
            const titleEl = r.querySelector('#video-title');
            const link = r.querySelector('a[href*="/video/"]');
            const href = link ? (link.getAttribute('href') || '') : '';
            const idM = href.match(/\/video\/([\w-]+)/);
            const cells = Array.from(r.querySelectorAll('[role="cell"]'));
            const pick = (cls) => {
                const c = cells.find(x => (x.className || '').toString().includes(cls));
                return c ? (c.innerText || '').replace(/\s+/g, ' ').trim() : '';
            };
            const dateCell = pick('tablecell-date');
            const descEl = r.querySelector('.tablecell-date .cell-description');
            const isDraft = Boolean(r.querySelector('ytcp-button.edit-draft-button:not([hidden])'));
            return {
                isDraft,
                videoId: idM ? idM[1] : '',
                title: titleEl ? (titleEl.textContent || '').trim() : '',
                visibility: pick('tablecell-visibility'),
                dateText: dateCell,
                statusText: descEl ? (descEl.textContent || '').trim() : '',
                viewsText: pick('tablecell-views'),
                commentsText: pick('tablecell-comments')
            };
        }).filter(v => v.videoId);
    });
}

/** Sayfa aralığı metni ("1–30 / 47") */
async function readRangeText(page) {
    return await page.evaluate(() => (document.body.innerText.match(/\d+\s*[–-]\s*\d+\s*\/\s*\d+/) || [])[0] || null).catch(() => null);
}

/** Listeyi İLK sayfadan son sayfaya kadar tarar (sayfalama). */
async function collectAllRows(page, listUrl, maxPages = 25) {
    await page.goto(listUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(6000);
    await dismissModals(page);
    await page.locator('ytcp-video-row').first().waitFor({ timeout: 30000 }).catch(() => {});
    const all = [];
    const seen = new Set();
    let pagesVisited = 0;
    for (let i = 0; i < maxPages; i++) {
        const rows = await collectRows(page);
        pagesVisited++;
        for (const r of rows) {
            if (!seen.has(r.videoId)) { seen.add(r.videoId); all.push(r); }
        }
        const range = await readRangeText(page);
        const next = page.locator('ytcp-icon-button#navigate-after');
        if (await next.count() === 0) break;
        const disabled = await next.getAttribute('aria-disabled').catch(() => null);
        if (disabled !== 'false') break;
        await next.click().catch(() => {});
        await page.waitForFunction(prev => {
            const m = (document.body.innerText.match(/\d+\s*[–-]\s*\d+\s*\/\s*\d+/) || [])[0] || null;
            return m && m !== prev;
        }, range, { timeout: 20000 }).catch(() => {});
        await page.waitForTimeout(1500);
    }
    return { rows: all, pagesVisited };
}

/** Bir video satırını tüm sayfalarda arar; bulunca o sayfada kalır. */
async function gotoVideoRow(page, listUrl, videoId, maxPages = 25) {
    await page.goto(listUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(5000);
    await dismissModals(page);
    await page.locator('ytcp-video-row').first().waitFor({ timeout: 30000 }).catch(() => {});
    for (let i = 0; i < maxPages; i++) {
        const cnt = await page.locator(`ytcp-video-row a[href*="/video/${videoId}"]`).count();
        if (cnt > 0) return true;
        const range = await readRangeText(page);
        const next = page.locator('ytcp-icon-button#navigate-after');
        if (await next.count() === 0) return false;
        const disabled = await next.getAttribute('aria-disabled').catch(() => null);
        if (disabled !== 'false') return false;
        await next.click().catch(() => {});
        await page.waitForFunction(prev => {
            const m = (document.body.innerText.match(/\d+\s*[–-]\s*\d+\s*\/\s*\d+/) || [])[0] || null;
            return m && m !== prev;
        }, range, { timeout: 20000 }).catch(() => {});
        await page.waitForTimeout(1500);
    }
    return false;
}

/** Yayında (PUBLIC) mı? Taslak / gizli / liste dışı / planlanmış videolar HEDEF DEĞİLDİR. */
function isPublicRow(video) {
    if (video.isDraft) return false;
    const v = (video.visibility || '').toLowerCase();
    return /herkese açık|public/.test(v);
}

/** Videonun yaşını (dakika) çözer: en güvenilir kaynaktan başlar */
function resolveAgeMinutes(video, publishedMap, state, now) {
    const rss = publishedMap[video.videoId];
    if (rss) {
        return { minutes: (now - rss.ts) / 60000, source: rss.source || 'rss', exact: true };
    }
    const st = state.videos[video.videoId];
    if (st && st.first_seen_at) {
        return { minutes: (now - Date.parse(st.first_seen_at)) / 60000, source: 'state', exact: true };
    }
    const rel = parseRelativeMinutes(video.dateText) || parseRelativeMinutes(video.statusText);
    if (rel !== null) {
        return { minutes: rel, source: 'studio-relative', exact: true };
    }
    const abs = parseAbsoluteDateTr(video.dateText);
    if (abs) {
        const minutes = (now - abs.ts) / 60000;
        // Aynı gün: 23:59 varsayımı NEGATİF yaş üretir -> yaş bilinmiyor say (korunur).
        if (minutes < 0) return { minutes: null, source: 'studio-date-same-day-unknown', exact: false };
        return { minutes, source: 'studio-date-conservative', exact: false };
    }
    return { minutes: null, source: 'unknown', exact: false };
}

async function deleteVideoById(page, videoId) {
    const row = page.locator('ytcp-video-row').filter({ has: page.locator(`a[href*="/video/${videoId}"]`) }).first();
    if (await row.count() === 0) return { ok: false, reason: 'satır bulunamadı (muhtemelen zaten silinmiş)' };

    await row.scrollIntoViewIfNeeded().catch(() => {});
    await row.hover().catch(() => {});
    await page.waitForTimeout(700);

    const menuBtn = row.locator(
        'ytcp-icon-button.open-menu-button, ytcp-icon-button#menu-button, ' +
        'ytcp-icon-button[aria-label="Seçenekler"], ytcp-icon-button[aria-label="Options"], ' +
        'ytcp-icon-button[aria-label*="Seçenek"], ytcp-icon-button[aria-label*="Diğer"], ' +
        'ytcp-icon-button[aria-label*="Option"], ytcp-icon-button[aria-label*="eylem"]'
    ).first();

    if (await menuBtn.count() === 0 || !(await menuBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
        return { ok: false, reason: 'menü butonu bulunamadı' };
    }
    await menuBtn.click({ force: true }).catch(() => {});
    await page.waitForTimeout(1500);

    const del = page.locator(
        'tp-yt-paper-item[test-id="delete"], ' +
        'tp-yt-paper-item:has-text("Tamamen sil"), ' +
        'tp-yt-paper-item:has-text("Sil"), ' +
        '[role="menuitem"]:has-text("Delete")'
    ).first();

    try {
        await del.waitFor({ state: 'visible', timeout: 8000 });
    } catch (_) {
        await page.keyboard.press('Escape').catch(() => {});
        return { ok: false, reason: 'menüde "Sil" kalemi bulunamadı' };
    }
    await del.click({ force: true }).catch(() => {});
    await page.waitForTimeout(1800);

    // Onay penceresi: "Bu video kalıcı olarak silinsin mi?" (ytcp-video-delete-dialog)
    const confirmBtn = page.locator(
        'ytcp-video-delete-dialog #confirm-button, ytcp-confirmation-dialog #confirm-button'
    ).first();
    try {
        await confirmBtn.waitFor({ state: 'visible', timeout: 10000 });
    } catch (_) {
        // Onay penceresi çıkmadıysa doğrudan silinmiş olabilir -> doğrulamaya geç
        return await verifyDeletion(page, videoId);
    }

    // "Bu videoyu silme işleminin kalıcı olduğunu ... kabul ediyorum." onay kutusu
    const ack = page.locator(
        'ytcp-confirmation-dialog #confirm-checkbox #checkbox, ' +
        'ytcp-video-delete-dialog #confirm-checkbox #checkbox, ' +
        'ytcp-confirmation-dialog [role="checkbox"], ' +
        'ytcp-video-delete-dialog [role="checkbox"]'
    ).first();
    if (await ack.count() > 0) {
        await ack.click({ force: true }).catch(() => {});
        await page.waitForTimeout(900);
        const checked = await ack.getAttribute('aria-checked').catch(() => null);
        if (checked !== 'true') {
            await ack.click({ force: true }).catch(() => {});
            await page.waitForTimeout(700);
        }
        log('[*] Kalıcı silme onay kutusu işaretlendi.');
    }

    await confirmBtn.click({ force: true }).catch(() => {});
    await page.waitForTimeout(2000);

    return await verifyDeletion(page, videoId);
}

/** Silme gerçekleşti mi? (satır listeden kayboldu mu?) */
async function verifyDeletion(page, videoId) {
    let goneFromPage = false;
    for (let i = 0; i < 15; i++) {
        await page.waitForTimeout(2000);
        const still = await page.locator(`ytcp-video-row a[href*="/video/${videoId}"]`).count();
        if (still === 0) { goneFromPage = true; break; }
    }
    if (!goneFromPage) return { ok: false, reason: 'onay sonrası video hâlâ listede (silinemedi)' };
    // İkinci doğrulama: listeyi yeniden yükle ve TÜM sayfalarda ara.
    const listUrl = page.url().split('?')[0];
    await page.waitForTimeout(8000);
    const found = await gotoVideoRow(page, listUrl, videoId).catch(() => null);
    if (found === true) return { ok: false, reason: 'yeniden yüklemede video hâlâ listede (silinmemiş)' };
    if (found === null) return { ok: false, reason: 'yeniden yükleme doğrulaması yapılamadı' };
    return { ok: true, verified: 'absent_after_full_rescan' };
}

async function pruneLowPerformers() {
    if (!fs.existsSync(COOKIES_PATH) && !fs.existsSync(STORAGE_STATE_PATH)) {
        console.error('[-] HATA: cookies.json / storage_state.json bulunamadı! Oturum süresi dolmuş olabilir.');
        process.exit(1);
    }
    fs.mkdirSync(LOG_DIR, { recursive: true });

    const state = loadState();
    const now = Date.now();

    const hasDisplay = Boolean(process.env.DISPLAY);
    const headlessMode = process.env.HEADLESS === 'true' ? true : !hasDisplay;
    const commonArgs = ['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-dev-shm-usage'];
    const commonContextOpts = {
        viewport: { width: 1366, height: 900 },
        locale: 'tr-TR',
        userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    };

    let browser = null;
    let context = null;
    if (fs.existsSync(STORAGE_STATE_PATH)) {
        browser = await chromium.launch({ headless: headlessMode, args: commonArgs });
        context = await browser.newContext({ ...commonContextOpts, storageState: STORAGE_STATE_PATH });
    } else {
        fs.mkdirSync(PROFILE_DIR, { recursive: true });
        context = await chromium.launchPersistentContext(PROFILE_DIR, { headless: headlessMode, ...commonContextOpts, args: commonArgs });
    }
    await context.addInitScript(() => {
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    });
    if (fs.existsSync(COOKIES_PATH)) {
        try {
            const cookies = JSON.parse(fs.readFileSync(COOKIES_PATH, 'utf8'));
            if (Array.isArray(cookies) && cookies.length > 0) await context.addCookies(cookies);
        } catch (_) {}
    }

    const page = context.pages()[0] || await context.newPage();
    const report = {
        started_at: new Date(now).toISOString(),
        channel_id: '',
        threshold_views: MIN_VIEWS,
        min_age_minutes: MIN_AGE_MINUTES,
        max_deletions: MAX_DELETIONS,
        dry_run: DRY_RUN,
        scanned: 0,
        targets: [],
        deleted: [],
        protected: [],
        errors: []
    };

    try {
        log('[*] Playwright Chromium başlatılıyor (Düşük Performanslı Video Temizleyici)...');
        log('[*] YouTube Studio İçerik sayfasına sızılıyor...');
        await page.goto('https://studio.youtube.com/', { waitUntil: 'domcontentloaded', timeout: 60000 });
        await page.waitForTimeout(6000);

        if (page.url().includes('accounts.google.com')) {
            await performGoogleLoginIfNeeded(page);
        }
        if (!page.url().includes('studio.youtube.com')) {
            throw new Error(`YouTube Studio'ya giriş yapılamadı (URL: ${page.url().slice(0, 120)})`);
        }
        await dismissModals(page);

        const chMatch = page.url().match(/\/channel\/(UC[\w-]+)/);
        const channelId = chMatch ? chMatch[1] : '';
        report.channel_id = channelId;
        log(`[*] Kanal: ${channelId || 'bilinmiyor'}`);

        const publishedMap = await fetchPublishedTimes(channelId);

        // Shorts sekmesi + uzun videolar sekmesi
        const tabs = channelId
            ? [`https://studio.youtube.com/channel/${channelId}/videos/short`, `https://studio.youtube.com/channel/${channelId}/videos/upload`]
            : ['https://studio.youtube.com/channel/UCBZVbwc7s7TeUCcOaN58oHQ/videos/short'];

        const seen = new Set();
        let deletedCount = 0;
        let scannedTotal = 0;

        let pagesTotal = 0;
        for (const url of tabs) {
            const { rows: pageRows, pagesVisited } = await collectAllRows(page, url);
            pagesTotal += pagesVisited;
            const rows = pageRows.filter(r => {
                if (seen.has(r.videoId)) return false;
                seen.add(r.videoId);
                return true;
            });
            scannedTotal += rows.length;
            report.scanned = scannedTotal;
            log(`[*] ${url.includes('/short') ? 'Shorts' : 'Uzun video'} sekmesi: ${rows.length} satır tarandı (${pagesVisited} sayfa).`);
            log(`[*] Toplam ${scannedTotal} video taranıyor...`);

            // RSS'te olmayan videolar için izleme sayfasından kesin yayın zamanı
            for (const video of rows) {
                if (publishedMap[video.videoId]) continue;
                const meta = await fetchWatchPageMeta(video.videoId);
                if (meta.ts !== null) publishedMap[video.videoId] = { ts: meta.ts, source: 'watch-page' };
                await new Promise(r => setTimeout(r, 300));
            }

            for (const video of rows) {
                const title = video.title || 'Bilinmeyen Başlık';
                const studioViews = parseViewsStrict(video.viewsText);
                const meta = WATCH_META_CACHE[video.videoId] || {};
                const watchViews = typeof meta.views === 'number' ? meta.views : null;
                // İki kaynaktan BÜYÜK olan görüntülenme esas alınır (asla erken silme).
                const views = studioViews === null && watchViews === null
                    ? null
                    : Math.max(studioViews === null ? -1 : studioViews, watchViews === null ? -1 : watchViews);
                const age = resolveAgeMinutes(video, publishedMap, state, now);
                const ageText = age.minutes === null ? 'bilinmiyor' : `${Math.round(age.minutes)} dk (${age.source})`;
                const base = `| Görüntüleme: ${views === null ? 'okunamadı' : views} | Yaş: ${ageText} | Durum: ${video.statusText || video.dateText}`;

                // İlk görülme kaydını tut
                if (!state.videos[video.videoId]) {
                    state.videos[video.videoId] = {
                        first_seen_at: new Date(now).toISOString(),
                        title,
                        views_at_first_seen: views
                    };
                }

                if (ONLY_IDS.length && !ONLY_IDS.includes(video.videoId)) {
                    logDetail(`[*] KORUNDU: '${title}' ${base} (seçili video listesinde değil)`);
                    report.protected.push({ videoId: video.videoId, title, views, reason: 'filtre' });
                    continue;
                }
                if (!isPublicRow(video) || meta.isPrivate === true || meta.isUnlisted === true) {
                    logDetail(`[*] KORUNDU: '${title}' ${base} | Yayında (PUBLIC) değil: ${video.isDraft ? 'taslak' : (video.visibility || 'bilinmiyor')}`);
                    report.protected.push({ videoId: video.videoId, title, views, reason: 'yayında-değil' });
                    continue;
                }
                if (views === null) {
                    logDetail(`[*] KORUNDU: '${title}' ${base} | Görüntülenme okunamadı`);
                    report.protected.push({ videoId: video.videoId, title, views, reason: 'görüntülenme-okunamadı' });
                    continue;
                }

                const tooYoung = age.minutes === null || age.minutes < MIN_AGE_MINUTES;
                const tooGood = views >= MIN_VIEWS;
                const wouldEmptyChannel = (scannedTotal - deletedCount) <= MIN_REMAINING;

                if (tooYoung) {
                    logDetail(`[*] KORUNDU: '${title}' ${base} | Henüz ${MIN_AGE_MINUTES} dk geçmedi`);
                    report.protected.push({ videoId: video.videoId, title, views, reason: age.minutes === null ? 'yaş-belirsiz' : 'çok-yeni', ageMinutes: age.minutes, ageSource: age.source });
                    continue;
                }
                if (tooGood) {
                    logDetail(`[*] KORUNDU: '${title}' ${base} | ${MIN_VIEWS}+ izlenme (performanslı)`);
                    report.protected.push({ videoId: video.videoId, title, views, reason: 'performanslı' });
                    continue;
                }
                if (deletedCount >= MAX_DELETIONS) {
                    logDetail(`[!] HEDEF TESPİT EDİLDİ ama atlandı: '${title}' ${base} | Çalıştırma silme limiti (${MAX_DELETIONS}) doldu`);
                    report.protected.push({ videoId: video.videoId, title, views, reason: 'limit' });
                    continue;
                }
                if (wouldEmptyChannel) {
                    logDetail(`[*] KORUNDU: '${title}' ${base} | Kanalda en az ${MIN_REMAINING} video bırakılmalı`);
                    report.protected.push({ videoId: video.videoId, title, views, reason: 'kanal-tabani' });
                    continue;
                }

                logDetail(`[!] HEDEF TESPİT EDİLDİ: '${title}' ${base} -> SİLİNİYOR!`);
                report.targets.push({ videoId: video.videoId, title, views, studioViews, watchViews, ageMinutes: Math.round(age.minutes), ageSource: age.source });

                if (DRY_RUN) {
                    logDetail(`[*] DRY-RUN: '${title}' silinmedi (PRUNE_DRY_RUN=true).`);
                    continue;
                }

                // Satır hangi sayfadaysa oraya git, sonra sil.
                const located = await gotoVideoRow(page, url, video.videoId);
                if (!located) {
                    logDetail(`[-] SİLEME BAŞARISIZ: '${title}' -> satır hiçbir sayfada bulunamadı`);
                    report.errors.push({ videoId: video.videoId, title, reason: 'satır bulunamadı' });
                    continue;
                }
                const res = await deleteVideoById(page, video.videoId);
                if (res.ok) {
                    logDetail(`[+] BAŞARILI: '${title}' kalıcı olarak silindi (${res.verified || 'doğrulandı'}).`);
                    report.deleted.push({ videoId: video.videoId, title, views, verified: res.verified || null });
                    deletedCount++;
                    delete state.videos[video.videoId];
                    await page.waitForTimeout(2500);
                } else {
                    logDetail(`[-] SİLEME BAŞARISIZ: '${title}' -> ${res.reason}`);
                    report.errors.push({ videoId: video.videoId, title, reason: res.reason });
                }
            }
        }
        report.pages_visited = pagesTotal;

        if (PERSIST_STATE) {
            saveState(state);
        } else {
            log('[*] Güvenlik aşaması: prune_state.json güncellenmedi (PRUNE_PERSIST_STATE=false).');
        }

        report.finished_at = new Date().toISOString();
        report.deleted_count = deletedCount;
        if (scannedTotal === 0 && FAIL_ON_ZERO_SCAN) {
            report.errors.push({ reason: 'zero-scan: Studio listesinden hiç satır okunamadı (oturum/DOM/yükleme sorunu olabilir)' });
        }
        fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2), 'utf8');
        log(`[*] Özet: taranan ${scannedTotal} | hedef ${report.targets.length} | silinen ${deletedCount} | korunan ${report.protected.length} | hata ${report.errors.length} | dry_run=${DRY_RUN}`);
        if (scannedTotal === 0 && FAIL_ON_ZERO_SCAN) {
            throw new Error('ZERO_SCAN: hiç video satırı taranamadı; koşu güvenlik gereği başarısız sayıldı.');
        }

        log('\n============================================================');
        log(` 🚀 TEMİZLİK TAMAMLANDI: ${deletedCount} adet düşük performanslı video imha edildi. 🚀`);
        log('============================================================\n');
        if (report.targets.length && !report.deleted.length) {
            log('[*] Not: Hedef tespit edildi ancak silme gerçekleşmedi (dry-run veya onay hatası).');
        }
    } finally {
        await context.close().catch(() => {});
        if (browser) await browser.close().catch(() => {});
    }
}

if (require.main === module) {
    pruneLowPerformers().catch(err => {
        console.error('[-] KRİTİK HATA:', err);
        try {
            fs.writeFileSync(REPORT_PATH, JSON.stringify({
                finished_at: new Date().toISOString(),
                error: String(err && err.message ? err.message : err)
            }, null, 2), 'utf8');
        } catch (_) {}
        process.exit(1);
    });
}

module.exports = {
    parseTrNumber,
    parseViewsStrict,
    isPublicRow,
    parseRelativeMinutes,
    parseAbsoluteDateTr,
    resolveAgeMinutes,
    pruneLowPerformers
};
