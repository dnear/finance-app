const CACHE_NAME = 'finance-app-v7';

const STATIC_ASSETS = [
    '/offline',
    '/static/css/style.css',
    '/static/js/script.js',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/static/icons/icon-512-maskable.png',
    '/static/manifest.json'
];

// ================================
// INSTALL
// ================================
self.addEventListener('install', event => {
    console.log('[SW] Installing', CACHE_NAME);

    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(STATIC_ASSETS))
            .then(() => self.skipWaiting())
    );
});


// ================================
// ACTIVATE
// ================================
self.addEventListener('activate', event => {
    console.log('[SW] Activating', CACHE_NAME);

    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames
                        .filter(name => name !== CACHE_NAME)
                        .map(name => caches.delete(name))
                );
            })
            .then(() => self.clients.claim())
    );
});


// ================================
// FETCH
// ================================
self.addEventListener('fetch', event => {

    // Hanya GET
    if (event.request.method !== 'GET') {
        return;
    }

    const request = event.request;
    const url = new URL(request.url);

    // Hanya handle origin sendiri
    if (url.origin !== self.location.origin) {
        return;
    }

    // ================================
    // STATIC ASSETS
    // Cache First
    // ================================
    if (url.pathname.startsWith('/static/')) {

        event.respondWith(
            caches.match(request)
                .then(cached => {
                    if (cached) {
                        return cached;
                    }

                    return fetch(request).then(response => {

                        if (response && response.ok) {
                            const responseClone = response.clone();

                            caches.open(CACHE_NAME)
                                .then(cache => {
                                    cache.put(request, responseClone);
                                });
                        }

                        return response;
                    });
                })
        );

        return;
    }


    // ================================
    // HTML / APP PAGES
    // Network First
    // ================================
    if (
        request.headers.get('accept')?.includes('text/html')
    ) {

        event.respondWith(

            fetch(request)
                .then(response => {

                    // Simpan halaman HTML yang berhasil dibuka
                    if (response && response.ok) {

                        const responseClone = response.clone();

                        caches.open(CACHE_NAME)
                            .then(cache => {
                                cache.put(request, responseClone);
                            });
                    }

                    return response;
                })

                .catch(() => {

                    // Jika offline, gunakan halaman yang pernah dibuka
                    return caches.match(request)
                        .then(cachedPage => {

                            if (cachedPage) {
                                return cachedPage;
                            }

                            // Kalau belum pernah dibuka
                            return caches.match('/offline');
                        });
                })
        );

        return;
    }


    // ================================
    // OTHER GET REQUESTS
    // Network only
    // ================================
});