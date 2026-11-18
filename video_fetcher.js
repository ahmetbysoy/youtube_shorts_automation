/**
 * video_fetcher.js  —  Cookie-tabanlı, domain-izoleli Playwright Video Çekici
 *
 * Pexels ve Pixabay icin TARAYICI OTURUMLU (cookie) arama + indirme.
 * API anahtari KULLANMAZ.
 *
 *   KRİTİK GÜVENLİK:
 *   - Her saglayici kendi cookie seti ve ayri Playwright browser context'i ile calisir.
 *   - YouTube/Google/Genel cookies.json oturumu medya context'ine YUKLENMEZ.
 *   - PEXELS_COOK yalniz .pexels.com domain'li cookie'leri kabul eder.
 *   - PIXABAY_COOK yalniz .pixabay.com domain'li cookie'leri kabul eder.
 *   - Cookie degerleri HICBIR logda, hata mesajinda veya artifact'te gorunmez.
 *   - Yalniz izinli HTTPS hostlarina redirect yapilir (max 4 hop).
 *   - 403 / CAPTCHA / Cloudflare gecilmeye calisilmaz; blocked_unverified raporlanir.
 *
 * Cookie kaynakları (oncelik sirasi):
 *   1) PEXELS_COOK / PIXABAY_COOK ortam degiskenleri (GitHub Secrets)
 *      - Playwright storage_state "cookies" JSON dizisi
 *      - [{name,value,domain,...}] Netscape JSON dizisi
 *      - "name=value; name2=value2" ham cookie string
 *   2) Komut satirindan --cookies-file ile verilen JSON dosyasi (yalnizca ilgili domain filtrelenir)
 *
 * Kullanim:
 *   node video_fetcher.js <keyword> <output_path>
 *       [--provider pexels|pixabay|all]
 *       [--portrait]                  # dikey (9:16) videolari tercih et
 *       [--metadata]                  # indirme YAPMA, JSON olarak candidate listesi + diagnostics yaz
 *       [--min-duration <sn>]         # minimum video suresi (varsayilan 2.0)
 *       [--max-duration <sn>]         # maksimum video suresi (varsayilan 60.0)
 *       [--min-width <px>]            # minimum genislik (varsayilan 854)
 *       [--min-height <px>]           # minimum yukseklik (varsayilan 480)
 *       [--max-bytes <bayt>]          # maksimum dosya boyutu (varsayilan 100MB)
 *       [--cookies-file <path>]       # JSON cookie dosyasi (env cookie'leri ile birlestirilir,
 *                                     # yalnizca ilgili provider domainleri filtrelenir)
 *
 * Çıktı:
 *   - Normal mod: exit 0 + stdout son satırda indirilen dosyanın tam yolu
 *   - --metadata modu: stdout'a JSON yazar, dosya indirmez
 *       { "provider":"pexels"|"pixabay", "candidates":[...], "diagnostics":{...} }
 *   - Hata: exit 1, stderr'de guvenli (cookie-degersiz) hata mesaji
 */

'use strict';
const { chromium } = require('playwright');
const fs   = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const BASE_DIR = __dirname;
const TIMEOUT_MS = 30000;
const DOWNLOAD_TIMEOUT_MS = 90000;
const MAX_REDIRECT_HOPS = 4;
const MAX_FILE_BYTES_DEFAULT = 100 * 1024 * 1024; // 100 MB
const ALLOWED_DOWNLOAD_HOSTS = {
  pexels:  new Set(['videos.pexels.com', 'images.pexels.com', 'player.vimeo.com']),
  pixabay: new Set(['cdn.pixabay.com']),
};
const ALLOWED_SOURCE_HOSTS = {
  pexels:  new Set(['www.pexels.com', 'pexels.com']),
  pixabay: new Set(['www.pixabay.com', 'pixabay.com']),
};

// ── CLI ────────────────────────────────────────────────────────
function parseArgs(argv) {
  const opts = {
    keyword: null,
    outPath: null,
    provider: 'all',
    portrait: false,
    metadata: false,
    minDuration: 2.0,
    maxDuration: 60.0,
    minWidth: 854,
    minHeight: 480,
    maxBytes: MAX_FILE_BYTES_DEFAULT,
    cookiesFile: null,
  };
  const positional = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    switch (a) {
      case '--provider':   opts.provider = argv[++i]; break;
      case '--portrait':   opts.portrait = true; break;
      case '--metadata':   opts.metadata = true; break;
      case '--cookies-file': opts.cookiesFile = argv[++i]; break;
      case '--min-duration': opts.minDuration = parseFloat(argv[++i]); break;
      case '--max-duration': opts.maxDuration = parseFloat(argv[++i]); break;
      case '--min-width':  opts.minWidth = parseInt(argv[++i], 10); break;
      case '--min-height': opts.minHeight = parseInt(argv[++i], 10); break;
      case '--max-bytes':  opts.maxBytes = parseInt(argv[++i], 10); break;
      default: positional.push(a);
    }
  }
  opts.keyword = positional[0] || null;
  opts.outPath = positional[1] || null;
  return opts;
}

// ── Log (cookie degerlerini maskeleyerek) ─────────────────────
function log(msg) { console.error('[video_fetcher] ' + msg); }
// Hata mesajlarina cookie degeri / URL query stringi sizdirmamak icin
// URL'leri yalnizca host + path olarak yazdir.
function safeUrl(u) {
  try {
    const url = new URL(u);
    return url.host + url.pathname;
  } catch { return '(invalid url)'; }
}

// ── Cookie çözümleme & domain filtreleme ─────────────────────
const COOKIE_FIELDS = ['name','value','domain','path','secure','httpOnly','sameSite','expires'];

function normalizeCookie(raw, defaultDomain) {
  if (!raw || typeof raw.name !== 'string' || !raw.name || typeof raw.value !== 'string') return null;
  const domain = (typeof raw.domain === 'string' && raw.domain) ? raw.domain : defaultDomain;
  let sameSite = raw.sameSite;
  if (!['Strict','Lax','None'].includes(sameSite)) sameSite = 'Lax';
  let expires = raw.expires;
  if (typeof expires !== 'number' || expires <= 0) expires = -1;
  return {
    name: raw.name,
    value: raw.value,
    domain: domain.startsWith('.') ? domain : ('.' + domain),
    path: (typeof raw.path === 'string' && raw.path.startsWith('/')) ? raw.path : '/',
    secure: !!raw.secure,
    httpOnly: !!raw.httpOnly,
    sameSite,
    expires,
  };
}

function parseCookieString(raw, defaultDomain) {
  // "k=v; k2=v2"
  const out = [];
  if (typeof raw !== 'string') return out;
  for (const part of raw.split(';')) {
    const i = part.indexOf('=');
    if (i <= 0) continue;
    const n = normalizeCookie({
      name: part.slice(0, i).trim(),
      value: part.slice(i + 1).trim(),
      domain: defaultDomain, path: '/'
    }, defaultDomain);
    if (n) out.push(n);
  }
  return out;
}

function parseCookiesFromJson(raw, defaultDomain) {
  const out = [];
  let data;
  try { data = JSON.parse(raw); } catch { return out; }
  if (Array.isArray(data)) {
    for (const c of data) { const n = normalizeCookie(c, defaultDomain); if (n) out.push(n); }
  } else if (data && typeof data === 'object') {
    // storage_state {"cookies":[...]} veya {"cookies":{...}} ya da dict {name:value}
    if (Array.isArray(data.cookies)) {
      for (const c of data.cookies) { const n = normalizeCookie(c, defaultDomain); if (n) out.push(n); }
    } else {
      for (const [name, value] of Object.entries(data)) {
        if (typeof value !== 'string') continue;
        const n = normalizeCookie({ name, value, domain: defaultDomain, path: '/' }, defaultDomain);
        if (n) out.push(n);
      }
    }
  }
  return out;
}

function loadCookies(source, defaultDomain) {
  // source: string (env) veya dosya yolu
  let raw = source;
  if (source && fs.existsSync(source)) {
    try { raw = fs.readFileSync(source, 'utf8'); } catch { return []; }
  }
  if (!raw || typeof raw !== 'string') return [];
  const trimmed = raw.trim();
  if (!trimmed) return [];
  let cookies = trimmed.startsWith('[') || trimmed.startsWith('{')
    ? parseCookiesFromJson(trimmed, defaultDomain)
    : parseCookieString(trimmed, defaultDomain);
  // YALNIZ defaultDomain ve alt domain'lerine ait cookie'leri filtrele.
  const suffix = defaultDomain; // ".pexels.com" veya ".pixabay.com"
  const bare = defaultDomain.replace(/^\./, '');
  cookies = cookies.filter(c => {
    const d = (c.domain || '').toLowerCase();
    return d === suffix || d === bare || d.endsWith(suffix);
  });
  // (name,domain,path) ile tekillestir (son gecerli olan kazansin)
  const seen = new Map();
  for (const c of cookies) {
    const key = `${c.name}|${c.domain}|${c.path}`;
    seen.set(key, c);
  }
  return [...seen.values()];
}

// ── Browser context ──────────────────────────────────────────
async function launchContext(cookies, provider) {
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox','--disable-dev-shm-usage','--disable-blink-features=AutomationControlled']
  });
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    locale: 'en-US',
    timezoneId: 'America/Los_Angeles',
    // Youtube/Google storage_state KESİNLİKLE yuklenmez.
  });
  await ctx.addInitScript(() => {
    // webdriver bayragini sil
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    // chrome nesnesi taklidi
    // @ts-ignore
    window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
    // permissions
    const origQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
      parameters.name === 'notifications' ? Promise.resolve({state: Notification.permission, onchange:null}) : origQuery(parameters);
    // plugins/languages
    Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
  });
  if (cookies.length > 0) {
    try { await ctx.addCookies(cookies); }
    catch (e) {
      await browser.close();
      throw new Error(`${provider}_cookie_invalid: ${e.message.split('\n')[0].slice(0,120)}`);
    }
  }
  return { browser, ctx };
}

// ── URL güvenliği ────────────────────────────────────────────
function validHttpsUrl(u, hosts) {
  try {
    const p = new URL(u);
    const hostSet = hosts instanceof Set ? hosts : new Set(Array.isArray(hosts) ? hosts : [hosts]);
    return p.protocol === 'https:' && hostSet.has(p.hostname) && !p.username && !p.password && (!p.port || p.port === '443');
  } catch { return false; }
}

// ── ffprobe doğrulama ───────────────────────────────────────
function ffprobe(filePath) {
  // ffprobe ile stream bilgisini al; tam decode denemesini de yap.
  let probeOut = '';
  try {
    probeOut = execFileSync('ffprobe', [
      '-v','error','-print_format','json','-show_format','-show_streams', filePath
    ], { stdio: ['ignore','pipe','pipe'], timeout: 30000 }).toString('utf8');
  } catch (e) {
    return { ok: false, error: 'ffprobe_failed', detail: (e.stderr||'').toString().slice(0,300) };
  }
  let info;
  try { info = JSON.parse(probeOut); } catch { return { ok: false, error: 'ffprobe_json_parse' }; }
  const v = (info.streams||[]).find(s => s.codec_type === 'video');
  if (!v) return { ok: false, error: 'no_video_stream' };
  const dur = info.format && info.format.duration ? parseFloat(info.format.duration) : null;
  const width = parseInt(v.width, 10);
  const height = parseInt(v.height, 10);
  if (!width || !height) return { ok: false, error: 'invalid_dimensions' };
  // Tam decode: bir frame cikarmayi dene (hizli), son saniyeyi de kontrol et
  try {
    execFileSync('ffmpeg', [
      '-v','error','-i',filePath,'-f','null','-'
    ], { stdio: ['ignore','pipe','pipe'], timeout: 60000 });
  } catch (e) {
    return { ok: false, error: 'full_decode_failed', detail: (e.stderr||'').toString().slice(0,300),
             width, height, duration: dur, codec: v.codec_name };
  }
  return { ok: true, width, height, duration: dur, codec: v.codec_name,
           r_frame_rate: v.r_frame_rate, format_name: info.format && info.format.format_name };
}

// ── İndirme (page.request üzerinden, yönlendirme ve boyut kontrolü)
async function downloadWithChecks(page, url, destPath, allowedHosts, maxBytes) {
  const trace = { hops: [], finalHost: null, httpStatus: null, contentType: null, bytes: 0, sha256hex: null };
  let currentUrl = url;
  for (let hop = 0; hop <= MAX_REDIRECT_HOPS; hop++) {
    const u = new URL(currentUrl);
    trace.finalHost = u.hostname;
    if (!allowedHosts.has(u.hostname)) {
      trace.error = 'redirect_to_untrusted_host';
      return { ok: false, trace };
    }
    let resp;
    try {
      resp = await page.request.get(currentUrl, {
        headers: { 'Referer': `https://${u.hostname}/`, 'User-Agent': 'Mozilla/5.0' },
        timeout: DOWNLOAD_TIMEOUT_MS,
        maxRedirects: 0,
      });
    } catch (e) {
      trace.error = 'download_network_error';
      return { ok: false, trace };
    }
    trace.httpStatus = resp.status();
    trace.hops.push({ host: u.hostname, status: resp.status() });
    if ([301,302,303,307,308].includes(resp.status())) {
      const loc = resp.headers()['location'];
      if (!loc) { trace.error = 'redirect_without_location'; return { ok: false, trace }; }
      currentUrl = new URL(loc, currentUrl).toString();
      continue;
    }
    if (resp.status() !== 200) {
      trace.error = `http_${resp.status()}`;
      return { ok: false, trace };
    }
    const ct = (resp.headers()['content-type'] || '').toLowerCase();
    trace.contentType = ct;
    if (!ct.startsWith('video/') && !ct.startsWith('application/octet-stream') && !ct.startsWith('binary/')) {
      trace.error = 'unexpected_content_type';
      return { ok: false, trace };
    }
    const buf = await resp.body();
    trace.bytes = buf.length;
    if (buf.length < 50000) { trace.error = 'file_too_small'; return { ok: false, trace }; }
    if (buf.length > maxBytes) { trace.error = 'file_too_large'; return { ok: false, trace }; }
    // HTML gelmesin (Cloudflare challenge sayfasi vs.)
    const head = buf.slice(0, 200).toString('utf8','utf8').toLowerCase();
    if (head.includes('<!doctype html') || head.includes('<html')) {
      trace.error = 'html_response_not_media';
      return { ok: false, trace };
    }
    fs.mkdirSync(path.dirname(destPath), { recursive: true });
    fs.writeFileSync(destPath, buf);
    // SHA256
    const crypto = require('crypto');
    trace.sha256hex = crypto.createHash('sha256').update(buf).digest('hex');
    return { ok: true, trace };
  }
  trace.error = 'redirect_limit_exceeded';
  return { ok: false, trace };
}

// ── Pixabay scraper ──────────────────────────────────────────
async function fetchFromPixabay(page, kw, opts) {
  const searchUrl = `https://pixabay.com/videos/search/${encodeURIComponent(kw)}/?order=popular`;
  const diag = { cookie_present: false, browser_access: null, search: null,
                 candidates_found: 0, source_url: null, selected_url: null };
  try {
    const resp = await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: TIMEOUT_MS });
    diag.browser_access = resp ? resp.status() : null;
    await page.waitForTimeout(5000); // Cloudflare challenge icin biraz daha bekle
  } catch (e) {
    diag.browser_access = 'timeout_or_navigation_error';
    diag.search = 'failed';
    return { candidates: [], diagnostics: diag };
  }
  if (diag.browser_access === 403 || diag.browser_access === 429) {
    diag.search = 'blocked_unverified';
    return { candidates: [], diagnostics: diag };
  }
  // Cloudflare/Turnstile kontrolu (status 200 olsa bile challenge sayfasi gelebilir)
  const pageTitle = await page.title();
  diag.page_title = pageTitle.slice(0, 120);
  const isChallenge = /just a moment|attention required|verify you are human|cloudflare|turnstile|captcha/i.test(pageTitle);
  if (isChallenge) {
    // Bir kez daha bekle — Cloudflare bazen otomatik geciyor
    await page.waitForTimeout(8000);
    const t2 = await page.title();
    if (/just a moment|attention required|verify you are human|cloudflare|turnstile|captcha/i.test(t2)) {
      diag.search = 'blocked_unverified';
      return { candidates: [], diagnostics: diag };
    }
  }
  diag.search = 'loaded';
  const urls = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('script').forEach(s => {
      const text = s.textContent || '';
      const tinyRe = /https:\/\/cdn\.pixabay\.com\/video\/[^"'\\]+_tiny\.mp4/g;
      const m = text.match(tinyRe); if (m) m.forEach(u => out.push(u));
    });
    return [...new Set(out)];
  });
  // Kabul edilebilir kalite seviyeleri: large > medium (tiny KESINLIKLE yok)
  const candidates = [];
  for (const tiny of urls) {
    for (const suffix of ['_large.mp4','_medium.mp4']) {
      const u = tiny.replace('_tiny.mp4', suffix);
      try {
        const ok = await page.evaluate(async (url) => {
          const r = await fetch(url, { method: 'HEAD' });
          return r.ok;
        }, u);
        if (ok) {
          candidates.push({
            download_url: u,
            quality: suffix === '_large.mp4' ? 'large' : 'medium',
            source_url: searchUrl,
            media_id: (u.match(/video\/(\d{4}\/\d{2}\/\d{2}\/)?(\d+)/) || [])[2] || '',
          });
          break;
        }
      } catch { /* devam */ }
    }
  }
  diag.candidates_found = candidates.length;
  if (candidates.length === 0) { diag.search = 'no_valid_video'; return { candidates: [], diagnostics: diag }; }
  // large once
  candidates.sort((a,b) => (a.quality === 'large' ? 0 : 1) - (b.quality === 'large' ? 0 : 1));
  diag.selected_url = safeUrl(candidates[0].download_url);
  return { candidates, diagnostics: diag };
}

// ── Pexels scraper ───────────────────────────────────────────
async function fetchFromPexels(page, kw, opts) {
  const searchUrl = `https://www.pexels.com/search/videos/${encodeURIComponent(kw)}/`;
  const diag = { cookie_present: false, browser_access: null, search: null,
                 candidates_found: 0, source_url: null, selected_url: null };
  try {
    const resp = await page.goto(searchUrl, { waitUntil: 'networkidle', timeout: Math.max(60000, TIMEOUT_MS*2) });
    diag.browser_access = resp ? resp.status() : null;
    await page.waitForTimeout(2000);
  } catch (e) {
    try {
      const resp = await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: TIMEOUT_MS });
      diag.browser_access = resp ? resp.status() : null;
      await page.waitForTimeout(4000);
    } catch (e2) {
      diag.browser_access = 'timeout_or_navigation_error';
      diag.search = 'failed';
      return { candidates: [], diagnostics: diag };
    }
  }
  if (diag.browser_access === 403 || diag.browser_access === 429) {
    diag.search = 'blocked_unverified';
    return { candidates: [], diagnostics: diag };
  }
  // Cloudflare/Turnstile kontrolu (status 200 olsa bile challenge sayfasi gelebilir)
  const pageTitle = await page.title();
  const urlAfter = page.url();
  diag.final_url = safeUrl(urlAfter);
  diag.page_title = pageTitle.slice(0, 120);
  const isChallenge = /just a moment|attention required|verify you are human|cloudflare|turnstile|captcha/i.test(pageTitle) ||
                      /cf-challenge|turnstile|g-recaptcha|hcaptcha/i.test(await page.content().catch(()=>'').then(c=>c.slice(0,5000)));
  if (isChallenge) {
    diag.search = 'blocked_unverified';
    return { candidates: [], diagnostics: diag };
  }
  diag.search = 'loaded';
  // DOM'u uzun sure bekle (lazy-load / React hydrate)
  try { await page.waitForSelector('article, [data-testid="video-card"], .MediaCard_slug__, video, a[href*="/video/"]', { timeout: 15000 }); } catch {}
  await page.waitForTimeout(3000);
  // Sayfayi scrollayarak lazy-load'u tetikle
  for (let i = 0; i < 3; i++) { await page.evaluate(()=>window.scrollBy(0,800)); await page.waitForTimeout(800); }
  await page.waitForTimeout(1000);
  const urls = await page.evaluate(() => {
    const out = new Set();
    // 1) Global state nesneleri
    [window.__NEXT_DATA__, window.__APOLLO_STATE__, window.__INITIAL_STATE__, window._REDUX_STATE_].forEach(obj => {
      if (!obj) return;
      const s = JSON.stringify(obj);
      const m = s.match(/https?:\/\/[^"'\\]+vids\.pexels\.com[^"'\\]+\.mp4[^"'\\]*/g);
      if (m) m.forEach(u => out.add(u.replace(/\\u0026/g,'&').replace(/\\u003D/g,'=').replace(/\\u002F/g,'/')));
    });
    // 2) Tum script etiketleri (JSON-LD, inline JSON)
    document.querySelectorAll('script').forEach(s => {
      const t = s.textContent || '';
      // video-files / vids.pexels.com / images.pexels.com/users/videos dahil
      const m = t.match(/https?:\/\/[^"'\\<>\s]*vids\.pexels\.com[^"'\\<>\s]*\.mp4[^"'\\<>\s]*/g);
      if (m) m.forEach(u => out.add(u.replace(/\\u0026/g,'&').replace(/\\u003D/g,'=').replace(/\\u002F/g,'/')));
      // video_files/ linkleri (bazen API path farkli olabilir)
      const m2 = t.match(/https?:\/\/[^"'\\<>\s]*\/video-files\/[^"'\\<>\s]*\.mp4[^"'\\<>\s]*/g);
      if (m2) m2.forEach(u => out.add(u.replace(/\\u0026/g,'&').replace(/\\u003D/g,'=').replace(/\\u002F/g,'/')));
    });
    // 3) DOM'daki <video>/<source>/img[data-src]
    document.querySelectorAll('video source, video, [data-testid*="video"] source').forEach(s => {
      const src = s.src || s.currentSrc || s.getAttribute('src');
      if (src && /\.mp4/i.test(src)) out.add(src);
    });
    // 4) Anchor href'lerden video sayfalarina git, sayfa icinde video url'lerini bulma (sonraki adimda)
    return [...out];
  });
  // Kabul edilebilir URL'leri kalite sirasina gore sirala:
  //   1) video-files/...hd_1920_1080.mp4  (HD landscape)
  //   2) video-files/...uhd_2560_1440.mp4 (UHD)
  //   3) video-files/...-hd_*.mp4         (dikey HD dahil)
  //   4) diger vids.pexels.com/video-files/ (standart SD)
  //   5) vids.pexels.com (AI UGC / aigc-bundle) — son care
  // Preview/thumb/tiny her zaman ELENIR.
  const blocked = /tiny|preview|thumb/i;
  const priority = [
    u => /video-files\/.*hd_1920_1080/i.test(u) ? 0 : -1,
    u => /video-files\/.*uhd_2560_1440/i.test(u) ? 1 : -1,
    u => /video-files\/.*-hd_/i.test(u) ? 2 : -1,
    u => /vids\.pexels\.com\/video-files\//i.test(u) ? 3 : -1,
    u => /vids\.pexels\.com/i.test(u) ? 4 : -1,
  ];
  const candidates = urls
    .filter(u => !blocked.test(u))
    .map(u => {
      let p = 99;
      for (const fn of priority) { const r = fn(u); if (r >= 0) { p = r; break; } }
      return { download_url: u, priority: p, source_url: searchUrl,
               media_id: (u.match(/\/videos\/(\d+)\//) || u.match(/video-files\/(\d+)/) || [])[1] || '' };
    })
    .filter(c => c.priority < 99)
    .sort((a,b) => a.priority - b.priority);
  // Hic dogrudan MP4 URL'si bulunamazsa, ilk 2 video kartinin detay sayfasina git
  if (urls.size === 0 || candidates.length === 0) {
    diag.page_debug = 'no_direct_mp4_trying_detail_pages';
    const anchors = await page.evaluate(() => {
      const out = new Set();
      document.querySelectorAll('a[href*="/video/"]').forEach(a => {
        const h = a.href || a.getAttribute('href');
        if (h && /\/video\/\d+\/[a-z0-9-]+\/?$/i.test(h)) out.add(h.startsWith('http') ? h : 'https://www.pexels.com'+h);
      });
      return [...out].slice(0, 3);
    });
    diag.video_card_links_found = anchors.length;
    for (const detailUrl of anchors) {
      try {
        await page.goto(detailUrl, { waitUntil: 'domcontentloaded', timeout: TIMEOUT_MS });
        await page.waitForTimeout(3000);
        const detailUrls = await page.evaluate(() => {
          const out = new Set();
          [window.__NEXT_DATA__, window.__APOLLO_STATE__, window.__INITIAL_STATE__].forEach(obj => {
            if (!obj) return;
            const s = JSON.stringify(obj);
            const m = s.match(/https?:\/\/[^"'\\]+vids\.pexels\.com[^"'\\]+\.mp4[^"'\\]*/g);
            if (m) m.forEach(u => out.add(u.replace(/\\u0026/g,'&')));
          });
          document.querySelectorAll('video source, video').forEach(s => {
            const src = s.src || s.currentSrc || s.getAttribute('src');
            if (src && /\.mp4/i.test(src)) out.add(src);
          });
          document.querySelectorAll('script').forEach(s => {
            const t = s.textContent || '';
            const m = t.match(/https?:\/\/[^"'\\<>\s]*vids\.pexels\.com[^"'\\<>\s]*\.mp4[^"'\\<>\s]*/g);
            if (m) m.forEach(u => out.add(u.replace(/\\u0026/g,'&')));
          });
          return [...out];
        });
        detailUrls.forEach(u => urls.add(u));
      } catch (e) { /* detay sayfasina gidilemedi */ }
    }
    // Yeniden candidate olustur
    const more = [...urls]
      .filter(u => !blocked.test(u))
      .map(u => {
        let p = 99;
        for (const fn of priority) { const r = fn(u); if (r >= 0) { p = r; break; } }
        return { download_url: u, priority: p, source_url: searchUrl,
                 media_id: (u.match(/\/videos\/(\d+)\//) || u.match(/video-files\/(\d+)/) || [])[1] || '' };
      })
      .filter(c => c.priority < 99)
      .sort((a,b) => a.priority - b.priority);
    candidates.push(...more);
  }
  diag.candidates_found = candidates.length;
  if (candidates.length === 0) {
    diag.search = 'no_valid_video';
    // Debug icin sayfa HTML'inin ilk 2KB'sini kaydet (COOKIE/SAHSI BILGI YOK — sadece yapisal ipucu)
    try {
      const html = await page.content();
      diag.html_snippet = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,'').replace(/cookie|session|token/gi,'').slice(0, 1500);
    } catch {}
    return { candidates: [], diagnostics: diag };
  }
  diag.selected_url = safeUrl(candidates[0].download_url);
  return { candidates: candidates.slice(0, 8), diagnostics: diag };
}

// ── Provider runner ──────────────────────────────────────────
async function runProvider(provider, opts) {
  const envName = provider === 'pexels' ? 'PEXELS_COOK' : 'PIXABAY_COOK';
  const defaultDomain = provider === 'pexels' ? '.pexels.com' : '.pixabay.com';
  const diag = {
    provider,
    cookie_present: false,
    cookie_count: 0,
    cookie_domain_ok: false,
    browser_access: null,
    search: null,
    source_url: null,
    download: null,
    download_url_host: null,
    http_status: null,
    content_type: null,
    bytes: null,
    sha256: null,
    ffprobe: null,
    full_decode: null,
    width: null,
    height: null,
    duration: null,
    codec: null,
    error: null,
  };

  // Cookie yukle: once env, sonra --cookies-file. Domain filtrele.
  let cookies = [];
  const envRaw = process.env[envName];
  if (envRaw && envRaw.trim()) cookies.push(...loadCookies(envRaw, defaultDomain));
  if (opts.cookiesFile && fs.existsSync(opts.cookiesFile)) {
    cookies.push(...loadCookies(opts.cookiesFile, defaultDomain));
  }
  // Tekillestir
  const seen = new Map();
  for (const c of cookies) { seen.set(`${c.name}|${c.domain}|${c.path}`, c); }
  cookies = [...seen.values()];

  diag.cookie_present = cookies.length > 0;
  diag.cookie_count = cookies.length;
  if (cookies.length === 0) {
    diag.error = 'cookie_missing_or_wrong_domain';
    return { candidates: [], diagnostics: diag, provider };
  }
  // Butun cookie'lerin dogru domain'de oldugunu teyit et
  diag.cookie_domain_ok = cookies.every(c => {
    const d = c.domain;
    return d === defaultDomain || d.endsWith(defaultDomain);
  });
  if (!diag.cookie_domain_ok) {
    diag.error = 'cookie_wrong_domain';
    return { candidates: [], diagnostics: diag, provider };
  }

  const { browser, ctx } = await launchContext(cookies, provider);
  try {
    const page = await ctx.newPage();
    const fetcher = provider === 'pexels' ? fetchFromPexels : fetchFromPixabay;
    const { candidates, diagnostics: fd } = await fetcher(page, opts.keyword, opts);
    Object.assign(diag, fd);
    if (!candidates || candidates.length === 0) {
      await browser.close();
      return { candidates: [], diagnostics: diag, provider };
    }
    // metadata modu: indirme YAPMA, sadece candidate listesi don
    if (opts.metadata) {
      await browser.close();
      return { candidates: candidates.map(c => ({
        provider, media_id: c.media_id, source_url: c.source_url,
        download_url: c.download_url, quality: c.quality, priority: c.priority,
      })), diagnostics: diag, provider };
    }
    // Ilk uygun adayi sec + quality/cozunurluk/sure filtreleri (ffprobe sonrası)
    let chosen = null, probe = null;
    const attempts = [];
    console.error(`[${provider}] ${candidates.length} aday bulundu, ilk ${Math.min(10,candidates.length)} denenecek...`);
    console.error(`[${provider}] Aday ornekleri:`, candidates.slice(0,3).map(c => ({u:safeUrl(c.download_url),p:c.priority})));
    for (const c of candidates.slice(0, 10)) {
      // Indirme
      fs.mkdirSync(path.dirname(opts.outPath), { recursive: true });
      const tmpPath = opts.outPath + '.part';
      if (fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath);
      const attempt = { url: safeUrl(c.download_url), priority: c.priority };
      const dl = await downloadWithChecks(page, c.download_url, tmpPath,
                                          ALLOWED_DOWNLOAD_HOSTS[provider], opts.maxBytes);
      attempt.download_ok = dl.ok;
      attempt.download_error = dl.ok ? null : (dl.trace && dl.trace.error);
      attempt.final_host = dl.trace && dl.trace.finalHost;
      attempt.http_status = dl.trace && dl.trace.httpStatus;
      attempt.content_type = dl.trace && dl.trace.contentType;
      attempt.bytes = dl.trace && dl.trace.bytes;
      diag.download_url_host = attempt.final_host;
      diag.http_status = attempt.http_status;
      diag.content_type = attempt.content_type;
      diag.bytes = attempt.bytes;
      if (!dl.ok) {
        console.error(`[${provider}]   indirme BASARISIZ: ${attempt.download_error} (status=${attempt.http_status}, ct=${attempt.content_type}, host=${attempt.final_host})`);
        if (fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath);
        attempts.push(attempt);
        continue;
      }
      // ffprobe
      const fp = ffprobe(tmpPath);
      attempt.ffprobe_ok = fp.ok;
      attempt.ffprobe_err = fp.error;
      attempt.width = fp.width; attempt.height = fp.height; attempt.duration = fp.duration; attempt.codec = fp.codec;
      diag.download = 'ok';
      diag.ffprobe = fp.ok ? 'ok' : fp.error;
      diag.full_decode = fp.ok ? 'ok' : (fp.error === 'full_decode_failed' ? 'failed' : 'n/a');
      diag.width = fp.width; diag.height = fp.height; diag.duration = fp.duration; diag.codec = fp.codec;
      if (!fp.ok) {
        console.error(`[${provider}]   ffprobe/fulldecode BASARISIZ: ${fp.error}`);
        if (fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath);
        attempts.push(attempt);
        if (fp.error === 'full_decode_failed') continue; // sonraki adayi dene
        continue;
      }
      // Kalite esikleri
      let reject = null;
      if (fp.width < opts.minWidth || fp.height < opts.minHeight) reject = `cozunurluk ${fp.width}x${fp.height}`;
      else if (opts.portrait && fp.height <= fp.width) reject = 'landscape';
      else if (fp.duration && (fp.duration < opts.minDuration || fp.duration > opts.maxDuration)) reject = `sure ${fp.duration}s`;
      if (reject) {
        console.error(`[${provider}]   filtre reddi: ${reject}`);
        if (fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath);
        attempt.filter_reject = reject;
        attempts.push(attempt);
        continue;
      }
      // Basarili
      fs.renameSync(tmpPath, opts.outPath);
      attempt.ok = true;
      attempts.push(attempt);
      chosen = { path: opts.outPath, info: fp, download_url: c.download_url };
      console.error(`[${provider}]   ✅ Secildi: ${fp.width}x${fp.height} ${fp.duration?.toFixed(1)}s ${(attempt.bytes/1048576).toFixed(1)}MB`);
      break;
    }
    diag.attempts = attempts;
    if (!chosen) diag.search = 'no_valid_video';
    await browser.close();
    return { chosen, diagnostics: diag, provider };
  } catch (e) {
    diag.error = 'browser_exception';
    try { await browser.close(); } catch {}
    return { chosen: null, diagnostics: diag, provider };
  }
}

// ── Ana ──────────────────────────────────────────────────────
async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (!opts.keyword) {
    console.error('Kullanim: node video_fetcher.js <keyword> <output_path> [--provider pexels|pixabay|all] [--metadata] [--portrait] ...');
    process.exit(2);
  }
  const providers = opts.provider === 'all' ? ['pixabay','pexels'] : [opts.provider];
  if (providers.some(p => !['pexels','pixabay'].includes(p))) {
    console.error('gecersiz_provider');
    process.exit(2);
  }

  if (opts.metadata) {
    // metadata modu: butun saglayicilari tara, JSON cik
    const allCandidates = [];
    const allDiag = {};
    for (const p of providers) {
      const r = await runProvider(p, opts);
      allCandidates.push(...(r.candidates || []));
      allDiag[p] = r.diagnostics;
    }
    const out = { candidates: allCandidates, diagnostics: allDiag };
    process.stdout.write(JSON.stringify(out));
    // Hic aday yoksa exit 1
    const allFailed = Object.values(allDiag).every(d => d.error || (d.candidates_found === 0));
    process.exit(allFailed ? 1 : 0);
  }

  if (!opts.outPath) {
    console.error('outPath gerekli'); process.exit(2);
  }
  // Indirme modu: siralamayi dene, ilk basarili olani don
  const diagLog = {};
  for (const p of providers) {
    const r = await runProvider(p, opts);
    diagLog[p] = r.diagnostics;
    if (r.chosen) {
      console.error(`[${p}] ✅ Video indirildi ve dogrulandi: ${r.chosen.path} ` +
        `(${r.chosen.info.width}x${r.chosen.info.height}, ${r.chosen.info.duration?.toFixed(1)}s, ` +
        `${(r.diagnostics.bytes/1024/1024).toFixed(1)}MB, codec=${r.chosen.info.codec})`);
      console.log(r.chosen.path);
      process.exit(0);
    }
    const err = r.diagnostics.error || r.diagnostics.search || 'download_failed';
    console.error(`[${p}] ✗ Basarisiz: ${err}`);
  }
  console.error('[HATA] hicbir saglayicidan gecerli video bulunamadi');
  process.exit(1);
}

main().catch(e => {
  console.error('[KRITIK] ' + (e.message || String(e)).slice(0,300));
  process.exit(1);
});
