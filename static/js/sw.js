const CACHE_NAME = 'finance-app-v5';

const urlsToCache = [
  '/',
  '/dashboard',
  '/transactions',
  '/offline',
  '/static/css/style.css',
  '/static/js/script.js'
];

// 🟢 INSTALL
self.addEventListener('install', event => {
  self.skipWaiting();

  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(urlsToCache);
    })
  );
});

// 🟢 ACTIVATE
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(names => {
      return Promise.all(
        names.map(name => {
          if (name !== CACHE_NAME) {
            return caches.delete(name);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// 🟢 FETCH (CORE LOGIC)
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request, { ignoreSearch: true }).then(cached => {
      
      // ✅ kalau ada di cache → langsung pakai
      if (cached) {
        return cached;
      }

      // 🌐 kalau tidak ada → ambil dari network
      return fetch(event.request)
        .then(networkResponse => {
          // cache response jika valid
          if (
            networkResponse &&
            networkResponse.status === 200 &&
            event.request.url.startsWith(self.location.origin)
          ) {
            const clone = networkResponse.clone();

            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, clone);
            });
          }

          return networkResponse;
        })
        .catch(() => {
          // 📵 fallback kalau offline
          return caches.match('/offline');
        });
    })
  );
});