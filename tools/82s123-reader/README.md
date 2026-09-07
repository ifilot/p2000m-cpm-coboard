# 82S123 ROM Reader

Hardware and software to read out 82S123 bipolar PROM chips using an
[Arduino Leonardo](https://docs.arduino.cc/hardware/leonardo)-based shield,
plus a Qt6 desktop GUI to drive it.

The repository is organized as follows:

* [arduino/82s123-reader](arduino/82s123-reader) — firmware for the Leonardo.
  It exposes a small serial command protocol (handshake + checksummed read)
  so a host application can request a dump on demand, rather than the board
  dumping blindly on boot.
* [gui](gui) — a Qt6 Widgets desktop application that connects to the board,
  reads the 32 bytes of the chip, displays them (hex / decimal / binary /
  ASCII), and exports the dump as `.bin`, Intel `.hex`, or a text table. See
  [gui/README.md](gui/README.md) for build and usage instructions.
* [kicad/82s123-reader](kicad/82s123-reader) — KiCad project for the reader
  shield.

## Wiring

| Signal | Arduino pin |
|---|---|
| ROM A0–A4 | D2, D3, D4, D5, D6 |
| ROM /CE | D7 |
| ROM D0–D3 | A3–A0 (PF4–PF7) |
| ROM D4–D7 | D8–D11 (PB4–PB7) |

## Firmware protocol

115200 baud, 8N1, ASCII, newline-terminated commands/responses:

| Host sends | Device replies |
|---|---|
| `PING` | `PONG 82S123-READER v0.1.0` |
| `READ` | 32× `AA:DD` lines (address:data, hex), then `CHK:xx` (XOR checksum of all 32 data bytes), then `OK` |
| anything else | `ERR UNKNOWN_CMD <cmd>` |

The GUI (or any other host, e.g. a serial terminal) drives the board with
these commands; the board never dumps unsolicited data, which makes reads
deterministic and easy to verify (missing bytes or a checksum mismatch are
detected instead of silently producing a bad dump).

## Quick start

1. Flash [`arduino/82s123-reader/82s123-reader.ino`](arduino/82s123-reader/82s123-reader.ino)
   to the Leonardo via the Arduino IDE.
2. Build the GUI — see [gui/README.md](gui/README.md).
3. Insert the 82S123 chip, connect the board, launch the GUI, connect to its
   serial port, and click **Read ROM**.

## Example dump

A sample 32-byte read from a 82S123 chip, as reported by the reader:

```
Address | Data
--------+------
0x00    | 0x02
0x01    | 0x07
0x02    | 0x0B
0x03    | 0x0F
0x04    | 0x12
0x05    | 0x17
0x06    | 0x1B
0x07    | 0x1F
0x08    | 0x22
0x09    | 0x27
0x0A    | 0x2A
0x0B    | 0x2F
0x0C    | 0x32
0x0D    | 0x37
0x0E    | 0x39
0x0F    | 0x3F
0x10    | 0x02
0x11    | 0x07
0x12    | 0x0B
0x13    | 0x0F
0x14    | 0x12
0x15    | 0x17
0x16    | 0x1B
0x17    | 0x1F
0x18    | 0x22
0x19    | 0x27
0x1A    | 0x2A
0x1B    | 0x2F
0x1C    | 0x32
0x1D    | 0x37
0x1E    | 0x3B
0x1F    | 0x3F
```

Read twice in a row, the dump was consistent except for address `0x0E`,
which alternated between `0x39` and `0x3B` — a sign of a marginal/floating
bit on that ROM read at the time (loose socket contact or a chip near its
switching threshold), rather than a firmware issue. The GUI's per-read
checksum check will flag such inconsistencies if they cause a corrupted
transfer, but a genuinely flaky chip/socket read that completes cleanly on
both ends can still produce different (self-consistent) data — worth
re-seating the chip and re-reading if you see this.

## Licensing

* All source code, i.e. the [firmware](arduino/82s123-reader) and the
  [GUI](gui), is released under a
  [GPLv3 license](https://www.gnu.org/licenses/gpl-3.0.html).
* The hardware files to (re)produce the Arduino shield are released under
  the [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
  license.
