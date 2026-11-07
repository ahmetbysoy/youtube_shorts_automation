// Gerçek Chromium ile sahte Studio sayfası: kimlik modalı algılama + telefon onayı bekleme akışı.
const assert = require('assert');
const path = require('path');
process.env.IDENTITY_WAIT_SEC = '12';
process.env.YT_EMAIL = process.env.YT_EMAIL || 'x@example.com';
process.env.YT_PASSWORD = process.env.YT_PASSWORD || 'dummy';
const { chromium } = require('playwright');
const up = require(path.join(__dirname, '..', 'youtube_studio_uploader.js'));

function studioHtml(mode) {
  // mode: 'ok'  -> popup 3 sn sonra kapanır (telefon onayı geldi)
  //       'wait'-> popup açık kalır (onay gelmez) → timeout
  return `<html><body>
  <h1>Studio sahte</h1>
  <tp-yt-paper-dialog role="dialog" style="display:block;border:1px solid #000;padding:10px">
    <h2>Kimliğinizi doğrulayın</h2>
    <p>Devam etmek için kimliğinizi doğrulamamız gerekiyor.</p>
    <button id="more">Daha fazla bilgi</button>
    <button id="next" onclick="(function(){var w=window.open('https://accounts.google.com/reauth?mode=${mode}','_blank');var iv=setInterval(function(){if(w&&w.closed){clearInterval(iv);var d=document.querySelector('tp-yt-paper-dialog');if(d)d.remove();}},300);})()">Sonraki</button>
  </tp-yt-paper-dialog>
  </body></html>`;
}
const reauthHtml = (mode) => `<html><body>
  <h1>Kimliğinizi doğrulayın</h1>
  <p>Google, cihazınıza bildirim gönderdi. Bildirimdeki Evet'e ve ardından telefonunuzdaki 42 sayısına dokunarak siz olduğunuzu doğrulayın.</p>
  ${mode === 'ok' ? '<script>setTimeout(function(){ window.close(); },3000)</script>' : ''}
  </body></html>`;

// Şifre + "Doğrulanamadı → Tekrar dene" senaryosu için sahte Google sayfaları
const pwdHtml = `<html><head><meta charset="utf-8"></head><body><h1>Hoş geldiniz</h1>
  <input type="password" id="p"><button id="passwordNext" onclick="location.href='/denied'">Sonraki</button></body></html>`;
const deniedHtml = `<html><head><meta charset="utf-8"></head><body><h1>Doğrulanamadı</h1>
  <p>Google'ın telefonunuza gönderdiği istemde Hayır seçeneğine dokunduğunuz için şu anda devam edemezsiniz.</p>
  <button onclick="location.href='/phone'">Tekrar dene</button></body></html>`;
const phoneOkHtml = `<html><head><meta charset="utf-8"></head><body>
  <p>Bildirimdeki Evet'e ve ardından telefonunuzdaki 17 sayısına dokunarak siz olduğunuzu doğrulayın.</p>
  <script>setTimeout(function(){ window.close(); },3000)</script></body></html>`;

(async () => {
  const browser = await chromium.launch({ headless: true });
  // --- Senaryo: şifre 1 kez → Doğrulanamadı → Tekrar dene (1 kez) → telefon onayı → ok
  {
    let pwdVisits = 0, pwdSubmits = 0;
    const context = await browser.newContext();
    await context.route('**/*', (route) => {
      const u = new URL(route.request().url());
      if (u.hostname === 'accounts.google.com') {
        if (u.pathname === '/reauth') { pwdVisits++; return route.fulfill({ contentType: 'text/html; charset=utf-8', body: pwdHtml }); }
        if (u.pathname === '/denied') { pwdSubmits++; return route.fulfill({ contentType: 'text/html; charset=utf-8', body: deniedHtml }); }
        if (u.pathname === '/phone') return route.fulfill({ contentType: 'text/html; charset=utf-8', body: phoneOkHtml });
      }
      return route.fulfill({ contentType: 'text/html; charset=utf-8', body: studioHtml('pwd') });
    });
    const page = await context.newPage();
    await page.goto('https://studio.youtube.com/fake');
    const t0 = Date.now();
    const ok = await up.handleIdentityVerificationModal(page, context);
    const dt = Math.round((Date.now() - t0) / 1000);
    assert.strictEqual(ok, true, 'pwd senaryosu başarıyla bitmeli');
    assert.strictEqual(pwdSubmits, 1, 'şifre tam 1 kez gönderilmeli, gönderilen=' + pwdSubmits);
    console.log(`PASS pwd→denied→retry→phone (${dt}s, şifre gönderimi=${pwdSubmits})`);
    await context.close();
  }
  for (const mode of ['ok', 'wait']) {
    const context = await browser.newContext();
    await context.route('**/*', (route) => {
      const u = new URL(route.request().url());
      if (u.pathname === '/reauth') return route.fulfill({ contentType: 'text/html; charset=utf-8', body: reauthHtml(u.searchParams.get('mode')) });
      return route.fulfill({ contentType: 'text/html; charset=utf-8', body: studioHtml(mode) });
    });
    const page = await context.newPage();
    await page.goto('https://studio.youtube.com/fake');
    const modal = await up.findIdentityModal(page);
    assert(modal, `[${mode}] modal algılanmalı`);
    const t0 = Date.now();
    let threw = null, ok = null;
    try { ok = await up.handleIdentityVerificationModal(page, context); } catch (e) { threw = e; }
    const dt = Math.round((Date.now() - t0) / 1000);
    if (mode === 'ok') {
      assert.strictEqual(threw, null, 'ok modunda hata fırlatılmamalı: ' + (threw && threw.message));
      assert.strictEqual(ok, true);
      assert(dt < 20, 'ok modu 20 sn altında dönmeli, süre=' + dt);
      console.log(`PASS ok (${dt}s)`);
    } else {
      assert(threw && /GOOGLE_IDENTITY_VERIFICATION_REQUIRED/.test(threw.message), 'wait modunda fail-closed hata bekleniyordu');
      assert(dt >= 29, 'timeout süresi IDENTITY_WAIT_SEC (min 30) kadar olmalı, süre=' + dt);
      console.log(`PASS wait/timeout fail-closed (${dt}s): ${threw.message}`);
    }
    await context.close();
  }
  // Modal yokken false dönmeli
  const ctx = await browser.newContext();
  await ctx.route('**/*', (r) => r.fulfill({ contentType: 'text/html', body: '<html><body><h1>Normal</h1></body></html>' }));
  const pg = await ctx.newPage(); await pg.goto('https://studio.youtube.com/none');
  assert.strictEqual(await up.handleIdentityVerificationModal(pg, ctx), false);
  console.log('PASS no-modal → false');
  await ctx.close();
  await browser.close();
})().catch((e) => { console.error('FAIL', e); process.exit(1); });
