@echo off
setlocal
pushd "%~dp0"
for %%b in (p2000m-cpm-coboard p2000m-cpm-coboard-no-floppy p2000m-stock-decoder) do (
    for %%e in (abs doc err fit io lst mx pin pla sim tt2 tt3) do (
        if exist "%%b.%%e" del /Q "%%b.%%e"
    )
)
rem JEDEC files are retained as release artifacts.
popd
