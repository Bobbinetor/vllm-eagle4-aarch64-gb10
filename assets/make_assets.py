#!/usr/bin/env python3
"""Generate the README diagrams with Pillow. Not needed to use the wheel."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

BG = "#0B1220"
PANEL = "#121C2C"
PANEL_2 = "#0F1726"
BORDER = "#26364D"
TEXT = "#E6EDF3"
MUTED = "#8B9BB4"
GREEN = "#76B900"
BLUE = "#4C8DFF"
ORANGE = "#FFB86B"
RED = "#FF7B72"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def text(draw: ImageDraw.ImageDraw, xy, s, size=24, fill=TEXT, bold=False, anchor="la"):
    draw.text(xy, s, font=font(size, bold), fill=fill, anchor=anchor)


def panel(draw: ImageDraw.ImageDraw, box, fill=PANEL, outline=BORDER, radius=22, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def arrow(draw: ImageDraw.ImageDraw, start, end, color, width=3, head=12):
    draw.line([start, end], fill=color, width=width)
    (x1, y1), (x2, y2) = start, end
    if abs(x2 - x1) >= abs(y2 - y1):
        sign = 1 if x2 > x1 else -1
        pts = [(x2, y2), (x2 - sign * head, y2 - head * 0.6), (x2 - sign * head, y2 + head * 0.6)]
    else:
        sign = 1 if y2 > y1 else -1
        pts = [(x2, y2), (x2 - head * 0.6, y2 - sign * head), (x2 + head * 0.6, y2 - sign * head)]
    draw.polygon(pts, fill=color)


def architecture():
    w, h = 1600, 940
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    text(d, (80, 54), "DGX SPARK  ·  GB10  ·  AARCH64  ·  SM_121", 20, GREEN, bold=True)
    text(d, (80, 96), "EAGLE-4 speculative decoding on vLLM", 46, TEXT, bold=True)
    text(d, (80, 160), "Prebuilt aarch64 wheel  ·  Qwen3.8-27B NVFP4  ·  64K context", 24, MUTED)

    # Target
    panel(d, (80, 250, 470, 640), fill=PANEL)
    text(d, (110, 280), "TARGET", 18, BLUE, bold=True)
    text(d, (110, 320), "Qwen3.8-27B", 34, TEXT, bold=True)
    text(d, (110, 366), "NVFP4  ·  ~21 GB", 22, MUTED)
    d.line([(110, 410), (440, 410)], fill=BORDER, width=2)
    for i, line in enumerate(["32K–64K context", "OpenAI-compatible API", "tool calls + streaming"]):
        d.ellipse((112, 442 + i * 46, 122, 452 + i * 46), fill=BLUE)
        text(d, (136, 432 + i * 46), line, 21, TEXT)

    # Center
    panel(d, (550, 210, 1050, 680), fill=PANEL_2, outline=GREEN, width=3)
    text(d, (580, 240), "ENGINE", 18, GREEN, bold=True)
    text(d, (580, 276), "vLLM 0.32", 36, TEXT, bold=True)
    text(d, (580, 320), "+ EAGLE-4 hooks", 26, GREEN, bold=True)
    text(d, (580, 362), "10/10 hook surface present", 20, MUTED)

    # Draft tree
    tree = [
        (800, 420),
        (735, 470), (865, 470),
        (700, 520), (770, 520), (830, 520), (900, 520),
    ]
    edges = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6)]
    for a, b in edges:
        d.line([tree[a], tree[b]], fill=BORDER, width=3)
    for i, (x, y) in enumerate(tree):
        r = 11 if i == 0 else 8
        color = GREEN if i in (0, 1, 3) else BLUE
        d.ellipse((x - r, y - r, x + r, y + r), fill=color, outline=BG, width=2)
    text(d, (660, 556), "draft tree", 18, MUTED)
    text(d, (660, 584), "verify → accept", 18, MUTED)

    d.line([(580, 620), (1020, 620)], fill=BORDER, width=1)
    text(d, (580, 634), "CUSTOM attention backend  ·  unquantized KV  ·  Model Runner V2", 17, MUTED)

    # Draft
    panel(d, (1130, 250, 1520, 640), fill=PANEL)
    text(d, (1160, 280), "DRAFT", 18, ORANGE, bold=True)
    text(d, (1160, 320), "EAGLE-4", 34, TEXT, bold=True)
    text(d, (1160, 366), "Qwen3.8-27B-EAGLE4", 19, MUTED)
    text(d, (1160, 398), "~5.8 GB", 22, MUTED)
    d.line([(1160, 438), (1490, 438)], fill=BORDER, width=2)
    for i, line in enumerate(["tree_depth 14", "node_top_k 4", "max_verify_width 16"]):
        d.ellipse((1162, 470 + i * 46, 1172, 480 + i * 46), fill=ORANGE)
        text(d, (1186, 460 + i * 46), line, 21, TEXT)

    # Arrows
    arrow(d, (470, 400), (550, 400), BLUE)
    arrow(d, (550, 500), (470, 500), BLUE)
    text(d, (510, 356), "hidden", 15, MUTED, anchor="ma")
    text(d, (510, 510), "tokens", 15, MUTED, anchor="ma")

    arrow(d, (1050, 400), (1130, 400), ORANGE)
    arrow(d, (1130, 500), (1050, 500), ORANGE)
    text(d, (1090, 356), "draft", 15, MUTED, anchor="ma")
    text(d, (1090, 510), "verify", 15, MUTED, anchor="ma")

    # Verified facts (no performance numbers)
    facts = [("10/10", "EAGLE-4 hooks"), ("aarch64", "linux wheel"), ("SHA-256", "verified asset")]
    x = 80
    for value, label in facts:
        panel(d, (x, 720, x + 460, 850), fill=PANEL, radius=18)
        text(d, (x + 28, 742), value, 34, GREEN, bold=True)
        text(d, (x + 28, 800), label, 20, MUTED)
        x += 490

    text(d, (80, 892), "Unofficial build  ·  Apache-2.0 vLLM wheel  ·  no performance claim: run scripts/bench.py and report", 16, MUTED)
    img.save(HERE / "architecture.png")
    print("wrote architecture.png")


if __name__ == "__main__":
    architecture()
