#!/usr/bin/env sh
set -eu

# Build the ATF1504AS PLCC-44 JEDEC file using WinCUPL under Wine.
# Override CUPL_ROOT if WinCUPL is installed in a different Wine prefix.

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CUPL_ROOT=${CUPL_ROOT:-${WINEPREFIX:-$HOME/.wine}/drive_c/WINCUPL}
CUPL_EXE="$CUPL_ROOT/Shared/cupl.exe"
FITTER_EXE="$CUPL_ROOT/WinCupl/Fitters/find1504.exe"
SOURCE=p2000m-cpm-coboard.pld
BASENAME=p2000m-cpm-coboard

if ! command -v wine >/dev/null 2>&1; then
    echo "Error: wine is not installed or is not in PATH." >&2
    exit 1
fi

if ! command -v winepath >/dev/null 2>&1; then
    echo "Error: winepath is not installed or is not in PATH." >&2
    exit 1
fi

if [ ! -f "$CUPL_EXE" ]; then
    echo "Error: cupl.exe not found at $CUPL_EXE" >&2
    echo "Set CUPL_ROOT to the WinCUPL installation directory." >&2
    exit 1
fi

if [ ! -f "$FITTER_EXE" ]; then
    echo "Error: find1504.exe not found at $FITTER_EXE" >&2
    exit 1
fi

cd "$SCRIPT_DIR"

rm -f "$BASENAME.abs" "$BASENAME.doc" "$BASENAME.err" \
      "$BASENAME.fit" "$BASENAME.io" "$BASENAME.jed" \
      "$BASENAME.lst" "$BASENAME.mx" "$BASENAME.pin" \
      "$BASENAME.pla" "$BASENAME.sim" "$BASENAME.tt2" "$BASENAME.tt3"

WIN_CUPL_BIN=$(winepath -w "$CUPL_ROOT/WinCupl")
WIN_FITTER_BIN=$(winepath -w "$CUPL_ROOT/WinCupl/Fitters")
WIN_SHARED=$(winepath -w "$CUPL_ROOT/Shared")
LIBCUPL=$(winepath -w "$CUPL_ROOT/Shared/CUPL.DL")
export LIBCUPL
WINEPATH="$WIN_CUPL_BIN;$WIN_FITTER_BIN;$WIN_SHARED${WINEPATH:+;$WINEPATH}"
export WINEPATH

echo "Compiling $SOURCE..."
wine "$CUPL_EXE" -a -l -e -x -f -b -j -m0 \
    -n f1504ispplcc44 "$SOURCE"

if [ ! -f "$BASENAME.tt2" ]; then
    echo "Error: CUPL did not produce $BASENAME.tt2." >&2
    exit 1
fi

echo "Fitting ATF1504AS PLCC-44 with JTAG enabled..."
TT2_WIN=$(winepath -w "$SCRIPT_DIR/$BASENAME.tt2")
wine "$FITTER_EXE" -i "$TT2_WIN" -CUPL \
    -dev P1504C44 -str JTAG ON

if [ ! -f "$BASENAME.jed" ]; then
    echo "Error: the fitter did not produce $BASENAME.jed." >&2
    exit 1
fi

echo "Built $SCRIPT_DIR/$BASENAME.jed"
