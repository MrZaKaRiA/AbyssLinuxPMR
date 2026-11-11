#!/bin/sh
# Exercise the actual Void Rofi parser and launcher with an old user config.
set -eu
: "${ABYSS_ROFI_REPAIR:?}" "${ABYSS_LAUNCHER:?}" "${LEGACY_CONFIG:?}" "${SYSTEM_CONFIG:?}"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
export HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/config"
mkdir -p "$HOME" "$XDG_CONFIG_HOME/rofi" /usr/share/abyss/rofi
cp "$SYSTEM_CONFIG" /usr/share/abyss/rofi/config.rasi
cp "$LEGACY_CONFIG" "$XDG_CONFIG_HOME/rofi/config.rasi"
if rofi -rasi-validate "$XDG_CONFIG_HOME/rofi/config.rasi" >"$tmp/old.out" 2>"$tmp/old.err"; then
  echo 'Legacy fixture unexpectedly passed Rofi validation' >&2; exit 1
fi
"$ABYSS_ROFI_REPAIR"
rofi -rasi-validate "$XDG_CONFIG_HOME/rofi/config.rasi" >"$tmp/new.out" 2>"$tmp/new.err" || { cat "$tmp/new.err" >&2; exit 1; }
# Direct calls should use the repaired user file, not only the Abyss wrapper.
rofi -dump-theme >"$tmp/theme.out" 2>"$tmp/theme.err"
[ -s "$tmp/theme.out" ] || { cat "$tmp/theme.err" >&2; exit 1; }
open_and_cancel() {
    "$@" >"$tmp/launch.out" 2>"$tmp/launch.err" & pid=$!
    win=
    for _ in $(seq 1 50); do
      win=$(xdotool search --onlyvisible --class '[Rr]ofi' 2>/dev/null | head -1 || :)
      [ -z "$win" ] || break
      sleep .2
    done
    if [ -z "$win" ]; then cat "$tmp/launch.err" >&2; kill "$pid" 2>/dev/null || :; return 1; fi
    xdotool key Escape
    wait "$pid" || :
    ! grep -iE 'error while parsing|parser error' "$tmp/launch.err"
}
open_and_cancel rofi -show run
# An unrelated invalid custom config must not be overwritten or prevent Abyss
# launching: use the packaged known-good config as the fallback.
printf 'configuration { invalid syntax here\n' > "$XDG_CONFIG_HOME/rofi/config.rasi"
cp "$XDG_CONFIG_HOME/rofi/config.rasi" "$tmp/custom-before"
open_and_cancel "$ABYSS_LAUNCHER" run
cmp "$tmp/custom-before" "$XDG_CONFIG_HOME/rofi/config.rasi"
echo 'Real Rofi legacy repair, direct launch, and custom-config fallback: PASS'
