# Night log, body-data (WO32A)

## MORNING SUMMARY
(in progress)

## Log
- FOR USER / 32B: `docs/RETARGET_RULES.md` (a) assumes motion `T x 159` axis-angle. The real FineDance files are `T x 315`: 3 root + 52 x 6D rotation (unit, orthogonal pairs; verified on 001). Not axis-angle. Joint order and which rows/columns the 6D holds are not in the files; check against the FineDance code (its 6D to matrix step) before the scale step. 30 fps confirmed by wav length.
- MOTORICA BLOCKED: the only download link is a SharePoint folder (kth-my.sharepoint.com); plain HTTPS returns 403 (needs an interactive browser session). Not attempted further (STOP rule).
- FINEDANCE READY b224446
- 2026-11-13 12:56 FineDance: public Google Drive file, plain HTTPS, no login. 4.4 GB, sha256 d6ea2054..., unpacked 6.3 GB to `/secondary/hyst-data/datasets/finedance/` (LICENSE.txt, SOURCE.txt, INVENTORY.md there). 203 sequences, 7.66 h at 30 fps, 17 fine-genre strings (5 coarse), motion (T,315) = root xyz + 52 x 6D rotation, wav 48 kHz. /secondary had 402 GB free before. Joint order and 6D layout are not in the files: 32B must check against the FineDance code.
