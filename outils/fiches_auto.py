#!/usr/bin/env python3
"""Préremplissage des fiches (Essentiel, Actuel, Futur, Budget) pour TOUS les locaux.

Sources exploitées : data/donnees.json (locaux, surfaces des plans vectoriels, données du dossier
d'étude), plans DOE, planches A0 du groupe (diagnostic D1-D5, réseaux R1-R2, programme).
Sortie : data/fiches/<niveau>.json — contenu de départ, protégé : seul un compte autorisé peut le
corriger (les corrections sont enregistrées dans la base, la version de départ reste dans le dépôt).

Chaque texte est marqué par sa provenance :
  [Plan]  lu sur les plans    [Projet]  décision du projet    [Estimation]  hypothèse de l'étude
  [À vérifier sur site]  information impossible à établir depuis les documents
Les budgets sont calculés ici (quantités × prix unitaires) à partir de ratios d'étude : ce ne sont
ni des devis ni des prix fournisseurs.

Usage : python3 outils/fiches_auto.py
"""
import json, math, re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
D = json.loads((RACINE / "data" / "donnees.json").read_text(encoding="utf-8"))
NIV = {n["id"]: n for n in D["niveaux"]}
DATE = "2026-11-26"
HAUTEUR = 2.50          # hauteur sous plafond supposée (aucune coupe fournie, planche D2.3)
AVERT = ("Budget prévisionnel établi à partir de ratios d'étude (prix HT 2026 estimés, hors honoraires, aléas et "
         "révision). Ni devis ni prix fournisseurs : validation par un économiste de la construction obligatoire avant engagement.")

ETAGE_TXT = {"sous-sol": "niveau -1 (parking)", "rdc-bas": "RDC bas (-2,16)", "rdc-haut": "RDC haut (±0,00)",
             "r1": "R+1", "r2": "R+2", "r3": "R+3", "r4": "R+4", "terrasse": "toiture-terrasse", "site": "abords"}
FOYER = {"r1", "r2", "r3", "r4", "terrasse"}


def surf(l):
    try:
        return float(re.sub(r"[^\d,\.]", "", (l.get("surface") or "").split("m")[0]).replace(",", ".") or 0)
    except ValueError:
        return 0.0


def murs_m2(S):
    """surface de murs à peindre : périmètre d'un rectangle 1:1,5 × hauteur, moins 15 % d'ouvertures"""
    if S <= 0:
        return 0
    p = 2 * (math.sqrt(S / 1.5) + 1.5 * math.sqrt(S / 1.5))
    return round(p * HAUTEUR * 0.85)


def L(poste, designation, q, unite, pu, tva=20):
    return {"poste": poste, "designation": designation, "quantite": round(q, 2) if isinstance(q, float) else q,
            "unite": unite, "pu_ht": pu, "tva": tva}


def finitions(S, tva, sol=("PVC / linoléum U3P3", 48), luminaire=None):
    out = []
    if S > 0:
        out.append(L("Revêtements de sols", f"Dépose et sol neuf {sol[0]}", S, "m²", sol[1], tva))
        out.append(L("Peinture", "Préparation et peinture murs et plafond (2 couches)", float(murs_m2(S) + S), "m²", 24, tva))
        if luminaire:
            out.append(L("Électricité", f"Luminaires LED {luminaire}", max(1, round(S / 9)), "u", 230, tva))
    return out


# --------------------------------------------------------------------------- classification par fonction
REGLES = [
    ("gaine", r"^gaine|trappe gaine|sortie ventilation|débouché"), ("vo", r"vide-ordures"),
    ("vbvh", r"^v[bh] "), ("ascenseur", r"ascenseur"), ("logement", r"^logement"),
    ("chambre", r"^ch\.|^chambre"), ("sde", r"salle d.eau"), ("place", r"^place "),
    ("rampe", r"rampe"), ("escalier", r"escalier|édicule"), ("toiture", r"^toiture"),
    ("chaufferie", r"chaufferie"), ("tgbt", r"tableau électr|tgbt"), ("ecs", r"ecs"),
    ("vmc", r"vmc|soufflage"), ("machinerie", r"machinerie"), ("tech", r"local tech|^local$|local à identifier|transfo"),
    ("danse", r"danse"), ("boxe", r"boxe"), ("muscu", r"muscu"), ("escalade", r"escalade"), ("street", r"street"),
    ("golf", r"golf"), ("cinema", r"cinéma|amphi"), ("musique", r"musique"), ("art", r"atelier|art\b"),
    ("popup", r"pop.?up"), ("fetes", r"salle polyvalente|salle des fêtes"), ("bar", r"^bar"),
    ("cuisine", r"cuisine"), ("restaurant", r"restaurant|cafét"), ("terrasse", r"^terrasse"),
    ("wc", r"\bwc\b|sanitaire"), ("vestiaire", r"vestiaire"), ("stockage", r"stockage|archive|réserve|rangement|ménage|reprographie|office"),
    ("poubelles", r"poubelle"), ("hall", r"hall|accueil|entrée"), ("parking", r"parking"),
    ("exterieur", r"patio|plantée|trémie"), ("circulation", r"circulation|couloir|dégagement|sas|palier|accès|regards"),
]


def fonction(l):
    n = l["nom"].lower()
    if l["categorie"] in ("securite", "batiment"):
        return l["categorie"]
    for k, rx in REGLES:
        if re.search(rx, n):
            return k
    return "autre"


# --------------------------------------------------------------------------- modèles de fiches
def fiche(l):
    f = fonction(l)
    S = surf(l)
    niv = l["niveau"]
    et = ETAGE_TXT.get(niv, niv)
    foyer = niv in FOYER or l.get("batiment") == "Foyer"
    tva_log = 10 if foyer else 20          # travaux d'amélioration dans des logements de plus de 2 ans : TVA 10 %
    sS = f"{S:.1f} m²".replace(".", ",") if S else "non mesurable sur le plan"
    src = l.get("source") or "plans vectoriels"
    num = (re.search(r"\d{3}", l["nom"]) or [None])[0] if re.search(r"\d{3}", l["nom"]) else ""
    E = {"reference": l["id"].upper() if not num else f"{niv.upper()}-{num}", "surface": f"[Plan] {sS}",
         "surface_future": f"[Projet] Inchangée ({sS})" if S else "",
         "configuration": "", "fonction_actuelle": "", "fonction_future": "", "capacite": "", "pmr": "À vérifier",
         "acces_circulation": l.get("acces") and f"[Plan] {l['acces']}" or "", "particularites": "", "contraintes": ""}
    A, F, B, hyp = {}, {}, [], []
    risques = "\n".join(f"- {r['texte']}" for r in (l.get("risques") or []))
    equipements = "\n".join(f"- {e['nom']}{' : ' + e['detail'] if e.get('detail') else ''}" for e in (l.get("equipements") or []))
    vigil_site = "[À vérifier sur site] État des murs, sols, plafonds, menuiseries et équipements : non documenté par les plans."

    if f == "chambre":
        pmr = "PMR" in l["nom"]
        couple = "couple" in l["nom"].lower()
        conserve = niv in ("r1", "r4") or not foyer
        E.update(fonction_actuelle="[Plan] Chambre d'étudiant du foyer (cellule sanitaire préfabriquée et bloc kitchenette d'origine).",
                 fonction_future=f"[Projet] {'Studio PMR' if pmr else 'Studio couple' if couple else 'Studio'} autonome : kitchenette, salle d'eau avec WC, espace nuit, rangements.",
                 configuration=f"[Plan] Pièce unique d'environ {sS}, une fenêtre en façade, porte palière sur le couloir central ; "
                               f"cellule sanitaire contre le refend porteur, placard technique (gaine) côté couloir.",
                 capacite=f"[Projet] {2 if couple else 1} personne{'s' if couple else ''}",
                 pmr="Accessible (chambre adaptée du DOE)" if pmr else "Non accessible",
                 particularites="[Plan] Plancher chauffant à eau noyé dans la dalle (1990) : aucun carottage ni trémie sans repérage des tubes.",
                 contraintes="[Plan] Refends porteurs sur la trame de 3,10 m ; ventilation par la VMC collective. "
                             "[À vérifier sur site] Le DOE ne dessine pas de gaine dans les noyaux sanitaires : passage des chutes et colonnes "
                             "entre les cellules dos à dos à confirmer.")
        A = {"description": f"[Plan] Chambre de {sS} au {et}, desservie par le couloir central, éclairée par une fenêtre "
                             f"(double vitrage d'origine, lame d'air 8 mm, Uw ≈ 3 d'après le DPE 2020). Équipée d'origine d'une cellule "
                             f"sanitaire préfabriquée (1990) et d'un bloc kitchenette.",
             "defauts": "[Plan] Défauts documentés à l'échelle du foyer (planches D2, D4) : enveloppe non isolée, menuiseries d'origine, "
                        "VMC autoréglable, DPE E (243 kWhep/m².an). Aucun défaut propre à cette chambre n'est documenté.",
             "problemes_techniques": "[Estimation] Cellule sanitaire et réseaux de 35 ans en fin de vie probable.\n[À vérifier sur site] Étanchéité des douches, état du plancher chauffant.",
             "murs_sols_plafonds": "[À vérifier sur site] État des peintures, du revêtement de sol et du plafond.",
             "menuiseries": "[Plan] Fenêtre PVC double vitrage d'origine.\n[À vérifier sur site] Joints, quincaillerie, porte palière (degré coupe-feu).",
             "equipements": "[À vérifier sur site] Kitchenette, appareils sanitaires, radiateur/plancher chauffant, appareillage électrique.",
             "accessibilite": "[Plan] Chambre adaptée PMR (DOE)." if pmr else "[Plan] Chambre non adaptée : largeur de passage et salle d'eau non conformes PMR.",
             "securite_circulation": "[Plan] Porte palière sur couloir d'évacuation : degré coupe-feu à vérifier.",
             "vigilance": "Amiante : DTA 2017 négatif pour les parties communes, chambres non visitées → repérage avant travaux obligatoire.",
             "observations": vigil_site}
        F = {"description": f"[Projet] {'Maintien de la structure existante' if conserve else 'Chambre conservée'} et transformation en "
                            f"studio fonctionnel : salle d'eau neuve {'PMR (aire de rotation Ø 1,50 m) ' if pmr else ''}avec douche de plain-pied, lavabo et WC "
                            f"à l'emplacement de la cellule existante (raccordement sur la gaine voisine), kitchenette de 120 cm le long de la "
                            f"cloison technique, penderie, lit {'140' if couple else '90'} près de la fenêtre et bureau.",
             "nouvelle_fonction": f"Studio {'PMR ' if pmr else ''}{'couple ' if couple else ''}étudiant",
             "travaux": "Dépose de la cellule sanitaire et de la kitchenette ; salle d'eau préfabriquée ou traditionnelle neuve ; kitchenette ; "
                        "mise aux normes électriques ; bouches VMC hygroréglables ; remplacement de la fenêtre ; sols et peintures.",
             "modifications": "Aucune modification de la structure : les refends et la gaine restent en place.",
             "amenagements": "Penderie 1 m, bureau, lit, rangements hauts au-dessus de la kitchenette.",
             "equipements": "Évier, 2 plaques induction, réfrigérateur table-top, hotte à recyclage ; douche, lavabo, WC ; VMC hygro B.",
             "accessibilite": "Studio PMR maintenu (au moins une unité adaptée par niveau)." if pmr else "Pas d'adaptation PMR possible dans cette surface.",
             "contraintes": "Réseaux d'évacuation imposés par la gaine existante ; aucun percement du plancher chauffant sans repérage ; "
                            "acoustique entre logements (bruit d'équipement ≤ 30 dB(A), planche R2.2).",
             "vigilance": "Proposition architecturale non validée techniquement : relevé des réseaux et visite à faire.",
             "temporalite": "[Estimation] 3 à 4 semaines par studio, en rénovation par lots de chambres (site occupé possible)."}
        B = [L("Dépose", "Dépose cellule sanitaire, kitchenette et revêtements, évacuation", 1, "forfait", 1400, tva_log),
             L("Plomberie", f"Salle d'eau {'PMR ' if pmr else ''}neuve (douche, lavabo, WC) raccordée sur gaine", 1, "u", 9800 if pmr else 7200, tva_log),
             L("Équipements", "Kitchenette 120 cm (évier, 2 feux induction, réfrigérateur, hotte)", 1, "u", 2400, tva_log),
             L("Électricité", "Mise aux normes et appareillage", S, "m²", 70, tva_log),
             L("Chauffage et ventilation", "Bouches VMC hygroréglables (salle d'eau, cuisine)", 2, "u", 180, tva_log),
             L("Menuiseries", "Fenêtre PVC Uw ≤ 1,3", 1, "u", 1150, tva_log),
             L("Menuiseries", "Bloc-porte palière EI30", 1, "u", 1250, tva_log)]
        B += finitions(S, tva_log)
        B.append(L("Mobilier", f"Lit {'140' if couple else '90'}, penderie, bureau, rangements", 1, "forfait", 1700 if couple else 1300, 20))
        hyp.append(f"Surface du plan : {sS} ; hauteur sous plafond supposée 2,50 m.")

    elif f == "logement":
        E.update(fonction_actuelle="[Plan] Deux chambres d'étudiant contiguës (cellules sanitaires et kitchenettes d'origine).",
                 fonction_future="[Projet] Logement T1 bis : séjour-cuisine, espace nuit, salle d'eau avec WC, rangements.",
                 configuration=f"[Projet] Deux anciennes chambres réunies ({sS}) par une baie de 2,40 m dans le refend ; une seule porte palière conservée ; "
                               f"kitchenette contre le refend (gaine), salle d'eau contre le noyau sanitaire.",
                 capacite="[Projet] 1 à 2 personnes", pmr="Non accessible (cheminements à vérifier)",
                 surface=f"[Plan] Deux chambres d'environ {S / 2:.1f} m² chacune".replace(".", ","),
                 surface_future=f"[Projet] {sS} (logement réuni, refend ouvert)",
                 particularites="[Plan] Gaine technique conservée en place à l'angle du refend, côté couloir.",
                 contraintes="[Estimation] Le refend entre les chambres est sur la trame porteuse : baie à dimensionner par un BET structure (ferroscan, note de calcul).")
        A = {"description": f"[Plan] Deux chambres d'environ 16 m² chacune au {et}, chacune avec sa cellule sanitaire préfabriquée et son bloc kitchenette, "
                             "séparées par un refend, desservies par deux portes palières.",
             "defauts": "[Plan] Défauts documentés à l'échelle du foyer : enveloppe non isolée, menuiseries d'origine, VMC autoréglable, DPE E.",
             "problemes_techniques": "[Estimation] Équipements sanitaires de 35 ans.\n[À vérifier sur site] Plancher chauffant, réseaux en gaine.",
             "murs_sols_plafonds": "[À vérifier sur site] État des revêtements.", "menuiseries": "[Plan] Deux fenêtres PVC d'origine.",
             "equipements": "[À vérifier sur site]", "accessibilite": "[Plan] Chambres non adaptées PMR.",
             "securite_circulation": "[Plan] Portes palières sur couloir d'évacuation : degré coupe-feu à vérifier.",
             "vigilance": "Repérage amiante avant travaux (colles, joints des cellules).", "observations": vigil_site}
        F = {"description": "[Projet] Logement d'une pièce et demie : entrée par la porte conservée, séjour avec kitchenette de 180 cm contre le refend "
                            "(raccordée sur la gaine), coin repas et canapé côté fenêtre ; espace nuit dans l'autre moitié avec lit 140 et penderie ; "
                            "salle d'eau de 4,8 m² (douche, lavabo, WC) contre le noyau sanitaire existant.",
             "nouvelle_fonction": "Logement T1 bis",
             "travaux": "Ouverture d'une baie de 2,40 m dans le refend avec linteau ; suppression d'une porte palière (rebouchage coupe-feu) ; "
                        "dépose des deux cellules ; cloisons de la salle d'eau ; kitchenette ; électricité ; VMC ; deux fenêtres ; sols, peintures.",
             "modifications": "Baie dans un refend porteur (à valider) ; rebouchage d'une porte palière.",
             "amenagements": "Penderie, rangements hauts, table pour 2, canapé.",
             "equipements": "Kitchenette 180 cm (évier, 2 feux, four combiné, réfrigérateur), douche 90 × 90, lavabo, WC suspendu, VMC hygro B.",
             "accessibilite": "Non prévu PMR.", "contraintes": "Gaine et noyau sanitaire conservés ; plancher chauffant ; validation structure obligatoire.",
             "vigilance": "Décision structurelle à confirmer par un BET avant toute démolition.",
             "temporalite": "[Estimation] 6 à 8 semaines par logement, après validation structure."}
        B = [L("Gros œuvre", "Étude BET structure, ferroscan et note de calcul", 1, "forfait", 1800, tva_log),
             L("Gros œuvre", "Baie de 2,40 m dans refend béton : sciage, linteau, renforts (à valider BET)", 1, "forfait", 5200, tva_log),
             L("Démolition", "Dépose de deux cellules sanitaires, deux kitchenettes et revêtements", 1, "forfait", 2300, tva_log),
             L("Gros œuvre", "Suppression d'une porte palière : dépose et rebouchage coupe-feu", 1, "forfait", 900, tva_log),
             L("Cloisons", "Cloisons de salle d'eau en plaques hydrofuges", 10.0, "m²", 65, tva_log),
             L("Plomberie", "Salle d'eau neuve (douche, lavabo, WC) raccordée sur gaine", 1, "u", 7800, tva_log),
             L("Équipements", "Kitchenette 180 cm équipée", 1, "u", 3600, tva_log),
             L("Électricité", "Installation neuve du logement", S, "m²", 75, tva_log),
             L("Chauffage et ventilation", "Bouches VMC hygroréglables", 3, "u", 180, tva_log),
             L("Menuiseries", "Fenêtres PVC Uw ≤ 1,3", 2, "u", 1150, tva_log),
             L("Menuiseries", "Bloc-porte palière EI30", 1, "u", 1250, tva_log)]
        B += finitions(S, tva_log)
        B.append(L("Mobilier", "Lit 140, canapé, table, penderie, rangements", 1, "forfait", 2900, 20))
        hyp.append("Prix de la baie hors renforcement exceptionnel : à reprendre après note de calcul.")

    elif f in ("gaine", "vo"):
        dans_toit = niv == "terrasse"
        E.update(fonction_actuelle="[Plan] Gaine technique verticale" + (" (débouché en toiture)" if dans_toit else ""),
                 fonction_future="[Projet] Conservée en place : élément fixe du projet.",
                 configuration=f"[Plan] Emprise {sS}, carré hachuré sur le DOE, aligné d'un étage à l'autre (comparaison des plans R+1 à R+3).",
                 pmr="Sans objet", particularites="[À vérifier sur site] Contenu non documenté : chutes EU/EV, colonnes EF/ECS, conduits VMC ?",
                 contraintes="Traversées de planchers à recouper au degré coupe-feu (planche R2.4).")
        if f == "vo":
            E["fonction_actuelle"] = "[Plan] Trémie de vide-ordures (V.O.) avec local de collecte au pied"
            E["fonction_future"] = "[Projet] Condamnation du vide-ordures et réaffectation de la trémie en gaine technique (proposition)."
        gid = (re.search(r"G\d", l["nom"]) or [None])[0] if re.search(r"G\d", l["nom"]) else ("VO" if f == "vo" else None)
        TOIT = {"G3": "sortie de ventilation G3 (DOE Ex12bis)", "G4": "trappe de la gaine G4 dans la chaufferie (DOE Ex12bis)",
                "VO": "débouché du vide-ordures (DOE Ex12bis)"}
        vertical = ("[Plan] Même gaine aux R+1, R+2, R+3 et R+4, au même emplacement : vérifié par superposition des plans DOE Ex09a "
                    "(R+1), Ex10a (R+2) et Ex11a (R+3) ; le R+4 reprend le R+3. "
                    + (f"Débouché en toiture : {TOIT[gid]}." if gid in TOIT else "[À vérifier sur site] Débouché en toiture non identifié sur le plan de terrasse."))
        A = {"description": f"[Plan] {'Vide-ordures' if f == 'vo' else 'Gaine technique'} relevé sur le DOE au {et}.\n" + (vertical if not dans_toit else ""),
             "problemes_techniques": "[À vérifier sur site] Nature et état des réseaux, calfeutrements coupe-feu, trappes d'accès.",
             "vigilance": "Ne pas déplacer ni supprimer : la gaine dessert les salles d'eau et kitchenettes voisines.", "observations": vigil_site}
        F = {"description": "[Projet] Gaine conservée ; repérage des réseaux ; raccordement des nouvelles salles d'eau et kitchenettes ; "
                            "remise à niveau des calfeutrements coupe-feu à chaque plancher ; trappe de visite.",
             "travaux": "Inspection, repérage, calfeutrements coupe-feu, trappe EI.", "contraintes": "Accès depuis le couloir ou la pièce voisine.",
             "temporalite": "[Estimation] Avec les travaux des logements voisins."}
        B = [L("Aménagements spécifiques", "Inspection et repérage des réseaux (caméra)", 1, "forfait", 250, tva_log),
             L("Gros œuvre", "Calfeutrement coupe-feu des traversées de plancher", 2, "u", 280, tva_log),
             L("Menuiseries", "Trappe de visite EI30", 1, "u", 380, tva_log)]
        if f == "vo":
            B = [L("Gros œuvre", "Condamnation des trappes de vide-ordures (EI60)", 1, "u", 650, tva_log),
                 L("Aménagements spécifiques", "Nettoyage et désinfection de la trémie", 1, "forfait", 900, tva_log)]
        if dans_toit:
            B = [L("Équipements", "Chapeau / sortie de ventilation neuve et relevé d'étanchéité", 1, "u", 450, 20)]

    elif f == "vbvh":
        E.update(fonction_actuelle=f"[Plan] Gaine de ventilation naturelle du parking ({'basse' if l['nom'].startswith('VB') else 'haute'}, air frais / air vicié).",
                 fonction_future="[Projet] Conservée ; contrôle des sections et des grilles.",
                 configuration=f"[Plan] {l['nom']} (surface lue sur le DOE).", pmr="Sans objet",
                 contraintes="Section libre à maintenir (ventilation réglementaire du parking).")
        A = {"description": f"[Plan] Gaine de ventilation du parking : {l['nom']}.", "problemes_techniques": "[À vérifier sur site] Grilles, encrassement, obstructions.",
             "observations": vigil_site}
        F = {"description": "[Projet] Nettoyage, contrôle de la section libre, remplacement des grilles si dégradées.", "travaux": "Nettoyage, grilles."}
        B = [L("Aménagements spécifiques", "Nettoyage et contrôle de la section libre", 1, "forfait", 450, 20),
             L("Équipements", "Grille de ventilation acier galvanisé", 1, "u", 320, 20)]

    elif f == "ascenseur":
        principal = niv == "sous-sol"
        E.update(fonction_actuelle="[Plan] Ascenseur" + (" du foyer" if foyer else " desservant le parking et le noyau central"),
                 fonction_future="[Projet] Conservé ; mise en conformité et modernisation.",
                 configuration=f"[Plan] Gaine d'emprise {sS} (cabine et parois), au {et}.", capacite="[À vérifier sur site] Charge et nombre de personnes (plaque de cabine).",
                 pmr="Accessible si cabine ≥ 1,00 × 1,25 m — à vérifier", particularites="[Plan] Machinerie en toiture pour l'ascenseur nord du foyer (DOE Ex12bis).",
                 contraintes="[Estimation] Installation d'environ 1990 : contrôle technique quinquennal, sécurité des ascenseurs existants, accessibilité.")
        A = {"description": f"[Plan] Ascenseur relevé sur le DOE au {et}.",
             "problemes_techniques": "[À vérifier sur site] Date de mise en service, rapport du dernier contrôle quinquennal, précision d'arrêt, portes palières.",
             "accessibilite": "[Plan] Un seul ascenseur relie le RDC bas et le RDC haut : une panne coupe l'accès PMR (planche D2.3)." if niv in ("rdc-bas", "rdc-haut", "sous-sol") else "",
             "vigilance": "Continuité de service pour les résidents et les PMR pendant les travaux.", "observations": vigil_site}
        F = {"description": "[Projet] Conservation de l'appareil ; diagnostic par un bureau de contrôle ; modernisation : armoire de commande, variation de fréquence, "
                            "portes palières, cabine (éclairage LED, main courante, miroir), boîte à boutons en relief et annonce vocale, téléalarme.",
             "travaux": "Diagnostic, modernisation de la machinerie, portes palières, cabine.", "accessibilite": "Signalétique en relief, annonce sonore, éclairage ≥ 100 lux.",
             "contraintes": "Arrêt de l'appareil pendant 3 à 6 semaines : prévoir un phasage.", "temporalite": "[Estimation] Après diagnostic, en dehors des périodes d'occupation maximale."}
        B = ([L("Équipements", "Diagnostic par bureau de contrôle", 1, "forfait", 1400, 20),
              L("Équipements", "Modernisation (armoire, moteur à variation de fréquence, cabine, téléalarme)", 1, "forfait", 32000, 20)]
             if principal else [L("Équipements", "Porte palière et boîte à boutons en relief (par niveau)", 1, "u", 4200, 20)])
        hyp.append("Le coût de modernisation de l'appareil est porté une seule fois (niveau le plus bas) ; les autres niveaux portent leur porte palière.")

    elif f == "escalier":
        if niv == "terrasse":
            E.update(fonction_actuelle="[Plan] Édicule de sortie d'escalier en toiture", fonction_future="[Projet] Conservé ; étanchéité et accès sécurisés.",
                     configuration=f"[Plan] Emprise {sS}.", pmr="Sans objet")
            A = {"description": f"[Plan] {l['nom']}.", "problemes_techniques": "[Plan] Étanchéités de 35 ans (planche D2.4).", "observations": vigil_site}
            F = {"description": "[Projet] Réfection des relevés d'étanchéité de l'édicule, porte d'accès à la terrasse verrouillée, éclairage."}
            per = 4 * math.sqrt(max(S, 1))
            B = [L("Gros œuvre", "Relevés d'étanchéité de l'édicule", per, "ml", 55, 20), L("Peinture", "Peinture extérieure de l'édicule", per * 2.5, "m²", 30, 20)]
        else:
            E.update(fonction_actuelle="[Plan] Escalier", fonction_future="[Projet] Conservé ; mise en sécurité.",
                     configuration=f"[Plan] Cage de {sS} au {et}.", pmr="Escalier : non accessible fauteuil ; mise en accessibilité « ambulants »",
                     contraintes="Dégagement d'évacuation : aucun stockage, désenfumage à vérifier.")
            A = {"description": f"[Plan] {l['nom']}, cage relevée sur le DOE.", "securite_circulation": "[À vérifier sur site] Désenfumage, éclairage de sécurité, mains courantes.",
                 "observations": vigil_site}
            F = {"description": "[Projet] Nez de marche contrastés et antidérapants, contremarches de première et dernière marche contrastées, bandes d'éveil "
                                "de vigilance en haut des volées, mains courantes des deux côtés prolongées, éclairage LED à détection, peinture de la cage."}
            B = [L("Aménagements spécifiques", "Nez de marche contrastés antidérapants", 22, "ml", 45, tva_log),
                 L("Aménagements spécifiques", "Bandes d'éveil de vigilance", 2, "u", 180, tva_log),
                 L("Aménagements spécifiques", "Main courante prolongée", 8, "ml", 140, tva_log),
                 L("Électricité", "Luminaires LED à détection", 3, "u", 230, tva_log),
                 L("Peinture", "Peinture de la cage", float(round(max(S, 8) * 3)), "m²", 24, tva_log)]

    elif f == "place":
        k = int(re.search(r"(\d+)", l["nom"]).group(1)) if re.search(r"(\d+)", l["nom"]) else 0
        pmr = "PMR" in l["nom"]
        irve = (k % 10 == 1) and not pmr
        E.update(fonction_actuelle="[Plan] Place de stationnement" + (" PMR" if pmr else ""),
                 fonction_future="[Projet] Place conservée" + (" avec point de recharge" if irve else "") + (", PMR (3,30 m)" if pmr else ""),
                 configuration=f"[Plan] {sS}, largeur 2,42 m relevée sur la trame du DOE.", capacite="1 véhicule",
                 pmr="Place PMR" if pmr else "Non", contraintes="Obligations : 2 % de places PMR, 1 point de recharge pour 20 places (1 pour 10 en 2027) — planche R1.3.")
        A = {"description": f"[Plan] Place {l['nom'].replace('Place ', '')} au niveau -1.", "observations": "[À vérifier sur site] Marquage, état du sol."}
        F = {"description": "[Projet] Re-marquage et numérotation." + (" Pré-équipement et borne de recharge 7 kW (quota IRVE)." if irve else "")
                            + (" Signalisation verticale et marquage PMR, largeur 3,30 m." if pmr else "")}
        B = [L("Aménagements spécifiques", "Marquage au sol et numérotation", 1, "u", 95, 20)]
        if irve:
            B.append(L("Électricité", "Borne de recharge 7 kW et raccordement", 1, "u", 1900, 20))
        if pmr:
            B.append(L("Aménagements spécifiques", "Signalisation PMR (panneau, pictogramme, bande)", 1, "u", 450, 20))

    elif f == "rampe":
        E.update(fonction_actuelle="[Plan] " + l["nom"], fonction_future="[Projet] Conservée ; sécurisation.", configuration=f"[Plan] {sS}.", pmr="Sans objet")
        A = {"description": f"[Plan] {l['nom']} (DOE Ex07c).", "securite_circulation": "[À vérifier sur site] Glissance, éclairage, signalisation entrée / sortie.",
             "observations": vigil_site}
        F = {"description": "[Projet] Revêtement résine antidérapant, éclairage LED, feux de signalisation entrée / sortie, chasse-roues."}
        B = [L("Revêtements de sols", "Résine antidérapante", S, "m²", 42, 20),
             L("Électricité", "Éclairage LED étanche", max(2, round(S / 15)), "u", 260, 20),
             L("Équipements", "Feux de signalisation entrée / sortie", 1, "forfait", 2200, 20)]

    elif f == "parking":
        E.update(fonction_actuelle="[Plan] Parking enterré, allées de circulation", fonction_future="[Projet] Parking mutualisé (résidents, ERP), vélos.",
                 configuration=f"[Plan] {sS} d'allées ; niveaux -2,20 et -2,80.", capacite="[Plan] 115 places (DOE)",
                 pmr="Places PMR à proximité de l'ascenseur", contraintes="Isolement renforcé vis-à-vis de l'ERP et du foyer, communication par sas (R2.5).")
        A = {"description": "[Plan] Parking de 115 places sur deux niveaux, ventilation naturelle par gaines VB/VH.",
             "problemes_techniques": "[Estimation] Carbonatation, aciers apparents possibles (planche D3.1).\n[À vérifier sur site]",
             "observations": vigil_site}
        F = {"description": "[Projet] Peinture de sol des allées, éclairage LED à détection, signalétique directionnelle, contrôle de la ventilation, local vélos couvert."}
        B = [L("Peinture", "Peinture de sol des allées", S, "m²", 18, 20),
             L("Électricité", "Éclairage LED à détection", max(4, round(S / 25)), "u", 260, 20),
             L("Aménagements spécifiques", "Signalétique directionnelle", 1, "forfait", 1500, 20),
             L("Gros œuvre", "Diagnostic béton (carbonatation, aciers)", 1, "forfait", 3500, 20)]

    elif f == "toiture":
        E.update(fonction_actuelle="[Plan] Toiture-terrasse inaccessible (béton)", fonction_future="[Projet] Toiture isolée et étanchée à neuf.",
                 configuration=f"[Plan] {sS} entre joints de dilatation (DOE Ex12bis).", pmr="Sans objet",
                 contraintes="Charge admissible et pentes non documentées ; accès technique uniquement.")
        A = {"description": f"[Plan] {l['nom']} : terrasse béton, acrotère, débouchés de gaines.",
             "defauts": "[Plan] Aucun isolant relevé, étanchéité d'environ 35 ans (planches D2.4, 1.5).",
             "problemes_techniques": "[À vérifier sur site] Infiltrations, état des relevés, évacuations EP.", "observations": vigil_site}
        F = {"description": "[Projet] Dépose de l'étanchéité, isolation 160 mm (R ≈ 6), étanchéité bicouche neuve, relevés et évacuations EP, ligne de vie pour l'entretien."}
        per = 2 * (math.sqrt(S / 4) * 5) if S else 0
        B = [L("Dépose", "Dépose de l'étanchéité existante", S, "m²", 18, 20),
             L("Gros œuvre", "Isolation 160 mm et étanchéité bicouche", S, "m²", 145, 20),
             L("Gros œuvre", "Relevés d'étanchéité en acrotère", float(round(per)), "ml", 55, 20)]

    elif f == "chaufferie":
        E.update(fonction_actuelle="[Plan] Chaufferie gaz (2 chaudières standard en cascade) en toiture du foyer",
                 fonction_future="[Projet] Production par pompe à chaleur collective (ou condensation + PAC) après étude ; raccordement au réseau de chaleur à tester.",
                 configuration=f"[Plan] {sS}, ventilations haute et basse, porte « passage » (DOE Ex12bis).", pmr="Sans objet",
                 contraintes="Local à risques isolé ; organe de coupure gaz accessible depuis l'extérieur.")
        A = {"description": "[Plan] Chaufferie gaz du foyer : 551 635 kWh PCS par an (DPE 2020).", "defauts": "[Estimation] Rendement faible, fin de vie probable.",
             "problemes_techniques": "[À vérifier sur site] Âge et état des chaudières, conformité gaz.", "observations": vigil_site}
        F = {"description": "[Projet] Étude de faisabilité PAC et réseau de chaleur ; remplacement de la production ; désembouage du plancher chauffant conservé."}
        B = [L("Chauffage et ventilation", "Étude de faisabilité PAC / réseau de chaleur", 1, "forfait", 4500, 20),
             L("Chauffage et ventilation", "Production PAC collective (hypothèse ≈ 80 €/m² chauffé × 2 037 m²)", 1, "forfait", 163000, 10),
             L("Chauffage et ventilation", "Désembouage et essais du plancher chauffant", 1, "forfait", 9500, 10)]
        hyp.append("Le coût de production est porté par la chaufferie pour tout le foyer.")

    elif f in ("tgbt", "ecs", "vmc", "machinerie", "tech"):
        txt = {"tgbt": "Tableau général basse tension", "ecs": "Production d'eau chaude sanitaire", "vmc": "Local de ventilation",
               "machinerie": "Machinerie d'ascenseur", "tech": "Local technique"}[f]
        inconnu = f == "tech" and not l.get("resume")
        E.update(fonction_actuelle=f"[Plan] {txt}" + (" — fonction exacte à vérifier sur site" if inconnu else ""),
                 fonction_future=f"[Projet] {txt} conservé" + (" ; affectation à confirmer après visite" if inconnu else ""),
                 configuration=f"[Plan] {sS} au {et}.", pmr="Sans objet (accès réservé au personnel)",
                 contraintes="Local à risques : porte coupe-feu, accès réservé, détection (planche R2.5).")
        A = {"description": f"[Plan] {l.get('resume') or txt + ' relevé sur le plan.'}",
             "problemes_techniques": (risques and "[Plan] " + risques) or "[À vérifier sur site] Équipements non diagnostiqués (planche D4.3).",
             "equipements": equipements and "[Plan] " + equipements or "[À vérifier sur site]", "observations": vigil_site}
        F = {"description": "[Projet] " + (l.get("projet") or f"{txt} conservé ; diagnostic, mise en conformité, porte coupe-feu et éclairage.")}
        B = [L("Aménagements spécifiques", "Diagnostic de l'installation", 1, "forfait", 600 if f != "tech" else 300, 20)]
        if f == "tgbt":
            B += [L("Électricité", "Remplacement du TGBT et bilan de puissance (hypothèse)", 1, "forfait", 28000, 20),
                  L("Menuiseries", "Bloc-porte EI60 avec ferme-porte", 1, "u", 1600, 20)]
        if f == "ecs":
            B += [L("Plomberie", "Calorifugeage, bouclage et analyses légionelles", 1, "forfait", 3800, 20)]
        if f == "vmc":
            B += [L("Chauffage et ventilation", "Centrale double flux (pôles ERP, hypothèse)", 1, "u", 18000, 20)]
        if not inconnu and f == "tech":
            B += finitions(S, 20, sol=("résine", 38))

    else:
        # espaces des RDC, salle des fêtes, circulations, sanitaires, stockage…
        M = MODELES.get(f, MODELES["autre"])
        E.update(fonction_actuelle="[Plan] " + M["actuel"], fonction_future="[Projet] " + M["futur"],
                 configuration=f"[Plan] {sS} au {et}." + (" " + M.get("config", "")),
                 capacite=(f"[Estimation] {max(1, round(S / M['ratio']))} personnes (effectif théorique à recalculer selon le règlement ERP)" if M.get("ratio") and S else ""),
                 pmr=M.get("pmr", "À vérifier"), particularites=M.get("particularites", ""), contraintes=M.get("contraintes", ""))
        A = {"description": f"[Plan] {l.get('resume') or M['actuel'] + ' relevé sur le plan vectoriel.'}",
             "problemes_techniques": (risques and "[Plan] " + risques) or M.get("problemes", "[À vérifier sur site]"),
             "accessibilite": M.get("acc_actuel", ""), "vigilance": M.get("vigilance", ""), "observations": vigil_site}
        F = {"description": "[Projet] " + (M["futur_long"] + (" " + l["projet"] if l.get("projet") else "")),
             "nouvelle_fonction": M["futur"], "travaux": M.get("travaux", ""), "equipements": M.get("equip", ""),
             "contraintes": M.get("contraintes", ""), "temporalite": M.get("temps", "")}
        B = [L(*x[:2], S * x[2] if x[3] == "m²" and x[2] < 5 and S else x[2], x[3], x[4], x[5] if len(x) > 5 else 20) for x in M.get("budget", [])]
        B += finitions(S, 20, sol=M.get("sol", ("PVC / linoléum U3P3", 48)), luminaire=M.get("lum")) if M.get("finitions", True) else []

    # affectation actuelle constatée par le groupe : prioritaire sur la lecture des plans (l'affectation future ne change pas)
    if l.get("affectation_actuelle"):
        aff = l["affectation_actuelle"]
        cours = "cours" in aff.lower()
        precision = (" Une salle de cours est équipée de chaises, de tables, d'un bureau et d'un tableau." if cours else "")
        E["fonction_actuelle"] = f"[Constat] {aff}.{precision}"
        A["description"] = f"[Constat] Affectation actuelle : {aff.lower() if not aff.startswith('Espace') else aff}.{precision}\n" + A.get("description", "")
        if cours:
            A["equipements"] = "[Constat] Mobilier de salle de cours (tables, chaises, bureau, tableau) à déposer.\n" + A.get("equipements", "[À vérifier sur site]")
            B.insert(0, L("Dépose", "Dépose et évacuation du mobilier de salle de cours", 1, "forfait", 600, 20))
        if "vide" in aff.lower():
            A["equipements"] = "[Constat] Salles vides : aucun équipement à déposer."
    if l.get("coupure"):
        A["securite_circulation"] = (A.get("securite_circulation", "") + "\n[Plan] Consignes de coupure : voir le bouton « Couper / sécuriser ».").strip()
    if l.get("remarques"):
        A["observations"] = (A.get("observations", "") + "\n" + l["remarques"]).strip()
    for k in list(E):
        if not E[k]:
            E[k] = "[À vérifier sur site]" if k in ("pmr", "capacite") and f not in ("gaine", "vo", "vbvh") else E[k]
    B = [b for b in B if b["quantite"] and b["quantite"] > 0]
    return {"essentiel": E, "actuel": {k: v for k, v in A.items() if v}, "futur": {k: v for k, v in F.items() if v},
            "budget": {"tva": 20, "lignes": B, "hypotheses": " ".join(hyp + [AVERT])},
            "_auto": {"genere_le": DATE, "fonction": f, "source": src}}


# modèles des espaces collectifs : budget = (poste, désignation, quantité ou ratio/m² si < 5 et unité m², unité, PU HT, TVA)
MODELES = {
    "danse": dict(actuel="Salle (ex-cours) affectée à la danse dans le projet", futur="Salle de danse", ratio=4,
                  futur_long="Salle de danse : parquet flottant sur lambourdes, miroirs sur un mur, barres, traitement acoustique du plafond, ventilation double flux.",
                  contraintes="Hauteur libre probable 2,50 à 2,80 m à confirmer (planche D2.3) ; acoustique vis-à-vis des étages.", pmr="Accessible par l'ascenseur du RDC bas",
                  budget=[("Revêtements de sols", "Parquet flottant sur lambourdes", 1, "m²", 110), ("Aménagements spécifiques", "Miroirs de sécurité", 8, "ml", 260),
                          ("Aménagements spécifiques", "Barres de danse", 8, "ml", 85), ("Aménagements spécifiques", "Plafond acoustique", 1, "m²", 55),
                          ("Chauffage et ventilation", "Ventilation double flux (quote-part)", 1, "m²", 90)],
                  sol=("parquet sportif (cf. ligne dédiée)", 0), finitions=False),
    "boxe": dict(actuel="Salle (ex-cours) affectée à la boxe dans le projet", futur="Salle de boxe", ratio=4,
                 futur_long="Salle de boxe : sol sportif souple, protections murales, ancrages de sacs (après vérification du plancher haut), ventilation double flux.",
                 contraintes="Fixations au plafond à valider par un BET (charge non documentée).", pmr="Accessible par l'ascenseur du RDC bas",
                 budget=[("Revêtements de sols", "Sol sportif souple", 1, "m²", 85), ("Aménagements spécifiques", "Protections murales", 20, "ml", 95),
                         ("Aménagements spécifiques", "Ancrages de sacs et renforts (à valider BET)", 1, "forfait", 2800),
                         ("Chauffage et ventilation", "Ventilation double flux (quote-part)", 1, "m²", 90)], finitions=False),
    "muscu": dict(actuel="Grande salle affectée à la musculation", futur="Salle de musculation", ratio=5,
                  futur_long="Salle de musculation sur dallage : sol caoutchouc 15 mm, renforts électriques, ventilation double flux.",
                  contraintes="Musculation sur dallage après sondage du plancher (planche D3.1).", pmr="Accessible par l'ascenseur du RDC bas",
                  budget=[("Gros œuvre", "Sondage du plancher", 1, "forfait", 900), ("Revêtements de sols", "Sol caoutchouc 15 mm", 1, "m²", 70),
                          ("Chauffage et ventilation", "Ventilation double flux (quote-part)", 1, "m²", 90)], finitions=False),
    "escalade": dict(actuel="Salle affectée à l'escalade dans le projet", futur="Salle sportive polyvalente (bloc bas si la hauteur le permet)", ratio=4,
                     futur_long="Les blocs de 4 m ne rentrent pas au RDC bas (planche 1.8) : salle polyvalente sport, pan d'escalade bas uniquement si la hauteur libre le permet.",
                     contraintes="Hauteur libre à relever avant tout choix.", budget=[("Aménagements spécifiques", "Relevé 3D des hauteurs", 1, "forfait", 1200),
                     ("Revêtements de sols", "Sol sportif", 1, "m²", 85), ("Aménagements spécifiques", "Tapis de réception (zone bloc)", 0.4, "m²", 140)], finitions=False),
    "street": dict(actuel="Patio extérieur", futur="Espace de street workout", ratio=6, futur_long="Agrès de street workout dans le patio, sol amortissant drainant.",
                   budget=[("Équipements", "Structure d'agrès", 1, "forfait", 9500), ("Revêtements de sols", "Sol amortissant drainant", 1, "m²", 95)], finitions=False),
    "golf": dict(actuel="Salle affectée au simulateur de golf", futur="Simulateur de golf", ratio=6,
                 futur_long="2 à 3 box de golf si la hauteur libre atteint 3,00 à 3,50 m (planche 1.8), écrans de projection, filets, ventilation.",
                 contraintes="Hauteur libre à confirmer.", budget=[("Équipements", "Box de simulateur (écran, capteurs, filets)", 2, "u", 14000),
                 ("Revêtements de sols", "Gazon synthétique", 1, "m²", 55)], finitions=False),
    "cinema": dict(actuel="Amphithéâtre de 140 places", futur="Cinéma / salle de spectacle", ratio=1,
                   futur_long="Salle de projection : fauteuils, écran et projection, traitement acoustique, désenfumage à recalculer, issues directes.",
                   contraintes="Sons amplifiés sous des chambres : acoustique critique (planche D5.4) ; classement « cinéma » interdit en zone UL (R1.1).",
                   budget=[("Aménagements spécifiques", "Étude acoustique et désenfumage", 1, "forfait", 4500), ("Équipements", "Écran et projection", 1, "forfait", 18000),
                           ("Aménagements spécifiques", "Traitement acoustique", 1, "m²", 95)], sol=("moquette", 42)),
    "musique": dict(actuel="Salle (ex-labo de langues)", futur="Studio de musique", ratio=6,
                    futur_long="Studio de musique : boîte dans la boîte (doublages, plafond désolidarisé), porte acoustique, traitement interne.",
                    contraintes="Isolement acoustique vis-à-vis des autres salles à mesurer.", budget=[("Cloisons", "Isolation acoustique boîte dans la boîte", 1, "m²", 260),
                    ("Menuiseries", "Porte acoustique", 1, "u", 2400)]),
    "art": dict(actuel="Salle de cours", futur="Atelier d'art (adultes et enfants)", ratio=5,
                futur_long="Atelier d'art en deux parties : évier avec bac de décantation, sol résine, éclairage 4000 K, rangements.",
                budget=[("Plomberie", "Évier et bac de décantation", 1, "forfait", 2200), ("Aménagements spécifiques", "Rangements", 6, "ml", 280)],
                sol=("résine", 55), lum="4000 K"),
    "popup": dict(actuel="Salles de cours", futur="Boutique éphémère (pop-up vêtements)", ratio=3, futur_long="Espace de vente éphémère : éclairage d'accent, cabine d'essayage, portants.",
                  budget=[("Aménagements spécifiques", "Cabine d'essayage et portants", 1, "forfait", 3500)], lum="d'accentuation"),
    "fetes": dict(actuel="Restaurant existant du bâtiment indépendant", futur="Salle des fêtes des étudiants (salle polyvalente)", ratio=1,
                  futur_long="Salle polyvalente avec scène mobile, bar et cuisine attenants, sanitaires dont PMR, rangement du mobilier.",
                  contraintes="Effectif ERP à calculer ; isolation acoustique vis-à-vis des riverains (émergence 5 dB(A) le jour, 3 la nuit).", pmr="Accessible de plain-pied (à vérifier)",
                  budget=[("Aménagements spécifiques", "Traitement acoustique", 1, "m²", 65), ("Équipements", "Sonorisation et éclairage scénique", 1, "forfait", 9000),
                          ("Mobilier", "Tables et chaises empilables", 1, "forfait", 12000)], lum="gradables"),
    "bar": dict(actuel="Self du restaurant", futur="Bar de la salle des fêtes", futur_long="Bar ouvert sur la salle : comptoir maçonné, arrière-bar réfrigéré, évier.",
                budget=[("Aménagements spécifiques", "Comptoir et arrière-bar", 1, "forfait", 9500), ("Plomberie", "Évier et alimentation", 1, "forfait", 1500)], sol=("carrelage", 75)),
    "cuisine": dict(actuel="Cuisine", futur="Cuisine", futur_long="Cuisine sur les réseaux existants : plans de travail inox, plonge, cuisson sous hotte, marche en avant (R2.1).",
                    contraintes="Rejet d'extraction à 8 m des fenêtres ; séparateur à graisses (R2.2).",
                    budget=[("Équipements", "Équipement de cuisine (inox, plonge, cuisson)", 1, "forfait", 38000), ("Chauffage et ventilation", "Hotte et extraction", 1, "forfait", 14000),
                            ("Plomberie", "Séparateur à graisses (quote-part)", 1, "forfait", 6500)], sol=("carrelage antidérapant", 75)),
    "restaurant": dict(actuel="Salle de restauration / cafétéria", futur="Salle de restaurant", ratio=1.4,
                       futur_long="Salle de restaurant : traitement acoustique, éclairage, mobilier ; liaison couverte avec la cuisine si elle reste dans un autre bâtiment (R2.1).",
                       budget=[("Aménagements spécifiques", "Traitement acoustique", 1, "m²", 55), ("Mobilier", "Mobilier de salle", 1, "m²", 120)], lum="décoratifs"),
    "terrasse": dict(actuel="Terrasse sur le RDC bas", futur="Terrasse du restaurant", ratio=1.4,
                     futur_long="Terrasse du restaurant après vérification prioritaire de la structure (5 kN/m² requis, planche D3.1) ; étanchéité et dallage sur plots.",
                     contraintes="Charge de calcul inconnue : vérification obligatoire avant toute utilisation.",
                     budget=[("Gros œuvre", "Vérification structure (sondages, note de calcul)", 1, "forfait", 4500), ("Gros œuvre", "Étanchéité et dallage sur plots", 1, "m²", 160)],
                     finitions=False),
    "wc": dict(actuel="Sanitaires", futur="Sanitaires rénovés (dont PMR)", futur_long="Sanitaires refaits : WC suspendus, lavabos, un cabinet PMR, carrelage, ventilation.",
               budget=[("Plomberie", "WC suspendu et lavabo par poste", 0.35, "m²", 1400), ("Chauffage et ventilation", "Extraction", 1, "forfait", 900)],
               sol=("carrelage", 75), pmr="Cabinet PMR à créer ou vérifier"),
    "vestiaire": dict(actuel="Vestiaire", futur="Vestiaires et douches", futur_long="Vestiaires avec douches collectives, bancs, casiers, sol antidérapant.",
                      budget=[("Plomberie", "Douches collectives", 4, "u", 1600), ("Mobilier", "Casiers et bancs", 1, "forfait", 3200)], sol=("carrelage antidérapant", 75)),
    "stockage": dict(actuel="Local de stockage", futur="Stockage", futur_long="Espace de stockage : rayonnages, éclairage à détection, sol peint.",
                     budget=[("Aménagements spécifiques", "Rayonnages", 0.8, "m²", 120)], sol=("peinture de sol", 22), pmr="Sans objet"),
    "poubelles": dict(actuel="Local poubelles", futur="Local déchets (tri)", futur_long="Local de tri ventilé, sol et murs lessivables, point d'eau, siphon.",
                      budget=[("Plomberie", "Point d'eau et siphon de sol", 1, "forfait", 1200)], sol=("carrelage", 75)),
    "hall": dict(actuel="Hall / accueil", futur="Accueil et exposition", ratio=2,
                 futur_long="Accueil des publics : banque d'accueil accessible, signalétique, éclairage ; séparation nette avec l'espace résidents par la double porte à badge.",
                 budget=[("Aménagements spécifiques", "Signalétique et banque d'accueil", 1, "forfait", 6500)], lum="d'accentuation", pmr="Accessible"),
    "exterieur": dict(actuel="Espace extérieur / vide", futur="Conservé", futur_long="Espace conservé ; entretien et sécurisation (garde-corps, verrière).",
                      budget=[("Aménagements spécifiques", "Entretien et mise en sécurité", 1, "forfait", 1500)], finitions=False),
    "circulation": dict(actuel="Circulation", futur="Circulation rénovée", futur_long="Revêtement de sol, peinture, éclairage LED à détection, signalétique, recoupement coupe-feu si nécessaire.",
                        budget=[("Menuiseries", "Portes de recoupement coupe-feu (si exigées)", 1, "u", 1900)], lum="à détection", pmr="Cheminement accessible à vérifier"),
    "autre": dict(actuel="Local", futur="Affectation à confirmer", futur_long="Affectation et travaux à définir après visite.",
                  budget=[("Aménagements spécifiques", "Visite et relevé", 1, "forfait", 300)], finitions=False),
    "securite": dict(actuel="Organe de sécurité", futur="Conservé et signalé", futur_long="Repérage, signalisation et accessibilité permanente.",
                     budget=[("Aménagements spécifiques", "Repérage et signalisation", 1, "forfait", 250)], finitions=False, pmr="Sans objet"),
    "batiment": dict(actuel="Bâtiment", futur="Voir les fiches des locaux", futur_long="Fiche de synthèse : les travaux sont détaillés local par local.",
                     budget=[], finitions=False),
    "sde": dict(actuel="Salle d'eau", futur="Salle d'eau", futur_long="Salle d'eau (douche, lavabo, WC).", budget=[], finitions=False),
}


def main():
    out = {}
    for l in D["locaux"]:
        out.setdefault(l["niveau"], {})[l["id"]] = fiche(l)
    dossier = RACINE / "data" / "fiches"
    dossier.mkdir(exist_ok=True)
    total = 0
    for niv, fiches in out.items():
        (dossier / f"{niv}.json").write_text(json.dumps(fiches, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        total += len(fiches)
    vides = [i for f in out.values() for i, x in f.items() if not x["budget"]["lignes"]]
    print(f"{total} fiches préremplies dans data/fiches/ ; sans ligne de budget : {len(vides)} {vides[:8]}")


if __name__ == "__main__":
    main()
