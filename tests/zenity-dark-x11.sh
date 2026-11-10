#!/bin/sh
# Exercise the packaged session and a real GTK4/libadwaita Zenity file chooser.
set -eu
: "${ABYSS_SESSION:?}" "${LUMINANCE:?}"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/home" "$tmp/runtime"
chmod 700 "$tmp/runtime"
cat > "$tmp/home/.xinitrc" <<'SESSION'
#!/bin/sh
exec zenity --file-selection --title=Abyss-theme-probe
SESSION
export HOME="$tmp/home" XDG_RUNTIME_DIR="$tmp/runtime"
check() {
    expected=$1
    if [ "$expected" = dark ]; then unset ADW_DEBUG_COLOR_SCHEME
    else ADW_DEBUG_COLOR_SCHEME=prefer-light; export ADW_DEBUG_COLOR_SCHEME; fi
    "$ABYSS_SESSION" &
    pid=$!
    win=
    for _ in $(seq 1 50); do
        win=$(xdotool search --onlyvisible --name '^Abyss-theme-probe$' 2>/dev/null | head -1 || true)
        [ -z "$win" ] || break
        sleep .2
    done
    if [ -z "$win" ]; then kill "$pid" 2>/dev/null || :; echo 'Zenity window did not open' >&2; exit 1; fi
    sleep 2
    value=$("$LUMINANCE" "$win")
    kill "$pid" 2>/dev/null || :
    wait "$pid" 2>/dev/null || :
    echo "$expected chooser average luminance: $value"
    if [ "$expected" = dark ]; then [ "$value" -lt 100 ]
    else [ "$value" -gt 150 ]; fi
}
check dark
check light
