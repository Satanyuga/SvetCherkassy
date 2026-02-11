const CACHE_NAME = 'svet-v1';

self.addEventListener('install', (e) => {
    self.skipWaiting();
});

// Проверка уведомлений каждые 60 секунд в фоне
setInterval(async () => {
    const group = await getSavedGroup();
    if (!group) return;

    const res = await fetch('data.json');
    const data = await res.json();
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

        // За 15 минут до выключения
        if (s - curMin === 15) {
            showNotify("Внимание!", `Свет выключат через 15 минут (в ${sStr})`);
        }
        // За 15 минут до включения
        if (e - curMin === 15) {
            showNotify("Ура!", `Свет включат через 15 минут (в ${eStr})`);
        }
    });
}, 60000);

function parseMin(t) {
    const p = t.trim().split(':');
    return parseInt(p[0]) * 60 + parseInt(p[1]);
}

async function getSavedGroup() {
    // В SW нет localStorage, используем трюк или просто ждем когда вкладка активна
    // Для GitHub Pages уведомления в фоне работают лучше через Push API, 
    // но это "локальный" костыль для проверки.
    return "4.1"; // Пока захардкодим 4.1 для теста, если не прокидывать через БД
}

function showNotify(title, body) {
    self.registration.showNotification(title, {
        body: body,
        icon: 'icon-192.png', // убедись что иконка есть в манифесте
        badge: 'icon-192.png'
    });
}
