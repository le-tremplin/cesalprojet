#!/usr/bin/env python3
"""Génère le QR code du site en SVG, prêt à imprimer (texte vectorisé, sans police requise).

Usage :
    pip install segno fonttools
    python3 outils/generer_qr.py              # QR d'accueil, 12 cm et 5 cm
    python3 outils/generer_qr.py --local tgbt # QR d'un local précis (lien ?local=tgbt)

L'adresse est lue dans config.js (URL_BASE) : après un changement de domaine,
modifier config.js puis relancer ce script.
"""
import argparse, json, re, sys
from pathlib import Path

import segno
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

RACINE = Path(__file__).resolve().parent.parent
ENCRE, FOND = "#2f3328", "#f2f0ea"
SOUS_TITRE = "Le Tremplin · ancien CESAL, Bourges"
POLICES = {
    "gras": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
             "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf"],
    "normal": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf",
               "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf"],
}


def url_base():
    txt = (RACINE / "config.js").read_text(encoding="utf-8")
    m = re.search(r'URL_BASE\s*:\s*"([^"]+)"', txt)
    if not m:
        sys.exit("URL_BASE introuvable dans config.js")
    return m.group(1)


def police(style):
    for p in POLICES[style]:
        if Path(p).exists():
            return TTFont(p)
    sys.exit(f"Aucune police {style} trouvée : ajoutez son chemin dans POLICES.")


def texte_en_chemin(font, texte, taille, cx, y_base, largeur_max):
    """Retourne un <path> SVG du texte centré sur cx, ligne de base y_base (unités mm)."""
    cmap, glyphs = font.getBestCmap(), font.getGlyphSet()
    upm = font["head"].unitsPerEm
    hmtx = font["hmtx"]
    noms = [cmap.get(ord(c), ".notdef") for c in texte]
    larg = sum(hmtx[n][0] for n in noms) * taille / upm
    if larg > largeur_max:
        taille *= largeur_max / larg
        larg = largeur_max
    k = taille / upm
    x = cx - larg / 2
    d = []
    for n in noms:
        pen = SVGPathPen(glyphs)
        glyphs[n].draw(TransformPen(pen, (k, 0, 0, -k, x, y_base)))
        if pen.getCommands():
            d.append(pen.getCommands())
        x += hmtx[n][0] * k
    return f'<path fill="{ENCRE}" d="{" ".join(d)}"/>', taille


def qr_svg(url, titre, cote_mm, chemin):
    qr = segno.make(url, error="q", micro=False)
    mat = qr.matrix
    n = len(mat)
    q = 4  # zone de silence de 4 modules
    mod = cote_mm / (n + 2 * q)
    rects = []
    for y, ligne in enumerate(mat):
        x = 0
        while x < n:
            if ligne[x]:
                x0 = x
                while x < n and ligne[x]:
                    x += 1
                rects.append(f"M{(x0 + q) * mod:.3f} {(y + q) * mod:.3f}h{(x - x0) * mod:.3f}v{mod:.3f}h{-(x - x0) * mod:.3f}z")
            else:
                x += 1
    gras, normal = police("gras"), police("normal")
    t1 = cote_mm * 0.085
    t2 = cote_mm * 0.050
    y1 = cote_mm + t1 * 0.35
    p1, t1 = texte_en_chemin(gras, titre, t1, cote_mm / 2, y1, cote_mm * 0.92)
    y2 = y1 + t2 * 1.6
    p2, t2 = texte_en_chemin(normal, SOUS_TITRE, t2, cote_mm / 2, y2, cote_mm * 0.92)
    h = y2 + t2 * 0.9 + mod * 2
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{cote_mm}mm" height="{h:.2f}mm" viewBox="0 0 {cote_mm} {h:.3f}">
<title>QR code · {titre} · {url}</title>
<rect width="{cote_mm}" height="{h:.3f}" fill="{FOND}"/>
<path fill="{ENCRE}" shape-rendering="crispEdges" d="{"".join(rects)}"/>
{p1}
{p2}
</svg>
'''
    chemin.write_text(svg, encoding="utf-8")
    print(f"{chemin.relative_to(RACINE)} · version {qr.version}, {n}×{n} modules, module {mod:.2f} mm · {url}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="identifiant d'un local (lien direct)")
    a = ap.parse_args()
    base = url_base()
    sortie = RACINE / "qr"
    sortie.mkdir(exist_ok=True)
    if a.local:
        d = json.loads((RACINE / "data" / "donnees.json").read_text(encoding="utf-8"))
        l = next((x for x in d["locaux"] if x["id"] == a.local), None)
        if not l:
            sys.exit(f"Local inconnu : {a.local}")
        url, titre, nom = f"{base}?local={a.local}", l["nom"], f"qr-{a.local}"
    else:
        url, titre, nom = base, "Plans et locaux techniques", "qr-accueil"
    for cm in (12, 5):
        qr_svg(url, titre, cm * 10, sortie / f"{nom}-{cm}cm.svg")


if __name__ == "__main__":
    main()
