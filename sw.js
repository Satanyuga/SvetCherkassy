const CACHE_NAME = 'svet-v10';
const notified = new Set();

self.addEventListener('install', (e) => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(clients.claim()));

async function checkSchedules() {
    try {
        // Добавляем случайное число, чтобы браузер не подсовывал старый файл
        const response = await fetch('data.json?v=' + Date.now());
        const data = await response.json();
        
        const now = new Date();
        const kiev = new Date(now.toLocaleString("en-US", {timeZone: "Europe/Kiev"}));
        const curMin = kiev.getHours() * 60 + kiev.getMinutes();
        const day = kiev.getDate();

        for (const [group, sched] of Object.entries(data)) {
            const intervals = sched.match(/\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}/g) || [];
            
            intervals.forEach(range => {
                const [sStr, eStr] = range.split('-');
                const s = parseMin(sStr);
                const e = parseMin(eStr) || 1440;

                const offKey = `off-${group}-${s}-${day}`;
                const onKey = `on-${group}-${e}-${day}`;

                // Проверка за 15 минут
                if (s - curMin === 15 && !notified.has(offKey)) {
                    sendNotify(`⚠️ Группа ${group}`, `Выключат через 15 мин (${sStr.trim()})`);
                    notified.add(offKey);
                }
                if (e - curMin === 15 && !notified.has(onKey)) {
                    sendNotify(`💡 Группа ${group}`, `Включат через 15 мин (${eStr.trim()})`);
                    notified.add(onKey);
                }
            });
        }
    } catch (err) {}
}

function parseMin(t) {
    const p = t.trim().split(':');
    return parseInt(p[0]) * 60 + parseInt(p[1]);
}

function sendNotify(title, msg) {
    self.registration.showNotification(title, {
        body: msg,
        icon: 'https://cdn-icons-png.flaticon.com/512/2988/2988014.png',
        badge: 'https://cdn-icons-png.flaticon.com/512/2988/2988014.png',
        tag: 'svet-alert',
        renotify: true,
        requireInteraction: true
    });
}

// Проверка трижды в минуту для надежности
setInterval(checkSchedules, 20000);
