# 82S123 motherboard PROM — normal (factory) mapping

Source: `literature/82s123_dump_mobo.bin`, a 32-byte dump of the 82S123 PROM
fitted on the motherboard, before any CP/M-board modification.

PROM contents as dumped:

```text
00  74 74 5C 5C  5C 5C 3C 3C  3C 3C 79 7D  7E 7E 7E 7E
10  7E 7E 7E 7E  FD FD FD FD  FD FD FD FD  FD FD FD FD
```

This is a clean decode: every byte selects at most one device, and no output
combination is contradictory (unlike the printed MW106 CP/M table, see
[sanecal_mapping.md](sanecal_mapping.md)). It is byte-for-byte identical to
the "P2000M, 1×2732" table in `literature/address_decoding.txt`, which fixes
both the ROM configuration (one 4 KiB 2732, not two 2 KiB 2716s — bytes
`00-01` are both `74`, not `74`/`6C`) and the signal-to-bit wiring below. This
dump is also the empirical source for that table's `5000-5FFF` row, which was
previously an unverified guess (see the note below).

## Signal lines

| Line | Signal | Active level | Function |
|---|---|---:|---|
| D0 | `MBEN/` | 0 | Enables the memory data-bus path |
| D1 | `RAMS1` | 1 | Selects the 16 KiB motherboard system RAM |
| D2 | `VIDS/` | 0 | Selects video RAM |
| D3 | `ROMS1/` | 0 | Selects the monitor ROM (2732: whole 4 KiB device) |
| D4 | `ROMS2/` | 0 | Selects the upper monitor-ROM half (unused with a 2732; only relevant for the 2×2716 variant) |
| D5 | `CARS1/` | 0 | Selects cartridge ROM bank 1 (`1000-2FFF`) |
| D6 | `CARS2/` | 0 | Selects cartridge ROM bank 2 (`3000-4FFF`) |
| D7 | `RAMS2` | 1 | Selects the 24 KiB expansion RAM |

## Interpretation

Each PROM address covers one 2 KiB CPU-address block because CPU address lines
A11-A15 drive the PROM address inputs. Consecutive blocks that contain the
same data are combined below.

| Data | Blocks | PROM addresses | CPU address range | D7 `RAMS2` | D6 `CARS2/` | D5 `CARS1/` | D4 `ROMS2/` | D3 `ROMS1/` | D2 `VIDS/` | D1 `RAMS1` | D0 `MBEN/` | Function |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `74` | 2 | `00-01` | `0000-0FFF` | 0 | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 4 KiB monitor ROM (single 2732) |
| `5C` | 4 | `02-05` | `1000-2FFF` | 0 | 1 | 0 | 1 | 1 | 1 | 0 | 0 | Cartridge ROM bank 1 |
| `3C` | 4 | `06-09` | `3000-4FFF` | 0 | 0 | 1 | 1 | 1 | 1 | 0 | 0 | Cartridge ROM bank 2 |
| `79` | 1 | `0A` | `5000-57FF` | 0 | 1 | 1 | 1 | 1 | 0 | 0 | 1 | Video RAM |
| `7D` | 1 | `0B` | `5800-5FFF` | 0 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | Nothing selected (unused window) |
| `7E` | 8 | `0C-13` | `6000-9FFF` | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 16 KiB motherboard RAM |
| `FD` | 12 | `14-1F` | `A000-FFFF` | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 24 KiB expansion RAM |

## Note on M vs T

This chip was pulled from a known P2000M motherboard, so the `79`/`7D` split
at `5000-5FFF` (`VIDS/` asserted for `5000-57FF`, nothing selected for
`5800-5FFF`) is confirmed M-model data.
