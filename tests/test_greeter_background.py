"""abyss-display-setup: the login screen shows the desktop wallpaper of the
user it offers first (like macOS), never a file that user could not open.

Runs the real script as root (LightDM runs it as root) against throwaway
users with 0700 homes:
  * no choice -> the Abyss wallpaper (link, no copy); "none" -> black;
    an image in ~/.local/share/backgrounds -> a byte-identical copy the
    lightdm group can read;
  * /etc/shadow, a link to it, a text file, a FIFO, a picture over 64 MiB
    -> the Abyss wallpaper, quickly, nothing copied;
  * the greeter's last user wins; unknown -> the first user;
  * going back to the default removes the copy.
Needs root, setpriv and useradd (CI container); skipped otherwise.
File from srcpkgs/abyss-desktop (or ABYSS_DISPLAY_SETUP).
"""
import grp
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SETUP = Path(os.environ.get('ABYSS_DISPLAY_SETUP') or ROOT / 'srcpkgs/abyss-desktop/files/bin/abyss-display-setup')
JPEG = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00' + b'\x00' * 64
PNG_SIG = b'\x89PNG\r\n\x1a\n'
USERS = ('abyssgbt1', 'abyssgbt2')


@unittest.skipUnless(SETUP.is_file() and os.geteuid() == 0 and shutil.which('setpriv') and shutil.which('useradd'),
                     'needs root, setpriv and useradd')
class GreeterBackgroundTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.tmp.name)
        cls.base.chmod(0o755)
        for u in USERS:
            subprocess.run(['userdel', '-r', u], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['useradd', '-m', '-d', str(cls.base / u), '-s', '/bin/sh', u], check=True)
            (cls.base / u).chmod(0o700)

    @classmethod
    def tearDownClass(cls):
        for u in USERS:
            subprocess.run(['userdel', '-r', u], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.tmp.cleanup()

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(dir=self.base))
        self.addCleanup(shutil.rmtree, self.work)
        self.greeter = self.work / 'greeter'
        self.state = self.work / 'state'
        self.backgrounds = self.work / 'backgrounds'
        self.backgrounds.mkdir()
        (self.backgrounds / 'abyss-wallpaper.jpg').write_bytes(JPEG)
        self.passwd = self.work / 'passwd'
        self.passwd.write_text(''.join(
            ':'.join(map(str, (p.pw_name, 'x', p.pw_uid, p.pw_gid, '', p.pw_dir, p.pw_shell))) + '\n'
            for p in map(pwd.getpwnam, USERS)))
        for u in USERS:
            self.choose(u, None)

    def home(self, user):
        return Path(pwd.getpwnam(user).pw_dir)

    def as_user(self, user, *cmd):
        p = pwd.getpwnam(user)
        subprocess.run(['setpriv', f'--reuid={p.pw_uid}', f'--regid={p.pw_gid}', '--init-groups', '--', *cmd], check=True)

    def choose(self, user, choice):
        conf = self.home(user) / '.config/abyss/wallpaper'
        if choice is None:
            if conf.exists():
                conf.unlink()
            return
        self.as_user(user, 'mkdir', '-p', str(conf.parent))
        self.as_user(user, 'sh', '-c', 'printf "%s\\n" "$1" > "$2"', 'sh', choice, str(conf))

    def run_setup(self, last_user=None):
        if last_user:
            self.state.write_text(f'[greeter]\nlast-user={last_user}\nlast-session=abyss\n')
        env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'ABYSS_GREETER_DIR': str(self.greeter),
               'ABYSS_GREETER_STATE': str(self.state), 'ABYSS_PASSWD': str(self.passwd),
               'ABYSS_BACKGROUNDS_DIR': str(self.backgrounds), 'ABYSS_BOOT_SPLASH': '/nonexistent'}
        t0 = time.time()
        r = subprocess.run(['/bin/sh', str(SETUP)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout)
        return time.time() - t0

    def target(self):
        return os.readlink(self.greeter / 'background')

    def picture(self, user, name, data=JPEG, mode=0o600):
        d = self.home(user) / '.local/share/backgrounds'
        self.as_user(user, 'mkdir', '-p', str(d))
        f = d / name
        f.write_bytes(data)
        p = pwd.getpwnam(user)
        os.chown(f, p.pw_uid, p.pw_gid)
        f.chmod(mode)
        return f

    def test_default_black_and_own_picture(self):
        self.run_setup('abyssgbt1')
        self.assertEqual(self.target(), str(self.backgrounds / 'abyss-wallpaper.jpg'))
        self.assertFalse((self.greeter / 'user-background').exists())
        self.assertEqual(self.greeter.stat().st_mode & 0o777, 0o750 if self.has_lightdm() else 0o755)

        self.choose('abyssgbt1', 'none')
        self.run_setup()
        self.assertEqual(self.target(), str(self.greeter / 'black.png'))
        self.assertTrue((self.greeter / 'black.png').read_bytes().startswith(PNG_SIG))

        pic = self.picture('abyssgbt1', 'mine.jpg', JPEG + b'own')
        self.choose('abyssgbt1', '~/.local/share/backgrounds/mine.jpg')
        self.run_setup()
        copy = self.greeter / 'user-background'
        self.assertEqual(self.target(), str(copy))
        self.assertEqual(copy.read_bytes(), pic.read_bytes())
        self.assertEqual(copy.stat().st_mode & 0o777, 0o644)
        self.assertEqual(copy.stat().st_uid, 0)

        # back to the default: no copy of the picture stays behind
        self.choose('abyssgbt1', None)
        self.run_setup()
        self.assertEqual(self.target(), str(self.backgrounds / 'abyss-wallpaper.jpg'))
        self.assertFalse(copy.exists())

    def has_lightdm(self):
        try:
            grp.getgrnam('lightdm')
            return True
        except KeyError:
            return False

    def test_files_the_user_cannot_or_should_not_show(self):
        home = self.home('abyssgbt1')
        text = self.picture('abyssgbt1', 'notes.jpg', b'secret notes, not a picture\n')
        big = self.picture('abyssgbt1', 'big.jpg', b'')
        with open(big, 'r+b') as f:
            f.write(JPEG)
            f.truncate(64 * 1024 * 1024 + 1)
        other = self.picture('abyssgbt2', 'theirs.jpg', JPEG + b'other user')
        link = home / '.local/share/backgrounds/shadow.jpg'
        link.symlink_to('/etc/shadow')
        fifo = home / '.local/share/backgrounds/fifo.jpg'
        os.mkfifo(fifo)
        os.chown(fifo, pwd.getpwnam('abyssgbt1').pw_uid, -1)
        for choice in ('/etc/shadow', str(link), str(text), str(big), str(other), str(fifo), 'missing.jpg'):
            with self.subTest(choice):
                self.choose('abyssgbt1', choice)
                took = self.run_setup('abyssgbt1')
                self.assertEqual(self.target(), str(self.backgrounds / 'abyss-wallpaper.jpg'))
                self.assertEqual(sorted(p.name for p in self.greeter.iterdir() if p.name != 'black.png'), ['background'])
                self.assertLess(took, 15)

    def test_which_user(self):
        self.picture('abyssgbt2', 'two.jpg', JPEG + b'two')
        self.choose('abyssgbt2', str(self.home('abyssgbt2') / '.local/share/backgrounds/two.jpg'))
        self.choose('abyssgbt1', 'none')
        self.run_setup('abyssgbt2')
        self.assertEqual((self.greeter / 'user-background').read_bytes(), JPEG + b'two')
        # an unknown or system last user: the first (lowest uid) user
        for last in ('nosuchuser', 'root'):
            self.run_setup(last)
            self.assertEqual(self.target(), str(self.greeter / 'black.png'))


if __name__ == '__main__':
    unittest.main()
