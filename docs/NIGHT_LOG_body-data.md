# Night log, body-data (WO32A)

## MORNING SUMMARY
- FINEDANCE READY b224446 (203 sequences, 7.66 h, 30 fps). `/secondary/hyst-data/datasets/finedance/`.
- MOTORICA BLOCKED: only link is a SharePoint folder, 403 to plain HTTPS.
- AIOZ-GDANCE READY: 1624 group sequences (3 splits), SMPL 72-D + wav, 14.9 GB unpacked. `datasets/aioz/`.
- AIST++ READY: motions.zip (411 SMPL .pkl) and keypoints3d.zip (1408 .pkl), annotations only. `datasets/aist/`.
- TOOL READY: see the last line. Look-test mode in `scripts/body/dialstudy_session.py`, `retarget_report.py`, `test_retarget_look.py` (3 tests; the two older test files still pass). Matches 32B's manifest (singles with variant/clip/genre; pairs with files + variants, order never reshuffled).
- FOR USER / 32B: `docs/RETARGET_RULES.md` (a) assumes motion `T x 159` axis-angle. Real FineDance files are `T x 315`: 3 root + 52 x 6D rotation (unit, orthogonal pairs). Joint order and the 6D to matrix layout are not in the files; check the FineDance code before the scale step.
- FOR USER: no `.pkl` was opened (unpickling untrusted files can run code); shapes for AIOZ and AIST++ come from READMEs. Open them only with a restricted unpickler.
- FOR USER: AIST++ ignore_list.txt not fetched (not in the zips). Each dataset dir has LICENSE, SOURCE.txt (sha256, dates), INVENTORY.md. Nothing was uploaded.

## Log
- 2026-11-13 12:56 FineDance: public Google Drive file, plain HTTPS, no login. 4.4 GB, sha256 d6ea2054..., unpacked 6.3 GB. 17 fine-genre strings (5 coarse), wav 48 kHz.
- MOTORICA BLOCKED: kth-my.sharepoint.com folder, plain HTTPS 403 (needs a browser session). Not attempted further (STOP rule).
- AIOZ: HF page aiozai/AIOZ-GDANCE is ungated; 12.4 GB zip fetched, sizes match. Disk before: 392 GB free.
- AIST++: motions.zip and keypoints3d.zip from the page's release links, no form.
