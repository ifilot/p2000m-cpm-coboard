# P2000M CP/M memory-map audit

Sources checked:

- `literature/MW106 CPM Kaart.pdf`, especially page 3 (EPROM bytes) and page
  16 (SANECAL schematic).
- `literature/P2000MT Field Support Manual.pdf`, especially pages 3-3, 3-5,
  3-14, 3-18 and 3-19.
- `software/CPM Nater.bin`.
- The current KiCad schematic and routed PCB.

## Result

The revised board can reproduce the SANECAL CPU-visible and physical RAM-source
order: 16 KiB motherboard RAM at `0x0000-0x3FFF`, 16 KiB local RAM at
`0x4000-0x7FFF`, and 24 KiB expansion RAM at `0x8000-0xDFFF`. The boot-ROM
window remains at `0xE000-0xEFFF` and P2000M video RAM at `0xF000-0xFFFF`.

No reroute is needed to obtain that order. The earlier reordered result came
from the EEPROM table, not from a PCB limitation. U2 D2 can select U1 in the
original local-RAM window by programming `0x79` there, while `0xFD` selects the
expansion RAM at `0x8000-0xDFFF`.

R3 is now a 4.7 kOhm pull-up from U1 `/CS` (`/RAMS3`) to VCC. It keeps U1
deselected while U2 is tri-stated after reset and in normal P2000 mode, resolving
the blocking issue found in the first audit.

A route-level connectivity check of the current PCB found no open signal net
(243 pads, 74 nets, 921 segments and 58 vias were inspected). This was not a
KiCad clearance/ERC/DRC run because `kicad-cli` is unavailable in the current
environment, so it is not a manufacturing sign-off.

## Original maps

The stock functional map documented by Philips is:

| CPU range | Device |
|---|---|
| `0x0000-0x0FFF` | Monitor ROM |
| `0x1000-0x4FFF` | Cartridge ROM |
| `0x5000-0x5FFF` | P2000M video RAM |
| `0x6000-0x9FFF` | 16 KiB motherboard RAM |
| `0xA000-0xFFFF` | Up to 24 KiB expansion RAM |

MW106 page 3 prints these 32 bytes for its M-model CP/M table:

```text
7E 7E 7E 7E  FE FE FE FE  7D 7D 7D 7D  7D 7D 7D 7D
FD FD FD FD  F9 F9 F9 F9  F9 F9 F9 F9  DC DC FD FD
```

One byte covers a 2 KiB CPU page. Together with the SANECAL local RAM and its
address adder, the effective M-model CP/M map is:

| CPU range | MW106 byte | Effective device |
|---|---:|---|
| `0x0000-0x1FFF` | `0x7E` | Motherboard RAM |
| `0x2000-0x3FFF` | `0xFE` | Motherboard RAM (with the literal extra `RAMS2` output) |
| `0x4000-0x7FFF` | `0x7D` | SANECAL local 16 KiB RAM; all external selects are off |
| `0x8000-0x9FFF` | `0xFD` | Expansion RAM |
| `0xA000-0xDFFF` | `0xF9` | Expansion RAM |
| `0xE000-0xEFFF` | `0xDC` | CP/M cartridge boot ROM |
| `0xF000-0xFFFF` | `0xFD` | P2000M video RAM |

The MW106 T-model table differs at EPROM address `0x3E`, where the scan prints
`0xF5`. That byte asserts the original `/ROMS1` bit, although the adjacent prose
says the model difference is video memory. The revised board avoids relying on
that apparent typo: its rewired T-video-only byte is `0x75`.

## Revised-board decode

### U2 address inputs

| U2 input | Source |
|---|---|
| A0-A4 | CPU A11-A15 |
| A5 | J3: M=`0`, T=`1` |
| A6 | `/MRQ` |
| A7-A16 | GND |

Therefore:

```text
U2 address = (CPU address >> 11) | (T_model << 5) | (/MRQ_level << 6)
```

The additional `/MRQ` input is handled correctly. Memory cycles use U2
addresses `0x00-0x3F`. I/O and idle cycles use `0x40-0x7F`, which must contain
`0x7D` throughout so U1 cannot be selected while `/RD` or `/WR` is active for
I/O.

### U2 outputs as actually routed

| Bit | Net | Active level |
|---:|---|---:|
| D0 | P0 `/MBEN` | 0 |
| D1 | P1 `RAMS1` | 1 |
| D2 | `/RAMS3` (U1 `/CS`) | 0 |
| D3 | P2 `/VIDS` | 0 |
| D4 | Not connected | - |
| D5 | P5 `/CARS1` | 0 |
| D6 | P6 `/CARS2` | 0 |
| D7 | P7 `RAMS2` | 1 |

P3 `/ROMS1` and P4 `/ROMS2` are held inactive by R2 and R1. Because D4 is not
connected, an EEPROM option that tries to select ROM2 through D4 cannot work on
this PCB.

### Fidelity choices

For a functionally faithful SRAM modernization, the current wiring is valid.
The EEPROM must translate the old DRAM's implicit local window into an explicit
`/RAMS3` output, which is why its bytes cannot be copied literally from MW106.
The table below preserves the device order seen by the CPU while avoiding
unwanted simultaneous selects.

For a literal PROM-pin reproduction instead, three U2 outputs would have to be
restored to the page-16 wiring: D2 to P2 `/VIDS`, D3 to P3 `/ROMS1`, and D4 to
P4 `/ROMS2`. U1 would then need a separate address decoder because no original
PROM output denotes the local `0x4000-0x7FFF` window. One 74HCT138 can implement
that decoder as follows:

| 74HCT138 pin function | Connection |
|---|---|
| `G1` | CPU A14 |
| `/G2A` | CPU A15 |
| `/G2B` | `/CPM_SEL` |
| `A` | `/MRQ` |
| `B`, `C` | GND |
| `Y0` | U1 `/RAMS3` |

This makes U1 `/CS` low only for a CP/M memory cycle in `0x4000-0x7FFF`.
R3 may remain fitted, and the added decoder needs its own 100 nF bypass
capacitor. U6 needs no change: its A4=P7/M15 connection matches SANECAL.

### Revised P2000M CP/M table (SANECAL device order)

| CPU range | U2 byte | Effective device |
|---|---:|---|
| `0x0000-0x3FFF` | `0x7E` | 16 KiB motherboard RAM |
| `0x4000-0x7FFF` | `0x79` | 16 KiB U1 SRAM |
| `0x8000-0xDFFF` | `0xFD` | 24 KiB expansion RAM |
| `0xE000-0xEFFF` | `0x5C` | 4 KiB CP/M cartridge boot-ROM slice |
| `0xF000-0xFFFF` | `0xFD` | P2000M video RAM |

U1 uses CPU A0-A13 directly and has A14 grounded. Its four physical 4 KiB
blocks appear linearly from `0x0000` through `0x3FFF` within the logical
`0x4000-0x7FFF` window. Every SRAM byte is mapped exactly once.

U6 adds six to the upper address group. The PCB faithfully follows the SANECAL
convention and connects U6 A4 to P7 (`RAMS2`, called `M15` on the original
drawing), not CPU A15. With P7 asserted, CPU pages `8,9,A,B,C,D` become translated
pages `E,F,0,1,2,3`, exactly the sequence produced by the original circuit.

The CP/M boot ROM contains `LD A,0x80` at file offset `0x036D` and
`OUT (0x20),A` at `0x0372`. U5 correctly decodes the mirrored write-port range `0x20-0x2F`, and
U4 therefore must (and does) latch D7, despite the D0 annotation in the MW106
drawing.

## EEPROM image

The concise generator is `scripts/build_eeprom.py`:

```sh
python3 scripts/build_eeprom.py p2000m-cpm-eeprom.bin
```

It writes a complete 128 KiB SST39SF010 image. Bytes `0x00-0x3F` are the M/T
memory-cycle tables, bytes `0x40-0x7F` are the `/MRQ=1` all-off tables, and the
unaddressed remainder is erased (`0xFF`).

For the expanded audit and regenerated comparison diagram, run:

```sh
python3 scripts/verify_memory_map.py --strict
```

`--strict` now verifies the routed R3 pull-up as well as the EEPROM and map.
