#!/usr/bin/env python3
"""Exercise sidebar migration, one-time behavior, and bookmark preservation."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

INIT = Path(os.environ.get('ABYSS_THUNAR_INIT', 'srcpkgs/abyss-desktop/files/bin/abyss-thunar-init')).resolve()

class ThunarInitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.config = self.root / 'config'
        for folder in ('Documents', 'Downloads', 'Pictures', 'Music', 'Videos'):
            (self.root / folder).mkdir()
        self.write('thunar', 'exit 0')
        self.write('xrdb', 'echo "Xft.dpi: ${TEST_DPI:-192}"')
        self.write('xrandr', 'printf "Monitors: 1\\n 0: +*Virtual-1 3600/300x2260/200+0+0 Virtual-1\\n"')
        self.write('xfconf-query', '''
case " $* " in
  *' -s '*) for arg in "$@"; do value=$arg; done; echo "$value" > "$TEST_WIDTH"; echo "$value" >> "$TEST_WRITES" ;;
  *) [ -f "$TEST_WIDTH" ] && cat "$TEST_WIDTH" || exit 1 ;;
esac''')
        self.write('xdg-user-dir', '''case "$1" in DOCUMENTS) echo "$HOME/Documents";; DOWNLOAD) echo "$HOME/Downloads";; PICTURES) echo "$HOME/Pictures";; MUSIC) echo "$HOME/Music";; VIDEOS) echo "$HOME/Videos";; esac''')
        self.write('gio', '''for arg in "$@"; do last=$arg; done; printf 'uri: file://%s\\n' "$last"''')
        self.env = dict(os.environ, HOME=str(self.root), XDG_CONFIG_HOME=str(self.config), PATH=str(self.bin) + os.pathsep + os.environ['PATH'], DBUS_SESSION_BUS_ADDRESS='test', TEST_WIDTH=str(self.root / 'width'), TEST_WRITES=str(self.root / 'writes'))

    def write(self, name, script):
        p = self.bin / name
        p.write_text('#!/bin/sh\n' + script + '\n')
        p.chmod(0o755)

    def run_init(self):
        subprocess.run([str(INIT)], env=self.env, check=True)

    def test_repairs_narrow_sidebar_and_seeds_once(self):
        (self.root / 'width').write_text('100\n')
        self.run_init()
        self.assertEqual((self.root / 'width').read_text(), '480\n')
        bookmarks = self.config / 'gtk-3.0/bookmarks'
        self.assertEqual(len(bookmarks.read_text().splitlines()), 5)
        (self.root / 'width').write_text('120\n')
        bookmarks.unlink()
        self.run_init()
        self.assertEqual((self.root / 'width').read_text(), '120\n')
        self.assertFalse(bookmarks.exists())
        self.assertEqual((self.root / 'writes').read_text().splitlines(), ['480'])

    def test_preserves_wide_sidebar_and_existing_bookmarks(self):
        (self.root / 'width').write_text('500\n')
        bookmarks = self.config / 'gtk-3.0/bookmarks'
        bookmarks.parent.mkdir(parents=True)
        bookmarks.write_text('file:///custom User choice\n')
        self.run_init()
        self.assertEqual((self.root / 'width').read_text(), '500\n')
        self.assertEqual(bookmarks.read_text(), 'file:///custom User choice\n')
        self.assertFalse((self.root / 'writes').exists())

    def test_preserves_legacy_bookmarks(self):
        (self.root / '.gtk-bookmarks').write_text('file:///custom\n')
        self.run_init()
        self.assertFalse((self.config / 'gtk-3.0/bookmarks').exists())
        self.assertTrue((self.config / 'abyss/thunar-bookmarks-v1').exists())

    def test_no_session_does_not_change_settings(self):
        self.env.pop('DBUS_SESSION_BUS_ADDRESS')
        self.run_init()
        self.assertFalse(self.config.exists())

if __name__ == '__main__': unittest.main()
