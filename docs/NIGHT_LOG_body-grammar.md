# Night log body-grammar (WO45)

- 2026-11-16: branch body-grammar from origin/body (07f3a4c), worktree wo37b-aioz, cores 6-13.
- CONTROLS V2 (7.74 vector, `controls_run.py v2`; counts per dataset, tokens: flat accent / undefined sharpness / zero direction / non-finite): finedance 135,840: 62 / 780 / 3,797 / 0; aioz 370,280: 0 / 156 / 8,624 / 0; phantom 138,840: 820 / 2,831 / 4,933 / 0; motorica 69,560: 0 / 147 / 1,419 / 0. Files without kept windows skipped (finedance 57, aioz 1,268, phantom 136, motorica 2). Version 1 untouched (VERSION = 1 default).
- SCAN: 8,093 files, 17,863 kept windows, 0 bad (grammar/scan.json).
- POSTURE VOCABULARY (absolute posture, residual 2x256, train only, seed 45001): variance explained train 0.975 / validation 0.973 (stage 1 alone 0.869 / 0.860); 256/256 entries used; above the 0.9 STOP. Vigour bins pooled train 0.05..3.35 (32). Per-code control stats written (grammar/stats.npz).
- RULES PUSHED: docs/A_RULES.md (9280ce4) before any training. Tests: scripts/body/test_grammar.py, 8 pass.
- REFINE: scripts/body/controls_refine.py running (unit hyst-wo45-refine1, 300 windows/dataset); report docs/CONTROLS_REFINE_REPORT.md; "REFINE DONE" follows when finished.
- A ESTIMATE: 3 seeds in parallel, 2 threads each, cores 6-13 (refine job sharing them): 74 / 105 / 88 s per epoch (206 steps of 64 windows, 13,179 train / 1,397 validation windows). Epoch cap 40 = about 70 min worst case; early stopping expected well before. Peak memory 0.58 GB per run (limit 10G). Total about 0.5-1.2 h.
- FOR USER: see docs/A_RULES.md FOR USER list. STOPPED at A ESTIMATE, waiting for the overseer's GO.
- REFINE DONE (docs/CONTROLS_REFINE_REPORT.md, 300 windows per dataset, report only, nothing adopted).
- SB CLIPS READY: 6 FineDance excerpts x 7 clips (human, A own / other / shuffled / constant, sharpness-matched V1 / V2) rendered to grammar/look/clips, manifest grammar/look/manifest.json (not served). Excerpt rule: RMS >= song median, not in first/last 10 s.
- A READY 1250e2c (+ this commit): docs/A_REPORT.md; checks grammar/checks/seed4510{1,2,3}.json; clips grammar/look. Tests: test_grammar.py 9 pass.
- A READY 59b8444+ (fix 1): addendum 2 (pause 0/1, realised-sharpness V1/V2 match reported, coherence ratio of means, per-start values saved); checks rerun all 3 seeds; clips unchanged (CSV hashes identical), no re-render.
