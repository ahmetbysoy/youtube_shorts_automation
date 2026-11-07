const { chromium } = require('playwright');
const fs = require('fs');
const os = require('os');
const path = require('path');
require('dotenv').config();

const BASE_DIR = process.cwd();
const VIDEO_PATH = path.join(BASE_DIR, 'output', 'final_short.mp4');
const SCRIPT_PATH = path.join(BASE_DIR, 'script.json');
const COOKIES_PATH = path.join(BASE_DIR, 'cookies.json');
const STORAGE_STATE_PATH = path.join(BASE_DIR, 'storage_state.json');
const HAR_PATH = path.join(BASE_DIR, 'session.har');
const PROFILE_DIR = path.join(os.tmpdir(), 'yt_studio_browser_profile');
const AUTH_STATUS_PATH = path.join(BASE_DIR, 'logs', 'auth_status.json');
const CODE_INPUT_FILE = '/tmp/yt_2fa_code.txt';

function writeAuthStatus(state, details = {}) {
    try {
        fs.mkdirSync(path.dirname(AUTH_STATUS_PATH), { recursive: true });
        fs.writeFileSync(
            AUTH_STATUS_PATH,
            JSON.stringify({ timestamp: new Date().toISOString(), state, ...details }, null, 2),
            'utf8'
        );
    } catch (_) {}
}

function saveSecureFile(filePath, content) {
    fs.writeFileSync(filePath, content, { encoding: 'utf8', mode: 0o600 });
}

async function persistAllSessionArtifacts(context) {
    const cookies = await context.cookies();
    saveSecureFile(COOKIES_PATH, JSON.stringify(cookies, null, 2));
    const storageState = await context.storageState();
    saveSecureFile(STORAGE_STATE_PATH, JSON.stringify(storageState, null, 2));
    console.log(`[*] Oturum cookie'leri (${cookies.length} adet) ve storage_state.json kaydedildi. Sonraki çalışmalarda tam otomatik!`);
}

async function dismissStudioModalsIfPresent(page) {
    // 1. Kanal henüz oluşturulmamışsa "Kanal oluştur / Create channel" modalını tamamla
    const createChannelSelectors = [
        'ytd-channel-creation-dialog-renderer #create-channel-button button',
        'ytd-channel-creation-dialog-renderer ytcp-button#create-channel-button',
        '#create-channel-button',
        'button:has-text("Create channel")',
        'button:has-text("Kanal oluştur")'
    ];
    for (const sel of createChannelSelectors) {
        const loc = page.locator(sel).first();
        if (await loc.isVisible({ timeout: 1200 }).catch(() => false)) {
            console.log(`[*] Yeni kanal oluşturma penceresi algılandı (${sel}), onaylanıyor...`);
            await loc.click({ force: true }).catch(() => {});
            await page.waitForTimeout(8000);
            break;
        }
    }

    // 2. "YouTube Studio'ya hoş geldiniz -> Devam" ve tanıtım pencerelerini kapat
    const dismissSelectors = [
        'ytcp-warm-welcome-dialog button:has-text("Devam")',
        'ytcp-warm-welcome-dialog button:has-text("Continue")',
        'ytcp-warm-welcome-dialog #dismiss-button',
        'button:has-text("Devam")',
        'button:has-text("Continue")',
        'ytcp-feature-discovery-callout #dismiss-button',
        'ytcp-button#dismiss-button',
        'button:has-text("Kapat")',
        'button:has-text("Close")'
    ];
    for (const sel of dismissSelectors) {
        const loc = page.locator(sel).first();
        if (await loc.isVisible({ timeout: 1000 }).catch(() => false)) {
            console.log(`[*] Tanıtım penceresi kapatılıyor (${sel})...`);
            await loc.click({ force: true }).catch(() => {});
            await page.waitForTimeout(1500);
        }
    }
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(500);
}

async function isAuthenticatedInStudio(page) {
    const url = page.url();
    if (url.includes('accounts.google.com') || url.includes('ServiceLogin')) {
        return false;
    }
    if (url.includes('studio.youtube.com')) {
        await dismissStudioModalsIfPresent(page);
        return !page.url().includes('accounts.google.com');
    }
    return false;
}

async function performGoogleLogin(page) {
    const email = process.env.YT_EMAIL;
    const password = process.env.YT_PASSWORD;
    if (!email || !password) {
        throw new Error("YT_EMAIL veya YT_PASSWORD .env dosyasında tanımlı değil!");
    }

    console.log("[!] Oturum açılmamış veya cookie geçersiz. Giriş yapılıyor...");
    writeAuthStatus('entering_email', { url: page.url() });

    await page.goto('https://accounts.google.com/ServiceLogin?service=youtube&continue=https%3A%2F%2Fstudio.youtube.com%2F', {
        waitUntil: 'domcontentloaded',
        timeout: 45000
    });

    // Eğer Google zaten oturumu tanıdıysa ve doğrudan studio.youtube.com'a yönlendirdiyse çık
    await page.waitForTimeout(2500);
    if (await isAuthenticatedInStudio(page)) {
        return;
    }

    // AccountChooser ekranındaysa kayıtlı hesaba tıkla
    if (page.url().includes('accountchooser')) {
        console.log("[*] Google AccountChooser algılandı, hesap seçiliyor...");
        const acctTile = page.locator(`[data-identifier="${email}"], [data-email="${email}"]`).first();
        if (await acctTile.isVisible({ timeout: 5000 }).catch(() => false)) {
            await acctTile.click();
            await page.waitForTimeout(2500);
            if (await isAuthenticatedInStudio(page)) {
                return;
            }
        } else {
            const anotherBtn = page.locator('li:has-text("Başka bir hesap kullan"), li:has-text("Use another account")').first();
            if (await anotherBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
                await anotherBtn.click();
                await page.waitForTimeout(1500);
            }
        }
    }

    const emailInput = page.locator('input[type="email"], input#identifierId').first();
    if (await emailInput.isVisible({ timeout: 8000 }).catch(() => false)) {
        await emailInput.fill(email);
        await page.locator('#identifierNext, button:has-text("Next"), button:has-text("İleri")').first().click();
    }

    const passInput = page.locator('input[type="password"], input[name="Passwd"]').first();
    await passInput.waitFor({ state: 'visible', timeout: 30000 });
    await page.waitForTimeout(1200);
    await passInput.fill(password);
    await page.locator('#passwordNext, button:has-text("Next"), button:has-text("İleri")').first().click();

    console.log("[!] Kimlik doğrulama yanıtı ve varsa 2FA / telefon bildirimi bekleniyor...");
    await page.waitForTimeout(3500);

    const waitMs = process.env.GITHUB_ACTIONS === 'true' ? 75000 : 600000;
    const deadline = Date.now() + waitMs;
    while (Date.now() < deadline) {
        const currentUrl = page.url();

        if (await isAuthenticatedInStudio(page)) {
            writeAuthStatus('authenticated', { url: page.url() });
            return;
        }

        if (
            currentUrl.includes('gds.google.com') ||
            currentUrl.includes('myaccount.google.com') ||
            (currentUrl.includes('youtube.com') && !currentUrl.includes('studio.youtube.com'))
        ) {
            console.log(`[*] Oturum sonrası Google ara ekranı algılandı (${currentUrl.slice(0, 65)}...), doğrudan YouTube Studio'ya geçiliyor...`);
            const skipInterstitial = page.locator(
                'button:has-text("İptal"), button:has-text("Cancel"), button:has-text("Şimdi değil"), button:has-text("Not now"), button:has-text("Daha sonra"), button:has-text("Atla"), button:has-text("Skip")'
            ).first();
            if (await skipInterstitial.isVisible({ timeout: 2000 }).catch(() => false)) {
                await skipInterstitial.click().catch(() => {});
                await page.waitForTimeout(2500);
            }
            await page.goto('https://studio.youtube.com/', { waitUntil: 'domcontentloaded', timeout: 45000 });
            await page.waitForTimeout(4000);
            if (await isAuthenticatedInStudio(page)) {
                writeAuthStatus('authenticated', { url: page.url() });
                return;
            }
        }

        const skipBtns = [
            'button:has-text("İptal")',
            'button:has-text("Cancel")',
            'button:has-text("Not now")',
            'button:has-text("Şimdi değil")',
            'button:has-text("I understand")',
            'button:has-text("Anladım")',
            'button:has-text("Continue")',
            'button:has-text("Devam")',
            '#confirm'
        ];
        for (const sb of skipBtns) {
            const btn = page.locator(sb).first();
            if (await btn.isVisible({ timeout: 500 }).catch(() => false)) {
                await btn.click().catch(() => {});
                await page.waitForTimeout(2000);
            }
        }

        if (fs.existsSync(CODE_INPUT_FILE)) {
            const suppliedCode = fs.readFileSync(CODE_INPUT_FILE, 'utf8').trim();
            if (suppliedCode) {
                fs.unlinkSync(CODE_INPUT_FILE);
                const otpInput = page.locator('input[type="tel"], input#idvPin, input[name="totpPin"], input[type="text"]').first();
                if (await otpInput.isVisible({ timeout: 2000 }).catch(() => false)) {
                    await otpInput.fill(suppliedCode);
                    await page.keyboard.press('Enter');
                    await page.waitForTimeout(4000);
                    continue;
                }
            }
        }

        const hasPasswordField = await page.locator('input[type="password"]').isVisible().catch(() => false);
        const bodyText = await page.locator('body').innerText().catch(() => '');
        writeAuthStatus('waiting_2fa_or_redirect', {
            url: currentUrl,
            promptText: bodyText.replace(/\s+/g, ' ').slice(0, 600)
        });

        if (!hasPasswordField) {
            await page.screenshot({ path: '/tmp/yt_auth_challenge.png' }).catch(() => {});
        }
        await page.waitForTimeout(3000);
    }

    throw new Error("2FA / Oturum açma zaman aşımına uğradı.");
}

async function openUploadModal(page) {
    await dismissStudioModalsIfPresent(page);

    // Yöntem 1: Sağ üst "+ Oluştur / Create" butonu veya doğrudan yükleme ikonu
    const createSelectors = [
        'ytcp-button#create-icon',
        '#create-icon',
        'button:has-text("Oluştur")',
        'button:has-text("Create")',
        'ytcp-icon-button#upload-icon',
        '#upload-icon',
        'button[aria-label*="Video yükle"]',
        'button[aria-label*="Upload videos"]'
    ];

    for (const sel of createSelectors) {
        const btn = page.locator(sel).first();
        if (await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
            console.log(`[*] Yükleme tetikleyicisine tıklanıyor (${sel})...`);
            await btn.click({ force: true });
            await page.waitForTimeout(1200);

            // Eğer zaten input[type="file"] eklendiyse tamam
            if (await page.locator('input[type="file"]').count() > 0) {
                return;
            }

            // Açılır menüden "Video yükle / Upload videos" seç
            const menuSelectors = [
                'tp-yt-paper-item#text-item-0',
                'ytcp-ve#upload-video-button',
                'tp-yt-paper-item:has-text("Video yükle")',
                'tp-yt-paper-item:has-text("Videoları yükle")',
                'tp-yt-paper-item:has-text("Upload videos")',
                '[role="menuitem"]:has-text("Video")',
                '[role="menuitem"]:has-text("Upload")'
            ];
            for (const ms of menuSelectors) {
                const item = page.locator(ms).first();
                if (await item.isVisible({ timeout: 1500 }).catch(() => false)) {
                    await item.click({ force: true });
                    await page.waitForTimeout(1500);
                    if (await page.locator('input[type="file"]').count() > 0) {
                        return;
                    }
                }
            }
        }
    }

    // Yöntem 2: Doğrudan kanal yükleme URL parametresi (?d=ud)
    const baseChannelUrl = page.url().split('?')[0].replace(/\/$/, '');
    const directUploadUrl = baseChannelUrl.includes('/channel/')
        ? `${baseChannelUrl}/videos/upload?d=ud`
        : 'https://www.youtube.com/upload';
    console.log(`[*] Doğrudan yükleme penceresi açılıyor: ${directUploadUrl}`);
    await page.goto(directUploadUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(4000);
    await dismissStudioModalsIfPresent(page);
}

async function fillContentEditable(page, containerSelector, value) {
    const candidates = [
        `${containerSelector} #textbox`,
        containerSelector
    ];
    for (const sel of candidates) {
        const box = page.locator(sel).first();
        if (await box.isVisible({ timeout: 15000 }).catch(() => false)) {
            await box.click({ force: true });
            await page.waitForTimeout(300);
            await page.keyboard.press('Control+A');
            await page.keyboard.press('Backspace');
            await page.keyboard.insertText(value);
            return;
        }
    }
    throw new Error(`Metin alanı bulunamadı: ${containerSelector}`);
}


// ============================================================================
// FAZ 11: VIRAL METADATA + AI KAPAK (THUMBNAIL) MOTORU
// ============================================================================

/** YouTube'un gunluk yukleme kotasinin dolup dolmadigini sayfa uzerinden kontrol eder. */
async function detectDailyUploadLimit(page, retries = 4, waitMs = 4000) {
    // Studio bu uyariyi birkac saniye gecikmeli basabiliyor -> birkac kez yeniden yokla.
    const markers = /günlük\s+yükleme\s+(sınır|limit)|yükleme\s+(sınırına\s+ulaşıldı|limiti)|daily\s+upload\s+limit|upload\s+limit\s+reached/i;
    for (let attempt = 0; attempt <= retries; attempt++) {
        try {
            const bodyText = await page.locator('body').innerText({ timeout: 5000 });
            if (markers.test(bodyText || '')) return true;
        } catch (_) {}
        try {
            const errorVisible = await page.locator(
                'ytcp-error, [class*="error-tip-container"], ytcp-video-upload-progress, [class*="ytcp-errors"]'
            ).first().innerText({ timeout: 3000 }).catch(() => '');
            if (markers.test(errorVisible || '')) return true;
        } catch (_) {}
        if (attempt < retries) await page.waitForTimeout(waitMs).catch(() => {});
    }
    return false;
}

/** Betikten gelen alanlari guvenli sekilde okur. */
function readScenarioField(scriptData, key, fallback = '') {
    const value = scriptData[key];
    if (value === undefined || value === null) return fallback;
    return String(value).trim();
}

/**
 * FAZ 11: Aciklamayi "viral" siralamayla kurar:
 *   [1] Affiliate CTA + link (Faz 9: en ustte)  [2] Etkilesim CTA (cta_line)
 *   [3] Govde metni                                [4] Tam 3 adet trend hashtag
 */
function buildFinalDescription(scriptData) {
    const desc = readScenarioField(scriptData, 'description');
    const affiliateCta = readScenarioField(scriptData, 'affiliate_cta');
    const affiliateLink = readScenarioField(scriptData, 'affiliate_link');
    const ctaLine = readScenarioField(scriptData, 'cta_line');
    const hashtags = (Array.isArray(scriptData.viral_hashtags) ? scriptData.viral_hashtags : [])
        .map(h => String(h).trim())
        .filter(Boolean)
        .slice(0, 3);

    const affiliateHook = readScenarioField(scriptData, 'affiliate_hook');

    const blocks = [];

    const top = [];
    // FAZ 12 SIRASI: [1] Affiliate hook/CTA+link -> [2] Etkilesim CTA -> [3] Govde -> [4] 3 hashtag
    if (affiliateHook) {
        top.push(affiliateHook);
    } else if (affiliateCta) {
        top.push(affiliateCta);
    } else if (affiliateLink) {
        top.push(`İncele: ${affiliateLink}`);
    }
    if (ctaLine) top.push(ctaLine);
    const topText = top.join('\n\n');
    if (topText && !desc.startsWith(topText)) {
        blocks.push(topText);
    }

    blocks.push(desc);

    const hashtagText = hashtags.join(' ');
    if (hashtagText && !desc.includes(hashtagText)) {
        blocks.push(hashtagText);
    }

    return blocks.filter(Boolean).join('\n\n').slice(0, 4900);
}

/** pollinations.ai (anahtarsiz, ucretsiz) ile dikey kapak uretir. Rate limit (402/429) olursa tekrar dener. */
async function generateAiThumbnail(prompt) {
    if (!prompt) return null;
    if (typeof fetch !== 'function') {
        console.log('[!] Bu Node surumunda global fetch yok, kapak uretilmedi (Node 18+ gerekir).');
        return null;
    }

    const seed = Math.floor(Math.random() * 1e9);
    // FAZ 12: Silahlandirilmis kapak promptu - CTR (tiklama orani) icin agresif gorsel dili.
    const STYLE_SUFFIX = [
        'YouTube Shorts thumbnail',
        'vertical 9:16',
        'single clear subject filling the frame',
        'subject large and centered, instantly recognizable',
        'bright well-lit subject, high contrast against the background',
        'no text, no letters, no logo, no end card, no split screen',
        'hyper-dramatic lighting',
        'vibrant colors',
        'glowing elements',
        'glowing arrows',
        'shocked expression',
        'mysterious or shocking focal point',
        '8k resolution',
        'cinematic',
        'highly detailed',
        'unreal engine 5 render',
        'dramatic shadows'
    ].join(', ');
    const encoded = encodeURIComponent(`${prompt}, ${STYLE_SUFFIX}`);
    const url = `https://image.pollinations.ai/prompt/${encoded}?width=1080&height=1920&nologo=true&model=flux&seed=${seed}`;
    const rawPath = path.join(os.tmpdir(), `yt_thumb_raw_${Date.now()}.jpg`);
    const finalPath = path.join(os.tmpdir(), `yt_thumb_${Date.now()}.jpg`);

    const retryDelays = [0, 3000];
    for (const delay of retryDelays) {
        if (delay > 0) {
            console.log(`[*] Kapak servisi meşgul (rate limit), ${delay / 1000}s sonra tekrar denenecek...`);
            await new Promise(r => setTimeout(r, delay));
        }
        try {
            const res = await fetch(url, {
                headers: { 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36' },
                signal: AbortSignal.timeout(15000)
            });
            if (res.status === 402) {
                console.log('[!] Kapak servisi ücret istiyor (HTTP 402); yerel yedeğe geçiliyor.');
                break;
            }
            if (res.status === 429) {
                console.log('[!] Kapak servisi rate limit döndü (HTTP 429).');
                continue;
            }
            if (!res.ok) {
                console.log(`[!] Kapak servisi HTTP ${res.status} döndü.`);
                continue;
            }
            const buffer = Buffer.from(await res.arrayBuffer());
            if (buffer.length < 8000) {
                console.log('[!] Kapak görseli boş geldi, atlanıyor.');
                continue;
            }
            fs.writeFileSync(rawPath, buffer);

            // YouTube minimum genislik 640 px ister -> ffmpeg ile 1080x1920'e buyut
            try {
                await new Promise((resolve, reject) => {
                    const ffmpeg = require('child_process').spawn('ffmpeg', [
                        '-y', '-i', rawPath,
                        '-vf', 'crop=iw:ih-52:0:0,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920',
                        '-q:v', '3', finalPath
                    ], { stdio: 'ignore' });
                    ffmpeg.on('error', reject);
                    ffmpeg.on('close', code => (code === 0 ? resolve() : reject(new Error(`ffmpeg ${code}`))));
                });
                fs.unlinkSync(rawPath);
                console.log(`[*] Kapak görseli 1080x1920 olarak hazırlandı (${Math.round(fs.statSync(finalPath).size / 1024)} KB).`);
                return finalPath;
            } catch (ffErr) {
                console.log(`[*] ffmpeg ile yeniden boyutlama yapılamadı (${ffErr.message}), ham görsel kullanılıyor.`);
                fs.copyFileSync(rawPath, finalPath);
                fs.unlinkSync(rawPath);
                return finalPath;
            }
        } catch (err) {
            console.log(`[!] Kapak indirme hatası: ${err.message}`);
        }
    }
    return null;
}

/** AI kapak servisi basarisiz oldugunda yerel yedek kapak uretir. */
function generateLocalFallbackThumbnail(title, topic, disableVision = false) {
    const outPath = path.join(os.tmpdir(), `yt_thumb_fallback_${Date.now()}.jpg`);
    const script = path.join(BASE_DIR, 'scripts', 'generate_fallback_thumbnail.py');
    try {
        // FAZ 13.3: video karesi (konu nesnesi) + konu rozeti ile uretilir.
        const args = [
            script,
            '--title', String(title || 'BILIM'),
            '--out', outPath,
            '--video', String(VIDEO_PATH || ''),
            '--topic', String(topic || ''),
            '--strict-subject', // uyumsuz rastgele kare yerine konu dogrulanamazsa metin karti
        ];
        const result = require('child_process').spawnSync(
            'python3',
            args,
            { encoding: 'utf-8', timeout: 120000, env: { ...process.env, GEMINI_FREE_VISION_ENABLED: disableVision ? '0' : (process.env.GEMINI_FREE_VISION_ENABLED || '0') } }
        );
        for (const line of (result.stdout || '').split('\n')) {
            if (line.startsWith('[KAPAK]')) console.log(line); // secret or full model response is never logged
        }
        if (result.status === 0 && fs.existsSync(outPath) && fs.statSync(outPath).size > 8000) {
            const detail = (result.stdout || '').match(/\(konu kareli\)|\(metin karti\)/);
            console.log(`[*] Yerel yedek kapak hazir (${Math.round(fs.statSync(outPath).size / 1024)} KB${detail ? ' ' + detail[0] : ''}).`);
            return outPath;
        }
        console.log(`[!] Yerel yedek kapak uretilemedi (${(result.stderr || '').trim().slice(0, 160)})`);
    } catch (err) {
        console.log(`[!] Yerel yedek kapak hatasi: ${err.message}`);
    }
    return null;
}

/** YouTube'un özel küçük resim sınırı, genel video yükleme sınırından ayrıdır. */
async function dismissThumbnailLimitDialog(page) {
    const text = await page.locator('body').innerText({ timeout: 5000 }).catch(() => '');
    const marker = /günlük\s+özel\s+küçük\s+resim\s+sınırına\s+ulaşıldı|daily\s+custom\s+thumbnail\s+limit\s+reached/i;
    if (!marker.test(text)) return false;
    console.log('[KAPAK] YouTube günlük özel kapak sınırına ulaşıldı; yerel kapak yüklenemedi. Kullanıcı seçimiyle otomatik kapakla devam edilecek.');
    const dialogs = page.locator('ytcp-dialog, tp-yt-paper-dialog, [role="dialog"]');
    for (let i = (await dialogs.count()) - 1; i >= 0; i--) {
        const dialog = dialogs.nth(i);
        if (!(await dialog.isVisible().catch(() => false))) continue;
        const dialogText = await dialog.innerText().catch(() => '');
        if (!marker.test(dialogText)) continue;
        const close = dialog.getByRole('button', { name: /^(Kapat|Close)$/i }).first();
        if (!(await close.isVisible().catch(() => false))) continue;
        await close.click({ timeout: 5000 });
        await page.waitForTimeout(1000);
        if (!(await dialog.isVisible().catch(() => false))) return true;
    }
    throw new Error('THUMBNAIL_QUOTA_DIALOG_BLOCKED: günlük özel kapak sınırı uyarısı kapatılamadı; yayın durduruldu');
}

/** YouTube Studio'daki "Küçük resim" (thumbnail) alanına özel kapağı yükler. */
async function uploadCustomThumbnail(page, thumbPath) {
    const input = page.locator(
        'ytcp-thumbnail-uploader input[type="file"], ' +
        'ytcp-video-thumbnail-editor input[type="file"], ' +
        'ytcp-video-custom-still-editor input[type="file"], ' +
        'input#file-loader'
    ).first();

    if (await input.count() === 0) {
        return { ok: false, reason: 'kapak dosya alanı bulunamadı' };
    }

    const previewBefore = await page.evaluate(() => {
        const editor = document.querySelector('ytcp-video-thumbnail-editor, ytcp-thumbnail-uploader, ytcp-video-custom-still-editor');
        return editor ? [...editor.querySelectorAll('img')].map(img => img.currentSrc || img.src).filter(Boolean).join('|') : '';
    });
    try {
        await input.setInputFiles(thumbPath);
    } catch (directErr) {
        // Yedek yol: "Kapak resmi" butonu -> file chooser
        console.log('[!] Doğrudan dosya yükleme başarısız, buton üzerinden deneniyor...');
        const thumbBtn = page.locator(
            'button[aria-label="Kapak resmi"], button[aria-label="Thumbnail"], ' +
            'ytcp-video-thumbnail-editor #custom-thumbnail-button'
        ).first();
        await thumbBtn.click({ timeout: 8000 });
        const [chooser] = await Promise.all([
            page.waitForEvent('filechooser', { timeout: 10000 }),
            page.locator('input[type="file"]').last().click({ force: true }).catch(() => {}),
        ]);
        await chooser.setFiles(thumbPath);
    }
    await page.waitForTimeout(5000);

    if (await dismissThumbnailLimitDialog(page)) {
        return { ok: false, dailyThumbnailLimit: true, reason: 'günlük özel kapak limiti; YouTube otomatik kapak seçimi' };
    }

    // Önizleme kontrolü yayınlamaz ve ana yayın/kaydet düğmesine dokunmaz.
    const previewAfter = await page.evaluate(() => {
        const editor = document.querySelector('ytcp-video-thumbnail-editor, ytcp-thumbnail-uploader, ytcp-video-custom-still-editor');
        return editor ? [...editor.querySelectorAll('img')].map(img => img.currentSrc || img.src).filter(Boolean).join('|') : '';
    });
    // Merely having an uploader DOM element or assigning files is not proof of success.
    if (!previewAfter || previewAfter === previewBefore) {
        return { ok: false, reason: 'kapak yükleme denendi; Studio önizleme değişimi doğrulanamadı' };
    }
    return { ok: true, customApplied: true };
}

/**
 * FAZ 3.5 (kapak karesi gomulu video): Studio'nun otomatik urettigi kare adaylari
 * arasindan output/cover.jpg'a en cok benzeyeni secer. Ayri kapak dosyasi YUKLEMEZ
 * (gunluk ozel kucuk resim kotasina girmez). Adaylar cikmazsa YouTube'un secimine birakir.
 * Donus: { ok, reason, index, distance }
 */
async function selectMatchingAutoStill(page, coverPath) {
    if (!coverPath || !fs.existsSync(coverPath)) {
        return { ok: false, reason: 'output/cover.jpg yok (FAZ 3.5 kapak gommemis)' };
    }
    const cellSelector = 'ytcp-video-thumbnail-editor ytcp-still-cell, ytcp-thumbnail-editor ytcp-still-cell, ytcp-still-cell';
    // Adaylar video islenirken gec gelir; en fazla 90 sn bekle.
    const deadline = Date.now() + 90000;
    const cells = page.locator(cellSelector);
    let count = 0;
    const readSrcs = () => cells.evaluateAll(els => els.map(e => { const i = e.querySelector('img'); return i ? (i.currentSrc || i.src || '') : ''; })).catch(() => []);
    while (Date.now() < deadline) {
        count = await cells.count().catch(() => 0);
        if (count > 0 && (await readSrcs()).some(Boolean)) break;
        await page.waitForTimeout(3000);
    }
    await page.screenshot({ path: path.join(BASE_DIR, 'logs', 'thumbnail_section.png'), fullPage: false }).catch(() => {});
    if (!count) return { ok: false, reason: 'Studio otomatik kare adayi gorunmedi (Shorts icin sunulmamis olabilir)' };

    const srcs = await readSrcs();
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'stills_'));
    const files = [];
    for (let i = 0; i < srcs.length; i++) {
        const src = srcs[i];
        if (!src) { files.push(''); continue; }
        try {
            let buf;
            if (src.startsWith('data:')) {
                buf = Buffer.from(src.split(',')[1] || '', 'base64');
            } else {
                const resp = await page.request.get(src, { timeout: 15000 });
                buf = Buffer.from(await resp.body());
            }
            const f = path.join(tmpDir, `still_${i}.img`);
            fs.writeFileSync(f, buf);
            files.push(f);
        } catch (_) { files.push(''); }
    }
    if (!files.some(Boolean)) return { ok: false, reason: `kare adaylari indirilemedi (${srcs.length} aday)` };

    const py = require('child_process').spawnSync('python3', [path.join(BASE_DIR, 'scripts', 'pick_matching_still.py'), coverPath, ...files], { encoding: 'utf8', timeout: 60000 });
    let best = null;
    try { best = JSON.parse((py.stdout || '').trim().split('\n').pop()); } catch (_) {}
    if (!best || typeof best.index !== 'number') {
        return { ok: false, reason: `benzerlik hesabi basarisiz (${(py.stderr || '').trim().slice(0, 120)})` };
    }
    const cell = cells.nth(best.index);
    await cell.scrollIntoViewIfNeeded().catch(() => {});
    await cell.click({ force: true, timeout: 10000 });
    await page.waitForTimeout(1200);
    const selected = await cell.evaluate(el => el.getAttribute('aria-checked') === 'true' || el.hasAttribute('selected') || el.classList.contains('selected') || el.getAttribute('aria-pressed') === 'true').catch(() => false);
    return { ok: true, index: best.index, distance: best.distance, matched: best.matched, selectedAttr: selected, total: srcs.length };
}

/** THUMBNAIL_MODE=custom: eski ozel kapak akisi (pollinations/PIL -> Studio'ya dosya yukleme). Davranis aynen korundu. */
async function legacyCustomThumbnailFlow(page, { title, thumbnailPrompt, scriptData }) {
        // --- FAZ 11: AI ile dikkat çekici kapak (thumbnail) oluşturuluyor ve yükleniyor ---
        console.log('[*] SİLAHLANDIRILMIŞ AI KAPAK (THUMBNAIL) ÜRETİLİYOR VE YÜKLENİYOR...');
    console.log('[*] AI ile dikkat çekici kapak (thumbnail) oluşturuluyor ve yükleniyor...');
        let thumbPath = null;
        // FAZ 12.6 / Islah 11: canli test modu -> AI kapak atlanir, yerel yedek kapak dogrudan kullanilir.
        const forceLocalThumbnail = String(process.env.FORCE_LOCAL_THUMBNAIL || '0') === '1';
        const skipThumbnail = false;
        const useFreeVision = !forceLocalThumbnail && !skipThumbnail && process.env.GEMINI_FREE_VISION_ENABLED === '1';

        if (skipThumbnail) {
            console.log('[KAPAK] SKIP_THUMBNAIL=1 -> thumbnail tamamen atlanıyor, video kapaksız yayınlanacak.');
        } else if (forceLocalThumbnail) {
            console.log('[!] FORCE_LOCAL_THUMBNAIL=1 -> AI kapak atlandi, yerel yedek kapak kullanilacak; Gemini da devre disi.');
        } else if (useFreeVision) {
            // Mevcut kareyi seçer; Google ile yeni görüntü üretmez. Uygun kare
            // yoksa aynı fonksiyon yerel temsili kart döndürür.
            console.log('[KAPAK] Ücretsiz Gemini kare incelemesi; doğrulanmamış seçim kapalıysa temsili yedek kullanılır. Görsel üretim API çağrılmaz.');
            thumbPath = generateLocalFallbackThumbnail(title, readScenarioField(scriptData, 'topic', ''));
        } else {
            try {
                thumbPath = await generateAiThumbnail(thumbnailPrompt);
            } catch (thumbErr) {
                console.log(`[!] Kapak üretimi başarısız: ${thumbErr.message}`);
            }
        }
        if (!thumbPath && !skipThumbnail) {
            // FAZ 12.6: AI kapak servisi rate limit verdi (HTTP 402) -> YEREL yedek kapak
            console.log('[!] AI kapak servisi basarisiz -> yerel yedek kapak deniyor...');
            thumbPath = generateLocalFallbackThumbnail(title, readScenarioField(scriptData, 'topic', ''), true);
            if (!thumbPath) {
                console.log('[!] Kapak resmi yüklenemedi, YouTube otomatik seçim yapacak.');
            }
        }
        if (thumbPath && !skipThumbnail) {
            try {
                const thumbResult = await uploadCustomThumbnail(page, thumbPath);
                if (thumbResult.ok) {
                    console.log('[KAPAK] Dosya gönderildi ve Studio önizlemesi değişti.');
                } else if (thumbResult.dailyThumbnailLimit) {
                    console.log('[KAPAK] Günlük thumbnail limiti dolmuş — video thumbnail\'siz devam ediyor.');
                    // Dialog kapandı, devam et — throw etme
                } else {
                    console.log(`[!] Kapak yüklenemedi (${thumbResult.reason}) — devam ediliyor.`);
                }
            } catch (thumbUploadErr) {
                // THUMBNAIL_QUOTA_DIALOG_BLOCKED dahil tüm thumbnail hatalarını yut
                console.log(`[!] Kapak yükleme hatası yutuldu (${thumbUploadErr.message.slice(0,80)}) — devam ediliyor.`);
            } finally {
                if (fs.existsSync(thumbPath)) {
                    try { fs.unlinkSync(thumbPath); } catch (_) {}
                }
            }
        }

}

async function uploadToYouTubeStudio() {
    const previousId = path.join(BASE_DIR, 'logs', 'channel_video_id.txt');
    if (fs.existsSync(previousId)) fs.unlinkSync(previousId);
    if (!fs.existsSync(VIDEO_PATH)) {
        console.error("[-] HATA: final_short.mp4 bulunamadı! Önce Python montaj hattını çalıştır.");
        process.exit(1);
    }
    if (!fs.existsSync(SCRIPT_PATH)) {
        console.error("[-] HATA: script.json bulunamadı!");
        process.exit(1);
    }

    const scriptData = JSON.parse(fs.readFileSync(SCRIPT_PATH, 'utf8'));
    const title = (scriptData.title || 'İlginç Bilgi #Shorts').slice(0, 100);
    // FAZ 11: Viral metadata kurulumu (affiliate CTA -> etkilesim CTA -> govde -> 3 hashtag)
    const description = buildFinalDescription(scriptData);
    const ctaLine = readScenarioField(scriptData, 'cta_line');
    const viralHashtags = (Array.isArray(scriptData.viral_hashtags) ? scriptData.viral_hashtags : [])
        .map(h => String(h).trim()).filter(Boolean).slice(0, 3);
    const thumbnailPrompt = readScenarioField(scriptData, 'thumbnail_prompt');
    if (ctaLine) console.log(`[*] Etkileşim CTA (açıklama üstü): ${ctaLine}`);
    if (viralHashtags.length) console.log(`[*] Trend hashtag'ler: ${viralHashtags.join(' ')}`);
    const tags = ['shorts', 'ilginçbilgiler', 'tarih', 'bilim', ...viralHashtags.map(h => h.replace('#', ''))]
        .filter(Boolean).join(',').slice(0, 500);

    const hasDisplay = Boolean(process.env.DISPLAY);
    const headlessMode = process.env.HEADLESS === 'true' ? true : !hasDisplay;
    const matrixChannelId = (process.env.MATRIX_CHANNEL_ID || '').trim();
    if (matrixChannelId && Number(matrixChannelId) > 1) {
        const staggerMs = (Number(matrixChannelId) - 1) * 10000;
        console.log(`[*] Matris Kanal #${matrixChannelId}: Paralel oturum çakışmasını önlemek için ${staggerMs / 1000}s kademeli başlatma...`);
        await new Promise(r => setTimeout(r, staggerMs));
    }

    console.log(`[*] Playwright Chromium başlatılıyor... (headless=${headlessMode})`);
    const hasLocalProfile = fs.existsSync(path.join(PROFILE_DIR, 'Default', 'Cookies'));
    let browser = null;
    let context = null;

    const commonArgs = [
        '--disable-blink-features=AutomationControlled',
        '--no-sandbox',
        '--disable-dev-shm-usage'
    ];
    const commonContextOpts = {
        viewport: { width: 1366, height: 900 },
        locale: 'tr-TR',
        userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        recordHar: { path: HAR_PATH, mode: 'minimal', content: 'omit' }
    };

    if (!hasLocalProfile && fs.existsSync(STORAGE_STATE_PATH)) {
        console.log("[*] CI modu: storage_state.json ile oturum bağlamı başlatılıyor...");
        browser = await chromium.launch({ headless: headlessMode, slowMo: 200, args: commonArgs });
        context = await browser.newContext({ ...commonContextOpts, storageState: STORAGE_STATE_PATH });
    } else {
        fs.mkdirSync(PROFILE_DIR, { recursive: true });
        context = await chromium.launchPersistentContext(PROFILE_DIR, {
            headless: headlessMode,
            slowMo: 200,
            ...commonContextOpts,
            args: commonArgs
        });
    }

    await context.addInitScript(() => {
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    });

    if (fs.existsSync(COOKIES_PATH)) {
        try {
            const cookies = JSON.parse(fs.readFileSync(COOKIES_PATH, 'utf8'));
            if (Array.isArray(cookies) && cookies.length > 0) {
                await context.addCookies(cookies);
                console.log("[*] Önceki oturum cookie'leri yüklendi.");
            }
        } catch (_) {}
    }

    const page = context.pages()[0] || await context.newPage();

    try {
        console.log("[*] YouTube Studio'ya gidiliyor...");
        await page.goto('https://studio.youtube.com/', { waitUntil: 'domcontentloaded', timeout: 45000 });
        await page.waitForTimeout(5000);

        if (!(await isAuthenticatedInStudio(page))) {
            await performGoogleLogin(page);
            if (!page.url().includes('studio.youtube.com')) {
                await page.goto('https://studio.youtube.com/', { waitUntil: 'domcontentloaded', timeout: 45000 });
                await page.waitForTimeout(5000);
            }
            await dismissStudioModalsIfPresent(page);
        } else {
            console.log(`[*] Kayıtlı oturum ile doğrudan YouTube Studio açıldı: ${page.url()}`);
        }

        // Oturum artefaktlarını hemen diske yaz (cookies.json + storage_state.json)
        await persistAllSessionArtifacts(context);

        await openUploadModal(page);

        console.log("[*] Video dosyası seçiliyor...");
        const fileInput = page.locator('input[type="file"]').first();
        await fileInput.waitFor({ state: 'attached', timeout: 45000 });
        await fileInput.setInputFiles(VIDEO_PATH);

        console.log("[*] Video yükleniyor, detaylar giriliyor... (Bu işlem video boyutuna göre 1-2 dakika sürebilir)");
        await page.waitForTimeout(2500);
        if (await detectDailyUploadLimit(page)) {
            console.log('[!] Uyarı: YouTube günlük yükleme kotanı dolu görünüyor (yayın adımında atlanacak).');
        }
        await page.locator('ytcp-social-suggestions-textbox#title-textarea #textbox').first().waitFor({ state: 'visible', timeout: 90000 });
        await page.waitForTimeout(1500);

        // İlk kez yüklemede çıkabilen küçük ipucu balonlarını kapat
        await page.locator('ytcp-feature-discovery-callout #dismiss-button').click({ timeout: 1500 }).catch(() => {});

        await fillContentEditable(page, 'ytcp-social-suggestions-textbox#title-textarea', title);
        await page.waitForTimeout(800);
        await fillContentEditable(page, 'ytcp-social-suggestions-textbox#description-textarea', description);
        await page.waitForTimeout(800);

        // --- KAPAK ---
        // Varsayilan (THUMBNAIL_MODE=frame): kapak FAZ 3.5'te videonun ilk 0.6 sn'sine gomuldu;
        // Studio'ya AYRI kapak dosyasi yuklenmez (gunluk ozel kucuk resim kotasi yok).
        // Studio otomatik kare adaylari sunarsa output/cover.jpg'a en yakin olani secilir.
        // THUMBNAIL_MODE=custom: eski yol (pollinations/PIL kapak -> Studio'ya dosya yukleme).
        const thumbnailMode = String(process.env.THUMBNAIL_MODE || 'frame').toLowerCase();
        const skipThumbnail = String(process.env.SKIP_THUMBNAIL || '0') === '1';
        if (skipThumbnail) {
            console.log('[KAPAK] SKIP_THUMBNAIL=1 -> kapak adimi tamamen atlandi.');
        } else if (thumbnailMode !== 'custom') {
            console.log('[KAPAK] Mod=frame: kapak video icine gomulu; Studio kare adaylari kontrol ediliyor (ayri dosya yuklenmez).');
            try {
                const stillResult = await selectMatchingAutoStill(page, path.join(BASE_DIR, 'output', 'cover.jpg'));
                if (stillResult.ok) {
                    console.log(`[KAPAK] Otomatik kare adayi secildi: #${stillResult.index + 1}/${stillResult.total} (fark=${stillResult.distance}, eslesme=${stillResult.matched ? 'evet' : 'zayif'}, secili-nitelik=${stillResult.selectedAttr}).`);
                } else {
                    console.log(`[KAPAK] Kare adayi secilemedi: ${stillResult.reason}. YouTube kendi karesini kullanacak (ilk kare = gomulu kapak).`);
                }
            } catch (stillErr) {
                console.log(`[KAPAK] Kare secimi hatasi yutuldu (${String(stillErr.message || stillErr).slice(0, 100)}); devam ediliyor.`);
            }
        } else {
            await legacyCustomThumbnailFlow(page, { title, thumbnailPrompt, scriptData });
        }

        // Thumbnail limiti veya diğer dialog'ları kapat, sayfayı normalleştir
        try {
            // Tüm açık dialog'ları kapat
            const dialogs = page.locator('ytcp-dialog, tp-yt-paper-dialog, [role="dialog"]');
            const dCount = await dialogs.count();
            for (let di = 0; di < dCount; di++) {
                const d = dialogs.nth(di);
                if (await d.isVisible().catch(() => false)) {
                    const closeBtn = d.locator('button:has-text("Kapat"), button:has-text("Close"), button:has-text("Tamam"), button:has-text("OK"), #close-button, ytcp-button[id="cancel-button"]').first();
                    if (await closeBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
                        await closeBtn.click({ force: true }).catch(() => {});
                    }
                }
            }
            await page.keyboard.press('Escape').catch(() => {});
            await page.waitForTimeout(2000);
        } catch (_) {}

        // Kota koruması: YouTube günlük yükleme limiti dolduysa boşuna uğraşma (kapak yüklendikten SONRA)
        if (await detectDailyUploadLimit(page)) {
            console.error('⏭️ YÜKLEME ATLANDI: YouTube günlük yükleme kotanı dolmuş (limit gece yarısı sıfırlanır).');
            writeAuthStatus('skipped_daily_limit', { title, thumbnail: thumbnailPrompt, channelUrl: page.url() });
            await page.screenshot({ path: path.join(BASE_DIR, 'logs', 'daily_limit.png') }).catch(() => {});
            process.exit(42);
        }

        // Studio bu alani zorunlu tutar. isVisible(timeout) beklemez: radio
        // gec render olursa eski kod secimi sessizce atlayip taslak birakiyordu.
        // Kanalin mevcut icerik politikasi: cocuklara ozel degil.
        const notForKids = page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').first();
        try {
            await notForKids.waitFor({ state: 'attached', timeout: 30000 });
            await notForKids.scrollIntoViewIfNeeded().catch(() => {});
            await page.waitForTimeout(1200); // overlay/animasyon bitmesini bekle
            // force:true: üst elementlerin intercept etmesi durumunda da tıkla
            if ((await notForKids.getAttribute('aria-checked').catch(() => null)) !== 'true') {
                await notForKids.click({ force: true, timeout: 15000 });
                await page.waitForTimeout(800);
            }
            // aria-checked doğrula; hâlâ false ise JS ile zorla set et
            const checked = await notForKids.getAttribute('aria-checked').catch(() => null);
            if (checked !== 'true') {
                await page.evaluate(() => {
                    const el = document.querySelector('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]');
                    if (el) { el.click(); el.setAttribute('aria-checked', 'true'); }
                });
                await page.waitForTimeout(600);
            }
            console.log("[*] 'Hayır, çocuklara özel değil' seçimi tamamlandı.");
        } catch (mfkErr) {
            console.error(`[!] MFK seçimi başarısız (devam ediliyor): ${mfkErr.message.slice(0,100)}`);
        }

        // Daha fazla göster -> Etiketler
        const toggleBtn = page.locator('ytcp-button#toggle-button, #toggle-button').first();
        await toggleBtn.scrollIntoViewIfNeeded().catch(() => {});
        if (await toggleBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
            await toggleBtn.click({ force: true });
            await page.waitForTimeout(1000);
            const tagInput = page.locator('ytcp-free-text-chip-bar input#text-input, input[aria-label*="Etiket"], input[aria-label*="Tags"]').first();
            if (await tagInput.isVisible({ timeout: 4000 }).catch(() => false)) {
                await tagInput.scrollIntoViewIfNeeded().catch(() => {});
                await tagInput.fill(tags);
                await page.keyboard.press('Enter');
                console.log("[*] Etiketler girildi.");
            }
        }

        console.log("[*] Görünürlük ayarı 'Herkese Açık' (Public) ekranına ilerleniyor...");
        const PUBLIC_RADIO_SEL = 'tp-yt-paper-radio-button[name="PUBLIC"]:visible, #public-radio-button:visible, input[value="PUBLIC"]:visible';

        // Önce video yüklemenin tamamlanmasını bekle (progress bar %100)
        for (let pw = 0; pw < 30; pw++) {
            const progressText = await page.locator('ytcp-video-upload-progress').innerText().catch(() => '');
            const publicVisible = await page.locator(PUBLIC_RADIO_SEL).first().isVisible({ timeout: 500 }).catch(() => false);
            if (publicVisible) { console.log('[*] PUBLIC zaten görünür, atlıyoruz.'); break; }
            if (/100\s*%|Kontroller.*tam|İşleme.*tam|upload.*complete/i.test(progressText) || !progressText) break;
            if (pw === 0) console.log(`[*] Video işleniyor, bekleniyor: ${progressText.replace(/\s+/g, ' ').trim().slice(0, 60)}`);
            await page.waitForTimeout(3000);
        }

        // Video upload + işleme tamamlanmasını bekle (max 5 dakika)
        console.log('[*] Video yükleme/işleme tamamlanması bekleniyor...');
        for (let pw = 0; pw < 60; pw++) {
            if (await page.locator(PUBLIC_RADIO_SEL).first().isVisible({ timeout: 500 }).catch(() => false)) {
                console.log('[*] PUBLIC zaten görünür.');
                break;
            }
            const progressText = await page.locator('ytcp-video-upload-progress').innerText().catch(() => '');
            const isComplete = !progressText ||
                /100\s*%|tamamland|complete|kontroller.*tamam|checks.*done|işleme.*tamam|processing.*done/i.test(progressText);
            if (pw % 5 === 0) console.log(`[*] Upload durumu: "${progressText.replace(/\s+/g,' ').trim().slice(0,60)}"`);
            if (isComplete) { console.log('[*] Upload/işleme tamamlandı.'); break; }
            await page.waitForTimeout(3000);
        }
        await page.waitForTimeout(1500);

        // "İleri" → "Sonraki" butonuna tıkla ve PUBLIC ekranının açılmasını bekle
        for (let attempt = 0; attempt < 25; attempt++) {
            if (await page.locator(PUBLIC_RADIO_SEL).first().isVisible({ timeout: 1000 }).catch(() => false)) {
                console.log(`[*] Görünürlük sekmesi açıldı (${attempt} tıklama sonrası).`);
                break;
            }
            const nextVariants = [
                'ytcp-button#next-button:not([disabled])',
                '#next-button:not([disabled])',
                'ytcp-button:has-text("Sonraki"):not([disabled])',
                'ytcp-button:has-text("Next"):not([disabled])',
                'ytcp-button:has-text("İleri"):not([disabled])',
                'ytcp-button#next-button',
                '#next-button',
            ];
            let clicked = false;
            for (const sel of nextVariants) {
                const btn = page.locator(sel).first();
                if (await btn.isVisible({ timeout: 600 }).catch(() => false)) {
                    await btn.scrollIntoViewIfNeeded().catch(() => {});
                    await btn.click({ force: true }).catch(() => {});
                    console.log(`[*] "İleri" tıklandı (deneme ${attempt + 1}).`);
                    clicked = true;
                    await page.waitForTimeout(attempt < 5 ? 2000 : 4000);
                    break;
                }
            }
            if (!clicked) {
                const pageTitle = await page.title().catch(() => '');
                console.log(`[*] "İleri" yok (deneme ${attempt + 1}), sayfa: "${pageTitle.slice(0,40)}", bekleniyor...`);
                await page.waitForTimeout(3000);
            }
        }

        // Herkese Açık (PUBLIC) seçeneğini işaretle - Faz 7 Tam Otonom Yayın!
        const publicRadio = page.locator(PUBLIC_RADIO_SEL).first();
        await publicRadio.scrollIntoViewIfNeeded().catch(() => {});
        try {
            await publicRadio.waitFor({ state: 'visible', timeout: 45000 });
        } catch (waitErr) {
            if (await detectDailyUploadLimit(page)) {
                console.error('⏭️ YÜKLEME ATLANDI: YouTube günlük yükleme kotanı dolmuş (limit gece yarısı sıfırlanır).');
                writeAuthStatus('skipped_daily_limit', { title, channelUrl: page.url() });
                await page.screenshot({ path: path.join(BASE_DIR, 'logs', 'daily_limit.png') }).catch(() => {});
                process.exit(42);
            }
            throw waitErr;
        }
        await publicRadio.click();
        await page.waitForFunction(
            el => el && (el.getAttribute('aria-checked') === 'true' || el.checked === true),
            await publicRadio.elementHandle(), { timeout: 10000 }
        );
        console.log("[*] Görünürlük 'PUBLIC (Herkese Açık)' seçimi doğrulandı.");

        // Olası ara onay/çocuk güvenliği diyaloglarını otomatik onayla
        const preConfirmDialog = page.locator('ytcp-confirmation-dialog, ytcp-confirmation-dialog-renderer').first();
        if (await preConfirmDialog.isVisible({ timeout: 2000 }).catch(() => false)) {
            const confirmBtn = preConfirmDialog.locator('ytcp-button#confirm-button, #confirm-button').first();
            if (await confirmBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
                await confirmBtn.click({ force: true });
                console.log("[*] Görünürlük onay penceresi kabul edildi.");
                await page.waitForTimeout(1000);
            }
        }

        // Video linkini yakala
        let videoUrl = '';
        const linkEl = page.locator('a[href*="youtube.com/shorts/"], a[href*="youtu.be/"]').first();
        if (await linkEl.isVisible({ timeout: 5000 }).catch(() => false)) {
            videoUrl = (await linkEl.getAttribute('href')) || '';
        }

        // Yüklemenin %100 tamamlandığından emin ol
        console.log("[*] Aktarımın %100 tamamlanması bekleniyor...");
        const uploadWaitDeadline = Date.now() + 180000;
        while (Date.now() < uploadWaitDeadline) {
            const progressText = await page.locator('ytcp-video-upload-progress').innerText().catch(() => '');
            const compactProg = progressText.replace(/\s+/g, ' ').trim();
            if (compactProg) {
                console.log(`[*] Durum: ${compactProg}`);
            }
            if (
                !compactProg ||
                ((/tamamlandı|complete|kontroller|checks|işleniyor|processing|sd|hd/i.test(compactProg)) &&
                !(/%\s*\d+|\d+\s*%|yükleniyor|uploading/i.test(compactProg)))
            ) {
                break;
            }
            await page.waitForTimeout(3000);
        }

        // Yayınla (Publish) butonuna tıkla
        const doneBtn = page.locator('ytcp-button#done-button').first();
        await doneBtn.waitFor({ state: 'visible', timeout: 30000 });
        await page.waitForFunction(() => {
            const button = document.querySelector('ytcp-button#done-button');
            return button && !button.hasAttribute('disabled') && button.getAttribute('aria-disabled') !== 'true';
        }, null, { timeout: 30000 });
        await doneBtn.click();
        console.log("[*] 'Yayınla' (Publish) butonuna tıklandı.");
        await page.waitForTimeout(3000);

        // Kontroller devam ederken çıkabilen 'Yine de yayınla / Publish anyway' veya onay penceresini geç
        const postPublishConfirmSelectors = [
            'ytcp-prechecks-warning-dialog ytcp-button#secondary-action-button',
            'ytcp-prechecks-warning-dialog #secondary-action-button',
            'ytcp-confirmation-dialog ytcp-button#confirm-button',
            'ytcp-confirmation-dialog-renderer ytcp-button#confirm-button',
            'button:has-text("Yine de yayınla")',
            'button:has-text("Publish anyway")',
            'ytcp-button#confirm-button'
        ];
        for (const sel of postPublishConfirmSelectors) {
            const btn = page.locator(sel).first();
            if (await btn.isVisible({ timeout: 1200 }).catch(() => false)) {
                await btn.click({ force: true });
                console.log(`[*] Yayın sonrası ek onay diyalogu geçildi: ${sel}`);
                await page.waitForTimeout(2500);
                break;
            }
        }

        await page.waitForTimeout(6000);
        if (!videoUrl) {
            const postLinkEl = page.locator('a[href*="youtube.com/shorts/"], a[href*="youtu.be/"]').first();
            if (await postLinkEl.isVisible({ timeout: 3000 }).catch(() => false)) {
                videoUrl = (await postLinkEl.getAttribute('href')) || '';
            }
        }
        await page.screenshot({ path: '/tmp/yt_upload_success.png' }).catch(() => {});
        // Yayın butonuna basılması veya işleniyor metni PUBLIC kanıtı değildir.
        // Studio içerik tablosunda tam video ID + PUBLIC durumu doğrulanmalıdır.
        const vidMatch = String(videoUrl || '').match(/[?&]v=([A-Za-z0-9_-]{11})(?:[&#]|$)/) ||
                         String(videoUrl || '').match(/\/(?:shorts|embed)\/([A-Za-z0-9_-]{11})(?:[?&#/]|$)/) ||
                         String(videoUrl || '').match(/youtu\.be\/([A-Za-z0-9_-]{11})(?:[?&#/]|$)/);
        const publishedId = vidMatch ? vidMatch[1] : '';
        const channelMatch = page.url().match(/\/channel\/(UC[A-Za-z0-9_-]{22})/);
        const channelId = channelMatch ? channelMatch[1] : '';
        let verifiedPublic = false;
        if (publishedId && channelId) {
            const checkPage = await context.newPage();
            try {
                for (let attempt = 0; attempt < 6; attempt++) {
                    await checkPage.goto(`https://studio.youtube.com/channel/${channelId}/videos/short`,
                        { waitUntil: 'domcontentloaded', timeout: 45000 });
                    const row = checkPage.locator(`ytcp-video-row:has(a[href*="/video/${publishedId}/"])`).first();
                    await row.waitFor({ state: 'visible', timeout: 10000 }).catch(() => {});
                    const icons = await row.locator('yt-icon.privacy-public-icon').count();
                    const labels = await row.locator('.icon-text-edit-triangle-wrap .label-span').allTextContents();
                    if (icons > 0 && labels.some(label => /^(herkese açık|public)$/i.test(label.trim()))) {
                        verifiedPublic = true;
                        break;
                    }
                    console.log(`[*] Studio PUBLIC doğrulaması bekleniyor (${attempt + 1}/6), video ID: ${publishedId}`);
                    await checkPage.waitForTimeout(5000);
                }
            } catch (verifyErr) {
                console.error(`[!] Studio görünürlük doğrulaması tamamlanamadı: ${verifyErr.message}`);
            } finally {
                await checkPage.close().catch(() => {});
            }
        }
        if (!verifiedPublic) {
            writeAuthStatus('publish_unverified', { title, videoUrl, videoId: publishedId, channelUrl: page.url() });
            throw new Error(`Yayın sonrası PUBLIC doğrulanamadı; tekrar yüklemeden Studio'yu kontrol edin. Video ID: ${publishedId || 'bilinmiyor'}`);
        }
        await persistAllSessionArtifacts(context);
        writeAuthStatus('upload_completed', { title, videoUrl, videoId: publishedId, visibility: 'PUBLIC', matrixChannelId: matrixChannelId || '1', channelUrl: page.url() });
        fs.mkdirSync(path.join(BASE_DIR, 'logs'), { recursive: true });
        fs.writeFileSync(path.join(BASE_DIR, 'logs', 'channel_video_id.txt'), publishedId);
        console.log(`[*] Yayınlanan video ID: ${publishedId}`);
        console.log('[+] YAYINLAMA İŞLEMİ ZORLANDI VE TAMAMLANDI! (Studio PUBLIC doğrulandı)');

        console.log("\n============================================================");
        console.log(" 🚀 PLAYWRIGHT TAM OTONOM YAYIN (PUBLIC) BAŞARILI! 🚀");
        console.log("============================================================");
        if (matrixChannelId) {
            console.log(` Matris Kanalı: #${matrixChannelId}`);
        }
        console.log(` Video: ${title}`);
        if (videoUrl) {
            console.log(` Link : ${videoUrl}`);
        }
        console.log(" Durum: PUBLIC (Herkese Açık) - Tam Otonom Yayınlandı!");
        console.log(" Not  : Kapak ve içerik kalitesi ayrıca kontrol edilmelidir.");
        console.log("============================================================\n");
    } catch (uploadErr) {
        const errShot = path.join(BASE_DIR, 'logs', 'studio_error.png');
        fs.mkdirSync(path.dirname(errShot), { recursive: true });
        await page.screenshot({ path: errShot }).catch(() => {});
        console.error("[-] Son URL:", page.url());
        // Kota doluysa bu bir HATA degil, planli bir atlama (exit 42)
        try {
            if (await detectDailyUploadLimit(page, 3, 3000)) {
                console.error('⏭️ YÜKLEME ATLANDI: YouTube günlük yükleme kotanı dolmuş (limit gece yarısı sıfırlanır).');
                writeAuthStatus('skipped_daily_limit', { title: title || '', channelUrl: page.url() });
                process.exit(42);
            }
        } catch (_) {}
        throw uploadErr;
    } finally {
        await context.close();
        if (browser) {
            await browser.close();
        }
        if (fs.existsSync(HAR_PATH)) {
            fs.chmodSync(HAR_PATH, 0o600);
        }
    }
}

uploadToYouTubeStudio().catch(err => {
    writeAuthStatus('error', { message: String(err && err.message ? err.message : err) });
    console.error("[-] KRİTİK HATA:", err);
    process.exit(1);
});
