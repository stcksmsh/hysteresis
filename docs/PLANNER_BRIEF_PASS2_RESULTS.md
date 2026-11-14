# Planner brief — K5-pass2 results (2026-11-08)

For the planning agent. Rules in force: BRAIN_SPEC 7.23-7.32 (pass2 bar = full K5 bar + `hyst check-csv` accepted on the three danced
songs + (e'1)/(e'2) per song <= 1.25x v47, 7.25; inner-rhythm wording by the kappa = 0 control, 7.31.3). ONE arm. ARGMAX for every claim.

## What ran

- **Training:** unit hyst-wo14-a2, branch body-k5p2. Options `--body v2f --hard-clip --floor-acc-hinges --contact-tc 0.006 --raised-plane
  --w-floor 1.0 --smooth-u` (c = 0.5).
  - One full pass, 977 rounds of 16 windows = 15,624 sixty-second training windows (260 h of window time; 162 h of distinct music,
    2,602 songs, 650 artists).
  - 17.50 h of compute (box 30 h). The run ended normally ("pass complete"); early stop never fired.
- **Validation** (217 windows, argmax, external/internal (a)):

  | Round | ext (a) | int (a) | (b) |
  |---|---|---|---|
  | 200 | 0.862 | 0.873 | 37.2 |
  | 400 | 0.895 | 0.921 | 36.3 |
  | **600 (best.pkl)** | **0.913** | **0.931** | 36.6 |
  | 800 | 0.875 | 0.869 | 37.1 |
  | 977 | 0.784 | 0.880 | 37.1 |

  K5 try 1 at round 977: 0.634 / 0.639.
- **Check** on best.pkl, round 600 (k5p2_eval.py, WO18; agent 1):
  - 1,071 check windows, 357 songs, 73 artists, none of them in training;
  - three policies (trained, untrained, trained with kappa forced to 0), argmax and sampled;
  - then the three danced songs as one continuous episode each, check-csv on each, (e') per song, and the three-panel videos
    (v47 one arm | fallback | pass2).

## Results (argmax). Overseer recomputed every interval

I recomputed every interval from the saved per-window a_gaps: per-song means, then a 10,000-resample bootstrap over the 357 songs, paired
for differences. My implementation is independent of the builder's code. All values match the builder's to 3 decimals.

| | Mean | 95 % interval |
|---|---|---|
| External (a), trained | 0.943 | [0.911, 0.977] |
| Internal (a), trained | 0.958 | [0.924, 0.992] |
| External, trained minus untrained | +0.922 | [0.891, 0.953] |
| Internal, trained minus untrained | +0.926 | [0.896, 0.957] |
| External, trained minus kappa0 | +0.025 | [0.021, 0.030] |
| Internal, trained minus kappa0 | +0.019 | [0.014, 0.023] |

- **K5 bar:** passes (external (a) > 0, and paired vs untrained > 0). K5 try 1: ext 0.625 [0.603, 0.648], +0.452 vs untrained,
  +0.086 vs kappa0.
- **Sampled (report only):** ext 0.943, int 0.957; vs untrained +1.044 / +1.057; vs kappa0 +0.025 / +0.019.
- **Untrained policy:** ext 0.022, int 0.032, (b) 53.2, MI 0.155 (p 0.001), 8 programs, e'1 8.47, e'2 0.103.
- **Trained kappa0 policy:** ext 0.918, int 0.939, 1 program.

**Danced songs.** Hand metrics recomputed by the overseer from the joint CSVs (m3f_report.hand_metrics on the 50 Hz CSV); they match the
builder's rollout-based values within 0.005. I also reran `hyst check-csv` myself: accepted on all three.

| Song | check-csv | e'1 (limit) | e'2 (limit) | Contact | End stops | Max hand speed | Lowest hand z |
|---|---|---|---|---|---|---|---|
| Instant Crush | accepted | 2.13 (5.32) | 0.000 (0.0121) | 0 | 0 | 0.741 m/s | 0.153 m |
| Five Years | accepted | 2.14 (5.18) | 0.000 (0.0066) | 0 | 0 | 0.741 m/s | 0.127 m |
| Presence | accepted | 2.11 (7.50) | 0.000 (0.0143) | 0 | 0 | 0.741 m/s | 0.140 m |

K5 try 1 on the same CSV measure: e'1 10.2 / 9.2 / 11.0, e'2 0.16 / 0.13 / 0.11, contact 91 / 89 / 96 %. v47 one arm: e'1 4.26 / 4.15 /
6.00.

**Pass2 bar: MET on every component.**

**Report only** (held-out windows, argmax):
- 0 % of time within 2 deg of a joint limit, on every ranged joint;
- 0 end-stop events and 0 clip-boundary holds;
- longest any-pose hold 0.06 s;
- (e) 6.4e-5.

**Readability per 60 s** of each danced song (external gap; its lower bound is in brackets):
- every segment > 0;
- the opening minute is lowest in all three songs: IC 0.29 [0.23], FY 0.33 [0.27], PR 0.38 [0.30];
- later segments range 0.61-3.06.

## Findings that need a ruling or a record

1. **One program.**
   - The trained policy uses a single program: 100 % in argmax on the check windows and in all three songs, and 128,513 of 128,520
     blocks in sampled mode.
   - (c) MI = 0.0 (p 1.0). Untrained: 8 programs, MI 0.155.
   - The readability comes entirely from the continuous movement, not from program choice.
2. **The inner-rhythm (kappa) contribution is small but above 0.**
   - Trained minus kappa0 is +0.025 external and +0.019 internal, with both intervals above 0. By 7.31.3 the inner-rhythm wording is
     licensed.
   - Trained kappa means are 0.005-0.015.
3. **Calmer than v47.**
   - Hand acceleration p99 is about 2.1 m/s² against v47's 4.1-6.0.
   - The hand never exceeds 1 m/s.
   - Peak hand speed is 0.741 m/s in all three songs, the same to 3 decimals. That looks like a ceiling of the movement mapping
     (probably the smooth-u map bounding the generator), not a song property. Cause not checked.
4. **Validation peaked at round 600 and fell after it** (ext 0.913 → 0.875 → 0.784; int 0.931 → 0.869 → 0.880). best.pkl = round 600 by the
   pre-set rule. Cause not checked.

## Questions

**Q1. Record pass2 as passing the pass2 bar (7.23 + 7.25), with K5 wording from round 600?**
Options:
- (a) record pass as is;
- (b) also require the user's verdict on the videos before any "pass" wording.

Recommend (a) for the numeric record, plus (b) for any public wording, since the user judges motion by eye (7.24 "spastic" verdict came
after a numeric pass).

**Q2. Inner-rhythm wording (7.31.3).**
Both kappa0 intervals are above 0, but the effect is +0.02-0.03 on a 0.94 gap.

Options:
- (a) license the wording as pre-registered;
- (b) license it with a mandatory size qualifier ("a small part of the readability, about 3 %").

Recommend (b).

**Q3. One program.**
Options:
- (a) record only (program-choice wording is already forbidden, 7.22);
- (b) a later diversity term.

Recommend (a) now. Revisit only if the user's verdict on the videos asks for more variety.

**Q4. Speed ceiling 0.741 m/s and calmer than v47.**
Options:
- (a) record and wait for the user's eye;
- (b) diagnose the ceiling now: report-only, no training; trace max hand speed vs the smooth-u bound on the toy.

Recommend (a) then (b) only if the user finds it too calm. (e'1)/(e'2) are upper limits only; nothing in the bar asks for a minimum.

**Q5. Late-run validation drop.**
Options:
- (a) record only;
- (b) a report-only diagnosis (e.g. kappa/temperature tau schedule, learning-rate cosine tail) before any future long run.

Recommend (a) now, (b) only before the next long run.

**Q6. Next step.**
Recommend: wait for the user's verdict on the three three-panel videos.
- Instant Crush: sent.
- Five Years and Presence: rendering, ETA about 23:40.

No new training is proposed. Hardware is untouched (never driven).

## Paths

- Check: `/secondary/hyst-data/body/k5p2/check/` (`check.json`, `summary.json`, `trained.json`, `untrained.json`,
  `trained_kappa0.json`, `songs/<song>.{json,pass2.csv}`).
- Videos: `/secondary/hyst-data/body/k5p2/video/<song>-three-panel-720p.mp4`, plus 1080p `<song>-k5p2.mp4`.
- Training: `/secondary/hyst-data/body/k5p2/run/` (`progress.json`, `train.log`, `best.pkl`).
- Code: branch body-k5p2 fd54a20 (not yet merged into body; verification of the diff pending).
