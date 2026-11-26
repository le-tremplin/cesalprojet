# Le Tremplin · plans interactifs

Plans et fiches des locaux du Tremplin (ancien CESAL, Bourges). Projet d'étude BUT GCCD 2026-2027.
**Document d'étude : ne remplace pas le plan d'intervention officiel.**

Adresse publique : https://ylieselamri-bot.github.io/cesalprojet/

## Liens directs
- Accueil : `…/cesalprojet/`
- Un niveau : `…/cesalprojet/?niveau=rdc-haut`
- Un local : `…/cesalprojet/?local=cuisine` (le niveau est retrouvé tout seul ; `?niveau=…&local=…` marche aussi)

Niveaux : `site` · `terrasse` · `r4` · `r3` · `r2` · `r1` · `rdc-haut` · `rdc-bas` · `sous-sol`
Locaux principaux : `tgbt` · `chaufferie` · `cuisine` · `parking` · `vanne-gaz` (liste complète dans `data/donnees.json`).

## Mettre en ligne (GitHub Pages)
1. Déposer tout le contenu de ce dossier à la racine du dépôt `cesalprojet` (branche `main`).
2. Sur GitHub : Settings → Pages → Source « Deploy from a branch » → `main` / `(root)` → Save.
3. Après chaque mise en ligne, augmenter `VERSION` dans `sw.js` pour que les téléphones rechargent le cache.

## Modifier les fiches et les zones
1. Ouvrir `…/cesalprojet/?edition=1`.
2. Toucher un local pour modifier sa fiche ; « + Local (zone) » puis toucher le plan pour poser les sommets.
3. « Exporter donnees.json », puis remplacer `data/donnees.json` dans le dépôt.

## QR code
Un seul QR (accueil) : `qr/qr-accueil-12cm.svg` (planches A0) et `qr/qr-accueil-5cm.svg` (étiquettes).
Texte vectorisé, anthracite #2f3328 sur ivoire #f2f0ea (contraste 11,3:1), correction Q, marge de 4 modules.

Changer d'adresse : modifier `URL_BASE` dans `config.js`, puis :

    pip install segno fonttools
    python3 outils/generer_qr.py
    python3 outils/generer_qr.py --local tgbt   # QR d'un local précis, si besoin

## Plans vectoriels (DAO)
Les plans affichés sont des SVG générés à partir de DXF (calques A-MURS, A-PORTES, A-FENETRES, A-ESCALIERS, A-SALLES-TEXTE…), unités en mètres :
- `plans/cad/rdc-bas.dxf`, `plans/cad/rdc-haut.dxf` : plans du groupe ;
- `plans/cad/r2.dxf`, `r3.dxf`, `r4.dxf` : reconstruits par `outils/foyer_etage.py` à partir du DOE Ex10a.

Après modification d'un DXF (dans n'importe quel logiciel de DAO, en gardant les calques) :

    pip install ezdxf shapely numpy
    python3 outils/dxf_vers_svg.py plans/cad/rdc-haut.dxf plans/rdc-haut.svg
    python3 outils/integrer_cad.py rdc-haut

Les fiches existantes sont conservées : le lien fiche ↔ salle se fait par le champ `salleCad` (nom de la salle dans le DXF).
Les niveaux R+1, sous-sol et terrasse sont encore affichés à partir des scans.

## Fichiers
- `index.html`, `app.css`, `app.js` : l'appli (aucune dépendance externe)
- `edition.js` : mode édition (`?edition=1`)
- `config.js` : adresse du site, mention, mot de passe (désactivé)
- `data/donnees.json` : niveaux, fiches, zones projet
- `plans/*.webp` : plans DOE (version légère `-l` chargée d'abord, HD au zoom)
- `sw.js`, `manifest.webmanifest` : fonctionnement hors ligne (PWA)
