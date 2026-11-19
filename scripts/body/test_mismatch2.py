"""Tests of the round-2 changes (docs/MISMATCH2_RULES.md section 0). Synthetic only: no audio, no renderer, no session data."""
import json
import random
import sys
import urllib.request
from pathlib import Path
from threading import Thread

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import armonly_page as A  # noqa: E402
import dialstudy_session as D  # noqa: E402
import mismatch2_build as M2  # noqa: E402
from retime import L, retime  # noqa: E402


def test_shift_range_4_to_6():
    for seed in range(300):
        o, flag = M2.shift_foil(random.Random(seed), 30.0, 100.0)
        assert 4.0 <= abs(o) <= 6.0 and not flag and 10 <= 30 + o and 30 + o + 10 <= 90
    for seed in range(100):
        o, flag = M2.shift_foil(random.Random(seed), 11.0, 100.0)
        assert o > 0 and not flag
    assert M2.shift_foil(random.Random(1), 0.0, 12.0) is None


def test_offsets_leave_room_for_L():
    for v in ("V1", "V2"):
        os_ = M2.offsets(v)
        assert os_[0] == 0.0 and os_[-1] == 9.5 and all(o + L[v] + 10 <= 20 for o in os_)


def test_retimed_rows_shift_movement_earlier_by_L():
    t = np.arange(1001) / 50.0
    q = np.stack([t * 10 + j for j in range(5)], axis=1)       # linear ramp: value = 10 * window time + j
    for v in ("V1", "V2"):
        r = M2.retimed_rows(q, 3.0, v)
        assert r.shape == (501, 5)
        assert np.allclose(r[:, 0], 10 * (3.0 + L[v] + np.arange(501) / 50), atol=1e-9)
    # a pulse at window time 5.0 s lands at clip time 5.0 - offset - L; V2 (14 rows) agrees with the shared helper exactly
    p = np.zeros((1001, 5)); p[250] = 1.0
    r = M2.retimed_rows(p, 0.0, "V2")
    assert int(np.argmax(r[:, 0])) == 250 - 14
    assert np.array_equal(r[:, 0], retime(p, 50, "V2")[0][:501, 0])
    r1 = M2.retimed_rows(p, 0.0, "V1")                        # half row: shared between rows 232 and 233
    assert np.isclose(r1[232, 0], 0.5) and np.isclose(r1[233, 0], 0.5)


def test_foil_candidates_other_datasets_first():
    lists = {"finedance": {"fd_1": 0, "fd_2": 0}, "aioz": {"ai_1": 0}, "phantomdance": {"ph_1": 0, "ph_2": 0}, "motorica": {"mo_1": 0}}
    c = M2.foil_candidates(random.Random(3), "ph_1", "phantomdance", lists, {"fd_2"})
    ds = [d for d, _ in c]
    assert ds[-1] == "phantomdance" and "phantomdance" not in ds[:-1] and ("phantomdance", "ph_1") not in c and ("finedance", "fd_2") not in c
    assert len(c) == 4


def test_armonly_patch_disables_both_loops():
    src = ("x for(let k=-120;k<0;k++) { y for(let k=0;k<22;k++) { z")
    import retarget_page as RP
    orig = RP.patch
    RP.patch = lambda s: s
    try:
        out = A.patch(src)
    finally:
        RP.patch = orig
    assert A.is_arm_only(out) and not A.is_arm_only(src)


def test_session_intro_option(tmp_path):
    clip = tmp_path / "m" / "a.mp4"; clip.parent.mkdir(); clip.write_bytes(b"x")
    man = tmp_path / "m" / "manifest.json"
    man.write_text(json.dumps({"intro": "Each clip shows the SAME movement twice.", "clips": [{"id": "P01", "file": "a.mp4", "kind": "single",
                               "questions": [{"q": "Which?", "labels": ["first", "second", "same"]}]}]}))
    D.build(man, tmp_path / "s", 1)
    assert json.loads((tmp_path / "s/intro.json").read_text()) == "Each clip shows the SAME movement twice."
    assert D.Session(tmp_path / "s").state()["intro"].startswith("Each clip")
    srv = D.make_server(tmp_path / "s", 0); Thread(target=srv.serve_forever, daemon=True).start()
    try:
        page = urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/").read().decode()
        assert "st.intro && !started" in page
    finally:
        srv.shutdown()
    # without intro: no file, state None (old behaviour)
    man.write_text(json.dumps({"clips": [{"id": "P01", "file": "a.mp4", "kind": "single"}]}))
    D.build(man, tmp_path / "s2", 1)
    assert not (tmp_path / "s2/intro.json").exists() and D.Session(tmp_path / "s2").state()["intro"] is None
