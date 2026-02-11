self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open('svet-store').then((cache) => cache.addAll([
      '/',
      '/index.html',
      '/data.json'
    ])),
  );
});

self.addEventListener('fetch', (e) => {
  e.respondWith(
    caches.match(e.request).then((response) => response || fetch(e.request)),
  );
});
