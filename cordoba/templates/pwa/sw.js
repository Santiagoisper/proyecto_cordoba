/* Service Worker — Proyecto Córdoba
   Estrategia:
   - Estáticos (css/js/íconos): cache-first con versionado por CACHE_NAME.
   - Navegación (HTML): network-first con fallback a /offline/.
   - Nunca cachear POST ni /media/ (tickets: datos sensibles, siempre red). */

const CACHE_NAME = 'cordoba-v1';

const PRECACHE_URLS = [
  '/offline/',
  '/static/css/app.css',
  '/static/js/htmx.min.js',
  '/static/js/lucide.min.js',
  '/static/icons/icon-192.png',
  '/static/manifest.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const request = event.request;

  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Datos sensibles: nunca cachear tickets ni admin.
  if (url.pathname.startsWith('/media/') || url.pathname.startsWith('/admin/')) return;

  // Estáticos: cache-first.
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((response) => {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
            return response;
          })
      )
    );
    return;
  }

  // Navegación: network-first con fallback offline.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() =>
        caches.match('/offline/').then((cached) => cached || Response.error())
      )
    );
  }
});
