# AIST++ BAS cross-check report (rules: `docs/AIST_BAS_RULES.md`)

Sequences: 1408 keypoints3d files, 45 dropped by the AIST++ ignore list, 1363 used. Per-sequence values: `/secondary/hyst-data/datasets/aist/bas/per_sequence.csv`. BAS = mean over sequences; chance = shifted-beat chance (20 draws); difference = per-sequence BAS minus chance, mean with 95 % bootstrap over sequences [A] and over music IDs [B] (2,000 resamples, seed 47101). Report only; no verdict.

### motion `optim`, constants `main`, BAS sum over music beats

| set | n seq | n music IDs | BAS | chance | difference [A: by sequence] | difference [B: by music ID] |
|---|---|---|---|---|---|---|
| full | 1363 | 60 | 0.2739 | 0.2378 | +0.0361 [+0.0271, +0.0451] | +0.0361 [+0.0176, +0.0544] |
| crossmodal_test | 20 | 10 | 0.3168 | 0.2368 | +0.0800 [-0.0301, +0.1909] | +0.0800 [-0.0710, +0.2342] |
| pose_test | 451 | 57 | 0.2802 | 0.2442 | +0.0360 [+0.0213, +0.0507] | +0.0360 [+0.0104, +0.0602] |

### motion `optim`, constants `main`, BAS sum over kin beats

| set | n seq | n music IDs | BAS | chance | difference [A: by sequence] | difference [B: by music ID] |
|---|---|---|---|---|---|---|
| full | 1363 | 60 | 0.4443 | 0.3902 | +0.0541 [+0.0402, +0.0678] | +0.0541 [+0.0284, +0.0795] |
| crossmodal_test | 20 | 10 | 0.4642 | 0.3907 | +0.0735 [-0.0599, +0.2101] | +0.0735 [-0.1021, +0.2532] |
| pose_test | 451 | 57 | 0.4422 | 0.3880 | +0.0541 [+0.0302, +0.0768] | +0.0541 [+0.0188, +0.0859] |

### motion `optim`, constants `literal`, BAS sum over music beats

| set | n seq | n music IDs | BAS | chance | difference [A: by sequence] | difference [B: by music ID] |
|---|---|---|---|---|---|---|
| full | 1363 | 60 | 0.2792 | 0.2126 | +0.0666 [+0.0554, +0.0774] | +0.0666 [+0.0458, +0.0875] |
| crossmodal_test | 20 | 10 | 0.3111 | 0.1873 | +0.1239 [+0.0256, +0.2264] | +0.1239 [+0.0016, +0.2603] |
| pose_test | 451 | 57 | 0.2769 | 0.2140 | +0.0629 [+0.0445, +0.0807] | +0.0629 [+0.0361, +0.0916] |

### motion `optim`, constants `literal`, BAS sum over kin beats

| set | n seq | n music IDs | BAS | chance | difference [A: by sequence] | difference [B: by music ID] |
|---|---|---|---|---|---|---|
| full | 1363 | 60 | 0.2555 | 0.1965 | +0.0590 [+0.0482, +0.0696] | +0.0590 [+0.0414, +0.0771] |
| crossmodal_test | 20 | 10 | 0.2978 | 0.1910 | +0.1069 [+0.0163, +0.1979] | +0.1069 [-0.0051, +0.2264] |
| pose_test | 451 | 57 | 0.2574 | 0.1952 | +0.0622 [+0.0438, +0.0799] | +0.0622 [+0.0379, +0.0868] |

### motion `raw`, constants `main`, BAS sum over music beats

| set | n seq | n music IDs | BAS | chance | difference [A: by sequence] | difference [B: by music ID] |
|---|---|---|---|---|---|---|
| full | 1351 | 60 | 0.2478 | 0.2316 | +0.0162 [+0.0090, +0.0234] | +0.0162 [+0.0001, +0.0320] |
| crossmodal_test | 20 | 10 | 0.2778 | 0.2468 | +0.0310 [-0.0500, +0.1212] | +0.0310 [-0.0673, +0.1512] |
| pose_test | 450 | 57 | 0.2527 | 0.2351 | +0.0176 [+0.0046, +0.0307] | +0.0176 [-0.0043, +0.0401] |

### motion `raw`, constants `main`, BAS sum over kin beats

| set | n seq | n music IDs | BAS | chance | difference [A: by sequence] | difference [B: by music ID] |
|---|---|---|---|---|---|---|
| full | 1351 | 60 | 0.4185 | 0.3930 | +0.0256 [+0.0140, +0.0374] | +0.0256 [+0.0028, +0.0476] |
| crossmodal_test | 20 | 10 | 0.4107 | 0.4259 | -0.0152 [-0.1162, +0.0914] | -0.0152 [-0.1408, +0.1119] |
| pose_test | 450 | 57 | 0.4153 | 0.3897 | +0.0256 [+0.0050, +0.0470] | +0.0256 [-0.0052, +0.0561] |

### motion `raw`, constants `literal`, BAS sum over music beats

| set | n seq | n music IDs | BAS | chance | difference [A: by sequence] | difference [B: by music ID] |
|---|---|---|---|---|---|---|
| full | 1363 | 60 | 0.2586 | 0.2197 | +0.0389 [+0.0289, +0.0484] | +0.0389 [+0.0193, +0.0588] |
| crossmodal_test | 20 | 10 | 0.2734 | 0.2073 | +0.0661 [-0.0298, +0.1704] | +0.0661 [-0.0483, +0.1978] |
| pose_test | 451 | 57 | 0.2632 | 0.2236 | +0.0395 [+0.0222, +0.0561] | +0.0395 [+0.0139, +0.0677] |

### motion `raw`, constants `literal`, BAS sum over kin beats

| set | n seq | n music IDs | BAS | chance | difference [A: by sequence] | difference [B: by music ID] |
|---|---|---|---|---|---|---|
| full | 1363 | 60 | 0.2324 | 0.1980 | +0.0344 [+0.0251, +0.0432] | +0.0344 [+0.0175, +0.0517] |
| crossmodal_test | 20 | 10 | 0.2328 | 0.2069 | +0.0259 [-0.0502, +0.1064] | +0.0259 [-0.0701, +0.1313] |
| pose_test | 451 | 57 | 0.2305 | 0.1946 | +0.0359 [+0.0203, +0.0524] | +0.0359 [+0.0123, +0.0609] |

Mean music beats per second: 1.59; mean sequence duration 13.2 s.
Notes. The ignore list holds 45 sequences (all present in keypoints3d). `crossmodal_test` holds 20 sequences in the file (all kept, none on the ignore list). The `raw` keypoints3d rows have 12 fewer sequences than `optim`: 12 sequences give no finite BAS (NaN keypoints, so no kinematic beats), counted as dropped there. Music alignment: 5 pairs of the same music ID from different videos align to 0.0 ms with correlation 0.9995-0.9999 (`scripts/body/aist_music.py align`). Music beats: 60 files, one per music ID, librosa as in WO47 V2.
