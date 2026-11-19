#!/bin/sh
# GnuPG's passphrase window through abyss-desktop's pinentry wrapper is dark;
# plain pinentry-gtk-2 (the GTK 2 default look) is light. Real pinentry-gtk-2
# on a real X server (xvfb-run), measured like the Zenity chooser.
set -eu
: "${ABYSS_PINENTRY_WRAPPER:?}" "${ABYSS_GTK2_RC:?}" "${LUMINANCE:?}"
export ABYSS_GTK2_RC
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp"     # no ~/.gtkrc-2.0 of the runner
check() {  # check dark|light COMMAND
    expected=$1; shift
    title="Abyss-pinentry-probe-$expected"
    # GETPIN keeps the window open until it is killed
    { printf 'SETTITLE %s\nSETDESC Passphrase probe\nGETPIN\n' "$title"; sleep 30; } |
        "$@" >/dev/null 2>&1 &
    pid=$!
    win=
    for _ in $(seq 1 50); do
        win=$(xdotool search --onlyvisible --name "^$title\$" 2>/dev/null | head -1 || true)
        [ -z "$win" ] || break
        sleep .2
    done
    if [ -z "$win" ]; then kill "$pid" 2>/dev/null || :; echo 'pinentry window did not open' >&2; exit 1; fi
    sleep 1
    value=$("$LUMINANCE" "$win")
    kill "$pid" 2>/dev/null || :   # the wrapper execs pinentry-gtk-2: the same process
    echo "$expected pinentry average luminance: $value"
    if [ "$expected" = dark ]; then [ "$value" -lt 100 ]
    else [ "$value" -gt 150 ]; fi
}
check dark /bin/sh "$ABYSS_PINENTRY_WRAPPER"
check light env GTK2_RC_FILES=/dev/null /usr/bin/pinentry-gtk-2
