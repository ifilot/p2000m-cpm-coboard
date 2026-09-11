# ATF1502AS CPLD firmware

**The schematic is the current implementation; these sources contain older logic.**
Only their pin assignments have been synchronized with the optimized PCB.
SRAM address outputs A14_RAM (11), A15_RAM (17), and A16_RAM (9) remain
unimplemented. A successful build does not validate the current schematic
functionality. See [the pin assignment report](../pcb/modern-revised/pin-optimization/README.md).

The regular source is `p2000m-cpm-coboard.pld`. It targets ATF1502AS PLCC44
with JTAG enabled. The working video-select correction is now part of this
regular build; the temporary `video-test` variant has been removed.

## Required wiring

- Isolate CPU connector J1 pin 26 from A15: that motherboard pin is RAMS2.
- Preserve PROM U3 pin 14 to CPLD U4 pin 44 for actual CPU A15.
- J2 pin 26 connects to CPLD pin 29 and carries RAMS2_EXP. The source retains
  the legacy name RA15 for this output; it is not an address line.
- A11-A14 CPLD pins are reassigned; see the report for the complete table.

## Operation

Reset selects the original PROM mapping. Write 80h to port 20h to select the
CP/M map; write 00h to restore stock mapping. Ports 20h-2Fh mirror this latch.
P2000M is fixed in firmware; pin 18 (D0, legacy T_MODEL) does not affect the logic.

| CP/M range | Target |
|---|---|
| 0000-3FFF | Motherboard RAM |
| 4000-9FFF | Expansion RAM |
| A000-DFFF | Local 16 KiB SRAM |
| E000-EFFF | Cartridge BIOS slice originally at 2000-2FFF |
| F000-FFFF | Video/attributes, translated page 5, RAMS2 low |

A12-A14 pass through in stock mode; CP/M adds six modulo eight to those three
address bits. Stock PROM outputs are address-only. In CP/M mode memory selects
are qualified by /MRQ. Local SRAM is disabled in stock mode and during I/O.
The original printed FD video-table entries led to an incorrect high RAMS2
select; real-hardware testing confirmed low RAMS2 works with this board. This
does not by itself establish an error in the original Sanechal circuit.

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
address translation, port writes and reset. It also rejects reintroduction of
RAMS2 high in the CP/M video window. These are functional checks, not timing
simulation. The original PROM fixture remains in literature/82s123_dump_mobo.bin.

Optional stock-only CPLD sources remain available through `build.bat stock`
and `build.bat stock-fast` (slow/fast slew). Both disable local SRAM, reproduce
the PROM table, pass A12-A14 and output RAMS2 on expansion pin 26. They cannot
switch to CP/M and are not the firmware for the working CP/M setup.
