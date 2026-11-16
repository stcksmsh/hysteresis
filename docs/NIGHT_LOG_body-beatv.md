# Night log, body-beatv (WO47)

- Rules pushed first (docs/BEATV_RULES.md); inputs scanned (1341 songs, 203 raw files, 0 bad); librosa beats for all 1341 songs; per-file errors caught, none occurred.
- V2 first: raw FineDance BAS 0.227 (proxy) / 0.218 (approx FK) vs published 0.2120 (Lodge CVPR 2024 Table 1; the ICCV FineDance paper has no BAS): not far. Shifted-beat chance 0.225 / 0.214: BAS - chance ~0. Realised stage also at chance.
- V3: best offset spread over +-1 s, mean correlation curve flat, no per-file sync offset at 33 ms; drift mostly offset ambiguity.
- V1: project grid locally irregular (line residual 80-620 ms) and no lock; librosa grid (6-8 ms residual): yaw peaks lock in all four datasets (song-specific phase), onsets in AIOZ, lamp minima/acc peaks not. 184 AIOZ sequences skipped (<12 beats; 0.40 of 38.5 h).
- Added per-item question for singles in dialstudy_session.py (+ test). FOR USER: see BEATV_REPORT.

BEATV READY
CLICKS READY (/secondary/hyst-data/body/beatv/clicks/, manifest.json + key.json, 20 singles; not served). STOP.
