#!/usr/bin/env python3
"""Reconstruit en DAO un étage courant du foyer (R+2, identique aux R+3 et R+4)
à partir des cotes relevées sur le plan DOE Ex10a (scan 200 dpi, échelle 1/100).

Sortie : plans/cad/r2.dxf, avec les mêmes calques que les plans des RDC
(A-MURS, A-MURS-HACHURES, A-PORTES, A-FENETRES, A-ESCALIERS, A-SALLES-TEXTE,
A-SALLES-SURFACES, A-CARTOUCHE). Unité : mètre.

Méthode :
- les mesures sont en pixels du scan (200 dpi) ; 79,2 px = 1 m, vérifié sur les
  cotes 577, 426 et 310 du plan et sur la trame de 3,10 m entre axes ;
- chaque mur est un axe + une épaisseur ; les murs sont fusionnés, puis les baies
  (portes, fenêtres) y sont découpées ;
- les salles sont trouvées dans le vide entre les murs, leur surface est calculée.
Les éléments relevés de façon approximative sont listés dans A_VERIFIER.

Usage : python3 outils/foyer_etage.py [2|3|4]   (numéro d'étage, 2 par défaut)
"""
import math, sys
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import LineString, Point, Polygon, box, MultiPolygon
from shapely.ops import unary_union
from shapely import affinity

RACINE = Path(__file__).resolve().parent.parent
ETAGE = int(sys.argv[1]) if len(sys.argv) > 1 else 2
LOGEMENTS = ETAGE in (2, 3)   # R+2 et R+3 : chambres réunies en logements ; R+1 et R+4 : structure conservée
PX = 79.2            # pixels du scan par mètre
X0, Y0 = 250, 2720   # origine du repère (pixels du scan)

A_VERIFIER = [
    "Aile est (chambres 229 à 231 et local) : murs biais relevés à ±0,3 m.",
    "Dégagement de la façade ouest et accès à l'escalier sud-ouest : simplifiés.",
    "Aménagements intérieurs : proposition architecturale, non validée techniquement (réseaux à relever).",
    "Chambres de l'aile est (murs biais) : aménagement dessiné dans un repère approché, à ajuster sur relevé.",
    "Partie est de la barre (axes 10 à 23) : le DOE ne dessine aucune gaine hachurée ; aucune n'a été ajoutée.",
    "R+1 : les refends entre chambres sont sur la trame porteuse ; la baie de réunion (≈ 2,4 m) est à valider par un BET.",
    "Numérotation des chambres : numérotation d'étude, absente du DOE.",
]


def m(x, y):
    """pixels du scan → mètres (y vers le haut)."""
    return ((x - X0) / PX, (Y0 - y) / PX)


# ------------------------------------------------------------------ relevés (pixels du scan)
Y_A = 1231          # façade nord, partie ouest (axe A)
Y_B = 1567          # cloison entre les deux chambres ouest (axe B)
Y_CN = 1685         # mur nord du couloir (= façade nord à l'est de l'escalier central)
Y_CS = 1810         # mur sud du couloir (axe C)
Y_S = 2260          # façade sud
X_1 = 414           # façade ouest (axe 1)
X_DEG = 877         # mur du dégagement ouest
CLOISONS_SUD = [1004, 1253, 1498, 1744, 1989, 2234, 2486, 2738, 2982, 3227, 3474, 3718, 3964,
                4210, 4455, 4699, 4953, 5204, 5448, 5690]
NOYAUX = {1253, 1744, 2234, 2738, 3227, 3718, 4210, 4699, 5204}   # cloisons avec cellules sanitaires en miroir
CLOISONS_NORD = [1004, 1253, 1498, 1744, 1989, 2234, 2486]

EP_FACADE, EP_REFEND, EP_CLOISON = 0.30, 0.20, 0.15

murs = []       # (LineString en mètres, épaisseur, porteur)
baies = []      # polygones à découper dans les murs
portes = []     # (charnière, direction du vantail, sens d'ouverture, largeur)
fenetres = []   # (point a, point b, épaisseur)
escaliers = []  # lignes
salles = []     # (nom, point en pixels, id d'étude)
boites = []     # gaines et ascenseurs : (calque, nom, x0, y0, x1, y1, fiabilité) en pixels
equip = []      # mobilier / équipements dessinés (polylignes en pixels)
# gaines techniques relevées sur le DOE Ex10a (carrés hachurés et blocs « GAINES »)
GAINES = [(1022, 1815, 1060, 1865), (2005, 1812, 2042, 1867), (1505, 1617, 1547, 1677),
          (2401, 1495, 2484, 1680), (5707, 1950, 5795, 2190)]
for i, (x0, y0, x1, y1) in enumerate(GAINES, 1):
    boites.append(("A-GAINES", f"Gaine G{i}", x0, y0, x1, y1, "C"))
# Gaines techniques des noyaux sanitaires (rangée sud), relevées par le groupe sur le plan de l'étage 1
# (annotations bleues) : une par noyau, sur son axe, de 0,55 m à 2,10 m du mur du couloir. Présentes aux 4 niveaux.
for i, xn in enumerate([1253, 1744, 2234, 2738, 3227, 3718, 4210, 4699, 5204], 1):
    boites.append(("A-GAINES", f"Gaine S{i}", xn - 16, Y_CS + 0.55 * PX, xn + 16, Y_CS + 2.10 * PX, "C"))
boites.append(("A-ASCENSEURS", "Ascenseur nord", 2305, 1241, 2476, 1354, "C"))
boites.append(("A-ASCENSEURS", "Ascenseur est", 5620, 2530, 5788, 2620, "C"))
boites.append(("A-GAINES", "Vide-ordures", 5620, 2280, 5788, 2505, "C"))
# Paires réunies (R+2, R+3) : cloison du milieu = cloison « gaine » (non porteuse de cellules), entre deux noyaux
PAIRES_SUD = [1498, 1989, 2486, 2982, 3474, 3964, 4455, 4953, 5448]
PAIRES_NORD = [1498]
legers = []     # cloisons d'aménagement (dessinées, mais exclues du contour des unités)
unites = []     # (nom affiché, numéro, point pixels) : chaque chambre / logement = une zone cliquable
PORTE_DEPUIS_CLOISON = 0.70   # m : la porte laisse la place au placard technique (gaine) contre la cloison, comme sur le DOE


def mur_leger(pts, ep=0.08):
    legers.append((LineString([m(*p) for p in pts]), ep))


def amenager(O, U, V, W, D, lit=0.90, pmr=False, cuisine=True):
    """Aménagement d'une chambre dans un repère local (mètres) :
    O = coin (côté cloison « gaine », côté couloir) en pixels ; U = vecteur unité (pixels / m) vers le noyau sanitaire ;
    V = vecteur unité vers la façade ; W = largeur utile, D = profondeur utile.
    Kitchenette contre la gaine, salle d'eau contre le noyau (réseaux existants), penderie, lit, bureau."""
    P = lambda u, v: (O[0] + u * U[0] + v * V[0], O[1] + u * U[1] + v * V[1])
    rect = lambda u0, v0, u1, v1: [P(u0, v0), P(u1, v0), P(u1, v1), P(u0, v1), P(u0, v0)]
    # Organisation du DOE conservée : contre le noyau sanitaire (gaine technique sur son axe, relevé du groupe),
    # la kitchenette côté couloir puis la salle d'eau ; côté opposé : penderie, puis lit près de la fenêtre.
    ls = 2.05 if pmr else 1.30           # largeur de la salle d'eau
    k1 = 1.75                            # fin de la kitchenette (depuis le couloir)
    v0, v1 = k1 + 0.08, k1 + 0.08 + (2.40 if pmr else 2.20)
    u0 = W - ls
    mur_leger([P(W, v0), P(u0, v0), P(u0, v1), P(W, v1)])
    porte([P(u0, v0), P(u0, v1)], 0.20, larg=0.90 if pmr else 0.73, ep=0.08, cote=-1)
    equip.append(rect(W - 0.90, v1 - 0.95, W - 0.05, v1 - 0.05))                      # douche
    equip.append([P(W - 0.90, v1 - 0.95), P(W - 0.05, v1 - 0.05)])
    equip.append(rect(W - 0.50, v0 + 0.05, W - 0.05, v0 + 0.55))                      # lavabo
    equip.append(rect(W - 0.45, v0 + 0.75, W - 0.05, v0 + 1.35))                      # WC
    if cuisine:                                                                         # kitchenette adossée au noyau
        equip.append(rect(W - 0.62, 0.10, W, k1))
        equip.append(rect(W - 0.52, 0.20, W - 0.12, 0.65))                            # évier (côté gaine)
        for dv in (1.05, 1.40):
            c = P(W - 0.31, dv)
            equip.append([(c[0] + 0.11 * PX * math.cos(t * math.pi / 6), c[1] + 0.11 * PX * math.sin(t * math.pi / 6)) for t in range(13)])
    if pmr:
        a = [P(u0 / 2 + 0.10 + 0.75 * math.cos(t * math.pi / 12), 2.30 + 0.75 * math.sin(t * math.pi / 12)) for t in range(25)]
        equip.append(a)                                                                 # aire de rotation Ø 1,50
    v_pend = 1.05                                                                       # après le débattement de la porte
    equip.append(rect(0.0, v_pend, 0.60, v_pend + 1.00))                                # penderie
    equip.append([P(0.0, v_pend), P(0.60, v_pend + 1.00)])
    equip.append(rect(0.0, D - 1.95, lit, D - 0.05))                                    # lit
    equip.append(rect(0.05, D - 0.50, lit - 0.05, D - 0.10))                           # oreiller
    if D - v1 > 1.35:
        equip.append(rect(W - 0.60, D - 1.25, W, D - 0.10))                             # bureau


def baie_x(x0, x1, y_c, y_f, sg):
    """Repère d'une baie de la barre : renvoie (O, U, V, W, D) depuis la cloison « gaine »."""
    return x0, x1


def repere_baie(a, b, y_c, y_f):
    """a, b : cloisons (pixels) ; le côté « gaine » est la cloison qui n'est pas un noyau sanitaire."""
    sg = 1 if y_f > y_c else -1
    xn, xk = (a, b) if b in NOYAUX else (b, a)
    d = 1 if xk > xn else -1
    O = (xn + d * 0.10 * PX, y_c + sg * 0.10 * PX)
    U, V = (d * PX, 0.0), (0.0, sg * PX)
    W = abs(xk - xn) / PX - 0.20
    D = abs(y_f - y_c) / PX - 0.25
    return O, U, V, W, D, xn, sg


def logement(a, mid, c, y_c, y_f):
    """Réunit les baies [a, mid] et [mid, c] (mid = cloison « gaine ») : baie de 2,4 m dans le refend,
    une seule porte (côté c), kitchenette contre la gaine, salle d'eau contre le noyau a, chambre côté a,
    séjour côté c. y_c = mur du couloir, y_f = façade (pixels)."""
    sg = 1 if y_f > y_c else -1
    mur([(mid, y_c), (mid, y_c + sg * 2.70 * PX)], EP_REFEND, True)     # refend conservé (gaine, porte)
    mur([(mid, y_f - sg * 0.55 * PX), (mid, y_f)], EP_REFEND, True)
    d = 1 if a < mid else -1
    # côté a : salle d'eau contre le noyau a, lit 140 près de la façade, penderie
    Oa = (a + d * 0.10 * PX, y_c + sg * 0.10 * PX)
    Pa = lambda u, v: (Oa[0] + d * u * PX, Oa[1] + sg * v * PX)
    ra = lambda u0, v0, u1, v1: [Pa(u0, v0), Pa(u1, v0), Pa(u1, v1), Pa(u0, v1), Pa(u0, v0)]
    mur_leger([Pa(2.00, 0.0), Pa(2.00, 2.40), Pa(0.0, 2.40)])
    porte([Pa(2.00, 2.40), Pa(2.00, 0.0)], 0.30, larg=0.80, ep=0.08, cote=1)
    equip.extend([ra(0.05, 0.05, 0.95, 0.95), [Pa(0.05, 0.05), Pa(0.95, 0.95)], ra(1.40, 0.05, 1.95, 0.50), ra(0.05, 1.55, 0.45, 2.15)])
    D = abs(y_f - y_c) / PX - 0.25
    equip.extend([ra(0.05, D - 2.00, 1.45, D - 0.10), ra(0.10, D - 0.50, 1.40, D - 0.15), ra(2.25, 2.60, 2.85, 3.60)])
    # côté c : kitchenette adossée au noyau c (gaine sur son axe), table et canapé côté refend
    Oc = (mid - d * 0.10 * PX, y_c + sg * 0.10 * PX)
    Pc = lambda u, v: (Oc[0] - d * u * PX, Oc[1] + sg * v * PX)
    rc = lambda u0, v0, u1, v1: [Pc(u0, v0), Pc(u1, v0), Pc(u1, v1), Pc(u0, v1), Pc(u0, v0)]
    Ok = (c - d * 0.10 * PX, y_c + sg * 0.10 * PX)
    Pk = lambda u, v: (Ok[0] - d * u * PX, Ok[1] + sg * v * PX)
    rk = lambda u0, v0, u1, v1: [Pk(u0, v0), Pk(u1, v0), Pk(u1, v1), Pk(u0, v1), Pk(u0, v0)]
    equip.extend([rk(0.0, 0.10, 0.62, 2.40), rk(0.10, 0.20, 0.50, 0.65)])
    for dv in (1.15, 1.50):
        cc = Pk(0.31, dv)
        equip.append([(cc[0] + 0.11 * PX * math.cos(t * math.pi / 6), cc[1] + 0.11 * PX * math.sin(t * math.pi / 6)) for t in range(13)])
    equip.extend([rk(1.20, 2.80, 2.00, 3.60), rc(0.10, D - 2.40, 0.95, D - 0.40)])   # table, canapé
    return ((a + c) / 2, y_c + sg * 3.4 * PX)


def mur(pts, ep, porteur=False):
    murs.append((LineString([m(*p) for p in pts]), ep, porteur))


def baie_sur(p1, p2, d0, larg, ep):
    """Découpe une baie le long du segment p1→p2 (pixels), à d0 m de p1, largeur larg (m)."""
    a, b = Point(m(*p1)), Point(m(*p2))
    L = a.distance(b)
    ux, uy = (b.x - a.x) / L, (b.y - a.y) / L
    s = (a.x + ux * d0, a.y + uy * d0)
    e = (a.x + ux * (d0 + larg), a.y + uy * (d0 + larg))
    nx, ny = -uy, ux
    k = ep / 2 + 0.02
    baies.append(Polygon([(s[0] + nx * k, s[1] + ny * k), (e[0] + nx * k, e[1] + ny * k),
                          (e[0] - nx * k, e[1] - ny * k), (s[0] - nx * k, s[1] - ny * k)]))
    return s, e, (ux, uy), (nx, ny)


def porte(seg, d0, larg=0.83, ep=EP_CLOISON, cote=1, charniere="debut"):
    s, e, u, n = baie_sur(seg[0], seg[-1], d0, larg, ep)
    h = s if charniere == "debut" else e
    autre = e if charniere == "debut" else s
    portes.append((h, autre, (n[0] * cote, n[1] * cote), larg))


def fenetre(seg, d0, larg=1.20, ep=EP_FACADE):
    s, e, u, n = baie_sur(seg[0], seg[-1], d0, larg, ep)
    fenetres.append((s, e, n, ep))


def tour_escalier(x0, y0, x1, y1, cote_arrondi, nb_marches=9):
    """Cage d'escalier rectangulaire fermée par un demi-cercle (relevé DOE)."""
    if cote_arrondi in ("est", "ouest"):
        r = (y1 - y0) / 2
        cx = x1 if cote_arrondi == "est" else x0
        cy = (y0 + y1) / 2
        arc = [(cx + (1 if cote_arrondi == "est" else -1) * r * math.sin(t * math.pi / 16),
                cy - r * math.cos(t * math.pi / 16)) for t in range(17)]
        if cote_arrondi == "est":
            mur([(x0, y0), (x1, y0)] + arc[1:-1] + [(x1, y1), (x0, y1)], EP_REFEND, True)
        else:
            mur([(x1, y0), (x0, y0)] + arc[1:-1] + [(x0, y1), (x1, y1)], EP_REFEND, True)
        # deux volées de marches de part et d'autre d'un mur d'échiffre
        ym = (y0 + y1) / 2
        xa, xb = (x0 + 10, x1 - 10)
        for k in range(nb_marches + 1):
            x = xa + (xb - xa) * k / nb_marches
            escaliers.append(LineString([m(x, y0 + 8), m(x, ym - 6)]))
            escaliers.append(LineString([m(x, ym + 6), m(x, y1 - 8)]))
        escaliers.append(LineString([m(xa, ym), m(xb, ym)]))
        return r


# ------------------------------------------------------------------ barre principale
# façades et couloir
mur([(X_1, Y_A), (2486, Y_A)], EP_FACADE, True)                       # façade nord ouest
mur([(X_1, Y_A), (X_1, Y_CS)], EP_FACADE + 0.02, True)                # pignon ouest
mur([(X_1, Y_CS), (1004, Y_CS)], EP_FACADE, True)                     # façade sud du bloc ouest
mur([(1004, Y_S), (5690, Y_S)], EP_FACADE, True)                      # façade sud
mur([(1004, Y_CS), (1004, Y_S)], EP_FACADE, True)                     # retour façade sud ouest
mur([(2640, Y_CN), (5695, Y_CN)], EP_FACADE, True)                    # façade nord du couloir
mur([(1004, Y_CN), (2486, Y_CN)], EP_REFEND, True)                    # mur nord du couloir (côté chambres)
mur([(1004, Y_CS), (5690, Y_CS)], EP_REFEND, True)                    # mur sud du couloir
mur([(2486, Y_A), (2486, Y_CN)], EP_REFEND, True)                     # refend axe 8
# bloc ouest (2 chambres + dégagement)
mur([(X_1, Y_B), (X_DEG, Y_B)], EP_REFEND, True)
mur([(X_DEG, 1436), (X_DEG, Y_CS)], EP_CLOISON)
mur([(X_DEG, 1436), (1004, 1436)], EP_CLOISON)
mur([(1004, Y_A), (1004, Y_CN)], EP_REFEND, True)
porte([(X_DEG, 1436), (X_DEG, Y_CS)], 0.25, cote=-1)                  # chambre couple
porte([(X_DEG, 1436), (X_DEG, Y_CS)], 3.30, cote=-1)                  # chambre ouest sud
amenager((X_DEG - 6, Y_B - 8), (0.0, -PX), (-PX, 0.0), (Y_B - Y_A) / PX - 0.25, (X_DEG - X_1) / PX - 0.25, lit=1.40)
amenager((X_DEG - 6, Y_CS - 8), (0.0, -PX), (-PX, 0.0), (Y_CS - Y_B) / PX - 0.25, (X_DEG - X_1) / PX - 0.25)
unites += [("Chambre couple", "201", (640, 1400)), ("Chambre", "202", (640, 1690))]
# rangée nord (axes 2 à 8)
for a, b in zip(CLOISONS_NORD, CLOISONS_NORD[1:]):
    if a != 1004 and not (LOGEMENTS and a in PAIRES_NORD):
        mur([(a, Y_A), (a, Y_CN)], EP_REFEND if a in NOYAUX else EP_CLOISON, a in NOYAUX)
noms_nord = ["Chambre", "Chambre", "Chambre", "Chambre", "Chambre PMR", "Office"]
num = 203
for (a, b), nom in zip(zip(CLOISONS_NORD, CLOISONS_NORD[1:]), noms_nord):
    larg = 0.90 if "PMR" in nom else 0.83
    xn = a if b in NOYAUX else b
    d0 = (xn - 1004) / PX + (PORTE_DEPUIS_CLOISON if xn == a else -PORTE_DEPUIS_CLOISON - larg)
    if nom == "Office":
        d0 = (2234 - 1004) / PX + 0.15
    if not (LOGEMENTS and b in PAIRES_NORD):          # une seule porte par logement
        porte([(1004, Y_CN), (2486, Y_CN)], d0, larg=larg, ep=EP_REFEND, cote=1)
    if nom != "Office":
        fenetre([(X_1, Y_A), (2486, Y_A)], ((a + b) / 2 - X_1) / PX - 0.6)
    if LOGEMENTS and b in PAIRES_NORD:
        continue
    if LOGEMENTS and a in PAIRES_NORD:
        a0 = CLOISONS_NORD[CLOISONS_NORD.index(a) - 1]
        unites.append(("Logement", str(num), logement(a0, a, b, Y_CN, Y_A)))
        num += 1
        continue
    if nom.startswith("Ch"):
        O, U, V, W, D, _, _ = repere_baie(a, b, Y_CN, Y_A)
        amenager(O, U, V, W, D, pmr="PMR" in nom)
        unites.append((nom, str(num), ((a + b) / 2, (Y_A + Y_CN) / 2)))
        num += 1
    else:
        salles.append((nom, ((a + b) / 2, (Y_A + Y_CN) / 2 + 60), None))
# rangée sud (19 chambres)
for c in CLOISONS_SUD[1:-1]:
    if LOGEMENTS and c in PAIRES_SUD:
        continue
    mur([(c, Y_CS), (c, Y_S)], EP_REFEND if c in NOYAUX else EP_CLOISON, c in NOYAUX)
mur([(5690, Y_CS), (5690, Y_S)], EP_FACADE, True)
for a, b in zip(CLOISONS_SUD, CLOISONS_SUD[1:]):
    xn = a if b in NOYAUX else b
    d0 = (xn - 1004) / PX + (PORTE_DEPUIS_CLOISON if xn == a else -PORTE_DEPUIS_CLOISON - 0.83)
    fenetre([(1004, Y_S), (5690, Y_S)], ((a + b) / 2 - 1004) / PX - 0.6)
    if LOGEMENTS and b in PAIRES_SUD:            # une seule porte par logement
        continue
    porte([(1004, Y_CS), (5690, Y_CS)], d0, ep=EP_REFEND, cote=-1)
    if LOGEMENTS and a in PAIRES_SUD:
        a0 = CLOISONS_SUD[CLOISONS_SUD.index(a) - 1]
        unites.append(("Logement", str(num), logement(a0, a, b, Y_CS, Y_S)))
        num += 1
        continue
    O, U, V, W, D, _, _ = repere_baie(a, b, Y_CS, Y_S)
    amenager(O, U, V, W, D)
    unites.append(("Chambre", str(num), ((a + b) / 2, (Y_CS + Y_S) / 2 + 40)))
    num += 1
# fenêtres du couloir (façade nord, partie est)
for a, b in zip(CLOISONS_SUD[7:], CLOISONS_SUD[8:]):
    fenetre([(2640, Y_CN), (5695, Y_CN)], ((a + b) / 2 - 2640) / PX - 0.6, larg=0.80)
salles.append(("Couloir", (3600, (Y_CN + Y_CS) / 2), None))

# ------------------------------------------------------------------ escaliers
tour_escalier(2613, 1213, 2893, 1480, "est")                         # escalier central nord
mur([(2493, 1213), (2613, 1213)], EP_REFEND, True)
mur([(2493, 1480), (2493, Y_CN)], EP_REFEND, True)
mur([(2640, 1480), (2640, Y_CN)], EP_REFEND, True)
mur([(2486, Y_CN), (2640, Y_CN)], EP_REFEND, True)
porte([(2486, Y_CN), (2640, Y_CN)], 0.25, larg=1.40, ep=EP_REFEND, cote=1)           # porte du palier
salles.append(("Escalier", (2700, 1346), None))

tour_escalier(695, 2127, 877, 2409, "ouest")                         # escalier sud-ouest
mur([(X_DEG, Y_CS), (X_DEG, 2127)], EP_REFEND, True)
mur([(1004, Y_S), (1004, 2127)], EP_REFEND, True)
mur([(877, 2127), (1004, 2127)], EP_CLOISON)
porte([(877, 2127), (1004, 2127)], 0.20, larg=1.20, cote=-1)
salles.append(("Escalier", (790, 2268), None))
salles.append(("Dégagement escalier sud-ouest", (940, 1980), None))

# ------------------------------------------------------------------ jonction et aile est
mur([(5690, Y_CS), (5705, Y_CS)], EP_REFEND, True)
mur([(5705, 1945), (5795, 1945), (5795, 2250), (5705, 2250), (5705, 1945)], EP_CLOISON)   # gaines
mur([(5690, Y_S), (5705, Y_S), (5705, 2633)], EP_REFEND, True)
mur([(5608, 2267), (5608, 2633), (5933, 2633)], EP_REFEND, True)                     # V.O. + ascenseur
mur([(5608, 2267), (5800, 2267)], EP_REFEND, True)
mur([(5608, 2517), (5800, 2517)], EP_CLOISON)
mur([(5800, 2267), (5800, 2633)], EP_REFEND, True)

tour_escalier(5933, 2383, 6075, 2633, "est")                                          # escalier sud-est
mur([(5933, 2250), (5933, 2383)], EP_REFEND, True)
salles.append(("Escalier", (6010, 2508), None))
mur([(5800, 2250), (5933, 2250)], EP_CLOISON)
porte([(5800, 2250), (5933, 2250)], 0.10, larg=1.40, cote=-1)

# aile est (murs biais)
N1, N2 = (5695, Y_CN), (7250, 1462)          # façade nord de l'aile
R1, R2 = (5947, 1766), (6790, 1650)          # mur nord des chambres de l'aile
S = [(5947, 2234), (6300, 2162), (6553, 2132), (6895, 2134)]   # façade sud de l'aile
mur([N1, N2], EP_FACADE, True)
mur([R1, R2], EP_REFEND, True)
mur([(5942, 1766), (5947, 2234)], EP_REFEND, True)
mur(S, EP_FACADE, True)
P1, P2 = [(6232, 1729), (6300, 2162)], [(6500, 1692), (6553, 2132)]
mur(P1, EP_REFEND, True)
mur(P2, EP_CLOISON)
mur([(6790, 1650), (6800, 2134)], EP_REFEND, True)
porte([R1, R2], 0.25, ep=EP_REFEND, cote=-1)
porte([R1, R2], 4.60, ep=EP_REFEND, cote=-1)
porte([R1, R2], 8.10, ep=EP_REFEND, cote=-1)
fenetre(S[:2], 1.5)
fenetre(S[1:3], 1.0)
fenetre(S[2:4], 1.0)
def repere_biais(gauche, droite, y_couloir_g, prof):
    """Repère d'une chambre de l'aile (murs biais) : origine sur le mur de couloir, contre la cloison gauche."""
    (gx0, gy0), (gx1, gy1) = gauche
    ux, uy = R2[0] - R1[0], R2[1] - R1[1]
    n = math.hypot(ux, uy)
    U = (ux / n * PX, uy / n * PX)
    V = (-U[1], U[0]) if (-U[1]) * 0 + U[0] > 0 else (U[1], -U[0])
    V = (abs(V[0]) * (1 if V[0] >= 0 else -1), abs(V[1]))          # vers la façade sud
    t = (y_couloir_g - gy0) / (gy1 - gy0)
    O = (gx0 + (gx1 - gx0) * t + U[0] * 0.12, y_couloir_g + 0.12 * PX)
    W = (droite - O[0]) / PX - 0.15
    return O, U, V, W, prof


for (g, xd, yg, prof, lit, nom) in [([(5942, 1766), (5947, 2234)], 6250, 1770, 5.3, 1.40, "Chambre couple"),
                                     ([(6232, 1729), (6300, 2162)], 6510, 1735, 5.0, 0.90, "Chambre"),
                                     ([(6500, 1692), (6553, 2132)], 6785, 1700, 5.0, 0.90, "Chambre")]:
    O, U, V, W, D = repere_biais(g, xd, yg, prof)
    amenager(O, U, V, W, D, lit=lit)
unites += [("Chambre couple", "229", (6090, 2000)), ("Chambre", "230", (6400, 1950)), ("Chambre", "231", (6660, 1920))]
# bloc est : 2 chambres de part et d'autre d'un refend
E = [(6805, 1505), (7250, 1462), (7333, 1929), (6790, 1960)]
mur([E[1], E[2], E[3]], EP_FACADE, True)
mur([(6790, 1650), E[0]], EP_REFEND, True)
mur([(6790, 1960), (6895, 1955), (6895, 2134)], EP_CLOISON)
mur([(6798, 1750), (7300, 1696)], EP_REFEND, True)
porte([(6790, 1650), E[0]], 0.30, ep=EP_REFEND, cote=-1)
porte([(6798, 1750), (6790, 1960)], 0.60, ep=EP_REFEND, cote=1)
fenetre([E[1], E[2]], 1.0)
fenetre([E[1], E[2]], 3.5)
amenager((6812, 1742), (0.0, -PX), (PX, -0.09 * PX), (1742 - 1515) / PX - 0.15, (7240 - 6812) / PX - 0.3)
amenager((6806, 1762), (0.0, PX), (PX, -0.06 * PX), (1955 - 1762) / PX - 0.12, (7300 - 6806) / PX - 0.4)
unites += [("Chambre", "232", (7050, 1600)), ("Chambre", "233", (7050, 1840))]
salles.append(("Local", (6845, 2050), None))

# ------------------------------------------------------------------ assemblage
def murs_polygones():
    geo = []
    for l, ep, _ in murs:
        geo.append(l.buffer(ep / 2, cap_style=2, join_style=2, mitre_limit=3))
    for l, ep in legers:
        geo.append(l.buffer(ep / 2, cap_style=2, join_style=2, mitre_limit=3))
    g = unary_union(geo).buffer(0.005).buffer(-0.005)
    return g.difference(unary_union(baies))


def ecrire(etage=2):
    # numérotation d'étude continue, d'ouest en est
    n = etage * 100 + 1
    for i, (nom, numero, pt) in enumerate(unites):
        unites[i] = (nom, str(n), pt)
        n += 1
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 6
    for nom, col in [("A-MURS", 7), ("A-MURS-HACHURES", 8), ("A-PORTES", 4), ("A-FENETRES", 5),
                     ("A-ESCALIERS", 7), ("A-SALLES-TEXTE", 7), ("A-SALLES-SURFACES", 9), ("A-CARTOUCHE", 7),
                     ("A-GAINES", 1), ("A-ASCENSEURS", 3), ("A-EQUIPEMENTS", 8), ("A-LOGEMENTS", 6)]:
        doc.layers.add(nom, color=col)
    msp = doc.modelspace()
    W = murs_polygones()
    polys = list(W.geoms) if isinstance(W, MultiPolygon) else [W]
    porteurs = unary_union([l.buffer(ep / 2 + 0.01, cap_style=2) for l, ep, p in murs if p])
    for p in polys:
        for ring in [p.exterior, *p.interiors]:
            msp.add_lwpolyline(list(ring.coords)[:-1], close=True, dxfattribs={"layer": "A-MURS"})
        if p.intersection(porteurs).area > 0.5 * p.area:
            h = msp.add_hatch(color=8, dxfattribs={"layer": "A-MURS-HACHURES"})
            h.paths.add_polyline_path(list(p.exterior.coords)[:-1], is_closed=True, flags=1)
            for r in p.interiors:
                h.paths.add_polyline_path(list(r.coords)[:-1], is_closed=True, flags=0)
    for h, autre, n, larg in portes:
        bout = (h[0] + n[0] * larg, h[1] + n[1] * larg)
        msp.add_line(h, bout, dxfattribs={"layer": "A-PORTES"})
        a0 = math.degrees(math.atan2(autre[1] - h[1], autre[0] - h[0]))
        a1 = math.degrees(math.atan2(n[1], n[0]))
        d = (a1 - a0) % 360
        if d > 180:
            a0, a1 = a1, a0
        msp.add_arc(h, larg, a0, a1, dxfattribs={"layer": "A-PORTES"})
    for s, e, n, ep in fenetres:
        for k in (-ep / 2, -0.03, 0.03, ep / 2):
            msp.add_line((s[0] + n[0] * k, s[1] + n[1] * k), (e[0] + n[0] * k, e[1] + n[1] * k), dxfattribs={"layer": "A-FENETRES"})
    for l in escaliers:
        msp.add_line(*l.coords, dxfattribs={"layer": "A-ESCALIERS"})
    for pts in equip:
        msp.add_lwpolyline([m(*p) for p in pts], dxfattribs={"layer": "A-EQUIPEMENTS"})
    # gaines et ascenseurs : un contour fermé chacun, cliquable sur le site
    for calque, nom, x0, y0, x1, y1, fia in boites:
        a, b = m(x0, y1), m(x1, y0)
        rect = [a, (b[0], a[1]), b, (a[0], b[1])]
        msp.add_lwpolyline(rect, close=True, dxfattribs={"layer": calque})
        if calque == "A-GAINES":
            h = msp.add_hatch(color=1, dxfattribs={"layer": calque})
            h.set_pattern_fill("ANSI31", scale=0.25)
            h.paths.add_polyline_path(rect, is_closed=True)
        else:
            msp.add_line(rect[0], rect[2], dxfattribs={"layer": calque})
            msp.add_line(rect[1], rect[3], dxfattribs={"layer": calque})
        t = msp.add_text(nom.replace("Gaine ", "").replace("Ascenseur", "Asc.").replace("Vide-ordures", "V.O."),
                         height=0.16, dxfattribs={"layer": calque})
        t.set_placement(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), align=TextEntityAlignment.MIDDLE_CENTER)
    # salles : surface calculée dans le vide entre les murs (baies refermées)
    plein = unary_union([l.buffer(ep / 2, cap_style=2, join_style=2) for l, ep, _ in murs]
                        + [box(*m(x0, y1), *m(x1, y0)) for _, _, x0, y0, x1, y1, _ in boites])
    xs, ys = zip(*[c for l, _, _ in murs for c in l.coords])
    cadre = box(min(xs) - 2, min(ys) - 2, max(xs) + 2, max(ys) + 2)
    vide = cadre.difference(plein.buffer(0.45, join_style=2))
    cel = list(vide.geoms) if isinstance(vide, MultiPolygon) else [vide]
    total = 0
    # chambres et logements : UNE zone par unité (contour intérieur complet, salle d'eau comprise, gaines exclues)
    for nom, numero, (px, py) in unites:
        pt = Point(m(px, py))
        c = next((c for c in cel if c.contains(pt)), None)
        if c is None:
            print("  unité sans contour :", nom, numero)
            continue
        env = c.buffer(0.45, join_style=2).difference(plein)
        if isinstance(env, MultiPolygon):
            env = max(env.geoms, key=lambda q: q.area)
        env = env.simplify(0.02)
        msp.add_lwpolyline(list(env.exterior.coords)[:-1], close=True, dxfattribs={"layer": "A-LOGEMENTS"})
        texte = {"Logement": "Logement ", "Chambre couple": "Ch. couple ", "Chambre PMR": "Ch. PMR "}.get(nom, "Ch. ") + numero
        q = env.representative_point() if not env.contains(pt) else pt
        t = msp.add_text(texte, height=0.30, dxfattribs={"layer": "A-LOGEMENTS"})
        t.set_placement((q.x, q.y + 0.12), align=TextEntityAlignment.MIDDLE_CENTER)
        sfc = msp.add_text(f"{env.area:.1f} m²".replace(".", ","), height=0.2, dxfattribs={"layer": "A-SALLES-SURFACES"})
        sfc.set_placement((q.x, q.y - 0.25), align=TextEntityAlignment.MIDDLE_CENTER)
        total += 1
    for nom, (px, py), numero in salles:
        pt = Point(m(px, py))
        c = next((c for c in cel if c.contains(pt)), None)
        aire = c.buffer(0.45, join_style=2).difference(plein).area if c is not None else None
        t = msp.add_text(nom, height=0.30 if len(nom) < 14 else 0.24, dxfattribs={"layer": "A-SALLES-TEXTE", "style": "Standard"})
        t.set_placement((pt.x, pt.y + 0.12), align=TextEntityAlignment.MIDDLE_CENTER)
        if aire and aire < 600:
            s = msp.add_text(f"{aire:.1f} m²".replace(".", ","), height=0.2, dxfattribs={"layer": "A-SALLES-SURFACES"})
            s.set_placement((pt.x, pt.y - 0.25), align=TextEntityAlignment.MIDDLE_CENTER)
    for i, t in enumerate(["ENSEMBLE D'ACCUEIL POUR ÉTUDIANTS — FOYER", (f"R+{etage} — PROJET : chambres réunies en logements (baie dans le refend, à valider BET)" if LOGEMENTS
                            else f"R+{etage} — structure existante conservée, chambres aménagées"),
                           "Échelle 1/100 — unités : mètres",
                           "Redessiné d'après plan DOE Ex10a (1990) — 26/11/2026",
                           f"{total} chambres et logements"]):
        msp.add_text(t, height=0.4, dxfattribs={"layer": "A-CARTOUCHE"}).set_placement((0, -2 - i * 0.6))
    out = RACINE / "plans" / "cad" / f"r{etage}.dxf"
    doc.saveas(out)
    print(f"{out.relative_to(RACINE)} : {len(polys)} murs, {len(portes)} portes, {len(fenetres)} fenêtres, "
          f"{len(salles)} salles dont {total} chambres")
    print("À vérifier :", *A_VERIFIER, sep="\n - ")


if __name__ == "__main__":
    ecrire(ETAGE)
