/* Le Tremplin · plans interactifs. Aucune dépendance externe. */
(() => {
"use strict";
const C = window.CONFIG || {};
const $ = (s, r = document) => r.querySelector(s);
const NS = "http://www.w3.org/2000/svg";
const params = new URLSearchParams(location.search);
const EDITION = params.get("edition") === "1";

// ---------------------------------------------------------------- stockage local (facultatif)
const stock = {
  get(k, d) { try { const v = localStorage.getItem("tremplin:" + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("tremplin:" + k, JSON.stringify(v)); return true; } catch { return false; } },
  del(k) { try { localStorage.removeItem("tremplin:" + k); } catch {} }
};
const session = {
  get(k, d) { try { const v = sessionStorage.getItem("tremplin:" + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { sessionStorage.setItem("tremplin:" + k, JSON.stringify(v)); } catch {} }
};

// ---------------------------------------------------------------- état
const S = {
  data: null, niveau: null, sel: null, etat: stock.get("etat", "existant"),
  cachees: new Set(stock.get("cachees", [])), onglet: "essentiel",
  v: { x: 0, y: 0, s: 1 }, fit: 1, w: 1, h: 1, hd: false
};
const el = {
  vp: $("#viewport"), ct: $("#contenu"), img: $("#plan-img"), psvg: $("#plan-svg"), calque: $("#calque"),
  fiche: $("#fiche"), corps: $("#fiche-corps"), niveaux: $("#niveaux"), zone: $(".scene-zone")
};

const norm = s => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const niv = id => S.data.niveaux.find(n => n.id === id);
const loc = id => S.data.locaux.find(l => l.id === id);
const zp = id => (S.data.zonesProjet || []).find(z => z.id === id);
const cat = id => S.data.categories[id] || { nom: id, couleur: "#888" };
const FIA = { C: "Constat", H: "Hypothèse", P: "Préconisation" };

function toast(t, ms = 2200) {
  const n = $("#toast"); n.textContent = t; n.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => (n.hidden = true), ms);
}

// ---------------------------------------------------------------- chargement
async function charger() {
  let d = null;
  if (EDITION) d = stock.get("brouillon", null);
  if (!d) {
    const r = await fetch("data/donnees.json", { cache: "no-cache" });
    d = await r.json();
  }
  S.data = d;
}

// ---------------------------------------------------------------- vue (zoom / déplacement)
function appliquer() {
  const { x, y, s } = S.v;
  el.ct.style.transform = `translate(${x}px,${y}px) scale(${s})`;
  el.calque.style.setProperty("--inv", (1 / s).toFixed(5));
  majHD();
}
function rectVisible() {
  const r = el.vp.getBoundingClientRect();
  let h = r.height;
  if (!el.fiche.hidden && innerWidth < 1000) {
    // hauteur réelle de la fiche (sans l'animation d'entrée)
    const haut = innerHeight - el.fiche.offsetHeight;
    h = Math.max(120, Math.min(r.height, haut - r.top));
  }
  return { w: r.width, h, left: r.left, top: r.top };
}
function ajuster(anime) {
  const r = rectVisible(), pad = 14;
  S.fit = Math.min((r.w - pad * 2) / S.w, (r.h - pad * 2) / S.h);
  allerA(S.fit, (r.w - S.w * S.fit) / 2, (r.h - S.h * S.fit) / 2, anime);
}
function allerA(s, x, y, anime) {
  if (anime) {
    el.ct.classList.add("anime");
    clearTimeout(allerA.t); allerA.t = setTimeout(() => el.ct.classList.remove("anime"), 650);
  }
  S.v = { x, y, s }; appliquer();
}
function bornes(s) { return Math.min(Math.max(s, S.fit * 0.6), S.fit * 14); }
function zoomA(f, cx, cy) {
  const v = S.v, ns = bornes(v.s * f);
  allerA(ns, cx - (cx - v.x) * ns / v.s, cy - (cy - v.y) * ns / v.s);
}
function ecranVersPlan(cx, cy) {
  const r = el.vp.getBoundingClientRect();
  return { x: (cx - r.left - S.v.x) / S.v.s, y: (cy - r.top - S.v.y) / S.v.s };
}
function boite(forme) {
  if (!forme) return null;
  if (forme.type === "point") return { x1: forme.x, y1: forme.y, x2: forme.x, y2: forme.y, pt: true };
  const xs = forme.points.map(p => p[0]), ys = forme.points.map(p => p[1]);
  return { x1: Math.min(...xs), y1: Math.min(...ys), x2: Math.max(...xs), y2: Math.max(...ys) };
}
function centrerSur(forme) {
  const b = boite(forme); if (!b) return;
  const r = rectVisible();
  const bw = Math.max(b.x2 - b.x1, 1), bh = Math.max(b.y2 - b.y1, 1);
  let s = b.pt ? S.fit * 3 : Math.min(r.w / (bw * 2.4), r.h / (bh * 2.4));
  s = Math.min(Math.max(s, S.fit * 1.15), S.fit * 7);
  const cx = (b.x1 + b.x2) / 2, cy = (b.y1 + b.y2) / 2;
  allerA(s, r.w / 2 - cx * s, r.h / 2 - cy * s, true);
}
function majHD() {
  const n = S.niveau; if (!n || !n.plan.src || S.hd) return;
  const dpr = window.devicePixelRatio || 1;
  if (S.v.s * dpr * S.w > 1700) {
    S.hd = true;
    const im = new Image();
    im.onload = () => { if (S.niveau === n) el.img.src = n.plan.src; };
    im.src = n.plan.src;
  }
}

// gestes : un doigt = déplacer, deux doigts = zoomer, toucher court = sélectionner
const pts = new Map();
let geste = null;
el.vp.addEventListener("pointerdown", e => {
  if (e.target.closest(".zoom,.legende")) return;
  pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
  el.vp.classList.add("saisi");
  if (pts.size === 1) geste = { x0: e.clientX, y0: e.clientY, t0: Date.now(), bouge: 0, vx: S.v.x, vy: S.v.y };
  else geste && (geste.bouge = 99);
  $("#astuce").classList.add("cache");
});
addEventListener("pointermove", e => {
  if (!pts.has(e.pointerId)) return;
  const avant = [...pts.values()].map(p => ({ ...p }));
  pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
  const apres = [...pts.values()];
  const r = el.vp.getBoundingClientRect();
  if (apres.length === 1 && geste) {
    const dx = e.clientX - geste.x0, dy = e.clientY - geste.y0;
    geste.bouge = Math.max(geste.bouge, Math.hypot(dx, dy));
    if (geste.bouge > 6) allerA(S.v.s, geste.vx + dx, geste.vy + dy);
  } else if (apres.length >= 2) {
    const d0 = Math.hypot(avant[0].x - avant[1].x, avant[0].y - avant[1].y);
    const d1 = Math.hypot(apres[0].x - apres[1].x, apres[0].y - apres[1].y);
    const m0 = { x: (avant[0].x + avant[1].x) / 2 - r.left, y: (avant[0].y + avant[1].y) / 2 - r.top };
    const m1 = { x: (apres[0].x + apres[1].x) / 2 - r.left, y: (apres[0].y + apres[1].y) / 2 - r.top };
    if (d0 > 0) {
      const ns = bornes(S.v.s * d1 / d0);
      const x = m1.x - (m0.x - S.v.x) * ns / S.v.s, y = m1.y - (m0.y - S.v.y) * ns / S.v.s;
      allerA(ns, x, y);
    }
  }
});
function fin(e) {
  if (!pts.has(e.pointerId)) return;
  pts.delete(e.pointerId);
  if (pts.size === 0) {
    el.vp.classList.remove("saisi");
    if (geste && geste.bouge <= 6 && Date.now() - geste.t0 < 600) toucher(e.clientX, e.clientY);
    geste = null;
  } else if (pts.size === 1) {
    const p = [...pts.values()][0];
    geste = { x0: p.x, y0: p.y, t0: 0, bouge: 99, vx: S.v.x, vy: S.v.y };
  }
}
addEventListener("pointerup", fin);
addEventListener("pointercancel", fin);
el.vp.addEventListener("wheel", e => {
  e.preventDefault();
  const r = el.vp.getBoundingClientRect();
  zoomA(Math.exp(-e.deltaY * 0.0016), e.clientX - r.left, e.clientY - r.top);
}, { passive: false });
let dernierTap = 0;
function toucher(cx, cy) {
  const API = window.TREMPLIN;
  if (API && API.surTap && API.surTap(ecranVersPlan(cx, cy))) return;
  const maintenant = Date.now();
  const cible = document.elementFromPoint(cx, cy);
  const z = cible && cible.closest("[data-id]");
  if (z) { ouvrir(z.dataset.id, { kind: z.dataset.kind, centrer: false }); dernierTap = 0; return; }
  if (maintenant - dernierTap < 320) {
    const r = el.vp.getBoundingClientRect();
    el.ct.classList.add("anime"); setTimeout(() => el.ct.classList.remove("anime"), 650);
    zoomA(2, cx - r.left, cy - r.top); dernierTap = 0; return;
  }
  dernierTap = maintenant;
}
$("#z-plus").onclick = () => { const r = el.vp.getBoundingClientRect(); el.ct.classList.add("anime"); zoomA(1.6, r.width / 2, r.height / 2); setTimeout(() => el.ct.classList.remove("anime"), 650); };
$("#z-moins").onclick = () => { const r = el.vp.getBoundingClientRect(); el.ct.classList.add("anime"); zoomA(1 / 1.6, r.width / 2, r.height / 2); setTimeout(() => el.ct.classList.remove("anime"), 650); };
$("#z-tout").onclick = () => ajuster(true);
new ResizeObserver(() => { if (!S.niveau) return; S.sel && S.sel.forme ? centrerSur(S.sel.forme) : ajuster(); }).observe(el.vp);

// ---------------------------------------------------------------- niveaux
function rail() {
  el.niveaux.innerHTML = "";
  S.data.niveaux.forEach((n, i) => {
    const nb = S.data.locaux.filter(l => l.niveau === n.id && (l.categorie === "technique" || l.categorie === "securite")).length;
    const b = document.createElement("button");
    b.className = "niv" + (/supposé/i.test(n.note || "") ? " suppose" : "");
    b.dataset.niv = n.id;
    b.title = n.nom;
    b.innerHTML = `<span class="etage">${esc(n.court)}</span><span class="lib">${esc(n.nom)}<small>${esc(n.alt || "")}</small></span>${nb ? `<span class="compte" title="${nb} local(aux) technique(s)">${nb}</span>` : ""}`;
    b.onclick = () => choisirNiveau(n.id, { url: true });
    el.niveaux.appendChild(b);
    if (n.id === "site") { const s = document.createElement("div"); s.className = "sep"; el.niveaux.appendChild(s); }
  });
}
function choisirNiveau(id, o = {}) {
  const n = niv(id); if (!n) return;
  const change = S.niveau !== n;
  S.niveau = n;
  document.querySelectorAll(".niv").forEach(b => b.classList.toggle("on", b.dataset.niv === id));
  $("#niv-titre").textContent = n.nom;
  const note = $("#niv-note"); note.textContent = n.note || ""; note.classList.toggle("suppose", /supposé|non fourni/i.test(n.note || ""));
  if (change) {
    S.w = n.plan.w; S.h = n.plan.h; S.hd = false;
    el.ct.style.width = S.w + "px"; el.ct.style.height = S.h + "px";
    if (n.plan.vecto) {
      // plan vectoriel (DXF converti) : SVG chargé puis inséré pour que app.css / cad.css le stylent
      el.img.hidden = true; el.img.removeAttribute("src");
      el.psvg.hidden = false; el.psvg.innerHTML = "";
      chargerVecto(n.plan.vecto).then(txt => {
        if (S.niveau !== n) return;
        el.psvg.innerHTML = txt;
        const s = el.psvg.querySelector("svg");
        if (s) { s.setAttribute("width", S.w); s.setAttribute("height", S.h); }
      }).catch(() => toast("Plan indisponible hors ligne."));
    } else if (n.plan.svg) {
      el.img.hidden = true; el.img.removeAttribute("src");
      el.psvg.hidden = false;
      el.psvg.innerHTML = `<svg xmlns="${NS}" viewBox="0 0 ${S.w} ${S.h}" width="${S.w}" height="${S.h}">${n.plan.svg}</svg>`;
    } else {
      el.psvg.hidden = true; el.psvg.innerHTML = "";
      el.img.hidden = false; el.img.width = S.w; el.img.height = S.h;
      el.img.src = n.plan.leger || n.plan.src;
    }
    el.calque.setAttribute("viewBox", `0 0 ${S.w} ${S.h}`);
    el.calque.setAttribute("width", S.w); el.calque.setAttribute("height", S.h);
    if (!o.garderFiche && S.sel && S.sel.niveau !== id) fermerFiche(true);
    ajuster(false);
  }
  dessiner();
  if (o.url) majUrl({ niveau: id });
}

const cacheVecto = new Map();
function chargerVecto(url) {
  if (!cacheVecto.has(url)) {
    cacheVecto.set(url, fetch(url).then(r => { if (!r.ok) throw new Error(r.status); return r.text(); })
      .catch(e => { cacheVecto.delete(url); throw e; }));
  }
  return cacheVecto.get(url);
}

// ---------------------------------------------------------------- dessin des zones
function svg(tag, attrs, parent) {
  const n = document.createElementNS(NS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  parent && parent.appendChild(n);
  return n;
}
function centre(forme) {
  if (forme.type === "point") return [forme.x, forme.y];
  // centre de masse du polygone
  let a = 0, x = 0, y = 0; const p = forme.points;
  for (let i = 0; i < p.length; i++) {
    const [x0, y0] = p[i], [x1, y1] = p[(i + 1) % p.length], f = x0 * y1 - x1 * y0;
    a += f; x += (x0 + x1) * f; y += (y0 + y1) * f;
  }
  if (Math.abs(a) < 1e-6) { const b = boite(forme); return [(b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2]; }
  return [x / (3 * a), y / (3 * a)];
}
function forme2svg(forme, attrs, parent) {
  if (forme.type === "point") return null;
  return svg("polygon", { points: forme.points.map(p => p.join(",")).join(" "), ...attrs }, parent);
}
function dessiner() {
  const c = el.calque; c.innerHTML = "";
  const n = S.niveau; if (!n) return;
  const gz = svg("g", {}, c), ge = svg("g", {}, c), gp = svg("g", {}, c);
  const legende = new Map();
  // sur un plan vectoriel, les noms des salles sont déjà dessinés : pas d'étiquette en double
  const vecto = !!n.plan.vecto;
  el.vp.classList.toggle("vecto", vecto);
  if (S.etat === "projet") {
    (S.data.zonesProjet || []).filter(z => z.niveau === n.id && !S.cachees.has(z.categorie)).forEach(z => {
      const col = cat(z.categorie).couleur; legende.set(z.categorie, col);
      forme2svg(z.forme, { class: "z z-projet", fill: col, "data-id": z.id, "data-kind": "projet" }, gz);
      if (vecto) return;
      const [x, y] = centre(z.forme);
      const t = svg("text", { x, y, class: "etiq etiq-projet", "text-anchor": "middle", "dominant-baseline": "middle" }, ge);
      t.textContent = z.nom;
    });
  }
  S.data.locaux.filter(l => l.niveau === n.id && l.forme && !S.cachees.has(l.categorie)).forEach(l => {
    if (S.etat === "projet" && !["technique", "securite", "circulation", "batiment"].includes(l.categorie)) return;
    const col = cat(l.categorie).couleur;
    legende.set(l.categorie, col);
    if (l.forme.type === "point") {
      const g = svg("g", { class: "repere" + (/localiser/i.test(l.resume + l.remarques) ? " alocaliser" : ""), "data-id": l.id, "data-kind": "local" }, gp);
      g.style.transformOrigin = `${l.forme.x}px ${l.forme.y}px`;
      g.style.transform = "scale(var(--inv))";
      svg("circle", { cx: l.forme.x, cy: l.forme.y, r: 26, class: "halo", fill: col }, g);
      svg("circle", { cx: l.forme.x, cy: l.forme.y, r: 13, class: "aff", fill: col, stroke: "#fff", "stroke-width": 3 }, g);
      if (!(vecto && l.salleCad)) {
        const t = svg("text", { x: l.forme.x + 20, y: l.forme.y + 5, class: "etiq", "font-size": 14 }, g);
        t.textContent = l.nom;
      }
    } else {
      forme2svg(l.forme, { class: "z z-local" + (S.sel && S.sel.id === l.id ? " sel" : ""), fill: col, stroke: col, "data-id": l.id, "data-kind": "local" }, gz);
      if (S.etat === "existant" && l.categorie !== "batiment" && !(vecto && l.salleCad)) {
        const [x, y] = centre(l.forme);
        const t = svg("text", { x, y, class: "etiq", "text-anchor": "middle", "dominant-baseline": "middle" }, ge);
        t.textContent = l.nom;
      }
    }
  });
  c.style.setProperty("--inv", (1 / S.v.s).toFixed(5));
  // légende
  const lg = $("#legende");
  if (legende.size) {
    lg.hidden = false;
    lg.innerHTML = [...legende].map(([k, col]) => `<span><i style="background:${col}"></i>${esc(cat(k).nom)}</span>`).join("");
  } else lg.hidden = true;
  if (S.sel) marquer(S.sel, false);
}
// tailles d'étiquettes constantes à l'écran
const st = document.createElement("style");
st.textContent = `.calque .etiq{font-size:calc(13px * var(--inv));stroke-width:calc(4px * var(--inv))}
.calque .repere .etiq{font-size:14px;stroke-width:4px}`;
document.head.appendChild(st);

function marquer(item, flash) {
  el.calque.querySelectorAll(".flash,.flash-fin").forEach(n => n.remove());
  el.calque.querySelectorAll(".sel").forEach(n => n.classList.remove("sel"));
  if (!item || !item.forme || item.niveau !== (S.niveau && S.niveau.id)) return;
  const sh = el.calque.querySelector(`[data-id="${CSS.escape(item.id)}"]`);
  sh && sh.classList.add("sel");
  let f;
  if (item.forme.type === "point") {
    f = svg("circle", { cx: item.forme.x, cy: item.forme.y, r: 22, class: flash ? "flash" : "flash-fin" }, el.calque);
    f.style.transformOrigin = `${item.forme.x}px ${item.forme.y}px`; f.style.transform = "scale(var(--inv))";
  } else f = forme2svg(item.forme, { class: flash ? "flash" : "flash-fin" }, el.calque);
  if (flash) setTimeout(() => { f.setAttribute("class", "flash-fin"); }, 2000);
}

// ---------------------------------------------------------------- fiche
function ouvrir(id, o = {}) {
  const kind = o.kind || (loc(id) ? "local" : "projet");
  const item = kind === "projet" ? zp(id) : loc(id);
  if (!item) { toast("Local introuvable : " + id); return; }
  if (!S.niveau || S.niveau.id !== item.niveau) choisirNiveau(item.niveau, { garderFiche: true });
  S.sel = { ...item, kind };
  if (S.sel.id !== (ouvrir.dernier || "")) S.onglet = "essentiel";
  ouvrir.dernier = S.sel.id;
  rendreFiche();
  el.fiche.hidden = false; el.zone.classList.remove("sans-fiche");
  requestAnimationFrame(() => {
    if (o.centrer !== false) centrerSur(item.forme);
    marquer(S.sel, true);
  });
  if (kind === "local") majUrl({ local: id });
  window.TREMPLIN && window.TREMPLIN.surSelection && window.TREMPLIN.surSelection(S.sel);
}
function fermerFiche(silencieux) {
  S.sel = null; el.fiche.hidden = true; el.zone.classList.add("sans-fiche");
  marquer(null);
  if (!silencieux && S.niveau) majUrl({ niveau: S.niveau.id });
  window.TREMPLIN && window.TREMPLIN.surSelection && window.TREMPLIN.surSelection(null);
}
function majUrl(q) {
  const p = new URLSearchParams();
  if (q.local) p.set("local", q.local); else if (q.niveau) p.set("niveau", q.niveau);
  if (EDITION) p.set("edition", "1");
  const s = p.toString();
  history.replaceState(null, "", location.pathname + (s ? "?" + s : ""));
}
function lienPublic(id) { return (C.URL_BASE || location.origin + location.pathname) + "?local=" + encodeURIComponent(id); }

function rendreFiche() {
  const l = S.sel; if (!l) return;
  const c = cat(l.categorie), n = niv(l.niveau);
  const memo = stock.get("perso:" + l.id, {});
  if (l.kind === "projet") {
    el.corps.innerHTML = `
      <div class="f-tete"><h2>${esc(l.nom)}</h2><button class="f-fermer" data-a="fermer" aria-label="Fermer">×</button></div>
      <div class="f-tags"><span class="tag"><i class="pastille" style="background:${c.couleur}"></i>${esc(c.nom)}</span>
        <span class="tag">${esc(n ? n.nom : l.niveau)}</span><span class="tag fia fia-H">H · zonage projet</span></div>
      <p class="f-resume">${esc(l.texte || "Zone du projet.")}</p>
      <div class="f-actions"><button data-a="existant">Voir l'existant</button><button data-a="recentrer">Recentrer</button></div>
      <p class="source">${esc(l.source || "")}. Zonage interprété : ajustable en mode édition.</p>`;
    return;
  }
  const F = window.FICHES;
  const onglets = F.ONGLETS.slice();
  if (!onglets.find(o => o[0] === S.onglet) && S.onglet !== "couper") S.onglet = "essentiel";
  const lienNiv = l.lien && (niv(l.lien) || loc(l.lien));
  const ref = (l.salleCad || "").match(/\d{3}/) ? l.salleCad : "";
  el.corps.innerHTML = `
    <div class="f-tete"><h2>${esc(l.nom)}</h2><button class="f-fermer" data-a="fermer" aria-label="Fermer">×</button></div>
    <div class="f-tags">
      <span class="tag"><i class="pastille" style="background:${c.couleur}"></i>${esc(c.nom)}</span>
      <button class="tag" data-a="niveau">${esc(n ? n.court : l.niveau)}${l.batiment ? " · " + esc(l.batiment) : ""}</button>
      ${l.surface ? `<span class="tag">${esc(l.surface)}</span>` : ""}
      <span class="tag fia fia-${esc(l.fiabilite)}" title="${esc(FIA[l.fiabilite] || "")}">${esc(l.fiabilite)} · ${esc(FIA[l.fiabilite] || "")}</span>
    </div>
    <div class="f-actions">
      ${lienNiv ? `<button class="prim" data-a="lien">Aller : ${esc((niv(l.lien) || loc(l.lien)).nom)} →</button>` : ""}
      ${l.coupure && l.coupure.length ? `<button class="${S.onglet === "couper" ? "prim" : ""}" data-a="tab:couper">⚠ Couper / sécuriser</button>` : ""}
      <button data-a="recentrer">Recentrer</button>
      <button data-a="partager">Partager</button>
    </div>
    <div class="f-etat"><span class="sauve ok"></span>${F.boutonCompte()}</div>
    <div class="onglets" role="tablist">${onglets.map(([k, t]) => `<button role="tab" data-a="tab:${k}" class="${S.onglet === k ? "on" : ""}">${t}</button>`).join("")}</div>
    <div class="panneau" id="f-panneau">${S.onglet === "couper" ? panneau(l, memo) : ""}</div>
    <div class="f-nav"><button data-a="prec">← Local précédent</button><button data-a="suiv">Local suivant →</button></div>
    <p class="source fiche-meta"></p>
    <p class="source">Identifiant : ${esc(l.id)}${l.remarques ? `<br>${esc(l.remarques)}` : ""}</p>`;
  if (S.onglet !== "couper") F.monter(el.corps.querySelector("#f-panneau"), l, S.onglet);
  else F.Sauvegarde.afficher(F.Sauvegarde.etat);
  el.corps.querySelector("[data-compte]") && (el.corps.querySelector("[data-compte]").onclick = e => {
    if (e.currentTarget.dataset.compte === "entrer") F.dialogueConnexion(() => rendreFiche());
    else { F.Auth.deconnexion(); F.oublier(); rendreFiche(); toast("Déconnecté."); }
  });
}
function panneau(l, memo) {
  if (S.onglet === "essentiel") {
    const lignes = [["Fonction", l.fonction], ["Surface", l.surface], ["Accès", l.acces]].filter(x => x[1]);
    return `<p class="f-resume">${esc(l.resume || "")}</p>
      ${lignes.map(([k, v]) => `<div class="ligne"><b>${k}</b><span>${esc(v)}</span></div>`).join("")}
      ${(l.risques || []).slice(0, 2).map(r => `<div class="risque ${esc(r.niveau)}" style="margin-top:10px"><b>${esc(r.niveau)}</b><span>${esc(r.texte)}</span></div>`).join("")}
      <div class="appels">${(S.data.urgences || []).map(u => `<a href="tel:${esc(u.numero)}">${esc(u.numero)}<small>${esc(u.nom)}</small></a>`).join("")}</div>`;
  }
  if (S.onglet === "couper") {
    const faits = session.get("coupure:" + l.id, []);
    const nb = faits.length, tot = l.coupure.length;
    return `<div class="progres"><span>${nb} / ${tot} fait${nb > 1 ? "s" : ""}</span><div class="barre-p"><i style="width:${(100 * nb / tot) | 0}%"></i></div>
        ${nb ? `<button class="puce" data-a="raz">Recommencer</button>` : ""}</div>
      <ol class="etapes">${l.coupure.map((k, i) => `<li><button class="etape ${faits.includes(i) ? "fait" : ""}" data-a="etape:${i}"><span class="num"><span>${i + 1}</span></span><span>${esc(k.texte)}</span><span class="f" title="${esc(FIA[k.fiabilite] || "")}">${esc(k.fiabilite)}</span></button></li>`).join("")}</ol>
      <div class="appels">${(S.data.urgences || []).map(u => `<a href="tel:${esc(u.numero)}">${esc(u.numero)}<small>${esc(u.nom)}</small></a>`).join("")}</div>
      <p class="source">Touchez une étape pour la cocher. Les étapes marquées H sont des hypothèses d'étude.</p>`;
  }
  if (S.onglet === "equip") {
    return `${(l.equipements || []).length ? `<div class="cartes">${l.equipements.map(e => `<div class="carte"><button data-a="carte"><span class="tag fia fia-${esc(e.fiabilite)}">${esc(e.fiabilite)}</span>${esc(e.nom)}</button><div class="det">${esc(e.detail || "Pas de détail.")}</div></div>`).join("")}</div>` : `<p class="vide">Aucun équipement renseigné.</p>`}
      ${(l.risques || []).length ? `<h3 style="font-size:14px;margin:16px 0 8px">Risques</h3>${l.risques.map(r => `<div class="risque ${esc(r.niveau)}"><b>${esc(r.niveau)}</b><span>${esc(r.texte)}</span></div>`).join("")}` : ""}`;
  }
  if (S.onglet === "projet") {
    return `<div class="bascule"><div class="av"><h4>Aujourd'hui</h4>${esc(l.resume)}</div><div class="ap"><h4>Dans le projet</h4>${esc(l.projet)}</div></div>
      <button class="puce" data-a="voirprojet">Afficher le plan projet</button>`;
  }
  return `<div class="perso">
      <button class="verif ${memo.verifie ? "on" : ""}" data-a="verif"><span class="case"></span>J'ai vérifié ce local sur place</button>
      <label for="notes">Mes notes (gardées sur cet appareil)</label>
      <textarea id="notes" placeholder="Ce que j'ai vu, ce qui manque, une question pour le groupe…">${esc(memo.notes || "")}</textarea>
      <label>Photo</label>
      <div class="photo">${memo.photo ? `<img src="${memo.photo}" alt="Photo de ${esc(l.nom)}">` : (l.photo ? `<img src="${esc(l.photo)}" alt="">` : `<span>Emplacement photo vide.<br>Touchez pour en prendre une (gardée sur cet appareil).</span>`)}
        <input type="file" id="photo-in" accept="image/*" capture="environment" aria-label="Ajouter une photo"></div>
      ${memo.photo ? `<button class="puce" data-a="photo-x" style="margin-top:8px">Retirer ma photo</button>` : ""}
    </div>`;
}
function photo(f, id) {
  if (!f) return;
  const r = new FileReader();
  r.onload = () => {
    const im = new Image();
    im.onload = () => {
      const k = Math.min(1, 900 / Math.max(im.width, im.height));
      const cv = document.createElement("canvas"); cv.width = im.width * k; cv.height = im.height * k;
      cv.getContext("2d").drawImage(im, 0, 0, cv.width, cv.height);
      const m = stock.get("perso:" + id, {}); m.photo = cv.toDataURL("image/jpeg", .72);
      if (!stock.set("perso:" + id, m)) toast("Mémoire pleine : photo non gardée.");
      rendreFiche();
    };
    im.src = r.result;
  };
  r.readAsDataURL(f);
}
el.corps.addEventListener("click", e => {
  const b = e.target.closest("[data-a]"); if (!b || !S.sel) return;
  const a = b.dataset.a, l = S.sel;
  if (a === "fermer") fermerFiche();
  else if (a === "recentrer") { centrerSur(l.forme); marquer(l, true); }
  else if (a === "niveau") choisirNiveau(l.niveau, { garderFiche: true });
  else if (a.startsWith("tab:")) { S.onglet = a.slice(4); rendreFiche(); el.corps.scrollTop = 0; }
  else if (a.startsWith("etape:")) {
    const i = +a.slice(6), k = "coupure:" + l.id, f = session.get(k, []);
    const j = f.indexOf(i); j < 0 ? f.push(i) : f.splice(j, 1); session.set(k, f);
    if (navigator.vibrate) navigator.vibrate(15);
    rendreFiche();
    if (f.length === l.coupure.length) toast("Toutes les étapes sont cochées.");
  }
  else if (a === "raz") { session.set("coupure:" + l.id, []); rendreFiche(); }
  else if (a === "carte") b.parentElement.classList.toggle("ouv");
  else if (a === "verif") { const m = stock.get("perso:" + l.id, {}); m.verifie = !m.verifie; stock.set("perso:" + l.id, m); rendreFiche(); }
  else if (a === "photo-x") { const m = stock.get("perso:" + l.id, {}); delete m.photo; stock.set("perso:" + l.id, m); rendreFiche(); }
  else if (a === "voirprojet") { etat("projet"); }
  else if (a === "existant") { etat("existant"); fermerFiche(); }
  else if (a === "lien") { niv(l.lien) ? (fermerFiche(true), choisirNiveau(l.lien, { url: true })) : ouvrir(l.lien); }
  else if (a === "partager") partager(l);
  else if (a === "prec" || a === "suiv") {
    const liste = S.data.locaux.filter(x => x.niveau === l.niveau && x.forme);
    const i = liste.findIndex(x => x.id === l.id), d = a === "suiv" ? 1 : -1;
    const n = liste[(i + d + liste.length) % liste.length]; n && ouvrir(n.id);
  }
});
async function partager(l) {
  const url = lienPublic(l.id);
  try {
    if (navigator.share) { await navigator.share({ title: l.nom + " · Le Tremplin", url }); return; }
    await navigator.clipboard.writeText(url); toast("Lien copié : " + url);
  } catch { toast(url, 5000); }
}

// poignée de la fiche (mobile) : glisser pour agrandir / fermer
(() => {
  const p = $("#poignee"); let y0 = null, h0 = 0;
  p.addEventListener("pointerdown", e => { y0 = e.clientY; h0 = el.fiche.getBoundingClientRect().height; el.fiche.classList.add("glisse"); p.setPointerCapture(e.pointerId); });
  p.addEventListener("pointermove", e => { if (y0 == null) return; el.fiche.style.setProperty("--hfiche", Math.max(80, h0 + y0 - e.clientY) + "px"); });
  p.addEventListener("pointerup", e => {
    if (y0 == null) return; el.fiche.classList.remove("glisse");
    const h = el.fiche.getBoundingClientRect().height, vh = innerHeight;
    if (h < vh * .18) { el.fiche.style.removeProperty("--hfiche"); fermerFiche(); }
    else el.fiche.style.setProperty("--hfiche", (h > vh * .6 ? vh * .78 : vh * .52) + "px");
    y0 = null;
    if (S.sel) setTimeout(() => centrerSur(S.sel.forme), 320);
  });
})();

// ---------------------------------------------------------------- calques
function etat(e) {
  S.etat = e; stock.set("etat", e);
  document.body.classList.toggle("etat-projet", e === "projet");
  document.querySelectorAll(".segment button").forEach(b => { const on = b.dataset.etat === e; b.classList.toggle("on", on); b.setAttribute("aria-checked", on); });
  dessiner();
}
document.querySelectorAll(".segment button").forEach(b => b.onclick = () => etat(b.dataset.etat));
function filtres() {
  const f = $("#filtres");
  f.innerHTML = Object.entries(S.data.categories).map(([k, c]) => `<button data-c="${k}" class="${S.cachees.has(k) ? "off" : ""}"><i class="pastille" style="background:${c.couleur}"></i>${esc(c.nom)}</button>`).join("");
  f.onclick = e => {
    const b = e.target.closest("[data-c]"); if (!b) return;
    const k = b.dataset.c; S.cachees.has(k) ? S.cachees.delete(k) : S.cachees.add(k);
    stock.set("cachees", [...S.cachees]); b.classList.toggle("off"); dessiner();
  };
}
$("#btn-filtres").onclick = e => { const f = $("#filtres"); f.hidden = !f.hidden; e.currentTarget.setAttribute("aria-expanded", !f.hidden); };

// ---------------------------------------------------------------- recherche
const inp = $("#recherche"), res = $("#resultats");
inp.addEventListener("input", () => {
  const q = norm(inp.value.trim());
  if (!q) { res.hidden = true; return; }
  const mots = q.split(/\s+/);
  const t = S.data.locaux.map(l => {
    const h = norm([l.nom, l.id, l.batiment, cat(l.categorie).nom, (niv(l.niveau) || {}).nom, l.resume].join(" "));
    let sc = 0; for (const m of mots) { if (!h.includes(m)) return null; sc += norm(l.nom).includes(m) ? 3 : 1; }
    return [sc + (l.qr ? 1 : 0), l];
  }).filter(Boolean).sort((a, b) => b[0] - a[0]).slice(0, 12);
  res.innerHTML = t.length ? t.map(([, l]) => `<li><button data-id="${esc(l.id)}"><i class="pastille" style="background:${cat(l.categorie).couleur}"></i>${esc(l.nom)}<small>${esc((niv(l.niveau) || {}).court || "")}</small></button></li>`).join("") : `<li class="vide" style="padding:10px">Aucun local trouvé.</li>`;
  res.hidden = false;
});
res.addEventListener("click", e => { const b = e.target.closest("[data-id]"); if (!b) return; res.hidden = true; inp.value = ""; inp.blur(); ouvrir(b.dataset.id); });
inp.addEventListener("keydown", e => { if (e.key === "Enter") { const b = res.querySelector("[data-id]"); b && b.click(); } });
document.addEventListener("click", e => { if (!e.target.closest(".recherche")) res.hidden = true; });
addEventListener("keydown", e => { if (e.key === "Escape") { res.hidden = true; if (!$("#accueil").hidden) $("#accueil").hidden = true; else if (S.sel) fermerFiche(); } });

// ---------------------------------------------------------------- accueil
function accueil() {
  const a = $("#accueil");
  const tech = S.data.locaux.filter(l => l.qr || l.categorie === "securite");
  const ordre = S.data.niveaux.filter(n => n.id !== "site");
  let d = 0; const dl = () => `style="animation-delay:${(d++ * 45)}ms"`;
  a.innerHTML = `<div class="acc">
    <p class="sous" style="margin:0">Plans interactifs · locaux techniques</p>
    <h1>${esc(C.NOM || "Le Tremplin")}</h1>
    <p class="sous">${esc(C.SOUS_TITRE || "")} · ${esc(S.data.site.adresse || "")}</p>
    <div class="urg">${(S.data.urgences || []).map(u => `<a href="tel:${esc(u.numero)}"><b>${esc(u.numero)}</b><span>${esc(u.nom)}</span></a>`).join("")}</div>
    <div class="bloc"><h2>Locaux techniques et coupures</h2>
      <div class="tuiles">${tech.map(l => `<button class="tuile" data-id="${esc(l.id)}" ${dl()}><i style="background:${cat(l.categorie).couleur}"></i><b>${esc(l.nom)}</b><small>${esc((niv(l.niveau) || {}).nom || "")}${l.fiabilite === "H" ? " · à confirmer" : ""}</small></button>`).join("")}</div></div>
    <div class="bloc"><h2>Choisir un niveau</h2>
      <div class="coupe">${ordre.map(n => `<button data-niv="${n.id}" ${dl()}><span class="e">${esc(n.court)}</span><span>${esc(n.nom)}</span><span class="alt">${esc(n.alt || "")}</span></button>${n.id === "rdc-haut" ? `<div class="sol" title="niveau de la rue"></div>` : ""}`).join("")}</div></div>
    <button class="entrer" data-niv="site">Explorer le plan de masse →</button>
    <p class="mention">${esc(C.MENTION || "")}</p></div>`;
  a.onclick = e => {
    const b = e.target.closest("[data-id],[data-niv]"); if (!b) return;
    a.hidden = true;
    b.dataset.id ? ouvrir(b.dataset.id) : choisirNiveau(b.dataset.niv, { url: true });
  };
  a.hidden = false;
}
$("#btn-accueil").onclick = accueil;

// ---------------------------------------------------------------- mot de passe (désactivé par défaut)
async function verrou() {
  const M = C.MOT_DE_PASSE || {};
  if (!M.actif || !M.sha256 || session.get("ouvert", false)) return;
  const v = $("#verrou"); v.hidden = false;
  await new Promise(ok => {
    $("#verrou-form").onsubmit = async e => {
      e.preventDefault();
      const b = new TextEncoder().encode($("#verrou-mdp").value);
      const h = [...new Uint8Array(await crypto.subtle.digest("SHA-256", b))].map(x => x.toString(16).padStart(2, "0")).join("");
      if (h === M.sha256.toLowerCase()) { session.set("ouvert", true); v.hidden = true; ok(); }
      else $("#verrou-err").hidden = false;
    };
  });
}

// ---------------------------------------------------------------- démarrage
async function demarrer() {
  $("#mention").textContent = C.MENTION || "";
  await verrou();
  try { await charger(); }
  catch (e) { document.body.insertAdjacentHTML("beforeend", `<p style="padding:20px">Impossible de charger les données (${esc(e.message)}).</p>`); return; }
  rail(); filtres(); etat(S.etat);
  el.zone.classList.add("sans-fiche");
  const pl = params.get("local"), pn = params.get("niveau");
  const l = pl && loc(pl);
  if (l) { choisirNiveau(l.niveau); ouvrir(l.id); }
  else if (pn && niv(pn)) choisirNiveau(pn);
  else { choisirNiveau("site"); if (!EDITION) accueil(); }
  if (pl && !l) toast("Local inconnu : " + pl);
  setTimeout(() => $("#astuce").classList.add("cache"), 3500);
  const hl = () => ($("#hors-ligne").hidden = navigator.onLine);
  addEventListener("online", hl); addEventListener("offline", hl); hl();
  if ("serviceWorker" in navigator && location.protocol !== "file:") navigator.serviceWorker.register("sw.js").catch(() => {});
}

// interface pour le mode édition (edition.js)
window.TREMPLIN = {
  S, EDITION, stock, toast, ouvrir, fermerFiche, choisirNiveau, dessiner, marquer, rendreFiche, ecranVersPlan,
  niv, loc, zp, cat, svg, forme2svg, surTap: null, surSelection: null,
  pret: null
};
window.TREMPLIN.pret = demarrer();
})();
