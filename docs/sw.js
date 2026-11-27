"use strict";
// Service worker : le site reste utilisable sans Internet après une première visite.
// Fichiers du site : réseau d'abord (toujours la dernière version), copie gardée pour le hors ligne.
// Bibliothèques des CDN (Pyodide, Plotly, KaTeX) : adresses à version figée, donc copie gardée d'abord.
// Le numéro change avec construire_web.py (empreinte du zip) : les anciennes copies sont alors effacées.

const VERSION = "mecastruct-1.7.0-40b35298";
const CDN_CACHE = "mecastruct-cdn"; // adresses à version figée : gardées d'une version du site à l'autre
const CDN = ["https://cdn.jsdelivr.net/", "https://cdnjs.cloudflare.com/", "https://files.pythonhosted.org/", "https://pypi.org/"];

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    // seulement les copies de MecaStruct : l'origine (…github.io) est partagée avec d'autres projets, dont les caches restent intacts
    for (const nom of await caches.keys()) if (nom.startsWith("mecastruct-") && nom !== VERSION && nom !== CDN_CACHE) await caches.delete(nom);
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
      // vérification de version (?verif=) et actualisation forcée (?maj=) : toujours le réseau, jamais gardées en copie
      if (/[?&](verif|maj)=/.test(url)) return fetch(req);
      const cache = await caches.open(VERSION);
      const copie = () => cache.match(req, { ignoreSearch: url.includes("mecastruct.zip") ? false : true });
      const reseau = fetch(req).then((rep) => {
        if (rep.ok) cache.put(req, rep.clone());
        return rep;
      });
      reseau.catch(() => {}); // si la copie répond la première, l'échec tardif du réseau n'est pas une erreur
      // réseau d'abord, mais pas plus de 4 s : au-delà, la copie gardée répond (connexion très lente = presque hors ligne)
      let minuterie;
      const delai = new Promise((_, ko) => { minuterie = setTimeout(() => ko(new Error("délai")), 4000); });
      try {
        return await Promise.race([reseau, delai]);
      } catch (err) {
        const garde = await copie();
        if (garde) return garde;
        return reseau; // pas de copie : on attend le réseau jusqu'au bout (ou son échec)
      } finally {
        clearTimeout(minuterie);
      }
    })());
  }
});
