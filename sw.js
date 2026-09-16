/* One-time cleanup worker: kills the old MediBridge offline-app service worker
   and wipes its caches, then unregisters itself so the site returns to normal
   browsing (fresh React web app). Nothing re-registers service workers. */
self.addEventListener("install", function (event) {
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    (async function () {
      var keys = await caches.keys();
      await Promise.all(keys.map(function (k) { return caches.delete(k); }));
      await self.registration.unregister();
      await self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", function (event) {
  event.respondWith(fetch(event.request));
});