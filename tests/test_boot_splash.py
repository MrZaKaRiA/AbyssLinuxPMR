"""abyss-boot: the clean start (Abyss logo from GRUB to the login screen).

  * INSTALL post on a system installed from an older image (run the way xbps
    runs it, in a temporary root): only the /etc/default/grub lines an Abyss
    image shipped change (galaxy GRUB_BACKGROUND, fixed GRUB_GFXMODE, kernel
    line), edited files stay as they are, a second run changes nothing; the
    plymouth theme becomes abyss-logo unless the user chose another one; the
    tty1 text login goes once, only while LightDM is enabled; nothing touches
    GRUB's menu or the initramfs outside the running system.
  * abyss-boot-splash picks the screen size (built-in panel first) and the
    logo size, and remakes the picture only when one of them changed.
  * /etc/grub.d/05_abyss_splash steps aside for a visible menu or the user's
    own GRUB_BACKGROUND / GRUB_THEME, and its GRUB script passes
    grub-script-check when that is installed.
  * The plymouth theme, the logo PNGs and the template agree on file names.

Files come from srcpkgs/abyss-boot (or ABYSS_BOOT_PKG).
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PKG = Path(os.environ.get('ABYSS_BOOT_PKG') or ROOT / 'srcpkgs/abyss-boot')
FIXTURES = Path(__file__).resolve().parent / 'fixtures/default-grub'
SHIPPED = sorted(FIXTURES.glob('*.grub'))

# Same prologue as void-packages common/hooks/post-install/04-create-xbps-metadata-scripts.sh,
# with a directory of stand-in commands first in PATH
HEADER = '''#!/bin/sh
export PATH="{fake}:/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin"
TRIGGERSDIR="./usr/libexec/xbps-triggers"
ACTION="$1"
PKGNAME="$2"
VERSION="$3"
UPDATE="$4"
CONF_FILE="$5"
ARCH="$6"
'''
CMDLINE = ('quiet splash loglevel=3 rd.udev.log_level=3 udev.log_level=3 '
           'vt.global_cursor_default=0 plymouth.ignore-serial-consoles')


def settings(text):
    """Active KEY=value lines of a /etc/default/grub."""
    return dict(l.split('=', 1) for l in text.splitlines() if re.match(r'^[A-Z_]+=', l))


def plymouth_reads_theme(text):
    """The theme plymouth-set-default-theme finds in a plymouthd.conf: its awk
    splits the file into sections and takes Theme= only when it is the first
    key of one (a DeviceScale= before it hides it: back to the default)."""
    text = ''.join(l for l in text.splitlines(True) if not l.startswith('#'))
    for record in re.split(r'\[[ \t]*\S+[\]\n]', text)[1:]:
        fields = re.split(r'[=\s]+', record)
        if 'Theme' in fields[0]:
            return fields[1]
    return ''


@unittest.skipUnless((PKG / 'INSTALL').is_file() and shutil.which('cmp'), 'abyss-boot package not found; set ABYSS_BOOT_PKG')
class InstallTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name).resolve()
        self.root = base / 'root'
        self.fake = base / 'fake'
        for d in ('etc/default', 'etc/runit/runsvdir/default', 'boot/grub'):
            (self.root / d).mkdir(parents=True)
        self.fake.mkdir()
        # plymouth-set-default-theme stand-in: prints / stores the theme name
        self.theme = base / 'theme'
        self.theme.write_text('spinner\n')
        self.log = base / 'calls'
        (self.root / 'etc/plymouth').mkdir(parents=True)
        self.plyconf = self.root / 'etc/plymouth/plymouthd.conf'
        self.plyconf.write_text('# stock\n[Daemon]\n')
        # (setting works like the real one: Theme= goes right after [Daemon],
        # the rest of the file stays)
        self.stub('plymouth-set-default-theme',
                  f'if [ $# -eq 0 ]; then cat "{self.theme}"; else echo "$1" > "{self.theme}"; '
                  f'awk -v t="$1" \'/^Theme[[:blank:]]*=/ {{ next }} {{ print }} /^\\[Daemon\\]$/ {{ print "Theme=" t }}\' '
                  f'"{self.plyconf}" > "{self.plyconf}.new" && mv "{self.plyconf}.new" "{self.plyconf}"; fi')
        # anything that would act on the real system must not run here
        for cmd in ('grub-mkconfig', 'dracut', 'update-grub'):
            self.stub(cmd, f'echo "{cmd} $*" >> "{self.log}"; exit 1')
        self.script = base / 'INSTALL'
        self.script.write_text(HEADER.format(fake=self.fake) + (PKG / 'INSTALL').read_text() + '\nexit 0\n')

    def stub(self, name, body):
        p = self.fake / name
        p.write_text('#!/bin/sh\n' + body + '\n')
        p.chmod(0o755)

    def install(self):
        r = subprocess.run(['/bin/sh', str(self.script), 'post', 'abyss-boot', '1.0_1', 'no', 'no', 'x86_64'],
                           cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout)
        return r.stdout

    def grub(self):
        return self.root / 'etc/default/grub'

    def test_shipped_files_get_the_logo_and_keep_everything_else(self):
        self.assertEqual(len(SHIPPED), 3)
        for fixture in SHIPPED:
            with self.subTest(fixture.name):
                shutil.copy(fixture, self.grub())
                before = settings(fixture.read_text())
                out = self.install()
                after = settings(self.grub().read_text())
                self.assertNotIn('GRUB_BACKGROUND', after)
                self.assertIn('#GRUB_BACKGROUND=', self.grub().read_text())
                self.assertEqual(after['GRUB_GFXMODE'], 'auto')
                self.assertEqual(after['GRUB_CMDLINE_LINUX_DEFAULT'], f'"{CMDLINE}"')
                for key in set(before) - {'GRUB_BACKGROUND', 'GRUB_GFXMODE', 'GRUB_CMDLINE_LINUX_DEFAULT'}:
                    self.assertEqual(after[key], before[key], key)
                self.assertEqual(after['GRUB_TIMEOUT_STYLE'], 'hidden')
                self.assertEqual(self.grub().stat().st_mode & 0o777, 0o644)
                self.assertIn('Abyss logo instead of the galaxy picture', out)
                # a second run (every later update) changes nothing
                text = self.grub().read_text()
                self.assertNotIn('galaxy', self.install())
                self.assertEqual(self.grub().read_text(), text)

    def test_edited_lines_are_kept(self):
        text = SHIPPED[-1].read_text()
        text = text.replace('GRUB_BACKGROUND="/usr/share/backgrounds/abyss/abyss-splash.png"',
                            'GRUB_BACKGROUND="/boot/my.png"')
        text = text.replace('GRUB_GFXMODE=1920x1080,1024x768,auto', 'GRUB_GFXMODE=2560x1440')
        text = text.replace('vt.global_cursor_default=0"', 'vt.global_cursor_default=0 nomodeset"')
        self.grub().write_text(text)
        self.install()
        # (only the comment above the kernel line may be brought up to date)
        self.assertEqual(settings(self.grub().read_text()), settings(text))
        self.assertIn('GRUB_BACKGROUND="/boot/my.png"', self.grub().read_text())

    def test_no_grub_defaults_no_file(self):
        self.install()
        self.assertFalse(self.grub().exists())

    def test_symlinked_grub_defaults_are_left_alone(self):
        (self.root / 'etc/default/grub.mine').write_text(SHIPPED[-1].read_text())
        self.grub().symlink_to('grub.mine')
        self.install()
        self.assertTrue(self.grub().is_symlink())
        self.assertEqual((self.root / 'etc/default/grub.mine').read_text(), SHIPPED[-1].read_text())

    def test_plymouth_theme(self):
        for current, expected in (('spinner', 'abyss-logo'), ('abyss', 'abyss-logo'), ('', 'abyss-logo'),
                                  ('bgrt', 'bgrt'), ('abyss-logo', 'abyss-logo')):
            with self.subTest(current):
                self.theme.write_text(current + '\n')
                self.install()
                self.assertEqual(self.theme.read_text().strip(), expected)
        # the Abyss theme draws pixel for pixel (once)
        self.theme.write_text('spinner\n')
        self.install()
        self.install()
        self.assertEqual(self.plyconf.read_text(), '# stock\n[Daemon]\nTheme=abyss-logo\nDeviceScale=1\n')
        # what plymouth-set-default-theme (and so dracut's plymouth module,
        # which picks the theme for the initramfs) reads back from it
        self.assertEqual(plymouth_reads_theme(self.plyconf.read_text()), 'abyss-logo')

    def test_tty1_login_goes_once_with_lightdm(self):
        sv = self.root / 'etc/runit/runsvdir/default'
        for name in ('lightdm', 'agetty-tty1', 'agetty-tty2'):
            (sv / name).symlink_to(f'/etc/sv/{name}')
        self.assertIn('tty1 is left to the login screen', self.install())
        self.assertFalse(os.path.lexists(sv / 'agetty-tty1'))
        self.assertTrue((sv / 'agetty-tty2').is_symlink())
        # the user brings it back on purpose: later updates leave it
        (sv / 'agetty-tty1').symlink_to('/etc/sv/agetty-tty1')
        self.assertNotIn('tty1', self.install())
        self.assertTrue((sv / 'agetty-tty1').is_symlink())

    def test_tty1_login_stays_without_lightdm(self):
        sv = self.root / 'etc/runit/runsvdir/default'
        for name in ('agetty-tty1', 'agetty-tty2'):
            (sv / name).symlink_to(f'/etc/sv/{name}')
        self.install()
        self.assertTrue((sv / 'agetty-tty1').is_symlink())

    def test_grub_menu_and_initramfs_only_on_the_running_system(self):
        (self.root / 'boot/grub/grub.cfg').write_text('# menu\n')
        shutil.copy(SHIPPED[-1], self.grub())
        self.install()
        self.assertFalse(self.log.exists(), self.log.read_text() if self.log.exists() else '')
        self.assertEqual((self.root / 'boot/grub/grub.cfg').read_text(), '# menu\n')


@unittest.skipUnless((PKG / 'files/abyss-boot-splash').is_file(), 'abyss-boot package not found')
class SplashTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.grub = self.base / 'grub'
        self.grub.mkdir()
        self.sys = self.base / 'sys'
        (self.sys / 'class/drm').mkdir(parents=True)
        self.calls = self.base / 'calls'
        self.render = self.base / 'render'
        self.render.write_text(f'#!/bin/sh\necho "$2x$3 ${{4##*/}}" >> "{self.calls}"\necho png > "$1"\n')
        self.render.chmod(0o755)
        self.env = dict(os.environ, ABYSS_GRUB_DIR=str(self.grub), ABYSS_SYSFS=str(self.sys),
                        ABYSS_BOOT_SHARE=str(PKG / 'files/logo'), ABYSS_SPLASH_RENDER=str(self.render))

    def connector(self, name, status, *modes):
        d = self.sys / 'class/drm' / name
        d.mkdir()
        (d / 'status').write_text(status + '\n')
        (d / 'modes').write_text(''.join(m + '\n' for m in modes))

    def run_splash(self, *args):
        r = subprocess.run(['/bin/sh', str(PKG / 'files/abyss-boot-splash'), *args], env=self.env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout)
        return self.calls.read_text().splitlines() if self.calls.exists() else []

    def test_size_and_logo(self):
        self.connector('card0-HDMI-A-1', 'connected', '3840x2160', '1920x1080')
        self.connector('card0-eDP-1', 'connected', '2880x1800', '1920x1200')
        self.connector('card0-DP-1', 'disconnected')
        self.assertEqual(self.run_splash(), ['2880x1800 abyss-logo-256.png'])
        self.assertEqual((self.grub / 'abyss-splash.png').read_text(), 'png\n')
        self.assertEqual((self.grub / 'abyss-splash.png').stat().st_mode & 0o777, 0o644)
        # same screen, same logo: nothing to do; --force makes it again
        self.assertEqual(len(self.run_splash()), 1)
        self.assertEqual(len(self.run_splash('--force')), 2)

    def test_external_monitor_and_fallbacks(self):
        self.connector('card0-DP-1', 'disconnected')
        self.connector('card0-HDMI-A-1', 'connected', '1920x1080i', '1280x720')
        self.assertEqual(self.run_splash(), ['1920x1080 abyss-logo-128.png'])
        for size, logo in (('2560x1440', 192), ('3840x2160', 256), ('5120x2880', 384), ('1024x768', 128)):
            self.assertEqual(self.run_splash('--size', size)[-1], f'{size} abyss-logo-{logo}.png')

    def test_no_display_no_grub_dir(self):
        self.assertEqual(self.run_splash(), ['1920x1080 abyss-logo-128.png'])
        shutil.rmtree(self.grub)
        self.run_splash('--force')
        self.assertFalse(self.grub.exists())


@unittest.skipUnless((PKG / 'files/05_abyss_splash').is_file(), 'abyss-boot package not found')
class GrubSnippetTest(unittest.TestCase):
    def snippet(self, **env):
        e = {'PATH': '/usr/bin:/bin', 'GRUB_TIMEOUT_STYLE': 'hidden', 'ABYSS_BOOT_SPLASH': '/bin/true'}
        e.update(env)
        r = subprocess.run(['/bin/sh', str(PKG / 'files/05_abyss_splash')], env=e,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_hidden_menu_gets_the_splash(self):
        out = self.snippet()
        self.assertIn('background_image "${prefix}/abyss-splash.png"', out)
        self.assertIn('set color_normal=black/black', out)
        self.assertIn('sleep --interruptible "${timeout}"', out)
        self.assertNotRegex(out, r'(?m)\|\||^\s*if !')   # GRUB's script has no || / !
        checker = shutil.which('grub-script-check')
        if checker:
            with tempfile.NamedTemporaryFile('w', suffix='.cfg') as f:
                f.write('set timeout_style=hidden\nset timeout=1\n' + out)
                f.flush()
                subprocess.run([checker, f.name], check=True)

    def test_steps_aside(self):
        for env in ({'GRUB_TIMEOUT_STYLE': 'menu'}, {'GRUB_TIMEOUT_STYLE': 'countdown'},
                    {'GRUB_BACKGROUND': '/boot/mine.png'}, {'GRUB_THEME': '/boot/grub/themes/x/theme.txt'},
                    {'GRUB_TERMINAL_OUTPUT': 'console'}):
            with self.subTest(env):
                self.assertEqual(self.snippet(**env), '')


@unittest.skipUnless((PKG / 'template').is_file(), 'abyss-boot package not found')
class FilesTest(unittest.TestCase):
    def test_logo_pngs_exist_for_every_size_used(self):
        script = (PKG / 'files/plymouth/abyss-logo.script').read_text()
        splash = (PKG / 'files/abyss-boot-splash').read_text()
        template = (PKG / 'template').read_text()
        for s in (128, 192, 256, 384):
            self.assertTrue((PKG / f'files/logo/abyss-logo-{s}.png').is_file())
            self.assertIn(f'abyss-logo-{s}.png', script)
            self.assertIn(f'px={s}', splash)
        self.assertIn('for s in 128 192 256 384', template)
        for name in re.findall(r'Image\("([^"]+)"\)', script):
            if not name.startswith('abyss-logo-'):
                self.assertTrue((PKG / 'files/plymouth' / name).is_file(), name)
                self.assertIn(name.removesuffix('.png'), template)

    def test_plymouth_script_uses_only_known_math(self):
        script = (PKG / 'files/plymouth/abyss-logo.script').read_text()
        # plymouth's script language has Math.Int, no bare Int(), and no ++
        self.assertNotRegex(script, r'(?<![.\w])Int\(')
        self.assertNotIn('++', script)


if __name__ == '__main__':
    unittest.main()
