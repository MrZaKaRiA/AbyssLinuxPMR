#!/usr/bin/env bash
# Exercise the installed packages and actual X11 input in an isolated Xvfb.
set -euo pipefail
testdir=$(mktemp -d /tmp/abyss-shortcuts-x11.XXXXXX)
display_pid= wm_pid= editor_pid=
cleanup() {
    result=$?
    if [ "$result" -ne 0 ]; then
        echo '--- X server log ---'; cat "$testdir/xvfb.log" 2>/dev/null || true
        echo '--- dwm log ---'; cat "$testdir/dwm.log" 2>/dev/null || true
        echo '--- editor log ---'; cat "$testdir/editor.log" 2>/dev/null || true
        echo '--- shortcut state ---'; abyss-key-capture --list 2>/dev/null || true
    fi
    [ -z "$editor_pid" ] || kill "$editor_pid" 2>/dev/null || true
    [ -z "$wm_pid" ] || kill "$wm_pid" 2>/dev/null || true
    [ -z "$display_pid" ] || kill "$display_pid" 2>/dev/null || true
    exit "$result"
}
trap cleanup EXIT
export DISPLAY=:98 XDG_CONFIG_HOME="$testdir/config" XDG_CACHE_HOME="$testdir/cache" XDG_DATA_HOME="$testdir/data"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME/applications"
Xvfb "$DISPLAY" -screen 0 1280x900x24 -nolisten tcp -ac > "$testdir/xvfb.log" 2>&1 &
display_pid=$!
for _ in $(seq 1 100); do xdotool getdisplaygeometry >/dev/null 2>&1 && break; sleep .1; done
xdotool getdisplaygeometry >/dev/null
dwm > "$testdir/dwm.log" 2>&1 &
wm_pid=$!
for _ in $(seq 1 100); do abyss-key-capture --list > "$testdir/bindings" 2>/dev/null && break; sleep .1; done
grep -F "$(printf 'B\t64\tReturn\t64\tReturn\tOpen terminal')" "$testdir/bindings" >/dev/null

# Verify Void's image viewer and both forms of the img command in X11.
xbps-query -p pkgver nsxiv
test -r /usr/share/applications/nsxiv.desktop
test -r /usr/share/applications/abyss-images.desktop
mkdir -p "$testdir/Pictures" "$testdir/bin"
python3 - "$testdir/Pictures/test.png" <<'PY'
import struct, sys, zlib
def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
image = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
image += chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00')) + chunk(b'IEND', b'')
with open(sys.argv[1], 'wb') as output: output.write(image)
PY
printf '#!/bin/sh\nprintf "%%s\\n" "%s"\n' "$testdir/Pictures" > "$testdir/bin/xdg-user-dir"
chmod 755 "$testdir/bin/xdg-user-dir"
export PATH="$testdir/bin:$PATH"
wait_image() {
    for _ in $(seq 1 100); do
        if xdotool search --onlyvisible --class '^Nsxiv$' >/dev/null 2>&1; then return; fi
        sleep .1
    done
    echo 'Timed out waiting for nsxiv' >&2; return 1
}
img "$testdir/Pictures/test.png" > "$testdir/image.log" 2>&1 &
viewer_pid=$!
wait_image
xdotool search --onlyvisible --class '^Nsxiv$' | head -1 | xargs xdotool windowclose
wait "$viewer_pid" || true
sleep .5
img
wait_image
xdotool search --onlyvisible --class '^Nsxiv$' | head -1 | xargs xdotool windowclose
sleep .5
abyss-apps --list | awk -F '\t' '$2 == "exec:abyss-control-center images" {found=1} END {exit !found}'
echo 'nsxiv and img launcher: PASS'

if abyss-key-capture --probe 64 Return; then
    echo 'Expected Super+Return to be reported as taken' >&2; exit 1
else
    [ "$?" -eq 3 ] || exit 1
fi
abyss-key-capture --probe 64 F2

wait_menu() {
    for _ in $(seq 1 100); do
        if xdotool search --onlyvisible --class '^dmenu$' >/dev/null 2>&1; then sleep .2; return; fi
        sleep .1
    done
    echo 'Timed out waiting for dmenu' >&2; return 1
}
select_menu() {
    wait_menu
    xdotool type --clearmodifiers --delay 2 "$1"
    xdotool key Return
    sleep .5
}
accept_message() { wait_menu; xdotool key Return; sleep .5; }
capture_shortcut() {
    for _ in $(seq 1 100); do
        if xdotool search --onlyvisible --name '^Press a shortcut$' >/dev/null 2>&1; then break; fi
        sleep .1
    done
    xdotool search --onlyvisible --name '^Press a shortcut$' >/dev/null
    sleep .5
    xdotool key --clearmodifiers "Super_L+$1"
    sleep 1.5
}
open_editor() { abyss-shortcut-editor > "$testdir/editor.log" 2>&1 & editor_pid=$!; sleep .3; }
finish_editor() { select_menu Done; wait "$editor_pid"; editor_pid=; }

# Change an actual built-in binding through the dmenu interface.
open_editor
select_menu 'System shortcuts'
select_menu 'Open terminal'
select_menu 'Change shortcut'
capture_shortcut F2
accept_message
finish_editor
abyss-key-capture --list | grep -F "$(printf 'B\t64\tReturn\t64\tF2\tOpen terminal')" >/dev/null
abyss-shortcuts </dev/null | grep -F 'Super+F2' >/dev/null
abyss-key-capture --probe 64 Return
if abyss-key-capture --probe 64 F2; then echo 'Changed key was not grabbed' >&2; exit 1; else [ "$?" -eq 3 ]; fi

# Add an installed .desktop entry, restart dwm, and launch it using the key.
cat > "$XDG_DATA_HOME/applications/abyss-test.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Abyss test app
Exec=/usr/bin/touch $testdir/app-fired
Categories=Utility;
EOF
open_editor
select_menu 'Add application shortcut'
select_menu 'Abyss test app'
capture_shortcut F3
accept_message
finish_editor
open_editor
select_menu 'Application shortcuts'
select_menu 'Abyss test app'
select_menu 'Change shortcut'
capture_shortcut F4
accept_message
finish_editor
abyss-key-capture --probe 64 F3
abyss-key-capture --list | awk -F '\t' '$1 == "A" && $3 == 64 && $4 == "F4" && $5 ~ /Abyss test app/ { found=1 } END { exit !found }'
abyss-shortcuts </dev/null | grep -F 'Launch Abyss test app' >/dev/null
kill "$wm_pid"; wait "$wm_pid" 2>/dev/null || true
dwm >> "$testdir/dwm.log" 2>&1 & wm_pid=$!
sleep 1
abyss-key-capture --list | grep -F "$(printf 'B\t64\tReturn\t64\tF2\tOpen terminal')" >/dev/null
xdotool key --clearmodifiers Super_L+F4
for _ in $(seq 1 50); do [ -e "$testdir/app-fired" ] && break; sleep .1; done
test -e "$testdir/app-fired"

# A taken shortcut must be rejected without changing the saved configuration.
cp "$XDG_CONFIG_HOME/abyss/shortcuts.conf" "$testdir/before-conflict"
open_editor
select_menu 'Add application shortcut'
select_menu 'Abyss test app'
capture_shortcut F2
accept_message
finish_editor
cmp "$testdir/before-conflict" "$XDG_CONFIG_HOME/abyss/shortcuts.conf"

# Disable a built-in binding, then restore defaults and its original key.
open_editor
select_menu 'System shortcuts'
select_menu 'Open terminal'
select_menu 'Disable shortcut'
accept_message
finish_editor
abyss-key-capture --list | grep -F "$(printf 'B\t64\tReturn\t0\t-\tOpen terminal')" >/dev/null
abyss-key-capture --probe 64 F2
open_editor
select_menu 'Restore all defaults'
select_menu 'Restore defaults'
accept_message
finish_editor
abyss-key-capture --list | grep -F "$(printf 'B\t64\tReturn\t64\tReturn\tOpen terminal')" >/dev/null
if abyss-key-capture --list | grep -q '^A'; then echo 'App shortcut survived restore' >&2; exit 1; fi
echo 'X11 shortcut editor integration: PASS'
