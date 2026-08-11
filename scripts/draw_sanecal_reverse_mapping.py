#!/usr/bin/env python3
"""Draw a static SANECAL M-model reverse address map as SVG."""

from html import escape
from pathlib import Path
import sys


# CPU page, corrected PROM byte, asserted outputs, effective destination page.
# LOCAL denotes RAM on the CP/M board, which has no stock P2000M destination.
ROWS = (
    ("0", "7E", "/MBEN + RAMS1", "6"),
    ("1", "7E", "/MBEN + RAMS1", "7"),
    ("2", "7E", "/MBEN + RAMS1", "8"),
    ("3", "7E", "/MBEN + RAMS1", "9"),
    ("4", "FD", "RAMS2", "A"),
    ("5", "FD", "RAMS2", "B"),
    ("6", "FD", "RAMS2", "C"),
    ("7", "FD", "RAMS2", "D"),
    ("8", "FD", "RAMS2", "E"),
    ("9", "FD", "RAMS2", "F"),
    ("A", "79", "/RAMS3", "LOCAL"),
    ("B", "79", "/RAMS3", "LOCAL"),
    ("C", "79", "/RAMS3", "LOCAL"),
    ("D", "79", "/RAMS3", "LOCAL"),
    ("E", "5C", "/MBEN + /CARS1", "2"),
    ("F", "FD", "RAMS2", "5"),
)

COLORS = {
    "main": "#2aa198",
    "local": "#859900",
    "expansion": "#6c71c4",
    "cartridge": "#cb4b16",
    "video": "#d33682",
    "rom": "#b58900",
}


def page_color(page: str) -> str:
    n = int(page, 16)
    if n < 4:
        return COLORS["main"]
    if n < 10:
        return COLORS["expansion"]
    if n < 14:
        return COLORS["local"]
    return COLORS["cartridge"] if n == 14 else COLORS["video"]


def build() -> str:
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="880" viewBox="0 0 1800 880">',
        '<rect width="1800" height="880" fill="#fdf6e3"/>',
        '<defs><marker id="arrow" markerWidth="4.5" markerHeight="4.5" refX="4" refY="2.25" orient="auto"><path d="M0 0L4.5 2.25L0 4.5Z" fill="context-stroke"/></marker></defs>',
    ]

    def rect(x: float, y: float, w: float, h: float, fill: str, stroke: str = "#93a1a1", radius: int = 7) -> None:
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')

    def text(x: float, y: float, value: str, size: int = 15, weight: int = 500, fill: str = "#073642", anchor: str = "start") -> None:
        out.append(f'<text x="{x}" y="{y}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(value)}</text>')

    top, page_h = 65, 50
    left_x, left_w = 35, 430
    local_x, local_w = 825, 360
    right_x, right_w = 1335, 430

    rect(left_x, 10, left_w, 45, "#eee8d5", "#93a1a1", 10)
    rect(local_x, 10, local_w, 45, "#eee8d5", "#93a1a1", 10)
    rect(right_x, 10, right_w, 45, "#eee8d5", "#93a1a1", 10)
    text(left_x + 14, 39, "CP/M CPU input and corrected PROM output", 18, 700)
    text(local_x + 14, 39, "Board-local destination", 18, 700)
    text(right_x + 14, 39, "Landing in stock P2000M map", 18, 700)

    # Stock address-space context on the right. Endpoints are numerical U6 pages;
    # the PROM selects still determine which downstream device actually responds.
    stock = (
        (0, 1, "Monitor ROM", COLORS["rom"]),
        (1, 3, "Cartridge CARS1", COLORS["cartridge"]),
        (3, 5, "Cartridge CARS2", COLORS["cartridge"]),
        (5, 6, "M video RAM", COLORS["video"]),
        (6, 10, "Motherboard RAM", COLORS["main"]),
        (10, 16, "Expansion RAM", COLORS["expansion"]),
    )
    for start, end, label, shade in stock:
        y = top + start * page_h
        rect(right_x, y, right_w, (end - start) * page_h - 2, shade, "#fdf6e3", 4)
        text(right_x + 14, y + 25, f"${start:X}000-${end - 1:X}FFF  {label}", 14, 700, "#fdf6e3")
    for page in range(16):
        y = top + page * page_h
        out.append(f'<line x1="{right_x}" y1="{y}" x2="{right_x + right_w}" y2="{y}" stroke="#fdf6e3" stroke-width="1" opacity=".65"/>')
        text(right_x + right_w - 10, y + 41, f"${page:X}", 12, 700, "#fdf6e3", "end")

    # Stock-map paths are drawn first so the local-RAM box can mask crossings.
    for index, (page, _, _, mapped) in enumerate(ROWS):
        if mapped == "LOCAL":
            continue
        source_y = top + index * page_h + page_h / 2
        target_y = top + int(mapped, 16) * page_h + page_h / 2
        color = page_color(page)
        data = f"M {left_x + left_w} {source_y} C 760 {source_y}, 1040 {target_y}, {right_x} {target_y}"
        out.append(f'<path d="{data}" fill="none" stroke="#fdf6e3" stroke-width="10" stroke-linecap="round"/>')
        out.append(f'<path d="{data}" fill="none" stroke="{color}" stroke-width="5" stroke-linecap="round" opacity=".72" marker-end="url(#arrow)"/>')

    # RAMS3 is local to the CP/M board and cannot be placed in the stock map.
    local_y = top + 10 * page_h
    rect(local_x, local_y, local_w, 4 * page_h - 2, COLORS["local"], "#fdf6e3", 4)
    text(local_x + 14, local_y + 27, "$A000-$DFFF  CP/M-board RAM", 15, 700, "#fdf6e3")
    text(local_x + 14, local_y + 50, "Selected by /RAMS3", 13, 600, "#fdf6e3")
    text(local_x + 14, local_y + 73, "No stock-map equivalent", 13, 600, "#fdf6e3")

    for index, (page, _, _, mapped) in enumerate(ROWS):
        if mapped != "LOCAL":
            continue
        source_y = top + index * page_h + page_h / 2
        target_y = source_y
        color = page_color(page)
        data = f"M {left_x + left_w} {source_y} C 610 {source_y}, 700 {target_y}, {local_x} {target_y}"
        out.append(f'<path d="{data}" fill="none" stroke="#fdf6e3" stroke-width="10" stroke-linecap="round"/>')
        out.append(f'<path d="{data}" fill="none" stroke="{color}" stroke-width="5" stroke-linecap="round" opacity=".82" marker-end="url(#arrow)"/>')

    # Input pages carry both the PROM byte and literal asserted signals.
    for index, (page, byte, signals, mapped) in enumerate(ROWS):
        y = top + index * page_h
        shade = page_color(page)
        rect(left_x, y, left_w, page_h - 3, shade, "#fdf6e3", 4)
        text(left_x + 12, y + 21, f"${page}000-${page}FFF", 14, 750, "#fdf6e3")
        text(left_x + 145, y + 21, f"${byte}  {signals}", 13, 600, "#fdf6e3")
        destination = "local RAM" if mapped == "LOCAL" else f"${mapped}"
        text(left_x + left_w - 10, y + 41, f"maps -> {destination}", 12, 700, "#fdf6e3", "end")

    out.append("</svg>")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    if len(sys.argv) > 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} [output.svg]")
    target = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).with_name("sanecal_reverse_mapping.svg")
    target.write_text(build(), encoding="utf-8")
    print(f"Wrote {target}")
