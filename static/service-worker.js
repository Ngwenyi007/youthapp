const CACHE_NAME = 'youth-app-cache-v1';
const urlsToCache = [
  '/',
  '/dashboard',
  '/static/style.css',
  '/static/script.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/manifest.json'
];

self.addEventListener('install', function (e) {
  console.log('Service Worker installed');
  e.waitUntil(
    caches.open('youthapp-cache').then(function (cache) {
      return cache.addAll([
        '/',
        '/static/styles.css',
        '/static/icons/icon-192.png',
        '/static/icons/icon-512.png'
      ]);
    })
  );
});

self.addEventListener('fetch', function (e) {
  e.respondWith(
    caches.match(e.request).then(function (response) {
      return response || fetch(e.request);
    })
  );
});
