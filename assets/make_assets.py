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

    # Stats
    stats = [("35.2", "tok/s agentic"), ("53.1", "tok/s echo"), ("239 ms", "TTFT agentic")]
    x = 80
    for value, label in stats:
        panel(d, (x, 720, x + 460, 850), fill=PANEL, radius=18)
        text(d, (x + 28, 742), value, 38, GREEN, bold=True)
        text(d, (x + 28, 800), label, 20, MUTED)
        x += 490

    text(d, (80, 892), "Unofficial build  ·  Apache-2.0 vLLM wheel  ·  measured on one DGX Spark, 2026-10-30", 16, MUTED)
    img.save(HERE / "architecture.png")
    print("wrote architecture.png")


def benchmark():
    w, h = 1400, 820
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    text(d, (80, 60), "Single-stream throughput on DGX Spark (GB10)", 40, TEXT, bold=True)
    text(d, (80, 118), "Qwen3.8-27B NVFP4  ·  64K context  ·  concurrency 1  ·  3 requests  ·  maintainer measurement", 20, MUTED)

    # Plot area
    left, top, right, bottom = 160, 220, 1320, 660
    d.line([(left, bottom), (right, bottom)], fill=BORDER, width=2)
    max_val = 60
    for tick in range(0, 61, 10):
        y = bottom - (tick / max_val) * (bottom - top)
        d.line([(left, y), (right, y)], fill="#1A2638", width=1)
        text(d, (left - 18, y), str(tick), 16, MUTED, anchor="rm")

    groups = [
        ("Agentic", [("Base", 12.17, "#3B4A5A"), ("DFlash2", 29.10, BLUE), ("EAGLE-4", 35.17, GREEN)]),
        ("Echo", [("Base", 12.13, "#3B4A5A"), ("DFlash2", 29.22, BLUE), ("EAGLE-4", 53.05, GREEN)]),
    ]
    group_centers = [420, 1000]
    bar_w = 78
    gap = 18
    for (label, bars), center in zip(groups, group_centers):
        total = len(bars) * bar_w + (len(bars) - 1) * gap
        start = center - total / 2
        for i, (name, value, color) in enumerate(bars):
            x0 = start + i * (bar_w + gap)
            y0 = bottom - (value / max_val) * (bottom - top)
            d.rounded_rectangle((x0, y0, x0 + bar_w, bottom), radius=8, fill=color)
            text(d, (x0 + bar_w / 2, y0 - 14), f"{value:.1f}", 20, TEXT, bold=True, anchor="mb")
        text(d, (center, bottom + 26), label, 22, TEXT, bold=True, anchor="ma")

    # Legend
    legend = [("Base", "#3B4A5A"), ("DFlash2", BLUE), ("EAGLE-4", GREEN)]
    x = 160
    for name, color in legend:
        d.rounded_rectangle((x, 728, x + 18, 746), radius=4, fill=color)
        text(d, (x + 28, 724), name, 18, MUTED)
        x += 160

    text(d, (160, 770), "End-to-end completion tokens / wall time. The echo prompt is synthetic and deliberately repetitive.", 16, MUTED)
    text(d, (160, 794), "Not an independent benchmark. See docs/BENCHMARKS.md for method and caveats.", 16, MUTED)
    img.save(HERE / "benchmark.png")
    print("wrote benchmark.png")


if __name__ == "__main__":
    architecture()
    benchmark()
