#!/usr/bin/env python3
"""make-abyss-orbit.py - procedurally render the "Abyss Orbit" wallpaper.

Part of Abyss Linux (MIT licence). Everything in the picture is computed
here from a fixed random seed; no external image is read.

What it draws
    A camera floats just above a vast disc of orbiting light (an accretion
    disc around an unseen black hole, off to the right of frame). Every orbit
    is a long-exposure trail: a thin circular arc on that disc, projected
    through a pinhole camera, so trails sweep in from the bottom-left, rise
    toward the horizon and curl right around the dark centre. The far edge of
    the disc piles thousands of trails into a white-blue horizon band that
    narrows to one bright point. Above it: a fine starfield, faint swirling
    streaks around the void, and the void itself. Colours are steel blue,
    cyan, white and deep red/orange, with Abyss violet (#a855f7 / #7c3aed)
    mixed into some orbit bands. Each trail carries fine dotted grain.

    Light is accumulated in floating point (near trails become crisp ribbons
    of parallel sub-strands, far ones single anti-aliased strands), blurred
    and bloomed in the frequency domain, tone-mapped, then dithered before
    8-bit quantisation so the gradients do not band.

Composition
    Built for 21:9 (default 5120x2160, for 3440x1440 ultrawides). The subject
    (bright point, horizon, curl) sits inside the central ~60 % of the width,
    so `feh --bg-fill` centre-crops to 16:9 and 16:10 keep it.

Usage
    python3 make-abyss-orbit.py                       # 5120x2160 -> abyss-orbit.jpg
    python3 make-abyss-orbit.py -W 1600 -H 675 -o preview.jpg
    python3 make-abyss-orbit.py --seed 7 --quality 92

    -W/--width, -H/--height  output size in pixels (default 5120x2160). The
                             scene scales with the width; a different aspect
                             ratio just shows more or less sky/disc.
    -o/--output              output file (JPEG, progressive; default
                             abyss-orbit.jpg next to this script)
    --seed                   random seed (default 4815; same seed = same image)
    --quality                JPEG quality (default 90)

Requires Python 3 with numpy and Pillow. About 10 s and 3 GB of RAM at
5120x2160 (most of it the float accumulators and FFTs).
"""

import argparse
import math
import os
import sys
import time

import numpy as np
from PIL import Image

REF_W = 5120.0  # all pixel-sized constants are tuned for this width


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def hex_rgb(h):
    h = h.lstrip("#")
    srgb = np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])
    # to linear light
    return np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)


def smooth_noise_1d(rng, n_knots):
    """Return f(x), x in [0,1], a smooth random function in [0,1]."""
    knots = rng.random(n_knots + 3)

    def f(x):
        t = np.clip(x, 0.0, 1.0) * n_knots
        i = np.floor(t).astype(int)
        u = t - i
        u = u * u * (3 - 2 * u)
        return knots[i] * (1 - u) + knots[i + 1] * u
    return f


class FFTBlur:
    """Gaussian blurs of one image size via the frequency domain (zero padded)."""

    def __init__(self, h, w, pad):
        self.h, self.w, self.pad = h, w, pad
        self.ph, self.pw = h + 2 * pad, w + 2 * pad
        fy = np.fft.fftfreq(self.ph)[:, None]
        fx = np.fft.rfftfreq(self.pw)[None, :]
        self.f2 = (fx * fx + fy * fy).astype(np.float64)

    def kernel(self, sigma):
        return np.exp(-2.0 * math.pi ** 2 * sigma * sigma * self.f2)

    def fwd(self, img):
        p = np.zeros((self.ph, self.pw), np.float32)
        p[self.pad:self.pad + self.h, self.pad:self.pad + self.w] = img
        return np.fft.rfft2(p)

    def inv(self, spec):
        out = np.fft.irfft2(spec, s=(self.ph, self.pw))
        return out[self.pad:self.pad + self.h, self.pad:self.pad + self.w].astype(np.float32)


# --------------------------------------------------------------------------
# scene
# --------------------------------------------------------------------------

class Camera:
    def __init__(self, W, H, pos, yaw, pitch, roll, hfov_deg, cx, cy):
        self.W, self.H = W, H
        self.pos = np.array(pos, float)
        cy_, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        f = np.array([sy * cp, -sp, cy_ * cp])
        r = np.array([cy_, 0.0, -sy])
        u = np.cross(f, r)
        cr, sr = math.cos(roll), math.sin(roll)
        self.r = cr * r + sr * u
        self.u = -sr * r + cr * u
        self.f = f
        self.F = W / (2.0 * math.tan(math.radians(hfov_deg) / 2.0))
        self.cx, self.cy = cx * W, cy * H

    def project(self, x, y, z):
        dx, dy, dz = x - self.pos[0], y - self.pos[1], z - self.pos[2]
        xc = dx * self.r[0] + dy * self.r[1] + dz * self.r[2]
        yc = dx * self.u[0] + dy * self.u[1] + dz * self.u[2]
        zc = dx * self.f[0] + dy * self.f[1] + dz * self.f[2]
        zs = np.maximum(zc, 1e-6)
        return self.cx + self.F * xc / zs, self.cy - self.F * yc / zs, zc


def disc_height(r, p):
    """The disc is not flat: it sags toward the hole and falls away outside."""
    inner = -p["well"] / np.maximum(r, 1.0)
    outer = -p["curve"] * np.maximum(r - p["rc"], 0.0) ** 2
    return inner + outer


def render(W, H, seed):
    t0 = time.time()
    s = W / REF_W
    rng = np.random.default_rng(seed)

    P = dict(
        rc=40.0,            # camera distance from the hole
        h=6.5,              # camera height above the disc
        well=0.0,           # depth of the gravity well
        curve=0.0001,       # outer fall-off (curved horizon)
        r_min=4.0, r_max=260.0,
        n_trails=7000,
        shadow=math.radians(90.0),   # where trails vanish behind the hole
    )
    cam = Camera(W, H, pos=(0.0, P["h"] + disc_height(np.array(P["rc"]), P), -P["rc"]),
                 yaw=math.radians(-20.0), pitch=math.radians(3.5),
                 roll=math.radians(-9.0), hfov_deg=100.0, cx=0.5, cy=0.42)

    npix = W * H
    light = np.zeros((3, npix), np.float32)     # linear light, before blur / bloom

    # ---- palette (linear light) -------------------------------------------
    pal = {
        "steel": hex_rgb("#4f7fc4"),
        "deep":  hex_rgb("#2b4c9a"),
        "cyan":  hex_rgb("#58c8f0"),
        "white": hex_rgb("#e8f2ff"),
        "red":   hex_rgb("#e0281a"),
        "ember": hex_rgb("#ff6a2a"),
        "violet": hex_rgb("#a855f7"),
        "indigo": hex_rgb("#7c3aed"),
    }
    names = list(pal)
    probs = np.array([0.24, 0.12, 0.08, 0.10, 0.20, 0.08, 0.09, 0.09])
    cdf = np.cumsum(probs) / probs.sum()

    band_sel = smooth_noise_1d(rng, 90)    # which colour family a radius band has
    band_lum = smooth_noise_1d(rng, 140)   # brightness bands
    band_lum2 = smooth_noise_1d(rng, 23)

    def shadow_at(x):
        return P["shadow"] + 0.55 * (1.0 - x) ** 1.4

    # orbit radii: dense everywhere, extra dense toward the outer rim
    u = rng.random(P["n_trails"])
    radii = P["r_min"] + (P["r_max"] - P["r_min"]) * (u ** 0.75)
    radii.sort()

    margin = 8 * s
    step = 0.42                      # px between samples along a trail
    width_world = 0.045            # physical trail width (sets near thickness)
    wscale = s                        # keeps the look resolution independent

    chunk_idx, chunk_w, chunk_col = [], [], []
    pending = 0

    def flush():
        nonlocal chunk_idx, chunk_w, chunk_col, pending
        if not chunk_idx:
            return
        idx = np.concatenate(chunk_idx)
        w = np.concatenate(chunk_w)
        col = np.concatenate(chunk_col)
        for c in range(3):
            light[c] += np.bincount(idx, weights=w * col[:, c], minlength=npix).astype(np.float32)
        chunk_idx, chunk_w, chunk_col = [], [], []
        pending = 0

    for r in radii:
        x = (r - P["r_min"]) / (P["r_max"] - P["r_min"])
        # colour family from the radius band (+ a little per-trail randomness)
        sel = band_sel(x) * 0.8 + rng.random() * 0.2
        name = names[int(np.searchsorted(cdf, sel))]
        # the outer disc (the horizon band) runs cooler: blue and white
        if name in ("red", "ember") and rng.random() < np.clip((x - 0.55) / 0.35, 0, 0.85):
            name = "white" if rng.random() < 0.3 else "steel"
        col = pal[name] * (0.85 + 0.3 * rng.random(3))
        if rng.random() < 0.06:
            col = pal["white"]
        lum = (0.10 + 3.4 * band_lum(x) ** 4.0) * (0.4 + 1.0 * band_lum2(x)) * rng.lognormal(0, 0.5)
        lum *= 0.35 + 0.65 * min(1.0, (1.0 - x) / 0.04)        # soft outer rim
        lum *= 1.0 - 0.35 * np.clip((x - 0.7) / 0.3, 0, 1)      # keep the band from clipping

        # long-exposure arc: start angle + span
        span = rng.uniform(1.2, 2.0) * math.pi
        a0 = rng.uniform(0, 2 * math.pi)
        n0 = 1200
        phi = a0 + np.linspace(0, span, n0)
        y = disc_height(np.array(r), P)
        X, Z = r * np.cos(phi), r * np.sin(phi)
        sx, sy, zc = cam.project(X, np.full_like(X, y), Z)
        ok = zc > 0.08
        ins = ok & (sx > -margin) & (sx < W + margin) & (sy > -margin) & (sy < H + margin)
        seg_ok = (ok[:-1] & ok[1:]) & (ins[:-1] | ins[1:])
        if not seg_ok.any():
            continue
        seglen = np.hypot(np.diff(sx), np.diff(sy))
        seglen = np.where(seg_ok, seglen, 0.0)
        cnt = np.minimum(np.ceil(seglen / step), 4000).astype(int)
        tot = int(cnt.sum())
        if tot == 0:
            continue
        seg = np.repeat(np.arange(n0 - 1), cnt)
        first = np.repeat(np.cumsum(cnt) - cnt, cnt)
        frac = (np.arange(tot) - first + rng.random(tot)) / np.repeat(cnt, cnt)
        dphi = span / (n0 - 1)
        ph = phi[seg] + frac * dphi
        fx, fy, fz = cam.project(r * np.cos(ph), np.full(tot, y), r * np.sin(ph))
        spacing = (seglen / np.maximum(cnt, 1))[seg]

        # fade in/out at the arc ends, distance falloff
        tpos = (ph - a0) / span
        ends = np.clip(np.minimum(tpos, 1 - tpos) / 0.08, 0, 1)
        # the hole's shadow: trails brighten toward the far side, then vanish
        # (inner orbits vanish earlier, so the ends taper into one point)
        sh = shadow_at(x)
        a = np.angle(np.exp(1j * (ph - sh)))                   # 0 where it vanishes
        sm = np.clip(a / 0.30, 0, 1)
        ends = ends * np.where(a >= 0, sm * sm * (3 - 2 * sm) * (1.0 + 0.9 * np.exp(-a / 0.45)),
                               np.clip((-a - 1.9) / 0.9, 0, 1))
        dist = 1.0 / (1.0 + fz / 140.0) ** 0.6 * (1.0 + 0.6 * np.exp(-fz / 12.0))
        base = lum * ends * dist * spacing * wscale * 0.14
        thick = np.minimum(cam.F * width_world / np.maximum(fz, 1e-3), 30.0 * s)
        # unit normal of the trail on screen (for ribbons of real width)
        gx, gy = np.gradient(fx), np.gradient(fy)
        gn = np.maximum(np.hypot(gx, gy), 1e-9)
        nx, ny = -gy / gn, gx / gn
        m = ((fx > -thick) & (fx < W + thick) & (fy > -thick) & (fy < H + thick) & (base > 0))
        if not m.any():
            continue
        base, thick, fx, fy, nx, ny, spacing = (v[m] for v in (base, thick, fx, fy, nx, ny, spacing))
        # near trails become crisp ribbons: several parallel sub-strands
        nof = np.where(thick > 1.6, np.minimum(np.ceil(thick / 0.7), 44), 1).astype(int)
        n = int(nof.sum())
        rp = np.repeat(np.arange(len(nof)), nof)
        j = np.arange(n) - np.repeat(np.cumsum(nof) - nof, nof)
        uo = (j + rng.random(n)) / nof[rp] - 0.5
        off = uo * thick[rp]
        px = fx[rp] + nx[rp] * off
        py = fy[rp] + ny[rp] * off
        prof = np.where(nof[rp] > 1, (0.55 + 0.9 * (1 - (2 * uo) ** 2)) / 1.15, 1.0)
        gain = np.where(thick > 1, thick, 1.0) ** 0.9
        # fine dotted grain: faint texture plus sparse bright sparks
        grain = 0.6 + 0.4 * rng.random(n) ** 3
        dots = rng.random(n) < spacing[rp] / (7.0 * s) / np.sqrt(nof[rp])
        grain = grain + dots * rng.uniform(2.0, 8.0, n)
        w = (base * gain)[rp] / nof[rp] * prof * grain

        ix = np.floor(px).astype(int)
        iy = np.floor(py).astype(int)
        m = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
        if not m.any():
            continue
        chunk_idx.append((iy[m] * W + ix[m]).astype(np.int64))
        chunk_w.append(w[m])
        chunk_col.append(np.broadcast_to(col, (int(m.sum()), 3)))
        pending += int(m.sum())
        if pending > 6_000_000:
            flush()
    flush()
    t_trails = time.time() - t0

    sharp = light.reshape(3, H, W)

    # ---- horizon: the projected far rim of the disc --------------------------
    R = P["r_max"]
    rim_phi = np.linspace(-math.pi, math.pi, 20000)
    rx, ry, rz = cam.project(R * np.cos(rim_phi), np.full(rim_phi.shape, disc_height(np.array(R), P)),
                             R * np.sin(rim_phi))
    vis = (rz > 0) & (rx > -0.5 * W) & (rx < 1.5 * W)
    o = np.argsort(rx[vis])
    cols = np.arange(W)
    hy = np.interp(cols, rx[vis][o], ry[vis][o])          # horizon height per column
    # bright point = the highest place where a trail vanishes into the shadow
    rs = np.linspace(P["r_min"], P["r_max"], 2000)
    sa = shadow_at((rs - P["r_min"]) / (P["r_max"] - P["r_min"]))
    tx, ty, _ = cam.project(rs * np.cos(sa), disc_height(rs, P), rs * np.sin(sa))
    k = int(np.argmin(ty))
    tipx, tipy = float(tx[k]), float(ty[k])
    # the void sits up and to the right of the bright point
    vx, vy = tipx + 0.07 * W, tipy - 0.06 * H

    # ---- stars ---------------------------------------------------------------
    n_stars = int(46000 * (W * H) / (REF_W * 2160))
    sxs = rng.random(n_stars) * W
    sys_ = rng.random(n_stars) * H
    mag = rng.pareto(2.0, n_stars) + 1.0
    six = np.clip(sxs.astype(int), 0, W - 1)
    siy = np.clip(sys_.astype(int), 0, H - 1)
    above = np.clip((hy[six] - sys_) / (0.02 * H), 0, 1)
    high = np.clip(1.25 - sys_ / H * 1.4, 0.25, 1.0)
    vd = np.hypot(sxs - vx, (sys_ - vy) * 1.4) / W
    void_k = 0.1 + 0.9 * np.clip((vd - 0.03) / 0.14, 0.0, 1.0) ** 1.5
    keep = rng.random(n_stars) < (0.08 + 0.92 * above) * high * void_k
    sxs, sys_, mag, six, siy = sxs[keep], sys_[keep], mag[keep], six[keep], siy[keep]
    tint = rng.random(len(sxs))[:, None]
    scol = np.where(tint < 0.55, hex_rgb("#cfe0ff"),
                    np.where(tint < 0.8, hex_rgb("#ffffff"),
                             np.where(tint < 0.92, hex_rgb("#b48cff"), hex_rgb("#ffcfb0"))))
    sw = np.minimum(mag, 25.0) * 0.08
    for c in range(3):
        np.add.at(sharp[c], (siy, six), (sw * scol[:, c]).astype(np.float32))
    big = mag > 3.0                                        # brighter stars get a body
    for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        bx = np.clip(six[big] + ddx, 0, W - 1)
        by = np.clip(siy[big] + ddy, 0, H - 1)
        for c in range(3):
            np.add.at(sharp[c], (by, bx), (0.3 * sw[big] * scol[big, c]).astype(np.float32))

    # ---- faint dotted streaks swirling around the void -------------------------
    rot = math.radians(-8.0)
    for _ in range(1000):
        rho = W * (0.03 + 0.30 * rng.random() ** 1.4)
        asp = 0.62 + 0.1 * rng.random()
        a0 = rng.uniform(0, 2 * math.pi)
        span = rng.uniform(0.08, 0.45)
        n = max(int(rho * span / (0.45 * s)), 8)
        th = a0 + np.linspace(0, span, n)
        ex, ey = rho * np.cos(th), rho * asp * np.sin(th)
        px = vx + ex * math.cos(rot) - ey * math.sin(rot)
        py = vy + ex * math.sin(rot) + ey * math.cos(rot)
        m = (px >= 0) & (px < W) & (py >= 0) & (py < H)
        if m.sum() < 2:
            continue
        ix, iy = px[m].astype(int), py[m].astype(int)
        sk = np.clip((hy[ix] - py[m]) / (0.03 * H), 0, 1)
        tt = np.linspace(0, 1, n)[m]
        env = np.sin(np.pi * tt) ** 2
        g = (0.25 + (rng.random(len(ix)) < 0.08) * 3.0) * env * sk * 0.07 * s
        g *= math.exp(-rho / (0.18 * W))
        c0 = pal["steel"] if rng.random() < 0.6 else (pal["violet"] if rng.random() < 0.6 else pal["red"])
        for c in range(3):
            np.add.at(sharp[c], (iy, ix), (g * c0[c]).astype(np.float32))

    # ---- horizon halo + bright point (analytic light) ------------------------
    yy = np.arange(H)[:, None].astype(np.float32)
    dy = yy - hy[None, :]
    along = np.clip((tipx - cols) / max(tipx, 1.0), 0.0, 1.0)[None, :]   # 0 at tip, 1 at left
    before = np.clip((tipx - cols) / (0.01 * W), 0, 1)[None, :]
    thick_up = (5 + 90 * along) * s
    thick_dn = (8 + 35 * along) * s
    prof = np.where(dy < 0, np.exp(-(dy / thick_up) ** 2), np.exp(-(dy / thick_dn) ** 2))
    band = (prof * (0.25 + 0.75 * (1 - along) ** 1.5) * before).astype(np.float32)
    band_col = hex_rgb("#6f9eff") * 0.85 + hex_rgb("#ffffff") * 0.15
    del dy, prof

    YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
    ddx, ddy = (XX - tipx) / W, (YY - tipy) / W
    del XX, YY
    rr2 = ddx * ddx + ddy * ddy
    point = (np.exp(-rr2 / (0.0012 ** 2)) * 6.0 + np.exp(-rr2 / (0.005 ** 2)) * 0.8
             + np.exp(-rr2 / (0.02 ** 2)) * 0.03)
    # thin anamorphic streak, longer and redder toward the void side
    streak = np.exp(-(ddy / 0.0006) ** 2) * np.exp(-np.abs(ddx) / np.where(ddx > 0, 0.012, 0.006)) * 1.6
    del ddx, ddy, rr2

    # ---- combine with blur / bloom ---------------------------------------------
    pad = int(200 * s) + 8
    fb = FFTBlur(H, W, pad)
    k_sharp = fb.kernel(max(0.6 * s, 0.5))
    bloom = 1.0 + 0.20 * fb.kernel(8 * s) + 0.10 * fb.kernel(32 * s) + 0.06 * fb.kernel(110 * s)
    img = np.zeros((3, H, W), np.float32)
    for c in range(3):
        img[c] = fb.inv(fb.fwd(sharp[c]) * k_sharp * bloom)
    del sharp, light

    warm = hex_rgb("#ff5530")
    for c in range(3):
        img[c] += band * band_col[c] * 0.42 + point * hex_rgb("#e4eeff")[c] \
            + streak * warm[c]
    del band, point, streak

    # subtle deep-space tint so the black is not dead
    ys = np.linspace(0, 1, H)[:, None]
    img[0] += 0.0012 * (1 - ys)
    img[1] += 0.0010 * (1 - ys)
    img[2] += 0.0030 * (1 - ys)

    # ---- tone map ------------------------------------------------------------
    exposure = 1.7
    lum = 0.2126 * img[0] + 0.7152 * img[1] + 0.0722 * img[2]
    out = 1.0 - np.exp(-img * exposure)
    lmap = 1.0 - np.exp(-lum * exposure)
    white = np.clip((lum * exposure - 1.2) / 3.0, 0, 1)[None] ** 1.2     # hot cores go white
    out = out * (1 - white) + lmap[None] * white
    del img, lum, lmap, white
    out = np.clip(out, 0, 1)
    srgb = np.where(out <= 0.0031308, out * 12.92, 1.055 * np.power(out, 1 / 2.4) - 0.055)
    # triangular dither (1 LSB) against banding
    dith = (rng.random(srgb.shape, dtype=np.float32) - rng.random(srgb.shape, dtype=np.float32))
    q = np.clip(srgb * 255.0 + dith + 0.5, 0, 255).astype(np.uint8)
    rgb = np.ascontiguousarray(np.transpose(q, (1, 2, 0)))
    return rgb, t_trails, (tipx / W, tipy / H)


def main():
    ap = argparse.ArgumentParser(description="Render the Abyss Orbit wallpaper.")
    ap.add_argument("-W", "--width", type=int, default=5120)
    ap.add_argument("-H", "--height", type=int, default=2160)
    ap.add_argument("-o", "--output",
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "abyss-orbit.jpg"))
    ap.add_argument("--seed", type=int, default=4815)
    ap.add_argument("--quality", type=int, default=90)
    a = ap.parse_args()
    t0 = time.time()
    rgb, t_tr, tip = render(a.width, a.height, a.seed)
    Image.fromarray(rgb, "RGB").save(a.output, "JPEG", quality=a.quality, progressive=True,
                                     optimize=True, subsampling=0)
    print(f"{a.output}: {a.width}x{a.height}, trails {t_tr:.1f}s, total {time.time() - t0:.1f}s, "
          f"horizon point at {tip[0]:.2f},{tip[1]:.2f}", file=sys.stderr)


if __name__ == "__main__":
    main()
