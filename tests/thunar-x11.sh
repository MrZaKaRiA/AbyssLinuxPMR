#!/bin/sh
# Launch the actual Thunar with the Abyss theme after migrating a narrow sidebar.
set -eu
: "${ABYSS_THUNAR_INIT:?}" "${SCREENSHOT:?}" "${OUTPUT:?}"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/home/.config" XDG_RUNTIME_DIR="$tmp/runtime"
mkdir -p "$HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
xdg-user-dirs-update
printf 'Xft.dpi: 192\n' | xrdb -merge
xfconf-query -c thunar -p /last-separator-position -n -t int -s 70
"$ABYSS_THUNAR_INIT"
width=$(xfconf-query -c thunar -p /last-separator-position)
[ "$width" = 480 ] || { echo "Unexpected sidebar width: $width" >&2; exit 1; }
for folder in Documents Downloads Pictures Music Videos; do
    grep -F "/$folder" "$XDG_CONFIG_HOME/gtk-3.0/bookmarks" >/dev/null
done
GTK_THEME=Abyss thunar "$HOME" > "$tmp/thunar.log" 2>&1 &
pid=$!
win=
for _ in $(seq 1 80); do
    win=$(xdotool search --onlyvisible --class Thunar 2>/dev/null | head -1 || true)
    [ -z "$win" ] || break
    sleep .2
done
if [ -z "$win" ]; then cat "$tmp/thunar.log" >&2; kill "$pid" 2>/dev/null || :; exit 1; fi
xdotool getwindowname "$win"
xdotool getwindowgeometry "$win"
xdotool windowmove "$win" 0 0
xdotool windowsize "$win" 1280 800
sleep 3
"$SCREENSHOT" "$win" "$OUTPUT"
if grep -i 'theme parsing error' "$tmp/thunar.log"; then kill "$pid" 2>/dev/null || :; exit 1; fi
kill "$pid" 2>/dev/null || :
wait "$pid" 2>/dev/null || :
echo "Thunar launched with a $width px sidebar and five folder bookmarks"
