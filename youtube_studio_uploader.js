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

    const blocks = [];

    const top = [];
    if (affiliateCta) {
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
    const encoded = encodeURIComponent(`${prompt}, vertical 9:16 aspect ratio, highly detailed, vibrant colors, youtube shorts thumbnail style`);
    const url = `https://image.pollinations.ai/prompt/${encoded}?width=1080&height=1920&nologo=true&model=flux&seed=${seed}`;
    const rawPath = path.join(os.tmpdir(), `yt_thumb_raw_${Date.now()}.jpg`);
    const finalPath = path.join(os.tmpdir(), `yt_thumb_${Date.now()}.jpg`);

    const retryDelays = [0, 12000, 30000, 60000];
    for (const delay of retryDelays) {
        if (delay > 0) {
            console.log(`[*] Kapak servisi meşgul (rate limit), ${delay / 1000}s sonra tekrar denenecek...`);
            await new Promise(r => setTimeout(r, delay));
        }
        try {
            const res = await fetch(url, {
                headers: { 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36' }
            });
            if (res.status === 402 || res.status === 429) {
                console.log(`[!] Kapak servisi rate limit döndü (HTTP ${res.status}).`);
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

    await input.setInputFiles(thumbPath);
    await page.waitForTimeout(5000);

    // Dogrulama: onizleme gorseli degisti mi? (otomatik secilen kare ile ayni olmamali)
    const applied = await page.evaluate(() => {
        const editor = document.querySelector('ytcp-video-thumbnail-editor');
        if (!editor) return false;
        const custom = editor.querySelector('ytcp-video-custom-still-editor');
        return !!custom;
    });
    return { ok: true, customApplied: applied };
}

async function uploadToYouTubeStudio() {
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

        // --- FAZ 11: AI ile dikkat çekici kapak (thumbnail) oluşturuluyor ve yükleniyor ---
        console.log('[*] AI ile dikkat çekici kapak (thumbnail) oluşturuluyor ve yükleniyor...');
        let thumbPath = null;
        try {
            thumbPath = await generateAiThumbnail(thumbnailPrompt);
        } catch (thumbErr) {
            console.log(`[!] Kapak üretimi başarısız: ${thumbErr.message}`);
        }
        if (!thumbPath) {
            console.log('[!] Kapak resmi yüklenemedi, YouTube otomatik seçim yapacak. (Manuel müdahale gerekebilir)');
        } else {
            try {
                const thumbResult = await uploadCustomThumbnail(page, thumbPath);
                if (thumbResult.ok) {
                    console.log('[+] Kapak resmi başarıyla yüklendi.');
                } else {
                    console.log(`[!] Kapak resmi yüklenemedi, YouTube otomatik seçim yapacak. (Sebep: ${thumbResult.reason})`);
                }
            } catch (thumbUploadErr) {
                console.log(`[!] Kapak resmi yüklenemedi, YouTube otomatik seçim yapacak. (Hata: ${thumbUploadErr.message})`);
            } finally {
                if (fs.existsSync(thumbPath)) {
                    try { fs.unlinkSync(thumbPath); } catch (_) {}
                }
            }
        }

        // Kota koruması: YouTube günlük yükleme limiti dolduysa boşuna uğraşma (kapak yüklendikten SONRA)
        if (await detectDailyUploadLimit(page)) {
            console.error('⏭️ YÜKLEME ATLANDI: YouTube günlük yükleme kotanı dolmuş (limit gece yarısı sıfırlanır).');
            writeAuthStatus('skipped_daily_limit', { title, thumbnail: thumbnailPrompt, channelUrl: page.url() });
            await page.screenshot({ path: path.join(BASE_DIR, 'logs', 'daily_limit.png') }).catch(() => {});
            process.exit(42);
        }

        // Çocuklara özel değil (Zorunlu YouTube Studio alanı!)
        const notForKids = page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').first();
        await notForKids.scrollIntoViewIfNeeded().catch(() => {});
        if (await notForKids.isVisible({ timeout: 10000 }).catch(() => false)) {
            await notForKids.click({ force: true });
            console.log("[*] 'Hayır, çocuklara özel değil' seçildi.");
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
        for (let step = 0; step < 3; step++) {
            const nextBtn = page.locator('ytcp-button#next-button').first();
            if (await nextBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
                await nextBtn.click({ force: true });
                await page.waitForTimeout(1500);
            }
        }

        // Herkese Açık (PUBLIC) seçeneğini işaretle - Faz 7 Tam Otonom Yayın!
        const publicRadio = page.locator('tp-yt-paper-radio-button[name="PUBLIC"], #public-radio-button, input[value="PUBLIC"]').first();
        await publicRadio.scrollIntoViewIfNeeded().catch(() => {});
        try {
            await publicRadio.waitFor({ state: 'visible', timeout: 25000 });
        } catch (waitErr) {
            if (await detectDailyUploadLimit(page)) {
                console.error('⏭️ YÜKLEME ATLANDI: YouTube günlük yükleme kotanı dolmuş (limit gece yarısı sıfırlanır).');
                writeAuthStatus('skipped_daily_limit', { title, channelUrl: page.url() });
                await page.screenshot({ path: path.join(BASE_DIR, 'logs', 'daily_limit.png') }).catch(() => {});
                process.exit(42);
            }
            throw waitErr;
        }
        await publicRadio.click({ force: true });
        console.log("[*] Görünürlük 'PUBLIC (Herkese Açık)' olarak işaretlendi.");
        await page.waitForTimeout(1500);

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
        await doneBtn.click({ force: true });
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
        await page.locator('ytcp-video-share-dialog ytcp-button#close-button, ytcp-uploads-still-processing-dialog ytcp-button#close-button').first().click({ timeout: 2500 }).catch(() => {});

        await persistAllSessionArtifacts(context);
        writeAuthStatus('upload_completed', { title, videoUrl, visibility: 'PUBLIC', matrixChannelId: matrixChannelId || '1', channelUrl: page.url() });

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
        console.log(" Not  : Sıfır API kotası, sıfır manuel müdahale ile yayında.");
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
