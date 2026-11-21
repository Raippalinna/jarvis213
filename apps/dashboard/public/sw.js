// Minimal service worker: app-shell cache, nätverk först för API.
const CACHE = "jarvis-shell-v1";
self.addEventListener("install", (e) => { self.skipWaiting(); });
self.addEventListener("activate", (e) => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))); });
self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.pathname.includes("/functions/v1/")) return;
  e.respondWith(
    fetch(e.request).then((r) => { const c = r.clone(); caches.open(CACHE).then((cache) => cache.put(e.request, c)); return r; })
      .catch(() => caches.match(e.request))
  );
});
