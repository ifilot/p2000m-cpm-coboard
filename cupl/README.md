# ATF1502AS firmware

The firmware targets the ATF1502AS in the canonical PCB under `pcb/`. The
tested standard implementation is `p2000m-cpm-coboard.pld`; its distributable
programming file is `p2000m-cpm-coboard.jed`.

## Implementations

| Build | Purpose | Status |
| --- | --- | --- |
| `cpm` | Normal CP/M co-board with seven optional SRAM banks | Tested on hardware |
| `no-floppy` | CP/M map with onboard replacement for the absent floppy-board RAM | Compiled and source-verified; hardware testing pending |
| `stock` | Diagnostic reproduction of the factory 82S123 decoder | Reference/test implementation |

The `no-floppy` image must only be used when the complete floppy-controller
board is absent. It replaces that board's 24 KiB RAM, not its controller or
storage functions. The video expansion board remains installed.

## Normal operation

Reset selects the stock P2000M map. Write `80h` to port `20h` to select the
CP/M map and `00h` to restore the stock map. Ports `20h`-`2Fh` are aliases.

| CP/M range | Target |
| --- | --- |
| `0000`-`3FFF` | Motherboard RAM |
| `4000`-`9FFF` | Floppy-controller-board RAM |
| `A000`-`DFFF` | Local SRAM bank 0 |
| `E000`-`EFFF` | Cartridge BIOS slice originally at `2000`-`2FFF` |
| `F000`-`FFFF` | Video/attributes through translated expansion address page 5 |

The CPLD keeps the video board isolated from the SRAM bank window and preserves
the normal video map. This decode and the banked interface have been tested on
hardware.

## Atomic bank switching

Use `OUT (20h),A`. On the Z80, an immediate `OUT` places the accumulator on the
data bus and on address lines A8-A15, allowing all five control bits to be
captured on one qualified write edge.

| Accumulator bit | Meaning | CPLD input |
| --- | --- | --- |
| 7 | Enable CP/M mapping | D7 |
| 5-3 | SRAM bank number, 0-7 | A13-A11 |
| 0 | Enable the SRAM overlay at `4000`-`7FFF` | D0 |
| 6, 2-1 | Reserved; write zero | - |

For the normal image, select bank `n` from 1 through 7 with
`81h OR (n << 3)`. For example:

```asm
LD A,099h       ; CP/M mode, bank 3, overlay enabled
OUT (020h),A
; Access bank 3 at 4000h-7FFFh.
LD A,080h       ; Restore the ordinary CP/M map
OUT (020h),A
```

Bank 0 remains reserved for resident CP/M. Keep the switching routine, stack,
interrupt handlers, and the software shadow of the control byte outside the
overlay. There is no bank-register readback, and the supplied CP/M 2.2 software
does not use the additional banks automatically.

With `OUT (C),A`, the bank bits come from B bits 3-5 rather than A. Prefer the
immediate form so the command is wholly represented by A.

## No-floppy RAM allocation

`p2000m-cpm-coboard-no-floppy.pld` dedicates bank 1 to `4000`-`7FFF` and the
lower half of bank 2 to `8000`-`9FFF`. Bank 0 remains fixed at `A000`-`DFFF`.
Only banks 3-7 are available for overlay use.

Commands requesting banks 1 or 2 do not enable an overlay in this variant;
the replacement RAM remains visible. Valid overlay commands are therefore:

| Bank | Command |
| ---: | ---: |
| 3 | `99h` |
| 4 | `A1h` |
| 5 | `A9h` |
| 6 | `B1h` |
| 7 | `B9h` |

The replacement is active only in CP/M mode. The standard `80h` command shows
the complete replacement RAM map without an overlay.

## Required board wiring

- CPU connector J1 pin 26 is isolated from A15; that motherboard pin is RAMS2.
- PROM U3 pin 14 supplies the real CPU A15 to CPLD pin 44.
- Video-expansion connector J2 pin 26 connects to CPLD pin 29 and carries
  RAMS2_EXP. The source retains the legacy output name RA15.
- CPU A11/A12/A13/A14 connect to CPLD pins 28/12/16/27.

## Build

Windows with WinCUPL installed at `C:\WINCUPL`:

```bat
cupl\build.bat cpm
cupl\build.bat no-floppy
cupl\build.bat stock
```

On Linux, `build.sh` runs the same compiler and fitter through Wine. Set
`CUPL_ROOT` if WinCUPL is installed elsewhere.

```sh
cupl/build.sh cpm
cupl/build.sh no-floppy
cupl/build.sh stock
```

The repository intentionally includes the standard and no-floppy JEDEC files
because the compiler is proprietary. Intermediate compiler and fitter reports
remain ignored. Both sources compile and fit successfully for the ATF1502AS
with JTAG enabled and slow outputs. The no-floppy image has not yet been tested
on physical hardware.

## Verify

The Python checker evaluates the CUPL equations, complete memory maps, SRAM
bank allocation, control writes, reset behavior, and independent video decode.
It is functional verification rather than a fitter or timing simulation.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 cupl/verify.py
PYTHONDONTWRITEBYTECODE=1 python3 cupl/verify.py --no-floppy
PYTHONDONTWRITEBYTECODE=1 python3 cupl/verify.py --stock
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s cupl -p 'test_*.py'
```

The stock checker compares its implementation with
`literature/82s123_dump_mobo.bin`.
