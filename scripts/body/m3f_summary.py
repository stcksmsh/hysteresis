"""WO13B summary: /secondary/hyst-data/body/m3f/summary.json from the grid (tune), try 1 (held-out) with controls and breaches, and the four ablations of movement changes 1-4 (report only):
(a) external and internal, (e'1), (e'2), (e), table contact, and the paired try 1 - ablation differences (per episode, 95 % bootstrap, 10,000 resamples) for (a), (e'1), (e'2), (e) and contact. Argmax carries the bar; sampled is reported.
Provisional servo model (Feetech STS3215 12 V assumed)."""
import json
from pathlib import Path

import m3d_controls as K

D = Path("/secondary/hyst-data/body/m3f")
ABL = {"m1_no_jerk": "1 minimum-jerk cost off", "m2_no_obs_lp": "2 observer low-pass and jerk-descriptor removal off", "m3_no_phase_lp": "3 phase low-pass and order-parameter coupling off",
       "m4_no_xfade": "4 crossfade and switch cost off"}


def row(r):
    s = {}
    for m in ("argmax", "sample"):
        x = r[m]
        s[m] = {"ext_a": x["ext"]["a_gap_mean"], "ext_ci": x["ext"]["a_ci"], "ext_pass": x["ext"]["a_pass"], "int_a": x["int"]["a_gap_mean"], "int_ci": x["int"]["a_ci"], "int_pass": x["int"]["a_pass"],
                "b": x["b_rms_nonroll"], "b_pass": x["b_pass"], "c_mi": x["c_mi"], "c_p": x["c_p"], "c_pass": x["c_pass"], "programs_used": x["programs_used"], "e": x["e"]["mean"], "eprime1_acc_p99": x.get("eprime", {}).get("acc_p99_mean"), "eprime2_fast": x.get("eprime", {}).get("fast_mean"),
                "contact_share": x.get("eprime", {}).get("contact_mean"), "contact_s_mean": x.get("eprime", {}).get("contact_s_mean"), "kappa_mean": x["kappa_mean"]}
    return s


def main():
    out = {"grid": {}, "try1": None, "ablations": {}}
    for p in sorted((D / "grid").glob("*/result.json")):
        j = json.loads(p.read_text())
        out["grid"][p.parent.name] = {"w_jerk": j["args"]["w_jerk"], "w_switch": j["args"]["w_switch"], **row(j["result"])}
    t1p = D / "try1" / "result.json"
    if t1p.exists():
        t = json.loads(t1p.read_text())
        out["try1"] = {"args": t["args"], "scores": row(t["result"]), "breaches": {m: t["result"][m]["breaches"] for m in ("argmax", "sample")}, "raw0_old_body": t.get("raw0_old_body"), "raw_this_body": t.get("raw_this_body")}
        cs = D / "try1" / "controls" / "summary.json"
        if cs.exists():
            out["try1"]["controls"] = json.loads(cs.read_text())
        for n, label in ABL.items():
            p = D / "abl" / n / "result.json"
            if not p.exists():
                continue
            r = json.loads(p.read_text())["result"]
            out["ablations"][n] = {"label": label, "scores": row(r), "breaches": {m: r[m]["breaches"] for m in ("argmax", "sample")},
                                   "paired_try1_minus_ablation": {m: {"ext_a": K.paired_difference(t["result"][m]["ext"]["a_gaps"], r[m]["ext"]["a_gaps"]), "int_a": K.paired_difference(t["result"][m]["int"]["a_gaps"], r[m]["int"]["a_gaps"]),
                                                                      "e": K.paired_difference(t["result"][m]["e"]["per_episode"], r[m]["e"]["per_episode"]),
                                                                      "eprime1": K.paired_difference(t["result"][m]["eprime"]["acc_p99"], r[m]["eprime"]["acc_p99"]),
                                                                      "eprime2": K.paired_difference(t["result"][m]["eprime"]["fast"], r[m]["eprime"]["fast"]),
                                                                      "contact": K.paired_difference(t["result"][m]["eprime"]["contact"], r[m]["eprime"]["contact"])} for m in ("argmax", "sample")}}
            for m in out["ablations"][n]["paired_try1_minus_ablation"].values():
                for v in m.values():
                    v.pop("per_episode", None)
    (D / "summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: (list(v) if isinstance(v, dict) else v) for k, v in out.items() if k != "try1"}, indent=1))


if __name__ == "__main__":
    main()
