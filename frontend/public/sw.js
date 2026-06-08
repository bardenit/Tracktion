const CACHE = 'tracktion-v5';
const STATIC_EXTS = ['.js', '.css', '.woff2', '.woff', '.ttf', '.svg', '.png', '.jpg', '.ico'];

function isStaticAsset(url) {
  const u = new URL(url);
  return u.pathname.startsWith('/assets/') || STATIC_EXTS.some((e) => u.pathname.endsWith(e));
}

function isApiCall(url) {
  return new URL(url).pathname.startsWith('/api/');
}

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(['/', '/index.html'])).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const { request } = e;
  if (request.method !== 'GET') return;

  const url = request.url;

  // Static assets: cache-first, refresh in background
  if (isStaticAsset(url)) {
    e.respondWith(
      caches.open(CACHE).then(async (cache) => {
        const cached = await cache.match(request);
        const fetchPromise = fetch(request).then((res) => {
          if (res.ok) cache.put(request, res.clone());
          return res;
        }).catch(() => cached);
        return cached || fetchPromise;
      })
    );
    return;
  }

  // API calls: network-first, fall back to cache for offline reading
  if (isApiCall(url)) {
    e.respondWith(
      caches.open(CACHE).then(async (cache) => {
        try {
          const res = await fetch(request);
          if (res.ok) cache.put(request, res.clone());
          return res;
        } catch {
          return cache.match(request) || Response.error();
        }
      })
    );
    return;
  }

  // HTML / SPA routes: network-first, fall back to cached index.html
  e.respondWith(
    fetch(request).catch(() =>
      caches.match('/index.html').then((r) => r || Response.error())
    )
  );
});
