"""Work order 5: sampled re-evaluation of the saved M3-family policies (BRAIN_SPEC 7.16 point 1). No retraining, nothing tuned.

    python -u reeval.py OUTDIR [policy-name ...]

Each policy is evaluated twice with the original evaluation seed (999) and size (8 episodes x 90 s):
  argmax  : program = argmax of the logits, modulation = mean (the original evaluation);
  sampled : program sampled from the softmax (as in training), modulation = mean (same for every family); torch seed 2026.
Both also report mutual information between the chosen program and the brain state (tm3.program_state_mi: arousal in pooled quartiles x L3 phase in 4 sectors).
Caveat: T-M3's saved .pt has no cerebellum weights, so T-M3 uses the calibration cerebellum for both modes (the originals used the online-trained one).
Resumable: an existing OUTDIR/<policy>.<mode>.json is skipped.
"""
import json
import sys
from pathlib import Path

import numpy as np
import torch

import m3_cortex as M
import run_tm3
import run_tm3b
import run_tm3c
import tm3
import tm3_world as W
import tm3b
import tm3c

D = Path("/secondary/hyst-data/body")
POLICIES = {                                                  # name: (family, directory, file stem)
    "tm3_try1": ("tm3", D / "tm3", "try1"), "tm3_try2": ("tm3", D / "tm3", "try2"),
    "m3b_g_b0_l0.01_c0.1_e0.01": ("m3b", D / "m3b", "g_b0_l0.01_c0.1_e0.01"), "m3b_g_b0_l0.01_c0_e0.01": ("m3b", D / "m3b", "g_b0_l0.01_c0_e0.01"),
    "m3b_g_b0_l0.01_c0_e0.05": ("m3b", D / "m3b", "g_b0_l0.01_c0_e0.05"), "m3b_g_b0_l0.1_c0_e0.01": ("m3b", D / "m3b", "g_b0_l0.1_c0_e0.01"),
    "m3c_try1": ("m3c", D / "m3c", "try1"), "m3c_try2": ("m3c", D / "m3c" / "t2", "try2"),
}


def build(family, d, stem):
    st = json.loads((d / f"{stem}.settings.json").read_text())
    cfg = tm3.Config(**st["config"])
    cal = json.loads((d / "calib.json").read_text())
    ck = torch.load(d / f"{stem}.pt")
    cc = torch.load(d / "calib.pt")
    bundle = st["bundle"]
    if family == "tm3":
        cx = run_tm3.load_cortex(d)
        cx.prop.load_state_dict(ck["relay"])
        run = tm3.Run(cfg, cx, bundle, cal)
        run.cb.net.load_state_dict(cc["cb"])
        run.pol.load_state_dict(ck["policy"])
        return run, tm3.evaluate
    if family == "m3b":
        cx = run_tm3b.load_cortex(d)
        cx.prop.load_state_dict(ck["relay"])
        run = tm3b.RunB(cfg, cx, bundle, cal)
        run.cb.net.load_state_dict(ck["cb"])
        run.pol.load_state_dict(ck["policy"])
        return run, tm3b.evaluate
    tm3c.OBS_HIDDEN = 16 if stem == "try2" else 64
    cx = run_tm3c.load_cortex(d)
    run = tm3c.RunC(cfg, cx, bundle, cal)
    run.cb.net.load_state_dict(ck["cb"])
    run.obs.load_state_dict(ck["observer"])
    run.pol.load_state_dict(ck["policy"])
    run.stats = {k: np.array(v) for k, v in cal["stats"].items()}
    return run, tm3c.evaluate


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    names = sys.argv[2:] or list(POLICIES)
    torch.set_num_threads(2)
    for name in names:
        fam, d, stem = POLICIES[name]
        run, ev = build(fam, d, stem)
        for mode in ("argmax", "sampled"):
            f = out / f"{name}.{mode}.json"
            if f.exists():
                continue
            torch.manual_seed(2026)
            res = ev(run, n_ep=8, secs=90.0, sample_prog=(mode == "sampled"))
            res = {k: v for k, v in res.items() if k not in ("a_per_episode", "partner", "control_shiftB_per_episode")}
            f.write_text(json.dumps(res, indent=1))
            print(name, mode, json.dumps({k: res[k] for k in ("a_mean", "a_pass", "b_pass", "programs_used", "switches_per_min", "selection_entropy_nats", "mi_nats", "mi_p") if k in res}), flush=True)


if __name__ == "__main__":
    main()
