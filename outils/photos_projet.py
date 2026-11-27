#!/usr/bin/env python3
"""Associe les photos du dossier (existant et projet) aux locaux : data/photos.json + fichiers dans photos/.

Les images sources (HEIC, PNG) sont converties en WebP (1 600 px max) par la commande de préparation ;
ce script ne fait que l'association nom de fichier → locaux, catégorie et légende.
Catégories : existant, futur (rendus du projet), autres (plans et planches).
Usage : python3 outils/photos_projet.py
"""
import json, re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
D = json.loads((RACINE / "data" / "donnees.json").read_text(encoding="utf-8"))
IDS = {l["id"] for l in D["locaux"]}
LOC = {l["id"]: l for l in D["locaux"]}
DATE_EXISTANT = "2026-11-27"


def surface(i):
    try:
        return float(re.sub(r"[^\d,]", "", LOC[i].get("surface") or "0").replace(",", "."))
    except ValueError:
        return 0


circ_haut = max([i for i in IDS if i.startswith("circulation-rdc-haut")], key=surface)
chambres = {k: [l["id"] for l in D["locaux"] if l["niveau"] == k and re.match(r"Ch\.", l["nom"])] for k in ("r1", "r2", "r3", "r4")}
logements = {k: [l["id"] for l in D["locaux"] if l["niveau"] == k and l["nom"].startswith("Logement")] for k in ("r2", "r3")}
toutes_chambres = sum(chambres.values(), [])
tous_logements = sum(logements.values(), [])
salles_de_cours = ["escalade-rdc-bas", "studio-musique-rdc-bas", "muscu-rdc-bas", "vestiaire-rdc-bas", "atelier-art-rdc-bas",
                   "pop-up-vetement-rdc-haut", "boxe-rdc-bas", "danse-rdc-bas"]

# fichier → (locaux, catégorie, légende)
E = "existant"
A = [
    ("actuel--logement-individuel", toutes_chambres + tous_logements, E, "Chambre type du foyer, état actuel"),
    ("actuel--salle-deau-logement-indi", toutes_chambres + tous_logements, E, "Cellule sanitaire d'une chambre, état actuel"),
    ("actuel--salle-de-cours-futur-salle-de-boxe", ["boxe-rdc-bas"], E, "Salle de cours, future salle de boxe"),
    ("actuel--salle-de-cours-futur-salle-de-danse", ["danse-rdc-bas"], E, "Salle de cours, future salle de danse"),
    ("actuel--img-7117", salles_de_cours, E, "Salle de cours type du RDC (pièce exacte à confirmer)"),
    ("actuel--salle-de-cours-futur", salles_de_cours, E, "Salle de cours type du RDC (pièce exacte à confirmer)"),
    ("actuel--salle-futur-simulateur-de-golf", ["simulateur-de-golf-rdc-haut"], E, "Salle actuelle, futur simulateur de golf"),
    ("actuel--img-7126", ["simulateur-de-golf-rdc-haut", "archives-2-rdc-bas"], E, "Rayonnages d'archives (localisation à confirmer)"),
    ("actuel--rdc-haut-futur-acceuil", ["accueil-rdc-haut"], E, "Bureau du personnel, futur accueil"),
    ("actuel--centre-du-bati", ["circulation-rdc-bas"], E, "Centre du bâtiment (puits central), RDC bas"),
    ("actuel--centre-du-bati-2", ["circulation-rdc-bas"], E, "Centre du bâtiment (puits central), RDC bas"),
    ("actuel--centre-du-bati-rdc-haut", ["hall-accueil"], E, "Centre du bâtiment, RDC haut"),
    ("actuel--rdc-haut-escalier-au-niveau-de-l-du-centre-du-bati", ["hall-accueil"], E, "Escalier au centre du bâtiment, RDC haut"),
    ("actuel--rdc-haut-escalier-vers-le-restaurant", ["restaurant-rdc-haut", "cafeteria-rdc-haut"], E, "Escalier vers le restaurant, RDC haut"),
    ("actuel--escalier-vers-rdc-haut-entre-futur-cinema-et-futur-atelier-dart", ["circulation-rdc-bas", "amphitheatre", "atelier-art-rdc-bas"], E,
     "Escalier vers le RDC haut, entre le futur cinéma et le futur atelier d'art"),
    ("actuel--escalier-rdc-haut-vers-rdc-bas-entre-cinema-et-atelier-d-art", [circ_haut], E, "Escalier du RDC haut vers le RDC bas"),
    ("actuel--rdc-bas-couloir-vers-muscu", ["circulation-rdc-bas", "muscu-rdc-bas"], E, "Couloir du RDC bas vers la future musculation"),
    ("actuel--rdc-bas-couloir-vers-muscu-1", ["circulation-rdc-bas", "muscu-rdc-bas"], E, "Couloir du RDC bas vers la future musculation"),
    ("actuel--toillette-rdc-bas", ["wc-rdc-bas", "wc-rdc-bas-2"], E, "Sanitaires du RDC bas"),
    ("actuel--toillete", ["wc-rdc-haut", "wc-rdc-haut-2"], E, "Sanitaires du RDC haut (localisation à confirmer)"),
    ("actuel--sous-sol-1", ["parking", "parking-nord-allees-sous-sol"], E, "Parking enterré, état actuel"),
]

# rendus du projet : même nom en version « intérieur » et « réaliste »
F = {
    "atelier-art": ["atelier-art-rdc-bas"], "boxe": ["boxe-rdc-bas"], "cafeteria": ["cafeteria-rdc-haut"],
    "cinema": ["amphitheatre"], "couloir-etage-2": ["couloir-r2", "couloir-r3"], "cuisine": ["cuisine-rdc-haut"],
    "danse": ["danse-rdc-bas"], "escalade": ["escalade-rdc-bas"], "grand-logement-etage-2": tous_logements,
    "muscu": ["muscu-rdc-bas"], "parking": ["parking", "parking-nord-allees-sous-sol"],
    "petit-logement-etage-1": toutes_chambres, "pop-up-vetement": ["pop-up-vetement-rdc-haut"],
    "porche-d-entree": ["entree-rdc-haut", "bat-1"], "restaurant": ["restaurant-rdc-haut"],
    "restaurant-existant": ["salle-restaurant", "bat-restaurant"], "salle-polyvalente": ["salle-restaurant", "bat-restaurant"],
    "simulateur-de-golf": ["simulateur-de-golf-rdc-haut"], "street-workout": ["patio-bas"], "studio-musique": ["studio-musique-rdc-bas"],
    "vestiaire": ["vestiaire-rdc-bas"], "wc": ["wc-rdc-bas", "wc-rdc-bas-2", "wc-rdc-haut", "wc-rdc-haut-2"],
    "proue": ["bat-1", "hall-accueil"], "vue-aerienne-nord-ouest": ["bat-1", "foyer", "bat-restaurant"],
    "vue-aerienne-sud-est": ["bat-1", "foyer", "bat-restaurant"],
}
NOMS = {"etage-2": "étage 2", "etage-1": "étage 1", "cafeteria": "cafétéria", "cinema": "cinéma", "vetement": "vêtement",
        "entree": "entrée", "aerienne": "aérienne", "wc": "WC"}
GENERAL = [
    ("futur-general--interieur-rdcb", ["bat-1", "bat-1-sous-sol"], "futur", "Vue intérieure du RDC bas (projet)"),
    ("futur-general--interieur-rdch", ["bat-1", "hall-accueil"], "futur", "Vue intérieure du RDC haut (projet)"),
    ("futur-general--interieur-etage1", ["foyer"], "futur", "Vue intérieure de l'étage 1 (projet)"),
    ("futur-general--proue-entree", ["bat-1", "entree-rdc-haut"], "futur", "Proue d'entrée (projet)"),
    ("futur-general--vue-aerienne-nord-ouest", ["bat-1", "foyer", "bat-restaurant"], "futur", "Vue aérienne nord-ouest (projet)"),
    ("futur-general--vue-aerienne-sud-est", ["bat-1", "foyer", "bat-restaurant"], "futur", "Vue aérienne sud-est (projet)"),
    ("futur-general--vue-pieton-sud", ["bat-1", "foyer"], "futur", "Vue piéton depuis le sud (projet)"),
    ("futur-general--plan-rdcb", ["bat-1", "bat-1-sous-sol"], "autres", "Plan du RDC bas (projet)"),
    ("futur-general--plan-rdch", ["bat-1"], "autres", "Plan du RDC haut (projet)"),
    ("futur-general--plan-e1", ["foyer"], "autres", "Plan de l'étage 1 (projet)"),
    ("futur-general--plan-e4", ["foyer"], "autres", "Plan de l'étage 4 (projet)"),
    ("futur-general--plan-ss", ["parking"], "autres", "Plan du sous-sol (projet)"),
    ("futur-general--plan-toit", ["foyer"], "autres", "Plan de toiture (projet)"),
    ("futur-general--planche-interieurs", ["bat-1", "foyer"], "autres", "Planche des intérieurs (projet)"),
    ("futur-general--planche-realiste", ["bat-1", "foyer"], "autres", "Planche des rendus réalistes (projet)"),
]


def lisible(cle):
    t = cle
    for a, b in NOMS.items():
        t = t.replace(a, b)
    return t.replace("-", " ").strip().capitalize()


def main():
    dossier = RACINE / "photos"
    dispo = {p.stem for p in dossier.glob("*.webp")}
    out, manque = {}, []

    def ajouter(fichier, locaux, cat, legende, date=None):
        if fichier not in dispo:
            manque.append(fichier)
            return
        for i in locaux:
            if i not in IDS:
                manque.append(f"{fichier} → local inconnu {i}")
                continue
            out.setdefault(i, []).append({"fichier": f"photos/{fichier}.webp", "categorie": cat, "legende": legende,
                                          "date_prise": date})

    for f, locaux, cat, leg in A:
        ajouter(f, locaux, cat, leg, DATE_EXISTANT)
    for cle, locaux in F.items():
        ajouter(f"futur-interieur--{cle}", locaux, "futur", f"{lisible(cle)} : ambiance intérieure (projet)")
        ajouter(f"futur-realiste--{cle}", locaux, "futur", f"{lisible(cle)} : rendu réaliste (projet)")
    for f, locaux, cat, leg in GENERAL:
        ajouter(f, locaux, cat, leg)
    (RACINE / "data" / "photos.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    utilises = {p["fichier"] for v in out.values() for p in v}
    sans = sorted(dispo - {Path(u).stem for u in utilises})
    ch_sans = [i for i in toutes_chambres + tous_logements if not out.get(i)]
    print(f"{len(utilises)} photos associées à {len(out)} locaux ; chambres et logements sans photo : {len(ch_sans)}")
    print("non utilisées :", sans)
    print("problèmes :", manque)


if __name__ == "__main__":
    main()
