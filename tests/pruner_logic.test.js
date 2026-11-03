/**
 * Faz 10 birim testleri (Node): "ölü ağırlık" temizleyicinin sayı/tarih çözümleme mantığı.
 * Çalıştırma:  node tests/pruner_logic.test.js
 */
const assert = require('assert');
const path = require('path');

const pruner = require(path.join(__dirname, '..', 'prune_low_performers.js'));

let passed = 0;
function check(name, fn) {
    fn();
    passed++;
    console.log(`  ok - ${name}`);
}

console.log('Faz 10 pruner mantık testleri:');

check('Türkçe sayı biçimi ayrıştırma', () => {
    assert.strictEqual(pruner.parseTrNumber('87'), 87);
    assert.strictEqual(pruner.parseTrNumber('1.234'), 1234);
    assert.strictEqual(pruner.parseTrNumber('1,2 B'), 1200);
    assert.strictEqual(pruner.parseTrNumber('3,4 Mn'), 3400000);
    assert.strictEqual(pruner.parseTrNumber(''), 0);
    assert.strictEqual(pruner.parseTrNumber(null), 0);
});

check('Göreli tarih çözümleme (saat/dakika/gün)', () => {
    assert.strictEqual(pruner.parseRelativeMinutes('3 saat önce'), 180);
    assert.strictEqual(pruner.parseRelativeMinutes('45 dakika önce'), 45);
    assert.strictEqual(pruner.parseRelativeMinutes('2 gün önce'), 2880);
    assert.strictEqual(pruner.parseRelativeMinutes('Yayınlandı'), null);
});

check('Mutlak Türkçe tarih çözümleme (asla erken silme garantisi)', () => {
    const parsed = pruner.parseAbsoluteDateTr('3 Kas 2026');
    assert.ok(parsed, 'tarih çözümlenmeli');
    assert.strictEqual(new Date(parsed.ts).getUTCMonth(), 10);
    assert.strictEqual(new Date(parsed.ts).getUTCDate(), 3);
    // Günün EN GEÇ anı varsayılır -> yaş asla şişirilmez
    assert.strictEqual(new Date(parsed.ts).getUTCHours(), 23);
    assert.strictEqual(pruner.parseAbsoluteDateTr('bilinmiyor'), null);
});

check('Yaş çözümleme önceliği: RSS > state > göreli > mutlak', () => {
    const now = Date.parse('2026-11-03T12:00:00Z');
    const video = { videoId: 'abc', dateText: '3 Kas 2026', statusText: 'Yayınlandı' };

    const viaRss = pruner.resolveAgeMinutes(
        video, { abc: { ts: Date.parse('2026-11-03T10:00:00Z') } }, { videos: {} }, now
    );
    assert.strictEqual(viaRss.source, 'rss');
    assert.strictEqual(Math.round(viaRss.minutes), 120);

    const viaState = pruner.resolveAgeMinutes(
        video, {}, { videos: { abc: { first_seen_at: '2026-11-03T11:00:00Z' } } }, now
    );
    assert.strictEqual(viaState.source, 'state');
    assert.strictEqual(Math.round(viaState.minutes), 60);

    const viaRelative = pruner.resolveAgeMinutes(
        { videoId: 'x', dateText: '2 saat önce', statusText: '' }, {}, { videos: {} }, now
    );
    assert.strictEqual(viaRelative.source, 'studio-relative');
    assert.strictEqual(Math.round(viaRelative.minutes), 120);

    const viaDate = pruner.resolveAgeMinutes(video, {}, { videos: {} }, now);
    assert.strictEqual(viaDate.source, 'studio-date-conservative');
    assert.ok(viaDate.minutes < 0, 'bugün yayınlanan video muhafazakâr biçimde atlanmalı');

    const unknown = pruner.resolveAgeMinutes(
        { videoId: 'y', dateText: '', statusText: '' }, {}, { videos: {} }, now
    );
    assert.strictEqual(unknown.minutes, null);
});

console.log(`\n${passed} test başarıyla geçti.`);
