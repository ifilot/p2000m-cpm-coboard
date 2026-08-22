# ATF1504AS CUPL source

This directory contains the first CPLD implementation for the
`pcb/modern-revised` schematic. It targets an ATF1504AS in a PLCC-44 socket
with JTAG left enabled.

## Implemented behavior

- Reset selects the normal factory P2000 memory map.
- A normal Z80 I/O write to `0x20-0x2F` latches D7 as the CP/M-map enable.
- The CP/M map is:

| CPU range | Selected target |
|---|---|
| `0x0000-0x3FFF` | Motherboard RAM (`P1/RAMS1`) |
| `0x4000-0x9FFF` | Expansion RAM (`P7/RAMS2`) |
| `0xA000-0xDFFF` | Local 16 KiB SRAM (`/RAMS3`) |
| `0xE000-0xEFFF` | Second 4 KiB cartridge slice (`P5/CARS1`) |
| `0xF000-0xFFFF` | Video window through translated expansion address `0x5xxx` |

- In CP/M mode, `RA15..RA12` is `A15..A12 + 6` modulo 16. In normal mode,
  the address passes through unchanged.
- J3/pin 44 is low for the P2000M and high for the P2000T. The T model also
  asserts `/VIDS` for `0xF000-0xF7FF`, matching its 2 KiB physical video RAM.
- `/MRQ` gates every memory selection, including `/RAMS3`, so I/O cycles
  cannot enable the local SRAM.

The fixed pin assignment is in `p2000m-cpm-coboard.pld`. Any schematic pin
change must be reflected there and in `verify.py`.

## Windows build

Install WinCUPL II and run:

```bat
cupl\build.bat
```

The scripts expect WinCUPL in `C:\WINCUPL`. Override that location when
needed:

```bat
set CUPL_ROOT=C:\path\to\WINCUPL
cupl\build.bat
```

## Linux build with Wine

Install WinCUPL into a Wine prefix and run:

```sh
./cupl/build.sh
```

By default the script uses `${WINEPREFIX:-$HOME/.wine}/drive_c/WINCUPL`.
An alternative installation can be selected with:

```sh
CUPL_ROOT=/path/to/WINCUPL ./cupl/build.sh
```

Both build wrappers perform the same two proprietary steps:

1. `cupl.exe` compiles the CUPL source to a `.tt2` netlist.
2. `find1504.exe` fits that netlist for `P1504C44` and emits the `.jed` file.

The fitter is invoked with `JTAG ON`. Review the generated `.fit` and `.pin`
reports before programming hardware.

## Verification

The behavioral checker requires only Python 3:

```sh
python3 cupl/verify.py
python3 cupl/verify.py --dump
```

It checks the source pin declarations, every normal and CP/M 2 KiB mapping
block, M/T video behavior, inactive I/O-cycle outputs, the port decoder, and
all sixteen upper-nibble address translations.

Generated compiler and fitter files are ignored. Clean them with
`cupl\clean.bat` or `./cupl/clean.sh`.
