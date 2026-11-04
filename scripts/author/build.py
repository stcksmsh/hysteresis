#!/usr/bin/env python3
"""Build the authoring page: one self-contained HTML (data and mapping maths inlined) in /secondary/hyst-data/brain/author/.

usage: build.py [OUT_DIR]
Per song it reads the B7 lanes (mindState.brain of <mindstate>/mind-<song>.json, scripts/brain/brain_mindstate.py, 0.1 s bins), core-2b's mood.energy (same file, 0.5 s steps), and the
interpreted sidecar (phrases and beats for the export). Audio is symlinked into OUT_DIR/audio/ and loaded by relative URL, so
serve OUT_DIR with serve.py. Nothing derived from the songs goes into git.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRAIN = Path("/secondary/hyst-data/brain/mindstate")
MUSIC = Path("/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm")
SONGS = {  # song: (audio file, interpreted sidecar, mind file)
    "instant-crush": ("instant-crush.m4a", "instant-crush.interpreted.sidecar.json", "mind-instant-crush.json"),
    "five-years": ("five-years.m4a", "five-years-steady.interpreted.sidecar.json", "mind-five-years.json"),
    "presence": ("presence.m4a", "presence.interpreted.sidecar.json", "mind-presence.json"),
}


def song_data(name):
    audio, sidecar, mind = SONGS[name]
    sc = json.loads((MUSIC / sidecar).read_text())
    energy = json.loads((BRAIN / mind).read_text())["mindState"]
    assert energy["hopSeconds"] == 0.5, "mood.energy is expected at 0.5 s steps"
    b = energy["brain"]
    assert b["source"] == "b7-epoch6" and b["hopSeconds"] == 0.1

    def lane(v):
        return [0.0 if x is None else x for x in v]

    return {
        "name": name, "audio": f"audio/{audio}", "duration": sc["duration"], "n_bins": len(b["smoothedSurprisal"]),
        "arousal": lane(b["smoothedSurprisal"]), "tension": lane(b["l4PredictedVariance"]),
        "familiarity": [-x for x in lane(b["surprisalSlope30s"])], "surprisal_total": lane(b["surprisal"]["total"]),
        "band_power": [lane(b["bandPower"][k]) for k in ("L1", "L2", "L3", "L4")],
        "mood_energy": energy["mood"]["energy"],
        "phrases": [[p["start"], p["end"]] for p in sc["musicalMemory"]["phrases"]],
        "beats": sc["beats"], "sidecar": sidecar,
    }


def build(out):
    out = Path(out)
    (out / "audio").mkdir(parents=True, exist_ok=True)
    data = {n: song_data(n) for n in SONGS}
    for audio, _, _ in SONGS.values():
        link = out / "audio" / audio
        if not link.exists():
            link.symlink_to(MUSIC / audio)
    html = (HERE / "author_template.html").read_text()
    html = html.replace("/*CORE*/", (HERE / "author_core.cjs").read_text()).replace("/*DATA*/", json.dumps(data, separators=(",", ":")))
    (out / "data.json").write_text(json.dumps(data, separators=(",", ":")))
    (out / "index.html").write_text(html)
    return out / "index.html"


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else "/secondary/hyst-data/brain/author"))
