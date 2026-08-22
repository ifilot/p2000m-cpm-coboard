# P2000M CP/M memory-map audit

Sources checked:

- `literature/MW106 CPM Kaart.pdf`, especially page 3 (EPROM bytes) and page
  16 (SANECAL schematic).
- `literature/P2000MT Field Support Manual.pdf`, especially pages 3-3, 3-5,
  3-14, 3-18 and 3-19.
- `software/CPM Nater.bin`.
- The current KiCad schematic and routed PCB.

## Result

The authoritative CP/M map is:

| CPU range | Effective device |
|---|---|
| `0x0000-0x3FFF` | 16 KiB motherboard RAM |
| `0x4000-0x9FFF` | 24 KiB expansion-card RAM |
| `0xA000-0xDFFF` | 16 KiB local card RAM |
| `0xE000-0xEFFF` | Second 4 KiB cartridge-ROM slice |
| `0xF000-0xFFFF` | P2000M video RAM |

The monitor ROM is not mapped in CP/M mode. The machine-readable source of
truth is `P2000M_MEMORY_TABLE` in `scripts/build_eeprom.py`.

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

### Authoritative P2000M CP/M table

| CPU range | U2 byte | Effective device |
|---|---:|---|
| `0x0000-0x3FFF` | `0x7E` | 16 KiB motherboard RAM |
| `0x4000-0x9FFF` | `0xFD` | 24 KiB expansion-card RAM |
| `0xA000-0xDFFF` | `0x79` | 16 KiB U1 SRAM |
| `0xE000-0xEFFF` | `0x5C` | 4 KiB CP/M cartridge boot-ROM slice |
| `0xF000-0xFFFF` | `0xFD` | P2000M video RAM |

U1 uses CPU A0-A13 directly and has A14 grounded. Its four physical 4 KiB
blocks appear linearly from `0x0000` through `0x3FFF` within the logical
`0xA000-0xDFFF` window. Every SRAM byte is mapped exactly once.

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
