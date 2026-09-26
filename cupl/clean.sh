#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

for basename in p2000m-cpm-coboard p2000m-cpm-coboard-no-floppy p2000m-stock-decoder; do
    rm -f "$basename.abs" "$basename.doc" "$basename.err" \
          "$basename.fit" "$basename.io" "$basename.lst" \
          "$basename.mx" "$basename.pin" "$basename.pla" \
          "$basename.sim" "$basename.tt2" "$basename.tt3"
done

# JEDEC files are release artifacts. Do not remove the checked-in standard
# image or a locally compiled no-floppy image during routine cleanup.
