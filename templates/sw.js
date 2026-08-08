// Service Worker for offline bookshelf reading.
// __CACHE_VERSION__ is replaced at build time (git short SHA) by epub2html.py.
const CACHE = 'bookshelf-__CACHE_VERSION__';
const PREFETCH_AHEAD = 20;
const CHAPTER_RE = /\/chapters\/(\d+)\.html$/;

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    await Promise.all(
      (await caches.keys()).map((k) => k !== CACHE && caches.delete(k))
    );
    await self.clients.claim();
  })());
});

const inflight = new Set();

// Sliding-window prefetch: after opening chapter N, cache N+1..N+PREFETCH_AHEAD.
// Sequential; stops at the first 404 (end of book). No page changes needed
// because chapter URLs are sequential (1.html, 2.html, ...).
async function prefetchAhead(url, cache) {
  const m = url.match(CHAPTER_RE);
  if (!m) return;
  if (!navigator.onLine) return;
  if (navigator.connection && navigator.connection.saveData) return; // metered
  if (inflight.has(m[0])) return;
  inflight.add(m[0]);
  try {
    const n = parseInt(m[1], 10);
    const base = url.slice(0, m.index + '/chapters/'.length);
    for (let i = n + 1; i <= n + PREFETCH_AHEAD; i++) {
      const req = new Request(base + i + '.html', { method: 'GET' });
      if (await cache.match(req)) continue; // already cached
      let resp;
      try {
        resp = await fetch(req);
      } catch (e) {
        break; // went offline mid-prefetch
      }
      if (!resp || !resp.ok) break; // 404 → end of book
      await cache.put(req, resp.clone());
    }
  } finally {
    inflight.delete(m[0]);
  }
}

// Same-origin GET only. Stale-while-revalidate: serve cached immediately,
// refresh in background; cache misses hit the network (or a fallback page).
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  if (new URL(req.url).origin !== self.location.origin) return;

  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(req);
    if (cached) {
      event.waitUntil(revalidate(cache, req));
      event.waitUntil(prefetchAhead(req.url, cache));
      return cached;
    }
    try {
      const fresh = await fetch(req);
      if (fresh && fresh.ok) await cache.put(req, fresh.clone());
      event.waitUntil(prefetchAhead(req.url, cache));
      return fresh;
    } catch (e) {
      return offlineFallback();
    }
  })());
});

async function revalidate(cache, req) {
  try {
    const fresh = await fetch(req);
    if (fresh && fresh.ok) await cache.put(req, fresh.clone());
  } catch (e) {
    /* offline — keep the cached copy */
  }
}

function offlineFallback() {
  const body =
    '<!doctype html><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<body style="font:16px/1.6 sans-serif;padding:2em">' +
    '本页尚未离线缓存。请联网后先打开一次，或在目录页点「离线下载整本」。</body>';
  return new Response(body, {
    status: 503,
    headers: { 'Content-Type': 'text/html; charset=utf-8' },
  });
}
