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
kill "$wm_pid"; wait "$wm_pid" 2>/dev/null || true
dwm >> "$testdir/dwm.log" 2>&1 & wm_pid=$!
sleep 1
abyss-key-capture --list | grep -F "$(printf 'B\t64\tReturn\t64\tF2\tOpen terminal')" >/dev/null
xdotool key --clearmodifiers Super_L+F3
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

# Restore defaults and ensure the original key is grabbed again.
open_editor
select_menu 'Restore all defaults'
select_menu 'Restore defaults'
accept_message
finish_editor
abyss-key-capture --list | grep -F "$(printf 'B\t64\tReturn\t64\tReturn\tOpen terminal')" >/dev/null
if abyss-key-capture --list | grep -q '^A'; then echo 'App shortcut survived restore' >&2; exit 1; fi
echo 'X11 shortcut editor integration: PASS'
