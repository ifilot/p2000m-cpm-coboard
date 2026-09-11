# Boot media

Confirmed working: `cartridge_mcpm.bin` (82.05.18) in SLOT1 with
`cpm_seeters_system.p2000m.img`, using `IMG.CFG` on FlashFloppy.
The Philips `mcpm_system.p2000m.img` is retained for comparison; on the current
hardware it returns to BOOT: rather than completing startup.

Both disks contain ASM.COM, DDT.COM, ED.COM, LOAD.COM, PIP.COM and STAT.COM.
Their filesystem contents are identical; only the two system tracks differ.

See [BOOT-IMAGE-COMPARISON.md](BOOT-IMAGE-COMPARISON.md) for the detailed code,
identifier, keyboard-table and timing comparison. Historical attribution is
uncertain; successful hardware operation and canonical provenance are separate
questions. The cartridge is 16 KiB, containing two identical 8 KiB copies.
