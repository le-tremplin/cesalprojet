/* Fiches des locaux : onglets Essentiel, Actuel, Futur, Budget, Galerie.
 * Sauvegarde partagée dans Supabase (config.js → SUPABASE). Sans configuration : mode local
 * (données gardées sur cet appareil seulement, signalé à l'écran).
 * Droits : lecteur (consultation), editeur (textes des fiches), admin (tout, dont budget et photos). */
(() => {
"use strict";
const C = window.CONFIG || {};
const SB = C.SUPABASE || {};
const EN_LIGNE = !!(SB.url && SB.cle_anon);
const URL_SB = (SB.url || "").replace(/\/$/, "");
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ls = {
  get(k, d) { try { const v = localStorage.getItem("tremplin:" + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("tremplin:" + k, JSON.stringify(v)); return true; } catch { return false; } },
  del(k) { try { localStorage.removeItem("tremplin:" + k); } catch {} }
};
const uid = () => (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2));
const euros = n => (Number(n) || 0).toLocaleString("fr-FR", { style: "currency", currency: "EUR" });

// ------------------------------------------------------------------ définition des champs
const CHAMPS = {
  essentiel: [
    ["reference", "Numéro ou référence", "court"], ["configuration", "Configuration"], ["surface_future", "Surface future", "court"], ["fonction_actuelle", "Fonction actuelle", "court"],
    ["fonction_future", "Fonction future", "court"], ["surface", "Surface actuelle", "court"],
    ["capacite", "Capacité d'accueil", "court"],
    ["pmr", "Accessibilité PMR", "court"],
    ["acces_circulation", "Accessibilité et circulation"], ["particularites", "Particularités techniques"],
    ["contraintes", "Contraintes principales"]
  ],
  actuel: [
    ["description", "Description générale de l'état actuel"], ["defauts", "Défauts constatés"],
    ["problemes_techniques", "Problèmes techniques"], ["murs_sols_plafonds", "État des murs, sols et plafonds"],
    ["menuiseries", "État des menuiseries"], ["equipements", "État des équipements"],
    ["accessibilite", "Problèmes d'accessibilité"], ["securite_circulation", "Problèmes de sécurité ou de circulation"],
    ["vigilance", "Points de vigilance"], ["observations", "Observations complémentaires"]
  ],
  futur: [
    ["description", "Description du futur aménagement"], ["nouvelle_fonction", "Nouvelle fonction du local", "court"],
    ["travaux", "Travaux à réaliser"], ["modifications", "Modifications architecturales"],
    ["amenagements", "Aménagements souhaités"], ["equipements", "Équipements à prévoir"],
    ["accessibilite", "Améliorations d'accessibilité"], ["contraintes", "Contraintes à prendre en compte"],
    ["vigilance", "Points de vigilance"], ["temporalite", "Temporalité prévisionnelle"]
  ]
};
const POSTES = ["Démolition", "Dépose", "Gros œuvre", "Cloisons", "Menuiseries", "Électricité", "Plomberie",
  "Chauffage et ventilation", "Revêtements de sols", "Peinture", "Mobilier", "Équipements", "Aménagements spécifiques", "Autre"];
const UNITES = ["m²", "ml", "m³", "u", "forfait", "ens.", "h", "kg"];
const CATEGORIES_PHOTO = [["existant", "Existant"], ["futur", "Projet futur"], ["travaux", "Travaux"],
  ["references", "Références et inspirations"], ["autres", "Autres documents"]];

// ------------------------------------------------------------------ session et droits
const EDITION_LOCALE = new URLSearchParams(location.search).get("edition") === "1";
const Auth = {
  session: ls.get("session", null),
  role: "lecteur",
  perms: {},
  nom: "",
  async init() {
    // sans base : lecture seule ; ?edition=1 = poste du propriétaire (corrections gardées sur cet appareil)
    if (!EN_LIGNE) { this.role = EDITION_LOCALE ? "proprietaire" : "lecteur"; this.nom = EDITION_LOCALE ? "propriétaire (local)" : ""; return; }
    if (!this.session) return;
    if (Date.now() / 1000 > (this.session.expires_at || 0) - 60) await this.rafraichir();
    await this.chargerRole();
  },
  async connexion(email, mdp) {
    const r = await fetch(`${URL_SB}/auth/v1/token?grant_type=password`, {
      method: "POST", headers: { apikey: SB.cle_anon, "Content-Type": "application/json" },
      body: JSON.stringify({ email, password: mdp })
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error_description || j.msg || "Connexion refusée");
    this.garder(j);
    await this.chargerRole();
  },
  garder(j) {
    this.session = { access_token: j.access_token, refresh_token: j.refresh_token, expires_at: Math.floor(Date.now() / 1000) + (j.expires_in || 3600), user: { id: j.user.id, email: j.user.email } };
    ls.set("session", this.session);
  },
  async rafraichir() {
    try {
      const r = await fetch(`${URL_SB}/auth/v1/token?grant_type=refresh_token`, {
        method: "POST", headers: { apikey: SB.cle_anon, "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: this.session.refresh_token })
      });
      if (!r.ok) throw 0;
      this.garder(await r.json());
    } catch { this.deconnexion(); }
  },
  async chargerRole() {
    if (!this.session) return;
    try {
      const r = await api(`/rest/v1/profils?id=eq.${this.session.user.id}&select=role,nom,permissions`);
      const p = (await r.json())[0];
      this.role = p && ["proprietaire", "admin"].includes(p.role) ? p.role : "lecteur";
      this.perms = (p && p.permissions) || {};
      this.nom = (p && p.nom) || this.session.user.email;
    } catch { this.role = "lecteur"; }
  },
  deconnexion() { this.session = null; this.role = "lecteur"; this.perms = {}; this.nom = ""; ls.del("session"); },
  peut(droit) { return this.role === "proprietaire" || (this.role === "admin" && !!this.perms[droit]); },
  peutEditer() { return this.peut("fiches"); },
  peutBudget() { return this.peut("budget"); },
  // sans base configurée, les photos restent sur l'appareil : l'import est ouvert (les fiches restent protégées)
  peutPhotos() { return !EN_LIGNE || this.peut("photos"); },
  estProprietaire() { return this.role === "proprietaire"; },
  estAdmin() { return this.peutPhotos(); }
};

async function api(chemin, opts = {}) {
  if (Auth.session && Date.now() / 1000 > Auth.session.expires_at - 60) await Auth.rafraichir();
  const h = { apikey: SB.cle_anon, Authorization: `Bearer ${Auth.session ? Auth.session.access_token : SB.cle_anon}`, ...(opts.headers || {}) };
  return fetch(URL_SB + chemin, { ...opts, headers: h });
}

// ------------------------------------------------------------------ stockage des photos en mode local (IndexedDB)
const IDB = {
  db: null,
  ouvrir() {
    if (this.db) return Promise.resolve(this.db);
    return new Promise((ok, ko) => {
      const r = indexedDB.open("tremplin", 1);
      r.onupgradeneeded = () => r.result.createObjectStore("photos", { keyPath: "id" }).createIndex("local", "local_id");
      r.onsuccess = () => ok(this.db = r.result);
      r.onerror = () => ko(r.error);
    });
  },
  async tx(mode, f) {
    const db = await this.ouvrir();
    return new Promise((ok, ko) => {
      const t = db.transaction("photos", mode); const s = t.objectStore("photos");
      const r = f(s); t.oncomplete = () => ok(r && r.result); t.onerror = () => ko(t.error);
    });
  }
};

// ------------------------------------------------------------------ données : fiches et photos
const urlsLocales = new Map();
const autoCache = new Map();
let dossierPhotos = null;
function photosDossier() {
  if (!dossierPhotos) dossierPhotos = fetch("data/photos.json").then(r => r.ok ? r.json() : {}).catch(() => ({}));
  return dossierPhotos;
}
function fichesAuto(niveau) {
  if (!autoCache.has(niveau)) autoCache.set(niveau, fetch(`data/fiches/${niveau}.json`).then(r => r.ok ? r.json() : {}).catch(() => ({})));
  return autoCache.get(niveau);
}
function fusion(auto, stocke) {
  // la version corrigée (base) l'emporte champ par champ ; le contenu préremplli comble les vides
  const out = { essentiel: {}, actuel: {}, futur: {}, budget: { tva: 20, lignes: [] } };
  for (const o of ["essentiel", "actuel", "futur"]) out[o] = { ...((auto || {})[o] || {}), ...Object.fromEntries(Object.entries((stocke || {})[o] || {}).filter(([, v]) => v !== "" && v != null)) };
  const sb = (stocke || {}).budget;
  out.budget = sb && (sb.modifie || (sb.lignes || []).length) ? sb : JSON.parse(JSON.stringify((auto || {}).budget || { tva: 20, lignes: [] }));
  return out;
}
const Base = {
  async lireFiche(id) {
    if (!EN_LIGNE) return ls.get("fiche:" + id, null);
    try {
      const r = await api(`/rest/v1/fiches?local_id=eq.${encodeURIComponent(id)}&select=contenu,updated_at,maj_par`);
      if (!r.ok) throw new Error(r.status);
      const d = (await r.json())[0] || null;
      ls.set("cache:fiche:" + id, d);
      return d;
    } catch { return ls.get("cache:fiche:" + id, null); }      // hors ligne : dernière version lue
  },
  async ecrireFiche(id, contenu) {
    const doc = { contenu, updated_at: new Date().toISOString(), maj_par: Auth.nom };
    if (!EN_LIGNE) { if (!ls.set("fiche:" + id, doc)) throw new Error("Mémoire de l'appareil pleine"); return doc; }
    const r = await api("/rest/v1/fiches", {
      method: "POST",
      headers: { "Content-Type": "application/json", Prefer: "resolution=merge-duplicates,return=representation" },
      body: JSON.stringify({ local_id: id, contenu, maj_par: Auth.nom })
    });
    if (!r.ok) throw new Error((await r.text()) || r.status);
    const d = (await r.json())[0]; ls.set("cache:fiche:" + id, d); return d;
  },
  async photos(id) {
    // photos du dossier (dépôt, lecture seule) puis photos ajoutées par les comptes autorisés
    const [dossier, ajoutees] = await Promise.all([photosDossier(), this.photosUtilisateurs(id)]);
    const fixes = (dossier[id] || []).map((p, i) => ({ ...p, id: `dossier-${id}-${i}`, url: p.fichier, statique: true }));
    return [...ajoutees, ...fixes];
  },
  async photosUtilisateurs(id) {
    if (!EN_LIGNE) {
      const tout = await IDB.tx("readonly", s => s.index("local").getAll(id));
      return (tout || []).map(p => {
        if (!urlsLocales.has(p.id)) urlsLocales.set(p.id, URL.createObjectURL(p.blob));
        return { ...p, url: urlsLocales.get(p.id) };
      }).sort((a, b) => (b.date_prise || "").localeCompare(a.date_prise || ""));
    }
    try {
      const r = await api(`/rest/v1/photos?local_id=eq.${encodeURIComponent(id)}&order=date_prise.desc.nullslast,created_at.desc`);
      const l = await r.json();
      return l.map(p => ({ ...p, url: `${URL_SB}/storage/v1/object/public/photos/${p.chemin}` }));
    } catch { return []; }
  },
  async ajouterPhoto(id, blob, meta) {
    if (!EN_LIGNE) {
      const p = { id: uid(), local_id: id, blob, ...meta, created_at: new Date().toISOString() };
      await IDB.tx("readwrite", s => s.put(p)); return p;
    }
    const chemin = `${id}/${uid()}.jpg`;
    const up = await api(`/storage/v1/object/photos/${chemin}`, { method: "POST", headers: { "Content-Type": "image/jpeg" }, body: blob });
    if (!up.ok) throw new Error("Envoi de la photo refusé (" + up.status + ")");
    const r = await api("/rest/v1/photos", { method: "POST", headers: { "Content-Type": "application/json", Prefer: "return=representation" },
      body: JSON.stringify({ local_id: id, chemin, ...meta }) });
    if (!r.ok) throw new Error("Enregistrement de la photo refusé");
    return (await r.json())[0];
  },
  async majPhoto(p, meta) {
    if (!EN_LIGNE) { await IDB.tx("readwrite", s => s.put({ ...p, ...meta, url: undefined })); return; }
    const r = await api(`/rest/v1/photos?id=eq.${p.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(meta) });
    if (!r.ok) throw new Error("Modification refusée");
  },
  async remplacerPhoto(p, blob) {
    if (!EN_LIGNE) { urlsLocales.delete(p.id); await IDB.tx("readwrite", s => s.put({ ...p, blob, url: undefined })); return; }
    const chemin = `${p.local_id}/${uid()}.jpg`;
    const up = await api(`/storage/v1/object/photos/${chemin}`, { method: "POST", headers: { "Content-Type": "image/jpeg" }, body: blob });
    if (!up.ok) throw new Error("Envoi refusé");
    await this.majPhoto(p, { chemin });
    await api(`/storage/v1/object/photos/${p.chemin}`, { method: "DELETE" });
  },
  async supprimerPhoto(p) {
    if (!EN_LIGNE) { urlsLocales.delete(p.id); await IDB.tx("readwrite", s => s.delete(p.id)); return; }
    const r = await api(`/rest/v1/photos?id=eq.${p.id}`, { method: "DELETE" });
    if (!r.ok) throw new Error("Suppression refusée");
    await api(`/storage/v1/object/photos/${p.chemin}`, { method: "DELETE" });
  }
};

// ------------------------------------------------------------------ sauvegarde automatique (avec file d'attente hors ligne)
const Sauvegarde = {
  attente: ls.get("attente", {}),        // modifications pas encore confirmées par le serveur
  minuteur: null, etat: "ok", heure: "",
  planifier(id, contenu) {
    this.attente[id] = contenu; ls.set("attente", this.attente);
    this.afficher("attente");
    clearTimeout(this.minuteur);
    this.minuteur = setTimeout(() => this.envoyer(), 1200);
  },
  async envoyer() {
    const ids = Object.keys(this.attente);
    if (!ids.length) return;
    this.afficher("envoi");
    try {
      for (const id of ids) {
        await Base.ecrireFiche(id, this.attente[id]);
        delete this.attente[id]; ls.set("attente", this.attente);
      }
      this.heure = new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
      this.afficher("ok");
    } catch (e) {
      this.afficher("erreur", e.message);
      clearTimeout(this.minuteur);
      this.minuteur = setTimeout(() => this.envoyer(), 15000);
    }
  },
  afficher(etat, msg) {
    this.etat = etat;
    document.querySelectorAll(".sauve").forEach(n => {
      n.className = "sauve " + etat;
      n.textContent = !Auth.peutEditer() && !Auth.peutBudget() ? "Consultation seule — contenu protégé"
        : etat === "ok" ? (this.heure ? `Enregistré à ${this.heure}` : (EN_LIGNE ? "À jour" : "Corrections gardées sur cet appareil"))
        : etat === "attente" ? "Modifications en cours…" : etat === "envoi" ? "Enregistrement…"
        : "Échec de l'enregistrement — nouvel essai automatique" + (msg ? ` (${msg.slice(0, 60)})` : "");
    });
  }
};
addEventListener("online", () => Sauvegarde.envoyer());
addEventListener("beforeunload", e => { if (Object.keys(Sauvegarde.attente).length) { Sauvegarde.envoyer(); e.preventDefault(); e.returnValue = ""; } });
if (Object.keys(Sauvegarde.attente).length) setTimeout(() => Sauvegarde.envoyer(), 2000);

// ------------------------------------------------------------------ affichage
const vide = () => ({ essentiel: {}, actuel: {}, futur: {}, budget: { tva: 20, lignes: [] } });
const etat = { id: null, contenu: vide(), maj: null, photos: [], filtre: "tout" };

const ORIGINES = { "Plan": "o-plan", "Projet": "o-projet", "Estimation": "o-estim", "Constat": "o-plan", "À vérifier sur site": "o-site" };
function provenance(t) {
  return esc(t).replace(/\[(Plan|Projet|Estimation|Constat|À vérifier sur site)\]/g, (m, k) => `<span class="origine ${ORIGINES[k]}">${k}</span>`);
}
function champ(onglet, [cle, libelle, type, options], valeur, modifiable) {
  const id = `f-${onglet}-${cle}`;
  if (!modifiable) {
    if (!valeur) return "";
    return `<div class="lu"><b>${esc(libelle)}</b><p>${provenance(valeur)}</p></div>`;
  }
  if (type === "choix") return `<label class="ch" for="${id}">${esc(libelle)}<select id="${id}" data-o="${onglet}" data-c="${cle}">${options.map(o => `<option ${o === valeur ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></label>`;
  if (type === "court") return `<label class="ch" for="${id}">${esc(libelle)}<input id="${id}" data-o="${onglet}" data-c="${cle}" value="${esc(valeur || "")}"></label>`;
  return `<label class="ch" for="${id}">${esc(libelle)}<textarea id="${id}" data-o="${onglet}" data-c="${cle}" rows="2">${esc(valeur || "")}</textarea></label>`;
}

function dossier(l, onglet) {
  // données du dossier d'étude (données de départ, jamais écrasées)
  const blocs = [];
  if (onglet === "essentiel") {
    if (l.resume) blocs.push(`<p>${esc(l.resume)}</p>`);
    const lignes = [["Surface (plan)", l.surface], ["Accès", l.acces], ["Fiabilité", { C: "Constat", H: "Hypothèse à vérifier", P: "Préconisation" }[l.fiabilite]]].filter(x => x[1]);
    if (lignes.length) blocs.push(lignes.map(([k, v]) => `<div class="ligne"><b>${k}</b><span>${esc(v)}</span></div>`).join(""));
  }
  if (onglet === "actuel") {
    if ((l.equipements || []).length) blocs.push(`<h4>Équipements relevés</h4><ul>${l.equipements.map(e => `<li><b>${esc(e.nom)}</b>${e.detail ? " — " + esc(e.detail) : ""} <span class="fia-mini fia-${esc(e.fiabilite)}">${esc(e.fiabilite)}</span></li>`).join("")}</ul>`);
    if ((l.risques || []).length) blocs.push(`<h4>Risques</h4>${l.risques.map(r => `<div class="risque ${esc(r.niveau)}"><b>${esc(r.niveau)}</b><span>${esc(r.texte)}</span></div>`).join("")}`);
  }
  if (onglet === "futur" && l.projet) blocs.push(`<p>${esc(l.projet)}</p>`);
  if (!blocs.length) return "";
  return `<details class="dossier"><summary>Dossier d'étude${l.source ? ` · ${esc(l.source)}` : ""}</summary>${blocs.join("")}</details>`;
}

function htmlPhotos(cats, titre) {
  const ph = etat.photos.filter(p => cats.includes(p.categorie));
  const admin = Auth.estAdmin();
  return `<section class="bloc-photos"><div class="tt"><h4>${titre}</h4>${admin ? `<button class="puce" data-f="ajouter" data-cat="${cats[0]}">+ Ajouter des photos</button>` : ""}</div>
    ${ph.length ? `<div class="vignettes">${ph.map(vignette).join("")}</div>` : `<p class="vide">Aucune photo${admin ? "" : " pour l'instant"}.</p>`}</section>`;
}
function vignette(p) {
  return `<figure class="vign" data-f="voir" data-id="${esc(p.id)}"><img src="${esc(p.url)}" alt="${esc(p.legende || "")}" loading="lazy">
    <figcaption>${p.categorie === "futur" ? `<span class="origine o-projet">Projet</span>` : p.categorie === "existant" ? `<span class="origine o-plan">Existant</span>` : ""}${esc(p.legende || "Sans légende")}${p.date_prise ? `<small>${esc(new Date(p.date_prise).toLocaleDateString("fr-FR"))}</small>` : ""}</figcaption></figure>`;
}

function htmlBudget(modifiable) {
  const b = etat.contenu.budget || { tva: 20, lignes: [] };
  const lignes = b.lignes || [];
  const calc = x => { const ht = (+x.quantite || 0) * (+x.pu_ht || 0); const tv = ht * ((x.tva ?? b.tva ?? 20) / 100); return { ht, tv, ttc: ht + tv }; };
  const parPoste = {};
  lignes.forEach(x => { const k = x.poste || "Autre"; const c = calc(x); parPoste[k] = parPoste[k] || { ht: 0, tv: 0, ttc: 0 }; parPoste[k].ht += c.ht; parPoste[k].tv += c.tv; parPoste[k].ttc += c.ttc; });
  const tot = Object.values(parPoste).reduce((a, c) => ({ ht: a.ht + c.ht, tv: a.tv + c.tv, ttc: a.ttc + c.ttc }), { ht: 0, tv: 0, ttc: 0 });
  const ligne = (x, i) => {
    const c = calc(x);
    if (!modifiable) return `<tr><td>${esc(x.poste)}</td><td>${esc(x.designation)}</td><td class="n">${esc(x.quantite)}</td><td>${esc(x.unite)}</td><td class="n">${euros(x.pu_ht)}</td><td class="n">${euros(c.ht)}</td><td class="n">${esc(x.tva ?? b.tva)} %</td><td class="n">${euros(c.ttc)}</td></tr>`;
    return `<tr data-i="${i}">
      <td data-l="Poste"><select data-b="poste">${POSTES.map(p => `<option ${p === x.poste ? "selected" : ""}>${p}</option>`).join("")}</select></td>
      <td data-l="Désignation"><input data-b="designation" value="${esc(x.designation || "")}" placeholder="Ex. dépose du faux plafond"></td>
      <td data-l="Quantité" class="n"><input data-b="quantite" type="number" step="any" min="0" value="${esc(x.quantite ?? "")}"></td>
      <td data-l="Unité"><select data-b="unite">${UNITES.map(u => `<option ${u === x.unite ? "selected" : ""}>${u}</option>`).join("")}</select></td>
      <td data-l="PU HT (€)" class="n"><input data-b="pu_ht" type="number" step="any" min="0" value="${esc(x.pu_ht ?? "")}"></td>
      <td data-l="Total HT" class="n calc">${euros(c.ht)}</td>
      <td data-l="TVA (%)" class="n"><input data-b="tva" type="number" step="any" min="0" value="${esc(x.tva ?? b.tva ?? 20)}"></td>
      <td data-l="Total TTC" class="n calc">${euros(c.ttc)}</td>
      <td><button class="suppr" data-f="ligne-x" aria-label="Supprimer la ligne">×</button></td></tr>`;
  };
  return `<div class="budget">
    ${lignes.length ? `<table class="tb"><thead><tr><th>Poste</th><th>Désignation</th><th>Qté</th><th>Unité</th><th>PU HT</th><th>Total HT</th><th>TVA</th><th>Total TTC</th>${modifiable ? "<th></th>" : ""}</tr></thead>
      <tbody>${lignes.map(ligne).join("")}</tbody></table>` : `<p class="vide">Aucune ligne de dépense. ${modifiable ? "Ajoutez les postes de travaux un par un : les montants se calculent seuls." : ""}</p>`}
    ${modifiable ? `<button class="puce prim" data-f="ligne+">+ Ajouter une ligne</button>` : ""}
    ${lignes.length ? `<h4>Sous-totaux par poste</h4><table class="tb tot"><tbody>${Object.entries(parPoste).map(([k, c]) => `<tr><td>${esc(k)}</td><td class="n">${euros(c.ht)} HT</td><td class="n">${euros(c.ttc)} TTC</td></tr>`).join("")}</tbody></table>
    <div class="totaux"><div><span>Total HT</span><b>${euros(tot.ht)}</b></div><div><span>TVA</span><b>${euros(tot.tv)}</b></div><div class="ttc"><span>Total TTC</span><b>${euros(tot.ttc)}</b></div></div>` : ""}
    ${b.hypotheses ? `<p class="hypotheses"><b>Hypothèses :</b> ${esc(b.hypotheses)}</p>` : ""}
    <p class="source">${etat.auto && etat.auto.budget === b ? "Proposition préremplie (estimation), " : ""}montants calculés automatiquement à partir des quantités et des prix unitaires.${!Auth.peutBudget() ? " Modification réservée aux comptes autorisés." : ""}</p></div>`;
}

// synthèse en tête de fiche : existant / projet / budget, lisible en un coup d'œil
const net = t => String(t || "").replace(/\[(Plan|Projet|Estimation|Constat|À vérifier sur site)\]\s*/g, "").trim();
const bref = t => { const x = net(t); const p = x.split(/(?<=\.)\s+(?=[A-ZÀ-Ý])/)[0]; return p.replace(/\.$/, ""); };
function totalTTC(b) {
  return (b && b.lignes || []).reduce((a, x) => { const ht = (+x.quantite || 0) * (+x.pu_ht || 0); return a + ht * (1 + ((x.tva ?? b.tva ?? 20) / 100)); }, 0);
}
function rendreSynthese(l) {
  const z = document.getElementById("f-synthese"); if (!z) return;
  const e = etat.contenu.essentiel || {}, f = etat.contenu.futur || {}, b = etat.contenu.budget || {};
  const ttc = totalTTC(b), n = (b.lignes || []).length;
  const trav = net(f.travaux || f.description);
  z.innerHTML = `<div class="cols">
      <div class="bloc existant"><h5>Existant</h5><dl>
        <dt>Affectation actuelle</dt><dd>${esc(bref(e.fonction_actuelle) || "À vérifier sur site")}</dd>
        <dt>Surface actuelle</dt><dd>${esc(net(e.surface) || l.surface || "—")}</dd></dl></div>
      <div class="bloc projet"><h5>Projet</h5><dl>
        <dt>Affectation future</dt><dd>${esc(bref(e.fonction_future) || "À définir")}</dd>
        <dt>Surface future</dt><dd>${esc(net(e.surface_future) || net(e.surface) || "—")}</dd></dl></div>
    </div>
    <div class="budget-cle" data-va="budget" role="button" tabindex="0"><div><span>Budget prévisionnel TTC</span><br><b>${n ? euros(ttc) : "Non chiffré"}</b></div>
      <span>${n ? `${n} poste${n > 1 ? "s" : ""} · estimation à valider` : ""} →</span></div>
    ${trav ? `<p class="travaux"><b>Travaux :</b> ${esc(trav.length > 190 ? trav.slice(0, 187) + "…" : trav)}</p>` : ""}`;
  const go = () => { const t = document.querySelector('[data-a="tab:budget"]'); t && t.click(); };
  z.querySelector(".budget-cle").onclick = go;
  z.querySelector(".budget-cle").onkeydown = ev => { if (ev.key === "Enter") go(); };
}
function rendrePanneau(box, l, onglet) {
  const c = etat.contenu, ed = Auth.peutEditer();
  if (onglet === "budget") { box.innerHTML = htmlBudget(Auth.peutBudget()); return; }
  if (onglet === "galerie") {
    const cats = etat.filtre === "tout" ? etat.photos : etat.photos.filter(p => p.categorie === etat.filtre);
    box.innerHTML = `<div class="filtres-photo">${[["tout", "Toutes"], ...CATEGORIES_PHOTO].map(([k, t]) => `<button class="puce ${etat.filtre === k ? "on" : ""}" data-f="filtre" data-k="${k}">${t} <span class="nb">${k === "tout" ? etat.photos.length : etat.photos.filter(p => p.categorie === k).length}</span></button>`).join("")}</div>
      ${Auth.estAdmin() ? `<button class="puce prim" data-f="ajouter" data-cat="${etat.filtre === "tout" ? "existant" : etat.filtre}">+ Ajouter des photos</button>` : ""}
      ${cats.length ? `<div class="vignettes grande">${cats.map(vignette).join("")}</div>` : `<p class="vide">Aucune photo dans cette catégorie.</p>`}`;
    return;
  }
  const v = c[onglet] || {};
  const champs = CHAMPS[onglet].map(f => champ(onglet, f, v[f[0]], ed)).join("");
  const rien = !ed && !CHAMPS[onglet].some(f => v[f[0]]);
  box.innerHTML = `${dossier(l, onglet)}
    <div class="formulaire">${champs}${rien ? `<p class="vide">Rien n'a encore été renseigné ici.${EN_LIGNE ? " Connectez-vous pour compléter la fiche." : ""}</p>` : ""}</div>
    ${onglet === "actuel" ? htmlPhotos(["existant"], "Photos de l'existant") : ""}
    ${onglet === "futur" ? htmlPhotos(["futur", "references"], "Images du projet (rendus, références)") : ""}`;
  box.querySelectorAll("textarea").forEach(ajuster);
}
function ajuster(t) { t.style.height = "auto"; t.style.height = Math.min(400, t.scrollHeight + 2) + "px"; }

// ------------------------------------------------------------------ photos : import (ordinateur), visionneuse, gestion
function redimensionner(f) {
  return new Promise((ok, ko) => {
    const im = new Image(); const u = URL.createObjectURL(f);
    im.onload = () => {
      const k = Math.min(1, 1800 / Math.max(im.width, im.height));
      const cv = document.createElement("canvas"); cv.width = Math.round(im.width * k); cv.height = Math.round(im.height * k);
      cv.getContext("2d").drawImage(im, 0, 0, cv.width, cv.height);
      URL.revokeObjectURL(u);
      cv.toBlob(b => b ? ok(b) : ko(new Error("Image illisible")), "image/jpeg", 0.82);
    };
    im.onerror = () => ko(new Error("Image illisible"));
    im.src = u;
  });
}
function modale(html) {
  let m = document.getElementById("modale");
  if (!m) { m = document.createElement("div"); m.id = "modale"; m.className = "modale"; document.body.appendChild(m); }
  m.innerHTML = `<div class="boite" role="dialog" aria-modal="true">${html}</div>`;
  m.hidden = false;
  m.onclick = e => { if (e.target === m || e.target.closest("[data-m='fermer']")) m.hidden = true; };
  return m;
}
function dialogueAjout(categorie, apres) {
  const m = modale(`<h3>Ajouter des photos</h3>${EN_LIGNE ? "" : `<p class="source">Base non configurée : les photos sont gardées sur cet appareil uniquement.</p>`}
    <label class="ch">Fichiers (sur cet ordinateur)<input type="file" id="ph-f" accept="image/*" multiple></label>
    <label class="ch">Catégorie<select id="ph-c">${CATEGORIES_PHOTO.map(([k, t]) => `<option value="${k}" ${k === categorie ? "selected" : ""}>${t}</option>`).join("")}</select></label>
    <label class="ch">Légende<input id="ph-l" placeholder="Ex. fissure en pied de mur, façade sud"></label>
    <label class="ch">Date de la photo<input id="ph-d" type="date" value="${new Date().toISOString().slice(0, 10)}"></label>
    <p class="source" id="ph-etat"></p>
    <div class="actions"><button class="puce" data-m="fermer">Annuler</button><button class="puce prim" id="ph-ok">Importer</button></div>`);
  m.querySelector("#ph-ok").onclick = async () => {
    const fs = [...m.querySelector("#ph-f").files];
    if (!fs.length) { m.querySelector("#ph-etat").textContent = "Choisissez au moins une image."; return; }
    const meta = { categorie: m.querySelector("#ph-c").value, legende: m.querySelector("#ph-l").value.trim(), date_prise: m.querySelector("#ph-d").value || null };
    const st = m.querySelector("#ph-etat");
    try {
      for (let i = 0; i < fs.length; i++) {
        st.textContent = `Envoi ${i + 1} / ${fs.length}…`;
        await Base.ajouterPhoto(etat.id, await redimensionner(fs[i]), meta);
      }
      m.hidden = true; T.toast(`${fs.length} photo(s) ajoutée(s).`); apres();
    } catch (e) { st.textContent = "Échec : " + e.message; }
  };
}
function visionneuse(p, apres) {
  const admin = Auth.estAdmin() && !p.statique;      // photos du dossier : gérées dans le dépôt (data/photos.json)
  const m = modale(`<figure class="grand"><img src="${esc(p.url)}" alt="${esc(p.legende || "")}"></figure>
    ${admin ? `<label class="ch">Légende<input id="pv-l" value="${esc(p.legende || "")}"></label>
      <div class="rang2"><label class="ch">Date<input id="pv-d" type="date" value="${esc((p.date_prise || "").slice(0, 10))}"></label>
      <label class="ch">Catégorie<select id="pv-c">${CATEGORIES_PHOTO.map(([k, t]) => `<option value="${k}" ${k === p.categorie ? "selected" : ""}>${t}</option>`).join("")}</select></label></div>
      <div class="actions"><button class="puce danger" id="pv-x">Supprimer</button><label class="puce">Remplacer l'image<input type="file" id="pv-r" accept="image/*" hidden></label>
      <button class="puce" data-m="fermer">Fermer</button><button class="puce prim" id="pv-ok">Enregistrer</button></div>`
    : `<p><b>${esc(p.legende || "Sans légende")}</b>${p.date_prise ? ` · ${esc(new Date(p.date_prise).toLocaleDateString("fr-FR"))}` : ""} · ${esc((CATEGORIES_PHOTO.find(c => c[0] === p.categorie) || [, ""])[1])}</p>
      <div class="actions"><button class="puce" data-m="fermer">Fermer</button></div>`}`);
  if (!admin) return;
  m.querySelector("#pv-ok").onclick = async () => {
    try { await Base.majPhoto(p, { legende: m.querySelector("#pv-l").value.trim(), date_prise: m.querySelector("#pv-d").value || null, categorie: m.querySelector("#pv-c").value }); m.hidden = true; apres(); }
    catch (e) { T.toast(e.message); }
  };
  m.querySelector("#pv-x").onclick = async () => {
    if (!confirm("Supprimer définitivement cette photo ?")) return;
    try { await Base.supprimerPhoto(p); m.hidden = true; T.toast("Photo supprimée."); apres(); } catch (e) { T.toast(e.message); }
  };
  m.querySelector("#pv-r").onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    try { await Base.remplacerPhoto(p, await redimensionner(f)); m.hidden = true; T.toast("Image remplacée."); apres(); } catch (er) { T.toast(er.message); }
  };
}

// ------------------------------------------------------------------ intégration dans la fiche
let T = null;
const FICHES = {
  EN_LIGNE, Auth, Sauvegarde, ONGLETS: [["essentiel", "Essentiel"], ["actuel", "Actuel"], ["futur", "Futur"], ["budget", "Budget"], ["galerie", "Galerie"]],
  async monter(box, l, onglet) {
    T = window.TREMPLIN;
    if (etat.id !== l.id) {
      etat.id = l.id; etat.contenu = vide(); etat.photos = []; etat.filtre = "tout";
      box.innerHTML = `<p class="vide">Chargement de la fiche…</p>`;
      const [d, ph, autos] = await Promise.all([Base.lireFiche(l.id), Base.photos(l.id), fichesAuto(l.niveau)]);
      if (etat.id !== l.id) return;
      const enAttente = Sauvegarde.attente[l.id];
      etat.auto = autos[l.id] || null;
      etat.contenu = fusion(etat.auto, enAttente || (d && d.contenu) || null);
      etat.maj = d && d.updated_at ? d : null;
      etat.photos = ph;
    }
    if (!box) { rendreSynthese(l); return; }        // onglet « Couper » : seule la synthèse est remplie
    const recharger = async () => { etat.photos = await Base.photos(l.id); rendrePanneau(box, l, onglet); };
    rendrePanneau(box, l, onglet);
    rendreSynthese(l);
    const pied = document.querySelector(".fiche-meta");
    if (pied) pied.innerHTML = etat.maj ? `Dernière modification : ${new Date(etat.maj.updated_at).toLocaleString("fr-FR")}${etat.maj.maj_par ? " · " + esc(etat.maj.maj_par) : ""}` : "";
    box.oninput = e => {
      const t = e.target;
      if (t.dataset.o) {
        etat.contenu[t.dataset.o] = { ...(etat.contenu[t.dataset.o] || {}), [t.dataset.c]: t.value };
        if (t.tagName === "TEXTAREA") ajuster(t);
        Sauvegarde.planifier(l.id, etat.contenu);
        rendreSynthese(l);
      } else if (t.dataset.b) {
        const i = +t.closest("tr").dataset.i;
        const lg = etat.contenu.budget.lignes[i];
        lg[t.dataset.b] = ["quantite", "pu_ht", "tva"].includes(t.dataset.b) ? (t.value === "" ? "" : Number(t.value)) : t.value;
        etat.contenu.budget.modifie = true;
        Sauvegarde.planifier(l.id, etat.contenu);
        // recalcul immédiat sans perdre le champ actif
        const tr = t.closest("tr"), b = etat.contenu.budget, ht = (+lg.quantite || 0) * (+lg.pu_ht || 0), ttc = ht * (1 + ((lg.tva ?? b.tva ?? 20) / 100));
        const cs = tr.querySelectorAll(".calc"); cs[0].textContent = euros(ht); cs[1].textContent = euros(ttc);
        clearTimeout(box._tot); box._tot = setTimeout(() => { rendreSynthese(l); const f = document.activeElement; const sel = f && f.dataset.b && [f.closest("tr").dataset.i, f.dataset.b]; rendrePanneau(box, l, onglet); if (sel) { const n = box.querySelector(`tr[data-i="${sel[0]}"] [data-b="${sel[1]}"]`); n && n.focus(); } }, 900);
      }
    };
    box.onchange = box.oninput;
    box.onclick = e => {
      const b = e.target.closest("[data-f]"); if (!b) return;
      const f = b.dataset.f;
      if (f === "ligne+") {
        const bud = etat.contenu.budget = etat.contenu.budget || { tva: 20, lignes: [] };
        bud.modifie = true;
        bud.lignes.push({ id: uid(), poste: POSTES[0], designation: "", quantite: "", unite: "m²", pu_ht: "", tva: bud.tva ?? 20 });
        Sauvegarde.planifier(l.id, etat.contenu); rendrePanneau(box, l, onglet);
        const n = box.querySelector("tbody tr:last-child [data-b='designation']"); n && n.focus();
      } else if (f === "ligne-x") {
        const i = +b.closest("tr").dataset.i, lg = etat.contenu.budget.lignes[i];
        if ((lg.designation || lg.pu_ht) && !confirm(`Supprimer la ligne « ${lg.designation || lg.poste} » ?`)) return;
        etat.contenu.budget.lignes.splice(i, 1); etat.contenu.budget.modifie = true; Sauvegarde.planifier(l.id, etat.contenu); rendrePanneau(box, l, onglet);
      } else if (f === "ajouter") dialogueAjout(b.dataset.cat, recharger);
      else if (f === "voir") { const p = etat.photos.find(x => x.id === b.dataset.id); p && visionneuse(p, recharger); }
      else if (f === "filtre") { etat.filtre = b.dataset.k; rendrePanneau(box, l, onglet); }
    };
    Sauvegarde.afficher(Object.keys(Sauvegarde.attente).length ? "attente" : Sauvegarde.etat);
  },
  oublier() { etat.id = null; },
  boutonCompte() {
    if (!EN_LIGNE) return `<span class="compte local" title="Base non configurée : consultation seule (propriétaire : ?edition=1)">${EDITION_LOCALE ? "Propriétaire · local" : "Consultation"}</span>`;
    if (!Auth.session) return `<button class="compte" data-compte="entrer">Connexion</button>`;
    return `${Auth.estProprietaire() ? `<button class="compte" data-compte="droits">Utilisateurs</button>` : ""}<button class="compte" data-compte="sortir" title="${esc(Auth.nom)}">${Auth.role === "proprietaire" ? "Propriétaire" : Auth.role === "admin" ? "Administrateur" : "Lecteur"} · Déconnexion</button>`;
  },
  dialogueConnexion(apres) {
    const m = modale(`<h3>Connexion</h3><p class="source">Réservée aux membres autorisés du projet.</p>
      <label class="ch">Adresse e-mail<input id="cx-e" type="email" autocomplete="username"></label>
      <label class="ch">Mot de passe<input id="cx-m" type="password" autocomplete="current-password"></label>
      <p class="source" id="cx-err"></p>
      <div class="actions"><button class="puce" data-m="fermer">Annuler</button><button class="puce prim" id="cx-ok">Se connecter</button></div>`);
    const go = async () => {
      try { await Auth.connexion(m.querySelector("#cx-e").value.trim(), m.querySelector("#cx-m").value); m.hidden = true; etat.id = null; apres(); }
      catch (e) { m.querySelector("#cx-err").textContent = e.message; }
    };
    m.querySelector("#cx-ok").onclick = go;
    m.querySelector("#cx-m").onkeydown = e => { if (e.key === "Enter") go(); };
  },
  async dialogueDroits() {
    const m = modale(`<h3>Utilisateurs et permissions</h3><p class="source">Chargement…</p>`);
    try {
      const r = await api("/rest/v1/profils?select=id,email,nom,role,permissions&order=email");
      if (!r.ok) throw new Error("Accès refusé");
      const l = await r.json();
      const DR = [["fiches", "Fiches"], ["budget", "Budgets"], ["photos", "Photos"]];
      m.querySelector(".boite").innerHTML = `<h3>Utilisateurs et permissions</h3>
        <p class="source">Les comptes se créent dans Supabase (Authentication → Users). Ici, le propriétaire attribue les rôles et les droits.</p>
        <table class="tb droits"><thead><tr><th>Compte</th><th>Rôle</th>${DR.map(d => `<th>${d[1]}</th>`).join("")}</tr></thead><tbody>
        ${l.map(u => `<tr data-u="${esc(u.id)}"><td>${esc(u.nom || u.email || u.id)}<br><small>${esc(u.email || "")}</small></td>
          <td><select data-r ${u.id === Auth.session.user.id ? "disabled" : ""}>${["lecteur", "admin", "proprietaire"].map(x => `<option ${x === u.role ? "selected" : ""}>${x}</option>`).join("")}</select></td>
          ${DR.map(([k]) => `<td><input type="checkbox" data-p="${k}" ${(u.permissions || {})[k] ? "checked" : ""} ${u.role !== "admin" ? "disabled" : ""}></td>`).join("")}</tr>`).join("")}
        </tbody></table><p class="source" id="dr-etat"></p><div class="actions"><button class="puce" data-m="fermer">Fermer</button></div>`;
      m.querySelector("tbody").onchange = async e => {
        const tr = e.target.closest("tr"); const id = tr.dataset.u;
        const role = tr.querySelector("[data-r]").value;
        const permissions = Object.fromEntries([...tr.querySelectorAll("[data-p]")].map(c => [c.dataset.p, c.checked]));
        tr.querySelectorAll("[data-p]").forEach(c => c.disabled = role !== "admin");
        if (role === "proprietaire" && !confirm("Donner le rôle de propriétaire (tous les droits) à ce compte ?")) { e.target.value = "admin"; return; }
        const w = await api(`/rest/v1/profils?id=eq.${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ role, permissions }) });
        m.querySelector("#dr-etat").textContent = w.ok ? "Droits enregistrés." : "Échec de l'enregistrement.";
      };
    } catch (e) { m.querySelector(".boite").innerHTML = `<h3>Utilisateurs</h3><p>${esc(e.message)}</p><div class="actions"><button class="puce" data-m="fermer">Fermer</button></div>`; }
  },
  pret: Auth.init()
};
window.FICHES = FICHES;
})();
