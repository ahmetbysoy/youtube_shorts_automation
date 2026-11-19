#!/usr/bin/env node
/**
 * FAZ 9: ANALİTİK GERİ BİLDİRİM DÖNGÜSÜ (analytics_scraper.js)
 * Playwright ile YouTube Studio'ya girer, son yüklenen Shorts videolarının
 * gerçek İzlenme (Views) ve Ortalama İzleme Süresi (Average View Duration) metriklerini kazır,
 * kazanan nişi (%50+ üstünlük kuralı) belirler ve `analytics_feedback.json` dosyasına yazar.
 */

const { chromium } = require('playwright');
const fs = require('fs');
const os = require('os');
const path = require('path');
require('dotenv').config();

const BASE_DIR = __dirname;
const COOKIES_PATH = path.join(BASE_DIR, 'cookies.json');
const STORAGE_STATE_PATH = path.join(BASE_DIR, 'storage_state.json');
const FEEDBACK_OUT_PATH = path.join(BASE_DIR, 'analytics_feedback.json');
const PROFILE_DIR = path.join(os.tmpdir(), 'yt_studio_analytics_profile');

function classifyNiche(title) {
    const t = String(title || '').toLowerCase();
    const spaceTokens = ['uzay', 'gezegen', 'güneş', 'venüs', 'neptün', 'uranüs', 'yıldız', 'nötron', 'voyager', 'astronot', 'galaksi', 'samanyolu', "ay'a", 'tunguska'];
    const historyTokens = ['tarih', 'savaş', 'antik', 'napolyon', 'göbeklitepe', 'pompeii', 'kleopatra', 'firavun', 'mısır', 'antikythera', 'zanzibar', 'krakatoa', 'emu', 'moğol', 'imparatorlu', 'orta çağ', 'oxford', 'roma', 'viking', 'olimpiyat', 'köle'];
    if (spaceTokens.some(tok => t.includes(tok))) return 'Uzay';
    if (historyTokens.some(tok => t.includes(tok))) return 'Tarih';
    return 'Bilim';
}

function parseMetricNumber(raw) {
    if (!raw) return 0;
    const cleaned = String(raw).replace(/\./g, '').replace(',', '.').trim();
    const m = cleaned.match(/(\d+(?:\.\d+)?)\s*([BbKkMm])?/);
    if (!m) return 0;
    let val = parseFloat(m[1]);
    const suffix = (m[2] || '').toUpperCase();
    if (suffix === 'B' || suffix === 'K') val *= 1000;
    if (suffix === 'M') val *= 1000000;
    return val;
}

function parseDurationSeconds(raw) {
    if (!raw) return 0;
    const m = String(raw).trim().match(/(\d+):(\d{2})/);
    if (!m) return 0;
    return parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
}

async function performGoogleLoginIfNeeded(page) {
    const email = (process.env.YT_EMAIL || '').trim();
    const password = (process.env.YT_PASSWORD || '').trim();
    if (!email || !password) return;

    if (page.url().includes('accountchooser')) {
        const accountTile = page.locator(`[data-identifier="${email}"], [data-email="${email}"]`).first();
        if (await accountTile.isVisible({ timeout: 5000 }).catch(() => false)) {
            await accountTile.click();
            await page.waitForTimeout(3000);
        }
    }

    const emailInput = page.locator('input[type="email"]');
    if (await emailInput.isVisible({ timeout: 4000 }).catch(() => false)) {
        await emailInput.fill(email);
        await page.keyboard.press('Enter');
        await page.waitForTimeout(3000);
    }

    const passInput = page.locator('input[type="password"]');
    if (await passInput.isVisible({ timeout: 10000 }).catch(() => false)) {
        await passInput.fill(password);
        await page.keyboard.press('Enter');
        await page.waitForTimeout(5000);
    }

    const deadline = Date.now() + 45000;
    while (Date.now() < deadline) {
        const u = page.url();
        if (u.includes('studio.youtube.com') && !u.includes('accounts.google.com')) return;
        if (!u.includes('accounts.google.com') && (u.includes('myaccount.google.com') || u.includes('gds.google.com') || u.includes('youtube.com'))) {
            await page.goto('https://studio.youtube.com/', { waitUntil: 'domcontentloaded', timeout: 45000 });
            await page.waitForTimeout(4000);
            if (page.url().includes('studio.youtube.com')) return;
        }
        await page.waitForTimeout(2000);
    }
}

async function scrapeStudioAnalytics() {
    const hasDisplay = Boolean(process.env.DISPLAY);
    const headlessMode = process.env.HEADLESS === 'true' ? true : !hasDisplay;
    const commonArgs = ['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-dev-shm-usage'];
    const commonContextOpts = {
        viewport: { width: 1366, height: 900 },
        locale: 'tr-TR',
        userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    };

    let browser = null;
    let context = null;
    if (fs.existsSync(STORAGE_STATE_PATH)) {
        browser = await chromium.launch({ headless: headlessMode, args: commonArgs });
        context = await browser.newContext({ ...commonContextOpts, storageState: STORAGE_STATE_PATH });
    } else {
        fs.mkdirSync(PROFILE_DIR, { recursive: true });
        context = await chromium.launchPersistentContext(PROFILE_DIR, { headless: headlessMode, ...commonContextOpts, args: commonArgs });
    }

    await context.addInitScript(() => {
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    });

    if (fs.existsSync(COOKIES_PATH)) {
        try {
            const cookies = JSON.parse(fs.readFileSync(COOKIES_PATH, 'utf8'));
            if (Array.isArray(cookies) && cookies.length > 0) await context.addCookies(cookies);
        } catch (_) {}
    }

    const page = context.pages()[0] || await context.newPage();

    try {
        console.log("[*] YouTube Studio İçerik & Analitik ekranına gidiliyor...");
        await page.goto('https://studio.youtube.com/', { waitUntil: 'domcontentloaded', timeout: 45000 });
        await page.waitForTimeout(5000);

        if (page.url().includes('accounts.google.com')) {
            await performGoogleLoginIfNeeded(page);
        }

        // Kanal kimliğini yakala ve doğrudan Shorts/Videolar sekmesine git
        const chMatch = page.url().match(/\/channel\/(UC[\w-]+)/);
        const channelId = chMatch ? chMatch[1] : '';
        if (channelId) {
            await page.goto(`https://studio.youtube.com/channel/${channelId}/videos/short`, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
            await page.waitForTimeout(5000);
        }

        // Tablodaki video satırlarını kazı (taslakları ve bozuk başlıkları filtrele)
        let videos = await page.evaluate(() => {
            const rows = Array.from(document.querySelectorAll('ytcp-video-row'));
            return rows.slice(0, 50).map(row => {
                const titleEl = row.querySelector('#video-title');
                const linkEl = row.querySelector('a[href*="/video/"]');
                const cells = Array.from(row.querySelectorAll('[role="cell"], .tablecell-views, .cell-body')).map(c => c.innerText.trim());
                const rawRowText = row.innerText || '';
                const href = linkEl ? linkEl.getAttribute('href') : '';
                const vidMatch = href ? href.match(/\/video\/([\w-]+)/) : null;
                const title = titleEl ? titleEl.textContent.trim() : '';
                const isDraft = /\b(taslak|draft)\b/i.test(rawRowText) || /^final short$/i.test(title) || title.length > 100;
                return {
                    videoId: vidMatch ? vidMatch[1] : '',
                    title,
                    isDraft,
                    cells,
                    rawRowText
                };
            }).filter(v => v.title && v.videoId && !v.isDraft);
        });

        // Eğer /videos/short sekmesinde satır yoksa genel /videos/upload listesini dene
        if (videos.length === 0 && channelId) {
            await page.goto(`https://studio.youtube.com/channel/${channelId}/videos/upload`, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
            await page.waitForTimeout(5000);
            videos = await page.evaluate(() => {
                const rows = Array.from(document.querySelectorAll('ytcp-video-row'));
                return rows.slice(0, 50).map(row => {
                    const titleEl = row.querySelector('#video-title');
                    const linkEl = row.querySelector('a[href*="/video/"]');
                    const cells = Array.from(row.querySelectorAll('[role="cell"], .tablecell-views, .cell-body')).map(c => c.innerText.trim());
                    const rawRowText = row.innerText || '';
                    const href = linkEl ? linkEl.getAttribute('href') : '';
                    const vidMatch = href ? href.match(/\/video\/([\w-]+)/) : null;
                    const title = titleEl ? titleEl.textContent.trim() : '';
                    const isDraft = /\b(taslak|draft)\b/i.test(rawRowText) || /^final short$/i.test(title) || title.length > 100;
                    return {
                        videoId: vidMatch ? vidMatch[1] : '',
                        title,
                        isDraft,
                        cells,
                        rawRowText
                    };
                }).filter(v => v.title && v.videoId && !v.isDraft);
            });
        }

        // Her satırın tablo izlenmesini önceden ayrıştır; izlenmesi >0 olan gerçek performanslı videoları öne al
        for (const v of videos) {
            let tableViews = 0;
            for (const c of v.cells.slice(2)) {
                if (/^\d[\d.,\s]*([BbKkMm])?$/.test(c)) {
                    tableViews = parseMetricNumber(c);
                    break;
                }
            }
            v.tableViews = tableViews;
        }
        const matureViews = videos.filter(v => v.tableViews >= 10).sort((a, b) => b.tableViews - a.tableViews);
        const withViews = videos.filter(v => v.tableViews > 0).sort((a, b) => b.tableViews - a.tableViews);
        const zeroViews = videos.filter(v => v.tableViews === 0);
        const candidateVideos = (
            matureViews.length >= 4 ? matureViews : (withViews.length >= 6 ? withViews : [...withViews, ...zeroViews])
        ).slice(0, 15);

        // ── FAZ 4H: Duplicate (aynı başlık / aynı videoId) temizle ──────────────
        // Studio tablosunda aynı başlık birden fazla video ID ile listelenebiliyor
        // (ör. Krakatoa). Bunlar kategori ortalamasını çift saymamalı.
        const seenIds = new Set();
        const seenTitleNorm = new Set();
        const normTitle = (t) => (t || '')
            .toLowerCase()
            .replace(/[#!?.',"`]/g, '')
            .replace(/\s+/g, ' ')
            .trim();
        const dedupVideos = [];
        const duplicateSkipped = [];
        for (const v of candidateVideos) {
            if (!v.videoId) continue;
            const nt = normTitle(v.title);
            if (seenIds.has(v.videoId)) { duplicateSkipped.push({reason:'videoId', v}); continue; }
            if (seenTitleNorm.has(nt))   { duplicateSkipped.push({reason:'title', v}); continue; }
            seenIds.add(v.videoId); seenTitleNorm.add(nt);
            dedupVideos.push(v);
        }
        if (duplicateSkipped.length) {
            console.log(`[ANALİTİK] Tekrarlayan videolar elendi (${duplicateSkipped.length}):`);
            for (const d of duplicateSkipped) console.log(`   - [${d.reason}] ${d.v.videoId} :: ${d.v.title}`);
        }

        const enrichedVideos = [];
        // En yüksek performanslı ilk 6 videonun tekil analitik sayfasından Ortalama İzleme Süresi (AVD) bilgisini de çek
        for (let idx = 0; idx < dedupVideos.length; idx++) {
            const v = dedupVideos[idx];
            let views = v.tableViews || 0;
            let avgViewDurationSec = null;  // null = ölçülemedi (0 gerçek 0'dan farklı)
            if (v.videoId && idx < 6) {
                await page.goto(`https://studio.youtube.com/video/${v.videoId}/analytics/tab-overview/period-default`, {
                    waitUntil: 'domcontentloaded',
                    timeout: 30000
                }).catch(() => {});
                await page.waitForTimeout(3000);
                const metricCards = await page.evaluate(() => {
                    return Array.from(document.querySelectorAll('yta-key-metric-card, yta-key-metric-block, #metric-total'))
                        .map(el => (el.innerText || '').replace(/\s+/g, ' ').trim());
                }).catch(() => []);

                for (const card of metricCards) {
                    if (/görüntüleme|views/i.test(card) && !/süre|duration|saat|hours/i.test(card)) {
                        const numMatch = card.match(/(\d[\d.,]*\s*[BbKkMm]?)/);
                        if (numMatch) views = Math.max(views, parseMetricNumber(numMatch[1]));
                    }
                    if (/ortalama görüntüleme süresi|average view duration/i.test(card)) {
                        const durMatch = card.match(/(\d+:\d{2})/);
                        if (durMatch) avgViewDurationSec = parseDurationSeconds(durMatch[1]);
                    }
                }
            }

            const niche = classifyNiche(v.title);
            // AVD null iken composite skora dahil ETME; yalnızca views kullan.
            // Eksik AVD verisi 0 diye şişirilmesin, 0'la bölme/yanlı skor üretilmesin.
            const compositeScore = (avgViewDurationSec != null)
                ? Number((views + avgViewDurationSec * 0.5).toFixed(2))
                : Number(views.toFixed(2));
            enrichedVideos.push({
                videoId: v.videoId,
                title: v.title,
                niche,
                views,
                avgViewDurationSec,
                avgViewDurationAvailable: avgViewDurationSec != null,
                compositeScore,
            });
            const avdStr = (avgViewDurationSec != null) ? `${avgViewDurationSec.toFixed(1)}s` : 'null';
            console.log(`[ANALİTİK] ${v.videoId} | Niş=${niche} | İzlenme=${views} | Ort.Süre=${avdStr} | ${v.title}`);
        }

        // Niş bazlı ortalamaları hesapla (null AVD'yi ortalamaya DAHİL ETME)
        const nicheMap = {};
        for (const item of enrichedVideos) {
            if (!nicheMap[item.niche]) nicheMap[item.niche] = {
                count: 0, totalViews: 0, totalAvd: 0, avdCount: 0, totalScore: 0,
            };
            const s = nicheMap[item.niche];
            s.count += 1;
            s.totalViews += item.views;
            s.totalScore += item.compositeScore;
            if (item.avgViewDurationSec != null) {
                s.totalAvd += item.avgViewDurationSec;
                s.avdCount += 1;
            }
        }

        const MIN_VIDEOS_FOR_BOOST = 4;
        const topicScores = Object.entries(nicheMap).map(([niche, s]) => {
            const avgViews = s.totalViews / s.count;
            const avgAvd = s.avdCount > 0 ? s.totalAvd / s.avdCount : null;
            return {
                niche,
                video_count: s.count,
                avg_views: Number(avgViews.toFixed(2)),
                avg_view_duration_sec: (avgAvd != null) ? Number(avgAvd.toFixed(2)) : null,
                avg_view_duration_sample_size: s.avdCount,
                avg_score: Number((s.totalScore / s.count).toFixed(2)),
                statistically_reliable: s.count >= MIN_VIDEOS_FOR_BOOST,
            };
        }).sort((a, b) => b.avg_score - a.avg_score);

        // ── FAZ 4E: Sifir video / yetersiz veri / login hatasi durumunda eski gecerli
        // raporu KORU; "winning_topic=Uzay" sahte varsayilanini yazma.
        const onLoginPage = page.url().includes('accounts.google.com');
        const notEnoughData = enrichedVideos.length === 0 || topicScores.length === 0;
        if (onLoginPage || notEnoughData) {
            const reason = onLoginPage ? 'login_required' : 'insufficient_data';
            // Eski raporu koru
            if (fs.existsSync(FEEDBACK_OUT_PATH)) {
                try {
                    const prev = JSON.parse(fs.readFileSync(FEEDBACK_OUT_PATH, 'utf8'));
                    if (prev && prev.videos_analyzed && prev.videos_analyzed >= 3) {
                        console.warn(`[!] ${reason}: yeni rapor yazilmiyor, onceki gecerli rapor korundu (videos_analyzed=${prev.videos_analyzed})`);
                        return;
                    }
                } catch (_) { /* onceki rapor bozuksa asagi yeni tane yaz */ }
            }
            const report = {
                scraped_at: new Date().toISOString(),
                channel_id: channelId,
                videos_analyzed: 0,
                status: reason,
                winning_topic: null,
                boost_active: false,
                outperformance_ratio: 1.0,
                discarded_topics: [],
                optimization_directive: 'Yetersiz analitik verisi (sifir video veya oturum acik degil); eski skorlar korunuyor.',
                topic_scores: [],
                recent_videos: [],
            };
            fs.writeFileSync(FEEDBACK_OUT_PATH, JSON.stringify(report, null, 2), 'utf8');
            console.error(`[!] Analitik verisi yetersiz: ${reason}. Rapor '${reason}' olarak isaretlendi.`);
            return;
        }

        // ── FAZ 4H: Kazanan nişi belirle (küçük örneklemde boost YAPMA) ───────
        // Agresif kategori optimizasyonu yanlış sinyale yol açabiliyor
        // (Krakatoa duplicate'i "Tarih"i yapay olarak zirveye taşıyordu gibi).
        // Boost'u yalnızca:
        //   - en az MIN_VIDEOS_FOR_BOOST video ile
        //   - ikinciye göre en az %20 üstün performansla
        //   - video_count diğer kategorilerden de düşük değilse
        // aktif et. Aksi durumda dengeli dağılımı koru.
        const winningTopic = topicScores[0].niche;
        let boostActive = false;
        let outperformanceRatio = 1.0;
        const discardedTopics = [];
        let optimizationDirective = 'Tüm konularda dengeli yüksek dopaminli kanca (hook) üretimine devam et.';
        let boostReason = 'baseline_balanced';

        if (topicScores.length >= 2) {
            const top = topicScores[0];
            const second = topicScores[1];
            const denom = second.avg_score > 0 ? second.avg_score : 1;
            outperformanceRatio = Number(((top.avg_score || 0) / denom).toFixed(2));
            const reliable = top.statistically_reliable && second.statistically_reliable;
            const clearWinner = outperformanceRatio >= 1.20 && top.avg_score > 0;
            if (reliable && clearWinner && outperformanceRatio >= 1.30) {
                boostActive = true;
                boostReason = `reliable+${(outperformanceRatio-1)*100|0}pc_lead`;
                optimizationDirective = `Önceki dönem '${top.niche}' kategorisi anlamlı farkla önde (${top.avg_views} vs ${second.avg_views}, n=${top.video_count}/${second.video_count}), yeni senaryoların ağırlığı bu kategoriye kaydırılsın.`;
                const worst = topicScores[topicScores.length - 1];
                if (worst.statistically_reliable && worst.niche !== top.niche && worst.avg_score * 1.3 <= top.avg_score) {
                    discardedTopics.push(worst.niche);
                }
            } else if (!reliable) {
                boostReason = `insufficient_sample(top=${top.video_count},second=${second.video_count})`;
                optimizationDirective = `En yüksek skor '${top.niche}' görünse de örneklem küçük (n=${top.video_count}); agresif kategori kayması YAPILMIYOR, dengeli dağılım korunuyor.`;
            } else {
                boostReason = 'no_clear_lead';
                optimizationDirective = `Kategoriler arası performans farkı ${((outperformanceRatio-1)*100|0)}% (eşik %30); boost YAPILMIYOR, dengeli dağılım korunuyor.`;
            }
        }

        // AVD örneklem durumu (veri kalitesi)
        const avdTotal = enrichedVideos.filter(v => v.avgViewDurationAvailable).length;
        const report = {
            scraped_at: new Date().toISOString(),
            channel_id: channelId,
            videos_analyzed: enrichedVideos.length,
            duplicates_removed: duplicateSkipped.length,
            status: 'ok',
            winning_topic: winningTopic,
            boost_active: boostActive,
            boost_reason: boostReason,
            outperformance_ratio: outperformanceRatio,
            discarded_topics: discardedTopics,
            optimization_directive: optimizationDirective,
            data_quality: {
                avg_view_duration_available_count: avdTotal,
                avg_view_duration_total: enrichedVideos.length,
                note: avdTotal === 0
                    ? 'Ortalama izleme süresi Studio metrik kartından okunamadı (muhtemelen yeni video/erişim yok); AVD sıfır değil null olarak kaydedildi, kategori skoruna dahil edilmedi.'
                    : `Ortalama izleme süresi ${avdTotal}/${enrichedVideos.length} videoda ölçülebildi.`,
                min_videos_per_niche_for_boost: MIN_VIDEOS_FOR_BOOST,
            },
            topic_scores: topicScores,
            recent_videos: enrichedVideos,
        };

        fs.writeFileSync(FEEDBACK_OUT_PATH, JSON.stringify(report, null, 2), 'utf8');
        console.log(`[+] Faz 9 analitik raporu yazildi: ${FEEDBACK_OUT_PATH}`);
        console.log(`[*] Kazanan niş: ${winningTopic} | Direktif: ${optimizationDirective}`);
    } finally {
        await context.close();
        if (browser) await browser.close();
    }
}

scrapeStudioAnalytics().catch(err => {
    console.error("[-] ANALİTİK KAZIMA HATASI:", err);
    process.exit(1);
});
