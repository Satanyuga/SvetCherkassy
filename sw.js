const CACHE_NAME = 'svet-v3';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

// Хранилище для отправленных уведомлений, чтобы не спамить каждую секунду
const sentNotifications = new Set();

setInterval(async () => {
    try {
        const response = await fetch('data.json?v=' + Date.now());
        const data = await response.json();
        
        // В SW нет localStorage, поэтому пробуем получить группу от активных вкладок
        const allClients = await clients.matchAll({type: 'window'});
        let currentGroup = null;
        
        for (const client of allClients) {
            // Передаем сообщение вкладке, чтобы она вернула свою группу
            client.postMessage({type: 'GET_GROUP'});
        }

        // В идеале группу надо хранить в IndexedDB, но для простоты 
        // мы будем проверять все группы из data.json, если у них подходит время
        const now = new Date();
        const kiev = new Date(now.toLocaleString("en-US", {timeZone: "Europe/Kiev"}));
        const curMin = kiev.getHours() * 60 + kiev.getMinutes();
        const curDay = kiev.getDate();

        for (const [group, sched] of Object.entries(data)) {
            const intervals = sched.match(/\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}/g) || [];
            
            intervals.forEach(range => {
                const [sStr, eStr] = range.split('-');
                const s = parseMin(sStr);
                const e = parseMin(eStr) || 1440;

                const offKey = `${group}-${s}-off-${curDay}`;
                const onKey = `${group}-${e}-on-${curDay}`;

                // Уведомление за 15 минут до выключения
                if (s - curMin === 15 && !sentNotifications.has(offKey)) {
                    showNotify("⚠️ Отключение!", `Группа ${group}: свет выключат через 15 минут.`);
                    sentNotifications.add(offKey);
                }
                
                // Уведомление за 15 минут до включения
                if (e - curMin === 15 && !sentNotifications.has(onKey)) {
                    showNotify("💡 Включение!", `Группа ${group}: свет дадут через 15 минут.`);
                    sentNotifications.add(onKey);
                }
            });
        }
    } catch (err) {
        console.error('SW Error:', err);
    }
}, 30000);

function parseMin(t) {
    if (!t) return 0;
    const p = t.trim().split(':');
    return parseInt(p[0]) * 60 + parseInt(p[1]);
}

function showNotify(title, body) {
    self.registration.showNotification(title, {
        body: body,
        icon: 'https://cdn-icons-png.flaticon.com/512/2988/2988014.png',
        badge: 'https://cdn-icons-png.flaticon.com/512/2988/2988014.png',
        vibrate: [300, 100, 300]
    });
}
