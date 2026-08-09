#!/usr/bin/env python3
"""Verify the P2000M CP/M co-board decode and draw its address shuffle.

Evidence used by this model
---------------------------
* MW106 manual, page 3: the 64 bytes for the 2716 address EPROM.
* MW106 manual, page 16: A11..A15 -> EPROM A0..A4, T/M -> A5,
  the I/O decoder, mode latch, and 74LS283 expansion-address adder.
* pcb/p2000m-cpm-coboard.kicad_sch: the modern implementation under review.
* software/CPM Nater.bin: the boot sequence ``3E 80 ... D3 20``.

The script has no third-party dependencies.  It prints the literal signal-level
memory map, checks the modern wiring assumptions, and writes an SVG diagram.
By default a failed circuit verdict is reported but the program exits zero so
the report and image are still convenient to generate.  Pass --strict to make
a failed circuit verdict return exit status 1.
"""

from __future__ import annotations

import argparse
import hashlib
import html
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


KIB = 1024
PAGE_SIZE = 2 * KIB

# Literal transcription of the four rows on manual page 3.  A scan-quality
# caveat matters at 0x3E: the printed byte is F5 (not F9 or FD).
MANUAL_EPROM = bytes.fromhex(
    "7E 7E 7E 7E FE FE FE FE 7D 7D 7D 7D 7D 7D 7D 7D "
    "FD FD FD FD F9 F9 F9 F9 F9 F9 F9 F9 DC DC FD FD "
    "7E 7E 7E 7E FE FE FE FE 7D 7D 7D 7D 7D 7D 7D 7D "
    "FD FD FD FD F9 F9 F9 F9 F9 F9 F9 F9 DC DC F5 FD"
)


@dataclass(frozen=True)
class Signal:
    bit: int
    name: str
    active_high: bool
    description: str


# Signal names and polarities shown in the modern schematic's select legend.
SIGNALS = (
    Signal(0, "/MBEN", False, "motherboard enable"),
    Signal(1, "RAMS1", True, "motherboard RAM"),
    Signal(2, "/VIDS", False, "video RAM"),
    Signal(3, "/ROMS1", False, "monitor ROM 1"),
    Signal(4, "/ROMS2", False, "monitor ROM 2"),
    Signal(5, "/CARS1", False, "cartridge ROM 1"),
    Signal(6, "/CARS2", False, "cartridge ROM 2"),
    Signal(7, "RAMS2", True, "expansion RAM"),
)


@dataclass(frozen=True)
class ModernWiring:
    """Relevant connections observed in the KiCad schematic."""

    latch_data_bit: int = 7
    sram_cs_eeprom_bit: int = 2  # U2 D2 is diverted from /VIDS to U1 /CS
    sram_a14_tied_low: bool = True
    sram_cs_qualified_by_mreq: bool = False
    cpm_adder_constant: int = 0x6  # U6 B2=B3=Q, B1=B4=0


MODERN = ModernWiring()


def model_base(model: str) -> int:
    """EPROM A5: M=0 selects 0x00..0x1F; T=1 selects 0x20..0x3F."""

    return 0x20 if model.upper() == "T" else 0x00


def eprom_address(cpu_address: int, model: str) -> int:
    """Return the physical EPROM address selected by CPU A15..A11 and T/M.

    The wiring looks reversed when read left-to-right on the page, but it is a
    direct binary mapping: CPU A11 drives EPROM A0, ..., CPU A15 drives A4.
    Consequently each successive table byte describes the next 2 KiB window.
    """

    if not 0 <= cpu_address <= 0xFFFF:
        raise ValueError("CPU address must be in 0x0000..0xFFFF")
    return model_base(model) | (cpu_address >> 11)


def decode_byte(cpu_address: int, model: str) -> int:
    return MANUAL_EPROM[eprom_address(cpu_address, model)]


def asserted_signals(value: int) -> tuple[str, ...]:
    asserted: list[str] = []
    for signal in SIGNALS:
        level = bool(value & (1 << signal.bit))
        if level == signal.active_high:
            asserted.append(signal.name)
    return tuple(asserted)


def windows_for_value(model: str, value: int) -> list[tuple[int, int]]:
    windows = []
    for page in range(32):
        start = page * PAGE_SIZE
        if decode_byte(start, model) == value:
            windows.append((start, start + PAGE_SIZE - 1))
    return windows


def windows_for_low_bit(model: str, bit: int) -> list[tuple[int, int]]:
    windows = []
    for page in range(32):
        start = page * PAGE_SIZE
        if not (decode_byte(start, model) & (1 << bit)):
            windows.append((start, start + PAGE_SIZE - 1))
    return windows


def merge_windows(windows: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(windows):
        if merged and start == merged[-1][1] + 1:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def fmt_windows(windows: Iterable[tuple[int, int]]) -> str:
    return ", ".join(f"0x{s:04X}-0x{e:04X}" for s, e in merge_windows(windows))


def expansion_address(cpu_address: int, cpm_selected: bool) -> int:
    """Model U6: add 6 to A15..A12 in CP/M mode, modulo 16."""

    high = cpu_address >> 12
    addend = MODERN.cpm_adder_constant if cpm_selected else 0
    return (((high + addend) & 0xF) << 12) | (cpu_address & 0x0FFF)


def find_boot_switch(rom: bytes) -> tuple[int, int] | None:
    """Find LD A,n ... OUT (20h),A in the supplied boot ROM.

    The known sequence has an intervening LD (E000h),A.  A small bounded search
    avoids claiming an unrelated D3 20 byte pair as evidence.
    """

    for pos in range(len(rom) - 8):
        if rom[pos] == 0x3E:  # LD A,n
            out = rom.find(b"\xD3\x20", pos + 2, min(pos + 12, len(rom)))
            if out >= 0:
                return pos, rom[pos + 1]
    return None


def verify(repo: Path) -> tuple[list[str], list[str], dict[str, object]]:
    passed: list[str] = []
    failed: list[str] = []

    assert len(MANUAL_EPROM) == 64
    assert all(eprom_address(page * PAGE_SIZE, "M") == page for page in range(32))
    assert all(eprom_address(page * PAGE_SIZE, "T") == 0x20 + page for page in range(32))
    passed.append("Manual table contains 64 bytes and maps one byte per 2 KiB CPU window.")

    model_differences = [
        page
        for page in range(32)
        if decode_byte(page * PAGE_SIZE, "M") != decode_byte(page * PAGE_SIZE, "T")
    ]
    if model_differences == [30]:
        passed.append("T and M tables differ only at CPU 0xF000-0xF7FF (EPROM 0x3E).")
    else:
        failed.append(f"Unexpected T/M differences at pages {model_differences!r}.")

    local_windows = windows_for_value("M", 0x7D)
    local_bytes = sum(end - start + 1 for start, end in local_windows)
    if merge_windows(local_windows) == [(0x4000, 0x7FFF)] and local_bytes == 16 * KIB:
        passed.append("0x7D leaves all external memory selects inactive for exactly 0x4000-0x7FFF (16 KiB).")
    else:
        failed.append("The manual table did not yield the expected contiguous 16 KiB local-RAM gap.")

    current_cs_windows = windows_for_low_bit("M", MODERN.sram_cs_eeprom_bit)
    current_cs_bytes = sum(end - start + 1 for start, end in current_cs_windows)
    if merge_windows(current_cs_windows) != [(0x4000, 0x7FFF)]:
        failed.append(
            "U1 /CS is wired to EEPROM D2 (/VIDS): it selects "
            f"{fmt_windows(current_cs_windows)} ({current_cs_bytes // KIB} KiB), "
            "not the manual's 0x7D local-RAM gap 0x4000-0x7FFF, and /VIDS is no longer sent to P2."
        )
    else:
        passed.append("U1 /CS selects the manual's 16 KiB local-RAM window.")

    if MODERN.sram_cs_qualified_by_mreq:
        passed.append("SRAM /CS is qualified by Z80 /MREQ.")
    else:
        # OUT (n),A presents A in the high address byte.  The boot command uses
        # A=80h and n=20h, hence 8020h on A15..A0 during the I/O write.
        io_bus_address = 0x8020
        value = decode_byte(io_bus_address, "M")
        selected = not bool(value & (1 << MODERN.sram_cs_eeprom_bit))
        if selected:
            failed.append(
                "U1 /CS is not /MREQ-qualified: OUT (20h),A with A=80h decodes "
                f"EPROM 0x{eprom_address(io_bus_address, 'M'):02X}=0x{value:02X}, "
                "asserts SRAM /CS and /WE, and can corrupt SRAM offset 0x0020."
            )
        else:
            failed.append("U1 /CS is not /MREQ-qualified (latent I/O-cycle hazard).")

    boot_path = repo / "software" / "CPM Nater.bin"
    boot = boot_path.read_bytes()
    switch = find_boot_switch(boot)
    if switch is None:
        failed.append(f"Could not find the CP/M switch command in {boot_path}.")
        switch_offset, switch_value = -1, -1
    else:
        switch_offset, switch_value = switch
        if bool(switch_value & 0x80) and not bool(switch_value & 0x01):
            passed.append(
                f"Boot ROM offset 0x{switch_offset:04X} loads A=0x{switch_value:02X} before OUT 0x20: "
                "D7 selects CP/M; the manual drawing's D0 would not."
            )
        else:
            failed.append(f"Unexpected switch value 0x{switch_value:02X} in boot ROM.")

    # The literal table says its sole T/M change is FD -> F5: bit 3 (/ROMS1),
    # although page 3's prose attributes the model split to video memory (bit 2).
    m_value = MANUAL_EPROM[0x1E]
    t_value = MANUAL_EPROM[0x3E]
    changed_bits = m_value ^ t_value
    if changed_bits == (1 << 3):
        failed.append(
            "Manual inconsistency: its only T/M data change is 0xFD -> 0xF5 "
            "(/ROMS1 at 0xF000-0xF7FF), while the prose says the difference is /VIDS. "
            "Confirm byte 0x3E against a known-good EPROM dump before programming hardware."
        )

    details: dict[str, object] = {
        "local_windows": local_windows,
        "current_cs_windows": current_cs_windows,
        "switch_offset": switch_offset,
        "switch_value": switch_value,
        "rom_sha256": hashlib.sha256(boot).hexdigest(),
    }
    return passed, failed, details


def print_table(model: str) -> None:
    print(f"\n{model}-MODEL SIGNAL-LEVEL MAP")
    print("CPU range       EPROM  Data  Asserted selects")
    print("---------------  -----  ----  ---------------------------------------------")
    for page in range(32):
        start = page * PAGE_SIZE
        end = start + PAGE_SIZE - 1
        eprom = eprom_address(start, model)
        value = MANUAL_EPROM[eprom]
        active = ", ".join(asserted_signals(value)) or "(none: co-board RAM gap)"
        print(f"0x{start:04X}-0x{end:04X}   0x{eprom:02X}   0x{value:02X}  {active}")


class Svg:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.parts: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            "<defs>",
            '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#091426"/><stop offset="1" stop-color="#132c46"/></linearGradient>',
            '<filter id="shadow"><feDropShadow dx="0" dy="5" stdDeviation="7" flood-opacity=".28"/></filter>',
            '<marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#7dd3fc"/></marker>',
            "</defs>",
            f'<rect width="{width}" height="{height}" fill="url(#bg)"/>',
        ]

    def rect(self, x: float, y: float, w: float, h: float, fill: str, radius: int = 10, stroke: str = "none") -> None:
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')

    def text(self, x: float, y: float, value: str, size: int = 16, fill: str = "#e8f1fa", weight: int = 400, anchor: str = "start") -> None:
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{html.escape(value)}</text>'
        )

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str = "#7dd3fc", width: int = 2, arrow: bool = False) -> None:
        marker = ' marker-end="url(#arrow)"' if arrow else ""
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"{marker}/>')

    def path(self, d: str, color: str = "#7dd3fc", width: float = 1.5, opacity: float = 0.7) -> None:
        self.parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" opacity="{opacity}" marker-end="url(#arrow)"/>')

    def finish(self) -> str:
        return "\n".join(self.parts + ["</svg>", ""])


def write_svg(path: Path, failed: list[str]) -> None:
    svg = Svg(1600, 1040)
    svg.text(70, 70, "P2000 CP/M address decode & memory shuffle", 34, "#f8fafc", 700)
    svg.text(70, 104, "Derived from MW106 pages 3 and 16 · modern KiCad schematic review", 17, "#9fb5c9")

    # Panel 1: direct address-PROM lookup.
    svg.rect(55, 135, 700, 210, "#10253b", 16, "#284866")
    svg.text(85, 175, "1  Address EPROM lookup", 21, "#bae6fd", 700)
    bits = [("A15", "A4"), ("A14", "A3"), ("A13", "A2"), ("A12", "A1"), ("A11", "A0")]
    for i, (cpu, ep) in enumerate(bits):
        x = 90 + i * 118
        svg.rect(x, 205, 72, 42, "#1e3a56", 7)
        svg.text(x + 36, 233, cpu, 16, "#f8fafc", 700, "middle")
        svg.line(x + 36, 250, x + 36, 275, arrow=True)
        svg.rect(x, 280, 72, 42, "#164e63", 7)
        svg.text(x + 36, 308, ep, 16, "#a5f3fc", 700, "middle")
    svg.text(690, 230, "+", 28, "#94a3b8", 700, "middle")
    svg.text(690, 286, "A5", 16, "#fef3c7", 700, "middle")
    svg.text(690, 312, "T/M", 13, "#fbbf24", 600, "middle")
    svg.text(85, 335, "Direct binary order: one EEPROM byte per 2 KiB CPU window", 14, "#9fb5c9")

    # Panel 2: 74LS283 +6 high-nibble permutation.
    svg.rect(785, 135, 760, 650, "#10253b", 16, "#284866")
    svg.text(815, 175, "2  U6 expansion-board shuffle in CP/M mode", 21, "#bae6fd", 700)
    svg.text(815, 202, "RA15..RA12 = (A15..A12 + 6) mod 16", 16, "#9fb5c9")
    left_x, right_x = 840, 1370
    top_y, row_h = 228, 31
    colors = ["#164e63", "#155e75", "#0e7490", "#0369a1"]
    for nibble in range(16):
        y = top_y + nibble * row_h
        mapped = (nibble + 6) & 0xF
        color = colors[(nibble // 4) % len(colors)]
        svg.rect(left_x, y, 128, 25, color, 4)
        svg.text(left_x + 64, y + 18, f"{nibble:X}000–{nibble:X}FFF", 12, "#ecfeff", 600, "middle")
        target_y = top_y + mapped * row_h
        bend1, bend2 = left_x + 175, right_x - 48
        svg.path(f"M {left_x + 128} {y + 12} C {bend1} {y + 12}, {bend2} {target_y + 12}, {right_x} {target_y + 12}", opacity=0.48)
        svg.rect(right_x, target_y, 128, 25, color, 4)
        svg.text(right_x + 64, target_y + 18, f"{mapped:X}000–{mapped:X}FFF", 12, "#ecfeff", 600, "middle")
    svg.text(left_x + 64, 755, "CPU address", 14, "#9fb5c9", 700, "middle")
    svg.text(right_x + 64, 755, "J2 RA address", 14, "#9fb5c9", 700, "middle")

    # Panel 3: coarse signal map and the incorrect SRAM selection.
    svg.rect(55, 375, 700, 410, "#10253b", 16, "#284866")
    svg.text(85, 415, "3  Manual signal map (M model)", 21, "#bae6fd", 700)
    blocks = [
        (0x0000, 0x1FFF, "7E", "RAMS1", "#0e7490"),
        (0x2000, 0x3FFF, "FE", "RAMS1 + RAMS2", "#0284c7"),
        (0x4000, 0x7FFF, "7D", "co-board RAM gap · 16 KiB", "#16a34a"),
        (0x8000, 0x9FFF, "FD", "RAMS2", "#7c3aed"),
        (0xA000, 0xDFFF, "F9", "/VIDS + RAMS2", "#9333ea"),
        (0xE000, 0xEFFF, "DC", "/CARS1 + RAMS2", "#c2410c"),
        (0xF000, 0xFFFF, "FD", "RAMS2", "#7c3aed"),
    ]
    bar_x, bar_y, bar_w, bar_h = 92, 450, 620, 92
    cursor = bar_x
    for start, end, value, label, color in blocks:
        width = bar_w * (end - start + 1) / 65536
        svg.rect(cursor, bar_y, width, bar_h, color, 1, "#dbeafe")
        if width >= 70:
            svg.text(cursor + width / 2, bar_y + 37, value, 14, "#fff", 700, "middle")
            svg.text(cursor + width / 2, bar_y + 62, f"{start:04X}", 11, "#e0f2fe", 500, "middle")
        cursor += width
    svg.text(92, 565, "Literal asserted signals:", 14, "#9fb5c9", 700)
    y = 590
    for start, end, value, label, _ in blocks:
        svg.text(100, y, f"{start:04X}–{end:04X}  {value}  {label}", 13, "#d8e7f4")
        y += 24
    svg.rect(86, 748, 650, 25, "#7f1d1d", 6)
    svg.text(411, 766, "Current D2→/CS selects A000–DFFF and removes /VIDS; 4000–7FFF remains a gap", 13, "#fee2e2", 700, "middle")

    # Verdict strip.
    svg.rect(55, 815, 1490, 170, "#111c2d", 16, "#334b63")
    verdict_color = "#ef4444" if failed else "#22c55e"
    verdict = f"NOT VERIFIED · {len(failed)} blocking findings" if failed else "VERIFIED"
    svg.text(85, 858, verdict, 24, verdict_color, 800)
    findings = [
        "✓ D7 mode latch matches boot ROM: LD A,80h / OUT (20h),A",
        "✗ SRAM /CS diverts D2 (/VIDS), not the 7D decode gap",
        "✗ SRAM /CS lacks /MREQ; matching I/O writes can write SRAM",
        "! Manual byte 3E is F5 (/ROMS1), although its prose says /VIDS",
    ]
    for i, finding in enumerate(findings):
        color = "#86efac" if finding.startswith("✓") else ("#fca5a5" if finding.startswith("✗") else "#fde68a")
        svg.text(90 + (i % 2) * 735, 900 + (i // 2) * 38, finding, 15, color, 600)
    svg.text(1510, 1012, "Generated by scripts/verify_memory_map.py", 12, "#70879b", 400, "end")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg.finish(), encoding="utf-8")


def write_eeprom(path: Path) -> None:
    """Write a literal SST39SF010 image: manual table at 0x00, rest erased."""

    image = MANUAL_EPROM + bytes([0xFF]) * (128 * KIB - len(MANUAL_EPROM))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image)


def main() -> int:
    script = Path(__file__).resolve()
    repo = script.parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("M", "T", "both"), default="both", help="map(s) to print")
    parser.add_argument(
        "--svg",
        type=Path,
        default=script.with_name("p2000m_memory_shuffle.svg"),
        help="SVG output path",
    )
    parser.add_argument("--write-eeprom", type=Path, help="optionally write a literal 128 KiB SST39SF010 image")
    parser.add_argument("--strict", action="store_true", help="return exit status 1 when circuit checks fail")
    args = parser.parse_args()

    models = ("M", "T") if args.model == "both" else (args.model,)
    print("MANUAL EEPROM BYTES")
    for row in range(4):
        chunk = MANUAL_EPROM[row * 16 : (row + 1) * 16]
        print(f"{row * 16:02X}: " + " ".join(f"{value:02X}" for value in chunk))
    for model in models:
        print_table(model)

    passed, failed, details = verify(repo)
    print("\nCHECKS")
    for message in passed:
        print(f"PASS  {message}")
    for message in failed:
        print(f"FAIL  {message}")
    print(f"INFO  CPM Nater.bin SHA-256: {details['rom_sha256']}")

    write_svg(args.svg, failed)
    print(f"INFO  Wrote diagram: {args.svg}")
    if args.write_eeprom:
        write_eeprom(args.write_eeprom)
        print(f"INFO  Wrote literal EEPROM image: {args.write_eeprom}")

    print("\nVERDICT: " + ("NOT VERIFIED" if failed else "VERIFIED"))
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
