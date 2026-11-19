"""WO54 A1 stage 12 direct: the lamp disc's pixel centroid per rendered frame against the FK lamp point of the csv rows. Body env (FK from m3f_report).

Delay tau minimising the residual of an affine fit  pixel(t) ~ A lamp(t - tau)  over tau in [-300, 300] ms (2 ms grid, parabola on top); positive tau = the picture is later than the csv.
Offset sign as everywhere: positive = movement later."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = Path("/secondary/hyst-data/body/syncaudit/a")


def disc_mask(im):
    r, g, b = (im[..., i].astype(int) for i in range(3))
    return (r > 200) & (g > 170) & (g < 215) & (b > 100) & (b < 150)


def best_tau(xy, lamp, hz_lamp=50.0, fps=30.0, span=0.3, step=0.002):
    good = ~np.isnan(xy[:, 0])
    tf = np.arange(len(xy)) / fps
    taus = np.arange(-span, span + 1e-9, step)
    tl = np.arange(len(lamp)) / hz_lamp
    cost = []
    for tau in taus:
        tt = tf - tau
        m = good & (tt >= 0) & (tt <= tl[-1])
        if m.sum() < 60:
            cost.append(np.inf); continue
        L = np.stack([np.interp(tt[m], tl, lamp[:, c]) for c in range(3)] + [np.ones(m.sum())], 1)
        res = 0.0
        for c in range(2):
            co, *_ = np.linalg.lstsq(L, xy[m, c], rcond=None)
            res += float(((L @ co - xy[m, c]) ** 2).mean())
        cost.append(res)
    cost = np.array(cost)
    k = int(np.argmin(cost))
    tau = taus[k]
    if 0 < k < len(taus) - 1 and np.isfinite(cost[k - 1:k + 2]).all():
        a, b, c = cost[k - 1], cost[k], cost[k + 1]
        d = a - 2 * b + c
        tau += (0.5 * (a - c) / d if d else 0.0) * step
    return float(tau), float(np.sqrt(cost[k] / 2)), float(np.sqrt(cost[int(np.argmin(np.abs(taus)))] / 2))


def main():
    import m3f_report as R
    key = json.loads((OUT / "material_key.json").read_text())["items"]
    out = {}
    for pid, it in key.items():
        vp = OUT / f"render_root/clips/{pid}_{it['version']}.mp4"
        rows = np.array([[float(x) for x in l.split(",")[1:]] for l in (OUT / f"render_root/work/{pid}_{it['version']}.csv").read_text().splitlines() if l and l[0].isdigit()])
        lamp = np.asarray(R.fk_points(rows)[:, 5], float)
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(vp), "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        fr = np.frombuffer(raw, np.uint8).reshape(-1, 720, 1280, 3)
        xy = np.full((len(fr), 2), np.nan)
        for k, im in enumerate(fr):
            m = disc_mask(im)
            if m.sum() > 150:
                ys, xs = np.nonzero(m)
                xy[k] = (xs.mean(), ys.mean())
        tau, rms, rms0 = best_tau(xy, lamp)
        out[pid] = dict(frames_with_lamp=int((~np.isnan(xy[:, 0])).sum()), tau_ms=1000 * tau, rms_px_at_best=rms, rms_px_at_zero=rms0, lamp_pixel_range_px=[float(np.nanmax(xy[:, c]) - np.nanmin(xy[:, c])) for c in range(2)])
        print(pid, out[pid], flush=True)
    (OUT / "lamppix.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
