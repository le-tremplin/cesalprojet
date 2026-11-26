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
PX = 79.2            # pixels du scan par mètre
X0, Y0 = 250, 2720   # origine du repère (pixels du scan)

A_VERIFIER = [
    "Aile est (chambres 229 à 231 et local) : murs biais relevés à ±0,3 m.",
    "Dégagement de la façade ouest et accès à l'escalier sud-ouest : simplifiés.",
    "Cellules sanitaires préfabriquées et mobilier : non dessinés.",
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
salles += [("Chambre couple", (640, 1400), "201"), ("Chambre", (640, 1690), "202"),
]
# rangée nord (axes 2 à 8)
for a, b in zip(CLOISONS_NORD, CLOISONS_NORD[1:]):
    if a != 1004:
        mur([(a, Y_A), (a, Y_CN)], EP_REFEND if a in NOYAUX else EP_CLOISON, a in NOYAUX)
noms_nord = ["Chambre", "Chambre", "Chambre", "Chambre", "Chambre PMR", "Ascenseur, gaines, office"]
num = 203
for (a, b), nom in zip(zip(CLOISONS_NORD, CLOISONS_NORD[1:]), noms_nord):
    pres_a = b in NOYAUX or nom.startswith("Asc")
    larg = 0.90 if "PMR" in nom else 0.83
    d0 = (a - CLOISONS_NORD[0]) / PX + 0.15 if pres_a else (b - CLOISONS_NORD[0]) / PX - 0.15 - larg
    porte([(1004, Y_CN), (2486, Y_CN)], d0, larg=larg, ep=EP_REFEND, cote=1)
    if not nom.startswith("Asc"):
        fenetre([(X_1, Y_A), (2486, Y_A)], ((a + b) / 2 - X_1) / PX - 0.6)
    salles.append((nom, ((a + b) / 2, (Y_A + Y_CN) / 2), str(num) if nom.startswith("Ch") else None))
    if nom.startswith("Ch"):
        num += 1
# rangée sud (19 chambres)
for c in CLOISONS_SUD[1:-1]:
    mur([(c, Y_CS), (c, Y_S)], EP_REFEND if c in NOYAUX else EP_CLOISON, c in NOYAUX)
mur([(5690, Y_CS), (5690, Y_S)], EP_FACADE, True)
for a, b in zip(CLOISONS_SUD, CLOISONS_SUD[1:]):
    pres_a = b in NOYAUX
    d0 = (a - 1004) / PX + 0.15 if pres_a else (b - 1004) / PX - 0.98
    porte([(1004, Y_CS), (5690, Y_CS)], d0, ep=EP_REFEND, cote=-1)
    fenetre([(1004, Y_S), (5690, Y_S)], ((a + b) / 2 - 1004) / PX - 0.6)
    salles.append(("Chambre", ((a + b) / 2, (Y_CS + Y_S) / 2 + 40), str(num)))
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

# ------------------------------------------------------------------ jonction et aile est
mur([(5690, Y_CS), (5705, Y_CS)], EP_REFEND, True)
mur([(5705, 1945), (5795, 1945), (5795, 2250), (5705, 2250), (5705, 1945)], EP_CLOISON)   # gaines
salles.append(("Gaines", (5750, 2100), None))
mur([(5690, Y_S), (5705, Y_S), (5705, 2633)], EP_REFEND, True)
mur([(5608, 2267), (5608, 2633), (5933, 2633)], EP_REFEND, True)                     # V.O. + ascenseur
mur([(5608, 2267), (5800, 2267)], EP_REFEND, True)
mur([(5608, 2517), (5800, 2517)], EP_CLOISON)
mur([(5800, 2267), (5800, 2633)], EP_REFEND, True)
salles.append(("Vide-ordures", (5704, 2390), None))
salles.append(("Ascenseur", (5704, 2575), None))
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
salles += [("Chambre couple", (6090, 2000), "229"), ("Chambre", (6400, 1950), "230"),
           ("Chambre", (6660, 1920), "231")]
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
salles += [("Chambre", (7050, 1600), "232"), ("Chambre", (7050, 1840), "233"), ("Local", (6845, 2050), None)]

# ------------------------------------------------------------------ assemblage
def murs_polygones():
    geo = []
    for l, ep, _ in murs:
        geo.append(l.buffer(ep / 2, cap_style=2, join_style=2, mitre_limit=3))
    g = unary_union(geo).buffer(0.005).buffer(-0.005)
    return g.difference(unary_union(baies))


def ecrire(etage=2):
    # numérotation d'étude continue, d'ouest en est
    n = etage * 100 + 1
    for i, (nom, pt, numero) in enumerate(salles):
        if numero:
            salles[i] = (nom, pt, str(n))
            n += 1
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 6
    for nom, col in [("A-MURS", 7), ("A-MURS-HACHURES", 8), ("A-PORTES", 4), ("A-FENETRES", 5),
                     ("A-ESCALIERS", 7), ("A-SALLES-TEXTE", 7), ("A-SALLES-SURFACES", 9), ("A-CARTOUCHE", 7)]:
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
    # salles : surface calculée dans le vide entre les murs (baies refermées)
    plein = unary_union([l.buffer(ep / 2, cap_style=2, join_style=2) for l, ep, _ in murs])
    xs, ys = zip(*[c for l, _, _ in murs for c in l.coords])
    cadre = box(min(xs) - 2, min(ys) - 2, max(xs) + 2, max(ys) + 2)
    vide = cadre.difference(plein.buffer(0.45, join_style=2))
    cel = list(vide.geoms) if isinstance(vide, MultiPolygon) else [vide]
    total = 0
    for nom, (px, py), numero in salles:
        pt = Point(m(px, py))
        c = next((c for c in cel if c.contains(pt)), None)
        aire = c.buffer(0.45, join_style=2).difference(plein).area if c is not None else None
        texte = f"{nom} {numero}" if numero else nom
        if nom.startswith("Chambre") and numero:
            texte = ("Ch. couple " if "couple" in nom else "Ch. PMR " if "PMR" in nom else "Ch. ") + numero
            total += 1
        t = msp.add_text(texte, height=0.30 if len(texte) < 14 else 0.24, dxfattribs={"layer": "A-SALLES-TEXTE", "style": "Standard"})
        t.set_placement((pt.x, pt.y + 0.12), align=TextEntityAlignment.MIDDLE_CENTER)
        if aire and aire < 600:
            s = msp.add_text(f"{aire:.1f} m²".replace(".", ","), height=0.2, dxfattribs={"layer": "A-SALLES-SURFACES"})
            s.set_placement((pt.x, pt.y - 0.25), align=TextEntityAlignment.MIDDLE_CENTER)
    for i, t in enumerate(["ENSEMBLE D'ACCUEIL POUR ÉTUDIANTS — FOYER", f"ÉTAGE COURANT R+{etage} (R+2, R+3 et R+4 identiques)",
                           "Échelle 1/100 — unités : mètres",
                           "Redessiné d'après plan DOE Ex10a (1990) — 26/11/2026",
                           f"{total} chambres"]):
        msp.add_text(t, height=0.4, dxfattribs={"layer": "A-CARTOUCHE"}).set_placement((0, -2 - i * 0.6))
    out = RACINE / "plans" / "cad" / f"r{etage}.dxf"
    doc.saveas(out)
    print(f"{out.relative_to(RACINE)} : {len(polys)} murs, {len(portes)} portes, {len(fenetres)} fenêtres, "
          f"{len(salles)} salles dont {total} chambres")
    print("À vérifier :", *A_VERIFIER, sep="\n - ")


if __name__ == "__main__":
    ecrire(int(sys.argv[1]) if len(sys.argv) > 1 else 2)
