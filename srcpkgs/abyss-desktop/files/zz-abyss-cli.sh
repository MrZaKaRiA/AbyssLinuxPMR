# ==============================================================================
# /etc/profile.d/zz-abyss-cli.sh  (shipped and updated by abyss-desktop)
# Lightweight interactive shell helpers and Void package shortcuts.
# /etc/profile runs this file in EVERY login shell (dash, busybox sh, bash):
# keep it POSIX sh. Bash-only parts go in /usr/share/abyss/abyss-cli.bash.
# Do not edit: package updates replace this file. Put your own definitions in
# ~/.bashrc (or another /etc/profile.d file) instead.
# The zz- name makes it load after every other profile.d file, including an
# old locally edited 99-void-dev-cli.sh, so these definitions win.
# ==============================================================================

# 1. Interactive shell guard — never affect non-interactive scripts or Makefiles
# (except the single root process the package helpers start: see __abyss_as_root).
case $- in
    *i*) ;;
    *) [ "${__abyss_root_step:-}" = 1 ] || return ;;
esac

# This file, by absolute path, so that root process can load the helpers.
__abyss_cli_file=${BASH_SOURCE:-/etc/profile.d/zz-abyss-cli.sh}
case $__abyss_cli_file in /*) ;; *) __abyss_cli_file="$PWD/$__abyss_cli_file" ;; esac

if [ "${__abyss_root_step:-}" != 1 ]; then
    # Login shells load this file more than once (/etc/profile, then ~/.bashrc);
    # add each directory only once.
    case ":${PATH}:" in
        *":${HOME}/.local/bin:"*) ;;
        *) PATH="${HOME}/.local/bin:${PATH}" ;;
    esac
    case ":${PATH}:" in
        *":/usr/local/bin:"*) ;;
        *) PATH="/usr/local/bin:${PATH}" ;;
    esac
    export PATH
    if command -v code >/dev/null 2>&1; then
        export EDITOR="code --wait" VISUAL="code --wait"
    else
        export EDITOR=vi VISUAL=vi
    fi
fi

# Run a command as root: directly when the shell already is root (doas only
# knows the wheel rules, and root needs no privilege tool), otherwise through
# doas, or sudo when doas is absent.
abyss_priv() {
    if [ "$(id -u)" -eq 0 ]; then "$@"
    elif command -v doas >/dev/null 2>&1; then doas "$@"
    else sudo "$@"; fi
}

# 2. Natural XBPS Package Management Functions
# Wait politely while another xbps command holds the package database.
__abyss_xbps_wait() {
    __abyss_xbps_busy || return 0
    echo "Another install or update is running; this one will start when it finishes. (Ctrl+C cancels)" >&2
    while __abyss_xbps_busy; do sleep "${ABYSS_LOCK_POLL:-2}"; done
}
__abyss_xbps_busy() {
    pgrep -x xbps-install >/dev/null 2>&1 || pgrep -x xbps-remove >/dev/null 2>&1
}

# Run a whole package step (lock wait, sync with retries, then the action) as
# root in ONE privileged process, so the password is asked once. doas only
# remembers a password for later doas calls from the same parent process, and
# the old helpers ran the sync from a pipeline subshell, so it asked twice.
__abyss_as_root() {  # __abyss_as_root update|upgrade|install [ARGS...]
    local step=$1 mark rc
    shift
    if [ "$(id -u)" -eq 0 ]; then "__abyss_root_$step" "$@"; return; fi
    # The root process removes the marker first: if it is still there, the
    # privilege tool refused (wrong password) and nothing ran.
    mark=$(mktemp "${TMPDIR:-/tmp}/abyss-elevate.XXXXXX") || return 1
    abyss_priv /bin/sh -c '__abyss_root_step=1; rm -f "$1"; ABYSS_RETRY_PAUSE=$2 ABYSS_LOCK_POLL=$3; . "$4" || exit 1; step=$5; shift 5; "__abyss_root_$step" "$@"' \
        sh "$mark" "${ABYSS_RETRY_PAUSE:-5}" "${ABYSS_LOCK_POLL:-2}" "$__abyss_cli_file" "$step" "$@"
    rc=$?
    if [ -e "$mark" ]; then
        rm -f "$mark"
        echo "This needs your password (doas or sudo); nothing was changed." >&2
        return 1
    fi
    [ "$step" != install ] || __abyss_audio_now "$@"
    return "$rc"
}

# Update the package lists (as root); retry network errors twice before explaining.
__abyss_sync() {
    local try=1 log rc
    log=$(mktemp) || return 1
    while :; do
        # Stream the output (xbps may ask to import a repository key).
        { xbps-install -S; echo $? >"$log.rc"; } 2>&1 | tee "$log"
        rc=$(cat "$log.rc" 2>/dev/null || echo 1); rm -f "$log.rc"
        if [ "$rc" -eq 0 ] && ! grep -q ERROR "$log"; then rm -f "$log"; return 0; fi
        [ "$try" -lt 3 ] || break
        echo "A package server could not be reached; trying again in ${ABYSS_RETRY_PAUSE:-5}s..." >&2
        sleep "${ABYSS_RETRY_PAUSE:-5}"; try=$((try + 1))
    done
    if grep -qiE 'resolv|name or service' "$log"; then
        echo "The package servers could not be found (DNS). Check your network connection, then run: update" >&2
    else
        echo "The package lists could not be updated. Check your network connection, then run: update" >&2
    fi
    rm -f "$log"
    return 1
}

__abyss_root_update() {
    __abyss_xbps_wait
    __abyss_sync && echo "Package lists updated."
}

# Upgrade, then say what happened: xbps prints nothing when there is nothing
# to do. The package database (before/after) tells what really changed.
__abyss_root_upgrade() {
    local log rc changed
    __abyss_xbps_wait
    __abyss_sync || echo "Upgrading with the package lists already on this computer." >&2
    __abyss_xbps_wait
    log=$(mktemp) || return 1
    xbps-query -l 2>/dev/null | awk '{ print $2 }' >"$log.before"
    { xbps-install -u "$@"; echo $? >"$log.rc"; } 2>&1 | tee "$log"
    rc=$(cat "$log.rc" 2>/dev/null || echo 1)
    # name-version of every package that is new or changed, "(new)" when it
    # was not installed before.
    xbps-query -l 2>/dev/null | awk '{ print $2 }' >"$log.after"
    changed=$(awk 'function name(p) { sub(/-[^-]*$/, "", p); return p }
        FILENAME == ARGV[1] { had[$1] = 1; was[name($1)] = 1; next }
        !($1 in had) { print "  " $1 ((name($1) in was) ? "" : " (new)") }' "$log.before" "$log.after")
    echo
    if [ "$rc" -ne 0 ]; then
        if grep -q "package must be updated" "$log"; then
            echo "The package manager must be updated first: run 'upgrade xbps', then 'upgrade' again." >&2
        else
            echo "The upgrade did not finish (xbps-install exit $rc); see the messages above." >&2
        fi
    elif [ -n "$changed" ]; then
        echo "Updated $(printf '%s\n' "$changed" | grep -c .) package(s):"
        printf '%s\n' "$changed"
    elif grep -q Aborting "$log"; then
        echo "Nothing was updated."
    elif [ "$#" -gt 0 ]; then
        echo "Already up to date: $*"
    else
        echo "System is up to date."
    fi
    rm -f "$log" "$log.rc" "$log.before" "$log.after"
    [ "$rc" -ne 0 ] || __abyss_clean_cache
    return "$rc"
}

# `install pipewire` (or wireplumber, pipewire-pulse) in a desktop session:
# start PipeWire for that session now instead of at the next login
# (session-audio checks for a user's graphical session).
__abyss_audio_now() {
    local audio=${ABYSS_SESSION_AUDIO:-/usr/libexec/abyss-desktop/session-audio} pkg
    for pkg in "$@"; do
        case $pkg in
            pipewire|wireplumber|pipewire-pulse) [ ! -x "$audio" ] || "$audio" now; return 0 ;;
        esac
    done
    return 0
}

__abyss_root_install() {
    local rc
    __abyss_xbps_wait
    __abyss_sync || echo "Continuing with the package lists already on this computer." >&2
    __abyss_xbps_wait
    xbps-install "$@"
    rc=$?
    [ "$rc" -ne 0 ] || __abyss_clean_cache
    return "$rc"
}

# After a successful install or upgrade: drop the package versions no
# repository offers any more from the cache, and say how much that freed.
__abyss_clean_cache() {
    local care=${ABYSS_DISK_CARE:-/usr/libexec/abyss-desktop/disk-care}
    [ ! -x "$care" ] || "$care" clean-cache
}

update() {
    __abyss_as_root update
}

upgrade() {
    __abyss_as_root upgrade "$@"
}

search() {
    xbps-query -Rs "$@"
}

remove() {
    abyss_priv xbps-remove -R "$@"
}

cleanup() {
    abyss_priv xbps-remove -Oo
}

# Safe `install` wrapper:
# Delegates to GNU coreutils `/usr/bin/install` (`command install`) whenever
# any option flag starting with `-` is passed (e.g., `-m`, `-d`, `-D`, `-c`, `-o`, `-g`)
# or when more than 1 path-like argument containing `/` is passed.
# Otherwise installs packages via XBPS with doas (or sudo if installed).
install() {
    if [ "$#" -eq 0 ]; then
        command install
        return $?
    fi

    local arg
    local slash_count=0
    for arg in "$@"; do
        case "$arg" in
            -*)
                command install "$@"
                return $?
                ;;
            */*)
                slash_count=$(( slash_count + 1 ))
                ;;
        esac
    done

    if [ "$slash_count" -gt 1 ]; then
        command install "$@"
        return $?
    fi

    __abyss_as_root install "$@"
}

# The root process (__abyss_as_root) needs only the package helpers above.
[ "${__abyss_root_step:-}" = 1 ] && return 0

# 3-4. pkg-ui and the prompt are bash-only: a function name like pkg-ui is a
# syntax error that dash and busybox sh report while parsing this file (the
# emergency shell, any `sh -l`), so they live in a file only bash reads.
__abyss_cli_bash=/usr/share/abyss/abyss-cli.bash
if [ -n "${BASH_VERSION:-}" ] && [ -r "$__abyss_cli_bash" ] && ! shopt -oq posix; then
    . "$__abyss_cli_bash"
fi

# 5. Modern CLI Tool Aliases
if command -v eza >/dev/null 2>&1; then
    alias ls='eza --icons --group-directories-first'
    alias ll='eza -la --icons --group-directories-first --git'
    alias lt='eza --tree --level=2 --icons --group-directories-first'
fi

if command -v bat >/dev/null 2>&1; then
    alias cat='bat --style=plain --paging=never'
fi

if command -v btop >/dev/null 2>&1; then
    alias top='btop'
fi
