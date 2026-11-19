#!/bin/sh
# Re-render the password field PNGs from their SVGs (needs rsvg-convert from
# librsvg-utils). The PNGs are committed: the package build does not run this.
set -eu
cd "$(dirname "$0")"
for n in field bullet; do
	rsvg-convert -z 1 "abyss-$n.svg" -o "abyss-$n.png"
	rsvg-convert -z 2 "abyss-$n.svg" -o "abyss-$n-2x.png"
done
