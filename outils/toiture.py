#!/usr/bin/env python3
"""Plan de toiture du foyer d'après le plan DOE Ex12bis « Terrasse » (scan 200 dpi, 1/100).

Le plan de terrasse est recalé sur le repère de l'étage courant (outils/foyer_etage.py) :
x_étage = x_terrasse + 165 ; y_étage = y_terrasse - 360 - 0,0066 (x_terrasse - 249)
(translation lue sur l'axe 1 et la file A, rotation de 0,4° lue sur l'axe 23).
L'emprise de la toiture est celle des murs de l'étage courant : les deux plans restent cohérents.

Éléments repris du DOE : acrotère, chaufferie (ventilations haute et basse, porte « passage »),
machinerie d'ascenseur, édicules des trois escaliers, débouchés de gaines (V., trappe, vide-ordures),
joints de dilatation (axes 8/9 et 19/20), parcours VMC, passage VMC coupe-feu, rive des balcons.
Non représentés faute d'information sur le DOE : pentes, descentes d'eaux pluviales, nature de l'étanchéité.

Sortie : plans/cad/terrasse.dxf. Usage : python3 outils/toiture.py
"""
import math, sys, importlib.util
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import LineString, Polygon, box, MultiPolygon
from shapely.ops import unary_union, split

RACINE = Path(__file__).resolve().parent.parent
sys.argv = [sys.argv[0], "2"]
spec = importlib.util.spec_from_file_location("etage", RACINE / "outils" / "foyer_etage.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)          # géométrie de l'étage courant (sans écrire de fichier)
m, PX = E.m, E.PX


def T(x, y):
    """pixels du plan de terrasse → pixels de l'étage courant"""
    return (x + 165, y - 360 - 0.0066 * (x - 249))


def mt(x, y):
    return m(*T(x, y))


def ecrire():
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 6
    for nom, col in [("A-MURS", 7), ("A-MURS-HACHURES", 8), ("A-ACROTERE", 7), ("A-TOITURES", 8), ("A-ESCALIERS", 7),
                     ("A-GAINES", 1), ("A-ASCENSEURS", 3), ("A-TOITURE-DETAILS", 9), ("A-ANNOTATIONS", 2),
                     ("A-PORTES", 4), ("A-SALLES-TEXTE", 7), ("A-SALLES-SURFACES", 9), ("A-CARTOUCHE", 7)]:
        doc.layers.add(nom, color=col)
    msp = doc.modelspace()

    # ---- emprise : murs de l'étage courant, sans les baies
    plein = unary_union([l.buffer(ep / 2, cap_style=2, join_style=2, mitre_limit=3) for l, ep, _ in E.murs])
    # fermeture de 1,5 m : les trouées (paliers, jonctions) ne doivent pas ouvrir l'emprise sur l'extérieur
    ferme = plein.buffer(1.5, join_style=2, mitre_limit=5).buffer(-1.5, join_style=2, mitre_limit=5)
    parts = list(ferme.geoms) if isinstance(ferme, MultiPolygon) else [ferme]
    emprise = unary_union([Polygon(g.exterior.coords) for g in parts if g.area > 1]).buffer(0)
    acro = emprise.difference(emprise.buffer(-0.20, join_style=2))          # acrotère 20 cm
    for p in (acro.geoms if isinstance(acro, MultiPolygon) else [acro]):
        for r in [p.exterior, *p.interiors]:
            msp.add_lwpolyline(list(r.coords)[:-1], close=True, dxfattribs={"layer": "A-ACROTERE"})

    # ---- édicules (cages d'escalier) et chaufferie : murs pleins
    def cage(x0, y0, x1, y1, cote):
        r = (y1 - y0) / 2
        cx = x1 if cote == "est" else x0
        pts = [(cx + (1 if cote == "est" else -1) * r * math.sin(t * math.pi / 16), (y0 + y1) / 2 - r * math.cos(t * math.pi / 16)) for t in range(17)]
        ring = ([(x0, y0), (x1, y0)] + pts + [(x1, y1), (x0, y1)]) if cote == "est" else ([(x1, y0), (x0, y0)] + pts + [(x0, y1), (x1, y1)])
        return Polygon([m(*p) for p in ring]).buffer(0)

    cages = [("Édicule escalier sud-ouest (accès terrasse, main courante inox)", cage(695, 2127, 877, 2409, "ouest")),
             ("Édicule escalier nord (porte grillagée au 4e étage)", cage(2613, 1213, 2893, 1480, "est")),
             ("Édicule escalier sud-est", cage(5933, 2383, 6075, 2633, "est"))]
    chauf = Polygon([mt(1818, 1595), mt(2318, 1595), mt(2318, 2191), mt(1818, 2191)])
    murs = unary_union([c.exterior.buffer(0.10, join_style=2) for _, c in cages] + [chauf.exterior.buffer(0.10, join_style=2)])
    # porte « passage » de la chaufferie (façade est, en bas) et sortie en terrasse de l'escalier sud-ouest
    px, py = mt(2318, 2150)
    murs = murs.difference(box(px - 0.3, py - 0.45, px + 0.3, py + 0.45))
    sx, sy = m(877, 2190)
    murs = murs.difference(box(sx - 0.3, sy - 0.45, sx + 0.3, sy + 0.45))
    for p in (murs.geoms if isinstance(murs, MultiPolygon) else [murs]):
        for r in [p.exterior, *p.interiors]:
            msp.add_lwpolyline(list(r.coords)[:-1], close=True, dxfattribs={"layer": "A-MURS"})
        h = msp.add_hatch(color=8, dxfattribs={"layer": "A-MURS-HACHURES"})
        h.paths.add_polyline_path(list(p.exterior.coords)[:-1], is_closed=True, flags=1)
        for r in p.interiors:
            h.paths.add_polyline_path(list(r.coords)[:-1], is_closed=True, flags=0)
    for (hx, hy), (ox, oy) in [((px, py - 0.45), (px + 0.9, py - 0.45)), ((sx, sy - 0.45), (sx + 0.9, sy - 0.45))]:
        msp.add_line((hx, hy), (ox, oy), dxfattribs={"layer": "A-PORTES"})
        msp.add_arc((hx, hy), 0.9, 0, 90, dxfattribs={"layer": "A-PORTES"})
    # marches visibles dans les édicules
    for x0, y0, x1, y1 in [(715, 2140, 860, 2400), (2630, 1225, 2780, 1470), (5945, 2395, 6065, 2620)]:
        a, b = m(x0, y1), m(x1, y0)
        n = 7
        for k in range(n + 1):
            x = a[0] + (b[0] - a[0]) * k / n
            msp.add_line((x, a[1]), (x, b[1]), dxfattribs={"layer": "A-ESCALIERS"})
    # machinerie d'ascenseur (au-dessus de l'ascenseur nord), ventilations de la chaufferie
    mach = [mt(2127, 1618), mt(2318, 1618), mt(2318, 1864), mt(2127, 1864)]
    msp.add_lwpolyline(mach, close=True, dxfattribs={"layer": "A-ASCENSEURS"})
    t = msp.add_text("Machinerie ascenseur", height=0.18, dxfattribs={"layer": "A-ASCENSEURS"})
    c = Polygon(mach).centroid
    t.set_placement((c.x, c.y), align=TextEntityAlignment.MIDDLE_CENTER)
    for gx, gy in [mt(1818, 1760), mt(2318, 1760)]:
        msp.add_line((gx, gy - 0.4), (gx, gy + 0.4), dxfattribs={"layer": "A-TOITURE-DETAILS"})

    # ---- débouchés de gaines (cliquables)
    def gaine(nom, x0, y0, x1, y1, terrasse=True):
        f = mt if terrasse else m
        q = [f(x0, y1), f(x1, y1), f(x1, y0), f(x0, y0)]
        msp.add_lwpolyline(q, close=True, dxfattribs={"layer": "A-GAINES"})
        h = msp.add_hatch(color=1, dxfattribs={"layer": "A-GAINES"})
        h.set_pattern_fill("ANSI31", scale=0.2)
        h.paths.add_polyline_path(q, is_closed=True)
        c = Polygon(q).centroid
        tt = msp.add_text(nom, height=0.16, dxfattribs={"layer": "A-GAINES"})
        tt.set_placement((c.x, c.y), align=TextEntityAlignment.MIDDLE_CENTER)

    gaine("Sortie ventilation G3", 1340, 1991, 1395, 2055)
    gaine("Trappe gaine G4", 2233, 1995, 2287, 2045)
    gaine("Débouché vide-ordures", 5455, 2691, 5493, 2729)

    # ---- zones de toiture séparées par les joints de dilatation (cliquables)
    jd = [T(2327, 1500)[0], T(4790, 1500)[0]]
    zones_t = emprise.difference(unary_union([c for _, c in cages] + [chauf]))
    for x in jd:
        a, b = m(x, 1000), m(x, 2900)
        msp.add_line(a, b, dxfattribs={"layer": "A-TOITURE-DETAILS"})
        tt = msp.add_text("joint de dilatation", height=0.2, dxfattribs={"layer": "A-ANNOTATIONS"})
        tt.set_placement((a[0] + 0.25, m(0, 1300)[1]), align=TextEntityAlignment.MIDDLE_LEFT)
        tt.dxf.rotation = 90
        zones_t = unary_union([g for g in split(zones_t, LineString([a, b])).geoms]) if zones_t.intersects(LineString([a, b])) else zones_t
    morceaux = []
    for x in jd:
        pass
    bornes = [-1e9] + [m(x, 0)[0] for x in jd] + [1e9]
    noms = ["Toiture-terrasse ouest (axes 1 à 8)", "Toiture-terrasse centrale (axes 9 à 19)", "Toiture-terrasse est et aile (axes 20 à 28)"]
    for i in range(3):
        z = zones_t.intersection(box(bornes[i], -1e9, bornes[i + 1], 1e9)).buffer(-0.20, join_style=2)
        if z.is_empty:
            continue
        z = max(z.geoms, key=lambda g: g.area) if isinstance(z, MultiPolygon) else z
        msp.add_lwpolyline(list(z.exterior.coords)[:-1], close=True, dxfattribs={"layer": "A-TOITURES"})
        c = z.representative_point()
        tt = msp.add_text(noms[i], height=0.32, dxfattribs={"layer": "A-TOITURES"})
        tt.set_placement((c.x, c.y), align=TextEntityAlignment.MIDDLE_CENTER)
    for nom, c in cages:
        msp.add_lwpolyline(list(c.buffer(-0.12).exterior.coords)[:-1], close=True, dxfattribs={"layer": "A-TOITURES"})
        p = c.representative_point()
        tt = msp.add_text(nom.split(" (")[0], height=0.18, dxfattribs={"layer": "A-TOITURES"})
        tt.set_placement((p.x, p.y), align=TextEntityAlignment.MIDDLE_CENTER)
        tt.dxf.text = nom
    ch = chauf.buffer(-0.12)
    msp.add_lwpolyline(list(ch.exterior.coords)[:-1], close=True, dxfattribs={"layer": "A-TOITURES"})
    tt = msp.add_text("Chaufferie", height=0.32, dxfattribs={"layer": "A-TOITURES"})
    c = Polygon([mt(1818, 1900), mt(2120, 1900), mt(2120, 2191), mt(1818, 2191)]).centroid
    tt.set_placement((c.x, c.y), align=TextEntityAlignment.MIDDLE_CENTER)

    # ---- détails linéaires : rive des balcons, parcours VMC, relevé, passage VMC
    for pts, txt in [([T(836, 2773), T(5430, 2795)], "rive des balcons (R+4)"),
                     ([T(2400, 2218), T(5430, 2218)], "parcours VMC"),
                     ([T(249, 2050), T(2327, 2055)], "relevé d'étanchéité (mur de couloir)")]:
        a, b = m(*pts[0]), m(*pts[1])
        msp.add_line(a, b, dxfattribs={"layer": "A-TOITURE-DETAILS"})
        tt = msp.add_text(txt, height=0.2, dxfattribs={"layer": "A-ANNOTATIONS"})
        tt.set_placement(((a[0] + b[0]) / 2, a[1] + 0.25), align=TextEntityAlignment.BOTTOM_CENTER)
    for txt, (x, y), h in [("passage VMC (coupe-feu)", (2330, 2125), 0.18), ("bardage", (2050, 1560), 0.18),
                           ("ventilations haute et basse", (2070, 2120), 0.16), ("v.o.", (5474, 2660), 0.16)]:
        tt = msp.add_text(txt, height=h, dxfattribs={"layer": "A-ANNOTATIONS"})
        tt.set_placement(mt(x, y), align=TextEntityAlignment.MIDDLE_CENTER)

    for i, t in enumerate(["ENSEMBLE D'ACCUEIL POUR ÉTUDIANTS — FOYER", "PLAN DE TOITURE (terrasse)",
                           "Échelle 1/100 — unités : mètres", "Redessiné d'après plan DOE Ex12bis — 26/11/2026",
                           "Pentes, EP et étanchéité : non renseignées sur le DOE"]):
        msp.add_text(t, height=0.4, dxfattribs={"layer": "A-CARTOUCHE"}).set_placement((0, -2 - i * 0.6))
    doc.saveas(RACINE / "plans" / "cad" / "terrasse.dxf")
    print("plans/cad/terrasse.dxf : acrotère, 3 zones de toiture, 3 édicules, chaufferie, machinerie, 3 débouchés de gaines")


if __name__ == "__main__":
    ecrire()
