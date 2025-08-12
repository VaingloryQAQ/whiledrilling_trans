// static/sw.js
const CACHE = 'imgweb-v1';

self.addEventListener('install', (e) => { self.skipWaiting(); });
self.addEventListener('activate', (e) => { clients.claim(); });

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  const isPreview = url.pathname.startsWith('/preview/');
  const isGrouped = url.pathname.startsWith('/api/grouped-data');
  if (!(isPreview || isGrouped)) return;

  e.respondWith(
    caches.open(CACHE).then(async (cache) => {
      try {
        const res = await fetch(e.request);
        // 只缓存成功的 200
        if (res && res.ok) cache.put(e.request, res.clone());
        return res;
      } catch (err) {
        const hit = await cache.match(e.request);
        if (hit) return hit;
        throw err;
      }
    })
  );
});
