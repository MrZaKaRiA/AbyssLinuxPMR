# Abyss Linux PMR — Package Manager Repository

The **Abyss Linux PMR** is a signed [XBPS](https://github.com/void-linux/xbps) repository that ships the Abyss builds of the [suckless](https://suckless.org) tools for **x86_64** and **aarch64**. It sits next to the official Void Linux repositories. When suckless releases a new dwm or st, or Abyss improves a patch, every Abyss system picks it up with a normal `xbps-install -Su`. You don't have to reinstall from a new ISO.

```
https://mrzakaria.github.io/AbyssLinuxPMR/current
```

| Package | Upstream | Abyss build | What it is |
|---|---|---|---|
| `abyss-dwm` | dwm 6.8 + git `bca7cf2` | `6.8_3` | Dynamic tiling window manager, the Abyss desktop |
| `abyss-st` | st 0.9.3 + git `fdaadd5` | `0.9.3_1` | Simple terminal |
| `abyss-dmenu` | dmenu 5.4 + git `8627d0c` | `5.4_1` | Keyboard-driven menu and launcher |
| `abyss-slock` | slock 1.7 + git `65cb721` | `1.7_1` | Screen locker |
| `abyss-tabbed` | tabbed 0.9 + git `e65146d` | `0.9_1` | Tabs for XEmbed applications |
| `abyss-wmname` | wmname 0.1 + git `1114a83` | `0.1_1` | Sets the WM name (`LG3D`) so Java GUIs render under dwm |
| `abyss-theme` | Abyss | `1.0_1` (noarch) | Dark GTK 3 theme "Abyss" + "Abyss" icons (Papirus-Dark, violet folders) for Thunar and other GTK apps |

Each suckless package conflicts with Void's stock package of the same tool (`dwm`, `st`, …), so only one build is installed at a time. `abyss-dwm` depends on `abyss-theme`, so the desktop look arrives with the window manager.

---

## Using it

### On Abyss Linux

Nothing to do. Abyss Linux 27.0 and later ships with:

* `/etc/xbps.d/20-abyss-pmr.conf`, which adds the repository,
* `/var/db/xbps/keys/c6:f0:d1:05:cb:f1:89:83:58:c2:e2:e4:4c:c9:09:9a.plist`, which holds the signing key.

Update the whole system, Abyss packages included:

```sh
sudo xbps-install -Su
```

### On any other Void Linux system (glibc, x86_64 or aarch64)

```sh
# 1. trust the Abyss signing key
sudo curl -fLo /var/db/xbps/keys/c6:f0:d1:05:cb:f1:89:83:58:c2:e2:e4:4c:c9:09:9a.plist \
  https://mrzakaria.github.io/AbyssLinuxPMR/keys/c6:f0:d1:05:cb:f1:89:83:58:c2:e2:e4:4c:c9:09:9a.plist

# 2. add the repository
echo 'repository=https://mrzakaria.github.io/AbyssLinuxPMR/current' | sudo tee /etc/xbps.d/20-abyss-pmr.conf

# 3. install (replaces Void's dwm/st/dmenu if you had them)
sudo xbps-install -S abyss-dwm abyss-st abyss-dmenu abyss-slock abyss-tabbed abyss-wmname
```

If you skip step 1, xbps shows the key fingerprint on the first sync and asks whether to import it. It must be:

```
c6:f0:d1:05:cb:f1:89:83:58:c2:e2:e4:4c:c9:09:9a   (RSA 4096, "Abyss Linux")
```

The same public key is in [`keys/abyss-pmr.pub.pem`](keys/abyss-pmr.pub.pem). You can check it yourself:
`ssh-keygen -l -E md5 -f <(ssh-keygen -i -m PKCS8 -f keys/abyss-pmr.pub.pem)`.

---

## How it works

```
srcpkgs/abyss-*/template          xbps-src recipe (Void's own format)
srcpkgs/abyss-*/patches/01-*.patch upstream suckless git fixes since the release tarball
srcpkgs/abyss-*/patches/10-*.patch the Abyss changes (patches + config.def.h)
common/build.sh                    clones void-packages, builds x86_64 natively, aarch64 cross
common/sign.sh                     xbps-rindex: index + sign repodata and every package
.github/workflows/build.yml        CI: build -> sign -> publish to GitHub Pages
keys/                              public signing key (plist for xbps, PEM for humans)
etc/xbps.d/20-abyss-pmr.conf       client configuration
site/                              landing page
```

1. Every package starts from the **official release tarball** on `dl.suckless.org`, pinned by its sha256 `checksum`.
2. `xbps-src` applies `patches/*.patch` in order. `01-upstream-git-<rev>.patch` brings the tree up to the suckless git revision Abyss tracks. `10-abyss.patch` adds the Abyss patches and configuration.
3. GitHub Actions builds in the official `ghcr.io/void-linux/void-glibc-full` container, the same way Void's own CI does (`uchroot` masterdir, `binary-bootstrap`).
4. The repository data and every `.xbps` are signed with the Abyss RSA key. The private key lives only in the `XBPS_SIGNING_KEY` Actions secret.
5. The signed repository is published to GitHub Pages at `/current`.

Everything is reproducible from this repository plus the public tarballs, so anyone can verify that a package matches its recipe.

### What the Abyss patches do

**abyss-dwm** (`10-abyss.patch`)

| Patch | Effect |
|---|---|
| [systray](https://dwm.suckless.org/patches/systray/) | System tray in the bar (opt-in tray icons such as nm-applet) |
| [status2d](https://dwm.suckless.org/patches/status2d/) | Colours in the status text (`^c#rrggbb^`, `^b#rrggbb^`, `^d^`) |
| [vanitygaps](https://dwm.suckless.org/patches/vanitygaps/) | Inner/outer gaps; `Super+Alt+0` toggle, `Super+Alt+=/-` resize |
| [scratchpad](https://dwm.suckless.org/patches/scratchpad/) | Drop-down terminal on `` Super+` `` |
| [attachaside](https://dwm.suckless.org/patches/attachaside/) | New windows go to the stack, the master stays put |
| [autostart](https://dwm.suckless.org/patches/autostart/) | Runs `~/.dwm/autostart.sh` at start |
| [movestack](https://dwm.suckless.org/patches/movestack/) | Move the window itself down/up the stack: `Super+Shift+j/k` or `Super+Shift+↓/↑` |
| [shiftview](https://dwm.suckless.org/patches/shiftview/) + shifttag | Previous/next desktop `Super+←/→`; carry the window there `Super+Shift+←/→` |
| Abyss config | Purple theme `#a855f7`, JetBrainsMono Nerd Font, `Super` as mod key, a status-bar click runs `abyss-control-center` (the Menu button), `Super+Esc` menu, `Super+F1` cheatsheet |

**abyss-st**: [clipboard](https://st.suckless.org/patches/clipboard/) (a selection is also copied to CLIPBOARD), the Abyss 16-colour palette, and the font set in points (`size=11`) so it follows `Xft.dpi` on HiDPI screens.

**abyss-dmenu**: [center](https://tools.suckless.org/dmenu/patches/center/) (`-c`), [border](https://tools.suckless.org/dmenu/patches/border/) (`-bw`), [line-height](https://tools.suckless.org/dmenu/patches/line-height/) (`-h`), [password](https://tools.suckless.org/dmenu/patches/password/) (`-P`), case-insensitive matching by default, Abyss colours and font.

**abyss-theme**: `/usr/share/themes/Abyss` (GTK's Adwaita dark with the Abyss palette), `/usr/share/icons/Abyss` (inherits Papirus-Dark; 600 folder links point at Papirus' violet set, generated in `files/violet-folders.list`), and system-wide `/etc/xdg/gtk-3.0/settings.ini`. A user's own `~/.config/gtk-3.0/settings.ini` still wins.

**abyss-slock**, **abyss-tabbed**: configuration only (privilege-drop group, colours, font). **abyss-wmname**: unmodified upstream git.

---

## Contributing

New suckless release, better patch, new package: see [CONTRIBUTING.md](CONTRIBUTING.md). In short:

```sh
git clone https://github.com/void-linux/void-packages && cd void-packages
cp -r ../AbyssLinuxPMR/srcpkgs/abyss-* srcpkgs/
./xbps-src binary-bootstrap
./xbps-src pkg abyss-dwm                 # native
./xbps-src -a aarch64 pkg abyss-dwm      # cross
```

Open a pull request. CI builds both architectures for every PR. Merged changes are signed and published automatically.

## License

Templates, scripts and Abyss patches: MIT ([LICENSE](LICENSE)). The suckless programs keep their own MIT/X licenses, installed with each package in `/usr/share/licenses/`.

Part of [**Abyss Linux**](https://github.com/MrZaKaRiA/AbyssLinux).
