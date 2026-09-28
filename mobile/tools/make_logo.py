# -*- coding: utf-8 -*-
"""Génère le logo FocusGuard v2 (1024×1024, pleine surface).

Composition : fond radial violet profond → noir, bouclier vitré (contour
violet lumineux qui suit la pointe), anneau de progression or, éclair
central dégradé or → blanc. Style cohérent avec l'UI (TimerRing + halo).

Usage : python make_logo.py
"""
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

S = 1024
cx, cy = S / 2, S / 2
R = 310          # demi-largeur du bouclier
RADIUS = 170     # arrondi des coins supérieurs

OUTER = (15, 9, 30)     # fond extrême
MID = (46, 24, 92)      # bouclier clair (haut)
DEEP = (24, 13, 48)     # bouclier sombre (bas)
EDGE = (139, 84, 245)   # liseré violet lumineux
GOLD = (255, 196, 77)
WHITE = (255, 255, 255)
GLOW = (88, 44, 178)

OUT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, "icon.png")
FG_PATH = os.path.join(OUT_DIR, "icon_adaptive_foreground.png")


def radial(size, inner, outer, cx_f=0.5, cy_f=0.42, spread=1.15):
    img = Image.new("RGB", (size, size), outer)
    px = img.load()
    c = size * 0.5
    ccx, ccy = size * cx_f, size * cy_f
    maxd = math.hypot(c, c) * spread
    for y in range(size):
        for x in range(size):
            d = math.hypot(x - ccx, y - ccy) / maxd
            t = min(1.0, d)
            px[x, y] = tuple(
                int(inner[i] + (outer[i] - inner[i]) * t) for i in range(3)
            )
    return img


def shield_mask():
    """Masque L du bouclier : rect arrondi + pointe, fondu ensemble."""
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((cx - R, cy - R, cx + R, cy + R), radius=RADIUS, fill=255)
    # Pointe : triangle large + ellipse de liaison pour un galbe régulier
    d.polygon(
        [(cx - R * 0.98, cy + R - 150), (cx + R * 0.98, cy + R - 150), (cx, cy + R + 118)],
        fill=255,
    )
    d.ellipse((cx - R * 0.98, cy + R - 260, cx + R * 0.98, cy + R - 60), fill=255)
    return m


def main():
    # 1. Fond pleine surface (halo haut-centré)
    img = radial(S, (52, 27, 104), OUTER).convert("RGBA")

    # 2. Halo lumineux derrière le bouclier
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((cx - 420, cy - 420, cx + 420, cy + 420), fill=GLOW + (110,))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img = Image.alpha_composite(img, glow)

    # 3. Bouclier : dégradé vertical clair→sombre via masque
    grad = Image.new("RGB", (S, S), DEEP)
    gdr = ImageDraw.Draw(grad)
    top, bottom = cy - R, cy + R + 118
    for y in range(S):
        t = max(0.0, min(1.0, (y - top) / (bottom - top)))
        col = tuple(int(MID[i] + (DEEP[i] - MID[i]) * t) for i in range(3))
        gdr.line([(0, y), (S, y)], fill=col)
    sm = shield_mask()
    shield_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shield_layer.paste(grad, (0, 0), sm)
    img = Image.alpha_composite(img, shield_layer)

    # 4. Contour lumineux : bords du masque colorisés
    inner = sm.filter(ImageFilter.MinFilter(9))   # érode de ~4 px
    edge_mask = ImageChops.subtract(sm, inner)
    edge_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    edge_layer.paste(EDGE, (0, 0), edge_mask)
    img = Image.alpha_composite(img, edge_layer)

    # 5. Anneau de progression (or) avec espace en haut à droite
    ring = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    box = (cx - 235, cy - 235, cx + 235, cy + 235)
    rd.arc(box, start=-60, end=262, fill=GOLD + (255,), width=20)
    img = Image.alpha_composite(img, ring)

    # 6. Éclair : dégradé or → blanc
    bolt = Image.new("L", (S, S), 0)
    bd = ImageDraw.Draw(bolt)
    pts = [
        (cx + 96, cy - 215),
        (cx - 100, cy + 30),
        (cx - 10, cy + 30),
        (cx - 96, cy + 220),
        (cx + 100, cy - 30),
        (cx + 10, cy - 30),
    ]
    bd.polygon(pts, fill=255)
    grad2 = Image.new("RGB", (S, S), WHITE)
    g2 = ImageDraw.Draw(grad2)
    for y in range(S):
        t = (y - (cy - 215)) / 435
        t = max(0.0, min(1.0, t))
        col = tuple(int(GOLD[i] + (WHITE[i] - GOLD[i]) * (t * t)) for i in range(3))
        g2.line([(0, y), (S, y)], fill=col)
    bolt_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bolt_layer.paste(grad2, (0, 0), bolt)
    img = Image.alpha_composite(img, bolt_layer)

    # 7. Export icône principale (pleine surface)
    img_rgb = img.convert("RGB")
    img_rgb.save(OUT_PATH)
    print("OK :", os.path.abspath(OUT_PATH), img_rgb.size)

    # 8. Variante foreground adaptive : art centré dans la zone sûre (66 %)
    fg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    art_size = int(S * 0.62)
    art = img_rgb.resize((art_size, art_size), Image.LANCZOS)
    off = (S - art_size) // 2
    fg.paste(art, (off, off))
    fg.save(FG_PATH)
    print("OK :", os.path.abspath(FG_PATH), fg.size)


if __name__ == "__main__":
    main()
