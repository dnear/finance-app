const CACHE_NAME = 'finance-app-v3';
const urlsToCache = [
    '/',
    '/dashboard',
    '/offline',
    '/static/css/style.css',
    '/static/js/script.js'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
    );
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(names =>
            Promise.all(
                names.map(name => {
                    if (name !== CACHE_NAME) {
                        return caches.delete(name);
                    }
                })
            )
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', event => {
    if (event.request.method !== 'GET') {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then(response => {
                if (!response || response.status !== 200 || response.type !== 'basic') {
                    return response;
                }

                return caches.open(CACHE_NAME).then(cache => {
                    cache.put(event.request, response.clone());
                    return response;
                });
            })
            .catch(() => {
                return caches.match(event.request).then(cached => {
                    if (cached) {
                        return cached;
                    }

                    if (event.request.mode === 'navigate') {
                        return caches.match('/offline');
                    }

                    return Response.error();
                });
            })
    );
});