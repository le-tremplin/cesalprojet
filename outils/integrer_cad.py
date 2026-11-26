#!/usr/bin/env python3
"""Branche les plans vectoriels (plans/<niveau>.svg + .salles.json) sur data/donnees.json.

Usage (après outils/dxf_vers_svg.py) :
    python3 outils/integrer_cad.py rdc-bas rdc-haut

Règles, pour ne rien perdre :
- un local garde son id et toutes ses données ; seul son contour (forme) change ;
- le lien local ↔ salle du plan est le champ "salleCad" (nom de la salle, suffixé #2, #3… si le nom revient) ;
- une salle du plan sans local devient un nouveau local (fiche à compléter) ;
- un local sans salle (ex. point placé à la main) est recalé par une transformation
  calculée sur les salles appariées ;
- les zones projet du niveau sont reprises des hachures A-ZONES-PROJET du DXF.
Relancer le script après une mise à jour du DXF met les contours à jour.
"""
import json, re, sys, unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "data" / "donnees.json"

# Premier appariement (anciens locaux dessinés sur les scans → salles DXF)
# Contours tracés à la main sur le plan vectoriel (salles non étiquetées dans le DXF)
CONTOURS = {
    "rdc-haut": {"cuisine": [[1490, 80], [2010, 80], [2155, 228], [2155, 385], [1490, 385]]},
}
APPARIEMENT = {
    "rdc-bas": {"local-ecs": "Local ECS n°2", "machinerie": "Machinerie", "local-techn-3": "Local technique 3",
                "local-techn-4": "Local technique 4", "local-techn-5": "Local technique 5",
                "amphitheatre": "Cinéma", "patio-bas": "Street workout"},
    **{f"r{k}": {f"escalier-r{k}": "Escalier", f"escalier-ouest-r{k}": "Escalier #2",
                 f"escalier-est-r{k}": "Escalier #3", f"ascenseur-r{k}": "Ascenseur"} for k in (2, 3, 4)},
    "rdc-haut": {"tgbt": "Local tableau électr.", "salle-restaurant": "Restaurant existant",
                 "hall-accueil": "Hall d'accueil", "patio": "Patio", "terrasse-accessible": "Terrasse",
                 "local-vmc-1": "Local tech. VMC 1", "local-vmc-2": "Local tech. VMC 2"},
}
ANCIENNES_ZONES = {  # texte des anciennes zones projet à conserver
    "Studio musique": "p-musique", "Escalade": "p-polyvalente", "Boxe": "p-boxe", "Danse": "p-danse",
    "Street workout": "p-workout", "Muscu": "p-muscu", "Vestiaire": "p-vestiaires", "Atelier Art": "p-art",
    "Local de rangement": "p-stock-bas", "Restaurant": "p-resto", "Terrasse": "p-terrasse",
    "Pop up vêtement": "p-popup",
}
CATEGORIES = [
    ("sanitaires", r"\bwc\b|sanit|vestiaire|toilette"),
    ("technique", r"local|tech|ecs|machinerie|vmc|tableau|archive|annexe|r[ée]serve|stockage|rangement|poubelle|reprographie|chaufferie|bureau"),
    ("circulation", r"escalier|circulation|hall|entr[ée]e|accueil|tr[ée]mie|patio|plant[ée]e|ascenseur|couloir|palier"),
    ("sport", r"boxe|danse|muscu|escalade|street|golf|sport"),
    ("culture", r"studio|atelier|cin[ée]ma|pop.?up|expo|art"),
    ("restauration", r"cuisine|restaurant|caf[ée]t|terrasse|self"),
    ("hebergement", r"chambre|logement|studio meubl"),
]


def slug(s):
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def categorie(nom):
    n = nom.lower()
    if re.match(r"ch\.? ", n):
        return "hebergement"
    for c, rx in CATEGORIES:
        if re.search(rx, n):
            return c
    return "circulation"


def centre(forme):
    if forme["type"] == "point":
        return forme["x"], forme["y"]
    p = forme["points"]
    return sum(a for a, _ in p) / len(p), sum(b for _, b in p) / len(p)


def affine(paires):
    """Moindres carrés : [x', y'] = A·[x, y, 1]."""
    import numpy as np
    src = np.array([[x, y, 1] for (x, y), _ in paires])
    dst = np.array([d for _, d in paires])
    A, *_ = np.linalg.lstsq(src, dst, rcond=None)
    res = np.abs(src @ A - dst).max()
    return (lambda x, y: tuple(float(v) for v in np.array([x, y, 1]) @ A)), res


def integrer(nid, d):
    meta = json.loads((RACINE / "plans" / f"{nid}.salles.json").read_text(encoding="utf-8"))
    niv = next(n for n in d["niveaux"] if n["id"] == nid)
    ancien_plan = niv["plan"]
    niv["plan"] = {"vecto": f"plans/{nid}.svg", "w": meta["w"], "h": meta["h"], "source": f"plans/cad/{nid}.dxf"}
    niv["note"] = f"Plan vectoriel redessiné d'après le DOE ({meta['source']})."
    if nid in ("r3", "r4"):
        niv["note"] += " Identique au R+2 (relevé sur le plan du R+2)."

    # noms uniques des salles
    vus, salles = {}, {}
    for s in meta["salles"]:
        vus[s["nom"]] = vus.get(s["nom"], 0) + 1
        cle = s["nom"] + ("" if vus[s["nom"]] == 1 else f" #{vus[s['nom']]}")
        salles[cle] = s

    def forme_de(s):
        if s["source"] == "point":
            return {"type": "point", "x": s["x"], "y": s["y"]}
        return {"type": "poly", "points": s["contour"]}

    locaux = [l for l in d["locaux"] if l["niveau"] == nid]
    for l in locaux:
        if not l.get("salleCad") and l["id"] in APPARIEMENT.get(nid, {}):
            l["salleCad"] = APPARIEMENT[nid][l["id"]]

    # transformation ancien repère → nouveau, si l'ancien plan était un scan
    paires = []
    if "vecto" not in ancien_plan:
        for l in locaux:
            s = salles.get(l.get("salleCad") or "")
            if s and l.get("forme") and s["source"] != "point":
                paires.append((centre(l["forme"]), (s["x"], s["y"])))
    T = None
    if len(paires) >= 3:
        T, res = affine(paires)
        print(f"  {nid} : recalage sur {len(paires)} salles, écart max {res:.0f} unités ({res / meta['echelle']:.1f} m)")

    pris = set()
    for l in locaux:
        s = salles.get(l.get("salleCad") or "")
        if s:
            l["forme"] = forme_de(s)
            if s.get("surface") and not l.get("surface"):
                l["surface"] = s["surface"]
            pris.add(l["salleCad"])
        elif l.get("forme") and T:
            f = l["forme"]
            if f["type"] == "point":
                x, y = T(f["x"], f["y"])
                l["forme"] = {"type": "point", "x": round(x, 1), "y": round(y, 1)}
            else:
                l["forme"]["points"] = [[round(v, 1) for v in T(x, y)] for x, y in f["points"]]
            l["remarques"] = (l.get("remarques") or "") + (" " if l.get("remarques") else "") + "Contour recalé automatiquement : à vérifier en mode édition."

    for lid, pts in CONTOURS.get(nid, {}).items():
        for l in locaux:
            if l["id"] == lid:
                l["forme"] = {"type": "poly", "points": pts}
                l["remarques"] = re.sub(r" ?Contour recalé automatiquement : à vérifier en mode édition\.", "", l.get("remarques") or "")

    ids = {l["id"] for l in d["locaux"]}
    nouveaux = 0
    for cle, s in salles.items():
        if cle in pris:
            continue
        base = f"{slug(s['nom'])}-{nid}"
        i, lid = 2, base
        while lid in ids:
            lid, i = f"{base}-{i}", i + 1
        ids.add(lid)
        d["locaux"].append({
            "id": lid, "nom": s["nom"], "niveau": nid, "batiment": "Bât. restaurant" if s["y"] < 1300 and nid == "rdc-haut" and s["x"] > 1300 and s["x"] < 2300 else "Bât. 1",
            "categorie": categorie(s["nom"]), "fiabilite": "C", "qr": False, "forme": forme_de(s),
            "resume": "", "surface": s.get("surface", ""), "acces": "", "equipements": [], "coupure": [],
            "risques": [], "projet": "", "source": f"Plan vectoriel {meta['source']}", "remarques": "",
            "photo": None, "lien": None, "salleCad": cle})
        nouveaux += 1

    # zones projet : celles du DXF remplacent les anciennes du niveau
    if not meta["zonesProjet"]:
        print(f"  {nid} : {len(pris)} locaux existants recalés sur leur salle, {nouveaux} nouvelles salles cliquables")
        return
    anciennes = {z["id"]: z for z in d.get("zonesProjet", []) if z["niveau"] == nid}
    d["zonesProjet"] = [z for z in d.get("zonesProjet", []) if z["niveau"] != nid]
    zid = set(z["id"] for z in d["zonesProjet"])
    for z in meta["zonesProjet"]:
        nom = z["nom"] or "Zone projet"
        old = anciennes.get(ANCIENNES_ZONES.get(nom, ""), {})
        base, i = "p-" + slug(nom) + "-" + nid, 2
        idz = base
        while idz in zid:
            idz, i = f"{base}-{i}", i + 1
        zid.add(idz)
        d["zonesProjet"].append({"id": idz, "niveau": nid, "nom": nom, "categorie": categorie(nom),
                                 "forme": {"type": "poly", "points": z["contour"]},
                                 "texte": old.get("texte", ""), "source": f"Plan vectoriel {meta['source']} (calque A-ZONES-PROJET)"})
    print(f"  {nid} : {len(pris)} locaux existants recalés sur leur salle, {nouveaux} nouvelles salles cliquables, "
          f"{len(meta['zonesProjet'])} zones projet")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    d = json.loads(DONNEES.read_text(encoding="utf-8"))
    for nid in sys.argv[1:]:
        integrer(nid, d)
    d["version"] = d.get("version", 1) + 1
    DONNEES.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
