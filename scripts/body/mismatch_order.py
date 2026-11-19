"""WO53A order checks (docs/MISMATCH_RULES.md section 6).   mismatch_order.py SESSION_DIR  -> mismatch/order_checks.json"""
import itertools
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mismatch_build import OUT  # noqa: E402


def main(session):
    from scipy.stats import spearmanr
    S = Path(session)
    key = json.loads((OUT / "material_key.json").read_text())["items"]
    skey = json.loads((S / "key/key.json").read_text())["key"]
    order = json.loads((S / "order.json").read_text())
    pos = {skey[it["code"]]["id"]: n for n, it in enumerate(order)}
    ids = sorted(key, key=lambda i: pos[i])
    first = [key[i]["real_side"] == "first" for i in ids]
    P = [i for i in key if not key[i]["repeat"]]
    r = {"first_presentations": {k: sum(key[i]["real_side"] == k for i in P) for k in ("first", "second")}}
    r["per_kind"] = {k: {s: sum(key[i]["real_side"] == s and key[i]["kind"] == k for i in P) for s in ("first", "second")} for k in ("shifted", "different_song")}
    r["repeat_sides"] = {k: sum(key[i]["real_side"] == k for i in key if key[i]["repeat"]) for k in ("first", "second")}
    r["balanced_ok"] = r["first_presentations"] == {"first": 10, "second": 10} and all(v == {"first": 5, "second": 5} for v in r["per_kind"].values())
    rho, p = spearmanr(range(len(first)), first)
    r["position_spearman_rho"], r["position_spearman_p"], r["position_ok"] = float(rho), float(p), bool(abs(rho) < 0.4)
    r["longest_side_run"] = max(len(list(g)) for _, g in itertools.groupby(first))
    par = [(int(c[1:], 16) % 2, key[skey[c]["id"]]["real_side"] == "first") for c in skey]
    agree = sum(a == b for a, b in par)
    r["code_parity_vs_side"] = {"agree": agree, "n": len(par)}
    r["code_parity_ok"] = bool(abs(agree - len(par) / 2) <= len(par) ** 0.5)       # within 2 sd of chance (sd = sqrt(n)/2)
    sizes = {i: (OUT / "clips_src" / f"{i}.mp4").stat().st_size for i in key}
    sf = [sizes[i] for i in P if key[i]["real_side"] == "first"]; ss = [sizes[i] for i in P if key[i]["real_side"] == "second"]
    r["half_sizes"] = "both halves of a clip are the same encoded video segment (identical bytes); they differ by 0 %"
    r["clip_size_mean_real_first"], r["clip_size_mean_real_second"] = float(np.mean(sf)), float(np.mean(ss))
    r["clip_size_rel_diff"] = float(abs(np.mean(sf) - np.mean(ss)) / np.mean([*sf, *ss])); r["clip_size_ok"] = r["clip_size_rel_diff"] <= 0.02
    leaks = []
    for f in (S / "clips").glob("*.mp4"):
        tags = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags:stream_tags", "-of", "json", str(f)], capture_output=True, check=True).stdout.decode().lower()
        leaks += [(f.name, w) for w in ("shifted", "different", "first", "second", "real", "foil", "fd_", "ph_", "mo_") if w in tags]
    r["metadata_leaks"], r["metadata_ok"] = leaks, not leaks
    man = (OUT / "manifest.json").read_text()
    r["manifest_names_ok"] = not any(w in man for w in ("shifted", "different_song", "real_side"))
    r["pass"] = all(r[k] for k in ("balanced_ok", "position_ok", "code_parity_ok", "clip_size_ok", "metadata_ok", "manifest_names_ok"))
    (OUT / "order_checks.json").write_text(json.dumps(r, indent=1))
    print(json.dumps(r, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
