@echo off
setlocal
pushd "%~dp0"
for %%e in (abs doc err fit io jed lst mx pin pla sim tt2 tt3) do (
    if exist "p2000m-cpm-coboard.%%e" del /Q "p2000m-cpm-coboard.%%e"
)
popd
