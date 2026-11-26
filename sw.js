/* Service worker : garde l'appli, les plans et les données pour un usage hors ligne.
 * Changer VERSION à chaque mise en ligne pour forcer la mise à jour du cache. */
const VERSION = "tremplin-v3";
const COQUILLE = [
  "./", "index.html", "app.css", "app.js", "edition.js", "config.js", "manifest.webmanifest",
  "data/donnees.json", "icones/icone.svg", "icones/icone-192.png", "icones/icone-512.png",
  "plans/cad.css", "plans/rdc-bas.svg", "plans/rdc-haut.svg", "plans/r2.svg", "plans/r3.svg", "plans/r4.svg",
  "plans/sous-sol-l.webp", "plans/r1-l.webp"
];
const PLANS_HD = ["plans/sous-sol.webp", "plans/r1.webp"];

self.addEventListener("install", e => {
  e.waitUntil((async () => {
    const c = await caches.open(VERSION);
    await c.addAll(COQUILLE);
    // plans HD : en arrière-plan, sans bloquer l'installation
    c.addAll(PLANS_HD).catch(() => {});
    self.skipWaiting();
  })());
});
self.addEventListener("activate", e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== VERSION) await caches.delete(k);
    await self.clients.claim();
  })());
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  const url = new URL(req.url);
  const reseauDabord = req.mode === "navigate" || /donnees\.json$|config\.js$/.test(url.pathname);
  e.respondWith((async () => {
    const c = await caches.open(VERSION);
    if (reseauDabord) {
      try {
        const r = await fetch(req);
        if (r.ok) c.put(req.mode === "navigate" ? "index.html" : req, r.clone());
        return r;
      } catch {
        return (await c.match(req.mode === "navigate" ? "index.html" : req, { ignoreSearch: true })) || Response.error();
      }
    }
    const en = await c.match(req, { ignoreSearch: true });
    if (en) return en;
    const r = await fetch(req);
    if (r.ok) c.put(req, r.clone());
    return r;
  })());
});
