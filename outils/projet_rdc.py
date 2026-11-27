#!/usr/bin/env python3
"""Applique les décisions de projet aux plans DXF du groupe (RDC haut et RDC bas).

Entrées (jamais modifiées) : plans/cad/origine/rdc-haut-groupe.dxf, plans/cad/origine/rdc-bas-groupe.dxf
Sorties : plans/cad/rdc-haut.dxf, plans/cad/rdc-bas.dxf

RDC haut
- bâtiment détaché → salle des fêtes : salle polyvalente, bar ouvert (le mur du self devient un comptoir),
  cuisine dans l'ancienne cuisine (réseaux existants), réserve, rangement du mobilier, sanitaires dont PMR,
  vestiaire du personnel, local ménage ;
- foyer : le local noté « WC PMR » est un ascenseur (porte déplacée face à l'escalier), double porte à badge
  entre le hall d'exposition et la circulation des résidents, escalier redessiné en demi-colimaçon.
RDC bas
- Archives 2 → Stockage ; chaque local fermé devient une zone cliquable (fait par dxf_vers_svg.py).

Usage : python3 outils/projet_rdc.py
"""
import math
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf import path as ezpath
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import Polygon, box, MultiPolygon
from shapely.ops import unary_union

RACINE = Path(__file__).resolve().parent.parent
ORIG = RACINE / "plans" / "cad" / "origine"


def poly(e):
    pts = [(v.x, v.y) for v in ezpath.make_path(e).flattening(0.02)]
    return Polygon(pts).buffer(0)


def retoucher_murs(msp, ouvertures=(), ajouts=()):
    """Découpe des baies / ajoute des pans de mur dans les polylignes A-MURS et leurs hachures."""
    zone = unary_union(list(ouvertures) + list(ajouts)).buffer(0.3)
    for calque in ("A-MURS", "A-MURS-HACHURES"):
        q = 'LWPOLYLINE[layer=="A-MURS"]' if calque == "A-MURS" else 'HATCH[layer=="A-MURS-HACHURES"]'
        for e in list(msp.query(q)):
            if calque == "A-MURS" and not e.closed:
                continue
            try:
                if calque == "A-MURS":
                    g = poly(e)
                else:
                    paths = [Polygon([(v.x, v.y) for v in p.flattening(0.02)]).buffer(0) for p in ezpath.from_hatch(e)]
                    g = None
                    for p in sorted(paths, key=lambda q: -q.area):
                        g = p if g is None else g.symmetric_difference(p)
            except Exception:
                continue
            if g is None or g.is_empty or not g.intersects(zone):
                continue
            n = g
            for o in ouvertures:
                n = n.difference(o)
            for a in ajouts:
                if a.buffer(0.05).intersects(n):
                    n = n.union(a)
            if n.equals(g):
                continue
            msp.delete_entity(e)
            for p in (n.geoms if isinstance(n, MultiPolygon) else [n]):
                if p.area < 0.005:
                    continue
                if calque == "A-MURS":
                    msp.add_lwpolyline(list(p.exterior.coords)[:-1], close=True, dxfattribs={"layer": "A-MURS"})
                    for r in p.interiors:
                        msp.add_lwpolyline(list(r.coords)[:-1], close=True, dxfattribs={"layer": "A-MURS"})
                else:
                    h = msp.add_hatch(color=8, dxfattribs={"layer": "A-MURS-HACHURES"})
                    h.paths.add_polyline_path(list(p.exterior.coords)[:-1], is_closed=True, flags=1)
                    for r in p.interiors:
                        h.paths.add_polyline_path(list(r.coords)[:-1], is_closed=True, flags=0)


def supprimer(msp, calque, x0, y0, x1, y1):
    for e in list(msp.query(f'*[layer=="{calque}"]')):
        b = bbox.extents([e])
        if b.has_data and b.extmin.x >= x0 and b.extmax.x <= x1 and b.extmin.y >= y0 and b.extmax.y <= y1:
            msp.delete_entity(e)


def renommer(msp, ancien, nouveau, pres=None):
    for t in msp.query('TEXT[layer=="A-SALLES-TEXTE"]'):
        p = t.dxf.align_point if t.dxf.hasattr("align_point") else t.dxf.insert
        if t.dxf.text == ancien and (pres is None or math.hypot(p.x - pres[0], p.y - pres[1]) < 3):
            t.dxf.text = nouveau
            return t
    return None


def texte(msp, calque, txt, x, y, h=0.30):
    t = msp.add_text(txt, height=h, dxfattribs={"layer": calque})
    t.set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)
    return t


def rect(msp, calque, x0, y0, x1, y1, ferme=True):
    return msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=ferme, dxfattribs={"layer": calque})


def porte(msp, hx, hy, ax, ay, ox, oy):
    """Vantail : charnière (hx, hy), fermé vers (ax, ay), ouvert vers (ox, oy)."""
    r = math.hypot(ax - hx, ay - hy)
    msp.add_line((hx, hy), (ox, oy), dxfattribs={"layer": "A-PORTES"})
    a0 = math.degrees(math.atan2(ay - hy, ax - hx))
    a1 = math.degrees(math.atan2(oy - hy, ox - hx))
    if (a1 - a0) % 360 > 180:
        a0, a1 = a1, a0
    msp.add_arc((hx, hy), r, a0, a1, dxfattribs={"layer": "A-PORTES"})


def zone(msp, pts, couleur):
    h = msp.add_hatch(dxfattribs={"layer": "A-ZONES-PROJET"})
    h.rgb = couleur
    h.paths.add_polyline_path(pts, is_closed=True)


def rdc_haut():
    doc = ezdxf.readfile(ORIG / "rdc-haut-groupe.dxf")
    msp = doc.modelspace()
    for nom in ("A-ASCENSEURS", "A-ANNOTATIONS", "A-GAINES"):
        if nom not in doc.layers:
            doc.layers.add(nom)

    # ---------------- salle des fêtes (bâtiment détaché)
    # le mur sud de l'ancien self devient un comptoir de bar ouvert sur la salle
    retoucher_murs(msp, ouvertures=[box(31.45, 59.05, 38.75, 59.40)])
    retoucher_murs(msp, ajouts=[box(31.30, 59.05, 37.85, 59.60)])              # comptoir maçonné, passage de 0,9 m à l'est
    for x in (32.5, 34.5, 36.5):                                               # tabourets / repères
        msp.add_circle((x, 58.55), 0.22, dxfattribs={"layer": "A-EQUIPEMENTS"})
    # passe-plat entre la cuisine et le bar
    retoucher_murs(msp, ouvertures=[box(33.8, 61.8, 35.3, 62.2)])
    rect(msp, "A-EQUIPEMENTS", 33.8, 61.85, 35.3, 62.15)
    # cuisine : plans de travail en L, plonge, piano de cuisson sous hotte
    msp.add_lwpolyline([(31.55, 64.9), (31.55, 62.4), (32.2, 62.4), (32.2, 64.25), (36.0, 64.25), (36.0, 64.9)], dxfattribs={"layer": "A-EQUIPEMENTS"})
    rect(msp, "A-EQUIPEMENTS", 33.0, 64.35, 34.2, 64.85)                      # plonge
    rect(msp, "A-EQUIPEMENTS", 34.6, 64.35, 35.8, 64.85)                      # cuisson
    msp.add_line((34.6, 64.35), (35.8, 64.85), dxfattribs={"layer": "A-EQUIPEMENTS"})
    msp.add_line((34.6, 64.85), (35.8, 64.35), dxfattribs={"layer": "A-EQUIPEMENTS"})
    # réserve cuisine : rayonnages
    rect(msp, "A-EQUIPEMENTS", 36.7, 64.4, 39.5, 64.9)
    rect(msp, "A-EQUIPEMENTS", 38.3, 62.4, 40.5, 62.9)
    # rangement du mobilier : rayonnages et chariots de chaises
    rect(msp, "A-EQUIPEMENTS", 24.6, 58.3, 27.3, 58.9)
    rect(msp, "A-EQUIPEMENTS", 24.6, 61.2, 27.3, 61.75)
    # sanitaires : WC et lavabos dessinés
    for x in (39.0, 40.0, 41.0):
        msp.add_lwpolyline([(x - 0.2, 48.9), (x + 0.2, 48.9), (x + 0.2, 49.5), (x - 0.2, 49.5)], close=True, dxfattribs={"layer": "A-EQUIPEMENTS"})
    msp.add_circle((40.6, 52.3), 0.75, dxfattribs={"layer": "A-EQUIPEMENTS"})            # aire de rotation PMR Ø 1,50
    rect(msp, "A-EQUIPEMENTS", 41.0, 51.5, 41.45, 52.2)                                  # WC PMR
    # scène mobile et repère d'aménagement
    rect(msp, "A-EQUIPEMENTS", 25.0, 50.0, 29.0, 53.0)
    texte(msp, "A-EQUIPEMENTS", "Scène mobile", 27.0, 51.5, 0.25)
    renommer(msp, "Restaurant existant", "Salle polyvalente")
    supprimer(msp, "A-SALLES-SURFACES", 31.0, 53.0, 34.5, 55.0)               # surface recalculée à la conversion
    renommer(msp, "Sanit. vest.", "Vestiaire personnel")
    renommer(msp, "Bureau", "Local ménage")
    renommer(msp, "Sanitaires", "Sanitaires")
    texte(msp, "A-SALLES-TEXTE", "Cuisine salle des fêtes", 33.8, 63.3, 0.26)
    texte(msp, "A-SALLES-TEXTE", "Réserve cuisine", 38.6, 63.6, 0.26)
    texte(msp, "A-SALLES-TEXTE", "Bar", 35.0, 60.6)
    texte(msp, "A-SALLES-TEXTE", "Rangement mobilier", 26.0, 60.1, 0.24)
    texte(msp, "A-SALLES-TEXTE", "Sanitaires PMR", 40.0, 52.7, 0.24)
    texte(msp, "A-SALLES-TEXTE", "Dégagement de service", 28.6, 63.6, 0.2)
    texte(msp, "A-ANNOTATIONS", "SALLE DES FÊTES (bâtiment détaché)", 33.0, 66.3, 0.5)

    # ---------------- bar du restaurant (bât. 1) : angle nord-ouest de la salle, contre le mur nord,
    # à l'écart des portes (porte du couloir à x = 6,6 m, double porte de la terrasse à y = 20 m) et du local VMC 1
    rect(msp, "A-EQUIPEMENTS", 0.35, 30.40, 4.30, 30.95)                     # arrière-bar contre le mur nord
    rect(msp, "A-EQUIPEMENTS", 0.35, 29.15, 3.45, 29.75)                     # comptoir (passage de service à l'est)
    rect(msp, "A-EQUIPEMENTS", 3.55, 30.45, 4.25, 30.90)                     # plonge à verres
    for x in (0.80, 1.55, 2.30, 3.05):                                       # tabourets
        msp.add_circle((x, 28.75), 0.20, dxfattribs={"layer": "A-EQUIPEMENTS"})
    texte(msp, "A-SALLES-TEXTE", "Bar du restaurant", 2.2, 28.05, 0.24)

    # ---------------- foyer : WC PMR → ascenseur, accès côté escalier
    supprimer(msp, "A-PORTES", 49.3, 29.9, 50.7, 31.1)                         # porte du « WC »
    retoucher_murs(msp, ajouts=[box(49.40, 29.92, 50.60, 30.14)])              # baie refermée
    retoucher_murs(msp, ouvertures=[box(51.15, 30.45, 51.95, 31.35)])          # nouvelle baie vers l'escalier
    renommer(msp, "WC PMR", "Ascenseur")
    t = [x for x in msp.query('TEXT[layer=="A-SALLES-TEXTE"]') if x.dxf.text == "Ascenseur"][0]
    t.dxf.layer = "A-ASCENSEURS"
    rect(msp, "A-ASCENSEURS", 49.25, 30.25, 51.15, 31.55)
    msp.add_line((49.25, 30.25), (51.15, 31.55), dxfattribs={"layer": "A-ASCENSEURS"})
    msp.add_line((49.25, 31.55), (51.15, 30.25), dxfattribs={"layer": "A-ASCENSEURS"})
    for dy in (0.0, 0.42):                                                     # portes palières coulissantes
        msp.add_line((51.6, 30.5 + dy), (51.6, 30.9 + dy), dxfattribs={"layer": "A-PORTES"})
    supprimer(msp, "A-SALLES-SURFACES", 49.7, 30.5, 50.7, 30.9)

    # ---------------- hall d'exposition → double porte à badge → circulation des résidents
    supprimer(msp, "A-PORTES", 52.4, 26.1, 53.5, 27.2)
    retoucher_murs(msp, ouvertures=[box(52.45, 25.95, 54.15, 26.45)])
    porte(msp, 52.50, 26.20, 53.30, 26.20, 52.50, 27.00)
    porte(msp, 54.10, 26.20, 53.30, 26.20, 54.10, 27.00)
    rect(msp, "A-EQUIPEMENTS", 54.30, 26.45, 54.55, 26.65)                     # lecteur de badge
    texte(msp, "A-ANNOTATIONS", "Double porte à badge", 53.3, 25.6, 0.22)
    renommer(msp, "Circulation", "Circulation résidents", pres=(55.2, 30.1))
    for t in msp.query('TEXT[layer=="A-SALLES-TEXTE"]'):
        if t.dxf.text == "Circulation résidents":
            t.dxf.height = 0.26
            t.set_placement((55.9, 27.05), align=TextEntityAlignment.MIDDLE_CENTER)
    for t in msp.query('TEXT[layer=="A-SALLES-SURFACES"]'):
        p_ = t.dxf.insert
        if 53.8 < p_.x < 56.5 and 29.2 < p_.y < 30.0:
            t.set_placement((55.9, 26.75), align=TextEntityAlignment.MIDDLE_CENTER)
    texte(msp, "A-ANNOTATIONS", "ESPACE RÉSIDENTS — accès aux logements", 55.0, 32.4, 0.3)
    texte(msp, "A-ANNOTATIONS", "ESPACE PUBLIC — exposition", 54.5, 19.8, 0.3)
    zone(msp, [(51.6, 19.2), (57.4, 19.2), (57.4, 26.1), (51.6, 26.1)], (143, 160, 126))
    zone(msp, [(51.3, 26.35), (55.3, 26.35), (57.8, 27.2), (57.9, 28.9), (57.8, 30.6), (55.3, 31.5), (51.3, 31.5), (51.3, 29.6), (52.1, 29.6), (52.1, 26.35)], (139, 125, 156))

    # ---------------- escalier demi-colimaçon (demi-tournant balancé) dans la cage existante
    # Cage relevée sur le DXF du groupe (mur A1) : intérieur x 53,33 → 56,88, y 27,95 → 31,50,
    # extrémité est arrondie (rayon intérieur ≈ 1,58 m centré en (55,30 ; 29,73)). La cage est celle de
    # l'escalier principal du foyer, au même emplacement à tous les étages : on ne touche à aucun mur.
    supprimer(msp, "A-ESCALIERS", 53.3, 27.8, 57.0, 31.8)
    xw, cx, cy = 53.45, 55.30, 30.07          # départ des volées, centre du demi-tour
    y_n, y_s = 31.45, 28.68                   # face nord ; au sud, nu du muret de départ (E9)
    r_in, r_out = 0.30, 1.36                  # jour central, rayon extérieur des balancements
    emm = 1.24                                # emmarchement (≥ 1,20 m)
    gir = 0.28                                # giron sur la ligne de foulée
    # volée sud (départ depuis la circulation, montée vers l'est) et volée nord (retour vers l'ouest)
    n_droit = int((cx - xw) / gir)
    for k in range(n_droit + 1):
        x = xw + k * (cx - xw) / n_droit
        msp.add_line((x, y_s), (x, y_s + emm), dxfattribs={"layer": "A-ESCALIERS"})
        msp.add_line((x, y_n - emm), (x, y_n), dxfattribs={"layer": "A-ESCALIERS"})
    # 7 marches balancées sur le demi-tour (giron constant sur la ligne de foulée à 0,50 m du jour)
    for k in range(8):
        a_ = math.radians(-90 + k * 180 / 7)
        msp.add_line((cx + r_in * math.cos(a_), cy + r_in * math.sin(a_)),
                     (cx + r_out * math.cos(a_), cy + r_out * math.sin(a_)), dxfattribs={"layer": "A-ESCALIERS"})
    # limon central (jour) et mur d'échiffre entre les volées
    msp.add_line((xw, y_s + emm), (cx, y_s + emm), dxfattribs={"layer": "A-ESCALIERS"})
    msp.add_line((xw, y_n - emm), (cx, y_n - emm), dxfattribs={"layer": "A-ESCALIERS"})
    msp.add_arc((cx, cy), r_in, -90, 90, dxfattribs={"layer": "A-ESCALIERS"})
    msp.add_lwpolyline([(xw + 0.3, cy - 0.20), (cx, cy - 0.20), (cx, cy + 0.20), (xw + 0.3, cy + 0.20)], close=True,
                       dxfattribs={"layer": "A-ESCALIERS"})
    # ligne de foulée et flèche de montée
    rf = r_in + 0.50
    msp.add_line((xw + 0.2, y_s + emm / 2), (cx, y_s + emm / 2), dxfattribs={"layer": "A-ESCALIERS"})
    msp.add_arc((cx, cy), cy - (y_s + emm / 2), -90, 90, dxfattribs={"layer": "A-ESCALIERS"})
    msp.add_line((cx, y_n - emm / 2), (xw + 0.4, y_n - emm / 2), dxfattribs={"layer": "A-ESCALIERS"})
    msp.add_line((xw + 0.4, y_n - emm / 2), (xw + 0.65, y_n - emm / 2 + 0.12), dxfattribs={"layer": "A-ESCALIERS"})
    msp.add_line((xw + 0.4, y_n - emm / 2), (xw + 0.65, y_n - emm / 2 - 0.12), dxfattribs={"layer": "A-ESCALIERS"})
    texte(msp, "A-ESCALIERS", "Escalier principal — demi-tournant balancé", 54.30, cy, 0.17)
    texte(msp, "A-ANNOTATIONS", "départ", xw + 0.35, y_s + 0.25, 0.16)
    texte(msp, "A-ANNOTATIONS", "Nb de marches à confirmer (hauteur d'étage non documentée)", 55.2, 32.05, 0.15)

    for t in msp.query('TEXT[layer=="A-CARTOUCHE"]'):
        if "PROJET" in t.dxf.text:
            t.dxf.text = "REZ-DE-CHAUSSÉE HAUT — PROJET (salle des fêtes, accès résidents)"
    doc.saveas(RACINE / "plans" / "cad" / "rdc-haut.dxf")
    print("plans/cad/rdc-haut.dxf : salle des fêtes, ascenseur, double porte à badge, escalier demi-colimaçon")


def rdc_bas():
    doc = ezdxf.readfile(ORIG / "rdc-bas-groupe.dxf")
    msp = doc.modelspace()
    renommer(msp, "Archives 2", "Stockage")
    doc.saveas(RACINE / "plans" / "cad" / "rdc-bas.dxf")
    print("plans/cad/rdc-bas.dxf : Archives 2 → Stockage")


if __name__ == "__main__":
    rdc_haut()
    rdc_bas()
