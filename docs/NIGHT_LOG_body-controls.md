# Night log body-controls (WO43)

- 2026-11-16: rules note docs/CONTROLS_RULES.md pushed before any control value is computed. Source = realised q50 (50 Hz) of kept windows, rebuilt as t1a2_realised.sim_one (~0.25 s/window).
- CONTROLS COMPUTED finedance 3396 windows / 135840 tokens (812 files), aioz 9257 / 370280 (7408), phantom 3471 / 138840 (1040), motorica 1739 / 69560 (296). Kept-window counts equal the T0 tables. Re-simulated gate verdicts: see CONTROLS_REPORT.
- Rules addendum 1: lead onset rule relaxed (original never fired). Norm fitted on 2544 FineDance train windows.
- LOOK CLIPS READY: 15 pairs (5 controls x 3), 30 clips of 8 s, FineDance validation+test, V1/V2, rendered to /secondary/hyst-data/body/controls/look/clips/; manifest /secondary/hyst-data/body/controls/look/manifest.json (kind "pair", per-item question; dialstudy_session.py gained an optional `question` field, tested in test_dialstudy_wo43.py). Frame of C10_V1 checked (arm, lamp, 8.0 s). No session built, no answers file opened.
- FOR USER: realised stage as source; workspace z 0.11..0.77 m; log transform + eps 0.01 for vigour; sharpness 3 Hz cutoff; pause 0.05 m/s / 13 samples; 8 s clips, shortlist 20, V1/V2 only; beat strength and cortex structure FineDance only; lead rule relaxed (addendum 1); ear lanes are clipped at +-3 sd (un-standardised acoustic measures inherit the clip).
