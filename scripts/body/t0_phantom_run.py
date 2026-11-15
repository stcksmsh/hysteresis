"""WO42 T0 driver for PhantomDance and Motorica. Rules: docs/T0_PHANTOM_RULES.md (T0 as FineDance, docs/T0_RULES.md). Data and everything derived stay outside git;
Motorica never leaves this laptop. SOURCE is `phantom` or `motorica`.

    t0_phantom_run.py SOURCE catalogue   body env: units -> OUT/catalogue.json, OUT/lanes_list.json
    t0_phantom_run.py SOURCE lanes       brain env, 2 threads: lanes per song (resumable) into OUT/lanes
    t0_phantom_run.py SOURCE split       body env: groups + split (own seed) -> OUT/split.json
    t0_phantom_run.py SOURCE seq [--limit N]   body env: per sequence and copy one npz in OUT/seq/ (resumable), 2 processes
"""
import hashlib
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t0_lib as T  # noqa: E402

FD_OUT = Path("/secondary/hyst-data/body/t0")
SRC = {
    "phantom": dict(root=Path("/secondary/hyst-data/phantomdance/raw/PhantomDanceDatav1.1"), out=Path("/secondary/hyst-data/body/t0_phantom"), seed=42001, prefix="ph"),
    "motorica": dict(root=Path("/secondary/hyst-data/motorica/raw/motion/motorica_dance_dataset"), out=Path("/secondary/hyst-data/body/t0_motorica"), seed=42002, prefix="mo"),
}
EXCL = ("blue-lagoon", "schizoid-man", "epitaph", "breathe", "one-of-these-days", "instant-crush", "five-years", "presence")
EXCL_WAV = [Path("/secondary/hyst-data/body/motornet_toy/work3/wav"), Path("/secondary/hyst-data/body/k5/danced")]
FAMILY = {"kthjazz": "jazz", "kthstreet": "street", "kthmisc": "misc"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def strip(s):
    return "".join(c for c in str(s).lower() if c.isalnum())


def load(source, c):
    import t0_phantom as P
    return P.phantom_rot(c["motion"]) if source == "phantom" else P.motorica_rot(c["motion"])


class sf:                                                                       # body env has no soundfile: duration through ffprobe
    @staticmethod
    def info(p):
        import subprocess
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True).stdout)
        return type("I", (), {"duration": d})


def cmd_catalogue(source):
    s = SRC[source]
    s["out"].mkdir(parents=True, exist_ok=True)
    cat = []
    if source == "phantom":
        for i in range(260):
            n = load(source, dict(motion=str(s["root"] / "motion" / f"{i:03d}.json")))[2]
            w = s["root"] / "music" / f"{i:03d}.wav"
            cat.append(dict(key=f"ph_{i:03d}", dataset="phantomdance", seq=f"{i:03d}", name=f"ph{i:03d}", genre="unlabelled", style1="", t30=int(n), hours=n / 30 / 3600, hash=sha(w),
                            motion=str(s["root"] / "motion" / f"{i:03d}.json"), wav=str(w), audio_s=float(sf.info(w).duration)))
    else:
        stems = sorted(p.stem for p in (s["root"] / "bvh").glob("*.bvh") if (s["root"] / "wav" / f"{p.stem}.wav").exists())
        for k in stems:
            with open(s["root"] / "bvh" / f"{k}.bvh") as f:
                for ln in f:
                    if ln.startswith("Frames"):
                        n120 = int(ln.split()[1])
                        break
            n = (n120 + 3) // 4
            w = s["root"] / "wav" / f"{k}.wav"
            fam, code = k.split("_")[0], k.split("_")[1]
            cat.append(dict(key=f"mo_{k}", dataset="motorica", seq=k, name=k, genre=FAMILY.get(fam, fam), style1=code, t30=n, hours=n / 30 / 3600, hash=sha(w),
                            motion=str(s["root"] / "bvh" / f"{k}.bvh"), wav=str(w), audio_s=float(sf.info(w).duration)))
    (s["out"] / "catalogue.json").write_text(json.dumps(cat, indent=1))
    (s["out"] / "lanes_list.json").write_text(json.dumps([dict(key=c["key"], wav=c["wav"]) for c in cat]))
    print("catalogue", source, len(cat), "hours", round(sum(c["hours"] for c in cat), 3))


def cmd_lanes(source):
    import torch
    torch.set_num_threads(2)
    import t0_lanes as L
    s = SRC[source]
    for it in json.loads((s["out"] / "lanes_list.json").read_text()):
        if (s["out"] / "lanes" / f"{it['key']}.npz").exists():
            continue
        t = time.time()
        L.song(it["key"], it["wav"], s["out"] / "lanes", s["out"] / "tmp")
        print("lanes", it["key"], round(time.time() - t, 1), "s", flush=True)


def cmd_split(source):
    s = SRC[source]
    cat = json.loads((s["out"] / "catalogue.json").read_text())
    ex_hash = {sha(p): p.name for d in EXCL_WAV if d.exists() for p in d.glob("*.wav")}
    ex_names = {strip(n) for n in EXCL}
    fd = json.loads((FD_OUT / "catalogue_fd.json").read_text())
    fd_names = {strip(c["name"]) for c in fd if strip(c["name"])}
    hits = [c["key"] for c in cat if strip(c["name"]) in ex_names or c["hash"] in ex_hash or any(e in strip(c["name"]) for e in ex_names)]
    in_fd = [c["key"] for c in cat if source == "motorica" and any(len(n) >= 6 and n in strip(c["name"]) for n in fd_names)]
    keep = [c for c in cat if c["key"] not in hits]
    groups = T.make_groups([dict(key=c["key"], name=c["name"], hash=c["hash"]) for c in keep])
    sp = T.split_groups(groups, seed=s["seed"])
    rows = [dict(group=g[0], members=g, split=sp[g[0]]) for g in groups]
    (s["out"] / "split.json").write_text(json.dumps(dict(seed=s["seed"], shares=T.SHARES, excluded_by_check_or_danced_match=hits, also_in_finedance_by_name=in_fd, n_groups=len(groups), groups=rows), indent=1))
    n = {k: sum(1 for r in rows if r["split"] == k) for k in ("train", "validation", "test")}
    print("groups", len(groups), n, "excluded", hits, "in finedance by name", in_fd)


def one(args):
    source, c, gate = args
    import t0_chain as C
    s = SRC[source]
    sp = {k: (r["group"], r["split"]) for r in json.loads((s["out"] / "split.json").read_text())["groups"] for k in r["members"]}
    nm = json.loads((FD_OUT / "token_norm.json").read_text())
    rot, trans, n = load(source, c)
    assert n == c["t30"], (n, c["t30"])
    mrot, _ = T.mirror(rot, trans)
    (s["out"] / "seq").mkdir(exist_ok=True)
    z = np.load(s["out"] / "lanes" / f"{c['key']}.npz")
    ntok = min(T.n_tokens(n), int(z["n_frames"]) // 50)
    raw, mask = T.pool_tokens(z["ear"], z["h_abs"], z["s10"][:, :4], z["arousal_b7"], z["ee"], z["y"], ntok)
    tok = T.standardise_tokens(raw, nm)
    out = []
    for copy in C.COPIES:
        p = s["out"] / "seq" / f"{c['key']}__{copy}.npz"
        if p.exists():
            continue
        t0 = time.time()
        r = C.process(mrot if copy.endswith("m") else rot, trans, copy, gate=gate)
        np.savez_compressed(str(p) + ".tmp.npz", tokens=tok, tokens_raw=raw, token_cols=np.array(T.TOKEN_COLS), token_lookahead_s=np.array(T.TOKEN_LOOKAHEAD_S, np.float32), token_mask=mask,
                            weight=1.0, fps=30.0, split=sp[c["key"]][1], group=sp[c["key"]][0], source=source, style=c["genre"], win_start_tok=np.arange(r["n_win"]) * T.WIN_TOK, **r)
        Path(str(p) + ".tmp.npz").replace(p)
        out.append((copy, time.time() - t0, r["n_win"], int(r["win_pass"].sum())))
    return c["key"], out


def cmd_seq(source, argv):
    s = SRC[source]
    sp = {k for r in json.loads((s["out"] / "split.json").read_text())["groups"] for k in r["members"]}
    cat = [c for c in json.loads((s["out"] / "catalogue.json").read_text()) if c["key"] in sp]
    lim = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    t0 = time.time()
    with mp.get_context("spawn").Pool(2) as pool:
        for key, out in pool.imap_unordered(one, [(source, c, True) for c in cat[:lim]]):
            print(key, [(a, round(b, 1), c_, d) for a, b, c_, d in out], f"elapsed {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    {"catalogue": lambda: cmd_catalogue(a[0]), "lanes": lambda: cmd_lanes(a[0]), "split": lambda: cmd_split(a[0]), "seq": lambda: cmd_seq(a[0], a[2:])}[a[1]]()
