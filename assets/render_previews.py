#!/usr/bin/env python3
"""Headless preview renderer: animated GIF + poster PNG per visualization.

Uses Pillow ONLY for pre-rendering repo assets — the screensaver itself
stays 100%% stdlib. Run from repo root:  python assets/render_previews.py
"""

import os
import importlib.util

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "spectral_geometry", os.path.join(ROOT, "spectral_geometry.py")
)
sg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sg)

W, H = 480, 300
POSTER_W, POSTER_H = 960, 600
FRAMES = 84
DT = 1 / 30
BG = (6, 8, 12)

# колко кадъра "загрявка" преди записа (динамиките имат нужда от контекст;
# Three-Body нарочно 0 — формирането на осмицата Е кадърът)
WARMUP = {
    "Three-Body Ballet": 0,
    "Murmuration Wars": 420,
    "Chaos Butterflies": 90,
    "Clifford Attractor": 30,
}


def hex_to_rgb(c):
    return tuple(int(c[i : i + 2], 16) for i in (1, 3, 5))


def render_frame(lines, w, h, scale):
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    for x1, y1, x2, y2, color, lw in lines:
        rgb = hex_to_rgb(color)
        x1, y1, x2, y2 = x1 * scale, y1 * scale, x2 * scale, y2 * scale
        wpx = max(1, round(lw * scale))
        if abs(x2 - x1) < 1.5 and abs(y2 - y1) < 1.5:  # "точка" (capstyle round)
            r = wpx / 2
            d.ellipse((x1 - r, y1 - r, x1 + r, y1 + r), fill=rgb)
        else:
            d.line((x1, y1, x2, y2), fill=rgb, width=wpx)
    return img


def main():
    out_dir = os.path.join(ROOT, "assets")
    slugs = []
    for cls in sg.VISUALIZATIONS:
        viz = cls()
        slug = viz.name.lower().replace(" ", "-")
        slugs.append((slug, viz.name))
        warm = WARMUP.get(viz.name, 150)
        for _ in range(warm):
            viz.update(DT)
        # GIF: рендерираме в "виртуален екран" 960x600, после мащаб 0.5
        frames = []
        for _ in range(FRAMES):
            viz.update(DT)
            lines = viz.get_lines(
                POSTER_W / 2, POSTER_H / 2 + 15, min(POSTER_W, POSTER_H) * 0.36
            )
            frames.append(render_frame(lines, W, H, 0.5))
        gif_path = os.path.join(out_dir, f"{slug}.gif")
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            duration=40,
            loop=0,
            optimize=True,
        )
        # Poster: още 40 кадъра напред, пълна резолюция
        for _ in range(40):
            viz.update(DT)
        lines = viz.get_lines(
            POSTER_W / 2, POSTER_H / 2 + 15, min(POSTER_W, POSTER_H) * 0.36
        )
        poster = render_frame(lines, POSTER_W, POSTER_H, 1.0)
        poster.save(os.path.join(out_dir, f"{slug}.png"), optimize=True)
        kb = os.path.getsize(gif_path) // 1024
        print(f"OK {viz.name:22} {slug}.gif ({kb} KB) + poster")
    print("DONE", len(slugs), "visualizations")


if __name__ == "__main__":
    main()
