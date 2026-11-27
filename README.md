# Le Tremplin · plans interactifs

Plans et fiches des locaux du Tremplin (ancien CESAL, Bourges). Projet d'étude BUT GCCD 2026-2027.
**Document d'étude : ne remplace pas le plan d'intervention officiel.**

Adresse publique : https://le-tremplin.github.io/cesalprojet/

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
Chaque niveau est un DXF (unités : mètres) converti en SVG. Calques : A-MURS, A-MURS-HACHURES, A-PORTES, A-FENETRES,
A-ESCALIERS, A-GAINES, A-ASCENSEURS, A-STATIONNEMENT, A-RAMPES, A-TOITURES, A-EQUIPEMENTS, A-SALLES-TEXTE…

| Niveau | Source DXF | Produit par |
|---|---|---|
| RDC haut, RDC bas | `plans/cad/origine/*-groupe.dxf` (plans du groupe, jamais modifiés) | `outils/projet_rdc.py` (salle des fêtes, ascenseur, double porte à badge, escalier demi-colimaçon, Stockage) |
| R+1, R+4 (structure conservée, chambres aménagées) | `plans/cad/r1.dxf`, `r4.dxf` | `outils/foyer_etage.py 1` (4) — d'après le DOE Ex09a/Ex10a |
| R+2, R+3 (logements regroupés) | `plans/cad/r2.dxf`, `r3.dxf` | `outils/foyer_etage.py 2` (3) |
| Sous-sol | `plans/cad/sous-sol.dxf` | `outils/sous_sol.py` — d'après le DOE Ex07c |
| Toiture | `plans/cad/terrasse.dxf` | `outils/toiture.py` — d'après le DOE Ex12bis |

Mettre à jour un niveau (après modification d'un DXF dans un logiciel de DAO, en gardant les calques) :

    pip install ezdxf shapely numpy
    python3 outils/dxf_vers_svg.py plans/cad/rdc-haut.dxf plans/rdc-haut.svg
    python3 outils/integrer_cad.py rdc-haut

Chaque pièce fermée, gaine, ascenseur, place de parking ou zone de toiture devient une zone cliquable.
Le lien fiche ↔ salle se fait par le champ `salleCad` : une géométrie qui change ne fait perdre aucune donnée.
Une pièce sans nom dans le DXF apparaît comme « Local à identifier n ».

## Fiches préremplies
`outils/fiches_auto.py` remplit les fiches (Essentiel, Actuel, Futur, Budget) de tous les locaux dans `data/fiches/<niveau>.json`,
à partir des plans et du dossier d'étude. Chaque information porte sa provenance : **Plan**, **Projet**, **Estimation**,
**À vérifier sur site**. Les budgets sont calculés par le code (quantités × prix unitaires de ratios d'étude) : ce sont des
estimations à faire valider par un économiste. Relancer le script après une modification des plans
(`python3 outils/fiches_auto.py`) : les corrections faites par les comptes autorisés, enregistrées dans la base, ne sont jamais écrasées.

## Photos du dossier
Les photos de l'existant et les rendus du projet sont dans `photos/` (WebP, 1 600 px max) et associés aux locaux par
`outils/photos_projet.py` (fichier `data/photos.json`). Elles apparaissent dans les onglets Actuel, Futur et Galerie,
en lecture seule ; les photos ajoutées depuis le site s'y ajoutent.

## Fiches, budgets et photos : base Supabase
Sans configuration, le site est en consultation seule ; `?edition=1` permet au propriétaire de corriger sur son appareil.
Pour partager les données entre appareils et utilisateurs :
1. Créer un projet sur supabase.com (région Europe).
2. SQL Editor → New query → coller `supabase/schema.sql` → Run.
3. Authentication → Users → Add user (cocher « Auto confirm ») pour chaque membre, puis désigner le propriétaire
   (requête en fin de `schema.sql`). Le propriétaire attribue ensuite, depuis le site (bouton « Utilisateurs »),
   le rôle `admin` avec des droits au choix (fiches, budgets, photos) ; les autres comptes restent en consultation.
4. Authentication → Sign In / Providers : désactiver « Allow new users to sign up ».
5. Project Settings → API : copier « Project URL » et la clé « anon public » dans `config.js` (bloc `SUPABASE`).

Sécurité : lecture publique (le site est public), écriture réservée aux comptes autorisés (règles RLS),
budget et photos réservés aux administrateurs, chaque version d'une fiche est archivée (`fiches_historique`).

## Fichiers
- `index.html`, `app.css`, `app.js` : l'appli (aucune dépendance externe)
- `fiches.js` : fiches (Essentiel, Actuel, Futur, Budget, Galerie), connexion, sauvegarde automatique
- `edition.js` : mode édition (`?edition=1`) des contours
- `supabase/schema.sql` : base de données, droits, historique
- `config.js` : adresse du site, mention, mot de passe (désactivé)
- `data/donnees.json` : niveaux, fiches, zones projet
- `plans/*.webp` : plans DOE (version légère `-l` chargée d'abord, HD au zoom)
- `sw.js`, `manifest.webmanifest` : fonctionnement hors ligne (PWA)
