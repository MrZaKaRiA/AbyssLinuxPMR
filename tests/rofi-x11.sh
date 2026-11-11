#!/bin/sh
# Exercise the real Void Rofi GUI with an old user config and direct calls.
set -eu
: "${ABYSS_ROFI_REPAIR:?}" "${ABYSS_LAUNCHER:?}" "${LEGACY_CONFIG:?}" "${SYSTEM_CONFIG:?}"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
export HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/config"
mkdir -p "$HOME" "$XDG_CONFIG_HOME/rofi" "$tmp/bin" /usr/share/abyss/rofi
PATH="$tmp/bin:$PATH"; export PATH
cp "$ABYSS_ROFI_REPAIR" "$tmp/bin/abyss-rofi-repair"
cp "$SYSTEM_CONFIG" /usr/share/abyss/rofi/config.rasi
cp "$LEGACY_CONFIG" "$XDG_CONFIG_HOME/rofi/config.rasi"
"$ABYSS_ROFI_REPAIR"
cmp "$LEGACY_CONFIG" "$XDG_CONFIG_HOME"/rofi/config.rasi.abyss-backup.*
# An actual Rofi dmenu must return the selected item. A parser-error dialog
# cannot pass this check merely by opening and closing its window.
printf 'legacy-repair-worked\n' | rofi -dmenu -no-custom >"$tmp/direct.out" 2>"$tmp/direct.err" & pid=$!
win=
for _ in $(seq 1 50); do
  win=$(xdotool search --onlyvisible --class '[Rr]ofi' 2>/dev/null | head -1 || :)
  [ -z "$win" ] || break
  sleep .2
done
if [ -z "$win" ]; then cat "$tmp/direct.err" >&2; kill "$pid" 2>/dev/null || :; exit 1; fi
xdotool key Return
wait "$pid" || { cat "$tmp/direct.err" >&2; exit 1; }
grep -Fx 'legacy-repair-worked' "$tmp/direct.out"
# A symlinked legacy config is deliberately not modified. The Abyss launcher
# must still bypass it using the packaged config and run the selected command.
rm "$XDG_CONFIG_HOME/rofi/config.rasi"
ln -s "$LEGACY_CONFIG" "$XDG_CONFIG_HOME/rofi/config.rasi"
printf '#!/bin/sh\nprintf yes > "$HOME/launched"\n' > "$tmp/bin/abyssrofitest"
chmod +x "$tmp/bin/abyssrofitest"
"$ABYSS_LAUNCHER" run >"$tmp/launch.out" 2>"$tmp/launch.err" & pid=$!
win=
for _ in $(seq 1 50); do
  win=$(xdotool search --onlyvisible --class '[Rr]ofi' 2>/dev/null | head -1 || :)
  [ -z "$win" ] || break
  sleep .2
done
if [ -z "$win" ]; then cat "$tmp/launch.err" >&2; kill "$pid" 2>/dev/null || :; exit 1; fi
xdotool type --delay 30 'abyssrofitest'
xdotool key Return
wait "$pid" || { cat "$tmp/launch.err" >&2; exit 1; }
for _ in $(seq 1 30); do [ ! -f "$HOME/launched" ] || break; sleep .2; done
[ "$(cat "$HOME/launched" 2>/dev/null)" = yes ]
[ -L "$XDG_CONFIG_HOME/rofi/config.rasi" ]
echo 'Real Rofi direct launch and legacy symlink fallback: PASS'
