#!/usr/bin/env node
'use strict';
// Lokal kapak uretim testi — CI'ye kosmadan once burada calistir.
// Kullanim:
//   node scripts/test_cover_generation.mjs                      -> 5 farkli baslik uretir
//   node scripts/test_cover_generation.mjs "Baslik burada"      -> tek baslik
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, '..');

const MODELS = (process.env.IMAGE_MODELS || 'sana,flux,turbo').split(',').map(s => s.trim()).filter(Boolean);
const MODEL_SWITCH_DELAY_MS = 8000;
const ATTEMPT_DELAY_MS = 8000;
const GLOBAL_COOLDOWN_MS = 15000;

const TITLES = process.argv[2]
  ? [process.argv.slice(2).join(' ')]
  : [
    'Güneş Her Saniye 4 Milyon Ton Kütlesini Işığa Dönüştürür! #Shorts',
    'Karınca Kolonisi Merkezi Komutan Olmadan Karar Alır! #Shorts',
    'Uzayda Kaybolan Astronutun Son Sözleri #Shorts',
    'Siyah Deliğin İçinde Ne Var? #Shorts',
    'Dünyanın En Derin Noktasına Kimse İnemedi! #Shorts',
  ];

const OUT_DIR = path.join(REPO, 'local_test_output');
fs.mkdirSync(OUT_DIR, { recursive: true });

function buildPrompt(title) {
  const clean = String(title || 'YouTube Shorts').replace(/#Shorts/ig, '').trim().slice(0, 180);
  return (
    'YouTube Shorts thumbnail, vertical 9:16 aspect ratio (1080x1920). ' +
    'Konu: "' + clean + '". ' +
    'Bu bir kisa video kapak fotografi. Kapagi goren izleyici merak edip tiklamali, ' +
    'etkilesim ve izlenme rekorlari kirmali, profesyonel YouTube thumbnail tasarimi olsun. ' +
    'Composition: one single dominant central subject filling 60-70% of the frame, extreme close-up, ' +
    'subject looks directly at camera. If about a person/living being, show a dramatic SHOCKED ' +
    'reaction face with mouth open, eyebrows raised — viral YouTube reaction look. ' +
    'Lighting: hyper-dramatic cinematic key light, strong rim light, deep shadows, lens flare, ' +
    'high contrast chiaroscuro, warm vs cold color clash. ' +
    'Color: ultra-saturated, punchy, neon accents, vivid red/yellow highlights that pop. ' +
    'Background: moody cinematic, heavy bokeh blur, slightly desaturated so subject pops. ' +
    'Emotion: jaw-dropping, mind-blowing, "you won\'t believe this" energy, curiosity gap. ' +
    'Accuracy: accurately represent the title — no invented objects, people, or facts. ' +
    'Quality: ultra-realistic photorealistic 8K, sharp focus, shallow depth of field, ' +
    'cinematic color grading, shot on Sony A7IV 85mm f/1.4. ' +
    'FORBIDDEN: any text, letters, numbers, captions, logos, watermarks, borders, arrows, ' +
    'red circles, emoji, collage, split screen, deformed faces/hands, AI artifacts.'
  );
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = m => console.log('[' + new Date().toISOString() + '] ' + m);

async function fetchPollinations(model, prompt, seed) {
  const modelParam = model ? '&model=' + encodeURIComponent(model) : '';
  const url = 'https://image.pollinations.ai/prompt/' + prompt +
    '?width=1080&height=1920&nologo=true&seed=' + seed + modelParam;
  log('  model=' + (model || '(default)') + ' seed=' + seed);
  const t0 = Date.now();
  const res = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36',
      'Accept': 'image/*,*/*;q=0.8',
      'Referer': 'https://studio.youtube.com/',
    },
    signal: AbortSignal.timeout(120000),
  });
  const dt = Date.now() - t0;
  log('    HTTP ' + res.status + ' (' + dt + 'ms) x-model=' + (res.headers.get('x-model-used') || '-'));
  if (res.status === 402 || res.status === 429) {
    const retry = Number(res.headers.get('retry-after') || 0);
    const err = new Error('RATE_LIMITED'); err.status = res.status; err.retryAfter = retry; throw err;
  }
  if (!res.ok) throw new Error('HTTP ' + res.status);
  const buf = Buffer.from(await res.arrayBuffer());
  const type = res.headers.get('content-type') || '';
  if (!type.includes('image') || buf.length < 20000) throw new Error('gecersiz gorsel (' + type + ',' + buf.length + 'B)');
  return { buf, type, modelUsed: res.headers.get('x-model-used') || model, ms: dt };
}

async function makeCover(title, outPath) {
  const prompt = encodeURIComponent(buildPrompt(title));
  const errs = [];
  for (let i = 0; i < MODELS.length; i++) {
    for (let a = 1; a <= 2; a++) {
      try {
        const r = await fetchPollinations(MODELS[i], prompt, Math.floor(Math.random()*1e9));
        fs.writeFileSync(outPath, r.buf);
        return r;
      } catch (e) {
        if (e.message === 'RATE_LIMITED') {
          log('    ⏳ rate limit (HTTP ' + e.status + '), ' + GLOBAL_COOLDOWN_MS/1000 + 'sn bekle');
          await sleep(GLOBAL_COOLDOWN_MS);
          break;
        }
        errs.push(MODELS[i]+'/'+a+': '+e.message);
        log('    ✗ ' + e.message);
        if (a < 2) await sleep(ATTEMPT_DELAY_MS);
      }
    }
    if (i < MODELS.length - 1) await sleep(MODEL_SWITCH_DELAY_MS);
  }
  // Son fallback: modelsiz
  try {
    log('  son sans: default model');
    const r = await fetchPollinations('', prompt, Math.floor(Math.random()*1e9));
    fs.writeFileSync(outPath, r.buf);
    return r;
  } catch (e) { errs.push('default: '+e.message); }
  throw new Error('Hicbir model calismadi: ' + errs.slice(-5).join(' | '));
}

function isJpeg(p) {
  const b = fs.readFileSync(p);
  return b.length > 4 && b[0] === 0xFF && b[1] === 0xD8 && b[2] === 0xFF;
}

(async () => {
  const results = [];
  for (let i = 0; i < TITLES.length; i++) {
    const title = TITLES[i];
    log('\n=== [' + (i+1) + '/' + TITLES.length + '] ' + title);
    const out = path.join(OUT_DIR, 'cover_' + (i+1) + '_' + Date.now() + '.jpg');
    try {
      const r = await makeCover(title, out);
      const ok = isJpeg(out);
      const size = fs.statSync(out).size;
      log('✅ dosya=' + path.basename(out) + ' size=' + size + ' jpeg=' + ok);
      results.push({ title, ok, size, model: r.modelUsed, ms: r.ms });
    } catch (e) {
      log('❌ HATA: ' + e.message);
      results.push({ title, ok: false, err: e.message });
    }
    if (i < TITLES.length - 1) {
      log('  (siradaki icin 8sn bekle...)');
      await sleep(8000);
    }
  }
  console.log('\n========== OZET ==========');
  results.forEach((r, i) => {
    console.log((i+1) + '. ' + (r.ok ? '✅' : '❌') + ' ' + r.title.slice(0, 55) + (r.ok ? '  (' + r.size + 'B, model=' + r.model + ')' : '  → ' + r.err));
  });
  const oks = results.filter(r => r.ok).length;
  console.log('\nBasari: ' + oks + '/' + results.length);
  if (oks !== results.length) process.exitCode = 1;
})();
