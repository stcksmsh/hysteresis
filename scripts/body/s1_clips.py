"""WO40 S1 rebuild-check clips (BRAIN_SPEC 7.62.5). Brain env. Out /secondary/hyst-data/body/s1/.
    s1_clips.py gate [PROCS]   Run B rebuild of every test window through the gate chain -> s1/gates_runB.npz (pass, q50)
    s1_clips.py pick           seeded pick (35001), original + rebuild sims, csv/m4a -> s1/work/, s1/picks.json
    s1_clips.py manifest       after the render: s1/clips/manifest.json (pair order by default_rng(35011))
"""
import json
import multiprocessing as mp
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import t1a_data as DD  # noqa: E402
import t1a_eval as E  # noqa: E402
import t1a2_realised as R  # noqa: E402

OUT = Path("/secondary/hyst-data/body/s1")
W = OUT / "work"
FDM = Path("/secondary/hyst-data/datasets/finedance/data/finedance/music_wav")
AIM = Path("/secondary/hyst-data/datasets/aioz/data/musics")
RUNB = DD.OUT.parent / "t1a2" / "runB"
SHOW_S = 20.0


def rows_b():
    post, tgt = E.test_rows()
    rec = np.load(RUNB / "recon_test.npy")
    r = post.copy()
    r[:, :2000] += rec
    r[:, 2000] += rec[:, -1]
    return r, tgt


def job(i, rows, z, cache):
    key = (int(z["dancer"][i]), int(z["copy"][i]))
    if key not in cache:
        cache[key] = np.load(next((DD.T0 / "seq").glob(f"*/{z['dancers'][key[0]]}__{E.COPIES[key[1]]}.npz")))
    a = int(z["win"][i]) * DD.WIN_ROWS
    t = cache[key]["targets"]
    return (rows[i].astype(float), t[a - E.PRE:a].astype(float) if a >= E.PRE else None, E.COPIES[key[1]][:2])


def cmd_gate(procs=8):
    OUT.mkdir(parents=True, exist_ok=True)
    z = np.load(DD.OUT / "windows_test.npz")
    rb, _ = rows_b()
    cache = {}
    jobs = [job(i, rb, z, cache) for i in range(len(rb))]
    with mp.get_context("spawn").Pool(procs) as pool:
        res = pool.map(R.sim_one, jobs, chunksize=8)
    np.savez(OUT / "gates_runB.npz", ok=np.array([r[0] for r in res]), q50=np.stack([r[1] for r in res]))
    print("pass share", np.mean([r[0] for r in res]), flush=True)


def cmd_pick():
    import arm_sim
    import dialstudy as D
    z = np.load(DD.OUT / "windows_test.npz")
    names, src = z["dancers"], DD.load("test")["src"]
    g = np.load(OUT / "gates_runB.npz")
    ok, q_b = g["ok"], g["q50"]
    cache = {}

    def seqf(i):
        k = (int(z["dancer"][i]), int(z["copy"][i]))
        if k not in cache:
            cache[k] = np.load(next((DD.T0 / "seq").glob(f"*/{names[k[0]]}__{E.COPIES[k[1]]}.npz")))
        return cache[k]
    idx = [i for i in range(len(ok)) if ok[i]]
    idx.sort(key=lambda i: (int(src[i]), str(names[z["dancer"][i]]), E.COPIES[z["copy"][i]], int(z["win"][i])))
    pool = {n: sum(1 for i in idx if src[i] == s) for s, n in ((0, "finedance"), (1, "aioz"))}
    perm = np.random.default_rng(35001).permutation(len(idx))
    take, groups = {0: [], 1: []}, set()
    for p in perm:
        i = idx[p]
        s = int(src[i])
        gk = (s, str(seqf(i)["group"]))
        if len(take[s]) < (4 if s == 0 else 2) and gk not in groups:
            take[s].append(i)
            groups.add(gk)
    sel = take[0] + take[1]
    _, tgt = rows_b()
    c2 = {}
    with mp.get_context("spawn").Pool(6) as pl:
        orig = pl.map(R.sim_one, [job(i, tgt, z, c2) for i in sel])
    W.mkdir(parents=True, exist_ok=True)
    picks = []
    for n, (i, (okq, q_o)) in enumerate(zip(sel, orig), 1):
        nm = str(names[z["dancer"][i]])
        win = int(z["win"][i])
        ds = "finedance" if src[i] == 0 else "aioz"
        stem = nm[3:] if ds == "finedance" else nm[len("aioz_"):].rsplit("_p", 1)[0]
        wav = (FDM / f"{stem}.wav") if ds == "finedance" else (AIM / f"{stem}.wav")
        cid = f"S{n:02d}"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{win * SHOW_S:.3f}", "-t", f"{SHOW_S}", "-i", str(wav), "-ac", "2", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(W / f"{cid}.m4a")], check=True)
        for tag, q in (("orig", q_o), ("rebuild", q_b[i])):
            (W / f"{cid}_{tag}.csv").write_text(arm_sim.csv_text(q, D.HZ, name=f"{cid}_{tag}"))
        picks.append(dict(id=cid, dataset=ds, dancer=nm, copy=E.COPIES[z["copy"][i]], window=win, group=str(seqf(i)["group"]), audio=str(wav), start_s=win * SHOW_S,
                          genre=ds, orig_gate_passed=bool(okq)))
    (OUT / "picks.json").write_text(json.dumps(dict(seed=35001, pool_size=pool, pool_total=len(idx), picks=picks), indent=1))
    print(json.dumps(dict(pool=pool, picks=[(p["id"], p["dancer"], p["copy"], p["window"], p["orig_gate_passed"]) for p in picks])), flush=True)


def cmd_manifest():
    C = OUT / "clips"
    picks = json.loads((OUT / "picks.json").read_text())["picks"]
    first = {int(x) for x in np.random.default_rng(35011).choice(len(picks), 3, replace=False)}
    man = []
    for k, p in enumerate(picks):
        v = ["rebuild", "orig"] if k in first else ["orig", "rebuild"]
        assert all((C / f"{p['id']}_{x}.mp4").exists() for x in v)
        man.append(dict(id=f"PAIR_{p['id']}", kind="pair", files=[f"{p['id']}_{x}.mp4" for x in v], variants=v, clip=p["id"], genre=p["genre"]))
    (C / "manifest.json").write_text(json.dumps(man, indent=1))
    print(json.dumps([(m["id"], m["variants"]) for m in man]))


if __name__ == "__main__":
    a = sys.argv[1:]
    {"gate": lambda: cmd_gate(int(a[1]) if len(a) > 1 else 8), "pick": cmd_pick, "manifest": cmd_manifest}[a[0]]()
