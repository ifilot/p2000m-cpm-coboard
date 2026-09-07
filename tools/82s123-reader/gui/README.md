# 82S123 ROM Reader — Qt6 GUI

A minimal Qt6 Widgets front-end for the Arduino Leonardo based 82S123 PROM
reader. It talks to the board over a small, checksummed serial protocol
(see [Protocol](#protocol) below), reads all 32 bytes of the chip, shows
them in a table (hex / decimal / binary / ASCII), and exports the dump as
`.bin`, Intel `.hex`, or a plain-text table. It can also flash the board
with the exact firmware it was built against (see
[Flashing firmware](#flashing-firmware)).

The UI intentionally uses only stock Qt widgets and the platform's default
style — no custom stylesheets/CSS.

## Layout

```
gui/
  CMakeLists.txt
  src/
    main.cpp                entry point
    mainwindow.h/.cpp        Qt Widgets UI
    romreader.h/.cpp         QSerialPort-based protocol client
    firmwareflasher.h/.cpp   compiles/uploads the firmware via arduino-cli
    firmware_source.h.in     template into which the .ino is embedded
  resources/
    app.svg                  icon source
    app.ico                  Windows executable icon (generated from app.svg)
    icons/app-*.png          in-app icon (generated from app.svg)
    app.qrc                  Qt resource bundling the PNGs
    app.rc.in                Windows resource script embedding app.ico
```

The firmware sketch (`arduino/82s123-reader/82s123-reader.ino`) is embedded
into the binary at CMake configure time as a generated header
(`build/generated/firmware_source.h`), so the "Flash Firmware" feature
always uploads the exact sketch version the GUI was built against —
editing the `.ino` and reconfiguring picks up the change automatically.

The app icon is embedded twice, both generated from the single
`resources/app.svg` source (regenerate with `rsvg-convert` + ImageMagick's
`convert` if you edit the SVG — there's no build-time step for this, unlike
the firmware): as PNGs via `app.qrc` for the in-app window/taskbar icon, and
as `app.ico` baked into the `.exe`'s own PE resources on Windows (via a
generated `.rc` file), so it shows up in Explorer and the taskbar even
before the app runs.

## Building

Requires Qt6 (`Widgets` + `SerialPort` modules) and CMake ≥ 3.16.

### Windows via MSYS2 (UCRT64)

Install the needed packages once from an MSYS2 shell:

```
pacman -S mingw-w64-ucrt-x86_64-qt6-base mingw-w64-ucrt-x86_64-qt6-serialport \
          mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-ninja \
          mingw-w64-ucrt-x86_64-toolchain
```

Then, from a **UCRT64** MSYS2 shell (or any shell with `C:\msys64\ucrt64\bin`
on `PATH`):

```
cmake -G Ninja -S gui -B gui/build -DCMAKE_PREFIX_PATH=C:/msys64/ucrt64 -DCMAKE_BUILD_TYPE=Release
cmake --build gui/build
```

The resulting `prom82s123-reader.exe` dynamically links `Qt6Core`, `Qt6Gui`,
`Qt6Widgets`, `Qt6SerialPort`, plus the MinGW runtime
(`libgcc_s_seh-1.dll`, `libstdc++-6.dll`, `libwinpthread-1.dll`). To make the
build folder self-contained/redistributable:

```
cd gui/build
windeployqt6.exe prom82s123-reader.exe --no-translations --no-opengl-sw
cp C:/msys64/ucrt64/bin/{libgcc_s_seh-1,libstdc++-6,libwinpthread-1}.dll .
```

### Linux

```
sudo apt install qt6-base-dev qt6-serialport-dev cmake ninja-build
cmake -G Ninja -S gui -B gui/build
cmake --build gui/build
```

On Linux, add your user to the `dialout` group (or equivalent) to get
permission to open `/dev/ttyACM*`.

## Usage

1. Flash the firmware onto the Leonardo — either with the Arduino IDE, or
   with the GUI itself (see below).
2. Launch `prom82s123-reader`, pick the board's serial port, click **Connect**
   (the app performs a `PING`/`PONG` handshake and will report a clear error
   if the board doesn't answer).
3. Click **Read ROM** to pull all 32 bytes; the table fills in and the
   checksum is verified automatically.
4. **Save As…** to export as `.bin`, Intel `.hex`, or a text table.
5. **View → Show Log** for a raw transcript of the serial conversation,
   useful for troubleshooting.

## Flashing firmware

The **Flash Firmware…** button (also under the **Firmware** menu) compiles
and uploads the embedded sketch directly from the GUI, by shelling out to
[`arduino-cli`](https://arduino.github.io/arduino-cli/) — it does not bundle
its own AVR toolchain.

* On first use, the app searches `PATH` and a couple of well-known install
  locations for `arduino-cli`; if it can't find one, it prompts you to
  browse to the executable. The chosen path is remembered (`QSettings`) and
  can be changed any time via **Firmware → Locate arduino-cli…**.
* The `arduino:avr` core must be installed once: `arduino-cli core install
  arduino:avr`.
* Flashing closes any active connection to the board first (the port can't
  be shared between the GUI and the upload tool), asks for confirmation
  (it overwrites the board's firmware), then streams `arduino-cli`'s
  compile/upload output live into the log panel while an indeterminate
  progress dialog is shown (cancellable).
* Internally it writes the embedded sketch to a temporary directory and
  runs `arduino-cli compile --upload -p <port> --fqbn arduino:avr:leonardo
  <sketch>` — the same command you'd run by hand.

## Protocol

115200 baud, 8N1, ASCII, newline-terminated commands/responses:

| Host sends | Device replies |
|---|---|
| `PING` | `PONG 82S123-READER v0.1.0` |
| `READ` | 32× `AA:DD` lines (address:data, hex), then `CHK:xx` (XOR checksum of all data bytes), then `OK` |
| anything else | `ERR UNKNOWN_CMD <cmd>` |

The GUI treats the handshake and the read as timeout-guarded operations
(1.5 s / 3 s respectively) and validates that all 32 addresses were seen and
that the checksum matches before accepting a read, so a dropped byte or a
disconnected cable is reported instead of silently producing a bad dump.
