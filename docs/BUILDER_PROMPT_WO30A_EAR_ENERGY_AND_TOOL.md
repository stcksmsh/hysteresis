# Builder prompt: work order 30A, ear energy, arousal/energy comparison, round-2 session tool (2026-11-13)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER" instead of
waiting. You start with no context: everything you need is named below.

**This is a disposable study.** Nothing ships. No learning or training of any kind, no verdict. Kosta (the user) judges blind. One arm only
(permanent rule). A second builder (30B) builds the round-2 motor network and clips in parallel and **waits for your step 1**.

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works. Retry on a GitHub server
  error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:**
  - `src/` and `tools/` are read-only. Never drive hardware. Install nothing. No network downloads.
  - The cortex (B7 epoch 6) is frozen: read its lanes, never change or retrain it.
  - Data, audio and videos stay outside git. Copyrighted audio is never committed or uploaded anywhere.
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-mnettool4 origin/body`, then push `body-mnettool4`.
- **Jobs:**
  - Detached and memory-capped:
    `systemd-run --user --unit=hyst-wo30a-<fresh-name> -p MemoryMax=8G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`.
  - `python -u`. Cores **12-17** (`taskset -c 12-17`), never 6-11 (30B's). State thread counts.
  - Mains only: the script polls `/sys/class/power_supply/ADP1/online` and waits while it reads 0.
- **Push** within 30 minutes and after every phase. Log: `docs/NIGHT_LOG_body-mnettool4.md` (new; MORNING SUMMARY on top).
- **Environments:** body `/secondary/hyst-env/body` (numpy, scipy), brain `/secondary/hyst-env/brain` (torch, for cortex lanes).

## Read first

- `docs/BRAIN_SPEC.md` **§7.47** (binding, including the overseer notes 7.47.6), then §7.46, §7.45, §7.44.
- `scripts/brain/fast_features.py` (the 44 features; column 40 `onset`, 41 `rms`, 100 Hz), `scripts/body/k5_video_lanes.py`,
  `scripts/body/k5_data.py` (`arousal_b7`, 10 Hz, and its standardisation), `scripts/body/motornet_music.py` (how round 1 made the lanes for
  the five check songs).
- `scripts/body/dialstudy_session.py`, `motornet_measure.py`, `motornet_report.py`, `test_motornet.py`, `test_dialstudy.py`;
  `docs/MOTORNET_REPORT.md`, `docs/MOTORNET_RULES.md`.
- `/secondary/hyst-data/emotion/dial/HOWTO.txt` (dial format 2).

## The work

1. **Ear energy formula FIRST (before you read any dial value or compute any correlation).**
   - Write `docs/EAR_ENERGY_RULES.md`: the exact formula of one scalar "acoustic energy" per frame from columns 40 (`onset`) and 41 (`rms`)
     only: loudness term (default: 20 log10 of rms with a stated floor, then a 1 s moving mean), onset-density term (default: count of onset
     peaks per second over a 2 s window, peak rule stated), how the two are combined (default: each standardised over the three danced
     songs, then averaged), the output rate (10 Hz) and the standardisation used as a network input (one mean and sd over the three danced
     songs, clipped to +-3, as `arousal_b7`).
   - Implement it as `scripts/body/ear_energy.py` (a function from the 44-feature array to the lane, plus a CLI that writes the lane for a
     song) with tests on synthetic input (louder -> higher; denser clicks -> higher; silence -> floor).
   - Commit, push, write **"ENERGY READY <commit>"** in the night log. 30B pulls this commit. Do not change the formula afterwards; a needed
     change is a FOR USER entry and a stop.
2. **Comparison (report only).** Signals: `arousal_b7` and ear energy, for the three danced songs (Instant Crush, Five Years, Presence) and
   the five check songs. Dial data: `/secondary/hyst-data/emotion/dial/dial2.json` (pass A energy for Five Years and Presence; pass B light
   and heavy for all three) and `dial-ic-try1.json` (Instant Crush pass A, the first try on the older pad: use as given, mark it so in every
   table). Method exactly as 7.47.6: 2 s moving mean, 2 Hz, Pearson and Spearman per song at every lag from -2 s to +4 s in 0.5 s steps (dial
   behind music = positive), all lags reported, none picked. The 5 excerpts: mean of each signal over round 1's 12 s excerpts (start times in
   §7.46.4), ranked, beside Kosta's Part 3 notes (in `/secondary/hyst-data/body/motornet_toy/session_2026-11-13_part3/`). Also the
   correlation of `arousal_b7` with ear energy per song (lag 0). Output `/secondary/hyst-data/body/arousal_energy/` (numbers json + csv);
   report `docs/AROUSAL_ENERGY_REPORT.md`, no verdict, no interpretation beyond the numbers. Push, "COMPARISON READY <commit>".
3. **Round-2 session tool** (the clips come from 30B; its manifest format is in its rules file `docs/MOTORNET2_RULES.md` on `body-mnet4`;
   read it when pushed and match it):
   - the session tool takes Part A (8 silent 30 s clips, labels as 7.44.3.6: calm / sad / tense / energetic / light / nothing, glitching /
     something, can't name it; optional note) and Part B (5 pairs, "which fits the music?" + "neither"; pair order and left/right seeded),
     coded names, seeded order, key not served, loopback only;
   - `motornet_measure.py` adds: base yaw and shoulder p5-p95 range, facing drift (mean base yaw over the last 3 s minus the first 3 s, and
     the range of its 3 s moving mean), PR per population (activity arrays from 30B, population index in the manifest);
   - `motornet_report.py` writes `docs/MOTORNET2_REPORT.md`: setting -> label -> note -> measurements; Part B picks with both renders' hand
     speed, mean ear energy and mean `arousal_b7`; discards by gate; network and body parameters. Generate it on a synthetic session and READ
     the generated file (round 1's script once duplicated a section).
   - Tests for all of it. Push, **"TOOL READY <commit>"**.
4. **Done when:** ENERGY READY, COMPARISON READY and TOOL READY are pushed with MORNING SUMMARY. Then stop. Do not start a session for Kosta;
   the overseer does.

**Out of scope (stop and ask; log FOR USER):** changing the formula after ENERGY READY; picking lags or songs; any network, gate or clip
work (30B's); cortex changes; training; hardware; other audio.
