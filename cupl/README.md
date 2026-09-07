# ATF1502AS CUPL source

This directory contains the first CPLD implementation for the
`pcb/modern-revised` schematic. It targets an ATF1502AS in a PLCC-44 socket
with JTAG left enabled.

## Implemented behavior

- Reset selects the normal factory P2000 memory map. In this mode P0-P7
  reproduce the original 82S123 table independently of `/MRQ`, and local
  SRAM stays disabled.
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
- In CP/M mode, `/MRQ` gates every memory selection. Local `/RAMS3` always
  requires both CP/M mode and an active memory cycle, so I/O cycles cannot
  enable the local SRAM.

The fixed pin assignment is in `p2000m-cpm-coboard.pld`. Any schematic pin
change must be reflected there and in `verify.py`.

## Separate stock-only diagnostic image

`p2000m-stock-prom.pld` is a combinational replacement for the original
`literature/82s123_dump_mobo.bin` PROM table. It has no mode register, port
decoder, reset dependency, or `/MRQ` gating. Local `/RAMS3` is permanently high.
RA12-RA15 always equal A12-A15; A0-A11 pass directly through the PCB from J1 to
J2, so the expansion/video board receives the original CPU address.

Build and verify it separately:

```bat
cupl\build.bat stock
```

```sh
./cupl/build.sh stock
python3 cupl/verify.py --stock
```

Program `p2000m-stock-prom.jed` for this test. The fit uses 13/32 logic cells,
zero flip-flops, and leaves JTAG enabled. Its build does not overwrite the
CP/M-capable image. This reproduces the PROM's logical table; propagation
delays and physical board connections still require a hardware test.

For a controlled output-slew comparison, `p2000m-stock-fast.pld` contains the
same stock logic, fitted with `-str output_fast ON`. Build with `build.bat stock-fast`
or `./cupl/build.sh stock-fast`; program `p2000m-stock-fast.jed`. Verify with
`python3 cupl/verify.py --stock --source cupl/p2000m-stock-fast.pld`.
Fast slew changes output transitions, not the chip's physical speed grade;
it may improve timing margin or worsen ringing depending on the wiring.

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
2. `find1502.exe` fits that netlist for `P1502C44` and emits the `.jed` file.

The fitter is invoked with `JTAG ON`. Review the generated `.fit` and `.pin`
reports before programming hardware.

## Verification

The behavioral checker requires only Python 3:

```sh
python3 cupl/verify.py
python3 cupl/verify.py --dump
```

It parses and evaluates the actual `.pld` equations against independent expected
memory tables. Checks cover source pins and device, all 256 combinations of
2 KiB block/map/model/memory-request level, all sixteen address translations,
and 16,384 port/control/data/reset/prior-state combinations. Register checks
cover rising-edge capture, holding without an edge, asynchronous reset priority,
and complete write/reset sequences. `--dump` prints source-evaluated results.
Unsupported syntax, undefined signals, duplicate declarations, and combinational
feedback fail verification. Checks remain enabled under `python3 -O`.
Dependencies on inputs outside the corresponding truth-table sweep also fail,
so a newly introduced input cannot silently escape verification.

Run the checker regression tests, including deliberately broken CUPL equations:

```sh
python3 -m unittest discover -s cupl -p 'test_*.py'
```

This is functional source verification for the scalar CUPL syntax used here.
It does not verify JEDEC fuses, propagation delays, setup/hold timing, or physical
hardware. A fresh compiler/fitter run and review of its reports are still required.
The existing ATF1502AS fitter report uses 14 of 32 logic cells, with JTAG enabled.

Generated compiler and fitter files are ignored. Clean them with
`cupl\clean.bat` or `./cupl/clean.sh`.
