#!/usr/bin/env python3
"""Reconstruit en DAO le niveau -1 (parking) d'après le plan DOE Ex07c « Plan du sous-sol,
115 places de parkings » (scan, échelle 1/100). Le RDC bas, au même niveau, est volontairement
omis (seul son mur mitoyen est dessiné) pour mettre en avant le stationnement et les accès.

Sortie : plans/cad/sous-sol.dxf. Usage : python3 outils/sous_sol.py

Mesures en pixels du scan rendu à 100 dpi (39,37 px = 1 m) : trame des places 95,3 px = 2,42 m,
trame des poteaux 287 px = 7,29 m (3 places), vérifiées sur le plan.
"""
import math
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import LineString, Point, Polygon, box, MultiPolygon
from shapely.ops import unary_union

RACINE = Path(__file__).resolve().parent.parent
PX = 39.37
X0, Y0 = 1000, 3200
PAS = 95.3          # largeur d'une place

A_VERIFIER = [
    "DOE : 115 places. Places redessinées : voir le cartouche ; les places de la zone entre les deux rampes "
    "d'accès et d'une partie du secteur nord ne sont pas lisibles sur le scan et n'ont pas été dessinées.",
    "Gaines VB/VH : surfaces lues sur le plan ; contours approximatifs quand la gaine n'est dessinée qu'en pointillé.",
    "Places PMR : 3 symboles sur le DOE, emplacements exacts à confirmer.",
    "Niveaux : secteur nord à -2,20, secteur principal à -2,80 (cotes du DOE) ; pente de la rampe intérieure non cotée.",
]


def m(x, y):
    return ((x - X0) / PX, (Y0 - y) / PX)


murs, poteaux, places, rampes, gaines, textes, lignes, fleches, salles, escaliers = [], [], [], [], [], [], [], [], [], []


def mur(pts, ep=0.25):
    murs.append((LineString([m(*p) for p in pts]), ep))


def arc(cx, cy, r, a0, a1, n=24):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy - r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


# ------------------------------------------------------------------ enveloppe
mur([(1094, 1569), (1094, 475), (1912, 475), (2287, 612), (2406, 612), (2406, 925), (2356, 925), (2356, 1929)], 0.30)  # secteur nord
mur([(1094, 1569), (1231, 1581), (1249, 1603)], 0.30)
mur([(1249, 1603), (2727, 3102)], 0.30)                    # mur mitoyen du RDC bas (omis)
mur([(2727, 3102), (4500, 3075), (4500, 2525), (5225, 2517), (5083, 1708)], 0.30)
ext = arc(4500, 2117, 333, 180, 90)                         # rampe hélicoïdale : rive extérieure
a0 = 180 - math.degrees(math.asin((2117 - 1931) / 333))     # l'arc rejoint le mur nord (y = 1931)
mur([(2356, 1931)] + arc(4500, 2117, 333, a0, 90) + [(5083, 1708)], 0.30)
inn = arc(4500, 2117, 167, 180, 90)
mur([(4333, 2117)] + inn + [(5100, 1875)], 0.18)            # rive intérieure (muret)
mur([(4833, 2380), (5183, 2325)], 0.18)                     # rampe d'entrée : muret nord
# voiles intérieurs relevés
for x, y0, y1 in [(3542, 2442, 2633), (3733, 2525, 2633), (3925, 2525, 2633)]:
    mur([(x, y0), (x, y1)], 0.20)

# ------------------------------------------------------------------ noyau central, escaliers, locaux
mur([(2068, 1841), (2368, 1841), (2368, 2118), (2068, 2118), (2068, 1841)], 0.20)
mur([(2190, 1960), (2190, 2118)], 0.12)
mur([(2290, 1900), (2290, 2118)], 0.12)
mur([(2068, 1960), (2290, 1960)], 0.12)
salles += [("Sas ouest", (2129, 2040)), ("Sas est", (2240, 2040))]
gaines.append(("A-ASCENSEURS", "Ascenseur", [(2072, 1882), (2156, 1882), (2156, 1956), (2072, 1956)], "C"))
escaliers.append(("Escalier central", 2296, 1905, 2364, 2112, "v"))
escaliers.append(("Escalier de secours ouest (sortie à -1,00)", 2615, 2782, 2685, 2970, "v"))
mur([(2610, 2777), (2690, 2777), (2690, 2975), (2610, 2975), (2610, 2777)], 0.15)
escaliers.append(("Escalier de secours est", 4397, 2855, 4488, 3055, "v"))
mur([(4392, 2850), (4492, 2850), (4492, 3060)], 0.15)
mur([(4317, 2975), (4392, 2975), (4392, 3060)], 0.12)
salles.append(("Local poubelles", (4352, 3020)))
escaliers.append(("Escalier nord-est", 2310, 730, 2400, 920, "v"))

# ------------------------------------------------------------------ gaines de ventilation (surfaces lues sur le DOE)
gaines += [
    ("A-GAINES", "VH 2,9 m² air frais", [(2283, 612), (2350, 612), (2350, 679), (2283, 679)], "H"),
    ("A-GAINES", "VB 1,3 m²", [(1231, 1583), (1300, 1583), (1300, 1640)], "H"),
    ("A-GAINES", "VB (hachurée)", [(1437, 1583), (1537, 1583), (1537, 1675), (1437, 1675)], "H"),
    ("A-GAINES", "VB 3,2 m²", [(2360, 1837), (2420, 1837), (2500, 1925), (2360, 1925)], "C"),
    ("A-GAINES", "VB 1,8 m²", [(4180, 2055), (4312, 2055), (4312, 2120), (4180, 2120)], "H"),
    ("A-GAINES", "VH 4,6 m²", [(3142, 3008), (3242, 3008), (3242, 3070), (3142, 3070)], "C"),
    ("A-GAINES", "VB 1,2 m²", [(4900, 2560), (5110, 2560), (5110, 2600), (4900, 2600)], "H"),
]

# ------------------------------------------------------------------ poteaux
for x in (1266, 1562):
    poteaux += [(x, y, "h") for y in (609, 797, 987, 1177, 1366)]
poteaux += [(1737, y, "h") for y in (609, 797, 987, 1177, 1366, 1556)]
poteaux += [(1894, y, "h") for y in (609, 894, 1177, 1462, 1650)]
poteaux += [(2181, y, "h") for y in (837, 1029, 1312, 1596)]
for x in (2544, 2830, 3117, 3404, 3690, 3976):
    poteaux += [(x, 2112, "v"), (x, 2417, "v")]
poteaux += [(3258, 2608, "v"), (4117, 2567, "v"), (4405, 2567, "v")]
poteaux += [(x, 2887, "v") for x in (3258, 3547, 3833, 4117)]

# ------------------------------------------------------------------ rampes
def bande(p_out, p_in, n_traits, nom, sens):
    rampes.append((nom, p_out + p_in[::-1], sens))
    for k in range(n_traits + 1):
        t = k / n_traits
        i = min(int(t * (len(p_out) - 1)), len(p_out) - 2)
        f = t * (len(p_out) - 1) - i
        a = (p_out[i][0] + (p_out[i + 1][0] - p_out[i][0]) * f, p_out[i][1] + (p_out[i + 1][1] - p_out[i][1]) * f)
        b = (p_in[i][0] + (p_in[i + 1][0] - p_in[i][0]) * f, p_in[i][1] + (p_in[i + 1][1] - p_in[i][1]) * f)
        lignes.append([a, b])


ext2 = arc(4500, 2117, 333, 180, 90, 12) + [(5083, 1708)]
inn2 = arc(4500, 2117, 167, 180, 90, 12) + [(5100, 1875)]
bande(ext2, inn2, 30, "Rampe de sortie (vers la rue, ±0,00)", "sortie")
bande([(4833, 2380), (5183, 2325)], [(4850, 2512), (5208, 2470)], 12, "Rampe d'entrée (depuis la rue)", "entree")
bande([(1838, 1982), (2215, 2353)], [(1750, 2088), (2109, 2453)], 14, "Rampe intérieure -2,80 / -2,20", "interieure")

# ------------------------------------------------------------------ places (rangées relevées, pas de 2,42 m)
def rangee(code, x0, y0, prof, n, orient, pmr=()):
    """orient 'v' : places côte à côte selon x, profondeur selon y ; 'h' : l'inverse."""
    for k in range(n):
        if orient == "v":
            r = [(x0 + k * PAS, y0), (x0 + (k + 1) * PAS, y0), (x0 + (k + 1) * PAS, y0 + prof), (x0 + k * PAS, y0 + prof)]
        else:
            r = [(x0, y0 + k * PAS), (x0 + prof, y0 + k * PAS), (x0 + prof, y0 + (k + 1) * PAS), (x0, y0 + (k + 1) * PAS)]
        places.append((code, k + 1, r, k in pmr))


rangee("N-A", 1100, 609, 197, 10, "h")
rangee("N-B", 1531, 610, 204, 7, "h")
rangee("N-C", 1737, 610, 188, 10, "h")
rangee("N-D", 2156, 744, 194, 9, "h")
rangee("P-A", 2450, 1935, 185, 18, "v")
rangee("P-B", 2545, 2442, 191, 19, "v", pmr=(0, 1))
rangee("P-C", 2700, 2863, 205, 16, "v", pmr=(15,))

salles += [("Parking (allées)", (3300, 2250)), ("Parking nord (allées)", (2000, 1100))]
textes += [("NIVEAU -2,20", (1650, 1500), 0.45), ("NIVEAU -2,80", (3600, 2750), 0.45),
           ("ENTRÉE", (5000, 2440), 0.40), ("SORTIE", (4980, 1800), 0.40), ("Sortie secours à -1,00", (2650, 2990), 0.22),
           ("Rez-de-chaussée bas (non représenté)", (1700, 2600), 0.35)]
fleches += [((5150, 2430), (4870, 2470)), ((4700, 1860), (5040, 1790)), ((2160, 2400), (1800, 2040))]


# ------------------------------------------------------------------ écriture DXF
def ecrire():
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 6
    for nom, col in [("A-MURS", 7), ("A-MURS-HACHURES", 8), ("A-POTEAUX", 7), ("A-ESCALIERS", 7), ("A-RAMPES", 3),
                     ("A-STATIONNEMENT", 5), ("A-GAINES", 1), ("A-ASCENSEURS", 3), ("A-ANNOTATIONS", 2),
                     ("A-SALLES-TEXTE", 7), ("A-SALLES-SURFACES", 9), ("A-CARTOUCHE", 7)]:
        doc.layers.add(nom, color=col)
    msp = doc.modelspace()
    W = unary_union([l.buffer(ep / 2, cap_style=2, join_style=2, mitre_limit=3) for l, ep in murs])
    for p in (W.geoms if isinstance(W, MultiPolygon) else [W]):
        msp.add_lwpolyline(list(p.exterior.coords)[:-1], close=True, dxfattribs={"layer": "A-MURS"})
        h = msp.add_hatch(color=8, dxfattribs={"layer": "A-MURS-HACHURES"})
        h.paths.add_polyline_path(list(p.exterior.coords)[:-1], is_closed=True, flags=1)
        for r in p.interiors:
            msp.add_lwpolyline(list(r.coords)[:-1], close=True, dxfattribs={"layer": "A-MURS"})
            h.paths.add_polyline_path(list(r.coords)[:-1], is_closed=True, flags=0)
    for x, y, o in poteaux:
        w, hgt = (0.30, 0.80) if o == "v" else (0.60, 0.30)
        cx, cy = m(x, y)
        r = [(cx - w / 2, cy - hgt / 2), (cx + w / 2, cy - hgt / 2), (cx + w / 2, cy + hgt / 2), (cx - w / 2, cy + hgt / 2)]
        msp.add_lwpolyline(r, close=True, dxfattribs={"layer": "A-POTEAUX"})
        h = msp.add_hatch(color=7, dxfattribs={"layer": "A-POTEAUX"})
        h.paths.add_polyline_path(r, is_closed=True)
    for nom, x0, y0, x1, y1, sens in escaliers:
        a, b = m(x0, y1), m(x1, y0)
        msp.add_lwpolyline([a, (b[0], a[1]), b, (a[0], b[1])], close=True, dxfattribs={"layer": "A-ESCALIERS"})
        n = max(6, int(abs(b[1] - a[1]) / 0.28))
        for k in range(1, n):
            y = a[1] + (b[1] - a[1]) * k / n
            msp.add_line((a[0], y), (b[0], y), dxfattribs={"layer": "A-ESCALIERS"})
        t = msp.add_text("Escalier", height=0.22, dxfattribs={"layer": "A-ESCALIERS"})
        t.set_placement(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), align=TextEntityAlignment.MIDDLE_CENTER)
        t.dxf.text = nom
    for nom, pts, sens in rampes:
        msp.add_lwpolyline([m(*p) for p in pts], close=True, dxfattribs={"layer": "A-RAMPES"})
        c = Polygon([m(*p) for p in pts]).representative_point()
        t = msp.add_text(nom, height=0.24, dxfattribs={"layer": "A-RAMPES"})
        t.set_placement((c.x, c.y), align=TextEntityAlignment.MIDDLE_CENTER)
    for a, b in lignes:
        msp.add_line(m(*a), m(*b), dxfattribs={"layer": "A-RAMPES"})
    for code, k, pts, pmr in places:
        q = [m(*p) for p in pts]
        msp.add_lwpolyline(q, close=True, dxfattribs={"layer": "A-STATIONNEMENT"})
        c = Polygon(q).centroid
        t = msp.add_text(f"{code}{k:02d}" + (" PMR" if pmr else ""), height=0.22, dxfattribs={"layer": "A-STATIONNEMENT"})
        t.set_placement((c.x, c.y), align=TextEntityAlignment.MIDDLE_CENTER)
    for calque, nom, pts, fia in gaines:
        q = [m(*p) for p in pts]
        msp.add_lwpolyline(q, close=True, dxfattribs={"layer": calque})
        if calque == "A-GAINES":
            h = msp.add_hatch(color=1, dxfattribs={"layer": calque})
            h.set_pattern_fill("ANSI31", scale=0.25)
            h.paths.add_polyline_path(q, is_closed=True)
        c = Polygon(q).representative_point()
        t = msp.add_text(nom, height=0.18, dxfattribs={"layer": calque})
        t.set_placement((c.x, c.y), align=TextEntityAlignment.MIDDLE_CENTER)
    for nom, (x, y) in salles:
        t = msp.add_text(nom, height=0.26, dxfattribs={"layer": "A-SALLES-TEXTE"})
        t.set_placement(m(x, y), align=TextEntityAlignment.MIDDLE_CENTER)
    for txt, (x, y), h in textes:
        t = msp.add_text(txt, height=h, dxfattribs={"layer": "A-ANNOTATIONS"})
        t.set_placement(m(x, y), align=TextEntityAlignment.MIDDLE_CENTER)
    for a, b in fleches:
        (ax, ay), (bx, by) = m(*a), m(*b)
        msp.add_line((ax, ay), (bx, by), dxfattribs={"layer": "A-ANNOTATIONS"})
        ang = math.atan2(by - ay, bx - ax)
        for s in (2.6, -2.6):
            msp.add_line((bx, by), (bx - 0.8 * math.cos(ang + s / 3), by - 0.8 * math.sin(ang + s / 3)), dxfattribs={"layer": "A-ANNOTATIONS"})
    nb = len(places)
    for i, t in enumerate(["ENSEMBLE D'ACCUEIL POUR ÉTUDIANTS — PARKING", "NIVEAU -1 : stationnement et accès véhicules",
                           "Échelle 1/100 — unités : mètres", "Redessiné d'après plan DOE Ex07c — 26/11/2026",
                           f"{nb} places dessinées (DOE : 115)"]):
        msp.add_text(t, height=0.4, dxfattribs={"layer": "A-CARTOUCHE"}).set_placement((0, -2 - i * 0.6))
    out = RACINE / "plans" / "cad" / "sous-sol.dxf"
    doc.saveas(out)
    print(f"{out.relative_to(RACINE)} : {nb} places ({sum(p[3] for p in places)} PMR), {len(poteaux)} poteaux, "
          f"{len(gaines)} gaines/ascenseurs, {len(rampes)} rampes, {len(escaliers)} escaliers")
    print("À vérifier :", *A_VERIFIER, sep="\n - ")


if __name__ == "__main__":
    ecrire()
