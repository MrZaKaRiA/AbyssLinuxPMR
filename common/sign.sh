#!/bin/bash
# ==============================================================================
# common/sign.sh <dir> - index and sign an XBPS repository directory
#
# Writes <arch>-repodata for every architecture found in <dir>, then signs the
# repodata and every package with the Abyss key. The private key comes from
# $XBPS_SIGNING_KEY (PEM text, a GitHub Actions secret) or $XBPS_SIGNING_KEY_FILE.
# The matching public key is keys/abyss-pmr.plist (fingerprint in keys/FINGERPRINT).
# ==============================================================================
set -euo pipefail

DIR="$(cd "${1:?usage: $0 <repo-dir>}" && pwd)"
SIGNED_BY="Abyss Linux"

KEY="${XBPS_SIGNING_KEY_FILE:-}"
if [ -z "$KEY" ]; then
    [ -n "${XBPS_SIGNING_KEY:-}" ] || { echo "sign.sh: no signing key given" >&2; exit 1; }
    KEY="$(mktemp)"
    trap 'rm -f "$KEY"' EXIT
    printf '%s\n' "$XBPS_SIGNING_KEY" > "$KEY"
    chmod 600 "$KEY"
fi

cd "$DIR"
rm -f ./*-repodata ./*.sig ./*.sig2
archs="$(ls ./*.xbps | sed -E 's/.*\.([^.]+)\.xbps$/\1/' | grep -vx noarch | sort -u)"

for arch in $archs; do
    # noarch packages (themes, scripts) belong in every architecture's index
    set -- "$DIR"/*."$arch".xbps
    for n in "$DIR"/*.noarch.xbps; do [ -e "$n" ] && set -- "$@" "$n"; done
    XBPS_TARGET_ARCH="$arch" xbps-rindex -a "$@"
    XBPS_TARGET_ARCH="$arch" xbps-rindex --privkey "$KEY" --sign --signedby "$SIGNED_BY" "$DIR"
done
xbps-rindex --privkey "$KEY" --sign-pkg "$DIR"/*.xbps

ls -l "$DIR"
