/* Agrivision PWA service worker — network-first for app shell so GPS/UI fixes ship */
const CACHE = "agrivision-v6";
const SHELL = [
  "/",
  "/index.html",
  "/app.html",
  "/location.html",
  "/loading.html",
  "/results.html",
  "/profile.html",
  "/manifest.webmanifest",
  "/images/icon-192.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.pathname.startsWith("/ml/")) return;

  // Always prefer network for JS/CSS so location fixes reach phones
  const isAsset =
    url.pathname.startsWith("/js/") || url.pathname.startsWith("/css/");

  if (isAsset) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res && res.ok && url.origin === self.location.origin) {
            const clone = res.clone();
            caches.open(CACHE).then((cache) => cache.put(req, clone));
          }
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.ok && url.origin === self.location.origin) {
          const clone = res.clone();
          caches.open(CACHE).then((cache) => cache.put(req, clone));
        }
        return res;
      })
      .catch(() => caches.match(req))
  );
});
