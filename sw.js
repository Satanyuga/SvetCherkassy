const VERSION = '4';

self.addEventListener('install', (e) => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(clients.claim()));

// Память уведомлений (чтобы не дублировать)
const notified = new Set();

async function checkSchedules() {
    try {
        const r = await fetch('data.json?v=' + Date.now());
        const data = await r.json();
        
        const now = new Date();
        const kiev = new Date(now.toLocaleString("en-US", {timeZone: "Europe/Kiev"}));
        const curMin = kiev.getHours() * 60 + kiev.getMinutes();
        const dateKey = kiev.getDate();

        // Проверяем все группы, которые есть в базе
        for (const [group, sched] of Object.entries(data)) {
            const intervals = sched.match(/\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}/g) || [];
            
            intervals.forEach(range => {
                const [sStr, eStr] = range.split('-');
                const s = parseMin(sStr);
                const e = parseMin(eStr) || 1440;

                // Ключи, чтобы не спамить
                const offKey = `off-${group}-${s}-${dateKey}`;
                const onKey = `on-${group}-${e}-${dateKey}`;

                // Ровно за 15 минут
                if (s - curMin === 15 && !notified.has(offKey)) {
                    sendNotify("⚠️ Отключение!", `Группа ${group}: свет выключат через 15 мин (${sStr.trim()})`);
                    notified.add(offKey);
                }
                if (e - curMin === 15 && !notified.has(onKey)) {
                    sendNotify("💡 Включение!", `Группа ${group}: свет дадут через 15 мин (${eStr.trim()})`);
                    notified.add(onKey);
                }
            });
        }
    } catch (err) {
        console.error('BG Error:', err);
    }
}

function parseMin(t) {
    const p = t.trim().split(':');
    return parseInt(p[0]) * 60 + parseInt(p[1]);
}

function sendNotify(title, body) {
    self.registration.showNotification(title, {
        body: body,
        icon: 'https://cdn-icons-png.flaticon.com/512/2988/2988014.png',
        badge: 'https://cdn-icons-png.flaticon.com/512/2988/2988014.png',
        tag: 'svet-notif',
        renotify: true,
        requireInteraction: true
    });
}

// Запуск проверки каждые 30 секунд
setInterval(checkSchedules, 30000);
