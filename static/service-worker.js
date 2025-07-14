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

self.addEventListener('install', function (event) {
  console.log('[ServiceWorker] Installed');
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  console.log('[ServiceWorker] Activated');
});

self.addEventListener('fetch', function (event) {
  event.respondWith(fetch(event.request));
});
