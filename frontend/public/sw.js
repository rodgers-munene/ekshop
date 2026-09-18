// Bumped from v1, which cached API responses and RSC payloads by mistake (see
// isStaticAsset below). Changing the name makes activate delete v1, so every
// installed client drops those frozen responses as soon as this worker lands.
const CACHE = "ekshop-v2";
const APP_SHELL = ["/", "/manifest.webmanifest"];

// Only files whose content never changes at a given URL may be served
// cache-first. v1 had no such check: every same-origin GET that wasn't a page
// navigation fell through to cache-first, so the first answer from any /api
// route — the M-Pesa payment status poll, the cart, admin settings — was kept
// forever and the network was never asked again.
const STATIC_EXTENSIONS = /\.(?:png|jpe?g|webp|avif|gif|svg|ico|woff2?|ttf|otf)$/i;

function isStaticAsset(url) {
  if (url.search) return false; // ?_rsc=… and any query-driven response
  if (url.pathname.startsWith("/_next/static/")) return true; // content-hashed
  if (url.pathname.startsWith("/icons/")) return true;
  if (url.pathname === "/manifest.webmanifest") return true;
  return STATIC_EXTENSIONS.test(url.pathname);
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Always hit the network for navigation (documents + dynamic pages) so
  // buyers always get fresh content; fall back to the cached shell offline.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
          return response;
        })
        .catch(() => caches.match(request).then((cached) => cached || caches.match("/")))
    );
    return;
  }

  // Anything else — /api, RSC payloads, data of any kind — goes to the network
  // untouched, exactly as if there were no service worker.
  if (!isStaticAsset(url)) return;

  // Cache-first for static assets (images, icons, fonts, hashed JS/CSS).
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
        }
        return response;
      });
    })
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") {
    self.skipWaiting();
  }
});