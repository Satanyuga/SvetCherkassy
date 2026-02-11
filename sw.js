const CACHE_NAME = 'svet-v2';

// При установке активируемся сразу
self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
    console.log('Service Worker активирован');
});

// Проверка каждую минуту
setInterval(async () => {
    try {
        // У SW нет доступа к localStorage, поэтому мы просим данные у открытых окон
        const allClients = await clients.matchAll({type: 'window'});
        let group = "4.1"; // Дефолт

        // Пытаемся достать выбранную группу из первого попавшегося окна
        for (const client of allClients) {
            const clientGroup = await client.evaluate(() => localStorage.getItem('userGroup'));
            if (clientGroup) {
                group = clientGroup;
                break;
            }
        }

        const response = await fetch('data.json?v=' + Date.now());
        const data = await response.json();
        const sched = data[group];
        if (!sched) return;

        const now = new Date();
        const kiev = new Date(now.toLocaleString("en-US", {timeZone: "Europe/Kiev"}));
        const curMin = kiev.getHours() * 60 + kiev.getMinutes();

        const intervals = sched.match(/\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}/g) || [];
        
        intervals.forEach(range => {
            const [sStr, eStr] = range.split('-');
            const s = parseMin(sStr);
            const e = parseMin(eStr) || 1440;

            // За 15 минут до ВЫКЛЮЧЕНИЯ
            if (s - curMin === 15) {
                showNotify("⚠️ Скоро выключат!", `Группа ${group}: свет уйдёт через 15 минут (в ${sStr.trim()})`);
            }
            // За 15 минут до ВКЛЮЧЕНИЯ
            if (e - curMin === 15) {
                showNotify("💡 Готовься!", `Группа ${group}: свет дадут через 15 минут (в ${eStr.trim()})`);
            }
        });
    } catch (err) {
        console.error('Ошибка в фоне:', err);
    }
}, 60000);

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
        vibrate: [200, 100, 200]
    });
}
