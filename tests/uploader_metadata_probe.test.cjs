'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {consume} = require('../scripts/uploader_metadata_probe.cjs');
const credit = 'Ocean 🌊 — Fixture Author — CC BY 4.0; https://creativecommons.org/licenses/by/4.0/';

test('actual extracted functions, no uploader entrypoint or network in VM', () => {
  const out = consume({title:' Fixture ',description:credit,cta_line:'Test CTA',viral_hashtags:['#test','#ocean','#shorts']});
  assert.equal(out.uploader_entrypoint_executed,false);
  assert.equal(out.network_available_in_vm,false);
  assert.deepEqual(out.functions,['readScenarioField','buildFinalDescription']);
  assert.match(out.uploader_source_sha256,/^[a-f0-9]{64}$/);
  assert.ok(out.description.includes(credit));
  assert.equal(out.title,'Fixture');
});
for (const affiliate of [{affiliate_hook:'Fixture hook'}, {affiliate_cta:'Fixture CTA'}, {affiliate_link:'https://example.org/fixture'}]) {
  test('actual affiliate branch preserves full source credit: '+Object.keys(affiliate)[0], () => {
    const out = consume({...affiliate,description:credit,cta_line:'CTA',viral_hashtags:['#a','#b','#c','#not-used']});
    assert.ok(out.description.includes(credit));
    assert.ok(!out.description.includes('#not-used'));
    assert.equal(out.utf16_units,out.description.length);
    assert.ok(out.utf16_units<=4900);
  });
}
test('UTF-16 emoji credit plus CTA and hashtags exactly at 4900 budget survives', () => {
  const top = 'CTA', tags = '#a #b #c';
  const padding = 'x'.repeat(4900-top.length-2-credit.length-2-tags.length);
  const out = consume({description:padding+credit,cta_line:top,viral_hashtags:['#a','#b','#c']});
  assert.equal(out.utf16_units,4900);
  assert.ok(out.description.includes(credit));
});
test('unchanged uploader really truncates unsafe inputs, proving upstream guard is necessary', () => {
  const out = consume({description:'🌊'.repeat(2450)+credit,cta_line:'CTA',viral_hashtags:['#a','#b','#c']});
  assert.equal(out.utf16_units,4900);
  assert.ok(!out.description.includes(credit));
});
