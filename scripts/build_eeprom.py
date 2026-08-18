#!/usr/bin/env python3
"""Build the SST39SF010 decode ROM for the P2000M CP/M co-board.

ROM address inputs used by the board:

    ROM A0..A4 = CPU A11..A15
    ROM A5     = P2000 M/T selection (ignored; both halves are identical)
    ROM A6     = /MRQ (0 for a memory cycle)
    ROM A7..A16 = 0

The output-bit assignments and memory-cycle values come from
``literature/sanecal_mapping.md``.  When /MRQ is high, every select is made
inactive.  This is particularly important for D2, the active-low /RAMS3
select for the RAM fitted to the co-board.
"""

from __future__ import annotations

import argparse
from pathlib import Path


ROM_SIZE = 128 * 1024

# One byte per 2 KiB CPU block.  CPU A11 is ROM A0, so the index is the
# five-bit CPU block number CPU[15:11].
P2000M_MEMORY_TABLE = bytes.fromhex(
    """
    7E 7E 7E 7E  7E 7E 7E 7E
    FD FD FD FD  FD FD FD FD
    FD FD FD FD  79 79 79 79
    79 79 79 79  5C 5C FD FD
    """
)

# D0=/MBEN, D1=RAMS1, D2=/RAMS3, D3=/VIDS, D4=unused,
# D5=/CARS1, D6=/CARS2, D7=RAMS2.  0x7D deasserts every select.
ALL_SELECTS_INACTIVE = 0x7D


def build_image() -> bytes:
    """Return a complete 128 KiB SST39SF010 programming image."""
    if len(P2000M_MEMORY_TABLE) != 32:
        raise AssertionError("the CPU memory table must contain 32 entries")

    image = bytearray([0xFF]) * ROM_SIZE

    # A5 is intentionally a don't-care: install the P2000M table for both
    # possible levels.  This also makes the image insensitive to J3's setting.
    for model_level in (0, 1):
        model_base = model_level << 5

        # /MRQ=0: normal memory decoding.
        image[model_base : model_base + 32] = P2000M_MEMORY_TABLE

        # /MRQ=1 (ROM A6 high): inhibit all targets, including /RAMS3.
        mrq_high_base = (1 << 6) | model_base
        image[mrq_high_base : mrq_high_base + 32] = bytes(
            [ALL_SELECTS_INACTIVE]
        ) * 32

    return bytes(image)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=Path("p2000m-cpm-eeprom.bin"),
        help="output file (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image = build_image()
    args.output.write_bytes(image)
    print(f"Wrote {len(image)} bytes to {args.output}")


if __name__ == "__main__":
    main()
