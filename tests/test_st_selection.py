"""st's text selection: drawn in Abyss purple (selectionfg/selectionbg) rather
than by swapping each cell's colours, which turned a selection into a bright
#f3e8ff block. Reads the abyss-st patches; with ABYSS_ST_TARBALL (the
st-0.9.3 tarball) and ABYSS_ST_TREE (AbyssLinux/st) set, it also checks that
the patches applied to upstream reproduce that tree exactly."""
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCHES = ROOT / 'srcpkgs/abyss-st/patches'
SEL_PATCH = PATCHES / '30-selection-colors.patch'


def added(patch, name):
    """The '+' lines of one file's hunks in a patch."""
    out, cur = [], None
    for line in patch.read_text().splitlines():
        if line.startswith('diff --git '):
            cur = line.split(' b/')[-1]
        elif cur == name and line.startswith('+') and not line.startswith('+++'):
            out.append(line[1:])
    return out


def luminance(hexcol):
    def chan(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class SelectionColours(unittest.TestCase):
    def colour(self, index):
        for line in added(PATCHES / '10-abyss.patch', 'config.def.h') + added(SEL_PATCH, 'config.def.h'):
            m = re.match(r'\s*"(#[0-9a-fA-F]{6})", /\* %d -> ' % index, line)
            if m:
                return m.group(1)
        self.fail('no colour %d in the abyss-st patches' % index)

    def index(self, name):
        for line in added(SEL_PATCH, 'config.def.h'):
            m = re.match(r'unsigned int %s = (\d+);' % name, line)
            if m:
                return int(m.group(1))
        self.fail('%s is not set' % name)

    def test_selection_is_readable_and_not_a_light_block(self):
        fg = self.colour(self.index('selectionfg'))
        bg = self.colour(self.index('selectionbg'))
        terminal_bg = self.colour(259)
        self.assertGreaterEqual(contrast(fg, bg), 4.5, 'selected text must stay readable (WCAG AA)')
        # The old selection was #f3e8ff on #0d0b18 (16.5:1), a flash on a dark screen.
        self.assertLess(contrast(bg, terminal_bg), 6, 'selection should not glare against the background')
        self.assertGreater(contrast(bg, terminal_bg), 2, 'selection must still be visible')

    def test_selected_cells_are_marked_not_reversed(self):
        xc = SEL_PATCH.read_text()
        self.assertIn('-\t\t\tnew.mode ^= ATTR_REVERSE;', xc)
        self.assertIn('+\t\t\tnew.mode |= ATTR_SELECTED;', xc)   # xdrawline
        self.assertIn('+\t\tog.mode |= ATTR_SELECTED;', xc)       # cell under the old cursor
        self.assertIn('bg = &dc.col[selectionbg];', xc)
        self.assertIn('\tATTR_SELECTED   = 1 << 11,', added(SEL_PATCH, 'st.h'))


@unittest.skipUnless(os.environ.get('ABYSS_ST_TARBALL') and os.environ.get('ABYSS_ST_TREE'),
                     'set ABYSS_ST_TARBALL and ABYSS_ST_TREE to compare with AbyssLinux/st')
class PatchesReproduceTree(unittest.TestCase):
    def test_patches_reproduce_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            with tarfile.open(os.environ['ABYSS_ST_TARBALL']) as tar:
                tar.extractall(tmp)
            src = Path(tmp) / 'st-0.9.3'
            for p in sorted(PATCHES.glob('*.patch')):
                subprocess.run(['patch', '-p1', '-s', '-i', str(p)], cwd=src, check=True)
            diff = subprocess.run(['diff', '-r', str(src), os.environ['ABYSS_ST_TREE']],
                                  stdout=subprocess.PIPE, text=True)
            self.assertEqual(diff.returncode, 0, diff.stdout)


if __name__ == '__main__':
    unittest.main()
