@echo off
setlocal

rem Build the ATF1502AS PLCC-44 JEDEC file with WinCUPL II.
rem CUPL_ROOT may be overridden before invoking this script.

if not defined CUPL_ROOT set "CUPL_ROOT=C:\WINCUPL"

set "CUPL_EXE=%CUPL_ROOT%\Shared\cupl.exe"
set "FITTER_EXE=%CUPL_ROOT%\WinCupl\Fitters\find1502.exe"
set "LIBCUPL=%CUPL_ROOT%\Shared\CUPL.DL"
set "PATH=%PATH%;%CUPL_ROOT%\WinCupl;%CUPL_ROOT%\WinCupl\Fitters;%CUPL_ROOT%\Shared"
set "SOURCE=p2000m-cpm-coboard.pld"
set "BASENAME=p2000m-cpm-coboard"
set "OUTPUT_FAST=OFF"
if /I "%~1"=="stock" (
    set "SOURCE=p2000m-stock-prom.pld"
    set "BASENAME=p2000m-stock-prom"
) else if /I "%~1"=="stock-fast" (
    set "SOURCE=p2000m-stock-fast.pld"
    set "BASENAME=p2000m-stock-fast"
    set "OUTPUT_FAST=ON"
) else if not "%~1"=="" if /I not "%~1"=="cpm" (
    echo Usage: build.bat [cpm^|stock^|stock-fast]
    exit /B 1
)

if not exist "%CUPL_EXE%" (
    echo Error: cupl.exe not found at "%CUPL_EXE%".
    echo Set CUPL_ROOT to the WinCUPL installation directory.
    exit /B 1
)

if not exist "%FITTER_EXE%" (
    echo Error: find1502.exe not found at "%FITTER_EXE%".
    exit /B 1
)

pushd "%~dp0"

for %%e in (abs doc err fit io jed lst mx pin pla sim tt2 tt3) do (
    if exist "%BASENAME%.%%e" del /Q "%BASENAME%.%%e"
)

echo Compiling %SOURCE%...
"%CUPL_EXE%" -a -l -e -x -f -b -j -m0 -n f1502ispplcc44 "%SOURCE%"
if errorlevel 1 goto :error

if not exist "%BASENAME%.tt2" (
    echo Error: CUPL did not produce %BASENAME%.tt2.
    goto :error
)

echo Fitting ATF1502AS PLCC-44 with JTAG enabled...
"%FITTER_EXE%" -i "%~dp0%BASENAME%.tt2" -CUPL -dev P1502C44 -str JTAG ON -str output_fast %OUTPUT_FAST%
if errorlevel 1 goto :error

if not exist "%BASENAME%.jed" (
    echo Error: the fitter did not produce %BASENAME%.jed.
    goto :error
)

echo Built %CD%\%BASENAME%.jed
popd
exit /B 0

:error
echo Build failed.
popd
exit /B 1
