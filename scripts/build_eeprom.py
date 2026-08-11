#!/usr/bin/env python3
"""Build the 128 KiB SST39SF010 image for the revised CP/M co-board."""

from pathlib import Path
import sys


OFF = 0x7D  # No memory-select output is active.

# One byte per 2 KiB CPU page.  A5 selects M (0) or T (1).
# This preserves the SANECAL device order: main, local, expansion, ROM, video.
M_TABLE = bytes([0x7E] * 8 + [0x79] * 8 + [0xFD] * 12 + [0x5C] * 2 + [0xFD] * 2)
T_TABLE = bytes([0x7E] * 8 + [0x79] * 8 + [0xFD] * 12 + [0x5C] * 2 + [0x75, OFF])

# U2 A6 is /MRQ: A6=1 must select an all-off table for I/O and idle cycles.
used = M_TABLE + T_TABLE + bytes([OFF] * 64)
image = used + bytes([0xFF] * (128 * 1024 - len(used)))

if len(sys.argv) > 2:
    raise SystemExit(f"usage: {Path(sys.argv[0]).name} [output.bin]")
output = Path(sys.argv[1] if len(sys.argv) == 2 else "p2000m-cpm-eeprom.bin")
output.write_bytes(image)
print(f"Wrote {len(image)} bytes to {output}")
