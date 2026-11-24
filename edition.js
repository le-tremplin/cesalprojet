/* Mode édition : s'ouvre avec ?edition=1.
 * Les modifications sont gardées en brouillon sur cet appareil.
 * « Exporter donnees.json » télécharge le fichier à déposer dans data/ du dépôt GitHub. */
(async () => {
"use strict";
const T = window.TREMPLIN;
if (!T || !T.EDITION) return;
await T.pret;
const S = T.S;
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const css = document.createElement("style");
css.textContent = `
.ed{position:fixed;right:12px;top:68px;width:min(380px,calc(100vw - 24px));max-height:calc(100vh - 90px);overflow:auto;z-index:40;
 background:#fffdf7;border:2px solid #b5654a;border-radius:16px;box-shadow:0 12px 40px rgba(0,0,0,.25);font-size:13px}
.ed.reduit .ed-corps{display:none}
@media (min-width:1000px){.ed{left:212px;right:auto;top:auto;bottom:40px;max-height:70vh}}
.ed-tete{position:sticky;top:0;background:#b5654a;color:#fff;padding:10px 12px;display:flex;gap:8px;align-items:center;font-weight:700}
.ed-tete button{margin-left:auto;background:rgba(255,255,255,.2);border:0;color:#fff;border-radius:8px;padding:4px 8px}
.ed-corps{padding:10px 12px;display:grid;gap:8px}
.ed .rang{display:flex;gap:6px;flex-wrap:wrap}
.ed button.b{border:1px solid #d9d5c9;background:#f2f0ea;border-radius:9px;padding:7px 9px;font-size:12.5px;font-weight:600}
.ed button.b.p{background:#2f3328;color:#f2f0ea;border-color:#2f3328}
.ed button.b.d{color:#a8432f}
.ed label{display:grid;gap:3px;font-weight:600;color:#6b6a60;font-size:11.5px}
.ed input,.ed select,.ed textarea{font:inherit;font-size:13px;padding:6px 8px;border:1px solid #d9d5c9;border-radius:8px;background:#fff;color:#2f3328;width:100%}
.ed textarea{min-height:54px;resize:vertical}
.ed .aide{color:#6b6a60;font-size:11.5px;line-height:1.35}
.ed .mode{background:#2f3328;color:#fff;padding:8px 10px;border-radius:9px;font-weight:600}
.ed h3{margin:6px 0 0;font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:#b5654a}
.trace{fill:#b5654a;fill-opacity:.2;stroke:#b5654a;stroke-width:3;vector-effect:non-scaling-stroke;stroke-dasharray:8 5;pointer-events:none}
.trace-pt{fill:#b5654a;pointer-events:none}`;
document.head.appendChild(css);

const box = document.createElement("div");
box.className = "ed";
document.body.appendChild(box);

let mode = null;      // null | 'zone' | 'point'
let trace = [];       // points en cours
let cible = null;     // {kind, id}

function sauver() {
  S.data.majour = new Date().toISOString().slice(0, 10);
  if (!T.stock.set("brouillon", S.data)) T.toast("Brouillon trop gros pour cet appareil : exportez maintenant.");
}
function itemCible() {
  if (!cible) return null;
  return cible.kind === "projet" ? T.zp(cible.id) : T.loc(cible.id);
}
const lignes = (arr, f) => (arr || []).map(f).join("\n");
const parse = (txt, f) => txt.split("\n").map(s => s.trim()).filter(Boolean).map(s => f(s.split("|").map(x => x.trim())));

function rendre() {
  const it = itemCible();
  const cats = Object.entries(S.data.categories);
  const nivs = S.data.niveaux;
  let f = "";
  if (it && cible.kind === "local") {
    f = `<h3>Fiche : ${esc(it.id)}</h3>
    <label>Nom<input data-k="nom" value="${esc(it.nom)}"></label>
    <div class="rang">
      <label style="flex:1">Niveau<select data-k="niveau">${nivs.map(n => `<option value="${n.id}" ${n.id === it.niveau ? "selected" : ""}>${esc(n.court)}</option>`).join("")}</select></label>
      <label style="flex:1">Fiabilité<select data-k="fiabilite">${["C", "H", "P"].map(x => `<option ${x === it.fiabilite ? "selected" : ""}>${x}</option>`).join("")}</select></label>
    </div>
    <div class="rang">
      <label style="flex:1">Catégorie<select data-k="categorie">${cats.map(([k, c]) => `<option value="${k}" ${k === it.categorie ? "selected" : ""}>${esc(c.nom)}</option>`).join("")}</select></label>
      <label style="flex:1">Bâtiment<input data-k="batiment" value="${esc(it.batiment)}"></label>
    </div>
    <label>Résumé<textarea data-k="resume">${esc(it.resume)}</textarea></label>
    <div class="rang"><label style="flex:1">Surface<input data-k="surface" value="${esc(it.surface)}"></label>
      <label style="flex:1">Fonction<input data-k="fonction" value="${esc(it.fonction)}"></label></div>
    <label>Accès / clé<input data-k="acces" value="${esc(it.acces)}"></label>
    <label>Consignes de coupure (une étape par ligne · texte | C/H/P)<textarea data-l="coupure">${esc(lignes(it.coupure, k => k.texte + " | " + k.fiabilite))}</textarea></label>
    <label>Équipements (nom | détail | C/H/P)<textarea data-l="equipements">${esc(lignes(it.equipements, e => [e.nom, e.detail, e.fiabilite].join(" | ")))}</textarea></label>
    <label>Risques (texte | fort/moyen/faible)<textarea data-l="risques">${esc(lignes(it.risques, r => r.texte + " | " + r.niveau))}</textarea></label>
    <label>Dans le projet<textarea data-k="projet">${esc(it.projet)}</textarea></label>
    <label>Photo (chemin d'image dans le dépôt, ex. photos/tgbt.webp)<input data-k="photo" value="${esc(it.photo || "")}"></label>
    <label>Lien « Aller » (id d'un niveau ou d'un local)<input data-k="lien" value="${esc(it.lien || "")}"></label>
    <label>Source<input data-k="source" value="${esc(it.source)}"></label>
    <label>Remarques<textarea data-k="remarques">${esc(it.remarques)}</textarea></label>
    <label style="display:flex;gap:8px;align-items:center"><input type="checkbox" data-k="qr" ${it.qr ? "checked" : ""} style="width:auto">Local mis en avant à l'accueil</label>
    <div class="rang"><button class="b" data-a="redessiner">Redessiner la zone</button><button class="b" data-a="deplacer">Placer en point</button><button class="b d" data-a="suppr">Supprimer</button></div>
    <p class="aide">Lien direct : ${esc((window.CONFIG.URL_BASE || "") + "?local=" + it.id)}</p>`;
  } else if (it && cible.kind === "projet") {
    f = `<h3>Zone projet : ${esc(it.id)}</h3>
    <label>Nom<input data-k="nom" value="${esc(it.nom)}"></label>
    <label>Catégorie<select data-k="categorie">${cats.map(([k, c]) => `<option value="${k}" ${k === it.categorie ? "selected" : ""}>${esc(c.nom)}</option>`).join("")}</select></label>
    <label>Texte<textarea data-k="texte">${esc(it.texte)}</textarea></label>
    <label>Source<input data-k="source" value="${esc(it.source)}"></label>
    <div class="rang"><button class="b" data-a="redessiner">Redessiner la zone</button><button class="b d" data-a="suppr">Supprimer</button></div>`;
  } else {
    f = `<p class="aide">Touchez un local sur le plan pour modifier sa fiche, ou créez-en un. En vue « Projet », touchez une zone colorée pour la modifier.</p>`;
  }
  box.innerHTML = `<div class="ed-tete">✎ Mode édition<button data-a="reduire">${box.classList.contains("reduit") ? "Ouvrir" : "Réduire"}</button></div>
  <div class="ed-corps">
    ${mode ? `<div class="mode">${mode === "zone" ? `Touchez le plan pour poser les sommets (${trace.length}). <br>` : "Touchez le plan pour placer le point."}</div>
      <div class="rang">${mode === "zone" ? `<button class="b p" data-a="terminer">Terminer la zone</button><button class="b" data-a="annuler-pt">Retirer le dernier sommet</button>` : ""}<button class="b" data-a="stop">Annuler</button></div>` : ""}
    <div class="rang"><button class="b p" data-a="nouveau-zone">+ Local (zone)</button><button class="b p" data-a="nouveau-point">+ Local (point)</button><button class="b" data-a="nouveau-projet">+ Zone projet</button></div>
    ${f}
    <h3>Fichier</h3>
    <div class="rang"><button class="b p" data-a="export">Exporter donnees.json</button><button class="b" data-a="import">Importer…</button><button class="b d" data-a="raz">Abandonner le brouillon</button></div>
    <p class="aide">Brouillon gardé sur cet appareil. Pour publier : exporter, puis remplacer <b>data/donnees.json</b> dans le dépôt GitHub (Add file → Upload files).</p>
  </div>`;
}

function maj(k, v) {
  const it = itemCible(); if (!it) return;
  it[k] = v;
  sauver();
  if (k === "niveau") { T.choisirNiveau(v); T.ouvrir(it.id, { kind: cible.kind }); }
  else { T.dessiner(); T.S.sel && (Object.assign(T.S.sel, it), T.rendreFiche()); }
}
box.addEventListener("input", e => {
  const t = e.target, it = itemCible(); if (!it) return;
  if (t.dataset.k) maj(t.dataset.k, t.type === "checkbox" ? t.checked : (t.value === "" && (t.dataset.k === "lien" || t.dataset.k === "photo") ? null : t.value));
  if (t.dataset.l) {
    const k = t.dataset.l;
    const v = k === "coupure" ? parse(t.value, ([texte, f]) => ({ texte, fiabilite: (f || "H").toUpperCase() }))
      : k === "equipements" ? parse(t.value, ([nom, detail, f]) => ({ nom, detail: detail || "", fiabilite: (f || "C").toUpperCase() }))
      : parse(t.value, ([texte, n]) => ({ texte, niveau: (n || "moyen").toLowerCase() }));
    maj(k, v);
  }
});

function dessinerTrace() {
  T.S && document.querySelectorAll(".trace,.trace-pt").forEach(n => n.remove());
  if (mode !== "zone" || !trace.length) return;
  const c = $("#calque");
  T.svg("polygon", { class: "trace", points: trace.map(p => p.join(",")).join(" ") }, c);
  trace.forEach(([x, y]) => {
    const p = T.svg("circle", { class: "trace-pt", cx: x, cy: y, r: 6 }, c);
    p.style.transformOrigin = `${x}px ${y}px`; p.style.transform = "scale(var(--inv))";
  });
}
T.surTap = p => {
  if (!mode) return false;
  const x = Math.round(p.x), y = Math.round(p.y);
  if (mode === "zone") { trace.push([x, y]); dessinerTrace(); rendre(); return true; }
  if (mode === "point") {
    const it = itemCible(); it.forme = { type: "point", x, y };
    mode = null; sauver(); T.dessiner(); T.ouvrir(it.id, { kind: cible.kind, centrer: false }); rendre(); return true;
  }
  return false;
};
T.surSelection = sel => { if (mode) return; cible = sel ? { kind: sel.kind, id: sel.id } : null; rendre(); };

function nouvelId(base) {
  let id = base, i = 2;
  const pris = new Set([...S.data.locaux.map(l => l.id), ...(S.data.zonesProjet || []).map(z => z.id)]);
  while (pris.has(id)) id = base + "-" + i++;
  return id;
}
function slug(s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }

box.addEventListener("click", async e => {
  const b = e.target.closest("[data-a]"); if (!b) return;
  const a = b.dataset.a;
  if (a === "reduire") { box.classList.toggle("reduit"); rendre(); return; }
  if (a === "nouveau-zone" || a === "nouveau-point" || a === "nouveau-projet") {
    const nom = prompt(a === "nouveau-projet" ? "Nom de la zone projet ?" : "Nom du local ?"); if (!nom) return;
    const nid = S.niveau.id;
    if (a === "nouveau-projet") {
      const z = { id: nouvelId("p-" + slug(nom)), niveau: nid, nom, categorie: "culture", forme: null, texte: "", source: "" };
      S.data.zonesProjet.push(z); cible = { kind: "projet", id: z.id };
      if (S.etat !== "projet") document.querySelector('.segment [data-etat="projet"]').click();
    } else {
      const l = { id: nouvelId(slug(nom)), nom, niveau: nid, batiment: "", categorie: "technique", fiabilite: "H", qr: false, forme: null,
        resume: "", surface: "", acces: "", equipements: [], coupure: [], risques: [], projet: "", source: "", remarques: "", photo: null, lien: null };
      S.data.locaux.push(l); cible = { kind: "local", id: l.id };
    }
    mode = a === "nouveau-point" ? "point" : "zone"; trace = []; sauver(); rendre(); T.toast("Touchez le plan.");
    return;
  }
  if (a === "redessiner") { mode = "zone"; trace = []; rendre(); T.toast("Touchez le plan pour poser les sommets."); return; }
  if (a === "deplacer") { mode = "point"; rendre(); return; }
  if (a === "annuler-pt") { trace.pop(); dessinerTrace(); rendre(); return; }
  if (a === "stop") {
    const it = itemCible(); mode = null; trace = []; dessinerTrace();
    if (it && !it.forme) T.toast("Ce local n'a pas encore de forme : il n'apparaît pas sur le plan.");
    rendre(); return;
  }
  if (a === "terminer") {
    if (trace.length < 3) { T.toast("Il faut au moins 3 sommets."); return; }
    const it = itemCible(); it.forme = { type: "poly", points: trace };
    mode = null; trace = []; dessinerTrace(); sauver(); T.dessiner(); T.ouvrir(it.id, { kind: cible.kind, centrer: false }); rendre(); return;
  }
  if (a === "suppr") {
    const it = itemCible(); if (!it || !confirm(`Supprimer « ${it.nom} » ?`)) return;
    const arr = cible.kind === "projet" ? S.data.zonesProjet : S.data.locaux;
    arr.splice(arr.indexOf(it), 1); cible = null; sauver(); T.fermerFiche(); T.dessiner(); rendre(); return;
  }
  if (a === "export") {
    const blob = new Blob([JSON.stringify(S.data, null, 1)], { type: "application/json" });
    const u = URL.createObjectURL(blob), l = document.createElement("a");
    l.href = u; l.download = "donnees.json"; document.body.appendChild(l); l.click(); l.remove();
    setTimeout(() => URL.revokeObjectURL(u), 2000); return;
  }
  if (a === "import") {
    const i = document.createElement("input"); i.type = "file"; i.accept = "application/json,.json";
    i.onchange = async () => {
      try { const d = JSON.parse(await i.files[0].text()); if (!d.niveaux || !d.locaux) throw 0; T.stock.set("brouillon", d); location.reload(); }
      catch { T.toast("Fichier non reconnu."); }
    };
    i.click(); return;
  }
  if (a === "raz") { if (confirm("Abandonner toutes les modifications non exportées ?")) { T.stock.del("brouillon"); location.reload(); } }
});
rendre();
T.toast("Mode édition actif");
})();
