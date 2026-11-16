"""WO46 part 1 run (docs/DIAG_RULES.md). Brain env.   T1B_POST=2 python -u diag_run.py [PROCS]
Resumable per song -> /secondary/hyst-data/body/diag/{rows,q50}/<song>.npz, measures.json."""
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import diag_lib as D  # noqa: E402
import join_lib as J  # noqa: E402
import join_run as JR  # noqa: E402
import t1b_t2 as T2  # noqa: E402
import t1b_t2b as B  # noqa: E402

OUT = Path("/secondary/hyst-data/body/diag")


def build_song(key, split, ctx):
    vq, sd, voc, norm, db, _ = ctx
    h = T2.human_window(key)
    hv = h["V1"]
    post0 = hv["post0"]
    out = {}
    for c in JR.COPIES:
        out[f"H|{c}"] = (h[c]["rows"], c[:2])
        out[f"HJ|{c}"] = (J.build_rows(h[c]["tok"], h[c]["post0"], voc, vq, sd, "blocks"), c[:2])
    ctl = np.load(JR.OUT / "controls" / f"{key}.npz")                                  # WO44's stored controls (same picks)
    cache = {}
    toks = {}
    for name, short in (("retrieval", "RT"), ("random", "RN")):
        toks[short] = JR.chunk_tokens(db, db["keys"], ctl[f"{name}_pick"], cache)
    gf = T2.OUT / "e1" / "seed41101" / "t2" / "gen" / f"{key}.npz"
    if split == "test" and gf.exists():
        g = np.load(gf)
        toks["M"] = {k: g[f"{k}_0"] for k in ("c1", "c2", "v", "p")}
    for short, tok in toks.items():
        out[f"{short}|A1"] = (J.build_rows(tok, post0, voc, vq, sd, "blocks"), "V1")
        out[f"{short}|hp"] = (J.build_rows(D.swap(hv["tok"], tok), post0, voc, vq, sd, "blocks"), "V1")      # human posture, control gesture
        out[f"{short}|hg"] = (J.build_rows(D.swap(tok, hv["tok"]), post0, voc, vq, sd, "blocks"), "V1")      # control posture, human gesture
    return out


def main(procs):
    import torch
    import t1a2_train as TR2
    torch.set_num_threads(1)
    vq = TR2.make("B")
    vq.load_state_dict(torch.load("/secondary/hyst-data/body/t1a2/runB/best.pt"))
    vq.eval()
    sd = B.sd_scale()
    voc, norm = T2.vocab(), T2.TR.load_norm()
    db = B.train_db(norm)
    ctx = (vq, sd, voc, norm, db, None)
    for d in ("rows", "q50"):
        (OUT / d).mkdir(parents=True, exist_ok=True)
    mf = OUT / "measures.json"
    res = json.loads(mf.read_text()) if mf.exists() else {}
    with mp.get_context("spawn").Pool(procs) as pool:
        for key, split in JR.songs():
            if key in res:
                continue
            t = time.time()
            built = build_song(key, split, ctx)
            names = list(built)
            qs = pool.map(JR.sim, [(built[n][0].astype(float), None, built[n][1]) for n in names])
            np.savez_compressed(OUT / "rows" / f"{key}.npz", **{n: built[n][0] for n in names})
            np.savez_compressed(OUT / "q50" / f"{key}.npz", **dict(zip(names, qs)))
            res[key] = dict(split=split, cond={n: JR.measure(q, built[n][0]) for n, q in zip(names, qs)})
            mf.write_text(json.dumps(res))
            print(key, split, len(names), "conditions", round(time.time() - t), "s", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
