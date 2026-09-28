"""ICON promo reel — animatic renderer (1080x1920, 30 fps).

Builds the full 9:16 timeline. App screens and logo are the untouched
reference images in assets/ref; live-action shots are marked placeholders
until they are generated (see reel/PRODUCCION.md).

Usage: python3 reel/render.py            -> reel/out/icon_reel_animatic.mp4
       python3 reel/render.py --stills   -> one PNG per segment in reel/out/stills
"""
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "assets", "ref")
FONTS = os.path.join(ROOT, "assets", "fonts")
OUT = os.path.join(ROOT, "reel", "out")
W, H, FPS = 1080, 1920, 30

# ICON identity: lilac / violet / silver / cream / white. No pink.
LILAC_LOGO = (189, 161, 245)   # sampled from the logo background
LILAC_LIGHT = (243, 239, 252)
LILAC_MID = (217, 204, 246)
VIOLET = (123, 99, 201)
VIOLET_DEEP = (62, 47, 115)
CREAM = (250, 246, 238)
WHITE = (255, 255, 255)


# ---------------------------------------------------------------- helpers
def font(name, size, weight=None):
    path = {
        "serif": "PlayfairDisplay[wght].ttf",
        "sans": "Inter[opsz,wght].ttf",
    }[name]
    f = ImageFont.truetype(os.path.join(FONTS, path), size)
    if weight is not None:
        try:
            f.set_variation_by_axes([weight] if name == "serif" else [14, weight])
        except Exception:
            pass
    return f


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, t0, t1):
    return clamp((t - t0) / (t1 - t0)) if t1 > t0 else 1.0


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    return 3 * x * x - 2 * x * x * x


def ease_back(x, s=1.6):
    x -= 1
    return x * x * ((s + 1) * x + s) + 1


def vgradient(size, top, bottom):
    w, h = size
    arr = np.linspace(0, 1, h)[:, None, None]
    a = np.array(top, float)[None, None, :]
    b = np.array(bottom, float)[None, None, :]
    img = (a + (b - a) * arr).repeat(w, axis=1)
    return Image.fromarray(img.astype(np.uint8), "RGB")


def rounded_mask(size, r):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), r, fill=255)
    return m


def card(img, width, radius=44, shadow=True):
    """Screenshot as a floating rounded card (RGBA) with a soft shadow."""
    h = round(img.height * width / img.width)
    body = img.convert("RGB").resize((width, h), Image.LANCZOS)
    pad = 70 if shadow else 0
    out = Image.new("RGBA", (width + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle(
            (pad, pad + 24, pad + width, pad + h + 24), radius, fill=(60, 40, 120, 90))
        out = Image.alpha_composite(out, sh.filter(ImageFilter.GaussianBlur(28)))
    rgba = body.convert("RGBA")
    rgba.putalpha(rounded_mask(body.size, radius))
    out.alpha_composite(rgba, (pad, pad))
    # thin silver rim
    ImageDraw.Draw(out).rounded_rectangle(
        (pad, pad, pad + width - 1, pad + h - 1), radius, outline=(255, 255, 255, 150), width=2)
    return out


def paste_center(base, layer, cx, cy, scale=1.0, alpha=1.0):
    if alpha <= 0 or scale <= 0:
        return
    if scale != 1.0:
        layer = layer.resize((max(1, round(layer.width * scale)), max(1, round(layer.height * scale))),
                             Image.BILINEAR)
    if alpha < 1.0:
        layer = layer.copy()
        a = layer.getchannel("A").point(lambda v: int(v * alpha))
        layer.putalpha(a)
    base.alpha_composite(layer, (round(cx - layer.width / 2), round(cy - layer.height / 2)))


def text_layer(txt, fnt, fill, spacing=10, align="center", stroke=0, stroke_fill=None):
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    box = d.multiline_textbbox((0, 0), txt, font=fnt, spacing=spacing, align=align, stroke_width=stroke)
    w, h = int(box[2] - box[0] + 8), int(box[3] - box[1] + 8)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).multiline_text((4 - box[0], 4 - box[1]), txt, font=fnt, fill=fill, spacing=spacing,
                                      align=align, stroke_width=stroke, stroke_fill=stroke_fill)
    return im


def silver_text(txt, fnt):
    """Text filled with a vertical silver gradient (matches the logo metal)."""
    mask = text_layer(txt, fnt, (255, 255, 255, 255)).getchannel("A")
    g = vgradient(mask.size, (252, 252, 255), (160, 160, 172)).convert("RGBA")
    g.putalpha(mask)
    return g


def pill(txt, fnt, fg, bg, pad=(34, 16), outline=None):
    t = text_layer(txt, fnt, fg)
    w, h = t.width + 2 * pad[0], t.height + 2 * pad[1]
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=bg, outline=outline, width=2)
    im.alpha_composite(t, (pad[0], pad[1]))
    return im


def sparkle(size, color=(255, 255, 255, 255)):
    """Four-point star like the one on the ICON logo."""
    s = size
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    c = s / 2
    pts = []
    for i in range(8):
        ang = math.pi / 4 * i - math.pi / 2
        r = c if i % 2 == 0 else c * 0.18
        pts.append((c + r * math.cos(ang), c + r * math.sin(ang)))
    ImageDraw.Draw(im).polygon(pts, fill=color)
    return im.filter(ImageFilter.GaussianBlur(0.6))


# ---------------------------------------------------------------- assets
def load(name):
    return Image.open(os.path.join(REF, name)).convert("RGB")


LOGO = load("logo.jpg")
ARMARIO = load("app_armario.jpg")
PALETA = load("app_paleta.jpg")
LOOK = load("app_look.jpg")
PRUEBA = load("app_prueba.jpg")

GRID_X = [(82, 320), (338, 576), (596, 834)]
GRID_Y = [(433, 686), (702, 946), (963, 1209), (1226, 1428)]


def tile(r, c):
    (x0, x1), (y0, y1) = GRID_X[c], GRID_Y[r]
    return ARMARIO.crop((x0, y0, x1, y1))


ITEMS = {
    "musculosa": tile(0, 0), "blazer": tile(0, 1), "pantalon": tile(0, 2),
    "vestido": tile(1, 0), "sweater": tile(1, 1), "campera": tile(1, 2),
    "jean": tile(2, 0), "cartera": tile(2, 1), "zapatillas": tile(2, 2),
    "pollera": tile(3, 0), "aros": tile(3, 1), "sandalias": tile(3, 2),
}
TOP_BORDO = PRUEBA.crop((750, 405, 1005, 630))
LOOK_PHOTO = LOOK.crop((55, 278, 600, 1303))

F_HOOK = font("serif", 100, 600)
F_TITLE = font("serif", 64, 500)
F_CHIP = font("sans", 34, 500)
F_CAP = font("sans", 40, 500)
F_BODY = font("sans", 36, 400)
F_SMALL = font("sans", 28, 500)
F_TAG = font("sans", 26, 700)

BG_LIGHT = vgradient((W, H), LILAC_LIGHT, LILAC_MID).convert("RGBA")
BG_DEEP = vgradient((W, H), (44, 33, 86), (118, 98, 190)).convert("RGBA")


def light_bg(t):
    """Soft lilac background with a slow diagonal light sweep."""
    im = BG_LIGHT.copy()
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    x = -400 + (t * 90) % (W + 800)
    ImageDraw.Draw(glow).ellipse((x - 380, 250, x + 380, 1650), fill=(255, 255, 255, 70))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(120)))
    return im


def chip(base, txt, t, t0, y=150):
    p = ease_out(prog(t, t0, t0 + 0.35))
    c = pill("      " + txt, F_CHIP, VIOLET_DEEP + (255,), (255, 255, 255, 215), outline=(255, 255, 255, 255))
    c.alpha_composite(sparkle(34, VIOLET + (255,)), (30, (c.height - 34) // 2))
    paste_center(base, c, W / 2, y + (1 - p) * 30, alpha=p)


def caption(base, txt, t, t0, t1, y=1740):
    """VO line as a subtitle (animatic only; final cut keeps text minimal)."""
    a = prog(t, t0, t0 + 0.2) * (1 - prog(t, t1 - 0.2, t1))
    if a <= 0:
        return
    c = pill(txt, F_CAP, WHITE + (255,), (62, 47, 115, 190), pad=(30, 14))
    paste_center(base, c, W / 2, y, alpha=a)


def placeholder(base, t, scene, lines, ref=None):
    """Marked slot for a live-action shot that still has to be generated."""
    im = BG_DEEP.copy()
    base.alpha_composite(im)
    d = ImageDraw.Draw(base)
    m = 56
    col = (210, 210, 225, 120)
    for x in range(m, W - m, 36):
        d.line((x, m, min(x + 20, W - m), m), fill=col, width=3)
        d.line((x, H - m, min(x + 20, W - m), H - m), fill=col, width=3)
    for y in range(m, H - m, 36):
        d.line((m, y, m, min(y + 20, H - m)), fill=col, width=3)
        d.line((W - m, y, W - m, min(y + 20, H - m)), fill=col, width=3)
    tag = pill("TOMA REAL · " + scene, F_TAG, VIOLET_DEEP + (255,), (235, 235, 245, 235), pad=(22, 10))
    base.alpha_composite(tag, (m + 30, m + 30))
    if ref is not None:
        r = card(ref, 430)
        paste_center(base, r, W / 2, 1130, scale=1 + 0.02 * t, alpha=0.9)
    if not lines:
        return
    body = text_layer(lines, F_BODY, (235, 230, 250, 230), spacing=14)
    paste_center(base, body, W / 2, 1620 if ref is not None else 930)


# ---------------------------------------------------------------- segments
def seg_hook(t):
    base = Image.new("RGBA", (W, H))
    placeholder(base, t, "ESCENA 1 · EL PROBLEMA",
                "Su cuarto, placard abierto, ropa sobre la cama.\n"
                "Levanta dos prendas, duda, resopla.\nCámara en mano, cortes rápidos.")
    # clothes floating around her = "tengo ropa pero no sé qué ponerme"
    order = ["blazer", "vestido", "jean", "sweater", "campera", "pollera", "musculosa", "pantalon"]
    spots = [(230, 1180), (850, 1150), (190, 1420), (890, 1410), (540, 1300), (340, 1600), (760, 1600), (540, 1520)]
    for i, (k, (x, y)) in enumerate(zip(order, spots)):
        p = ease_back(prog(t, 1.2 + i * 0.18, 1.6 + i * 0.18))
        if p <= 0:
            continue
        c = card(ITEMS[k], 190, radius=26).rotate(math.sin(i * 1.7) * 12, expand=True, resample=Image.BICUBIC)
        wob = math.sin(t * 2 + i) * 8
        paste_center(base, c, x, y + wob, scale=0.2 + 0.8 * p, alpha=min(1, p) * 0.95)
    # hook: exact line, word by word
    words = "¿Otra vez no sabés qué ponerte?".split(" ")
    lines = [" ".join(words[:3]), " ".join(words[3:])]
    shown = 0
    for li, line in enumerate(lines):
        ws = line.split(" ")
        for wi in range(len(ws)):
            shown += 1
        y = 520 + li * 130
        k = sum(len(l.split(" ")) for l in lines[:li])
        n = len(ws)
        # progressive reveal per word
        acc = ""
        for wi, w in enumerate(ws):
            p = ease_out(prog(t, 0.25 + (k + wi) * 0.16, 0.45 + (k + wi) * 0.16))
            if p <= 0:
                break
            acc = (acc + " " + w).strip()
        if acc:
            full = text_layer(line, F_HOOK, WHITE + (255,))
            part = text_layer(acc, F_HOOK, WHITE + (255,), stroke=0)
            shadow = text_layer(acc, F_HOOK, (30, 20, 70, 140)).filter(ImageFilter.GaussianBlur(8))
            x0 = W / 2 - full.width / 2
            base.alpha_composite(shadow, (round(x0 + 4), round(y - full.height / 2 + 8)))
            base.alpha_composite(part, (round(x0), round(y - full.height / 2)))
    caption(base, "Tenés el placard lleno… y nada te convence.", t, 2.2, 4.8)
    return base


def seg_open(t):
    base = Image.new("RGBA", (W, H))
    if t < 1.1:
        placeholder(base, t, "ESCENA 2 · ICON APARECE",
                    "Se sienta en la cama, saca el celular\ny abre ICON. Primer plano de la mano\n"
                    "y la pantalla iluminándole la cara.")
    else:
        placeholder(base, t, "ESCENA 2 · ICON APARECE", "")
        p = ease_in_out(prog(t, 1.1, 1.6))
        splash = Image.new("RGBA", (W, H), LILAC_LOGO + (255,))
        lg = LOGO.convert("RGBA")
        s = (W - 80) / lg.width * (0.94 + 0.06 * ease_out(prog(t, 1.1, 2.2)))
        paste_center(splash, lg, W / 2, H / 2, scale=s)
        mask = Image.new("L", (W, H), 0)
        r = p * 1200
        ImageDraw.Draw(mask).ellipse((W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r), fill=255)
        base.paste(splash, (0, 0), mask)
    caption(base, "Tranqui. Abrí ICON.", t, 0.1, 2.2)
    return base


_EMPTY = None


def empty_armario():
    """Wardrobe screen with every grid cell emptied (glass tile only)."""
    global _EMPTY
    if _EMPTY is None:
        im = ARMARIO.copy()
        for r in range(4):
            for c in range(3):
                (x0, x1), (y0, y1) = GRID_X[c], GRID_Y[r]
                t_ = im.crop((x0, y0, x1, y1))
                edge = np.concatenate([np.asarray(t_)[:6].reshape(-1, 3), np.asarray(t_)[-6:].reshape(-1, 3)])
                col = tuple(int(v) for v in np.median(edge, axis=0))
                fill = Image.new("RGB", t_.size, col)
                m = rounded_mask(t_.size, 22).filter(ImageFilter.GaussianBlur(1))
                blurred = t_.filter(ImageFilter.GaussianBlur(40))
                im.paste(Image.blend(fill, blurred, 0.35), (x0, y0), m)
        _EMPTY = im
    return _EMPTY


def seg_wardrobe(t):
    base = light_bg(t)
    cw = 800
    s = cw / ARMARIO.width
    scr = empty_armario().copy()
    order = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2), (3, 0), (3, 1), (3, 2)]
    layer_cells = []
    for i, (r, c) in enumerate(order):
        p = prog(t, 0.55 + i * 0.16, 0.9 + i * 0.16)
        if p > 0:
            layer_cells.append((r, c, ease_back(p)))
    for r, c, p in layer_cells:
        (x0, x1), (y0, y1) = GRID_X[c], GRID_Y[r]
        tl = tile(r, c)
        sc = 0.55 + 0.45 * p
        tw, th = max(1, round(tl.width * sc)), max(1, round(tl.height * sc))
        tl2 = tl.resize((tw, th), Image.BILINEAR)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        scr.paste(tl2, (round(cx - tw / 2), round(cy - th / 2)), rounded_mask((tw, th), 22))
    enter = ease_out(prog(t, 0.0, 0.45))
    cd = card(scr, cw)
    cy = 960 + (1 - enter) * 500
    paste_center(base, cd, W / 2, cy, scale=0.96 + 0.04 * enter, alpha=enter)
    # sparkle on the newest tile
    if layer_cells and t < 2.9:
        r, c, p = layer_cells[-1]
        (x0, x1), (y0, y1) = GRID_X[c], GRID_Y[r]
        top = cy - ARMARIO.height * s / 2
        sx = W / 2 - cw / 2 + x1 * s - 20
        sy = top + y0 * s + 20
        paste_center(base, sparkle(56), sx, sy, scale=0.6 + 0.4 * math.sin(t * 12) ** 2)
    chip(base, "Subí tu ropa · armario digital", t, 0.2)
    caption(base, "Subí tu ropa y armá tu armario digital.", t, 0.3, 3.2)
    return base


def seg_palette(t):
    base = light_bg(t + 3)
    e = ease_out(prog(t, 0, 0.35))
    paste_center(base, card(PALETA, 860), W / 2, 960, scale=0.9 + 0.1 * e + 0.02 * t, alpha=e)
    chip(base, "Analiza tu paleta ideal", t, 0.05)
    caption(base, "ICON combina tus prendas…", t, 0.1, 1.0)
    return base


def slot_panel(pieces, labels, t, t0, title, sub=None):
    """Glass panel with 2x2 slots; pieces drop in one by one."""
    pw, ph = 900, 1180
    panel = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle((0, 0, pw - 1, ph - 1), 48, fill=(255, 255, 255, 170),
                                            outline=(255, 255, 255, 255), width=3)
    tt = text_layer(title, F_TITLE, VIOLET_DEEP + (255,))
    panel.alpha_composite(tt, (60, 50))
    panel.alpha_composite(sparkle(46, VIOLET + (255,)), (60 + tt.width + 18, 70))
    if sub:
        panel.alpha_composite(text_layer(sub, F_SMALL, (110, 95, 170, 255)), (62, 50 + tt.height + 10))
    sw, sh = 370, 430
    pos = [(60, 250), (470, 250), (60, 720), (470, 720)]
    for i, (x, y) in enumerate(pos):
        ImageDraw.Draw(panel).rounded_rectangle((x, y, x + sw, y + sh), 34, fill=(236, 230, 250, 255))
        lb = text_layer(labels[i], F_SMALL, (120, 104, 180, 255))
        panel.alpha_composite(lb, (int(x + 24), int(y + sh - 52)))
    for i, (x, y) in enumerate(pos):
        p = prog(t, t0 + i * 0.32, t0 + 0.35 + i * 0.32)
        if p <= 0 or pieces[i] is None:
            continue
        im = pieces[i]
        k = min((sw - 30) / im.width, (sh - 80) / im.height)
        piece = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS).convert("RGBA")
        piece.putalpha(rounded_mask(piece.size, 26))
        e = ease_back(p)
        layer = Image.new("RGBA", panel.size, (0, 0, 0, 0))
        cx, cy = x + sw / 2, y + (sh - 60) / 2 + 8
        paste_center(layer, piece, cx, cy - (1 - min(1, e)) * 60, scale=0.7 + 0.3 * e, alpha=min(1, p * 2))
        panel.alpha_composite(layer)
    return panel


def seg_assemble(t):
    base = light_bg(t + 4)
    pieces = [ITEMS["musculosa"], ITEMS["pantalon"], ITEMS["zapatillas"], ITEMS["cartera"]]
    panel = slot_panel(pieces, ["Top", "Abajo", "Calzado", "Accesorio"], t, 0.25,
                       "Creando tu look", "Con lo que ya tenés en tu armario")
    e = ease_out(prog(t, 0, 0.3))
    paste_center(base, panel, W / 2, 1010, alpha=e)
    chip(base, "Outfit personalizado", t, 0.0)
    caption(base, "…y te arma el look completo.", t, 0.1, 2.0)
    return base


def seg_look(t):
    base = light_bg(t + 6)
    e = ease_out(prog(t, 0, 0.35))
    paste_center(base, card(LOOK, 930), W / 2, 960, scale=0.92 + 0.08 * e + 0.015 * t, alpha=e)
    chip(base, "Outfit + maquillaje + peinado", t, 0.05)
    return base


def seg_context(t):
    base = light_bg(t + 8)
    night = t >= 1.6
    flip = prog(t, 1.6, 2.4)
    dia = [ITEMS["blazer"], ITEMS["musculosa"], ITEMS["pantalon"], ITEMS["cartera"]]
    noche = [ITEMS["campera"], ITEMS["vestido"], ITEMS["sandalias"], ITEMS["aros"]]
    labels_d = ["Blazer", "Top", "Pantalón", "Cartera"]
    labels_n = ["Campera", "Vestido", "Sandalias", "Aros"]
    if not night:
        panel = slot_panel(dia, labels_d, 9, 0, "Plan: Día", "Oficina · reunión · almuerzo")
    else:
        # staggered flip of each slot to the night version
        panel = slot_panel([None] * 4, [""] * 4, 9, 0, "Plan: Noche", "Salida · cumple · evento")
        sw, sh = 370, 430
        pos = [(60, 250), (470, 250), (60, 720), (470, 720)]
        for i, (x, y) in enumerate(pos):
            p = prog(t, 1.6 + i * 0.18, 1.95 + i * 0.18)
            im = dia[i] if p < 0.5 else noche[i]
            lb = text_layer(labels_d[i] if p < 0.5 else labels_n[i], F_SMALL, (120, 104, 180, 255))
            panel.alpha_composite(lb, (int(x + 24), int(y + sh - 52)))
            k = min((sw - 30) / im.width, (sh - 80) / im.height)
            piece = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS).convert("RGBA")
            piece.putalpha(rounded_mask(piece.size, 26))
            sx = abs(math.cos(p * math.pi))
            if sx < 0.02:
                continue
            piece = piece.resize((max(1, round(piece.width * sx)), piece.height), Image.BILINEAR)
            layer = Image.new("RGBA", panel.size, (0, 0, 0, 0))
            paste_center(layer, piece, x + sw / 2, y + (sh - 60) / 2 + 8)
            panel.alpha_composite(layer)
    e = ease_out(prog(t, 0, 0.3))
    paste_center(base, panel, W / 2, 1060, alpha=e)
    # Día / Noche toggle
    tw, th = 520, 96
    tg = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(tg)
    d.rounded_rectangle((0, 0, tw - 1, th - 1), th // 2, fill=(255, 255, 255, 200), outline=(255, 255, 255, 255), width=2)
    kx = 6 + (tw / 2 - 6) * ease_in_out(prog(t, 1.35, 1.65))
    d.rounded_rectangle((kx, 6, kx + tw / 2 - 12, th - 7), (th - 12) // 2, fill=VIOLET + (255,))
    for i, lbl in enumerate(["Día", "Noche"]):
        active = (i == 1) == (t >= 1.5)
        tl = text_layer(lbl, F_CHIP, (WHITE if active else VIOLET_DEEP) + (255,))
        tg.alpha_composite(tl, (round(tw / 4 + i * tw / 2 - tl.width / 2), round(th / 2 - tl.height / 2)))
    paste_center(base, tg, W / 2, 330, alpha=e)
    if 1.3 < t < 1.8:  # tap
        r = 30 + 60 * prog(t, 1.3, 1.8)
        ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse((W / 2 + 130 - r, 330 - r, W / 2 + 130 + r, 330 + r),
                                     outline=(123, 99, 201, int(200 * (1 - prog(t, 1.3, 1.8)))), width=6)
        base.alpha_composite(ring)
    chip(base, "Se adapta a la ocasión", t, 0.0)
    caption(base, "¿Salís de noche? El look se adapta a la ocasión.", t, 0.2, 3.6)
    return base


def seg_tryon(t):
    base = light_bg(t + 11)
    cw = 920
    e = ease_out(prog(t, 0, 0.35))
    scr = PRUEBA.copy()
    # scanning light over the try-on photo (inside the screenshot coords)
    x0, y0, x1, y1 = 50, 303, 700, 1297
    sy = y0 + (y1 - y0) * ((t * 0.55) % 1.0)
    ov = Image.new("RGBA", scr.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for k in range(40):
        a = int(110 * (1 - k / 40))
        d.line((x0, sy - k, x1, sy - k), fill=(190, 170, 250, a), width=1)
    d.line((x0, sy, x1, sy), fill=(255, 255, 255, 230), width=3)
    scr = Image.alpha_composite(scr.convert("RGBA"), ov).convert("RGB")
    paste_center(base, card(scr, cw), W / 2, 960, scale=0.93 + 0.07 * e + 0.012 * t, alpha=e)
    chip(base, "Prueba virtual", t, 0.05)
    caption(base, "Probátelo virtualmente, sin salir de casa.", t, 0.2, 3.2)
    return base


def seg_shop(t):
    base = light_bg(t + 14)
    pw, ph = 900, 1180
    panel = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)
    d.rounded_rectangle((0, 0, pw - 1, ph - 1), 48, fill=(255, 255, 255, 190), outline=(255, 255, 255, 255), width=3)
    im = TOP_BORDO
    k = 520 / im.height
    prod = im.resize((round(im.width * k), 520), Image.LANCZOS).convert("RGBA")
    d.rounded_rectangle((60, 60, pw - 60, 620), 36, fill=(236, 230, 250, 255))
    panel.alpha_composite(prod, (round(pw / 2 - prod.width / 2), 80))
    panel.alpha_composite(text_layer("Top corset bordó", F_TITLE, VIOLET_DEEP + (255,)), (60, 660))
    # rating (animated fill)
    p = prog(t, 0.5, 1.3)
    for i in range(5):
        fillv = clamp(p * 5 - i)
        col = (123, 99, 201, 255) if fillv > 0.5 else (205, 195, 235, 255)
        panel.alpha_composite(sparkle(44, col), (62 + i * 52, 770))
    panel.alpha_composite(text_layer("4,8  ·  1.248 reseñas", F_BODY, (110, 95, 170, 255)), (340, 772))
    rows = [("Precio", "$ 32.500"), ("Talles", "XS – L"), ("Envío", "24–48 h")]
    for i, (a_, b_) in enumerate(rows):
        pr = ease_out(prog(t, 0.9 + i * 0.2, 1.2 + i * 0.2))
        if pr <= 0:
            continue
        y = 850 + i * 68
        la = text_layer(a_, F_BODY, (120, 104, 180, int(255 * pr)))
        lb = text_layer(b_, F_BODY if i else font("sans", 40, 700), (62, 47, 115, int(255 * pr)))
        panel.alpha_composite(la, (62, y))
        panel.alpha_composite(lb, (pw - 62 - lb.width, y - (2 if i == 0 else 0)))
    btn_p = ease_back(prog(t, 1.7, 2.1))
    if btn_p > 0:
        btn = pill("Dónde comprarlo  ›", font("sans", 40, 600), WHITE + (255,), VIOLET + (255,), pad=(60, 22))
        paste_center(panel, btn, pw / 2, 1100, scale=0.8 + 0.2 * btn_p, alpha=min(1, btn_p))
    e = ease_out(prog(t, 0, 0.3))
    paste_center(base, panel, W / 2, 1010, alpha=e, scale=0.96 + 0.04 * e)
    chip(base, "Dónde comprar · precio · reseñas", t, 0.0)
    caption(base, "Y si te falta algo, te dice dónde comprarlo.", t, 0.1, 3.0)
    return base


def seg_result(t):
    base = Image.new("RGBA", (W, H))
    placeholder(base, t, "ESCENA 4 · EL RESULTADO",
                "Selfie en el espejo con el look de ICON.\nSonríe, se acomoda el blazer, gira.\n"
                "Mismo cuarto, mismo celular.", ref=LOOK_PHOTO)
    caption(base, "Por fin sé qué ponerme.", t, 0.5, 3.3, y=1800)
    return base


def seg_end(t):
    base = Image.new("RGBA", (W, H), LILAC_LOGO + (255,))
    e = ease_out(prog(t, 0.0, 0.8))
    lg = LOGO.convert("RGBA")
    s = (W - 80) / lg.width
    paste_center(base, lg, W / 2, H / 2, scale=s * (0.96 + 0.04 * e), alpha=e)
    return base


SEGMENTS = [  # (name, start, end, fn)
    ("hook", 0.0, 4.8, seg_hook),
    ("open", 4.8, 7.0, seg_open),
    ("wardrobe", 7.0, 10.2, seg_wardrobe),
    ("palette", 10.2, 11.2, seg_palette),
    ("assemble", 11.2, 13.2, seg_assemble),
    ("look", 13.2, 14.8, seg_look),
    ("context", 14.8, 18.4, seg_context),
    ("tryon", 18.4, 21.6, seg_tryon),
    ("shop", 21.6, 24.6, seg_shop),
    ("result", 24.6, 28.0, seg_result),
    ("end", 28.0, 31.5, seg_end),
]
DURATION = SEGMENTS[-1][2]
XFADE = 0.2


def frame(t):
    for i, (_, t0, t1, fn) in enumerate(SEGMENTS):
        if t0 <= t < t1 or (i == len(SEGMENTS) - 1 and t >= t0):
            cur = fn(t - t0)
            if i > 0 and t - t0 < XFADE:
                _, p0, p1, pfn = SEGMENTS[i - 1]
                prev = pfn(p1 - p0 - 1e-3)
                a = ease_in_out((t - t0) / XFADE)
                cur = Image.blend(prev, cur, a)
            return cur.convert("RGB")


# ---------------------------------------------------------------- audio
def music(path, dur=DURATION, sr=44100):
    """Light, airy synth bed (no samples): pad + pluck arpeggio + soft kick."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    bar = 2.4  # 100 bpm, 4/4
    chords = [[62, 66, 69, 73, 76], [59, 62, 66, 69, 73], [55, 59, 62, 66, 69], [57, 61, 64, 66, 69]]
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    for b in range(int(dur / bar) + 1):
        ch = chords[b % 4]
        s0, s1 = int(b * bar * sr), min(n, int((b + 1) * bar * sr + 0.4 * sr))
        if s0 >= n:
            break
        tt = t[s0:s1] - b * bar
        env = np.minimum(1, tt / 0.6) * np.exp(-tt * 0.25)
        for m in ch:
            f = hz(m - 12)
            out[s0:s1] += 0.05 * env * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2.003 * f * tt))
        # pluck arpeggio from the problem->solution turn onwards
        if b * bar >= 4.8:
            for k in range(8):
                ps = int((b * bar + k * bar / 8) * sr)
                if ps >= n:
                    break
                pe = min(n, ps + int(0.5 * sr))
                pt = t[ps:pe] - t[ps]
                f = hz(ch[[0, 2, 4, 2, 1, 3, 4, 3][k]] + 12)
                out[ps:pe] += 0.06 * np.exp(-pt * 9) * np.sin(2 * np.pi * f * pt)
        # soft kick during the feature run
        if 7.0 <= b * bar < 24.6:
            for k in range(4):
                ks = int((b * bar + k * bar / 4) * sr)
                ke = min(n, ks + int(0.25 * sr))
                if ks >= n:
                    break
                kt = t[ks:ke] - t[ks]
                out[ks:ke] += 0.22 * np.exp(-kt * 22) * np.sin(2 * np.pi * (48 + 90 * np.exp(-kt * 30)) * kt)
    rng = np.random.default_rng(7)
    for _, t0, _, _ in SEGMENTS[1:]:  # whoosh on every cut
        ws, we = int((t0 - 0.35) * sr), int((t0 + 0.15) * sr)
        wt = np.linspace(0, 1, we - ws)
        noise = np.convolve(rng.standard_normal(we - ws), np.ones(40) / 40, "same")
        out[ws:we] += 0.18 * noise * np.sin(np.pi * wt) ** 2
    # chime on the logo
    cs = int(28.1 * sr)
    ct = t[cs:] - t[cs]
    for f in (hz(86), hz(90), hz(93)):
        out[cs:] += 0.05 * np.exp(-ct * 1.6) * np.sin(2 * np.pi * f * ct)
    fade = np.minimum(1, (dur - t) / 1.2)
    out *= np.clip(fade, 0, 1) * np.minimum(1, t / 0.4)
    out /= max(1e-9, np.max(np.abs(out))) / 0.7
    st = np.stack([out, out], 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((st * 32767).astype(np.int16).tobytes())


def ffmpeg_bin():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def main():
    os.makedirs(OUT, exist_ok=True)
    if "--stills" in sys.argv:
        sd = os.path.join(OUT, "stills")
        os.makedirs(sd, exist_ok=True)
        for name, t0, t1, fn in SEGMENTS:
            fn(min(t1 - t0 - 0.05, max(0.9 * (t1 - t0), 0))).convert("RGB").save(os.path.join(sd, f"{name}.jpg"), quality=88)
        return
    wav = os.path.join(OUT, "music.wav")
    music(wav)
    mp4 = os.path.join(OUT, "icon_reel_animatic.mp4")
    cmd = [ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", mp4]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total = int(DURATION * FPS)
    for i in range(total):
        p.stdin.write(frame(i / FPS).tobytes())
        if i % 60 == 0:
            print(f"{i}/{total}", flush=True)
    p.stdin.close()
    p.wait()
    print(mp4)


if __name__ == "__main__":
    main()
