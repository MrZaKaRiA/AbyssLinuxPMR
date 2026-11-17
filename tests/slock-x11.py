#!/usr/bin/env python3
"""Test xss-lock inhibitor handoff using an isolated Xvfb display; run as root.

The invoking user needs a usable password hash in /etc/shadow: slock exits at
startup with "crypt: Invalid argument" for an empty or locked ("!", "*") entry.
"""
import ctypes
import os
import select
import subprocess
import sys

if os.geteuid() != 0 or not os.environ.get('DISPLAY'):
    sys.exit('Run as root under xvfb-run on an isolated display')

read_fd, write_fd = os.pipe()
env = os.environ.copy()
env['XSS_SLEEP_LOCK_FD'] = str(write_fd)
locker = subprocess.Popen([os.environ.get('ABYSS_SLOCK', '/usr/bin/slock')], env=env,
                          pass_fds=(write_fd,), stderr=subprocess.PIPE)
os.close(write_fd)
try:
    ready, _, _ = select.select([read_fd], [], [], 10)
    if not ready or os.read(read_fd, 1) != b'':
        raise RuntimeError('slock did not release the sleep inhibitor')
    if locker.poll() is not None:
        raise RuntimeError('slock exited before locking: ' + locker.stderr.read().decode())
    x11 = ctypes.CDLL('libX11.so.6')
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XGrabKeyboard.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    display = x11.XOpenDisplay(None)
    if not display:
        raise RuntimeError('could not open test display')
    status = x11.XGrabKeyboard(display, x11.XDefaultRootWindow(display), 0, 1, 1, 0)
    x11.XCloseDisplay(display)
    if status != 1:  # AlreadyGrabbed: the locker owns the keyboard.
        raise RuntimeError(f'keyboard was not locked at inhibitor release: XGrabKeyboard={status}')
    print('PASS: slock released inhibitor after acquiring the keyboard')
finally:
    os.close(read_fd)
    locker.terminate()
    try:
        locker.wait(timeout=5)
    except subprocess.TimeoutExpired:
        locker.kill()
        locker.wait()
