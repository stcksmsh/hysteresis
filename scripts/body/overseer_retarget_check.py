"""Overseer's own recompute for the retarget look test (BRAIN_SPEC 7.52): speed/acceleration at 1.25, clearance on v2p, end stops,
shoulder accel from the realised CSV, pick spread, pair order, clip durations and audio offset vs the FineDance music window.
Usage: python overseer_retarget_check.py BUILDER_SCRIPTS_DIR [RETARGET_LOOK_DIR]  (builder dir = an archive of the commit under test)."""
import json, subprocess, sys
import numpy as np

sys.path.insert(0, sys.argv[1])
import dialstudy as D
import make_arm_v2p as P

R = sys.argv[2] if len(sys.argv) > 2 else "/secondary/hyst-data/body/retarget_look"
MUS = "/secondary/hyst-data/datasets/finedance/data/finedance/music_wav/"
TOL = 1.25
man = json.load(open(R + "/manifest.json"))
num = json.load(open(R + "/numbers.json"))


def rows(f):
    return np.array([l.split(",") for l in open(f) if l[0].isdigit() or l[0] == "-"], float)


def pcm(args):
    return np.frombuffer(subprocess.run(["ffmpeg", "-v", "error"] + args + ["-ac", "1", "-ar", "8000", "-f", "f32le", "-"],
                                        capture_output=True).stdout, np.float32)


bad = 0
singles = [m for m in man if m["kind"] == "single"]
for m in singles:
    d = rows(R + "/work/" + m["csv"])
    q = d[:, 1:6]
    v = np.abs(np.diff(q, axis=0)).max(0) * 50 / D.LIM_V
    a = np.abs(q[2:] - 2 * q[1:-1] + q[:-2]) * 2500 / D.LIM_A
    am = a.max(0)
    marg = float(P.margins(q).min())
    lo, hi = D.LO + D.CLIP_MARGIN, D.HI - D.CLIP_MARGIN
    near = int(((q <= D.LO + 1.0) | (q >= D.HI - 1.0)).any(1).sum())
    g = num[m["id"]]["gates"]
    ok = v.max() <= TOL and am.max() <= TOL and marg >= 0
    bad += not ok
    sh = num[m["id"]].get("shoulder") or {}
    print(f"{m['id']:10s} {m['genre']:12s} seq {m['source_seq']} n {len(q)} t {d[-1,0]-d[0,0]:.2f}s | v/lim {v.max():.3f} (num {g['speed_ratio']:.3f}) "
          f"a/lim {am.max():.3f} (num {g['accel_ratio']:.3f}) | margin {marg:+.3f} (num {g['floor_m']:+.3f}) | within 1 deg of stop {near} "
          f"| sh real p50/p95/max {np.percentile(a[:,1],50):.2f}/{np.percentile(a[:,1],95):.2f}/{am[1]:.2f}"
          + (f" (num max {sh['realised_accel_x_limit']['max']:.2f}; cmd p50/p95/max {sh['commanded_accel_x_limit']['p50']:.2f}/"
             f"{sh['commanded_accel_x_limit']['p95']:.2f}/{sh['commanded_accel_x_limit']['max']:.2f}; lim share {sh['limiter_share']:.2f}; "
             f"rms {sh['rms_command_minus_limiter_deg']:.2f} deg)" if sh else " (no shoulder numbers)")
          + ("" if ok else "  <-- FAIL"))

picks = {m["clip"]: (m["genre"], m["source_seq"]) for m in singles if m["variant"] in ("V1", "V2")}
seqs = [s for _, s in picks.values()]
gen = [g for g, _ in picks.values()]
print("clips", len(picks), "distinct seqs", len(set(seqs)), "max per genre", max(gen.count(x) for x in set(gen)), sorted(set(gen)))
pairs = [m for m in man if m["kind"] == "pair"]
print("pairs", len(pairs), "V1 first in", sum(m["variants"][0] == "V1" for m in pairs), [m["id"] + ":" + m["variants"][0] for m in pairs])
print("recompute fails at 1.25:", bad)

for m in singles:
    f = R + "/clips/" + m["file"]
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height,duration", "-of", "csv=p=0", f],
                         capture_output=True, text=True).stdout.split()
    a = pcm(["-i", f])
    b = pcm(["-ss", str(max(m["window_start_s"] - 1, 0)), "-t", "23", "-i", MUS + m["source_seq"] + ".wav"])
    x = np.correlate(b, a[8000:8000 * 11], "valid")
    lag = np.argmax(x) / 8000 - min(m["window_start_s"], 1) - 1
    print(m["id"], dur, "audio s", round(len(a) / 8000, 2), "offset vs window start s", round(lag, 3))
