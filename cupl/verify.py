#!/usr/bin/env python3
"""Exhaustively check the intended ATF1502AS mapper truth tables."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


PLD_PATH = Path(__file__).with_name("p2000m-cpm-coboard.pld")

EXPECTED_PINS = {
    1: "RES_N",
    2: "A5",
    4: "M1_N",
    5: "WR_N",
    6: "IORQ_N",
    8: "A15",
    9: "MRQ_N",
    11: "A6",
    12: "A14",
    14: "A4",
    16: "RA12",
    17: "RA14",
    18: "RA15",
    19: "D7",
    20: "RA13",
    21: "A11",
    27: "P6_CARS2_N",
    28: "P7_RAMS2",
    29: "RAMS3_N",
    31: "P5_CARS1_N",
    33: "P4_ROMS2_N",
    34: "A13",
    36: "P3_ROMS1_N",
    37: "P2_VIDS_N",
    39: "P1_RAMS1",
    40: "P0_MBEN_N",
    41: "A12",
    43: "A7",
    44: "T_MODEL",
}

NORMAL_P_TABLE = bytes.fromhex(
    """
    74 74 5C 5C  5C 5C 3C 3C
    3C 3C 79 7D  7E 7E 7E 7E
    7E 7E 7E 7E  FD FD FD FD
    FD FD FD FD  FD FD FD FD
    """
)

# P7..P0 only. RAMS3_N is a separate CPLD output, so local RAM has the
# all-inactive P-byte 0x7D rather than the old combined EEPROM byte 0x79.
CPM_M_P_TABLE = bytes.fromhex(
    """
    7E 7E 7E 7E  7E 7E 7E 7E
    FD FD FD FD  FD FD FD FD
    FD FD FD FD  7D 7D 7D 7D
    7D 7D 7D 7D  5C 5C FD FD
    """
)

CPM_T_P_TABLE = CPM_M_P_TABLE[:30] + bytes([0xF9, 0xFD])
ALL_P_SELECTS_INACTIVE = 0x7D


def bits(value: int, width: int) -> list[int]:
    return [(value >> bit) & 1 for bit in range(width)]


def mapper_outputs(
    block: int, *, cpm_mode: bool, t_model: bool, mrq_n: bool
) -> tuple[int, int]:
    """Return the physical P7..P0 byte and RAMS3_N for one 2 KiB block."""
    a11 = block & 1
    page = block >> 1

    normal_monitor = page == 0x0
    normal_cart1 = page in (0x1, 0x2)
    normal_cart2 = page in (0x3, 0x4)
    normal_video = page == 0x5 and a11 == 0
    normal_ram1 = 0x6 <= page <= 0x9
    normal_ram2 = 0xA <= page <= 0xF

    cpm_ram1 = 0x0 <= page <= 0x3
    cpm_ram2 = 0x4 <= page <= 0x9
    cpm_ram3 = 0xA <= page <= 0xD
    cpm_cart1 = page == 0xE
    cpm_video = page == 0xF
    cpm_t_video = cpm_video and t_model and a11 == 0

    sel_monitor = not cpm_mode and normal_monitor
    sel_cart1 = (not cpm_mode and normal_cart1) or (cpm_mode and cpm_cart1)
    sel_cart2 = not cpm_mode and normal_cart2
    sel_video = (not cpm_mode and normal_video) or (cpm_mode and cpm_t_video)
    sel_ram1 = (not cpm_mode and normal_ram1) or (cpm_mode and cpm_ram1)
    sel_ram2 = (not cpm_mode and normal_ram2) or (
        cpm_mode and (cpm_ram2 or cpm_video)
    )
    sel_ram3 = cpm_mode and cpm_ram3

    memory_cycle = not mrq_n
    p0 = int(not (memory_cycle and (sel_monitor or sel_cart1 or sel_cart2 or sel_ram1)))
    p1 = int(memory_cycle and sel_ram1)
    p2 = int(not (memory_cycle and sel_video))
    p3 = int(not (memory_cycle and sel_monitor))
    p4 = 1
    p5 = int(not (memory_cycle and sel_cart1))
    p6 = int(not (memory_cycle and sel_cart2))
    p7 = int(memory_cycle and sel_ram2)
    rams3_n = int(not (memory_cycle and sel_ram3))

    p_byte = sum(bit << index for index, bit in enumerate((p0, p1, p2, p3, p4, p5, p6, p7)))
    return p_byte, rams3_n


def translated_page(page: int, cpm_mode: bool) -> int:
    return (page + 6) & 0xF if cpm_mode else page


def is_cpm_write(port: int, *, iorq_n: bool, wr_n: bool, m1_n: bool) -> bool:
    return not iorq_n and not wr_n and m1_n and (port & 0xF0) == 0x20


def read_source_pins() -> dict[int, str]:
    source = PLD_PATH.read_text(encoding="ascii")
    device = re.search(r"^Device\s+([^;]+);", source, flags=re.MULTILINE)
    assert device is not None and device.group(1).strip() == "f1502ispplcc44"
    return {
        int(number): name
        for number, name in re.findall(
            r"^PIN\s+(\d+)\s*=\s*([A-Z0-9_]+)\s*;",
            source,
            flags=re.MULTILINE,
        )
    }


def verify() -> None:
    assert read_source_pins() == EXPECTED_PINS

    normal = bytes(
        mapper_outputs(block, cpm_mode=False, t_model=False, mrq_n=False)[0]
        for block in range(32)
    )
    assert normal == NORMAL_P_TABLE

    cpm_m = bytes(
        mapper_outputs(block, cpm_mode=True, t_model=False, mrq_n=False)[0]
        for block in range(32)
    )
    assert cpm_m == CPM_M_P_TABLE

    cpm_t = bytes(
        mapper_outputs(block, cpm_mode=True, t_model=True, mrq_n=False)[0]
        for block in range(32)
    )
    assert cpm_t == CPM_T_P_TABLE

    for block in range(32):
        _, normal_rams3_n = mapper_outputs(
            block, cpm_mode=False, t_model=False, mrq_n=False
        )
        _, cpm_rams3_n = mapper_outputs(
            block, cpm_mode=True, t_model=False, mrq_n=False
        )
        assert normal_rams3_n == 1
        assert cpm_rams3_n == int(not (20 <= block <= 27))

        for cpm_mode in (False, True):
            for t_model in (False, True):
                p_byte, rams3_n = mapper_outputs(
                    block,
                    cpm_mode=cpm_mode,
                    t_model=t_model,
                    mrq_n=True,
                )
                assert p_byte == ALL_P_SELECTS_INACTIVE
                assert rams3_n == 1

    for page in range(16):
        assert translated_page(page, False) == page
        assert translated_page(page, True) == (page + 6) & 0xF

    for port in range(256):
        assert is_cpm_write(port, iorq_n=False, wr_n=False, m1_n=True) == (
            0x20 <= port <= 0x2F
        )
        assert not is_cpm_write(port, iorq_n=True, wr_n=False, m1_n=True)
        assert not is_cpm_write(port, iorq_n=False, wr_n=True, m1_n=True)
        assert not is_cpm_write(port, iorq_n=False, wr_n=False, m1_n=False)


def format_table(data: bytes) -> str:
    return "\n".join(
        " ".join(f"{value:02X}" for value in data[offset : offset + 8])
        for offset in range(0, len(data), 8)
    )


def dump_tables() -> None:
    print("Normal P7..P0:")
    print(format_table(NORMAL_P_TABLE))
    print("\nCP/M P2000M P7..P0:")
    print(format_table(CPM_M_P_TABLE))
    print("\nCP/M P2000T P7..P0:")
    print(format_table(CPM_T_P_TABLE))
    print("\nCP/M upper-nibble translation:")
    print(" ".join(f"{page:X}->{translated_page(page, True):X}" for page in range(16)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", action="store_true", help="print the verified tables")
    args = parser.parse_args()

    verify()
    print("CUPL pinout and mapper truth tables verified.")
    if args.dump:
        dump_tables()


if __name__ == "__main__":
    main()
