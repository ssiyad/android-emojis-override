#!/usr/bin/env bash
# Build the module zip: fetch the sources, build and verify the font, package.
# The zip goes to OUT.
set -euo pipefail
cd "$(dirname "$0")"
out=${OUT:-../zips}
version=$(sed -n 's/^version=//p' module/module.prop)
run() { uv run -q --project build python -I "$@"; }

build/fetch.sh
run build/build.py build/cache/src build/cache/out/AppleColorEmoji.ttf
run build/verify.py build/cache/src build/cache/out/AppleColorEmoji.ttf
run build/package.py module build/cache/out/AppleColorEmoji.ttf "$out/apple-emoji-$version.zip"
