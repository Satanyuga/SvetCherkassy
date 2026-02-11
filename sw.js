self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : { title: 'Внимание!', body: 'График изменился' };
  const options = {
    body: data.body,
    icon: 'https://cdn-icons-png.flaticon.com/512/2983/2983973.png',
    badge: 'https://cdn-icons-png.flaticon.com/512/2983/2983973.png',
    vibrate: [200, 100, 200]
  };
  event.waitUntil(self.registration.showNotification(data.title, options));
});
