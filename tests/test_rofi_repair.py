#!/usr/bin/env python3
"""Repair the exact legacy Rofi bug while preserving personal configuration."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPAIR = Path(os.environ.get('ABYSS_ROFI_REPAIR', ROOT / 'srcpkgs/abyss-desktop/files/bin/abyss-rofi-repair'))
FIXTURE = (ROOT / 'tests/fixtures/rofi-27.1-broken.rasi').read_text()
BROKEN = '}";\n    font:                "JetBrainsMono Nerd Font 11";\n    terminal:            "st";\n}'

class RofiRepairTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.config = self.home / 'config' / 'rofi' / 'config.rasi'
        self.config.parent.mkdir(parents=True)
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / 'config'))

    def repair(self):
        return subprocess.run([str(REPAIR)], env=self.env, text=True, capture_output=True, check=True)

    def test_repairs_original_and_keeps_a_backup(self):
        original = FIXTURE.replace('abyss-accent:  #a855f7;', 'abyss-accent:  #123456;')
        self.assertIn(BROKEN, original)
        self.config.write_text(original)
        self.config.chmod(0o640)
        self.repair()
        self.assertEqual(self.config.read_text(), original.replace(BROKEN, '}'))
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o640)
        backups = list(self.config.parent.glob('config.rasi.abyss-backup.*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), original)
        self.repair()
        self.assertEqual(len(list(self.config.parent.glob('config.rasi.abyss-backup.*'))), 1)

    def test_unrelated_or_edited_stanza_is_not_overwritten(self):
        custom = FIXTURE.replace('font:                "JetBrainsMono Nerd Font 11";\n    terminal:            "st";\n}\n', 'font: "Custom Font 16";\n    terminal: "my-terminal";\n}\n', 1)
        self.config.write_text(custom)
        self.repair()
        self.assertEqual(self.config.read_text(), custom)
        self.assertEqual(list(self.config.parent.glob('config.rasi.abyss-backup.*')), [])

    def test_does_not_follow_a_user_symlink(self):
        target = self.home / 'custom.rasi'
        target.write_text(FIXTURE)
        self.config.symlink_to(target)
        self.repair()
        self.assertTrue(self.config.is_symlink())
        self.assertEqual(target.read_text(), FIXTURE)

    def test_valid_config_and_missing_config_remain_unchanged(self):
        valid = FIXTURE.replace(BROKEN, '}')
        self.config.write_text(valid)
        self.repair()
        self.assertEqual(self.config.read_text(), valid)
        self.config.unlink()
        self.repair()
        self.assertFalse(self.config.exists())

if __name__ == '__main__': unittest.main()
