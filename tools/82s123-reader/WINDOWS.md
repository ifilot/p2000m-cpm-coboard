# Windows reader control

Software copied from `D:\PROGRAMMING\KiCAD\82S123-reader`, commit
`a315694` (Arduino firmware, Qt GUI and original README; hardware and build
outputs excluded). Original licensing remains as described in README.md.

The local firmware identifies as `82S123-READER v0.1.1` to distinguish this
copy. Its reading logic includes the existing Leonardo JTAG-disable sequence.
The GUI binary-export bug is corrected here: `.bin` files use binary mode.

Use Windows PowerShell and the Windows Arduino CLI:

```powershell
.\tools\82s123-reader\windows.ps1 -Action Build
.\tools\82s123-reader\windows.ps1 -Action Ports
.\tools\82s123-reader\windows.ps1 -Action Flash -Port COM5
.\tools\82s123-reader\windows.ps1 -Action Read -Port COM5 -Reads 3
```

Replace COM5 with the actual Leonardo port. Close the GUI/Serial Monitor
before using this controller. `Build` does not upload anything. `Flash`
recompiles and uploads with verification; it requires an explicit port.
`Read` checks the firmware identity, captures three independent reads, checks
each transfer checksum, compares all reads, and compares against the existing
`literature/82s123_dump_mobo.bin`. It never overwrites that reference file.

Captures are written as exact binary bytes alongside a serial log in an
ignored, timestamped `captures` subdirectory. Repeated agreement and the
checksum do not prove that the electrical reading of the PROM is correct.

From WSL, invoke the script through `powershell.exe -NoProfile
-ExecutionPolicy Bypass -File` using its Windows path. Compilation, uploading
and serial access all run on Windows; no WSL USB forwarding is needed.
