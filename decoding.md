# P2000 CP/M address decoding

This document describes the address decoding implemented by the modern CP/M
co-board.

The source material is:

- `literature/P2000MT Field Support Manual.pdf`, especially pages 3-3, 3-4 and
  3-14.
- `literature/MW106 CPM Kaart.pdf`.
- `literature/address_decoding.txt`.
- `pcb/p2000m-cpm-coboard.kicad_sch`.

## Selecting normal or CP/M mode

U5, a 74LS138, decodes I/O ports `0x20–0x2F`. An output to this mirrored port
range clocks U4A. The CP/M boot ROM executes an `OUT 0x20` with bit D7 set, so
U4A's `Q` output becomes high.

After reset, U4A is cleared and the board is in normal P2000 mode:

- The original address PROM U3 is enabled.
- The custom EEPROM U2 is disabled.
- U6 adds zero to the address sent to the expansion board.

After the CP/M-select output:

- U3 is disabled.
- U2 is enabled.
- U6 adds six to CPU address bits A15–A12.

The data bus remains unchanged. Only the memory-selection signals and the four
most significant expansion-board address bits are changed.

## U2 EEPROM address inputs

U2 is an SST39SF010. Only the first 128 bytes are selected by the circuit:

| U2 input | Source | Meaning |
|---|---|---|
| A0 | CPU A11 | Lowest EEPROM index bit; one byte per 2 KiB CPU page |
| A1 | CPU A12 | Address decode |
| A2 | CPU A13 | Address decode |
| A3 | CPU A14 | Address decode |
| A4 | CPU A15 | Address decode |
| A5 | T/M jumper | `0` selects the P2000M table; `1` selects P2000T |
| A6 | `/MRQ` | `0` selects memory decoding; `1` selects the all-off bank |
| A7–A16 | GND | Unused |

The EEPROM address is therefore:

```text
U2_address = (CPU_address >> 11) | (T_model << 5) | (/MRQ_level << 6)
```

This produces four 32-byte regions:

| U2 range | T/M | `/MRQ` | Contents |
|---|---:|---:|---|
| `0x00–0x1F` | M | 0 | P2000M CP/M memory table |
| `0x20–0x3F` | T | 0 | P2000T CP/M memory table |
| `0x40–0x5F` | M | 1 | `0x7D` throughout: all selects inactive |
| `0x60–0x7F` | T | 1 | `0x7D` throughout: all selects inactive |

The remaining SST39SF010 bytes are not addressed by the circuit and may remain
erased (`0xFF`).

## U2 output assignments

The CP/M table intentionally differs from the factory PROM assignment. In
particular, D2 is the new SRAM select and D3 is the video select.

| Bit | Signal | Active level | Destination |
|---:|---|---:|---|
| D7 | `RAMS2` | 1 | Expansion RAM selection |
| D6 | `/CARS2` | 0 | Cartridge ROM 2 |
| D5 | `/CARS1` | 0 | Cartridge ROM 1 |
| D4 | `/ROMS2` | 0 | Monitor ROM 2 |
| D3 | `/VIDS` | 0 | P2, for P2000T video RAM |
| D2 | `/RAMS3` | 0 | U1 local 16 KiB SRAM `/CS` |
| D1 | `RAMS1` | 1 | Motherboard system RAM |
| D0 | `/MBEN` | 0 | Motherboard memory bus enable |

With these polarities, `0x7D` asserts no select at all:

```text
bit:       7 6 5 4 3 2 1 0
0x7D:      0 1 1 1 1 1 0 1
signal:   R2 C2 C1 O2 VD R3 R1 MB
asserted:  -  -  -  -  -  -  -  -
```

This is why the `/MRQ=1` bank prevents I/O reads and writes from reaching U1,
even though U1 `/OE` and `/WE` are connected directly to `/RD` and `/WR`.

## P2000M CP/M map

| CPU range | U2 byte | Asserted signals | Result |
|---|---:|---|---|
| `0x0000–0x3FFF` | `0x7E` | `RAMS1`, `/MBEN` | 16 KiB motherboard RAM |
| `0x4000–0x9FFF` | `0xFD` | `RAMS2` | 24 KiB expansion RAM, translated by U6 |
| `0xA000–0xDFFF` | `0x79` | `/RAMS3` | 16 KiB local SRAM U1 |
| `0xE000–0xEFFF` | `0x5C` | `/CARS1`, `/MBEN` | 4 KiB CP/M boot-ROM slice |
| `0xF000–0xFFFF` | `0xFD` | `RAMS2` | U6 produces `RA=0x5000–0x5FFF`; the M video board decodes this range |

The field-support manual states that the P2000M video board has its own video
memory decoder for `0x5000–0x5FFF`. Consequently the CPU-board EEPROM does not
need to produce `/VIDS` for the M model.

### Only 4 KiB of cartridge ROM is exposed

The stock cartridge area is 16 KiB: `/CARS1` selects `0x1000–0x2FFF` and
`/CARS2` selects `0x3000–0x4FFF`. The cartridge receives CPU A0–A12, so each
select addresses an 8 KiB ROM bank.

CP/M asserts `/CARS1` only at `0xE000–0xEFFF`. This is a 4 KiB window, and its
A0–A12 values select the same ROM locations that appear at stock addresses
`0x2000–0x2FFF`. The following stock cartridge areas are not exposed in CP/M
mode:

- `0x1000–0x1FFF`, the other 4 KiB half selected by `/CARS1`.
- `0x3000–0x4FFF`, the complete 8 KiB `/CARS2` bank.

Thus the cartridge is not shifted wholesale. The EEPROM blocks three quarters
of it and makes only the required 4 KiB boot-ROM slice visible at
`0xE000–0xEFFF`.

## P2000T CP/M map

| CPU range | U2 byte | Asserted signals | Result |
|---|---:|---|---|
| `0x0000–0x3FFF` | `0x7E` | `RAMS1`, `/MBEN` | 16 KiB motherboard RAM |
| `0x4000–0x9FFF` | `0xFD` | `RAMS2` | 24 KiB expansion RAM, translated by U6 |
| `0xA000–0xDFFF` | `0x79` | `/RAMS3` | 16 KiB local SRAM U1 |
| `0xE000–0xEFFF` | `0x5C` | `/CARS1`, `/MBEN` | Cartridge/CP/M boot ROM |
| `0xF000–0xF7FF` | `0x75` | `/VIDS` | 2 KiB P2000T video RAM |
| `0xF800–0xFFFF` | `0x7D` | none | Unused |

For the optional P2000T+ROM2 variant, U2 address `0x3F` contains `0x6C` instead
of `0x7D`. This asserts `/ROMS2` and `/MBEN` at CPU `0xF800–0xFFFF`.

## Expansion-board address translation

U6 is a 74LS283 connected to the four high address bits. In normal mode its
addend is zero. In CP/M mode its addend is six:

```text
RA15..RA12 = (A15..A12 + 6) modulo 16
RA11..RA0  = A11..A0
```

The important CP/M translations are:

| CPU range | Expansion-board RA range | Purpose |
|---|---|---|
| `0x4000–0x9FFF` | `0xA000–0xFFFF` | Moves the physical 24 KiB expansion RAM into the CP/M lower-memory area |
| `0xF000–0xFFFF` | `0x5000–0x5FFF` | Reaches the independently decoded P2000M video memory |

The effective P2000M remapping, after applying both the U6 translation and the
EEPROM selection signals, is shown in `scripts/p2000m_memory_shuffle.svg`.

## Local SRAM address order

U1 uses CPU A0–A13 directly and has A14 tied low. The logical CP/M SRAM window
is contiguous, but its four physical 4 KiB blocks appear in a rotated order:

| CPU range | U1 offset |
|---|---|
| `0xA000–0xAFFF` | `0x2000–0x2FFF` |
| `0xB000–0xBFFF` | `0x3000–0x3FFF` |
| `0xC000–0xCFFF` | `0x0000–0x0FFF` |
| `0xD000–0xDFFF` | `0x1000–0x1FFF` |

Every one of the 16 KiB SRAM locations is still mapped exactly once; only the
physical block order differs.

## Generating and checking the EEPROM

Run the verifier without external dependencies:

```sh
python3 scripts/verify_memory_map.py --strict
```

Generate a complete 128 KiB SST39SF010 image:

```sh
python3 scripts/verify_memory_map.py --write-eeprom p2000-cpm.bin
```

For the optional T-model ROM2 mapping:

```sh
python3 scripts/verify_memory_map.py --t-rom2 --write-eeprom p2000-cpm-rom2.bin
```

The image contains the 128 active decode bytes described above followed by
erased `0xFF` bytes.
