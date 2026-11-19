# Night log: body-dialtool (WO28B)

## MORNING SUMMARY (2026-11-12)

- Effector shapes done: `ensemble_preview --implement lamp|gripper` (visual only; sim mass unchanged, 28A keeps the ball's).
- Blind labelling tool and report script done, tested on a fake 5-clip manifest.
- Not run with Kosta: the overseer starts the real session.

**EFFECTOR READY f936827**

## How Kosta runs it

```
python3 scripts/body/dialstudy_session.py --clips /secondary/hyst-data/body/dialstudy/clips/manifest.json --out /secondary/hyst-data/body/dialstudy/session_2026-11-13 --serve
```

Then open http://127.0.0.1:8765/ . Answers are saved at once (reload resumes). Never open the `key/` folder. Report afterwards:
`python3 scripts/body/dialstudy_report.py --session <that folder>` writes `docs/DIALSTUDY_REPORT.md`.
Re-serving an already built session: same command without `--clips`.

## Effector facts

- Shapes are sets of flat coloured polygons (new optional `aspect` and `matte` on `Mirror`; absent from the ball's JSON; matte parts throw no projector light).
- lamp: ten-panel conical shade, lit face at its mouth, opens along the last link; radius 0.100 m.
- gripper: 0.08 x 0.03 x 0.08 m palm block, three 0.06 m finger bars along the last link; radius 0.083 m.
- ball (for comparison): radius 0.080 m, stated mass 0.1019 kg (shell 0.0387 + mirrors 0.0632, `make_arm.ball()`). Sim keeps this mass and inertia for all shapes.
- Regression: `cargo test -p hyst-compile -p hyst-previz` 103 passed, clippy -D warnings clean on both. Ball and disc pages for a 3 s test CSV were built before (origin/body) and after: the embedded data (score, rig, ball and disc implement JSON) is byte-identical; the page differs only in 12 template-JS pieces (matte/aspect drawing), so the ball page's file hash changes (b2d10dfb to fd736be5). Not avoidable without a second template. v47 Off score/CSV exports go through code this change does not touch (rig JSON of the ball has no new fields; unit test asserts it).
- Looked at frames of both 3 s clips (/secondary/hyst-data/body/dialstudy/eff/{lamp,gripper}-still.mp4): lamp reads as a lamp, gripper as a palm with three fingers (small at this camera distance).

## Assumptions / FOR USER

- FOR USER: the label list is read as seven buttons: tense, heavy, calm, angry, light, "nothing, glitching", "something, can't name it".
- FOR USER: Set D manifest entries are assumed to be `{set: "D", files: [renderA, renderB], intent, id}`; 28A has not defined pairs.
- Manifest paths are relative to the manifest's folder. Port 8765 (`--port` to change).
- Tests: `python3 -I scripts/body/test_dialstudy.py` (5 tests: seeded stable order, key and order never served (404), answers written and resumed, pair items and range requests, report tables without verdict wording).
