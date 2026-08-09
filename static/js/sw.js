const CACHE_NAME = 'finance-app-v6';

const STATIC_ASSETS = [
    '/offline',
    '/static/css/style.css',
    '/static/js/script.js',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/static/manifest.json'
];

// ================================
// INSTALL
// ================================
self.addEventListener('install', event => {
    console.log('[SW] Installing...');

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
    console.log('[SW] Activating...');

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

    // Jangan intercept request dari domain lain
    if (url.origin !== self.location.origin) {
        return;
    }

    // ============================
    // STATIC ASSETS
    // Cache First
    // ============================
    if (
        url.pathname.startsWith('/static/')
    ) {
        event.respondWith(
            caches.match(request)
                .then(cached => {

                    if (cached) {
                        return cached;
                    }

                    return fetch(request);
                })
        );

        return;
    }


    // ============================
    // HTML / APP PAGES
    // Network First
    // ============================
    if (
        request.headers.get('accept')?.includes('text/html')
    ) {

        event.respondWith(
            fetch(request)
                .catch(() => {
                    return caches.match('/offline');
                })
        );

        return;
    }


    // ============================
    // OTHER REQUESTS
    // Network only
    // ============================
});