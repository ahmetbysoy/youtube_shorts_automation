'use strict';
// Strict Phase 4 catalog: source-page JSON-LD + observed license link.
// A naked CDN URL/search term is NEVER sufficient. No downloads or secret logs.
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');

function durationSeconds(value) {
  const m = String(value || '').match(/^PT(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?$/);
  return m ? Number(m[1] || 0) * 3600 + Number(m[2] || 0) * 60 + Number(m[3] || 0) : null;
}
function parseCatalog(payload, sourceUrl, provider, licenseLinkObserved) {
  const hosts = { pexels: ['www.pexels.com', 'pexels.com'], pixabay: ['pixabay.com', 'www.pixabay.com'] };
  let source;
  try { source = new URL(sourceUrl); } catch { return []; }
  if (source.protocol !== 'https:' || !hosts[provider]?.includes(source.hostname) || source.username || source.password) return [];
  const id = source.pathname.match(/(?:-|\/)(\d+)\/?$/)?.[1];
  if (!id || !licenseLinkObserved) return [];
  const rows = [];
  function walk(item) {
    if (Array.isArray(item)) return item.forEach(walk);
    if (!item || typeof item !== 'object') return;
    const types = [].concat(item['@type'] || []);
    if (types.includes('VideoObject') && typeof item.contentUrl === 'string') {
      rows.push({ provider, media_id: id, source_url: sourceUrl, download_url: item.contentUrl,
        title: String(item.name || '').slice(0, 1000), description: String(item.description || '').slice(0, 6000),
        width: Number(item.width?.value || item.width) || null, height: Number(item.height?.value || item.height) || null,
        duration: durationSeconds(item.duration), license_link_observed: true });
    }
    for (const value of Object.values(item)) if (value && typeof value === 'object') walk(value);
  }
  walk(payload);
  return rows.slice(0, 6);
}
async function main(args) {
  const { chromium } = require('playwright');
  const query = args[0]; const provider = args[args.indexOf('--provider') + 1];
  if (!query || query.length > 180 || !['pexels', 'pixabay'].includes(provider)) throw new Error('invalid_catalog_arguments');
  const storagePath = path.join(ROOT, 'storage_state.json'); const cookiesPath = path.join(ROOT, 'cookies.json');
  const domains = provider === 'pexels' ? /(^|\.)pexels\.com$/i : /(^|\.)pixabay\.com$/i;
  // Do not bring YouTube/Google sessions into stock-catalog browser contexts.
  let cookies = [];
  if (fs.existsSync(storagePath)) cookies.push(...(JSON.parse(fs.readFileSync(storagePath, 'utf8')).cookies || []));
  if (fs.existsSync(cookiesPath)) cookies.push(...JSON.parse(fs.readFileSync(cookiesPath, 'utf8')));
  cookies = cookies.filter(c => domains.test(String(c.domain || '').replace(/^\./, '')));
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  try {
    const context = await browser.newContext({ locale: 'en-US' });
    if (cookies.length) await context.addCookies(cookies);
    const page = await context.newPage();
    const base = provider === 'pexels' ? 'https://www.pexels.com' : 'https://pixabay.com';
    const search = provider === 'pexels' ? `${base}/search/videos/${encodeURIComponent(query)}/` : `${base}/videos/search/${encodeURIComponent(query)}/`;
    const response = await page.goto(search, { waitUntil: 'domcontentloaded', timeout: 20000 });
    const diagnostics = { search_http_status: response?.status() || null, source_links: 0, source_pages_parsed: 0, license_links_observed: 0 };
    // Stop at HTTP denial. No challenge handling, bypass, source navigation or
    // request/body/cookie logging. Python emits only a hashed query identifier.
    if (diagnostics.search_http_status !== 200) {
      console.log(JSON.stringify({ provider, candidates: [], diagnostics: { search_http_status: diagnostics.search_http_status } }));
      return;
    }
    const links = await page.locator('a[href]').evaluateAll((elements, data) => [...new Set(elements.map(a => a.href)
      .filter(href => { try { const u = new URL(href); return u.origin === data.base && (data.provider === 'pexels' ? /^\/video\/.+-\d+\/$/.test(u.pathname) : /^\/videos\/.+-\d+\/$/.test(u.pathname)); } catch { return false; } }))].slice(0, 3), { base, provider });
    diagnostics.source_links = links.length;
    const candidates = [];
    for (const source of links) {
      await page.goto(source, { waitUntil: 'domcontentloaded', timeout: 15000 });
      const raw = await page.evaluate(() => ({
        json: [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => { try { return JSON.parse(s.textContent); } catch { return null; } }),
        links: [...document.querySelectorAll('a[href]')].map(a => a.href)
      }));
      const observed = raw.links.some(href => href.startsWith(provider === 'pexels' ? 'https://www.pexels.com/license' : 'https://pixabay.com/service/'));
      diagnostics.source_pages_parsed += 1;
      diagnostics.license_links_observed += Number(observed);
      candidates.push(...parseCatalog(raw.json, page.url(), provider, observed));
    }
    console.log(JSON.stringify({ provider, candidates, diagnostics }));
  } finally { await browser.close(); }
}
module.exports = { parseCatalog, durationSeconds, main };
