const CACHE_NAME = "ai-sight-cache-v1";
const urlsToCache = [
  "/static/index.html",
  "/static/sounds/success.mp3",
  "/static/sounds/error.mp3",
  "/static/sounds/notification.mp3",
  "/static/sounds/connect.mp3",
  "/static/sounds/disconnect.mp3",
  "/static/sounds/gesture.mp3",
  "/static/sounds/startListening.mp3",
  "/static/sounds/stopListening.mp3",
  "/static/sounds/alert.mp3",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(urlsToCache))
  );
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches
      .match(event.request)
      .then((response) => response || fetch(event.request))
  );
});
