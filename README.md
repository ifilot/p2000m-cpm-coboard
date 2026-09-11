# P2000M CP/M co-board

The modern schematic is the current implementation. CPLD pin assignments have
been optimized for the existing placement; see the [comparison and complete pin
table](pcb/modern-revised/pin-optimization/README.md). Firmware logic is older:
its pin numbers have been synchronized, but its functionality has not been
updated to implement the latest schematic.

The previously confirmed working setup was:

- SLOT1 cartridge: [cartridge_mcpm.bin](software/cartridge_mcpm.bin), banner `82.05.18`.
- Floppy image: [cpm_seeters_system.p2000m.img](software/cpm_seeters_system.p2000m.img),
  using [IMG.CFG](software/IMG.CFG) for FlashFloppy.
- CPLD: [p2000m-cpm-coboard.pld](cupl/p2000m-cpm-coboard.pld), ATF1502AS
  PLCC44, fixed to P2000M. Build instructions are in [cupl/README.md](cupl/README.md).

Press Return at `BOOT:` to start disk loading. This specific combination was
reported to boot on real hardware. Its historical provenance is uncertain;
filenames alone should not be used to infer compatibility with other images.

## Verified hardware corrections (previous PCB pinout)

1. CPU-side J1 pin 26 is RAMS2, not A15. Leave it isolated. Actual A15 enters
   through PROM connector U3 pin 14 and reaches CPLD pin 8.
2. Expansion-side J2 pin 26 receives RAMS2 from CPLD pin 18 (`RAMS2_EXP` in
   the schematic, legacy `RA15` identifier in CUPL).
3. During CP/M video accesses F000-FFFF, RAMS2 must be low while the upper
   expansion address is translated to page 5. This change restored video.

The latest schematic/PCB work is in `pcb/modern-revised`. Check routing and
run manufacturing checks before producing a new board; netlist review alone
is not a manufacturing sign-off.

## Validation and limits

Real-hardware diagnostics passed the tested RAM ranges in stock and CP/M
maps, confirmed the remapped cartridge byte, and obtained FDC Sense Drive
Status after enabling the controller with OUT (90h),04h. Subsequent testing
confirmed the retained cartridge/floppy pair boots. This does not establish
that every utility or disk operation has been exercised.

The previously tested board used 16 KiB of its 128 KiB SRAM chip with A14-A16
grounded. The older firmware does not implement the modern schematic's
SRAM A14-A16 outputs. In the optimized schematic D0 connects to CPLD pin 18 (legacy firmware
name T_MODEL, unused); A14_RAM/A15_RAM/A16_RAM connect to pins 11/17/9.

Temporary diagnostic cartridges, their generators, and unused boot media were
removed after debugging. Original hardware literature, the original 82S123
PROM dump, reader tools, and previous hardware design files are retained.
`decoding.md` and `literature/sanecal_mapping.md` contain historical decoding
analysis. Use the modern schematic for current hardware connections and the
older CUPL only as a record of the previously tested mapping logic.
