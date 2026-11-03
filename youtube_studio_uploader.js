const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

const BASE_DIR = process.cwd();
const VIDEO_PATH = path.join(BASE_DIR, 'output', 'final_short.mp4');
const SCRIPT_PATH = path.join(BASE_DIR, 'script.json');
const COOKIES_PATH = path.join(BASE_DIR, 'cookies.json');
const STORAGE_STATE_PATH = path.join(BASE_DIR, 'storage_state.json');
const HAR_PATH = path.join(BASE_DIR, 'session.har');
const PROFILE_DIR = path.join(BASE_DIR, 'browser_profile');
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
    console.log("[*] Oturum cookie'leri ve storage_state kaydedildi. Bir sonraki çalıştırmada tam otomatik olacak.");
}

async function dismissStudioModalsIfPresent(page) {
    // Kanal henüz oluşturulmamışsa "Kanal oluştur / Create channel" modalını tamamla
    const createChannelSelectors = [
        'ytd-channel-creation-dialog-renderer #create-channel-button button',
        'ytd-channel-creation-dialog-renderer ytcp-button#create-channel-button',
        '#create-channel-button',
        'button:has-text("Create channel")',
        'button:has-text("Kanal oluştur")'
    ];
    for (const sel of createChannelSelectors) {
        const loc = page.locator(sel).first();
        if (await loc.isVisible({ timeout: 1500 }).catch(() => false)) {
            console.log(`[*] Yeni kanal oluşturma penceresi algılandı (${sel}), onaylanıyor...`);
            await loc.click().catch(() => {});
            await page.waitForTimeout(4000);
            break;
        }
    }

    // Hoş geldiniz / tanıtım pencerelerini kapat
    const dismissSelectors = [
        'ytcp-warm-welcome-dialog #dismiss-button',
        'ytcp-feature-discovery-callout #dismiss-button',
        'ytcp-button#dismiss-button',
        'button:has-text("Continue")',
        'button:has-text("Devam")'
    ];
    for (const sel of dismissSelectors) {
        const loc = page.locator(sel).first();
        if (await loc.isVisible({ timeout: 1000 }).catch(() => false)) {
            await loc.click().catch(() => {});
            await page.waitForTimeout(1000);
        }
    }
}

async function isStudioReady(page) {
    await dismissStudioModalsIfPresent(page);
    const selectors = [
        'ytcp-button#create-icon',
        '#create-icon',
        'ytcp-icon-button#upload-icon',
        '#upload-icon'
    ];
    for (const sel of selectors) {
        if (await page.locator(sel).first().isVisible({ timeout: 1500 }).catch(() => false)) {
            return true;
        }
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

    const emailInput = page.locator('input[type="email"], input#identifierId').first();
    await emailInput.waitFor({ state: 'visible', timeout: 30000 });
    await emailInput.fill(email);
    await page.locator('#identifierNext, button:has-text("Next"), button:has-text("İleri")').first().click();

    const passInput = page.locator('input[type="password"], input[name="Passwd"]').first();
    await passInput.waitFor({ state: 'visible', timeout: 30000 });
    await page.waitForTimeout(1200);
    await passInput.fill(password);
    await page.locator('#passwordNext, button:has-text("Next"), button:has-text("İleri")').first().click();

    console.log("[!] Kimlik doğrulama yanıtı ve varsa 2FA / telefon bildirimi bekleniyor...");
    await page.waitForTimeout(3500);

    // 2FA veya bildirim kontrol döngüsü (3 dakika)
    const deadline = Date.now() + 180000;
    while (Date.now() < deadline) {
        const currentUrl = page.url();

        if (currentUrl.includes('studio.youtube.com') || currentUrl.includes('youtube.com/channel')) {
            if (await isStudioReady(page)) {
                writeAuthStatus('authenticated', { url: currentUrl });
                return;
            }
        }

        // Google "Anladım / I understand / Not now / Şimdi değil" geçiş ekranları
        const skipBtns = [
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

        // Harici 2FA kodu dosyası bırakıldıysa otomatik gir
        if (fs.existsSync(CODE_INPUT_FILE)) {
            const suppliedCode = fs.readFileSync(CODE_INPUT_FILE, 'utf8').trim();
            if (suppliedCode) {
                fs.unlinkSync(CODE_INPUT_FILE);
                const otpInput = page.locator('input[type="tel"], input#idvPin, input[name="totpPin"], input[type="text"]').first();
                if (await otpInput.isVisible({ timeout: 2000 }).catch(() => false)) {
                    console.log("[*] Harici doğrulama kodu/yanıtı giriliyor...");
                    await otpInput.fill(suppliedCode);
                    await page.keyboard.press('Enter');
                    await page.waitForTimeout(4000);
                    continue;
                }
            }
        }

        // Ekrandaki bildirim metnini ve olası eşleşme sayısını oku (şifre alanı yokken!)
        const hasPasswordField = await page.locator('input[type="password"]').isVisible().catch(() => false);
        const bodyText = await page.locator('body').innerText().catch(() => '');
        const compactText = bodyText.replace(/\s+/g, ' ').slice(0, 600);
        writeAuthStatus('waiting_2fa_or_redirect', { url: currentUrl, promptText: compactText });

        if (!hasPasswordField) {
            await page.screenshot({ path: '/tmp/yt_auth_challenge.png' }).catch(() => {});
        }

        await page.waitForTimeout(3000);
    }

    throw new Error("2FA / Oturum açma zaman aşımına uğradı (180s).");
}

async function fillContentEditable(page, containerSelector, value) {
    const box = page.locator(`${containerSelector} #textbox, ${containerSelector}`).first();
    await box.waitFor({ state: 'visible', timeout: 60000 });
    await box.click();
    await page.keyboard.press('Control+A');
    await page.keyboard.press('Backspace');
    await page.keyboard.insertText(value);
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
    const description = (scriptData.description || '').slice(0, 4900);
    const tags = 'shorts,ilginçbilgiler,tarih,bilim';

    const hasDisplay = Boolean(process.env.DISPLAY);
    const headlessMode = process.env.HEADLESS === 'true' ? true : !hasDisplay;

    console.log(`[*] Playwright Chromium başlatılıyor... (headless=${headlessMode})`);
    fs.mkdirSync(PROFILE_DIR, { recursive: true });

    const context = await chromium.launchPersistentContext(PROFILE_DIR, {
        headless: headlessMode,
        slowMo: 250,
        viewport: { width: 1366, height: 900 },
        locale: 'tr-TR',
        userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        recordHar: { path: HAR_PATH, mode: 'minimal', content: 'omit' },
        args: [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage'
        ]
    });

    await context.addInitScript(() => {
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    });

    // Varsa eski cookie'leri yükle (Session bypass)
    if (fs.existsSync(COOKIES_PATH)) {
        try {
            const cookies = JSON.parse(fs.readFileSync(COOKIES_PATH, 'utf8'));
            if (Array.isArray(cookies) && cookies.length > 0) {
                await context.addCookies(cookies);
                console.log("[*] Önceki oturum cookie'leri yüklendi.");
            }
        } catch (e) {
            console.warn("[!] cookies.json okunamadı, temiz oturumla devam ediliyor.");
        }
    }

    const page = context.pages()[0] || await context.newPage();

    try {
        console.log("[*] YouTube Studio'ya gidiliyor...");
        await page.goto('https://studio.youtube.com/', { waitUntil: 'domcontentloaded', timeout: 45000 });
        await page.waitForTimeout(4000);

        if (!(await isStudioReady(page))) {
            await performGoogleLogin(page);
            if (!page.url().includes('studio.youtube.com')) {
                await page.goto('https://studio.youtube.com/', { waitUntil: 'domcontentloaded', timeout: 45000 });
                await page.waitForTimeout(4000);
            }
            await dismissStudioModalsIfPresent(page);
        }

        // Cookie ve oturum durumunu kaydet (Gelecekte tek seferde çalışması için)
        await persistAllSessionArtifacts(context);

        console.log("[*] Yükleme penceresi açılıyor...");
        const uploadIcon = page.locator('ytcp-icon-button#upload-icon, #upload-icon').first();
        if (await uploadIcon.isVisible({ timeout: 2500 }).catch(() => false)) {
            await uploadIcon.click();
        } else {
            await page.locator('ytcp-button#create-icon, #create-icon').first().click();
            await page.waitForTimeout(1000);
            await page.locator('tp-yt-paper-item#text-item-0, ytcp-ve#upload-video-button, tp-yt-paper-item:has-text("Video yükle"), tp-yt-paper-item:has-text("Upload videos")').first().click();
        }

        console.log("[*] Video dosyası seçiliyor...");
        const fileInput = page.locator('input[type="file"]').first();
        await fileInput.waitFor({ state: 'attached', timeout: 30000 });
        await fileInput.setInputFiles(VIDEO_PATH);

        console.log("[*] Video yükleniyor, detaylar giriliyor... (Bu işlem video boyutuna göre 1-2 dakika sürebilir)");
        await fillContentEditable(page, 'ytcp-social-suggestions-textbox#title-textarea', title);
        await page.waitForTimeout(800);
        await fillContentEditable(page, 'ytcp-social-suggestions-textbox#description-textarea', description);
        await page.waitForTimeout(800);

        // Çocuklara özel değil (Zorunlu YouTube Studio alanı!)
        const notForKids = page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').first();
        if (await notForKids.isVisible({ timeout: 10000 }).catch(() => false)) {
            await notForKids.click();
        }

        // Daha fazla göster -> Etiketler
        const toggleBtn = page.locator('ytcp-button#toggle-button, #toggle-button').first();
        if (await toggleBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
            await toggleBtn.click();
            await page.waitForTimeout(1000);
            const tagInput = page.locator('ytcp-free-text-chip-bar input#text-input, input[aria-label*="Etiket"], input[aria-label*="Tags"]').first();
            if (await tagInput.isVisible({ timeout: 4000 }).catch(() => false)) {
                await tagInput.fill(tags);
                await page.keyboard.press('Enter');
            }
        }

        console.log("[*] Görünürlük ayarı 'Gizli' (Private) yapılıyor...");
        for (let step = 0; step < 3; step++) {
            await page.locator('ytcp-button#next-button').click();
            await page.waitForTimeout(1200);
        }

        const privateRadio = page.locator('tp-yt-paper-radio-button[name="PRIVATE"], input[value="PRIVATE"]').first();
        await privateRadio.waitFor({ state: 'visible', timeout: 20000 });
        await privateRadio.click();
        await page.waitForTimeout(1000);

        // Video linkini yakala (varsa)
        let videoUrl = '';
        const linkEl = page.locator('a.style-scope.ytcp-video-info[href*="youtu"], a[href*="youtube.com/shorts/"], a[href*="youtu.be/"]').first();
        if (await linkEl.isVisible({ timeout: 3000 }).catch(() => false)) {
            videoUrl = (await linkEl.getAttribute('href')) || '';
        }

        // Yüklemenin %100 tamamlandığından emin ol
        console.log("[*] Aktarımın %100 tamamlanması bekleniyor...");
        const uploadWaitDeadline = Date.now() + 180000;
        while (Date.now() < uploadWaitDeadline) {
            const progressText = await page.locator('ytcp-video-upload-progress').innerText().catch(() => '');
            if (
                !progressText ||
                /tamamlandı|complete|checks complete|kontroller tamamlandı|işleniyor|processing|sd|hd/i.test(progressText) &&
                !/yükleniyor|uploading/i.test(progressText)
            ) {
                break;
            }
            await page.waitForTimeout(2000);
        }

        await page.locator('ytcp-button#done-button').click();
        await page.waitForTimeout(5000);

        await persistAllSessionArtifacts(context);
        writeAuthStatus('upload_completed', { title, videoUrl });

        console.log("\n============================================================");
        console.log(" 🚀 PLAYWRIGHT BACKDOOR YÜKLEME BAŞARILI! 🚀");
        console.log("============================================================");
        console.log(` Video: ${title}`);
        if (videoUrl) {
            console.log(` Link : ${videoUrl}`);
        }
        console.log(" Durum: PRIVATE (Gizli) - API Kotası Kullanılmadı!");
        console.log(" Not: YouTube Studio'dan manuel olarak 'Herkese Açık' yapabilirsin.");
        console.log("============================================================\n");
    } finally {
        await context.close();
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
