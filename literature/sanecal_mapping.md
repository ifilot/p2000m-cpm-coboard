# SANECAL MW106 M-model mapping

This mapping is derived only from the first two EPROM rows printed in section
3.4 of [MW106 CPM Kaart](MW106%20CPM%20Kaart.pdf). No suspected errors have
been corrected in the transcription or decode.

## Literal EPROM contents

```text
00  7E 7E 7E 7E  FE FE FE FE  7D 7D 7D 7D  7D 7D 7D 7D
10  FD FD FD FD  F9 F9 F9 F9  F9 F9 F9 F9  DC DC FD FD
```

The PROM is addressed by CPU A11-A15, so each byte covers 2 KiB. The original
SANECAL schematic connects the output bits as follows:

```text
CP/M       7       6       5       4       3       2       1      0
         RAMS2  CARS2/  CARS1/  ROMS2/  ROMS1/   VIDS/   RAMS1  MBEN/
7E * 4     0       1       1       1       1       1       1      0   0000-1FFF
FE * 4     1       1       1       1       1       1       1      0   2000-3FFF
7D * 8     0       1       1       1       1       1       0      1   4000-7FFF
FD * 4     1       1       1       1       1       1       0      1   8000-9FFF
F9 * 8     1       1       1       1       1       0       0      1   A000-DFFF
DC * 2     1       1       0       1       1       1       0      0   E000-EFFF
FD * 2     1       1       1       1       1       1       0      1   F000-FFFF
```

`RAMS1` and `RAMS2` are active high. The other named outputs are active low.

## Literal signal map

This is what follows directly from the bytes, before assigning an effective
device to a range:

| CPU range | Byte | Asserted outputs |
|---|---:|---|
| `0000-1FFF` | `7E` | `MBEN/`, `RAMS1` |
| `2000-3FFF` | `FE` | `MBEN/`, `RAMS1`, `RAMS2` |
| `4000-7FFF` | `7D` | none |
| `8000-9FFF` | `FD` | `RAMS2` |
| `A000-DFFF` | `F9` | `RAMS2`, `VIDS/` |
| `E000-EFFF` | `DC` | `MBEN/`, `CARS1/`, `RAMS2` |
| `F000-FFFF` | `FD` | `RAMS2` |

The simultaneous selects are part of the printed data. In particular, the
EPROM rows alone do **not** justify simplifying `FE`, `F9`, or `DC` to a single
selected device.

## U6 address translation

U6 adds six to the four-bit value formed by `RAMS2` and CPU A14-A12:

```text
translated page = ((RAMS2 << 3) | A14:A12) + 6  (modulo 16)
```

CPU A15 is not an input to this value; U6 A4 is P7/`RAMS2` (called `M15` on
the SANECAL drawing). At 4 KiB granularity the printed bytes therefore produce:

| CPU range | RAMS2 | Translated U6 pages |
|---|---:|---|
| `0000-1FFF` | 0 | `6,7` |
| `2000-3FFF` | 1 | `0,1` |
| `4000-7FFF` | 0 | `A,B,C,D` |
| `8000-9FFF` | 1 | `E,F` |
| `A000-DFFF` | 1 | `0,1,2,3` |
| `E000-EFFF` | 1 | `4` |
| `F000-FFFF` | 1 | `5` |

Thus the six expansion-RAM pages selected from `8000-DFFF` are translated in
the order `E,F,0,1,2,3`. The `F000-FFFF` range is translated to the native
P2000M video window at `5000-5FFF`.

## Inferred effective memory map

The most direct functional interpretation of the printed M-model rows is:

```text
CP/M       7       6       5       4       3       2       1      0
         RAMS2  CARS2/  CARS1/  ROMS2/  ROMS1/   VIDS/   RAMS1  MBEN/
7E * 4     0       1       1       1       1       1       1      0   0000-1FFF MB
FE * 4     1       1       1       1       1       1       1      0   2000-3FFF MB (+RAMS2)
7D * 8     0       1       1       1       1       1       0      1   4000-7FFF CPM RAM
FD * 4     1       1       1       1       1       1       0      1   8000-9FFF EXT
F9 * 8     1       1       1       1       1       0       0      1   A000-DFFF EXT (+VIDS/)
DC * 2     1       1       0       1       1       1       0      0   E000-EFFF CAR (+RAMS2, MBEN/)
FD * 2     1       1       1       1       1       1       0      1   F000-FFFF M VIDEO
```

| CPU range | Effective device | Basis and caveat |
|---|---|---|
| `0000-3FFF` | 16 KiB motherboard RAM | `MBEN/` and `RAMS1` are asserted throughout; `RAMS2` is additionally asserted in the upper half. |
| `4000-7FFF` | 16 KiB SANECAL onboard RAM | No external PROM output is asserted; the onboard 4116 bank supplies the local RAM window. |
| `8000-DFFF` | 24 KiB expansion RAM | `RAMS2` is asserted throughout; `VIDS/` is additionally asserted from `A000-DFFF`. |
| `E000-EFFF` | CP/M boot cartridge | `CARS1/` is asserted, but so are `RAMS2` and `MBEN/`. |
| `F000-FFFF` | P2000M video RAM | `RAMS2` is asserted and U6 translates this range to `5000-5FFF`. |

This inferred map contains 56 KiB of contiguous RAM at `0000-DFFF`, followed by
the 4 KiB boot-ROM window and the 4 KiB P2000M video window.

## Ambiguities exposed by the literal table

The following cannot be resolved from the two EPROM rows alone and should not
be silently corrected when reproducing the SANECAL design:

- `FE` asserts both the motherboard-RAM and expansion-RAM control signals at
  `2000-3FFF`.
- `F9` asserts both `RAMS2` and `VIDS/` at `A000-DFFF`.
- `DC` asserts the cartridge, `RAMS2`, and `MBEN/` together at `E000-EFFF`.
- `FD` names only `RAMS2` at `F000-FFFF`; identifying the effective device as
  P2000M video RAM also requires the U6 translation and video-board decode.

Consequently, the literal bytes establish the signal map with certainty. The
single-device labels in the effective map are circuit-level interpretations,
not additional information printed in the manual.
