"""Beeld zonder betaalde API: gebrande OG-kaarten (1200x630) en meme-kaarten (1080x1080) met
Pillow. Eigen ontwerp, eigen fonts (OFL), geen auteursrechtelijk beschermde meme-templates."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import FONTS, SITE

INK = (11, 15, 25)
PAPER = (247, 246, 242)
ACCENT = (255, 90, 31)
MINT = (30, 200, 150)
VIOLET = (120, 90, 255)
MUTED = (120, 124, 135)


def _font(name: str, size: int, weight: str = "Regular"):
    f = ImageFont.truetype(str(FONTS / name), size)
    try:
        f.set_variation_by_name(weight)
    except Exception:  # noqa: BLE001
        pass
    return f


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit(draw, text, name, weight, max_w, max_h, start, floor=28):
    size = start
    while size >= floor:
        f = _font(name, size, weight)
        lines = _wrap(draw, text, f, max_w)
        lh = int(size * 1.12)
        if len(lines) * lh <= max_h:
            return f, lines, lh
        size -= 4
    f = _font(name, floor, weight)
    return f, _wrap(draw, text, f, max_w)[: max(1, max_h // int(floor * 1.12))], int(floor * 1.12)


def _blobs(img, seed: str):
    """Zachte gekleurde vormen op de achtergrond — per artikel anders, deterministisch."""
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    W, H = img.size
    cols = [ACCENT, MINT, VIOLET]
    for i in range(3):
        c = cols[(h >> (i * 4)) % 3]
        x = int(W * (0.15 + ((h >> (i * 7)) % 70) / 100))
        y = int(H * (0.1 + ((h >> (i * 5 + 3)) % 80) / 100))
        r = int(min(W, H) * (0.22 + ((h >> (i * 3)) % 20) / 100))
        d.ellipse((x - r, y - r, x + r, y + r), fill=c + (34,))
    img.alpha_composite(over)


def _brand(d, W, H, dark=True):
    fg = PAPER if dark else INK
    f = _font("Inter.ttf", 30, "SemiBold")
    d.rectangle((60, H - 92, 60 + 14, H - 78), fill=ACCENT)
    d.text((88, H - 100), SITE["domain"], font=f, fill=fg)


def og_card(title: str, category: str, out: Path, seed: str = "") -> Path:
    W, H = 1200, 630
    img = Image.new("RGBA", (W, H), INK + (255,))
    _blobs(img, seed or title)
    d = ImageDraw.Draw(img)
    cat_f = _font("Inter.ttf", 26, "SemiBold")
    d.text((60, 60), category.upper(), font=cat_f, fill=ACCENT)
    f, lines, lh = _fit(d, title, "Fraunces.ttf", "SemiBold", W - 120, 340, 76, 40)
    y = 120
    for ln in lines:
        d.text((60, y), ln, font=f, fill=PAPER)
        y += lh
    _brand(d, W, H)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out


def meme_card(top: str, bottom: str, out: Path, seed: str = "") -> Path:
    """Tekstmeme: twee panelen — situatie boven (papier), punchline onder (inkt)."""
    W, H = 1080, 1080
    img = Image.new("RGBA", (W, H), PAPER + (255,))
    d = ImageDraw.Draw(img)
    # bovenpaneel
    tag = _font("Inter.ttf", 28, "SemiBold")
    d.text((70, 64), "AI-MEME VAN DE DAG", font=tag, fill=ACCENT)
    f1, l1, lh1 = _fit(d, top, "Fraunces.ttf", "SemiBold", W - 140, 330, 68, 36)
    y = 130
    for ln in l1:
        d.text((70, y), ln, font=f1, fill=INK)
        y += lh1
    # onderpaneel
    d.rectangle((0, 540, W, H), fill=INK)
    _blobs(img, seed or bottom)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 540, W, 548), fill=ACCENT)
    f2, l2, lh2 = _fit(d, bottom, "Fraunces.ttf", "Black", W - 140, 340, 84, 40)
    y = 600
    for ln in l2:
        d.text((70, y), ln, font=f2, fill=PAPER)
        y += lh2
    _brand(d, W, H)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out


def prompt_card(title: str, prompt: str, out: Path) -> Path:
    W, H = 1200, 630
    img = Image.new("RGBA", (W, H), PAPER + (255,))
    d = ImageDraw.Draw(img)
    d.text((60, 56), "PROMPT VAN DE DAG", font=_font("Inter.ttf", 26, "SemiBold"), fill=ACCENT)
    f, lines, lh = _fit(d, title, "Fraunces.ttf", "SemiBold", W - 120, 150, 60, 34)
    y = 104
    for ln in lines:
        d.text((60, y), ln, font=f, fill=INK)
        y += lh
    y += 24
    box_top = y
    d.rounded_rectangle((60, box_top, W - 60, H - 120), radius=18, fill=INK)
    mono = _font("Inter.ttf", 26, "Medium")
    pl = _wrap(d, prompt, mono, W - 180)[:6]
    yy = box_top + 24
    for ln in pl:
        d.text((90, yy), ln, font=mono, fill=PAPER)
        yy += 34
    if len(_wrap(d, prompt, mono, W - 180)) > 6:
        d.text((90, yy), "…", font=mono, fill=MUTED)
    _brand(d, W, H, dark=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out


def logo_png(out: Path, size: int = 512) -> Path:
    img = Image.new("RGBA", (size, size), INK + (255,))
    d = ImageDraw.Draw(img)
    r = size * 0.18
    d.rounded_rectangle((size * 0.14, size * 0.2, size * 0.86, size * 0.72), radius=r, fill=PAPER)
    # spreekbubbel-punt
    d.polygon([(size * 0.32, size * 0.72), (size * 0.30, size * 0.86), (size * 0.48, size * 0.72)], fill=PAPER)
    f = _font("Fraunces.ttf", int(size * 0.34), "Black")
    d.text((size * 0.5, size * 0.46), "?", font=f, fill=ACCENT, anchor="mm")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    return out
