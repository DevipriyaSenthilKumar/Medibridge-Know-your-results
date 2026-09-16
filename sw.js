/* MediBridge offline service worker — cache-first, never touches the network once installed */
var VERSION = "medi-bridge-v1";
var ASSETS = [
  "./",
  "./index.html",
  "./app.js",
  "./core.js",
  "./engine-data.json",
  "./manifest.webmanifest",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./vendor/tesseract.min.js",
  "./vendor/worker.min.js",
  "./vendor/core/tesseract-core-simd.wasm.js",
  "./vendor/core/tesseract-core-simd.wasm",
  "./vendor/tessdata/eng.traineddata.gz"
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(VERSION).then(function (cache) {
      return cache.addAll(ASSETS);
    }).then(function () {
      return self.skipWaiting();
    })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (event) {
  var request = event.request;
  if (request.method !== "GET") return;
  var url = new URL(request.url);
  if (url.origin !== location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(
      caches.match("./index.html").then(function (cached) {
        if (cached) return cached;
        return fetch(request).then(function (res) {
          var copy = res.clone();
          caches.open(VERSION).then(function (c) { c.put("./index.html", copy); });
          return res;
        });
      })
    );
    return;
  }

  event.respondWith(
    caches.match(request).then(function (cached) {
      if (cached) return cached;
      return fetch(request).then(function (res) {
        if (res.status === 200 && (url.pathname.indexOf(".wasm") !== -1 || url.pathname.indexOf(".traineddata") !== -1)) {
          var copy = res.clone();
          caches.open(VERSION).then(function (c) { c.put(request, copy); });
        }
        return res;
      }).catch(function () {
        return Response.error();
      });
    })
  );
});