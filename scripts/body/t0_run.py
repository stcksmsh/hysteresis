"""WO37 T0 driver. Rules: docs/T0_RULES.md. Output /secondary/hyst-data/body/t0/. Data and audio stay outside git.

    t0_run.py catalogue            body env: FineDance units (key, name, wav hash, frames) -> t0/catalogue_fd.json, t0/lanes_list_fd.json
    t0_run.py split                body env: groups + split -> t0/split.json (FineDance + t0/aioz_keep.json if present); check-song / danced-song match report
    t0_run.py norm                 body env: train-split token constants -> t0/token_norm.json (needs lanes of the train songs)
    t0_run.py seq [--limit N] [--only KEY ...] [--nogate]   body env: per dancer and copy one npz in t0/seq/ (resumable), 8 processes
    t0_run.py report               body env: docs/T0_REPORT.md + t0/numbers.json
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

FD = Path("/secondary/hyst-data/datasets/finedance/data/finedance")
OUT = Path("/secondary/hyst-data/body/t0")
EXCL = ("blue-lagoon", "schizoid-man", "epitaph", "breathe", "one-of-these-days", "instant-crush", "five-years", "presence")
EXCL_WAV = [Path("/secondary/hyst-data/body/motornet_toy/work3/wav"), Path("/secondary/hyst-data/body/k5/danced")]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def cmd_catalogue():
    OUT.mkdir(exist_ok=True)
    cat = []
    for p in sorted((FD / "motion").glob("*.npy")):
        lab = json.loads((FD / "label_json" / f"{p.stem}.json").read_text())
        n = int(np.load(p, mmap_mode="r").shape[0])
        cat.append(dict(key=f"fd_{p.stem}", dataset="finedance", seq=p.stem, name=lab["name"], genre=lab["style2"].lower(), style1=lab["style1"], t30=n, hours=n / 30 / 3600,
                        hash=sha(FD / "music_wav" / f"{p.stem}.wav")))
    (OUT / "catalogue_fd.json").write_text(json.dumps(cat, indent=1))
    (OUT / "lanes_list_fd.json").write_text(json.dumps([dict(key=c["key"], wav=str(FD / "music_wav" / f"{c['seq']}.wav")) for c in cat]))
    print("catalogue", len(cat), "hours", round(sum(c["hours"] for c in cat), 3))


def load_catalogue():
    cat = json.loads((OUT / "catalogue_fd.json").read_text())
    if (OUT / "catalogue_aioz.json").exists():                                  # written by cmd_split from aioz_keep.json (Builder B's output)
        cat += json.loads((OUT / "catalogue_aioz.json").read_text())
    return cat


def cmd_split():
    cat = load_catalogue()
    ex_hash = {sha(p): p.name for d in EXCL_WAV for p in d.glob("*.wav")} if any(d.exists() for d in EXCL_WAV) else {}
    strip = lambda s: "".join(c for c in s.lower() if c.isalnum())
    ex_names = {strip(n) for n in EXCL}
    hits = [c["key"] for c in cat if strip(c["name"]) in ex_names or c["hash"] in ex_hash]
    cat = [c for c in cat if c["key"] not in hits]
    units = [dict(key=c["key"], name=c["name"], hash=c["hash"]) for c in cat]
    groups = T.make_groups(units)
    sp = T.split_groups(groups)
    by = {c["key"]: c for c in cat}
    rows = [dict(group=g[0], members=g, dataset=sorted({by[k]["dataset"] for k in g}), split=sp[g[0]]) for g in groups]
    (OUT / "split.json").write_text(json.dumps(dict(seed=T.SEED, shares=T.SHARES, excluded_by_check_or_danced_match=hits, n_groups=len(groups), groups=rows), indent=1))
    n = {s: sum(1 for r in rows if r["split"] == s) for s in ("train", "validation", "test")}
    print("groups", len(groups), n, "excluded", hits)


def split_of():
    d = json.loads((OUT / "split.json").read_text())
    return {k: (r["group"], r["split"]) for r in d["groups"] for k in r["members"]}


def song_tokens(key, n_tok, nm=None):
    z = np.load(OUT / "lanes" / f"{key}.npz")
    tok, mask = T.pool_tokens(z["ear"], z["h_abs"], z["s10"][:, :4], z["arousal_b7"], z["ee"], z["y"], n_tok)
    return tok, mask


def cmd_norm():
    sp = split_of()
    cat = [c for c in load_catalogue() if c["key"] in sp and sp[c["key"]][1] == "train"]
    tm = []
    for c in cat:
        n = min(T.n_tokens(c["t30"]), int(np.load(OUT / "lanes" / f"{c['key']}.npz")["n_frames"]) // 50)
        tm.append(song_tokens(c["key"], n))
    nm = T.fit_token_norm(tm)
    (OUT / "token_norm.json").write_text(json.dumps(nm))
    print("token norm from", len(cat), "train sequences,", nm["n_tokens"], "tokens,", nm["n_masked"], "masked")


def one(args):
    """one dancer, all four copies: -> list of (copy, seconds, n_win, n_pass)"""
    c, gate = args
    import t0_chain as C
    seq = Path(c["motion"])
    sp = split_of()
    nm = json.loads((OUT / "token_norm.json").read_text())
    rot, trans = T.load_rot(seq) if c["dataset"] == "finedance" else __import__("t0_aioz").load_rot(c)
    mrot, _ = T.mirror(rot, trans)
    (OUT / "seq" / c["dataset"]).mkdir(parents=True, exist_ok=True)
    n = min(T.n_tokens(c["t30"]), int(np.load(OUT / "lanes" / f"{c['song_lane']}.npz")["n_frames"]) // 50)
    tok, mask = song_tokens(c["song_lane"], n)
    tok = T.standardise_tokens(tok, nm)
    out = []
    for copy in C.COPIES:
        p = OUT / "seq" / c["dataset"] / f"{c['key']}__{copy}.npz"
        if p.exists():
            continue
        t0 = time.time()
        r = C.process(mrot if copy.endswith("m") else rot, trans, copy, gate=gate)
        np.savez_compressed(str(p) + ".tmp.npz", tokens=tok, token_cols=np.array(T.TOKEN_COLS), token_mask=mask, weight=c["weight"], fps=30.0, split=sp[c["key"]][1], group=sp[c["key"]][0],
                            win_start_tok=np.arange(r["n_win"]) * T.WIN_TOK, **r)
        Path(str(p) + ".tmp.npz").replace(p)
        out.append((copy, time.time() - t0, r["n_win"], int(r["win_pass"].sum())))
    return c["key"], out


def dancers():
    cat = [c for c in load_catalogue() if c["key"] in split_of()]
    byg = {}
    for c in cat:
        byg.setdefault(split_of()[c["key"]][0], []).append(c)
    for g in byg.values():
        w = T.hours_of_dancers([(c["key"], c["hours"]) for c in g])
        for c in g:
            c["weight"] = w[c["key"]]
            c["motion"] = str(FD / "motion" / f"{c['seq']}.npy") if c["dataset"] == "finedance" else c.get("motion")
            c["song_lane"] = c["key"] if c["dataset"] == "finedance" else c["lane_key"]
    return cat


def cmd_seq(argv):
    gate = "--nogate" not in argv
    only = [argv[i + 1] for i, a in enumerate(argv) if a == "--only"]
    lim = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    ds = [c for c in dancers() if not only or c["key"] in only][:lim]
    t0 = time.time()
    with mp.get_context("spawn").Pool(8) as pool:
        for key, out in pool.imap_unordered(one, [(c, gate) for c in ds]):
            print(key, [(a, round(b, 1), c_, d) for a, b, c_, d in out], f"elapsed {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    {"catalogue": cmd_catalogue, "split": cmd_split, "norm": cmd_norm, "seq": lambda: cmd_seq(a[1:])}[a[0]]()
