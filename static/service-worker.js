const CACHE_NAME = 'attendance-uae-cache-v1';
const urlsToCache = [
  '/',
  '/static/logo.png',
  '/static/success-sound.mp3',
  '/static/manifest.json',
  '/static/favicon.ico',
  '/static/icon-192x192.png',
  '/static/icon-512x512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return fetch('/static/manifest.json').then(response => {
        if (response.status === 200) {
          return cache.addAll(urlsToCache);
        } else {
          console.log('Manifest fetch failed:', response.status);
        }
      }).catch(function(error) {
        console.error('Failed to cache manifest:', error);
      });
    })
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        return response || fetch(event.request);
      })
  );
});

self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});