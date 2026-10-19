# Contributing to the Abyss Linux PMR

Templates use Void's `xbps-src` format. The [Void packaging manual](https://github.com/void-linux/void-packages/blob/master/Manual.md) is the reference for every variable used here.

## Bump to a new suckless release

1. In `srcpkgs/abyss-<tool>/template` set `version=` to the new release, `revision=1`, and update `checksum=` (`sha256sum` of the new tarball).
2. Delete `patches/01-upstream-git-*.patch` if the release already includes those commits. Otherwise regenerate it against the new tarball.
3. Rebase `patches/10-abyss.patch` onto the new source (see below) and fix any rejects.
4. Build both architectures (next section) and open a pull request.

## Change an Abyss patch or configuration

Bump `revision=` by one, then regenerate the patch from a working tree:

```sh
tar xf dwm-6.8.tar.gz && cd dwm-6.8
for p in ../srcpkgs/abyss-dwm/patches/*.patch; do patch -p1 < "$p"; done
git init -q && git add -A && git commit -qm base
# ... edit dwm.c / config.def.h ...
git diff > ../srcpkgs/abyss-dwm/patches/10-abyss.patch     # if editing on top of 01
```

Keep `config.def.h` as the single source of configuration. The Makefile copies it to `config.h`.

## Build locally

On a Void Linux machine or container (glibc):

```sh
git clone https://github.com/void-linux/void-packages && cd void-packages
cp -r ../AbyssLinuxPMR/srcpkgs/abyss-* srcpkgs/
./xbps-src binary-bootstrap
./xbps-src pkg abyss-dwm
./xbps-src -a aarch64 pkg abyss-dwm
sudo xbps-install --repository=hostdir/binpkgs abyss-dwm    # try it
```

Or run the CI script itself, as root in `ghcr.io/void-linux/void-glibc-full`:

```sh
useradd -G xbuilder -M builder && bash common/build.sh abyss-dwm
```

## Add a new package

* Name it `abyss-<name>` and add `conflicts="<name>>=0"` if Void ships the same program.
* Use `maintainer`, `license`, `homepage`, `distfiles` and `checksum` like the existing templates.
* Add a row to the package table in `README.md`.

## Signing and publishing

Only `main` is signed and published, by CI with the `XBPS_SIGNING_KEY` secret. Never commit a private key. Pull requests are built but never signed.
