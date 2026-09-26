# Memory decoding

The implemented source of truth is the CUPL firmware in `cupl/`. Historical
documents explain the origin of the design, but they do not override the tested
CUPL equations.

## Source hierarchy

1. `cupl/p2000m-cpm-coboard.pld`: tested canonical implementation.
2. `cupl/verify.py` and its regression tests: executable functional checks of
   the source equations.
3. `literature/82s123_dump_mobo.bin`: physical 32-byte dump of a P2000M
   motherboard decoder PROM.
4. The PDFs under `literature/`: historical context. Printed tables in those
   documents contain values that do not match the implemented, tested decode.

## Factory P2000M map

The original 82S123 has A11-A15 as inputs, so each byte describes one 2 KiB
CPU block. The physical dump decodes this map:

| CPU range | Device |
| --- | --- |
| `0000`-`0FFF` | Monitor ROM |
| `1000`-`2FFF` | Cartridge ROM bank 1 |
| `3000`-`4FFF` | Cartridge ROM bank 2 |
| `5000`-`57FF` | Video RAM |
| `5800`-`5FFF` | Unused |
| `6000`-`9FFF` | 16 KiB motherboard RAM |
| `A000`-`FFFF` | 24 KiB RAM on the floppy-controller board |

The dumped bytes are:

```text
74 74 5C 5C  5C 5C 3C 3C  3C 3C 79 7D  7E 7E 7E 7E
7E 7E 7E 7E  FD FD FD FD  FD FD FD FD  FD FD FD FD
```

The stock diagnostic source, `cupl/p2000m-stock-decoder.pld`, reproduces this
table and deliberately never selects the co-board SRAM.

## Canonical CP/M map

Writing `80h` to a port in `20h`-`2Fh` enables the tested CP/M decode:

| CPU range | Device |
| --- | --- |
| `0000`-`3FFF` | 16 KiB motherboard RAM |
| `4000`-`9FFF` | 24 KiB floppy-controller-board RAM |
| `A000`-`DFFF` | 16 KiB co-board SRAM, bank 0 |
| `E000`-`EFFF` | CP/M cartridge BIOS slice |
| `F000`-`FFFF` | P2000M video RAM |

The monitor ROM is not mapped in CP/M mode. External motherboard selects are
qualified by `/MRQ` in CP/M mode, and local SRAM is never selected during I/O.

CPU A12-A14 are translated by six modulo eight for the video-expansion
connector. RAMS2 is carried separately on connector pin 26; it is not A15.
The video board independently recognizes translated page 5 while RAMS2 is low.
Consequently, the banked `7000`-`7FFF` window is translated to harmless page 4
to prevent simultaneous SRAM and video selection. The actual `F000`-`FFFF`
video window continues to land on page 5.

## Optional bank window

The canonical firmware reserves physical SRAM bank 0 for `A000`-`DFFF` and can
overlay banks 1-7 at `4000`-`7FFF`. All control bits are captured atomically by
an immediate `OUT (20h),A`; see `cupl/README.md` for the command format.

## Floppy-controller board absent

The separate `p2000m-cpm-coboard-no-floppy.pld` implementation suppresses the
external RAM select and maps local SRAM across `4000`-`9FFF` in CP/M mode:

| CPU range | Physical SRAM allocation |
| --- | --- |
| `4000`-`7FFF` | Bank 1 |
| `8000`-`9FFF` | Lower 8 KiB of bank 2 |
| `A000`-`DFFF` | Bank 0 |

Banks 3-7 remain available for the optional `4000`-`7FFF` overlay. Because
A0-A13 connect directly to the SRAM, this allocation requires only the three
CPLD-controlled high SRAM address lines. The `7000`-`7FFF` video-isolation
translation applies even when the overlay is disabled.

This alternative does not emulate stock-map expansion RAM, the floppy
controller, or disk storage. It is only for systems where the complete floppy
controller board is physically absent.
