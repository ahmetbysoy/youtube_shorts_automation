'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { parseCatalog, durationSeconds } = require('../scripts/stock_media_catalog.cjs');
const fixture = { '@type': 'VideoObject', name: 'ocean sea waves', description: 'Ocean water', contentUrl: 'https://videos.pexels.com/1.mp4', width: 1080, height: 1920, duration: 'PT12.5S' };
test('duration uses measured structured value, not a fabricated default', () => {
  assert.equal(durationSeconds('PT1M5S'), 65); assert.equal(durationSeconds('unknown'), null);
});
test('source page ID, actual caption and dimensions are preserved', () => {
  const row = parseCatalog([fixture], 'https://www.pexels.com/video/ocean-sea-123/', 'pexels', true)[0];
  assert.equal(row.media_id, '123'); assert.equal(row.width, 1080); assert.equal(row.duration, 12.5); assert.equal(row.title, 'ocean sea waves');
});
test('no source license link means no catalog candidate', () => {
  assert.deepEqual(parseCatalog([fixture], 'https://www.pexels.com/video/ocean-123/', 'pexels', false), []);
});
test('foreign page, bare CDN and guessed ID are not accepted', () => {
  for (const url of ['https://evil.test/video/ocean-123/', 'https://videos.pexels.com/1.mp4', 'https://www.pexels.com/search/videos/ocean/']) {
    assert.deepEqual(parseCatalog([fixture], url, 'pexels', true), []);
  }
});
test('unknown dimensions and duration are kept null for subsequent probe, not invented', () => {
  const row = parseCatalog({ ...fixture, width: undefined, height: undefined, duration: undefined }, 'https://pixabay.com/videos/ocean-123/', 'pixabay', true)[0];
  assert.equal(row.width, null); assert.equal(row.duration, null);
});
