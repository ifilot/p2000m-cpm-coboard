#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

rm -f p2000m-cpm-coboard.abs p2000m-cpm-coboard.doc \
      p2000m-cpm-coboard.err p2000m-cpm-coboard.fit \
      p2000m-cpm-coboard.io p2000m-cpm-coboard.jed \
      p2000m-cpm-coboard.lst p2000m-cpm-coboard.mx \
      p2000m-cpm-coboard.pin p2000m-cpm-coboard.pla \
      p2000m-cpm-coboard.sim p2000m-cpm-coboard.tt2 \
      p2000m-cpm-coboard.tt3
