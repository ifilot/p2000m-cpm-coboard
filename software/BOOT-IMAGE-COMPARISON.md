# Boot-image comparison — 2026-09-09

Compared the actual local files, not their historical filenames:

- `cpm_seeters_system.p2000m.img`: SHA-256
  `41095dbc22d25c5af0d9027943f5c94d57ad5602faf46340006f99c5f398c312`
- `mcpm_system.p2000m.img`: SHA-256
  `784641f62f06241f0b160275b7c7d3b1afc2433fcf40e4e3ddd4fdb9ebe3853f`
- Shared cartridge: `cartridge_mcpm.bin`, banner `82.05.18`.

User reports Seeters boots on real hardware; MCPM returns to BOOT: after
Return. Video is now working with the corrected CPLD RAMS2 selection.

## What is identical

Both files are 143360 bytes: 35 tracks x 16 sectors x 256 bytes.
All bytes from offset 2000h onward are identical. That includes the filesystem,
directory, and ASM.COM, DDT.COM, ED.COM, LOAD.COM, PIP.COM, and STAT.COM.
Only the first two tracks, 8192 bytes, differ: 1906 byte positions.
These IMG files match the previously examined BIN files byte-for-byte.

Both use the same local FlashFloppy IMG.CFG profile. This comparison does not
independently validate the behavior of that configuration on the actual USB
media; it establishes that the two local files have the same geometry and
filesystem layout, so those do not explain their different behavior by name.

## Why raw offsets exaggerate the code differences

The cartridge loads 64 logical 128-byte records at address 2000h. Its sector
translation table is:

```
1,2,5,6,9,10,13,14,17,18,21,22,25,26,29,30,
3,4,7,8,11,12,15,16,19,20,23,24,27,28,31,32
```

To recover loaded memory, for each of the two tracks concatenate the 128-byte
halves indexed by this table, rather than comparing the file as linear Z80
memory. Addresses below refer to this reconstructed loaded memory unless
explicitly called resident addresses.

Both start with `JP 3680h`. At 3680h Seeters jumps to 3820h; Philips jumps to
385Fh. The BIOS jump table from 3683h is otherwise identical and calls the same
cartridge entry points E000h, E003h, E006h, E00Ch, and so on. The disk parameter
and warm-start area through 3750h also matches.

Both cold-start routines begin:

```asm
LD HL,2080h
LD DE,C400h
LD BC,1783h
LDIR
```

Thus both install the same-sized resident CP/M/BIOS region, C400h–DB82h.
**Only 19 bytes differ in this entire 6019-byte source region.** They comprise
one byte of the cold-entry jump target, eight bytes across the two identifiers
below, and ten input/configuration-table bytes. There is no wholesale different
BDOS or floppy driver in this region.

## Differences that matter to interpretation

### 1. Identification and entry relocation

At 3804h:

- Seeters: `Seeters CP/M 2.2`.
- Philips: `PHILIPS P2000 M UK`, `56K CP/M VER 2.2`, `BIOS VER 3.1`, and
  `Copyright (c) 1982, PHILIPS EFW` (spacing in the image includes double spaces).

The Philips cold-entry code follows a longer banner and is displaced by 3Fh.
Comparing the cold routines with that displacement removed shows the same
instruction structure. Pointer changes point to equivalently displaced tables;
these are not evidence of a different RAM map.

The explicit Philips identifiers make MCPM a stronger canonical *candidate*.
They do not prove the recovered image is original, unmodified, or complete.
No MiniWare identifier was found in either set of boot tracks. In particular,
Seeters floppy and Nater/MiniWare cartridge must not be treated as synonymous.

### 2. Matching six-byte identifiers in CCP and BDOS

At loaded 23A8h and 2880h (resident C728h and CC00h):

| Image | Six-byte field at both locations |
|---|---|
| Seeters | 9A 16 02 00 01 CD |
| Philips | 02 16 00 00 0B 0C |

These look like the paired CP/M identification/serial fields. The fields match
within each disk. Four bytes differ per copy, accounting for eight differing
positions. They are not, by themselves, evidence of mismatched CCP and BDOS.
The BDOS entry jump immediately after the six-byte field is the same.

### 3. Input/configuration table

Ten bytes differ at loaded addresses 3751, 3753, 3763, 3766, 3768, 378D,
3799, 379B, 37AE, and 37B0. Examples are Seeters 1Eh/1Dh versus Philips 20h,
and Seeters 10h versus Philips 5Dh. This is a character/control-code table,
consistent with keyboard customization rather than a floppy geometry change.
Its complete input behavior has not been simulated here.

A separate 96-byte character table copied to F780h is byte-identical after
accounting for the banner displacement (source 38D6h versus 3915h).

### 4. A real timing configuration difference

Near the end of cold start, Seeters stores 41h at DFD9h; Philips stores 82h.
The shared cartridge reads DFD9h at E555h and E5B6h and writes it to CTC port
8Ah, following the 87h control byte. This is a CTC channel-2 time constant,
with the Philips value twice the Seeters value.

The first path is reached through cartridge E00Ch -> E53Eh, the BIOS LIST
entry in the disk's BIOS jump table. This points to output timing, not a
changed disk-sector format. It is a concrete configuration difference worth
retaining in the analysis, but there is no evidence yet that it causes the
BOOT: retry. Do not label it a disk timeout or assign a baud rate without
tracing the clock and mode completely.

### 5. Trailing material

The Seeters image contains additional CP/M-looking material beyond its active
cold-start/table area; much of the corresponding Philips space is E5 fill.
There is also a differing byte immediately after the 96-byte character table.
Neither is included in the 1783h resident copy. These bytes contribute heavily
to the raw 1906-byte difference count, but they must not be called active
startup differences without a demonstrated reference to them.

## What this does and does not explain

The disks present the same BIOS interface to the same cartridge and use the
same broad 56 KiB CP/M layout. The difference is not simply that one requires
a Nater/MiniWare cartridge while the other requires Philips. The successful
Seeters boot with cartridge 82.05.18 is direct evidence of that compatibility.

There is no obvious corrupted branch or geometry change in the compared active
startup code that explains the observed retry. A copied historical image can
still contain faults, but the banner or a large raw byte-difference count is
not sufficient evidence.

The cartridge's ordinary boot path initializes the FDC, calls E057h to load the
system, then executes `JP NZ,6039h` on a nonzero return. Otherwise it jumps to
2000h. Code in the loaded system could also return to the cartridge later.
The visible return to BOOT: cannot distinguish these cases.

**Next discriminating experiment:** instrument the existing cartridge to save
and display the boot-reader result before that conditional jump, and mark
entry to 2000h. If the reader fails, inspect FDC status and the failing sector.
If loading succeeds, trace the Philips cold start and CTC/output configuration.
That is more informative than patching metadata or declaring either disk corrupt.

The sibling emulator boots the Philips image, but it uses simplified peripheral
behavior and different physical RAM-order handling. That is useful counterevidence
to an unconditional software crash, not proof of real-hardware compatibility.

## Isolated CTC experiment

`mcpm_system_ctc41.p2000m.img` differs from the Philips image at exactly one byte:
file offset 11DFh, loaded address 38DFh, changes 82h to 41h.
This changes the operand of `LD A,82h` at 38DEh before `LD (DFD9h),A`.
All other bytes, including the filesystem and banner, remain identical.
Use the same IMG.CFG and cartridge. Hardware result pending.
SHA-256: `9662f4dd99cf742e8825da9216b84bf2a75897dda34b73530218b23de9fcdeb3`.
