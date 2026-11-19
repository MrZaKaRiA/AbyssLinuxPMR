#!/bin/sh
# Re-render the boot logo PNGs from abyss-logo.svg (needs rsvg-convert from
# librsvg-utils). The PNGs are committed: the package build does not run this.
# Sizes: abyss-boot-splash picks one by screen height (128 px on 1080p,
# 192 on 1440p/1600p, 256 on 4K, 384 above).
set -eu
cd "$(dirname "$0")"
for s in 128 192 256 384; do
	rsvg-convert -w "$s" -h "$s" abyss-logo.svg -o "abyss-logo-$s.png"
done
