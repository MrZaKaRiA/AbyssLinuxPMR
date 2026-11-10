import os
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(os.environ.get('ABYSS_CENTER', 'srcpkgs/abyss-desktop/files/bin/abyss-control-center')).resolve()

class TextSize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / 'bin').mkdir()
        (self.root / '.config/abyss').mkdir(parents=True)
        (self.root / '.config/abyss/dpi').write_text('192\n')
        self.stub('xrdb', '''if [ "$1" = -query ]; then echo 'Xft.dpi: 192'; else cat >> "$HOME/merges"; fi''')
        self.stub('timeout', 'shift; exec "$@"')
        self.stub('dmenu', 'cat >/dev/null; printf "%s\\n" "$TEST_ANSWER"')
        self.stub('notify-send', 'exit 0')
        self.env = dict(os.environ, HOME=str(self.root), PATH=str(self.root / 'bin') + os.pathsep + os.environ['PATH'], DISPLAY=':test')

    def stub(self, name, script):
        path = self.root / 'bin' / name
        path.write_text('#!/bin/sh\n' + script + '\n')
        path.chmod(0o755)

    def run_action(self, answer):
        subprocess.run([str(SCRIPT), 'dpi-96'], env=dict(self.env, TEST_ANSWER=answer), check=True)
        return (self.root / 'merges').read_text()

    def test_revert_keeps_previous_preference(self):
        result = self.run_action('Revert to previous size')
        self.assertIn('Xft.dpi: 96', result)
        self.assertTrue(result.rstrip().endswith('xmenu.height: 56'))
        self.assertEqual((self.root / '.config/abyss/dpi').read_text(), '192\n')

    def test_cancel_reverts(self):
        result = self.run_action('')
        self.assertIn('Xft.dpi: 192', result)
        self.assertEqual((self.root / '.config/abyss/dpi').read_text(), '192\n')

    def test_confirm_persists(self):
        result = self.run_action('Keep this size')
        self.assertNotIn('Xft.dpi: 192', result)
        self.assertEqual((self.root / '.config/abyss/dpi').read_text(), '96\n')

if __name__ == '__main__':
    unittest.main()
