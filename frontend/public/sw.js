const CACHE = 'tracktion-static-v6';
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
      Promise.all(keys.filter((k) => k.startsWith('tracktion-') && k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
      .then(() => self.clients.matchAll({ type: 'window' }))
      .then((clients) => Promise.all(clients.map((client) => client.postMessage({ type: 'TRACKTION_SW_ACTIVATED' }))))
  );
});

self.addEventListener('message', (event) => {
  if (event.data?.type !== 'PURGE_TRACKTION_CACHES') return;
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith('tracktion-') && key !== CACHE).map((key) => caches.delete(key))))
      .then(() => event.ports[0].postMessage({ ok: true }))
  );
});

self.addEventListener('fetch', (e) => {
  const { request } = e;
  if (request.method !== 'GET') return;

  const url = request.url;

  // API calls must be excluded before extension-based static matching.
  if (isApiCall(url)) {
    e.respondWith(fetch(request));
    return;
  }

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

  // HTML / SPA routes: network-first, fall back to cached index.html
  e.respondWith(
    fetch(request).catch(() =>
      caches.match('/index.html').then((r) => r || Response.error())
    )
  );
});
