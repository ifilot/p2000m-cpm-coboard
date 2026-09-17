# ATF1502AS CPLD firmware

Pin assignments follow `pcb/modern-revised/p2000m-cpm-coboard.kicad_sch`.
SRAM address outputs A14_RAM (11), A15_RAM (17), and A16_RAM (9) select one
of eight 16 KiB banks. The regular CP/M build reserves bank 0 for A000-DFFF
and optionally maps banks 1-7 at 4000-7FFF, providing 112 KiB of extra storage.
The banked image has passed source verification and fitting; hardware testing
of banking remains outstanding. The stock-prom image has been reported working
on the revised board.

The regular source is `p2000m-cpm-coboard.pld`. It targets ATF1502AS PLCC44
with JTAG enabled. The working video-select correction is now part of this
regular build; the temporary `video-test` variant has been removed.

## Required wiring

- Isolate CPU connector J1 pin 26 from A15: that motherboard pin is RAMS2.
- Preserve PROM U3 pin 14 to CPLD U4 pin 44 for actual CPU A15.
- J2 pin 26 connects to CPLD pin 29 and carries RAMS2_EXP. The source retains
  the legacy name RA15 for this output; it is not an address line.
- CPU A11/A12/A13/A14 connect to CPLD pins 28/12/16/27 respectively.

## Operation

Reset selects the original PROM mapping. Write 80h to port 20h to select the
CP/M map; write 00h to restore stock mapping. Ports 20h-2Fh mirror this latch.
P2000M is fixed in firmware. Pin 18 is D0 (legacy CUPL name T_MODEL) and
supplies the overlay-enable bit.

| CP/M range | Target |
|---|---|
| 0000-3FFF | Motherboard RAM |
| 4000-7FFF | Expansion RAM, or selected SRAM bank 1-7 when enabled |
| 8000-9FFF | Expansion RAM |
| A000-DFFF | Local 16 KiB SRAM, always bank 0 |
| E000-EFFF | Cartridge BIOS slice originally at 2000-2FFF |
| F000-FFFF | Video/attributes, translated page 5, RAMS2 low |

A12-A14 pass through in stock mode; CP/M adds six modulo eight to those three
address bits. Stock PROM outputs are address-only. In CP/M mode memory selects
are qualified by /MRQ. Local SRAM is disabled in stock mode and during I/O.
The original printed FD video-table entries led to an incorrect high RAMS2
select; real-hardware testing confirmed low RAMS2 works with this board. This
does not by itself establish an error in the original Sanechal circuit.

## Atomic bank switching

Use the Z80 instruction `OUT (20h),A`. It places A on both the data bus and
address lines A8-A15, allowing the CPLD to capture three bank bits through
its existing A11-A13 inputs. All five control bits latch together at assertion
of the qualified I/O write strobe; interrupt-acknowledge cycles are excluded.

| Accumulator bit | Meaning | CPLD input |
|---|---|---|
| 7 | Enable CP/M mapping | D7 |
| 5-3 | SRAM bank number, 0-7 | A13-A11 |
| 0 | Enable SRAM overlay at 4000-7FFF | D0 |
| 6, 2-1 | Reserved; write zero (currently ignored) | — |

For bank n (1-7), write `81h OR (n << 3)`. For example:

```asm
LD A,099h       ; CP/M mode, bank 3, overlay enabled
OUT (020h),A
; Access bank 3 at 4000h-7FFFh here.
LD A,080h       ; Restore expansion RAM and the ordinary CP/M map
OUT (020h),A
```

The overlay requires CP/M mode, enable=1, and a nonzero bank. Selecting bank 0
leaves expansion RAM visible, protecting the bank used by resident CP/M.
Reset asynchronously clears all five bits. Existing 80h/00h writes retain
their original behavior and disable the overlay. All ports 20h-2Fh are aliases.
Expansion RAM select is suppressed while local SRAM serves the overlay.

With `OUT (C),A`, the bank bits instead come from B bits 3-5; D7 and D0 still
come from A. Prefer immediate `OUT (20h),A` to keep the whole command in A.
This bus behavior is documented in the [Zilog Z80 manual, page 306](https://www.zilog.com/docs/z80/um0080.pdf).

Keep the switching/copy routine, stack, and software shadow of the control byte
outside 4000-7FFF. Interrupt handlers must also avoid the window or interrupts
must remain disabled during access, preserving the caller's interrupt state.
Restore the normal map before returning to ordinary CP/M code. There is no
bank-register readback. A RAM-disk driver or bank-aware program is needed to
use the extra memory; the supplied CP/M 2.2 software does not use it automatically.

## Build and verify

Windows, with WinCUPL installed at C:\WINCUPL:

```bat
cupl\build.bat cpm
```

This produces `cupl/p2000m-cpm-coboard.jed`. Set CUPL_ROOT if installed elsewhere.
`build.sh` provides the corresponding Wine build on Linux.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 cupl/verify.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s cupl -p 'test_*.py'
```

The checker evaluates the actual CUPL equations: mapping, RAMS2 output,
address translation, every bank/control state, atomic writes and reset. It also rejects reintroduction of
RAMS2 high in the CP/M video window. These are functional checks, not timing
simulation. The original PROM fixture remains in literature/82s123_dump_mobo.bin.

Optional stock-only CPLD sources remain available through `build.bat stock`
and `build.bat stock-fast` (slow/fast slew). Both disable local SRAM, reproduce
the PROM table, pass A12-A14 and output RAMS2 on expansion pin 26. They cannot
switch to CP/M and hold SRAM A14-A16 low. They are not the firmware for the
working CP/M setup.
