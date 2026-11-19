# abyss-boot: the boot logo (plymouth, started in the initramfs) must never
# hide the text console when it is needed. Sourced by runit stage 1.
#  - An emergency shell (failed fsck, missing disk, ...) first takes the
#    logo away, then shows the boot log and the shell (same text as Void's)
#    on the screen: on the first VT when the kernel's console is a serial
#    port (virtual machines and some ARM boards), where it would be invisible.
#  - Without LightDM, plymouth stops here (the picture stays until the text
#    login draws over it), so nothing waits behind it.
#  - With LightDM, the login screen takes over from the logo; if it has not
#    after 60 seconds, the logo goes anyway.

if command -v plymouth >/dev/null 2>&1 && plymouth --ping >/dev/null 2>&1; then
    emergency_shell() {
        plymouth quit >/dev/null 2>&1
        con=/dev/console
        # /proc/consoles marks the console /dev/console is with "C"
        if [ -c /dev/tty1 ] && ! grep -q '^tty[0-9][0-9]* .*(.*C' /proc/consoles 2>/dev/null; then
            con=/dev/tty1
            chvt 1 >/dev/null 2>&1
        fi
        exec <"$con" >"$con" 2>&1
        [ -r /run/abyss-boot.log ] && cat /run/abyss-boot.log
        echo
        echo "Cannot continue due to errors above, starting emergency shell."
        echo "When ready type exit to continue booting."
        /bin/sh -l
    }
    if [ -e /etc/runit/runsvdir/default/lightdm ] || [ -e /var/service/lightdm ]; then
        ( sleep 60; plymouth --ping && plymouth quit ) </dev/null >/dev/null 2>&1 &
    else
        plymouth quit --retain-splash >/dev/null 2>&1
    fi
fi
