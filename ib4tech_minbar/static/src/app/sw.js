/* IB4Tech Minbar service worker: makes the app installable and readable offline.
 * Served from /app/sw.js with the module version substituted in. */
const VERSION = "__VERSION__";
const STATIC_CACHE = "minbar-static-" + VERSION;
const PAGE_CACHE = "minbar-pages";
const IMAGE_CACHE = "minbar-images";
const STATIC_ROOT = "/ib4tech_minbar/static/src/app/";
const OFFLINE_URL = "/app/offline";

const PRECACHE = [
    OFFLINE_URL,
    STATIC_ROOT + "app.css?v=" + VERSION,
    STATIC_ROOT + "app.js?v=" + VERSION,
    STATIC_ROOT + "fonts/tajawal-arabic-400-normal.woff2",
    STATIC_ROOT + "fonts/tajawal-arabic-500-normal.woff2",
    STATIC_ROOT + "fonts/tajawal-arabic-700-normal.woff2",
    STATIC_ROOT + "fonts/tajawal-latin-400-normal.woff2",
    STATIC_ROOT + "fonts/tajawal-latin-700-normal.woff2",
    STATIC_ROOT + "fonts/amiri-arabic-400-normal.woff2",
    STATIC_ROOT + "icons/icon-192.png",
];

// Personal or always-fresh routes are never answered from the cache.
const NETWORK_ONLY = ["/app/my", "/app/join", "/app/sw.js", "/app/manifest.webmanifest",
    "/app/favorites/cards", "/app/offline/urls"];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(
            keys.filter((key) => key.startsWith("minbar-static-") && key !== STATIC_CACHE)
                .map((key) => caches.delete(key))
        )).then(() => self.clients.claim())
    );
});

async function cacheFirst(request, cacheName) {
    const cached = await caches.match(request);
    if (cached) {
        return cached;
    }
    const response = await fetch(request);
    if (response.ok) {
        const cache = await caches.open(cacheName);
        cache.put(request, response.clone());
    }
    return response;
}

async function networkFirst(request) {
    const cache = await caches.open(PAGE_CACHE);
    try {
        const response = await fetch(request);
        if (response.ok && !response.redirected) {
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        const cached = await cache.match(request) || await cache.match(request, { ignoreSearch: true });
        if (cached) {
            return cached;
        }
        if (request.mode === "navigate") {
            const offline = await caches.match(OFFLINE_URL);
            if (offline) {
                return offline;
            }
        }
        throw error;
    }
}

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") {
        return;
    }
    const url = new URL(request.url);
    if (url.origin !== self.location.origin) {
        return;
    }
    if (url.pathname.startsWith(STATIC_ROOT)) {
        event.respondWith(cacheFirst(request, STATIC_CACHE));
    } else if (url.pathname.startsWith("/app/image/")) {
        event.respondWith(cacheFirst(request, IMAGE_CACHE));
    } else if (url.pathname === "/app" || url.pathname.startsWith("/app/")) {
        if (NETWORK_ONLY.some((prefix) => url.pathname.startsWith(prefix))) {
            return;
        }
        event.respondWith(networkFirst(request));
    }
});
