"use strict";
// Service worker : le site reste utilisable sans Internet après une première visite.
// Fichiers du site : réseau d'abord (toujours la dernière version), copie gardée pour le hors ligne.
// Bibliothèques des CDN (Pyodide, Plotly, KaTeX) : adresses à version figée, donc copie gardée d'abord.
// Le numéro change avec construire_web.py (empreinte du zip) : les anciennes copies sont alors effacées.

const VERSION = "mecastruct-1.6.0-971e9a84";
const CDN_CACHE = "mecastruct-cdn"; // adresses à version figée : gardées d'une version du site à l'autre
const CDN = ["https://cdn.jsdelivr.net/", "https://cdnjs.cloudflare.com/", "https://files.pythonhosted.org/", "https://pypi.org/"];

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    for (const nom of await caches.keys()) if (nom !== VERSION && nom !== CDN_CACHE) await caches.delete(nom);
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = req.url;
  if (CDN.some((c) => url.startsWith(c))) {
    e.respondWith((async () => {
      const cache = await caches.open(CDN_CACHE);
      const garde = await cache.match(req);
      if (garde) return garde;
      const rep = await fetch(req);
      if (rep.ok) cache.put(req, rep.clone());
      return rep;
    })());
  } else if (url.startsWith(self.registration.scope)) {
    e.respondWith((async () => {
      const cache = await caches.open(VERSION);
      try {
        const rep = await fetch(req);
        if (rep.ok) cache.put(req, rep.clone());
        return rep;
      } catch (err) {
        const garde = await cache.match(req, { ignoreSearch: url.includes("mecastruct.zip") ? false : true });
        if (garde) return garde;
        throw err;
      }
    })());
  }
});
