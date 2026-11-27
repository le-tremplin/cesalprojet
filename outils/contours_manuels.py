#!/usr/bin/env python3
"""Contours corrigés à la main pour les espaces ouverts que le calcul automatique fusionne
(salle des fêtes, entrée du foyer). Les contours sont découpés dans la pièce réelle (vide entre
les murs du DXF) : ils suivent exactement les murs. Les locaux concernés reçoivent
« contour_fixe » : outils/integrer_cad.py ne les recalcule plus.

Usage : python3 outils/contours_manuels.py   (après outils/dxf_vers_svg.py et outils/integrer_cad.py)
"""
import importlib.util, json
from pathlib import Path

import ezdxf
from shapely.geometry import Point, box, MultiPolygon, Polygon
from shapely.ops import unary_union

RACINE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("c", RACINE / "outils" / "dxf_vers_svg.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def cellule(cv, murs, x, y, f=0.25):
    cadre = box(cv.x0, cv.y0, cv.x1, cv.y1)
    v = cadre.difference(murs.buffer(f, join_style=2))
    for q in (v.geoms if isinstance(v, MultiPolygon) else [v]):
        if q.contains(Point(x, y)):
            g = q.buffer(f, join_style=2).difference(murs)
            return max(g.geoms, key=lambda z: z.area) if isinstance(g, MultiPolygon) else g
    raise ValueError(f"pas de pièce en ({x}, {y})")


def main():
    d = json.loads((RACINE / "data" / "donnees.json").read_text(encoding="utf-8"))
    cv = c.Conv(ezdxf.readfile(RACINE / "plans" / "cad" / "rdc-haut.dxf"))
    murs = cv.murs()
    loc = {l["id"]: l for l in d["locaux"]}
    poly_m = lambda l: Polygon([((a / c.ECHELLE) + cv.x0, cv.y1 - b / c.ECHELLE) for a, b in l["forme"]["points"]]).buffer(0)

    # --- salle des fêtes : une seule pièce ouverte, partagée selon l'aménagement du projet
    sdf = cellule(cv, murs, 30, 54)
    fixes = {i: poly_m(loc[i]) for i in ("sanit-vest-rdc-haut", "bureau-rdc-haut", "sanitaires-rdc-haut", "sanitaires-pmr-rdc-haut") if i in loc}
    menage = fixes.get("bureau-rdc-haut", box(0, 0, 0, 0))
    vest = fixes.get("sanit-vest-rdc-haut", box(0, 0, 0, 0))
    zones = {
        "cuisine": box(31.60, 61.80, 37.02, 65.10),                    # entre le mur du bar et le mur de la réserve
        "reserve-cuisine-rdc-haut": box(37.10, 61.80, 41.70, 65.20),
        "bar-rdc-haut": box(31.50, 59.60, 38.75, 61.70),               # derrière le comptoir
        "rangement-mobilier-rdc-haut": box(24.20, 57.95, 28.25, 61.65),
        "degagement-de-service-rdc-haut": unary_union([box(24.20, 61.75, 31.55, 62.65), box(28.30, 62.65, 31.55, 65.20)]).difference(menage).difference(vest),
    }
    pris = unary_union(list(fixes.values()))
    for i, z in zones.items():
        g = z.intersection(sdf).difference(pris)
        zones[i] = max(g.geoms, key=lambda q: q.area) if isinstance(g, MultiPolygon) else g
        pris = pris.union(zones[i])
    salle = sdf.difference(pris.buffer(0.01))
    zones["salle-restaurant"] = max(salle.geoms, key=lambda q: q.area) if isinstance(salle, MultiPolygon) else salle

    # --- entrée du foyer : la pièce d'entrée et le local poubelles sont séparés par le mur x ≈ 47,65 m
    ent = cellule(cv, murs, 45.5, 29.0)
    zones["entree-rdc-haut"] = ent.intersection(box(0, 0, 47.62, 99))
    zones["local-poubelles-rdc-haut"] = ent.intersection(box(47.68, 0, 99, 99))

    for i, g in zones.items():
        if i not in loc:
            print("absent :", i)
            continue
        if isinstance(g, MultiPolygon):
            g = max(g.geoms, key=lambda q: q.area)
        g = g.simplify(0.03)
        loc[i]["forme"] = {"type": "poly", "points": [[round(a, 1), round(b, 1)] for a, b in (cv.P(*q) for q in list(g.exterior.coords)[:-1])]}
        loc[i]["surface"] = f"{g.area:.1f} m²".replace(".", ",")
        loc[i]["contour_fixe"] = True
        print(f"{i:34s} {g.area:6.1f} m²")
    (RACINE / "data" / "donnees.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
