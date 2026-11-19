# ==============================================================================
# /usr/share/abyss/abyss-cli.bash  (shipped and updated by abyss-desktop)
# The bash-only part of the Abyss shell helpers: the pkg-ui command and the
# prompt. /etc/profile.d/zz-abyss-cli.sh loads it in interactive bash only
# (not in bash's POSIX mode), because /etc/profile runs every profile.d file
# in every login shell and dash or busybox sh stop at "pkg-ui()" with
# "Syntax error: Bad function name". Do not source it from other shells.
# Do not edit: package updates replace this file.
# ==============================================================================

# 3. Searchable dmenu package browser
pkg-ui() {
    command -v abyss-software >/dev/null 2>&1 && abyss-software --search || {
        echo "abyss-software is not installed." >&2
        return 1
    }
}

# 4. Abyss Linux Cosmic Neon PS1 Prompt
__abyss_git_branch() {
    command -v git >/dev/null 2>&1 || return
    local branch dirty=""
    branch=$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --short HEAD 2>/dev/null) || return
    if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
        dirty="*"
    fi
    printf " \001\033[1;38;5;51m\002(%s%s)\001\033[0m\002" "$branch" "$dirty"
}

__abyss_prompt_cmd() {
    local u_col="197"
    if [ "$(id -u)" -eq 0 ]; then
        u_col="196"
    fi
    PS1="${debian_chroot:+($debian_chroot)}\[\e[1;38;5;${u_col}m\]\u\[\e[0m\]\[\e[38;5;250m\] at \[\e[1;38;5;141m\]\h\[\e[0m\] \[\e[38;5;244m\]in \[\e[1;38;5;191m\]\W\[\e[0m\]\$(__abyss_git_branch) \[\e[1;38;5;${u_col}m\]\$\[\e[0m\] "
}

PROMPT_COMMAND=__abyss_prompt_cmd
