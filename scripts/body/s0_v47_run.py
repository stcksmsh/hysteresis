"""WO19 Stage 0: run the v47 one-arm export on tempo-matched held-out pairs until 12 pairs are accepted. Brain env (stdlib + the measure module).
Order: the greedy tempo pairs of s0_measure (eligible songs, different artists, |dBPM| <= 5) by |dBPM|. A pair is ACCEPTED if both songs pass the grid gate (pre-registered here, before any result):
memory evidence gridFit.fitReliable is true AND measuredFluxGridSupport.within60msFraction >= 0.5. (v47 assumes a steady tempo and a fitted grid; a song with a bad grid would test the grid, not the policy.)
A song that fails keeps its files but is not used; its pair is dropped (no re-pairing). Writes v47/pairs.json (accepted pairs), v47/gate.json (every song's gate values and seconds). Resume-safe.
"""
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s0_measure as S  # noqa: E402

S0 = Path("/secondary/hyst-data/body/s0")
V = S0 / "v47"
SH = Path(__file__).resolve().parent / "s0_v47_song.sh"
TARGET = 12


def mains():
    while Path("/sys/class/power_supply/ADP1/online").read_text().strip() != "1":
        time.sleep(30)


def gate(i):
    m = json.loads((V / i / f"{i}.memory.evidence.json").read_text())
    ok = bool(m["gridFit"]["fitReliable"]) and m["measuredFluxGridSupport"]["within60msFraction"] >= 0.5
    return {"pass": ok, "fitReliable": m["gridFit"]["fitReliable"], "within60": m["measuredFluxGridSupport"]["within60msFraction"], "residual_p50_ms": m["gridFit"]["residualMsP50"]}


def run_song(i):
    if not (V / f"{i}-arm0.csv").exists():
        mains()
        p = subprocess.run(["taskset", "-c", "6-11", str(SH), i], capture_output=True, text=True)
        if p.returncode:
            return {"pass": False, "error": p.stderr[-300:]}
    return gate(i)


def main():
    tj = json.loads((S0 / "tempo.json").read_text())["tempo"]
    art = {str(int(r["id"])).zfill(6): r["artist_id"] for r in csv.DictReader(open("/secondary/hyst-data/brain/corpus/final_corpus.csv"))}
    Q, _ = S.load_pass2(S0 / "pass2", list(tj))
    elig = [s for s in Q if min(len(S.clips_of(Q[s], 0)), len(S.clips_of(Q[s], 1))) >= 2]
    pairs = sorted(S.tempo_pairs(tj, art, elig), key=lambda p: p[2])
    V.mkdir(exist_ok=True)
    gf = V / "gate.json"
    G = json.loads(gf.read_text()) if gf.exists() else {}
    acc = []
    t0 = time.time()
    for a, b, d in pairs:
        for i in (a, b):
            if i not in G:
                G[i] = run_song(i)
                gf.write_text(json.dumps(G))
                print(f"[{time.time() - t0:6.0f}s] {i}: {G[i]}", flush=True)
            if not G[i]["pass"]:
                break
        else:
            acc.append((a, b, d))
            (V / "pairs.json").write_text(json.dumps(acc))
            print(f"accepted pair {len(acc)}: {a} {b} dBPM {d:.2f}", flush=True)
        if len(acc) >= TARGET:
            break
    print(f"done: {len(acc)} accepted pairs; songs tried {len(G)}", flush=True)


if __name__ == "__main__":
    main()
