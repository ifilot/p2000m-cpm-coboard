# SANECAL MW106 M-model mapping

PROM encoding as printed in MW106:

```text
00  7E 7E 7E 7E  FE FE FE FE  7D 7D 7D 7D  7D 7D 7D 7D
10  FD FD FD FD  F9 F9 F9 F9  F9 F9 F9 F9  DC DC FD FD
```

Several printed values cannot form a valid decode with the signal assignments
on this board. `FE` asserts both active-high RAM selects, `7D` selects no
memory, `F9` asserts both `RAMS2` and `RAMS3/`, and `DC` asserts both `RAMS2`
and `CARS1/`. They are treated here as errors in the printed MW106 table. The
corrected functional encoding keeps the memory selects mutually exclusive:

```text
00  7E 7E 7E 7E  7E 7E 7E 7E  FD FD FD FD  FD FD FD FD
10  FD FD FD FD  79 79 79 79  79 79 79 79  5C 5C FD FD
```

## Signal lines

| Line | Signal on this board | Active level | Function |
|---|---|---:|---|
| D0 | `MBEN/` | 0 | Enables the memory data-bus path |
| D1 | `RAMS1` | 1 | Selects the 16 KiB motherboard system RAM |
| D2 | `RAMS3/` | 0 | Selects the CP/M board's local RAM |
| D3 | `VIDS/` | 0 | Selects video RAM |
| D4 | Unconnected | - | No function on this board |
| D5 | `CARS1/` | 0 | Selects cartridge ROM bank 1 (`1000-2FFF`) |
| D6 | `CARS2/` | 0 | Selects cartridge ROM bank 2 (`3000-4FFF`) |
| D7 | `RAMS2` | 1 | Selects the 24 KiB expansion RAM |
| P3 | `ROMS1/` | 0 | Selects the lower 2 KiB monitor ROM; held at 1 (inactive) on this board |
| P4 | `ROMS2/` | 0 | Selects the upper 2 KiB monitor ROM; held at 1 (inactive) on this board |

## Interpretation

Each PROM address covers one 2 KiB CPU-address block because CPU address lines
A11-A15 drive the PROM address inputs. Consecutive blocks that contain the same
data are combined below; the block count states how many 2 KiB blocks the row
covers. `0` is low and `1` is high, and the slash in a signal name denotes an
active-low signal. D4 is included even though it is not connected. P3 and P4
are not driven by the PROM and remain high throughout.

The final column relates the CP/M-visible range to the corresponding part of
the stock P2000M map. `RAMS3/` has no equivalent destination in the stock map;
when asserted, it connects the CPU to the RAM fitted on the CP/M board.

| Data | Blocks | PROM addresses | CPU address range | D7 `RAMS2` | D6 `CARS2/` | D5 `CARS1/` | D4 unconnected | D3 `VIDS/` | D2 `RAMS3/` | D1 `RAMS1` | D0 `MBEN/` | P3 `ROMS1/` | P4 `ROMS2/` | Landing relative to the stock P2000M map |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `7E` | 8 | `00-07` | `0000-3FFF` | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | `6000-9FFF`: all 16 KiB of motherboard RAM |
| `FD` | 12 | `08-13` | `4000-9FFF` | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 1 | `A000-FFFF`: all 24 KiB of expansion RAM |
| `79` | 8 | `14-1B` | `A000-DFFF` | 0 | 1 | 1 | 1 | 1 | 0 | 0 | 1 | 1 | 1 | `RAMS3/` connects to the 16 KiB RAM on the CP/M board; there is no stock-map equivalent |
| `5C` | 2 | `1C-1D` | `E000-EFFF` | 0 | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 1 | 1 | Selects the `CARS1/` ROM slice originally visible at `2000-2FFF` |
| `FD` | 2 | `1E-1F` | `F000-FFFF` | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 1 | `5000-5FFF`: M-model video RAM through the translated address and the video-board decoder |
