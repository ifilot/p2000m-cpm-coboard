# TODO

## CP/M co-board schematic

- [ ] Correct the 16 KiB SRAM decode.
  - U1 `/CS` is currently driven by U2 `D2`.
  - In the manual's EEPROM table, `D2` is `/VIDS` and is low for CPU addresses
    `0xA000–0xDFFF` (`0xF9`). Diverting it selects U1 in that range and prevents
    `/VIDS` from reaching P2.
  - The table's `0x7D` entries at `0x4000–0x7FFF` disable all external memory
    selects and form the contiguous 16 KiB window intended for the co-board RAM.
  - Restore U2 `D2` to P2 `/VIDS` and generate `/RAMS3` for the `0x7D` window.
    One possible implementation is to repurpose otherwise-unused U2 `D4` with
    appropriately modified EEPROM data; otherwise add explicit decode logic.

- [ ] Qualify U1 SRAM selection with Z80 `/MREQ`.
  - U1 `/OE` and `/WE` are connected directly to `/RD` and `/WR`, while `/CS`
    is currently determined only by address-EEPROM output.
  - The Z80 drives the address bus and `/RD` or `/WR` during I/O cycles too, so
    an I/O access with matching high address bits can read or corrupt SRAM.
  - Ensure U1 `/CS` can become low only when both the SRAM address window is
    selected and `/MREQ` is low. For active-low signals, this can be implemented
    as `/CS = /RAMS3_decode OR /MREQ`.

- [ ] Resolve the manual's EEPROM byte `0x3E` ambiguity before programming U2.
  - The table on manual page 3 shows `0xF5` at EEPROM address `0x3E`, corresponding
    to CPU addresses `0xF000–0xF7FF` in the T-model table.
  - Relative to the M-model value `0xFD`, `0xF5` asserts `/ROMS1` (bit 3).
  - The accompanying prose says the T/M difference concerns video memory
    (`/VIDS`, bit 2), which does not agree with `0xF5`.
  - Compare with a known-good original 2716 dump or functioning board before
    deciding whether `0xF5` is intentional or a printing error.

## Verified details to preserve

- [x] Keep U4A's data input on `D7`, despite the manual drawing showing `D0`.
  `software/CPM Nater.bin` loads `A=0x80` before `OUT 0x20`, so `D7` is the bit
  that actually selects CP/M mode.
- [x] Keep U5 decoding the mirrored I/O range `0x20–0x2F`.
- [x] Keep U6's CP/M-mode expansion-address transformation:
  `RA15..RA12 = (A15..A12 + 6) mod 16`.

Run `python3 scripts/verify_memory_map.py --strict` after making schematic or
EEPROM changes. The generated diagram is `scripts/p2000m_memory_shuffle.svg`.
