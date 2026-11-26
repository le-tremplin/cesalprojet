#!/usr/bin/env python3
"""Convertit un plan DXF (unités : mètres, calques A-*) en SVG vectoriel pour le site,
et extrait les salles (nom, surface, contour) dans un fichier JSON.

Usage :
    pip install ezdxf shapely
    python3 outils/dxf_vers_svg.py plans/cad/rdc-haut.dxf plans/rdc-haut.svg

Le SVG produit :
- 1 m = ECHELLE unités SVG (voir ci-dessous), axe Y retourné (le nord reste en haut) ;
- un groupe <g class="l-NOM-DU-CALQUE"> par calque, pour que le site puisse
  montrer / masquer les démolitions, ouvertures nouvelles, textes… ;
- pas de couleurs de calque « en dur » : le style vient de app.css.

Le JSON produit (même nom, extension .salles.json) liste les salles :
  { "nom", "surface", "x", "y", "contour": [[x,y],…] }  (unités SVG)
Le contour vient d'une hachure A-ZONES-PROJET si elle contient l'étiquette,
sinon il est calculé à partir des murs (fermeture des baies de portes).
"""
import json, math, sys
from pathlib import Path

import ezdxf
from ezdxf import bbox as ezbbox
from ezdxf import path as ezpath
from shapely.geometry import Polygon, Point, LineString, MultiPolygon, box
from shapely.ops import unary_union, polygonize

ECHELLE = 50          # unités SVG par mètre
MARGE = 1.5           # m autour du dessin
CALQUES_IGNORES = {"A-CARTOUCHE", "Defpoints", "A-ZONES-PROJET"}
FERMETURE_PORTES = 0.55  # m : demi-largeur max des baies refermées pour trouver les salles


def arc_pts(cx, cy, r, a0, a1, n=None):
    if a1 < a0:
        a1 += 360
    n = n or max(4, int((a1 - a0) / 6))
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def lwpoly_pts(e):
    """Sommets d'une LWPOLYLINE, arcs (bulge) discrétisés."""
    pts = [(v.x, v.y) for v in ezpath.make_path(e).flattening(0.02)]
    if e.closed and len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def hatch_polys(e):
    out = []
    for p in ezpath.from_hatch(e):
        v = [(q.x, q.y) for q in p.flattening(0.02)]
        if len(v) >= 3:
            out.append(v)
    return out


class Conv:
    def __init__(self, doc):
        self.doc = doc
        self.msp = doc.modelspace()
        b = ezbbox.extents(e for e in self.msp if e.dxf.layer not in CALQUES_IGNORES)
        self.x0, self.y0 = b.extmin.x - MARGE, b.extmin.y - MARGE
        self.x1, self.y1 = b.extmax.x + MARGE, b.extmax.y + MARGE
        self.W = (self.x1 - self.x0) * ECHELLE
        self.H = (self.y1 - self.y0) * ECHELLE

    def P(self, x, y):
        return ((x - self.x0) * ECHELLE, (self.y1 - y) * ECHELLE)

    def path(self, pts, ferme):
        if not pts:
            return ""
        s = "M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in (self.P(*p) for p in pts))
        return s + ("Z" if ferme else "")

    def svg(self):
        groupes = {}
        for e in self.msp:
            lay = e.dxf.layer
            if lay in CALQUES_IGNORES:
                continue
            t = e.dxftype()
            g = groupes.setdefault(lay, [])
            if t == "LINE":
                g.append(f'<path d="{self.path([(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)], False)}"/>')
            elif t == "LWPOLYLINE":
                g.append(f'<path d="{self.path(lwpoly_pts(e), e.closed)}"/>')
            elif t == "CIRCLE":
                cx, cy = self.P(e.dxf.center.x, e.dxf.center.y)
                g.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{e.dxf.radius * ECHELLE:.1f}"/>')
            elif t == "ARC":
                g.append(f'<path d="{self.path(arc_pts(e.dxf.center.x, e.dxf.center.y, e.dxf.radius, e.dxf.start_angle, e.dxf.end_angle), False)}"/>')
            elif t == "HATCH":
                d = " ".join(self.path(p, True) for p in hatch_polys(e))
                g.append(f'<path class="h" fill-rule="evenodd" d="{d}"/>')
            elif t in ("TEXT", "MTEXT"):
                txt = e.dxf.text if t == "TEXT" else e.plain_text()
                ins = e.dxf.insert
                x, y = self.P(ins.x, ins.y)
                hgt = (e.dxf.height if t == "TEXT" else e.dxf.char_height) * ECHELLE
                rot = -(e.dxf.get("rotation", 0) or 0)
                anc = "start"
                if t == "TEXT" and e.dxf.get("halign", 0) in (1, 4):
                    anc = "middle"
                    if e.dxf.hasattr("align_point"):
                        x, y = self.P(e.dxf.align_point.x, e.dxf.align_point.y)
                tr = f' transform="rotate({rot:.1f} {x:.1f} {y:.1f})"' if abs(rot) > 0.1 else ""
                esc = txt.replace("&", "&amp;").replace("<", "&lt;")
                g.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{hgt:.1f}" text-anchor="{anc}"{tr}>{esc}</text>')
        ordre = ["A-ZONES", "A-MURS-HACHURES", "A-MURS", "A-POTEAUX", "A-DEMOLITION", "A-OUVERTURES-NOUVELLES",
                 "A-ESCALIERS", "A-GARDE-CORPS", "A-EQUIPEMENTS", "A-PORTES", "A-SALLES-SURFACES", "A-SALLES-TEXTE"]
        cles = sorted(groupes, key=lambda k: ordre.index(k) if k in ordre else 5)
        corps = "\n".join(f'<g class="l-{k.lower()}">' + "".join(groupes[k]) + "</g>" for k in cles if groupes[k])
        return corps

    # ------------------------------------------------------------- salles
    def murs(self):
        polys = []
        fermes = []
        for e in self.msp.query('LWPOLYLINE[layer=="A-MURS"]'):
            pts = lwpoly_pts(e)
            if e.closed and len(pts) >= 3:
                p = Polygon(pts).buffer(0)
                if p.area > 0:
                    fermes.append(p)
            elif len(pts) >= 2:
                polys.append(LineString(pts).buffer(0.08))
        # règle pair-impair : un contour fermé à l'intérieur d'un autre est un vide (pièce), pas un mur
        plein = None
        for p in sorted(fermes, key=lambda q: -q.area):
            plein = p if plein is None else plein.symmetric_difference(p)
        if plein is not None:
            polys.append(plein)
        for e in self.msp.query('HATCH[layer=="A-MURS-HACHURES"]'):
            h = None                       # contours d'une hachure : règle pair-impair (îlots = vides)
            for v in sorted(hatch_polys(e), key=lambda q: -Polygon(q).buffer(0).area):
                p = Polygon(v).buffer(0)
                if p.area > 0:
                    h = p if h is None else h.symmetric_difference(p)
            if h is not None:
                polys.append(h)
        # une porte ferme la pièce : vantail (ligne) + corde de son arc d'ouverture
        for e in self.msp.query('*[layer=="A-PORTES"]'):
            t = e.dxftype()
            if t == "LINE":
                polys.append(LineString([(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]).buffer(0.03))
            elif t in ("ARC", "LWPOLYLINE"):
                pts = [(v.x, v.y) for v in ezpath.make_path(e).flattening(0.05)]
                if len(pts) >= 2 and Point(pts[0]).distance(Point(pts[-1])) > 0.3:
                    polys.append(LineString([pts[0], pts[-1]]).buffer(0.03))
        for e in self.msp.query('LINE[layer=="A-FENETRES"]'):   # une fenêtre ferme la pièce
            polys.append(LineString([(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]).buffer(0.05))
        for e in self.msp.query('CIRCLE[layer=="A-POTEAUX"]'):
            polys.append(Point(e.dxf.center.x, e.dxf.center.y).buffer(e.dxf.radius))
        for g, _, _ in self.boites():          # gaines et ascenseurs : exclus des pièces voisines
            polys.append(g)
        return unary_union(polys)

    def boites(self):
        """Gaines techniques et cages d'ascenseur : chaque contour fermé est un local à part."""
        out = []
        for calque, genre in (("A-GAINES", "gaine"), ("A-ASCENSEURS", "ascenseur"), ("A-STATIONNEMENT", "place"),
                              ("A-RAMPES", "rampe"), ("A-ESCALIERS", "escalier"), ("A-TOITURES", "toiture"),
                              ("A-LOGEMENTS", "logement")):
            textes = [(Point(t.dxf.insert.x, t.dxf.insert.y) if not t.dxf.hasattr("align_point") else Point(t.dxf.align_point.x, t.dxf.align_point.y), t.dxf.text)
                      for t in self.msp.query(f'TEXT[layer=="{calque}"]')]
            for e in self.msp.query(f'LWPOLYLINE[layer=="{calque}"]'):
                if not e.closed:
                    continue
                g = Polygon(lwpoly_pts(e)).buffer(0)
                nom = next((t for p, t in textes if g.buffer(0.05).contains(p)), "")
                out.append((g, genre, nom))
        return out

    def salles(self):
        etiquettes = []
        surfaces = [(Point(e.dxf.insert.x, e.dxf.insert.y), e.dxf.text) for e in self.msp.query('TEXT[layer=="A-SALLES-SURFACES"]')]
        for e in self.msp.query('TEXT[layer=="A-SALLES-TEXTE"]'):
            p = e.dxf.align_point if e.dxf.get("halign", 0) and e.dxf.hasattr("align_point") else e.dxf.insert
            etiquettes.append((e.dxf.text, Point(p.x, p.y)))
        zones = []
        for e in self.msp.query('HATCH[layer=="A-ZONES-PROJET"]'):
            for v in hatch_polys(e):
                zones.append((Polygon(v).buffer(0), e.dxf.get("true_color")))
        murs = self.murs()
        cadre = box(self.x0, self.y0, self.x1, self.y1)
        # fermeture morphologique : on épaissit les murs pour refermer les baies,
        # on découpe le vide en cellules, puis on rend l'épaisseur perdue.
        # Plusieurs épaisseurs sont essayées ; on garde la cellule dont l'aire
        # se rapproche le plus de la surface écrite sur le plan.
        bord = cadre.exterior.buffer(0.01)
        decoupes = []
        for f in (0.25, 0.4, FERMETURE_PORTES, 0.8, 1.2):
            vide = cadre.difference(murs.buffer(f, join_style=2))
            cel = list(vide.geoms) if isinstance(vide, MultiPolygon) else [vide]
            decoupes.append((f, [c for c in cel if not c.intersects(bord)]))
        out = []
        for nom, pt in etiquettes:
            surf = min(surfaces, key=lambda s: s[0].distance(pt))[1] if surfaces else ""
            if surfaces and min(s[0].distance(pt) for s in surfaces) > 0.8:
                surf = ""
            try:
                cible = float(surf.replace("m²", "").replace("m2", "").replace(",", ".").strip())
            except ValueError:
                cible = None
            geo, src = None, ""
            for z, col in zones:
                if z.contains(pt):
                    geo, src = z, "hachure"
                    break
            # une pièce fermée par des murs prime sur une hachure qui en couvre plusieurs
            hachure = geo
            if True:
                cand = []
                for f, cel in decoupes:
                    for c in cel:
                        if c.distance(pt) < 0.3:
                            g = c.buffer(f, join_style=2).difference(murs)
                            if isinstance(g, MultiPolygon):
                                g = max(g.geoms, key=lambda q: q.area)
                            cand.append(g)
                            break
                if cand:
                    if cible:
                        g = min(cand, key=lambda g: abs(math.log(max(g.area, 0.01) / cible)))
                    else:
                        g = cand[len(cand) // 2]
                    if hachure is None or g.area < hachure.area * 0.95:
                        geo, src = g.simplify(0.05), "murs"
            if geo is not None and not geo.is_empty and not surf and geo.area < 2500:
                surf = f"{geo.area:.1f} m²".replace(".", ",")
            if geo is None or geo.is_empty or geo.area > 2500:
                geo, src = pt.buffer(0.8, 6), "point"
            if isinstance(geo, MultiPolygon):
                geo = max(geo.geoms, key=lambda q: q.area)
            x, y = self.P(pt.x, pt.y)
            out.append({"nom": nom, "surface": surf, "x": round(x, 1), "y": round(y, 1), "source": src,
                        "contour": [[round(a, 1), round(b, 1)] for a, b in (self.P(*c) for c in list(geo.exterior.coords)[:-1])]})
        # espaces ouverts : deux étiquettes dans la même cellule (ex. cafétéria dans le hall) →
        # partage de la cellule par une ligne perpendiculaire aux deux étiquettes, à la surface écrite sur le plan
        from shapely.ops import split as couper
        from shapely.geometry import LineString as LS
        polys = [Polygon([((a / ECHELLE) + self.x0, self.y1 - b / ECHELLE) for a, b in o["contour"]]).buffer(0) for o in out]
        for i, oi in enumerate(out):
            for j, oj in enumerate(out):
                if i == j or oi["source"] != "murs" or oj["source"] != "murs":
                    continue
                A, B = polys[i], polys[j]
                if A.area < B.area and A.intersection(B).area > 0.9 * A.area:
                    try:
                        cible = float(oi["surface"].replace(" m²", "").replace(",", "."))
                    except ValueError:
                        continue
                    pa = Point((oi["x"] / ECHELLE) + self.x0, self.y1 - oi["y"] / ECHELLE)
                    pb = Point((oj["x"] / ECHELLE) + self.x0, self.y1 - oj["y"] / ECHELLE)
                    dx, dy = pb.x - pa.x, pb.y - pa.y
                    n_ = math.hypot(dx, dy) or 1
                    ux, uy = dx / n_, dy / n_
                    lo, hi, piece = 0.0, n_, None
                    for _ in range(30):
                        t = (lo + hi) / 2
                        cx_, cy_ = pa.x + ux * t, pa.y + uy * t
                        ligne = LS([(cx_ - uy * 200, cy_ + ux * 200), (cx_ + uy * 200, cy_ - ux * 200)])
                        morceaux = [g for g in couper(B, ligne).geoms]
                        cote = [g for g in morceaux if g.buffer(0.01).contains(pa)]
                        if not cote:
                            lo = t
                            continue
                        piece = cote[0]
                        lo, hi = (t, hi) if piece.area < cible else (lo, t)
                    if piece is not None and abs(piece.area - cible) < 0.15 * cible:
                        reste = B.difference(piece.buffer(0.01))
                        if isinstance(reste, MultiPolygon):
                            reste = max(reste.geoms, key=lambda q: q.area)
                        polys[i], polys[j] = piece, reste
                        oi["contour"] = [[round(a, 1), round(b, 1)] for a, b in (self.P(*q) for q in list(piece.exterior.coords)[:-1])]
                        oj["contour"] = [[round(a, 1), round(b, 1)] for a, b in (self.P(*q) for q in list(reste.exterior.coords)[:-1])]
                        oi["source"] = oj["source"] = "partage"
        # pièces fermées sans étiquette : chacune devient un local à identifier
        deja = unary_union([Polygon([((a / ECHELLE) + self.x0, self.y1 - b / ECHELLE) for a, b in o["contour"]]).buffer(0) for o in out])
        k = 0
        for c in sorted(decoupes[1][1], key=lambda c: (-c.centroid.y, c.centroid.x)):
            g = c.buffer(decoupes[1][0], join_style=2).difference(murs)
            if isinstance(g, MultiPolygon):
                g = max(g.geoms, key=lambda q: q.area)
            if not (2.5 < g.area < 600) or g.intersection(deja).area > 0.3 * g.area or g.buffer(-0.45).is_empty:
                continue
            k += 1
            q = g.representative_point()
            x, y = self.P(q.x, q.y)
            out.append({"nom": f"Local à identifier {k}", "surface": f"{g.area:.1f} m²".replace(".", ","), "x": round(x, 1), "y": round(y, 1),
                        "source": "murs", "contour": [[round(a, 1), round(b, 1)] for a, b in (self.P(*q) for q in list(g.simplify(0.05).exterior.coords)[:-1])]})
        for g, genre, nom in self.boites():
            c = g.representative_point()
            x, y = self.P(c.x, c.y)
            libelle = {"gaine": "Gaine technique", "ascenseur": "Ascenseur", "place": "Place", "rampe": "Rampe", "escalier": "Escalier", "toiture": "Toiture", "logement": "Logement"}[genre]
            if nom and genre in ("place", "rampe", "escalier", "toiture", "logement"):
                libelle = ("Place " + nom) if genre == "place" else nom
            elif nom:
                if " " in nom and not nom.startswith("Asc."):
                    libelle = nom                                   # nom déjà explicite
                elif genre == "gaine":
                    libelle = "Vide-ordures" if nom.startswith(("V.O", "Vide")) else f"Gaine {nom}"
                else:
                    libelle = nom if nom.startswith("Ascenseur") else f"Ascenseur {nom.replace('Asc.', '').strip()}".strip()
            out.append({"nom": libelle, "surface": (f"{g.area:.2f} m²" if genre in ("gaine", "ascenseur") else f"{g.area:.1f} m²").replace(".", ","), "x": round(x, 1), "y": round(y, 1),
                        "source": genre, "contour": [[round(a, 1), round(b, 1)] for a, b in (self.P(*q) for q in list(g.exterior.coords)[:-1])]})
        zp = []
        for z, col in zones:
            noms = [n for n, p in etiquettes if z.contains(p)]
            zp.append({"nom": noms[0] if noms else "", "couleur": f"#{col:06x}" if col else None,
                       "contour": [[round(a, 1), round(b, 1)] for a, b in (self.P(*c) for c in list(z.exterior.coords)[:-1])]})
        return out, zp


def convertir(src, dst):
    doc = ezdxf.readfile(src)
    c = Conv(doc)
    corps = c.svg()
    W, H = round(c.W), round(c.H)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" class="plan-cad">\n'
           f'<!-- généré par outils/dxf_vers_svg.py depuis {Path(src).name} · 1 m = {ECHELLE} unités -->\n{corps}\n</svg>\n')
    Path(dst).write_text(svg, encoding="utf-8")
    salles, zones = c.salles()
    meta = {"source": Path(src).name, "echelle": ECHELLE, "w": W, "h": H,
            "origine_m": [round(c.x0, 3), round(c.y1, 3)], "salles": salles, "zonesProjet": zones}
    Path(dst).with_suffix(".salles.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{dst} : {W}×{H}, {len(salles)} salles ({sum(s['source'] == 'murs' for s in salles)} par les murs, "
          f"{sum(s['source'] == 'hachure' for s in salles)} par hachure, {sum(s['source'] == 'point' for s in salles)} non fermées), "
          f"{len(zones)} zones projet, {Path(dst).stat().st_size // 1024} Ko")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    convertir(sys.argv[1], sys.argv[2])
