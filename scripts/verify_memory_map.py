#!/usr/bin/env python3
"""Audit the original/revised decode and draw the CP/M memory shuffle.

Sources used by the model:

* ``literature/P2000MT Field Support Manual.pdf``, pp. 3-3, 3-4 and 3-14.
* ``literature/MW106 CPM Kaart.pdf``, especially the decode and adder diagrams.
* ``literature/address_decoding.txt`` (the programs being checked).
* ``pcb/p2000m-cpm-coboard.kicad_sch`` (the modern wiring).

No third-party Python modules are required. The script distinguishes the
literal SANECAL table from the revised-board table, prints the asserted signals,
and writes a self-contained SVG. U2 A6 is the active-low ``/MRQ`` input; its
A6=1 bank disables every memory select during I/O and idle cycles.
"""

from __future__ import annotations

import argparse
import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


KIB = 1024
PAGE = 2 * KIB


@dataclass(frozen=True)
class Signal:
    bit: int
    name: str
    active_high: bool


FACTORY_SIGNALS = (
    Signal(0, "/MBEN", False),
    Signal(1, "RAMS1", True),
    Signal(2, "/VIDS", False),
    Signal(3, "/ROMS1", False),
    Signal(4, "/ROMS2", False),
    Signal(5, "/CARS1", False),
    Signal(6, "/CARS2", False),
    Signal(7, "RAMS2", True),
)

# U2 is intentionally rewired relative to the factory PROM: D3 is /VIDS and
# D2 is the new local-SRAM select. D4 is physically unconnected; P3 and P4 are
# pulled high because neither monitor-ROM select is needed in CP/M mode.
CUSTOM_SIGNALS = (
    Signal(0, "/MBEN", False),
    Signal(1, "RAMS1", True),
    Signal(2, "/RAMS3", False),
    Signal(3, "/VIDS", False),
    Signal(5, "/CARS1", False),
    Signal(6, "/CARS2", False),
    Signal(7, "RAMS2", True),
)


def expand(*runs: tuple[int, int]) -> bytes:
    return bytes(value for value, count in runs for _ in range(count))


# The factory programs listed in address_decoding.txt. Each byte covers 2 KiB.
FACTORY_M_2ROM = expand(
    (0x74, 1), (0x6C, 1), (0x5C, 4), (0x3C, 4),
    (0xFD, 2), (0x7E, 8), (0xFD, 12),
)
FACTORY_M_1ROM = expand(
    (0x74, 2), (0x5C, 4), (0x3C, 4), (0xFD, 2),
    (0x7E, 8), (0xFD, 12),
)
FACTORY_T_2ROM = expand(
    (0x74, 1), (0x6C, 1), (0x5C, 4), (0x3C, 4),
    (0x79, 1), (0x7D, 1), (0x7E, 8), (0xFD, 12),
)
FACTORY_T_1ROM = expand(
    (0x74, 2), (0x5C, 4), (0x3C, 4), (0x79, 1),
    (0x7D, 1), (0x7E, 8), (0xFD, 12),
)

# The memory-cycle half of U2: M in 00..1F, T in 20..3F (J3 drives A5).
# U2's rewired D2 selects the SRAM in the original SANECAL 4000-7FFF slot.
CUSTOM_M = expand((0x7E, 8), (0x79, 8), (0xFD, 12), (0x5C, 2), (0xFD, 2))
CUSTOM_T = expand(
    (0x7E, 8), (0x79, 8), (0xFD, 12), (0x5C, 2), (0x75, 1), (0x7D, 1)
)
ALL_SELECTS_OFF = 0x7D

# Literal MW106 page-3 EPROM contents. These cannot be copied byte-for-byte to
# U2 because the modern board assigns D2 to /RAMS3 and D3 to /VIDS.
SANECAL_M = expand(
    (0x7E, 4), (0xFE, 4), (0x7D, 8), (0xFD, 4),
    (0xF9, 8), (0xDC, 2), (0xFD, 2),
)
SANECAL_T = SANECAL_M[:30] + bytes([0xF5, 0xFD])


PROGRAMS = (
    FACTORY_M_2ROM,
    FACTORY_M_1ROM,
    CUSTOM_M,
    FACTORY_T_2ROM,
    FACTORY_T_1ROM,
    CUSTOM_T,
)


def asserted(value: int, signals: Iterable[Signal]) -> tuple[str, ...]:
    result = []
    for signal in signals:
        level = bool(value & (1 << signal.bit))
        if level == signal.active_high:
            result.append(signal.name)
    return tuple(result)


def used_eeprom() -> bytes:
    """Return U2 addresses 00-7F.

    A6 follows /MRQ. It is low for memory cycles, selecting the first 64 bytes,
    and high for I/O/idle cycles, selecting 64 all-inactive 0x7D bytes.
    """

    return CUSTOM_M + CUSTOM_T + bytes([ALL_SELECTS_OFF]) * 64


def eeprom_address(cpu_address: int, t_model: bool, mreq_high: bool) -> int:
    """Map CPU A15..A11, T/M and /MRQ to U2 A0..A6."""

    if not 0 <= cpu_address <= 0xFFFF:
        raise ValueError("CPU address must be in 0x0000..0xFFFF")
    return (cpu_address >> 11) | (int(t_model) << 5) | (int(mreq_high) << 6)


def merged_map(program: bytes, signals: Iterable[Signal]) -> list[tuple[int, int, int, tuple[str, ...]]]:
    rows: list[list[object]] = []
    for page, value in enumerate(program):
        start, end = page * PAGE, (page + 1) * PAGE - 1
        active = asserted(value, signals)
        if rows and rows[-1][2] == value and rows[-1][3] == active:
            rows[-1][1] = end
        else:
            rows.append([start, end, value, active])
    return [(int(a), int(b), int(v), tuple(s)) for a, b, v, s in rows]


ROW_RE = re.compile(
    r"^\s*([0-9A-Fa-f]{2})\s*\*\s*(\d+).*?\b([0-9A-Fa-f]{4})-([0-9A-Fa-f]{4})\b"
)


def rows_from_text(path: Path) -> list[tuple[int, int, int, int]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ROW_RE.search(line)
        if match:
            value, count, start, end = match.groups()
            rows.append((int(value, 16), int(count), int(start, 16), int(end, 16)))
    return rows


def expected_rows() -> list[tuple[int, int, int, int]]:
    result = []
    for program in PROGRAMS:
        for start, end, value, _ in merged_map(program, ()):  # merge equal bytes only
            result.append((value, (end - start + 1) // PAGE, start, end))
    return result


def verify_text(path: Path) -> list[str]:
    errors = []
    actual = rows_from_text(path)
    for value, count, start, end in actual:
        if end - start + 1 != count * PAGE:
            errors.append(
                f"0x{value:02X} *{count} does not span {count} 2-KiB pages: "
                f"0x{start:04X}-0x{end:04X}."
            )
    return errors


def sexpr_block(text: str, start: int) -> str:
    """Return one balanced S-expression beginning at *start*."""

    depth = 0
    quoted = escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise ValueError("unbalanced S-expression")


def footprint(pcb: str, reference: str) -> str:
    position = 0
    marker = f'(property "Reference" "{reference}"'
    while (position := pcb.find("(footprint ", position)) >= 0:
        block = sexpr_block(pcb, position)
        if marker in block:
            return block
        position += len(block)
    raise ValueError(f"footprint {reference} not found")


def verify(repo: Path) -> tuple[list[str], list[str]]:
    passed: list[str] = []
    failed: list[str] = []

    text_errors = verify_text(repo / "literature" / "address_decoding.txt")
    if text_errors:
        failed.extend(text_errors)
    else:
        passed.append("All numeric rows in address_decoding.txt span the stated 2-KiB pages.")

    mw106_bytes = bytes.fromhex(
        "7E 7E 7E 7E FE FE FE FE 7D 7D 7D 7D 7D 7D 7D 7D "
        "FD FD FD FD F9 F9 F9 F9 F9 F9 F9 F9 DC DC FD FD "
        "7E 7E 7E 7E FE FE FE FE 7D 7D 7D 7D 7D 7D 7D 7D "
        "FD FD FD FD F9 F9 F9 F9 F9 F9 F9 F9 DC DC F5 FD"
    )
    if SANECAL_M + SANECAL_T == mw106_bytes:
        passed.append("Literal M/T tables match all 64 bytes printed on MW106 page 3.")
    else:
        failed.append("Modeled SANECAL tables do not match MW106 page 3.")

    boot = (repo / "software" / "CPM Nater.bin").read_bytes()
    switch = bytes.fromhex("3E 80 32 00 E0 D3 20")
    if boot.find(switch) == 0x036D:
        passed.append("Boot ROM loads D7=1 and executes OUT 20h at offsets 036D-0373.")
    else:
        failed.append("Could not confirm the D7/OUT 20h CP/M switch sequence in the boot ROM.")

    # Philips Field Support Manual, page 3-3.
    field_manual = (
        (0x0000, 0x07FF, ("/MBEN", "/ROMS1")),
        (0x0800, 0x0FFF, ("/MBEN", "/ROMS2")),
        (0x1000, 0x2FFF, ("/CARS1", "/MBEN")),
        (0x3000, 0x4FFF, ("/CARS2", "/MBEN")),
        (0x5000, 0x57FF, ("/VIDS",)),
        (0x6000, 0x9FFF, ("/MBEN", "RAMS1")),
        (0xA000, 0xFFFF, ("RAMS2",)),
    )
    t_rows = merged_map(FACTORY_T_2ROM, FACTORY_SIGNALS)
    for start, end, expected_signals in field_manual:
        found = [set(active) for a, b, _, active in t_rows if a <= start and b >= end]
        if not found or found[0] != set(expected_signals):
            failed.append(
                f"Factory T decode disagrees with field manual at 0x{start:04X}-0x{end:04X}."
            )
    if not any("field manual" in item for item in failed):
        passed.append("Factory T signal ranges agree with Field Support Manual page 3-3.")

    # The M video board has its own decoder: field manual page 3-14 says VIDS is
    # 5000-5FFF. This is independent of the CPU-board PROM's D2 output.
    passed.append("M video-board VIDS is independently decoded at 0x5000-0x5FFF (manual p. 3-14).")

    custom_m_rows = merged_map(CUSTOM_M, CUSTOM_SIGNALS)
    wanted_custom = (
        (0x0000, 0x3FFF, ("/MBEN", "RAMS1")),
        (0x4000, 0x7FFF, ("/RAMS3",)),
        (0x8000, 0xDFFF, ("RAMS2",)),
        (0xE000, 0xEFFF, ("/CARS1", "/MBEN")),
        (0xF000, 0xFFFF, ("RAMS2",)),
    )
    actual_custom = [(a, b, tuple(sorted(s))) for a, b, _, s in custom_m_rows]
    expected_custom = [(a, b, tuple(sorted(s))) for a, b, s in wanted_custom]
    if actual_custom == expected_custom:
        passed.append(
            "Revised M table yields 56 KiB logical RAM: main 0000-3FFF, "
            "local 4000-7FFF, expansion 8000-DFFF."
        )
    else:
        failed.append("Custom M signal map does not match the intended CP/M map.")

    expansion_pages = tuple(
        expansion_address(address, True) >> 12 for address in range(0x8000, 0xE000, 0x1000)
    )
    expansion_ok = expansion_pages == (0xE, 0xF, 0x0, 0x1, 0x2, 0x3)
    if expansion_ok:
        passed.append(
            "U6 maps CPU 8000-DFFF through E,F,0,1,2,3, matching the literal SANECAL sequence."
        )
    else:
        failed.append("Actual U6 wiring does not produce the required expansion-RAM addresses.")

    video_ok = all(
        (expansion_address(address, True) & 0x7FFF) == (0x5000 | (address & 0x0FFF))
        for address in range(0xF000, 0x10000)
    )
    if video_ok:
        passed.append("Actual U6 wiring maps CPU F000-FFFF to M-video address 5000-5FFF.")
    else:
        failed.append("Actual U6 wiring does not produce the required M-video addresses.")

    local_offsets = {local_sram_offset(address) for address in range(0x4000, 0x8000)}
    if local_offsets == set(range(0x4000)):
        passed.append("U1 A0-A13 map every local SRAM byte exactly once.")
    else:
        failed.append("The local SRAM window aliases or omits physical SRAM bytes.")

    # The cartridge has A0-A12 plus two 8 KiB bank selects (Field Support
    # Manual p. 3-5). CP/M asserts only CARS1 for two 2 KiB pages. E000-EFFF
    # has the same A0-A12 values as the stock CARS1 slice 2000-2FFF.
    cpm_cartridge = CUSTOM_M[0x1C:0x1E]
    if cpm_cartridge == bytes([0x5C, 0x5C]) and all(
        "/CARS2" not in asserted(value, CUSTOM_SIGNALS) for value in CUSTOM_M
    ):
        passed.append(
            "CP/M exposes only 4 KiB of cartridge ROM: stock 0x2000-0x2FFF at 0xE000-0xEFFF."
        )
    else:
        failed.append("CP/M cartridge selection is not limited to the intended 4 KiB CARS1 slice.")

    # Directly check the routed pad nets for the two distinct U2 output paths.
    schematic = (repo / "pcb" / "p2000m-cpm-coboard.kicad_sch").read_text(encoding="utf-8")
    pcb = (repo / "pcb" / "p2000m-cpm-coboard.kicad_pcb").read_text(encoding="utf-8")
    u2 = footprint(pcb, "U2")
    u2_pad_nets = dict(re.findall(r'\(pad "([^"]+)"[\s\S]*?\(net "([^"]+)"\)', u2))
    if u2_pad_nets.get("15") == "~{RAMS3}" and u2_pad_nets.get("17") == "P2":
        passed.append("KiCad wiring has U2 D2 -> /RAMS3 and U2 D3 -> P2 (/VIDS) as separate nets.")
    else:
        failed.append("Could not confirm the expected U2 D2/D3 paths in the KiCad source.")

    # U2 is tri-stated in stock mode. Its private D2 net therefore needs a
    # pull-up so U1 remains deselected until CP/M mode is latched.
    resistor_blocks = [footprint(pcb, reference) for reference in ("R1", "R2", "R3")]
    if any('(net "~{RAMS3}")' in block and '(net "VCC")' in block for block in resistor_blocks):
        passed.append("/RAMS3 has a hardware pull-up for the stock-mode interval.")
    else:
        failed.append(
            "U1 /CS (/RAMS3) floats whenever U2 is disabled (reset/stock mode); "
            "add a pull-up to VCC."
        )

    if '(net "unconnected-(U2-D4-Pad18)")' in u2:
        passed.append("U2 D4 is correctly modeled as unconnected; no ROM2 table is offered.")
    else:
        failed.append("U2 D4 connectivity changed; update the output model before programming U2.")

    # U2 A6 is /MRQ. With /MRQ high, addresses 40-7F must all emit 0x7D,
    # whose custom meaning is "no selects asserted".
    io_bank = used_eeprom()[0x40:0x80]
    if u2_pad_nets.get("6") == "~{MRQ}" and io_bank == bytes([ALL_SELECTS_OFF]) * 64:
        passed.append(
            "U2 A6 is /MRQ and its A6=1 bank is 0x7D throughout; I/O cycles cannot select U1."
        )
    elif u2_pad_nets.get("6") != "~{MRQ}":
        failed.append("KiCad wiring does not connect /MRQ to U2 A6.")
    else:
        failed.append("The U2 /MRQ=1 bank does not disable every memory select.")

    # Custom T address 3E: 0x75 has D3 low and D2 high.
    if used_eeprom()[0x3E] == 0x75 and asserted(0x75, CUSTOM_SIGNALS) == ("/VIDS",):
        passed.append("Custom U2 byte 0x3E=0x75 correctly selects only T-model /VIDS.")
    else:
        failed.append("Custom T-model video byte at U2 address 0x3E is incorrect.")

    # The PCB follows the SANECAL convention: U6 A4 is RAMS2 (P7), not CPU A15.
    # The documented P2000 M upper-board address bus is AU0-AU14, so selected
    # RAM/video accesses still receive the required low 15 translated bits.
    u6 = footprint(pcb, "U6")
    pad12 = re.search(r'\(pad "12"[\s\S]*?\(net "([^"]+)"\)', u6)
    if pad12 and pad12.group(1) == "P7":
        passed.append("U6 A4 is P7/RAMS2 as wired; only RA12-RA14 are used by the documented upper boards.")
    else:
        failed.append("Unexpected U6 A4 wiring; recalculate the translated expansion addresses.")

    return passed, failed


def expansion_address(address: int, rams2: bool) -> int:
    """Return J2 RA; U6's top input is P7/RAMS2 rather than CPU A15."""

    nibble = (int(rams2) << 3) | ((address >> 12) & 7)
    return (((nibble + 6) & 0xF) << 12) | (address & 0x0FFF)


def local_sram_offset(address: int) -> int:
    # U1 A0..A13 follow CPU A0..A13; U1 A14 is grounded.
    return address & 0x3FFF


class Svg:
    def __init__(self, width: int, height: int) -> None:
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<defs><marker id="arrow" markerWidth="4.5" markerHeight="4.5" refX="4" refY="2.25" orient="auto"><path d="M0 0L4.5 2.25L0 4.5Z" fill="context-stroke"/></marker></defs>',
            f'<rect width="{width}" height="{height}" fill="#fdf6e3"/>',
        ]

    def rect(self, x: float, y: float, w: float, h: float, fill: str, stroke: str = "none", r: int = 8) -> None:
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}"/>')

    def text(self, x: float, y: float, value: str, size: int = 15, fill: str = "#586e75", weight: int = 400, anchor: str = "start") -> None:
        self.parts.append(f'<text x="{x}" y="{y}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{html.escape(value)}</text>')

    def line(self, x1: float, y1: float, x2: float, y2: float, opacity: float = 1.0) -> None:
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#657b83" stroke-width="1.6" opacity="{opacity}" marker-end="url(#arrow)"/>')

    def curve(self, x1: float, y1: float, x2: float, y2: float, color: str) -> None:
        bend = (x2 - x1) * 0.48
        data = f"M{x1} {y1} C{x1 + bend} {y1},{x2 - bend} {y2},{x2} {y2}"
        self.parts.append(f'<path d="{data}" fill="none" stroke="#fdf6e3" stroke-width="9" stroke-linecap="round"/>')
        self.parts.append(f'<path d="{data}" fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round" opacity=".9" marker-end="url(#arrow)"/>')
        self.parts.append(f'<circle cx="{x1}" cy="{y1}" r="5" fill="{color}" stroke="#fdf6e3" stroke-width="2"/>')

    def finish(self) -> str:
        return "\n".join(self.parts + ["</svg>", ""])


def draw_map(
    svg: Svg,
    x: int,
    y: int,
    w: int,
    h: int,
    rows: list[tuple[int, int, str, str, str, str]],
) -> None:
    for start, end, label, value, color, text_color in rows:
        top = y + h * start / 65536
        height = h * (end - start + 1) / 65536
        svg.rect(x, top, w, height, color, "#fdf6e3", 2)
        if height >= 14:
            size = 11 if height < 22 else 13
            shown_value = f"${value}" if re.fullmatch(r"[0-9A-F]{2}", value) else value
            svg.text(
                x + 9,
                top + height / 2 + size * 0.36,
                f"${start:04X}-${end:04X}  {label}  [{shown_value}]",
                size,
                text_color,
                650,
            )


def write_svg(path: Path, failed: list[str]) -> None:
    svg = Svg(1800, 880)
    svg.text(45, 55, "P2000M memory shuffle: stock, SANECAL, and revised board", 30, "#002b36", 750)

    colors = {
        "rom": "#b58900",
        "car": "#cb4b16",
        "video": "#d33682",
        "system": "#2aa198",
        "expansion": "#6c71c4",
        "local": "#859900",
        "mixed": "#dc322f",
        "neutral": "#93a1a1",
    }
    dark = "#002b36"
    light = "#fdf6e3"

    panels = ((25, "Stock P2000M"), (615, "MW106 literal PROM outputs"), (1205, "Revised co-board"))
    for x, title in panels:
        svg.rect(x, 85, 570, 710, "#eee8d5", "#93a1a1", 14)
        svg.text(x + 20, 125, title, 21, "#073642", 700)

    stock_rows = [
        (0x0000, 0x07FF, "Monitor ROM 1", "74", colors["rom"], dark),
        (0x0800, 0x0FFF, "Monitor ROM 2", "6C", colors["rom"], dark),
        (0x1000, 0x1FFF, "Cartridge CARS1", "5C", colors["car"], light),
        (0x2000, 0x2FFF, "Cartridge CARS1", "5C", colors["car"], light),
        (0x3000, 0x4FFF, "Cartridge CARS2", "3C", colors["car"], light),
        (0x5000, 0x5FFF, "Video RAM", "internal decode", colors["video"], light),
        (0x6000, 0x9FFF, "Motherboard RAM", "7E", colors["system"], dark),
        (0xA000, 0xFFFF, "Expansion RAM", "FD", colors["expansion"], light),
    ]
    sanecal_rows = [
        (0x0000, 0x1FFF, "MBEN/ + RAMS1", "7E", colors["system"], dark),
        (0x2000, 0x3FFF, "MBEN/ + RAMS1 + RAMS2", "FE", colors["mixed"], light),
        (0x4000, 0x7FFF, "No PROM select", "7D", colors["neutral"], dark),
        (0x8000, 0x9FFF, "RAMS2", "FD", colors["expansion"], light),
        (0xA000, 0xDFFF, "RAMS2 + VIDS/", "F9", colors["mixed"], light),
        (0xE000, 0xEFFF, "MBEN/ + CARS1/ + RAMS2", "DC", colors["mixed"], light),
        (0xF000, 0xFFFF, "RAMS2", "FD", colors["expansion"], light),
    ]
    revised_rows = [
        (0x0000, 0x3FFF, "Motherboard RAM", "7E", colors["system"], dark),
        (0x4000, 0x7FFF, "Local SRAM /RAMS3", "79", colors["local"], dark),
        (0x8000, 0xDFFF, "Expansion RAM", "FD", colors["expansion"], light),
        (0xE000, 0xEFFF, "Cartridge boot ROM", "5C", colors["car"], light),
        (0xF000, 0xFFFF, "Video RAM", "FD", colors["video"], light),
    ]
    draw_map(svg, 45, 150, 530, 620, stock_rows)
    draw_map(svg, 635, 150, 530, 620, sanecal_rows)
    draw_map(svg, 1225, 150, 530, 620, revised_rows)

    svg.text(
        900,
        835,
        "The middle panel is a literal PROM-output map; simultaneous selects are intentionally not simplified to devices.",
        17,
        "#073642",
        650,
        "middle",
    )
    path.write_text(svg.finish(), encoding="utf-8")


def print_program(title: str, program: bytes, signals: Iterable[Signal]) -> None:
    print(f"\n{title}")
    print("CPU range       Data  asserted signals")
    for start, end, value, active in merged_map(program, signals):
        names = ", ".join(active) or "(none)"
        print(f"0x{start:04X}-0x{end:04X}   0x{value:02X}  {names}")


def write_eeprom(path: Path) -> None:
    programmed = used_eeprom()
    image = programmed + bytes([0xFF]) * (128 * KIB - len(programmed))
    path.write_bytes(image)


def main() -> int:
    script = Path(__file__).resolve()
    repo = script.parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg", type=Path, default=script.with_name("p2000m_memory_shuffle.svg"))
    parser.add_argument("--write-eeprom", type=Path, help="write a 128 KiB SST39SF010 image with the verified 128-byte U2 table")
    parser.add_argument("--strict", action="store_true", help="return 1 if a confirmed circuit issue remains")
    args = parser.parse_args()

    print_program("STOCK P2000M (2 x 2716)", FACTORY_M_2ROM, FACTORY_SIGNALS)
    print_program("ORIGINAL SANECAL MW106 TABLE (P2000M)", SANECAL_M, FACTORY_SIGNALS)
    print_program("REVISED BOARD TABLE (P2000M)", CUSTOM_M, CUSTOM_SIGNALS)

    passed, failed = verify(repo)
    print("\nCHECKS")
    for item in passed:
        print(f"PASS  {item}")
    for item in failed:
        print(f"FAIL  {item}")

    write_svg(args.svg, failed)
    print(f"INFO  Wrote {args.svg}")
    if args.write_eeprom:
        write_eeprom(args.write_eeprom)
        print(f"INFO  Wrote {args.write_eeprom}")
    print("\nVERDICT: " + ("NOT VERIFIED" if failed else "VERIFIED"))
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
