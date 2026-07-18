// Cache-Version bei Bedarf erhoehen -> der neue SW loescht beim activate ALLE
// alten Caches. Das holt Clients aus einem veralteten/vergifteten Cache heraus
// (z.B. nachdem waehrend eines kaputten Deploys eine defekte Version gecacht wurde).
const CACHE_NAME = "manuel-tu-chemie-v2";
const SHELL = ["/", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/uploads/")) return;

  if (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/icons/")) {
    // Gehashte, immutable Assets: cache-first ist sicher (neue Deploys = neue Dateinamen).
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cached = await cache.match(request);
        if (cached) return cached;
        const response = await fetch(request);
        if (response.ok) cache.put(request, response.clone());
        return response;
      })
    );
    return;
  }

  if (request.mode === "navigate") {
    // Network-first und bei Erfolg die Shell aktualisieren, damit der Offline-Fallback
    // nicht auf eine veraltete index.html mit alten Asset-Hashes zeigt.
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put("/", copy)).catch(() => {});
          return response;
        })
        .catch(() => caches.match("/"))
    );
  }
});
