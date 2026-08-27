/* TERRAIN - service worker
   Objectif : l'application s'ouvre instantanement, meme si le service Render
   dort encore. La derniere information connue est servie depuis le cache,
   puis remplacee en arriere-plan des que le reseau repond. */

const CACHE = 'terrain-v1';
const SHELL = ['/', '/manifest.json', '/icon-180.png', '/icon-192.png', '/icon-512.png'];
const API_TIMEOUT = 2500;

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.allSettled(SHELL.map((u) => c.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// La page d'attente de Render est du HTML valide : on refuse de la mettre en
// cache en verifiant que la reponse contient bien les donnees de TERRAIN.
async function isRealApp(response) {
  try {
    const text = await response.clone().text();
    return text.includes('id="news-data"');
  } catch (e) {
    return false;
  }
}

async function serveDocument(request) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match('/');

  const network = fetch(request).then(async (res) => {
    if (res && res.ok && await isRealApp(res)) {
      cache.put('/', res.clone());
      return res;
    }
    throw new Error('reponse inutilisable');
  });

  if (cached) {
    network.catch(() => {});   // mise a jour silencieuse pour la prochaine ouverture
    return cached;
  }
  try {
    return await network;
  } catch (e) {
    return fetch(request);
  }
}

async function serveNews(request) {
  const cache = await caches.open(CACHE);
  try {
    const res = await Promise.race([
      fetch(request, { cache: 'no-store' }),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), API_TIMEOUT))
    ]);
    if (res && res.ok) {
      cache.put('/api/news', res.clone());
      return res;
    }
    throw new Error('reponse non ok');
  } catch (e) {
    const cached = await cache.match('/api/news');
    if (cached) return cached;
    return new Response('{}', { headers: { 'Content-type': 'application/json' } });
  }
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith(serveDocument(request));
    return;
  }

  if (url.pathname.startsWith('/api/news')) {
    event.respondWith(serveNews(request));
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request).then((res) => {
      if (res && res.ok) {
        caches.open(CACHE).then((c) => c.put(request, res.clone()));
      }
      return res;
    }).catch(() => cached))
  );
});
