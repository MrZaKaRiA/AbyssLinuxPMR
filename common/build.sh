#!/bin/bash
# ==============================================================================
# common/build.sh [pkg...] - build Abyss packages with Void's xbps-src
#
# Runs as root inside ghcr.io/void-linux/void-glibc-full (CI) or any Void box.
# Clones void-packages, drops srcpkgs/abyss-* into it, builds every package
# natively for x86_64 and cross-compiled for aarch64, and collects the
# resulting .xbps files in ./public/current (unsigned; see common/sign.sh).
#
# Env: ARCHS (default "x86_64 aarch64"), VOID_PACKAGES (clone dir),
#      BUILD_USER (default builder; must be in the xbuilder group)
# ==============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VP="${VOID_PACKAGES:-/tmp/void-packages}"
ARCHS="${ARCHS:-x86_64 aarch64}"
BUILD_USER="${BUILD_USER:-builder}"
OUT="$ROOT/public/current"
HOST_ARCH="$(xbps-uhelper arch)"

if [ $# -gt 0 ]; then
    PKGS="$*"
else
    PKGS="$(cd "$ROOT/srcpkgs" && ls -d abyss-* | tr '\n' ' ')"
fi

as_builder() { sudo -Eu "$BUILD_USER" "$@"; }

if [ ! -d "$VP/.git" ]; then
    git clone --depth 1 https://github.com/void-linux/void-packages.git "$VP"
fi
for p in $PKGS; do
    rm -rf "$VP/srcpkgs/$p"
    cp -a "$ROOT/srcpkgs/$p" "$VP/srcpkgs/$p"
done
chown -R "$BUILD_USER:$BUILD_USER" "$VP"

cd "$VP"
if [ ! -f etc/conf ] || ! grep -q '^XBPS_CHROOT_CMD=' etc/conf; then
    as_builder sh -c 'echo XBPS_ALLOW_RESTRICTED=yes >> etc/conf; echo XBPS_CHROOT_CMD=uchroot >> etc/conf'
fi
[ -d masterdir-"$HOST_ARCH" ] || [ -d masterdir ] || as_builder ./xbps-src binary-bootstrap

for arch in $ARCHS; do
    cross=""
    [ "$arch" != "$HOST_ARCH" ] && cross="-a $arch"
    for p in $PKGS; do
        echo "::group::$p ($arch)"
        # shellcheck disable=SC2086
        as_builder ./xbps-src -j"$(nproc)" $cross pkg "$p"
        echo "::endgroup::"
    done
done

mkdir -p "$OUT"
for p in $PKGS; do
    cp -f hostdir/binpkgs/"$p"-[0-9]*.xbps "$OUT"/
done
ls -l "$OUT"
