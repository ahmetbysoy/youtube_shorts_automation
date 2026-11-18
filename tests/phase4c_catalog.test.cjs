'use strict';
// Pure offline metadata/cookie-isolation tests. NO browser/network is launched.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { providerCookies, officialLicenseLink } = require('../scripts/stock_media_catalog.cjs');
const rows = ['.pexels.com', '.pixabay.com', '.google.com', '.youtube.com', '.github.com', 'sub.pexels.com', 'pexels.com.evil.test', '..pexels.com'].map(domain => ({ name: 'fixture', value: 'private-fixture-value', domain, path: '/', extra: 'discard' }));
test('Pexels context receives only exact approved Pexels cookie domains', () => {
  const c = providerCookies(rows, 'pexels'); assert.equal(c.length, 1); assert.equal(c[0].domain, '.pexels.com'); assert.equal(c[0].extra, undefined);
});
test('Pixabay context cannot receive a Pexels/Google/YouTube/GitHub cookie', () => {
  const c = providerCookies(rows, 'pixabay'); assert.equal(c.length, 1); assert.equal(c[0].domain, '.pixabay.com');
});
test('Unsupported provider receives no cookie context', () => { assert.deepEqual(providerCookies(rows, 'github'), []); });
test('Official permission links are exact host/path, not a misleading prefix', () => {
  assert.equal(officialLicenseLink('https://www.pexels.com/license/', 'pexels'), true);
  assert.equal(officialLicenseLink('https://pixabay.com/service/license-summary/', 'pixabay'), true);
  assert.equal(officialLicenseLink('https://pixabay.com/service/terms/', 'pixabay'), true);
  for (const url of ['https://www.pexels.com/license-evil/', 'https://www.pexels.com.evil.test/license/', 'https://www.pexels.com/license/?token=fixture', 'http://www.pexels.com/license/', 'https://user:pass@www.pexels.com/license/']) {
    assert.equal(officialLicenseLink(url, 'pexels'), false);
  }
});
test('Provider permission links cannot borrow an unrelated privacy/service page', () => {
  assert.equal(officialLicenseLink('https://pixabay.com/service/privacy/', 'pixabay'), false);
  assert.equal(officialLicenseLink('https://www.pexels.com/license/', 'pixabay'), false);
});
