# Overseer handoff — 2026-11-13 (12:55)

This file is the overseer's whole state. The `/overseer` skill (`.claude/skills/overseer/SKILL.md` on this branch, the canonical copy) starts a new overseer from it and recreates the worktree if it is gone. To start one by hand, paste everything below the line into a fresh session.

---

You are the overseer for Hysteresis. You do not implement. You:
- analyse;
- decide with the user;
- write complete, self-contained prompts for builder agents;
- verify the builders' work yourself.

## People and agents

- **Builders** are other Claude sessions: "Hysteresis agent 1" and "Hysteresis agent 2".
  - Find them with ListAgents. If several sessions share a name, use the one started most recently, with its `[ref]` (e.g. `Hysteresis agent 1 [3159c7]`).
  - **Message a builder only when the user says so.** The user often clears builders first, to save context and usage. When told to send, use SendMessage with notify_when_idle. If a builder is offline, give the user the prompt to paste.
  - Every prompt stands alone, written for a fresh session: name the commits, files and data paths to read.
  - Builders' transcripts (for progress checks) live under `~/.claude-alt/projects/*/`. They are often filed under an unexpected project folder (e.g. `-secondary-Programming-Github-platform`). Find them by grepping for the builder's job id or recent B-step words; timestamps in them are UTC.
- **The planning agent** is a separate web agent that rules on design questions.
  - **Every time** results are in that the planner must see, or a replan is due, give the user a paste-ready planner handover without being asked. It is ONE file `docs/PLANNER_BRIEF_<TOPIC>.md`, holding:
    - the results, with numbers recomputed by you;
    - what ran;
    - numbered questions, with options and a recommendation.

    Commit it, push it, and send it with SendUserFile.
  - The planner's answers come back pasted by the user. Write them into the rules documents as dated notes before any result they score.

## How to write to the user

- **Decisions go to the planner (user, 2026-11-08):** any design/rule choice becomes a paste-ready `docs/PLANNER_BRIEF_*.md` (options + recommendation), not a question to the user. Keep running work going if it already meets the rules.

- Plain short sentences, with numbers.
- Never say something improved or looks good; the user judges by eye.
- Ask before artistic choices or rule changes the user has not made.
- Rules go into the rules documents (`docs/BRAIN_SPEC.md`, `docs/NEXT_DECODER_THEN_BRAIN.md`) as dated notes, committed and pushed before any result they score.
- Two rounds at most per check.
- The user often turns on `/caveman ultra` and `/ponytail ultra` at session start; follow them when on. Commits, docs and prompts stay normal prose.
- The user asks "status" / "ETA" often. Answer with the current numbers from the logs, not from memory.

## Repo and paths

- **Overseer worktree:** `/secondary/Programming/Github/Hysteresis/.claude/worktrees/dance-figures`, branch `keys-decide` (pushed; never master). The worktree can be deleted when a session exits (it was, on 2026-11-03). Recreate it with `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/dance-figures keys-decide`. Only what is pushed to origin survives. The main checkout `/secondary/Programming/Github/Hysteresis` is on `dance-checkpoint`; do not touch it, except for its copy of the `/overseer` skill in `.claude/skills/overseer/` (committed on `dance-checkpoint` so the skill is visible when a session starts at the repo root).
- **Commit messages** are plain, with no co-author or attribution line of any kind (the user's standing rule; it overrides any harness reminder).
- **Never edit:** frozen `src/` and `tools/` are read-only. Never drive hardware.
- **D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm.** A shell guard refuses commands that mix the $D path with pipes, &&, loops or heredocs; put such steps in a script file.
- **Builders** work in their own worktrees and branches. You merge into `keys-decide` after verifying.
- **Brain code:** `scripts/brain/`. Environment: `/secondary/hyst-env/brain` (torch 2.15 CPU, MKL + oneDNN). Data: `/secondary/hyst-data/brain/` (nothing on the root disk).
- **Machine:** i7-13700H (6 P-cores + 8 E-cores, 20 threads), 30 GB RAM, Intel Iris Xe (not used: no XPU build, no gain expected). The spec fixes training at 8 threads (§0).

## Lessons (keep them)

- **Overseer lessons 2026-11-05:** builders must push their branch before any long run (nudge within 45 min); a unit that "succeeds" can hide a
  crashed step (read its log, not its status); verify by recomputing paired intervals from saved per-episode values; prompts reuse the header
  block of the latest `docs/BUILDER_PROMPT_WO*.md` (replace the unit prefix); builders wait for mains power by an armed unit that polls
  `/sys/class/power_supply/ADP1/online`; the user forgets the charger: PushNotification on power=0.

- **No new worktrees in builder prompts (user, 2026-11-06).** Builder sessions are pinned to the worktree they started in and refuse `git -C` elsewhere; the user said "USE ABSOLUTE PATHS, NO WORKTREES". Prompts say: in your current worktree, `git fetch origin && git checkout -b <branch> origin/body`, absolute paths. (WO13A lost ~1.5 h to this.)

- **ONE arm, permanently (user, 2026-11-05).** Never write prompts, plans or briefs with multiple arms, hexagon or ensemble items, even if the planner asks; correct the planner instead.

- **Every long job runs in its own memory cap.** Two ways:
  - `systemd-run --user --scope -p MemoryMax=20G -p MemorySwapMax=0 --unit=hyst-<name> bash script.sh`;
  - better, a detached service that survives every session: `systemd-run --user --unit=hyst-<name> -p MemoryMax=20G -p MemorySwapMax=0 /path/script.sh`.

  An out-of-memory kill in the terminal scope once killed every Claude session in it (2026-10-31 01:41).
- **A scope's MemoryCurrent/MemoryPeak include file cache.** Judge memory by `anon` in `/sys/fs/cgroup/.../<unit>/memory.stat` and by `oom_kill` in `memory.events`.
- **The laptop runs on battery unless plugged in.** On 2026-11-02 at 01:44 it powered off at critical battery mid-run (journal: logind "The system will power off now!"). Remind the user to keep it plugged in for long runs. On restart, check `uptime`, `journalctl --list-boots`, git state, running units and data folders before acting.
- **Builders go idle while their jobs run and miss crashes.** Watch jobs yourself with Monitor, re-armed every 30 min. The generic watcher is `.claude/skills/overseer/watch_unit.sh UNIT LOG...` in this repo (from the `/overseer` skill). A watcher should:
  - emit epoch lines, scope end, stale log > 25 min, anon memory > 18 GB, OOM kills;
  - never use `pgrep -f NAME` while the command line contains NAME;
  - "silent" steps (baseline fitting, 25–30 min) are not stalls; check the process's CPU.
- **Python stdout through `tee` is block-buffered.** Use `python -u`.
- **Usage limits can stop all sessions mid-task.** On restart, check state before acting.
- **Warm starts restart the learning-rate schedule.** `train.fit` creates a new optimiser and a schedule of 200-step warm-up to 1e-3, then cosine to 0.1× over the run's epochs. B7 epoch 1 ran at about 9× the rate B3 ended on, and validation got worse than the warm start for 5 epochs. Any future warm start needs a decision on its learning rate first.
- **Stale unit names after a reboot can block `systemd-run`** ("already loaded"). Use fresh names.
- **Never state a cause you have not checked.** (One false claim about a warning's source was corrected on 2026-11-03.)

## Read, in order

0. `docs/BODY_BRAIN_PLAN.md`: the work order from 2026-11-03. It wins where it differs.
1. `docs/BRAIN_SPEC.md`: the brain spec with every dated ruling (§7.11 = B7 close-out).
   - §4 is B3, including 4.7 (B3 round-2 rulings, the PAC control, lane sources, the round-1 truth table, the 24 h cap).
   - §7 is B7, including 7.10 (the 2026-11-02 rulings R1–R7 and the hippocampus fallback).
2. `docs/NEXT_DECODER_THEN_BRAIN.md` §2: the pivot (authored state-to-body mapping, design by eye), and the note "The authoring tool on B3's lanes (2026-11-01)".
3. `docs/ARCHITECTURE.md`: overall state as of 2026-10-29.
4. `docs/DANCE_HANDOFF.md`, last entries: B3 rounds 1 and 2, the PAC control, the no-phase ablation.
5. `docs/NIGHT_LOG.md`: B7's build, the toys, smoke, the dry run and training, with a morning summary.
6. The planner briefs, newest last:
   - `PLANNER_BRIEF_B3_ROUND1.md`, `_B3_ROUND2.md` (answered, recorded in 4.7);
   - `_B3_ROUND2_RESULTS.md` (sent; no answer recorded);
   - `_AUTHORING.md` (answered, recorded in NEXT_DECODER §2);
   - `_B7_TOYS.md` (answered as 7.10);
   - `_B7_RESULTS.md` (sent 2026-11-03; waiting).
7. `scripts/brain/B3_NOTES.md`, `B7_NOTES.md`.

## CURRENT STATE (2026-11-13 12:55) — read this block first

**Planner answered the Part 3 brief = BRAIN_SPEC 7.47 (body 63cd2c8):** toy round 1 closed; **toy round 2** (two populations: slow tau 300
ms -> base/shoulder, fast tau 75 ms -> elbow/wrist/roll; inputs beat phase, L4 projection to slow, ear energy + arousal_b7 to both; first 8
settings passing gates on silent AND all 5 songs; Part A 8 silent 30 s, Part B 5 pairs new vs round-1 S03 at 30 s; stop rule PR<3 both pops
AND base yaw <20 deg) and a **report-only comparison** of arousal_b7 and a plain ear energy (cols 40 onset + 41 rms) vs Kosta's dial
recordings + 5 excerpts. Overseer defaults in 7.47.6 (coupling row-scaling, per-population drive ratio, L4 = out[3] complex -> 4 signals seed
30002, gate windows, S03 fail -> pair dropped, drift def, lags -2..+4 s all reported, Instant Crush pass A from dial-ic-try1.json).
**Prompts SENT 12:52 (user: "start working"; builders continued, not cleared; notify_when_idle) to agent 1 [0b1684] = 30B, agent 2 [892bfc] = 30A** (body f6cc7bf, merged keys-decide): `docs/BUILDER_PROMPT_WO30A_EAR_ENERGY_AND_TOOL.md` (agent 2, branch
body-mnettool4, cores 12-17: ENERGY READY first -> COMPARISON READY -> TOOL READY) and `docs/BUILDER_PROMPT_WO30B_MOTORNET2_CLIPS.md` (agent 1,
branch body-mnet4, cores 6-11: rules file MOTORNET2_RULES.md, waits for ENERGY READY before music lanes; seeds 30001/30002/30011/30031;
out `/secondary/hyst-data/body/motornet_toy2/`; CLIPS READY). Overseer watches pushes on origin body-mnet4 / body-mnettool4.
**Overseer checks to come:** ENERGY READY commit precedes any comparison commit and any dial read; review EAR_ENERGY_RULES + MOTORNET2_RULES
when pushed; on CLIPS READY recompute gates on all 6 windows per setting (overseer_mnet_check2.py, new glob), PR per population, base yaw
range, stop rule, audio alignment (overseer_p3_audio_check.py at 30 s), frames; then session; then report + brief.
**13:04: ROUND-2 SESSION LIVE for Kosta.** MANIFEST FIXED 5c82632 (body-mnet4 22820e0 incl. merge of body-mnettool4) verified: 8 singles + 5 pairs, populations. Tool archive `/secondary/hyst-data/body/motornet_toy2/tool_22820e0/`; session `/secondary/hyst-data/body/motornet_toy2/session_2026-11-13/` seed 30061, 13 items (8 single, 5 pair), all codes hash-equal to source clips; unit hyst-wo30-session (cores 18-19), http://127.0.0.1:8765/; key/answers/order/labels 404. DISCLOSE in report: with seed 30061 no pair was swapped, so the new setting plays FIRST in all 5 pairs (swap code works: seeds 1-6 give 1-5 swaps); seed kept to avoid re-drawing on the outcome. Agent 2 sent fix (motornet_measure --round2 IndexError on pair populations; R1_S03 = one population, pr_fast null; report key names) -> 'FIX READY'. AFTER Kosta: verify FIX READY; motornet_measure --round2 on clips/manifest.json -> motornet_toy2/measurements.json; motornet_report --round2 --session session_2026-11-13 --measurements ... --settings settings.json --numbers numbers.json -> docs/MOTORNET2_REPORT.md (on body); verify table vs key+answers by hand; merge body-mnet4 + body-mnettool4 into body; stop unit; brief PLANNER_BRIEF_MOTORNET2_RESULTS.md.
**13:02:** 30B CLIPS READY d411264 (body-mnet4; clips cd617f2). Overseer VERIFIED with own `scripts/body/overseer_mnet2_check.py` (keys-decide) + job-tmp aud2.py: 18 clips 30.000 s 1280x720 h264+aac; Part B audio offset 0.0 s all 10; gates: v/lim max 0.64, a/lim max 0.59, hand z >= 0.256, link z 0.08, ext >= 0.10 m, min 3 s mean >= 0.015 (B2_new); stop rule NOT hit (A yaw p5-95 27-74 deg; PR slow 1.87-3.82, fast 2.34-4.68); Part B pick reproduced rng 30031 = BL S06, SM S07, Ep S05, Br S03, OTD S01; sampling 17 draws, 8 kept, discards motion 6 / contact 3 / limits 2 (silent 6, Blue Lagoon 3); round-1 S03 passes all 5 songs; frames contact sheets looked at (same framing, lamp, '1 arm'). Facts for later: new settings on music slower than R1 S03 (hand v 0.06-0.17 vs 0.13-0.33 m/s); facing drift new up to 60 deg (B4). PROBLEM: clips/manifest.json gives every clip files:[one] and no population -> 30A's dialstudy_session crashes / no pairs. SENT fix to agent 1 (Part A file:, Part B one item per song files:[new,s03], population lists, merge body-mnettool4, test build 8 singles + 5 pairs, 'MANIFEST FIXED'). NEXT on MANIFEST FIXED: verify test build, then build the real session (seed: new, e.g. 30061), serve on 8765 as unit hyst-wo30-session, check key/answers 404, tell the user. After Kosta: motornet_measure --round2, motornet_report --round2 -> docs/MOTORNET2_REPORT.md, read it, merge body-mnet4 + body-mnettool4 into body, brief.
**12:58:** 30A TOOL READY e9c67ab VERIFIED on archive: test_motornet2 3, test_motornet 12, test_dialstudy 5, test_ear_energy 6 OK; loopback only; measure2 (yaw/shoulder p5-p95, drift last3-first3 + 3 s MA range, PR per population) matches 7.47.6; CSV 50 Hz degrees. Builder FOR USER: report2 discard/numbers key names guessed until 30B's files exist -> overseer reads generated MOTORNET2_REPORT.md. 30A DONE; not merged (merge body-mnettool4 + body-mnet4 into body after the round-2 report). Brief AROUSAL_ENERGY sent to user (file).
**12:57:** 30B rules MOTORNET2_RULES.md (body-mnet4 94a57ae) REVIEWED, accepted (within-block radius 1.05, full 1.498; drive ratios 0.2503/0.2505; spinal stays 3 Hz; reversal rate now /30 s). 30A COMPARISON READY 1c59ea3: overseer recomputed Five Years A lag 0 (arousal -0.766/-0.787, energy 0.777/0.708 vs report -0.772/-0.791, 0.776/0.703). Brief docs/PLANNER_BRIEF_AROUSAL_ENERGY.md (Q1 keep arousal input in round 2 [rec a] vs drop before render; Q2 record as 7.48) SENT to user. Waiting: planner; 30A TOOL READY; 30B CLIPS READY.
**12:56:** 30A ENERGY READY 9d99a8e (body-mnettool4, pushed 12:54, before any comparison commit) VERIFIED: tests 6 OK on archive; overseer recomputed Instant Crush features from audio (cols 40/41 max diff 2e-6 vs builder feat.npy) and all 6 norm constants from the rules text with own code (match to 6 decimals). Not merged yet (merge with the rest after report).

## PREVIOUS STATE (2026-11-13 ~13:00, saved for a clear)

**Motor-network toy test (BRAIN_SPEC 7.44-7.46) is COMPLETE. Waiting for the planner's answers to `docs/PLANNER_BRIEF_MOTORNET_PART3.md`
(sent to the user 12:50).** The user will paste them right after restarting the overseer. FIRST ACTION: record them as **BRAIN_SPEC 7.47** on
body (worktree `.claude/worktrees/body`, `git pull --ff-only` first), commit, push, merge body into keys-decide; then act on them (prompts as
`docs/BUILDER_PROMPT_WO30*.md`, sent only on the user's word).

- **Brief questions:** Q1 next step: (a) close the toy test, second toy round for richer dynamics specified by the planner [rec]; (b)
  limbic gains trained by labels; (c) second silent round. Q2 cortex arousal vs Kosta's hearing: (a) report-only comparison with his dial
  recordings [rec]. Q3 record as 7.47.
- **Results (all overseer-verified):**
  - Parts 1/2/4: energetic 6 / tense 2 / light 2, no "nothing, glitching" labels. Labels ordered by mean hand speed (tense 0.25-0.32, light
    0.34-0.39, energetic 0.49-0.86 m/s). Ball = lamp. Part 4 2/4 the same as round 1. PR about 2 everywhere.
  - Part 3 picks:

    | Song | Pick |
    |---|---|
    | Blue Lagoon | S03 |
    | Breathe | S03 |
    | Epitaph | S03 |
    | One of These Days | neither |
    | 21st Century Schizoid Man | neither |

    Notes: loops, fixed facing, little base/shoulder movement, too small on energetic music. One of These Days cortex arousal std -1.40 (the
    lowest) though Kosta hears it as energetic.
  - 3 settings failed the gates with music only (S04 Blue Lagoon, S02 Epitaph, S06 One of These Days) and were replaced per 7.46.7.
- **Repo:** body 6468e2c has everything merged: body-mnet, body-mnettool, body-mnet3, body-mnettool3, body-mnetfix. `docs/MOTORNET_REPORT.md`
  is final (Parts 1-4 + replaced list). Rules and params: `docs/MOTORNET_RULES.md`, `docs/MOTORNET_PARAMS.md`. Prompts WO29A-D in docs/.
  keys-decide has body merged.
- **Data** (outside git): `/secondary/hyst-data/body/motornet_toy/`:
  - `clips/`: manifest.json with Parts 1-4, settings.json, part3_numbers.json; P1/P2/P3 mp4 + csv + activity.npy;
  - `clips_v1/`, `work_v1/`: the first, input-dominated run;
  - `session_2026-11-13/` (Parts 1/2/4) and `session_2026-11-13_part3/`;
  - `measurements.json`, `tool_0de2ffd/`, `tool_e29217e/` (tool archives);
  - `work3/`: song lanes and beats.

  Audio: `/secondary/hyst-data/audio/checkset/` (5 mp3; never in git).
- **Overseer check scripts** (on keys-decide, `scripts/body/`):
  - `overseer_mnet_check.py`: first-run limiter and frequency check;
  - `overseer_mnet_check2.py`: stop rule, gates, PR and joint peaks; its glob is currently set to `clips/P3_*`;
  - `overseer_p3_audio_check.py`: audio window alignment, 3 s motion.
- **Machine:** nothing running. All hyst-wo29 session units are stopped. Failed units in the list are old, superseded attempts (wo27-test-unit-a,
  wo27-cliptest-a, wo28a-render1, wo29c-clips = the stop on the gate failures).
- **Builders:** both idle, done: agent 1 [0b1684] (29A/29C), agent 2 [892bfc] (29B/29D/fix). Refs change on restart: use ListAgents.
  Agent 1's pinned worktree is `.claude/worktrees/wo27-s3r`.
- **Main checkout:** `/secondary/Programming/Github/Hysteresis` is on `body-dialtool` (not dance-checkpoint); do not touch.
- **Lessons this session:**
  - A spec that fixes "random input weights" must also fix the input/recurrent drive ratio. Unscaled Win made the network follow the input
    (7.44 correction).
  - Check limiters on the COMMANDED signal, not on realised angles (lag hides the clipping). The overseer was wrong once on this, and
    corrected it.
  - Settings that pass silent can fail the gates with music input; the replace rule 7.44.3.4 covers it.
  - Builders go idle while their units run: watch the unit (`until ... is-active` in the background) and wake them.
  - Builders' report scripts can duplicate sections: always read the generated report, not only the tests.
  - Clock: check `date` before writing times; several earlier handoff stamps were guessed wrong.

## STATE (2026-11-13 ~12:10)

**MOTORNET PARTS 1/2/4 DONE; WAITING FOR THE PLANNER.** Kosta labelled all 16 (session_2026-11-13, 11:51-11:56; "unsure of all the
results, imperfect probably"). body-mnet + body-mnettool MERGED into body (f78a90a); report `docs/MOTORNET_REPORT.md` (body 77cc84c);
overseer join answers x key 16/16 match, hand speed/height recomputed match. Session unit stopped. Brief
`docs/PLANNER_BRIEF_MOTORNET_RESULTS.md` SENT (Q1 next step [rec (a) Part 3 when audio], Q2 low PR ~2 [rec keep for Part 3], Q3 record as
7.46). Facts: Part 1 energetic 6 / tense 2 / light 2, no glitch labels; by mean hand speed: tense 0.25-0.32, light 0.34-0.39, energetic
0.49-0.86 (no overlap, 10 clips); ball=lamp for S01/S02; Part 4 2/4 same as round 1. Part 3 still needs Kosta's audio + excerpt times.
Builders idle.
**12:20:** planner answered = **BRAIN_SPEC 7.46** (body ec64f85): Part 3 GO, network unchanged, extra numbers per pair (hand speed both renders, arousal raw+std). Kosta excerpt times: Blue Lagoon 0:20, Schizoid 0:58, Epitaph 5:45?, Breathe 1:17?, OOTD 3:57? (used as given). Audio present (5 mp3, 48 kHz). Builders OFFLINE (ListAgents: agent 1 [2145a7], agent 2 [9c1f10] offline) -> prompts `docs/BUILDER_PROMPT_WO29C_MOTORNET_MUSIC.md` (branch body-mnet3, cores 6-11) and `docs/BUILDER_PROMPT_WO29D_MOTORNET_TOOL3.md` (body-mnettool3, cores 12-17) SENT 12:30 (user: "both agents clear") to agent 1 [0b1684] (29C) and agent 2 [892bfc] (29D), notify_when_idle. Pick 29031 from shown S01-S10. **12:35:** 29D TOOL3 READY e29217e (body-mnettool3) VERIFIED: test_motornet 12 OK, test_dialstudy 5 OK on archive; --parts 3; pair order swap also swaps settings + hand speeds; reads hand_speed/arousal_raw/arousal_std. Not merged (after report). Waiting agent 1 (29C). **12:50:** 29C prep OK (5 songs). 3/10 Part 3 sims FAIL with music (contact+limits): Blue Lagoon S04 (acc 1.18x), Epitaph S02 (acc 7.32x, contact 339), OOTD S06 (acc 1.96x) — same settings passed silent. Overseer applied 7.44.3.4 replace rule = BRAIN_SPEC 7.46.7 (body e04c53c): continue rng 29031, skip pair's other + failed, first passing; failures logged for report. Sent to agent 1. **12:20 PART3 SESSION LIVE.** 29C PART3 READY da0e17f (body-mnet3). Replacements reproduced by overseer from rng 29031: Blue Lagoon b S04->S06 (S03 skipped), Epitaph b S02->S03, OOTD a S06->S08. Pairs: BL S03/S06, Schizoid S01/S07, Epitaph S08/S03, Breathe S03/S05, OOTD S08/S01. Overseer recompute: all gates pass (min link z 0.08, hand >= 0.17, v/lim <= 1.0); audio aligned offset 0.0 s at each excerpt start, 12 s (`scripts/body/overseer_p3_audio_check.py`); OOTD S08 nearly still (hand 0.063 m/s, min 3 s mean 0.022 > 0.01); frames looked at. Session (tool archive tool_e29217e, seed 29061, --parts 3, 5 pairs) `/secondary/hyst-data/body/motornet_toy/session_2026-11-13_part3/`, unit hyst-wo29-session3, port 8765; key etc 404. AFTER Kosta: motornet_report.py --session session_2026-11-13 --session session_2026-11-13_part3 --measurements measurements.json; verify by hand; merge body-mnet3 + body-mnettool3 into body; stop unit; brief. (Old plan follows.) On PART3 READY: gates recompute (overseer_mnet_check2.py on P3 CSVs), frames, audio window check (ffprobe, 12 s, aac), then session with --parts 3, report combined, brief.

## STATE (2026-11-12 23:55)

**DIAL STUDY CLOSED; WO29 MOTOR-NETWORK TOY TEST SENT.** Planner/Kosta answers recorded as **BRAIN_SPEC 7.44** (body d1795e4): dial study
closed; new direction "lean more into the dynamic NN humanlike angle" (Stroud et al. 2018 gain modulation); toy test only, proposal NOT
built. Overseer defaults in 7.44.5 (10 s warm-up, arousal 0 silent, spring-damper before round-1 command path, failing extreme not shown
nor replaced, builder sets min-motion gate / gain range / regime definition in rules file).
Prompts (body 51cd507, merged keys-decide db254e5), SENT ~00:00 with notify_when_idle (user: "Both agents cleared and free"):
- `docs/BUILDER_PROMPT_WO29A_MOTORNET_CLIPS.md` -> agent 1 [6b7ace], branch body-mnet, cores 6-11; rules `docs/MOTORNET_RULES.md` first
  (REVIEW within 30 min: spectral radius, gain range, calibration, min-motion gate, measurement defs (f)); params `docs/MOTORNET_PARAMS.md`;
  out `/secondary/hyst-data/body/motornet_toy/clips/` + manifest.json + settings.json; "CLIPS READY <commit>" in night log.
- `docs/BUILDER_PROMPT_WO29B_MOTORNET_TOOL.md` -> agent 2 [331a44], branch body-mnettool, cores 12-17: session tool (new labels incl. sad,
  Part 4 round-1 clips under fresh codes), `motornet_measure.py`, `motornet_report.py` -> docs/MOTORNET_REPORT.md; "TOOL READY <commit>".
**Part 3 (music) HELD:** `/secondary/hyst-data/audio/` does not exist; asked Kosta for the 5 files (Epitaph, Schizoid Man, One of These Days,
Breathe, Blue Lagoon) in `/secondary/hyst-data/audio/checkset/` AND the 12 s excerpt start per song (builder must not pick). When given:
tell agent 1 to render Part 3.
**Overseer checks before Kosta sees anything:** gates recomputed by own code from each CSV (clearance via m3f_report.fk_points, no-contact
can't be recomputed from CSV -> trust sim log + look, end-stop dwell, >8 Hz share, speed/acc p99+max vs make_arm.LIMITS, min motion);
discards per gate; sampling in draw order (settings.json draw index); spot-check 2 measurements; frames + contact sheet; Part 4 files =
round-1 files (hash). Then session on 8765, then report, merge body-mnet + body-mnettool into body, brief to planner, no verdict.
**23:50:** 29B TOOL READY d349e6e verified by overseer on an archive: test_motornet Session 5 / Measure 4 / Report 1 OK (10 tests; log said 13), test_dialstudy 5 OK; no external URL. Measurement defaults match prompt. Overseer error fixed: dominant freq now = summed hand-POSITION spectra (speed spectrum doubles back-and-forth) -> sent to agent 2 (fix + test, push, no merge; then align with MOTORNET_RULES (f)) and agent 1 (use in rules (f)). Not merged. Agent 1 had not pushed body-mnet at 23:47 (due ~00:10).
**~00:00 RULES REVIEW + FINDING (overseer, own code `scripts/body/overseer_mnet_check.py` on keys-decide):** MOTORNET_RULES (body-mnet afef526): N 200, tau 75 ms, rho 1.05, 4 control units x 80 neurons, c in [0.5,2] log-uniform, no global gain, Win iid N(0,1) (NOT /sqrt N), CAL_FRAC 1.0 (dev from 0.6), min-motion 0.05 m (dev from 0.10), spinal 3 Hz zeta 0.7, servo kp_scale 1 zeta 1.5. Sampling done: 10/10 kept (0 discards), S11 AND S12 FAIL motion (not shown). 12 clips rendered (P1 S01-S10, P2 ball S01/S02). Overseer measured P1 CSVs: speed and acc >0.9 lim share 0.00 all joints (builder's 'speed-limited' cause FALSE); every joint peak 1.66 Hz (= input) in all 10; activity PR 2.02-2.21 all; ranges ~same (base 5-6 deg, shoulder 1-4, elbow 10-14, wrist 10-18, roll ~43); hand extent 5-9 cm; hand v mean 0.30-0.42 m/s. => input-slaved network, gains change little. Session HELD. Agent 1 told HOLD + report diagnosis (Win u vs W r drive, target/spinal/realised ranges per joint, S11/S12 + autonomous PR/freq) under 'DIAGNOSIS FOR OVERSEER', no fixes. Next: planner brief PLANNER_BRIEF_MOTORNET_INPUT.md (Q: show as is / rescale input weights by a pre-registered numeric rule and resample / autonomous network for silent clips). 29B fixes (0de2ffd) verified: tests OK incl 0.8 Hz test; not merged.
**00:15:** agent 1 diagnosis (body-mnet d3961db): input drive std 0.864 vs recurrent 0.553 at gain 1; base yaw target 47.5 -> spring 41.7 -> command limiter 13.4 -> realised 5.4 (limiter DOES bite: overseer's realised-angle check missed it; corrected). Brief `docs/PLANNER_BRIEF_MOTORNET_INPUT.md` (body) SENT: Q1 input scale [rec b: Win so input std = 0.25 x recurrent at gain 1, resample], Q2 limiter [rec a, fallback spinal 1.5 Hz by rule], Q3 restore gate defaults if feasible, Q4 extremes keep 7.44.5d. Agent 1 on hold; agent 2 idle. WAITING planner -> record as 7.45 before any rerun.
**2026-11-13 ~00:25:** planner answers recorded as **BRAIN_SPEC 7.45** (body c8f5aad) + correction under 7.44.4. Q1 (b) Win scaled so input std = 0.25 x recurrent at gain 1 silent; Q2 (a) + rule: limiter cuts base/shoulder > half -> spinal 1.5 Hz; Q3 (b) defaults if gain-1 reaches 0.10 m at +-60 %; Q4 (a); NEW STOP 7.45.5: if ALL shown settings have every joint peaking at 100/60 Hz (within 1/12 Hz) AND PR < 3 -> no session, report, hold. Merge both branches only after re-run report. Re-run order SENT to agent 1 (notify_when_idle); old clips kept in clips_v1/. Overseer on CLIPS READY: recompute s ratio? (needs network; at least check PARAMS), limiter shares, joint peaks + PR (scripts/body/overseer_mnet_check.py, update its glob to new work/), gates, frames; apply 7.45.5; then session (Parts 1,2,4; tell Kosta Part 3 pending) or hold + brief.
**01:30 SESSION LIVE for Kosta (motor-network round, Parts 1,2,4; Part 3 pending audio).** 29A re-run CLIPS READY 265fe79 (body-mnet): s 0.04278 (ratio 0.2504), limiter shares 0.977-0.997 (1.5 Hz rule not triggered), gain-1 extent 0.182 m -> +-60 % and 0.10 m gate; seed 29011: 41 draws, 10 kept (discards motion 20, limits 11, contact 9, clearance 1, endstop 1); S11 fail motion, S12 fail contact+limits, not shown. Overseer recompute (`scripts/body/overseer_mnet_check2.py`): matches builder; joint peaks 0.25-0.50 Hz except elbow S01/S10 at 1.66; PR 1.97-2.64; 7.45.5 stop NOT triggered; min link z 0.08, min hand z 0.122; v/lim max <= 1.0, a/lim p99 <= 0.91; all clips 12.00 s 1280x720; clip CSVs == measured; Part 4 = round-1 files in place; contact sheets looked at (framing same, lamp P1, ball P2). Session: tool = archive of body-mnettool 0de2ffd at `/secondary/hyst-data/body/motornet_toy/tool_0de2ffd/`, session `/secondary/hyst-data/body/motornet_toy/session_2026-11-13/` (seed 29051, 16 items), unit `hyst-wo29-session` (cores 18-19), http://127.0.0.1:8765/; key/answers/order/labels 404; no external URL. AFTER Kosta: motornet_measure.py on clips manifest -> measurements.json; motornet_report.py --session ... --measurements ... -> docs/MOTORNET_REPORT.md (on body via a builder or overseer? report is a doc: overseer may commit it); verify table vs key+answers by hand; then merge body-mnet + body-mnettool into body (7.45.8 after report); stop unit; brief to planner, no verdict.
Note: main checkout `/secondary/Programming/Github/Hysteresis` is now on `body-dialtool` (not dance-checkpoint); not touched.

## STATE (2026-11-12 ~23:30)

**DIAL STUDY DONE; WAITING FOR THE PLANNER.** Kosta labelled all 22 clips (session_2026-11-12). body-dial merged into body (edf3c35).
Report `docs/DIALSTUDY_REPORT.md` (body b4efa26; overseer joined answers.csv with key/key.json independently: 22/22 match). Brief
`docs/PLANNER_BRIEF_DIALSTUDY_RESULTS.md` SENT (Q1 add "sad" button [rec a]; Q2 reshuffled consistency re-run [rec yes]; Q3 meaning/next =
Kosta's call; Q4 effector record-only). Facts: presets as intended with ball 1/5 (light); light 3/3 effectors; angry only with lamp; heavy
0/3; 5/5 dials shift the label from neutral "calm"; "sad" volunteered in 6 notes; angry/tense called "choppy". Session unit stopped; both
builders idle. NEXT: planner answers -> record as BRAIN_SPEC 7.44 on body before anything else.

## STATE (2026-11-12 19:45)

**NEW DIRECTION (Kosta via planner) = BRAIN_SPEC 7.42 (Stage 3 closed; no more proxy-objective movement training) + 7.43 (the piece:
a machine conveying emotion it does not understand; the hand-set dial study, WO28)**, body 665abdc. Read 7.43 in full: five dials, Sets
A-D, blind labelling tool, out-of-scope list, overseer notes 7.43.6 (Set D skipped: no audio in `/secondary/hyst-data/audio/checkset/`;
defaults for tense "long holds" and light "bouncy"; glitch gates = builder's rules file, overseer reviews).
**SENT 19:45 (user: "both agents free"), notify_when_idle both:**
- `docs/BUILDER_PROMPT_WO28A_DIAL_CLIPS.md` -> agent 1 [19f533]: branch body-dial, cores 6-11; rules file `docs/DIALSTUDY_RULES.md` first
  (REVIEW IT: gates, dial ranges, not v47), Sets A (11) + B (5) to `/secondary/hyst-data/body/dialstudy/clips/` + manifest.json; Set C waits
  for overseer word after 28B's effector merge; dial notes `docs/DIALSTUDY_DIALS.md`.
- `docs/BUILDER_PROMPT_WO28B_DIAL_TOOL.md` -> agent 2 [778c35]: branch body-dialtool, cores 12-17; `--implement lamp|gripper` in
  ensemble_preview (visual only; v47 Off byte-identical), then blind tool (`dialstudy_session.py`, 127.0.0.1, key in session/key/) and
  `dialstudy_report.py` (no verdict). "EFFECTOR READY <commit>" in its night log -> overseer verifies (hash, tests, frames), merges into
  body, tells agent 1 to render Set C.
**Overseer checks before Kosta sees anything:** every clip's gates recomputed from its CSV (clearance via m3f_report.fk_points, end-stop
dwell, jitter), frames looked at, same framing, 12 s; tool: key not served, no external URL. Then start the session for Kosta (< 20 min);
report from the CSV, no verdict. Asked Kosta (pending): the "long holds"/"bouncy" defaults; Set D audio files.
**22:15:** 28B EFFECTOR READY f936827 VERIFIED (overseer: cargo test hyst-compile+hyst-previz 103 OK on an archive of f936827, cores
12-17; tool tests 5 OK; no external URL; lamp/gripper frames read; new Mirror fields serde-skipped at default so ball JSON unchanged; ball
page file hash changes by template JS only) -> body fast-forwarded to ef0081c, keys-decide merged. 28A rules (body-dial 59e909d) reviewed
and ACCEPTED (seed 28011, 1 move / 2 beats, gates incl. no contact at any substep). Told agent 1: Set C go; neutral identical on-screen label
(page prints "K5 policy"); roundness 'angular' = joint-linear with stops, note it + straightness. Agent 2 done (idle). Next: agent 1 says
A-C ready -> overseer recomputes gates from CSVs, frames -> start the session for Kosta (dialstudy_session.py ... --serve, port 8765).
**22:25: SESSION LIVE for Kosta.** 28A done (body-dial edf3c35, NOT merged yet): 22 clips A 11 / B 5 / C 6 in
`/secondary/hyst-data/body/dialstudy/clips/` + manifest. Overseer gate recompute (job tmp gate_check.py, own code): all 22 pass; 12.00 s
1280x720; min link z 0.070 m, min hand z 0.144 m; end-stop dwell 0; >8 Hz share 0.0000; max speed <= 0.99 lim, max acc <= 0.99 lim.
Contact sheets looked at: same framing, neutral label "1 arm · ·". Session `/secondary/hyst-data/body/dialstudy/session_2026-11-12/`
(seeded order, coded names; key/ order.json answers.csv all 404 over HTTP; /api/state leaks no intent), unit `hyst-wo28-session`,
http://127.0.0.1:8765/. AFTER Kosta finishes: `python3 -I scripts/body/dialstudy_report.py --session <that dir>` -> docs/DIALSTUDY_REPORT.md
(on body; verify table vs key + answers.csv by hand), merge body-dial into body, stop the unit, send the report to Kosta; no verdict. Then
the planner brief with the report.

## STATE (2026-11-12 19:20)

**STAGE 3 STOPPED ON THE USER'S VERDICT. ALL WORK STOPPED.** User on the round-400 clip (~19:13): "Again same issue, it's the same tight
move all the time with variations. Stop all work and make handoff explaining state so far to planner". Overseer stopped
`hyst-wo26b-run-r3` (clean, round 511/977, 10.94 h compute, ckpt.pkl resumable, best.pkl = r400) and `hyst-wo27-watcher-s3`. Nothing
runs; no builder assigned. Brief **`docs/PLANNER_BRIEF_STAGE3_VERDICT.md`** written, pushed, sent to the user (Q1 close Stage 3 [rec (a) no
bar eval]; Q2 next direction [rec report-only energy/workspace diagnosis on r400, then the authored path]; Q3 record verdict as 7.42).
Key numbers (Instant Crush whole song, overseer): hand p5-p95 extent x/y S3 36/27 cm vs pass2 59/58 vs v47 84/83; cells/60 s 78 vs 277 vs
474; base sd 12 vs 99 deg; hand speed p50 0.19 vs 0.37 m/s; shoulder sd 8.8 vs 3.0. WAITING: the planner's answers (pasted by the user) ->
record as BRAIN_SPEC 7.42 on body before anything else. The block below is history.

## STATE (2026-11-12 09:30)

**Stage 3 run was stopped twice by a system power-off, then resumed.** `hyst-wo26b-run-r1` ran 22:16-23:25 on 2026-11-09 and stopped at
round 54/977 (1.13 h compute, no validation yet) when the machine powered off (journal: logind "The system will power off now!"; cause not
checked — no critical-battery line found). `hyst-wo26b-run-r2` was started 2026-11-10 20:17 (not by the overseer), waited on battery, and the
machine powered off at 20:20. Machine booted 2026-11-12 09:23 on mains (battery 93 %). The overseer resumed it at 09:28 as
**`hyst-wo26b-run-r3`** (same script `s3t_run.sh` in body-m3f, code identical to body a9fd858, 14 GB cap, cores 6-11): log says "resumed at
round 54 of 977, 1.13 h of compute spent". Remaining 923 rounds x 73 s + 5 validations x 200 s = ~19.0 h -> end ~04:30 2026-11-13 if on
mains throughout. Validations: round 200 ~12:30, 400 ~16:35, 600 ~20:40, 800 ~00:45, 977 ~04:25. No builders online (ListAgents empty).
Everything else in the block below still holds.
**09:40 update:** rounds now ~82 s (timed round 73 s; Kabl sessions also running on the machine, cause not checked) -> round 200 ~12:50,
400 ~17:30, end ~07:00 2026-11-13. User: charger in, agents free. WO27 prompt amended (keys-decide 0462f43: unit r3, new times, follow
`hyst-wo26b-run-*`) and SENT 09:40 to agent 1 [b15601] (notify_when_idle). Agent 2 [c56de4] idle, nothing assigned. Check body-s3r's
first push (rules file) by ~10:15 and read it; the watcher must be armed before round 200.
**09:50:** WO27 watcher ARMED 09:42, unit `hyst-wo27-watcher-s3` (affinity 12-17 and MemoryMax 6G checked by overseer), out
`/secondary/hyst-data/body/s3/run_report/` (summary.txt, <R>/hinges.json, watch.log). body-s3r 8d43f66 (rules 99a1539, new files only),
read by overseer: matches the prompt (thresholds, 16 val windows, seed 4242, argmax, copies first; Instant Crush slow lanes via
`s3_slow.load_norm` corpus PCA/normalisation, no refit). Builder notes: own worktree `.claude/worktrees/wo27-s3r` (harness forced);
floor = check-csv margin, plus `floor_trained` (raised-plane, trainer's hinge) and `lim_any_bend` reported alongside (FOR USER/planner).
Timed-round test shares (untrained policy, information only): hand_v 4.03 %, jolt 0.17 %, acc 1.87 %, floor 0 %, floor_trained 17 %,
lim 1.78 %, energy 85.5 %, jerk 23.7 %. Agent 1 next: render-path test, then waits for round 400. Merge body-s3r after the clip is verified.
**09:43 (clock check: earlier "09:50" note times ran ~8 min ahead):** Kabl sessions' cargo/clippy/rustc builds (nice 5, unpinned) run
on all cores incl. 6-11; per-round seconds r55-60 76-98, r61 264 (r54 231 = post-resume compile). ETA depends on Kabl load: at 82 s ->
end ~07:00 2026-11-13; at 100 s -> ~11:30. Told the user; overseer does not touch Kabl.
**09:50:** agent 1 idle after the clip-path test (body-s3r e4e5c68): 10 s test clip 720p h264+aac 15 MB, deleted; `shoulder_cells` repeats
s0_measure's hand/cells/unique definition (sklearn absent in body env) — overseer compared: identical. The watcher renders the r400 clip
itself. Agent 1 asked to be woken ~17:30: when the round-400 validation line appears, message agent 1 to verify and report the clip;
overseer then checks the clip (size, duration, audio window 60-120 s, frames) and recomputes shoulder sd + cells from its CSV, then sends
it to the user.
**09:52 RISK:** rounds 62-64 took 134/151/214 s under Kabl build load. The run stops at the 30 h compute box (k5_train.py:345,
`clock.spent >= BOX_H*3600`, BOX_H 30 via k5p2_train; the clock is wall time while running). Spent 1.13 h at resume. At ~150 s/round the
box ends the run near round ~750 (validations 200/400/600 only, no 800/977); at 73 s it finishes. Told the user: pause Kabl builds or pin
them to cores 0-5/12-19 (12-17 is WO27's watcher). User's call; overseer does not touch Kabl. (Kabl load eased by ~10:00; rounds back
to ~72 s.)
**12:52 ROUND 200 VALIDATION** (train.log 12309 s, compute 4.55 h): ext a 0.442 [0.407, 0.477], int a 0.431, b 37.0, programs 1,
e'1 2.28, e'2 0; best.pkl = r200. Side-car (run_report/200/hinges.json, summary.txt): active shares hand_v/jolt/acc/floor/lim/jerk all
0.00 %, energy 15.62 % of blocks (>= 0.3747 J); mu energy 11.44, jerk 165.3, others ~1.0-1.08; muD fast 12.07 slow 18.22 (rising);
D_fast 0.459, D_slow 0.155 (safeguard 0.7 not reached; 7.40: safeguard, not a bar). Not overseer-recomputed yet (side-car numbers are the
builder's code). Next: round 400 ~17:00 + clip.
**15:27 (saved before a usage limit):** round 325/977, ~73 s/round, mains on. Round 400 ~17:00 (WO27 watcher renders the clip itself to
run_report/400/instant-crush-r400-60s.mp4); end ~05:30 2026-11-13. On resume: tail train.log + run_report/summary.txt; message agent 1
[b15601] to verify/report the clip; overseer checks the clip (size, duration, audio 60-120 s, frames) and recomputes shoulder sd + cells,
then sends to the user. Re-arm a Monitor on train.log ("validation at|Traceback|Error|nan|Killed|waiting for mains|box") + unit end + power. Lesson: a wait loop must not grep "fail" in logs that print "Failed to import warp".
**19:15 (new overseer session after a clear):** round 506/977, 72 s/round, mains on. ROUND 400 VALIDATION (17:00, compute 8.69 h): ext a
0.572 (best; r200 0.442); side-car shares energy 7.31 %, jerk 0.33 %, others 0; muD fast 19.24 slow 32.49; D_fast 0.509 D_slow 0.326.
Round-400 clip CHECKED by overseer (agent 1 [b15601] not in ListAgents; not messaged): 60.0 s, 1280x720 h264, 1800 frames, AAC 60.0 s,
28.3 MB, window 60-120 s; frame at 30 s shows the arm. Recomputed from the CSVs (job tmp clip_check.py, m3f_report.fk_points, 5 cm floor
cells): 60-120 s Stage 3 shoulder sd 5.42 deg, 67 cells; pass2 1.94 deg, 279 cells (match builder). Context: pass2 base_yaw sd 95.6 deg vs
Stage 3 9.35 deg in that window (pass2's cells come from base rotation); hand speed p50 0.19 vs 0.40 m/s. 0-120 s: S3 sd 9.42 / 155 cells,
pass2 4.18 / 375. Whole song: S3 8.78 / 203, pass2 3.03 / 441. Clip SENT to user 19:15 with the two numbers; waiting for the user's eye
(may stop the run, 7.41). Round 600 ~21:10, 800 ~01:15, end ~05:30 2026-11-13. Monitor re-armed 19:15.
**19:20:** body-s3r MERGED (new files only, 7 files): body fast-forwarded to e4e5c68, keys-decide 19bcc54. test_s3_sidecar rerun by
overseer at e4e5c68: OK. Failed units hyst-wo27-test-unit-a (09:37, floor sign test) and hyst-wo27-cliptest-a (09:46) are superseded
first attempts (test_unit_b 09:40 OK; clip test passed ~09:50); ignore. No Hysteresis builder online (all offline in ListAgents); nothing
to nudge. After the run: s3_eval.py (see "After the run" below) needs a builder or the user's word.

## CURRENT STATE (2026-11-09 ~22:40, saved before a usage limit)

**Rules of record:** BRAIN_SPEC on body, latest **7.39-7.41** (7.39 Stage 3 design + bars (a)-(f); 7.39.6/7.40.1 rising D multiplier;
7.40 build defaults, thresholds from v47; 7.41 launch rulings: energy 0.375 kept, report-only side-car items, NO mid-run changes).
Build rules: `docs/STAGE3_RULES_DATA_EVAL.md` (26A), `docs/STAGE3_RULES_TRAIN.md` (26B, incl. the dated metres entry).

**RUNNING: Stage 3 run, unit `hyst-wo26b-run-r1`** since 2026-11-09 22:16 (agent 2 launched; script `scripts/body/s3t_run.sh` in agent 2's
worktree body-m3f; code = body a9fd858; 6 threads cores 6-11, 14 GB cap; log `/secondary/hyst-data/body/s3/run/train.log`; ckpt every round,
resumable by rerunning the same script under a fresh unit name). Projected 20.2 h (73.4 s/round x 977 + 5 validations x 200 s) -> end ~18:30
2026-11-10 on mains. Validations at rounds 200 (~02:30), 400 (~06:30), 600, 800, 977. On restart: check `systemctl --user status
hyst-wo26b-run-r1`, tail train.log, power; re-arm a Monitor on the log (validation/Traceback/nan lines + unit end + power).

**Agents:** agent 1 [9ae40e] idle (did WO26A); agent 2 [59fba5] idle (restarted session; did the WO26B timed round + launch). Refs change on
restart: ListAgents.

**WAITING on the user:** "send" for **WO27** (`docs/BUILDER_PROMPT_WO27_STAGE3_SIDECAR.md`, body e96443d) -> agent 1: side-car watcher on
cores 12-17 reading copies of ckpt.pkl/best.pkl: per-hinge active share + multipliers at each validation (s3/run_report/summary.txt), and at
round 400 a 60 s Instant Crush clip (60-120 s, one-arm camera) + shoulder sd + cells (and pass2's on the same 60 s) -> overseer checks, sends
to user; user may stop the run early on it. If round 200 passes before WO27 is armed, its hinge report can still be computed later from a
copy of that round's ckpt only if saved — the watcher copies ckpt at the validation; a missed round is reported as missed.

**After the run:** `s3_eval.py --policy /secondary/hyst-data/body/s3/run/best.pkl --out /secondary/hyst-data/body/s3/eval_run/ --ref-bars
/secondary/hyst-data/body/s3/eval_pass2/bars.json` (agent 1 or 2, cores 6-11 once the run has ended); overseer recomputes bars (b)-(e) from the
rollouts (as done for pass2: shoulder sd col 1, 5 cm cells first 120 s via m3f_report.fk_points), checks (a)/(f); then three-panel videos
(v47 | pass2 | Stage 3) on the three danced songs for the user's eye (7.39.4); planner brief with results. Two tries; round 2 changes only what
the failing bar names (energy threshold may change only if (e) fails, 7.41.1).

**Pass2 reference bars** (s3/eval_pass2/bars.json, verified): (a) 0.943 PASS; (b) 0.468 on 54 pairs; (c) 0.48; (d) 385 -> Stage 3 needs >= 577.5;
(e) 0 % (median 3.76 deg); (f) pass.

**Lessons (2026-11-09 evening):** builder sessions can restart under a new ref mid-task (agent 2 [4cd51a] -> [59fba5]): send standalone
messages; cores 12-19 are E-cores (smoke timings there overstate per-round cost ~1.3x+ vs P-cores 6-11); builders ran long smoke tests
in their shell (31 min) — ask for detached units; my own test timeouts must exceed smoke tests (>= 35 min) or run only fast classes;
review rules files the moment they are pushed (caught the observer-units deviation before code).

## CURRENT STATE (2026-11-09 ~19:20) — read this first, then the dated notes below

**Rules of record:** `docs/BRAIN_SPEC.md` on body, latest **7.37-7.38** (7.37 Stage 1 results rulings: fresh-seed rerun, pre-registered
precondition, cap probe; 7.38 Stage 1 closed without verdict, arm ii forward, D-hinge toy check, thread-count rule). Toy rules
`docs/STAGE1_RULES.md` (sections 11 = WO22, 12 = WO24 D hinge). Decisions go to the planner as briefs.

**Nothing is running.** Both builders idle: agent 1 [9ae40e] (did WO23), agent 2 [4cd51a] (did WO22, WO24). Refs change on restart: use
ListAgents. All builder branches verified and merged: body = caca60d (body-s1r, body-s1d, body-acc), keys-decide merged.

**2026-11-09 ~18:45 — CURRENT:** WO25 DONE (agent 2, body-s1f e2f7761, unit hyst-wo25-falling-mu success 2386 s), verified by overseer
(result.json recomputed, matches report; test_s1f/s1d/s1_toy OK). Held-out D rising 0.782/0.651, falling 0.778/0.665; MMD mean rising 0.240,
falling 0.295 -> by rule **RISING multiplier** = BRAIN_SPEC 7.39.6 (body f0ea2f9). Rising also misses held-out 0.7 on seed 7; held-in D_est
optimistic ~0.13. body-s1f (325978b, night log) MERGED: body 111dcb1, keys-decide 7fc37a5. Agent 2 idle.
**2026-11-09 ~19:20:** planner answered the gaps brief = **BRAIN_SPEC 7.40** (body e3044b0): rising confirmed; D >= 0.7 = training safeguard,
not a bar; Q1 (b) energy thr = v47 mean block energy replayed on v2f, jerk thr = 1.25x v47 (fallback pass2 realised x 1.5); Q2 switch 0.01
kept; Q3 one D hinge per stream, D_est on 16 fixed VALIDATION windows; Q4 overseer defaults accepted; Q5 build now, timed round after 7.40
(recorded), ask if > 30 h.
**Prompts SENT 2026-11-09 ~19:25 (user "do it"; notify_when_idle both; check first pushes of body-s3d / body-s3t by ~19:55):**
- `docs/BUILDER_PROMPT_WO26A_STAGE3_DATA_EVAL.md` -> agent 1 [9ae40e]: branch body-s3d, L4 slow lanes (13 cols) + tempo_rms.json +
  thresholds.json (v47 replay on v2f) + `s3_eval.py` bars (a)-(f) + pass2 reference bars; data /secondary/hyst-data/body/s3/, cores 6-11, 12 GB.
- `docs/BUILDER_PROMPT_WO26B_STAGE3_TRAINER.md` -> agent 2 [4cd51a]: branch body-s3t, `s3_train.py` (ingredients from s1_toy on
  k5p2/m3f), tests, smoke on cores 12-17; WAITS; timed round only on overseer's word ("timed round") after 26A merged; never launches the run.
**~19:40:** both rules files pushed first (s3d 609afc6, s3t 5bbae46), read by overseer: match 7.39/7.40 except (1) 26B external observer kept
pass2 joint-angle descriptors -> CORRECTED to 7.39.4 metres (causal 1.5 s window of elbow/wrist/hand FK positions at 10 Hz, G = 4); overseer's own
Q4 text wrongly said pass2's external observer reads positions (it reads descriptors) — tell the planner in the next brief; (2) 26A Burger
"low-band flux" used B7 L3 power -> changed to audio 50-200 Hz spectral flux (report-only). 26B FOR USER for the planner (information): a round =
2 anchors + 14 matched neighbours, so 1,954 anchors over the run, neighbours may repeat.
**~20:30:** 26A thresholds verified (energy 0.3747, jerk 4.748e6 = 1.25 x 3.799e6, v47 arm 0 replay on v2f, 1,784 blocks; recomputed
block-weighted means OK). 26A data unit hyst-wo26a-data2 (after a b2-import crash fixed in bb642e9) running, L4 raw ~20:45, then PCA,
tempo/RMS; hyst-wo26a-eval2 waits for it (pass2 reference bars). 26B (body-s3t 70a9acf, new files only): overseer reran 8 fast tests OK;
smoke unit hyst-wo26b-smoke OK (resume bit-identical, no NaN, rising multipliers, validation writes best.pkl) after a first smoke failed on
a stub gap. Smoke timing 95 s/round for 4 windows on E-cores 12-17 -> naive 16-window projection ~380 s x 977 = ~100 h (!); timed round
on P-cores 6-11 decides; > 30 h -> ask (brief).
**~21:30:** WO26A DONE + verified (tests 8 OK rerun; slow lanes spot-check: blocks match k5, train z ~0/1; tempo_rms 3,176, check bpm = s0;
8 train songs bpm < 40 (6 = 0) left as is; pass2 reference bars (d) 385 cells/285 songs and (e) median 3.76 deg, 0 % >= 8 recomputed from s0/pass2
rollouts: match). Pass2 reference: (a) 0.943 PASS, (b) 46.8 % [40.7, 52.8] on 54 pairs (interleaved needs songs >= 210 s), (c) 0.321/0.663 = 0.48
(interleaved within is larger than Stage 0 half split -> not the spec's 0.69; for the planner), (d) ref 385 -> Stage 3 needs >= 577.5, (e) 0 %,
(f) pass; pass2 used ONE program for all blocks. MERGED body-s3d + body-s3t into body a9fd858, keys-decide 668b996. Agent 2 restarted as
[59fba5] (fresh session; sent a standalone timed-round message); TIMED ROUND RUNNING: unit hyst-wo26b-timed-r1 (2 rounds + 1 validation, cores
6-11), out /secondary/hyst-data/body/s3/train_timed/timed_round.json. > 30 h -> planner brief (with the (c) definition note, 54 pairs, bpm-0
songs, the overseer's Q4 observer error, 2-anchors-per-round design); <= 30 h -> confirm with the user, then launch.
**~21:10: TIMED ROUND DONE** (hyst-wo26b-timed-r1, /secondary/hyst-data/body/s3/train_timed/): round 73.4 s (one post-compile round), validation
200 s, 977 rounds + 5 validations -> **20.2 h** (overseer arithmetic matches), within the 30 h box. Round 1: g_jerk 90 (start policy jerk ~4.6e8 vs
threshold 4.75e6; pass2 untrained 4.56e8 -> trained r600 5.8e5, so reachable), mu_jerk 108 after 1 round; g_energy 2.5 (pass2 trained 0.363
J/block vs threshold 0.375: Stage 3 has ~pass2's energy budget). D_fast/D_slow ~0 at start. val2 ext a 0.242. User: "send to planner or start work" -> overseer
LAUNCH sent to agent 2 [59fba5] (~21:15; out /secondary/hyst-data/body/s3/run/, cores 6-11, 14 GB). Info brief
`docs/PLANNER_BRIEF_STAGE3_LAUNCH.md` (body b467341) SENT to user (8 facts incl. overseer's Q4 observer error; optional Q1 energy threshold).
RUNNING: unit hyst-wo26b-run-r1 since 22:16 (s3t_run.sh, code = body a9fd858, log /secondary/hyst-data/body/s3/run/train.log); ETA ~18:30 tomorrow if on mains.
**7.41 recorded (body 846ebdd):** energy 0.375 kept (round-2 only if (e) fails); facts 1-8 recorded; report-only: hinge active share +
multiplier at each validation, round-400 60 s render of best.pkl on one danced song + shoulder sd + cells -> user (may stop the run early); no
mid-run changes. Prompt `docs/BUILDER_PROMPT_WO27_STAGE3_SIDECAR.md` (agent 1, side-car watcher on cores 12-17, out s3/run_report/) written,
send on the user's word.
NEXT: watch (Monitor, re-arm 30 min); report each validation (every 200 rounds, ~4 h); after the run: s3_eval.py
--policy best.pkl --ref-bars s3/eval_pass2/bars.json, verify bars, videos, brief.
**NEXT:** verify 26A (recompute PCA var, thresholds from replay, pass2 reference bars vs 2AFC ~49 % / ratio ~0.69 / shoulder 3-4 deg) and 26B
(bit-identity, Lipschitz test, design file vs 7.39.4/7.40); merge both into body; say "timed round" to agent 2; projection <= 30 h -> per 7.39.4
the run may launch (still confirm with the user); > 30 h -> ask.

**Today's results (all verified by overseer, numbers in the briefs):**
- WO22 Stage 1 rerun seeds 2/3: no verdict (arm 0 ratio 0.93/4.84, arm i 4.82/1.21). Brief `PLANNER_BRIEF_STAGE1_RERUN.md` -> 7.38.
- WO24 D hinge seeds 4/5: iii+D D 0.790/0.769, cells 47 vs ii 21-24; plain iii also >= 0.7 here (fails 3/6 seeds overall); mu_D only rises
  (ends 8.45/10.21), MMD lowest. Data `/secondary/hyst-data/body/s1d/`.
- WO23 cap probe (M3f toy seed 0, 6 thr): acc within servo limits (p99 <= 0.46x); speed max 1.006x (A1) / 1.001x (AS); raising ACC_SHARE
  moves joints acc-cap -> speed-cap, shoulder 99.6 % on acc cap always; JS ratio 0.78-0.81 everywhere; e'2 A1 .033 / AS .048 (toy limit
  .011). Data `/secondary/hyst-data/body/acc/` (report.txt). 7.37.3 hypothesis not supported.

**Session lessons (2026-11-09 day):**
- M3f training numbers depend on thread count with the same code (now rule 7.38.4): retrain baselines at the probe's thread count.
- Monitor pipelines: `cut` after `grep --line-buffered` buffers -> silent watcher; use `awk '{...; fflush()}'`. watch_unit.sh filters
  can miss epoch lines; a direct `tail -F | grep --line-buffered | awk fflush` + unit-state loop works.
- Report scripts that read old runs must default missing new options (WO23 report crashed on rerun4's args).
- A single-sample max of realised acceleration depends on the difference method (central vs plain); report p99 alongside.
- Builders go idle with units running; nudge them when the unit ends (they did their report steps only when asked).

**Key verified results of the 2026-11-08/09 night session:** pass2 (K5-pass2, best r600) passed its numeric bar (7.33) but the user rejected the videos;
Stage 0: pass2 machine 2AFC 49.1 % (chance) over 128 tempo-matched held-out pairs, JS between 0.30 < half 0.46; v47 held-out impossible
(auto beat grid fails), v47 3 danced songs = weak ref; 0.741 m/s = start-up transient at 2.74 s, not a bound (after 8 s peak 0.680 sd 0.036).

**Overseer scripts (job tmp, NOT durable):** verify_p2.py (pass2 paired bootstrap), ep_csv.py / shape*.py (posture, e'), s0_fk.py +
s0_check.py (independent Stage 0 2AFC/JS), all simple; rewrite if needed.

**Session lessons (2026-11-08/09):**
- "Distinct postures >= 0.5 % dwell" runs backwards for wide motion; use occupied cells at equal duration (7.36.2).
- A numeric legibility bar can pass with one shape modulated in timing; the user's eye is the real test (7.33.7).
- The B7 `omega` lane is the L3 phase rate, not the beat tempo; use librosa for tempo.
- Glob carefully when counting result files (smoke-run result.json files counted as runs once).
- Run scripts/body test modules in separate processes (16 errors only when run together).
- Builders often go idle with a unit running; watch units yourself.

**2026-11-09 ~02:50 — CURRENT:** Stage 1 DONE (agent 2, body-s1 5999c31, 12 runs, 51 min), recomputed by overseer from run_*/result.json
(match). Collapse precondition NOT MET (JS ok, occupied cells fail: untrained toy arm nearly still, 23-27 cells) -> no verdict, as ruled.
Informational: arms 0/i reproduce pass2's between~half JS signature; arm ii JS 0.77 (3.7x i) with D 0.73/0.77; iii doubles cells;
iv D < 0.7. Brief `docs/PLANNER_BRIEF_STAGE1_RESULTS.md` SENT (Q1 pre-register new precondition = between/half JS ratio <= 1.5, rerun fresh
seeds 2/3; Q2 ingredients after rerun; Q3 report-only ACC_SHARE probe; Q4 record partial-collapse caveat). body-s1 not merged yet
(new files only). Both agents idle.

**2026-11-09 ~02:10:** WO21 ceiling DONE (agent 1, body-s0b b813796, merged into body), verified (overseer recomputed from Stage 0 hand
positions): 0.741 m/s is a START-UP transient at t = 2.74 s from the fixed start pose (peak in first 8 s on 331/357 songs, 0.7407 sd 0.0004);
after 8 s peak 0.680 sd 0.036 (0.554-0.806). Amp cap x1.5 / freq x1.5: unchanged; c = 0.35 lowers it -> (a)(b)(c) ruled out. Steady-dance
limiter (builder, not recomputed): the CPG's own caps in cpg.py: pitch joints on the acceleration cap ACC_SHARE 0.25 for 99.8-99.9 % of
steps; base/roll on the 0.8 V speed cap 96/98 %; analytic max hand speed ~1.9-2.0 m/s. Goes into the Stage 1 results brief (Stage 3 design).
Stage 1 running (hyst-wo20-stage1-a, ETA ~02:50-03:20).

**2026-11-09 ~02:00 — CURRENT:** Planner ruled Stage 0 = BRAIN_SPEC 7.36 (body 4c4ebcd): Stage 0 closed (2AFC at chance confirms diagnosis;
v47 3 songs weak ref); occupied cells (any dwell, equal durations) + entropy replace dwell postures everywhere; Stage 3 2AFC interleaved
clips with 30 s gap; RUN Stage 1 now; report-only 0.741 ceiling diagnosis. body-s0 MERGED into body (8ef8d5a), keys-decide 3224f55.
SENT: agent 2 [4cd51a] amend rules (occupied cells) then run all 12 Stage 1 runs (6 thr cores 6-11, one unit); agent 1 [9ae40e] WO21
ceiling diagnosis (branch body-s0b, 3 thr cores 12-14, out /secondary/hyst-data/body/s0/ceiling/). notify_when_idle both.
NEXT: verify Stage 1 amendment pushed before launch; watch the unit; verify results (collapse precondition first); brief planner.

**2026-11-09 ~01:40:** Stage 0 DONE (agent 1, body-s0), VERIFIED by overseer (independent FK + sklearn, job tmp s0_check.py):
pass2 2AFC 49.1 % [45.4, 52.7] (overseer 48.4 %), pairs valid (128, tempo <= 5, different artists), JS 0.298 vs half 0.463, peak 0.742 sd
0.007, shoulder 3.87. Expectation met (<= 60 %). v47 held-out NOT feasible (auto beat grid fails gate 0/10) -> 3 danced songs only.
FINDING: "distinct postures >= 0.5 % dwell" runs backwards (v47 7 vs pass2 60; occupied cells v47 1,507 vs 412) -> affects 7.35.2 Stage 1
precondition. Brief `docs/PLANNER_BRIEF_STAGE0_RESULTS.md` SENT (Q1 accept with v47 weak ref, Q2 occupied cells in precondition,
Q3 interleaved 2AFC split for Stage 3, Q4 run Stage 1 after Q2). Agent 2 Stage 1 ready (body-s1 5ba7343, 17 tests rerun OK by overseer,
arm (i) surviving sd 0.20 vs 0.99). Stage 1 run waits for Q2 ruling + user's word. body-s0 not merged yet (new files only).

**2026-11-09 ~01:00:** Stage 0 pass2 rollouts DONE (357 songs, 25 min, hyst-wo19-roll1); agent 1 measuring next. Tempo: omega-BPM
disagreed with librosa on 20/20 -> librosa tempo for all (prompt's fallback; note: omega is not the beat tempo). Stage 1 toy built
(agent 2, body-s1 8700c2b, 13 tests). Planner ruled on it = BRAIN_SPEC 7.35 (body 665eb4d): 5 s z-score; NEW arm (0) = arm (i) target with
pass2 soft costs; collapse precondition ((0) or (i) JS and postures <= 1/3 untrained) else stop; MMD secondary; amendments recorded;
logistic-regression test vs scipy (scipy IS in the body env). Rulings NOT yet sent to agent 2 (waiting for the user's word). Stage 1 run
still waits for the Stage 0 report.

**2026-11-09 ~00:15:** NEW DIRECTION = BRAIN_SPEC 7.34 (user + planner; research doc `docs/RESEARCH_2026-11-08.md` reference
only). Diagnosis (untested): one shape because the target was low-dim/fast, 30 s within-song z-scoring hid song differences, costs priced
variety. Stage 0 = analysis only (pass2 best.pkl r600 + v47 one arm): between-song JS (5 cm ball grid), postures >= 0.5 % dwell, shoulder sd,
peak hand speed vs bound, program entropy, machine 2AFC on tempo-matched held-out pairs; expect pass2 <= 60 %, v47 clearly higher; pass2
> 60 % -> stop/report. Overseer operationalisation committed at the end of 7.34 (planner may amend before the run). Stage 1 = toy 2-link arm,
arms (i)-(iv) cumulative, hinges + dual multipliers; pass (iv) JS >= 3x (i) with decoding >= 0.7. Order: report after Stage 0, then Stage 1.
Prompts on body a4b4e77: `docs/BUILDER_PROMPT_WO19_STAGE0.md` (agent 1, branch body-s0, data /secondary/hyst-data/body/s0/, 6 thr/12 GB),
`docs/BUILDER_PROMPT_WO20_STAGE1_TOY.md` (agent 2, branch body-s1, data .../s1/, builds + STAGE1_RULES.md, NO run until overseer says
"run Stage 1" after the Stage 0 report). SENT 2026-11-09 ~00:25 (user cleared both agents): WO19 -> agent 1 [9ae40e], WO20 -> agent 2 [4cd51a], notify_when_idle both. Check first pushes of body-s0 / body-s1 within 30 min. Hardware memory updated (12 V STS3215).

**2026-11-08 ~23:40:** Planner ruled on pass2 = BRAIN_SPEC 7.33 (pass recorded numerically; inner-rhythm wording only with
"about 3 %" qualifier; BG single program -> "present", never choosing; 0.741 m/s ceiling recorded; late-val-drop diagnosis required before
any future long run). USER VERDICT on the three-panel videos = 7.33.7: pass2 "same exact shape of movement, just repeated at different
speeds ... not conveying anything". Overseer measurement: pass2 214-239 distinct 5-deg bend postures vs v47 1,734-2,321; shoulder sd ~3 deg
vs 14-17; shape identical across songs. Brief `docs/PLANNER_BRIEF_PASS2_VERDICT.md` SENT (Q1 toy diagnosis first, Q2 variety gate
incl. song-dependence, Q3 program diversity after diagnosis, Q4 keep numeric pass marked rejected by eye, Q5 demo fallback = user's choice).
WAITING: planner answers. All three three-panel videos checked and sent. body-k5p2 (bed52b9, new files only; tests OK when each module runs
in its own process — together in one process 16 errors) MERGED: body e6cc888, keys-decide fe50466. Nothing running; agents 1 and 2 idle.
Agent 1 reported WO18 done (matches overseer numbers; its "early stop rule fired" is wrong: run completed).
Lesson: run scripts/body test modules in separate processes (cross-module import side effects).

**2026-11-08 ~23:10:** WO18 check DONE; pass2 bar MET (builder), VERIFIED by overseer: paired per-song bootstraps recomputed (job tmp
verify_p2.py logic: per-song mean of a_gaps over windows.json check songs, 10k resamples) match to 3 dp: ext 0.943 [0.911, 0.977], int 0.958;
vs untrained +0.922/+0.926; vs kappa0 +0.025 [0.021, 0.030] / +0.019 [0.014, 0.023]. check-csv rerun by overseer: accepted x3. e' from CSVs
(m3f_report.hand_metrics) match: e'1 2.13/2.14/2.11, e'2 0 all; contact 0; end stops 0. FINDINGS: ONE program (MI 0); hand speed max
0.741 m/s in all songs (ceiling?); val dropped after r600. Instant Crush three-panel checked (frames 100/250 s, 339.82 s) and SENT to user.
Brief `docs/PLANNER_BRIEF_PASS2_RESULTS.md` written (Q1-Q6). FY/PR videos rendering (chain hyst-wo18-chain2). NEXT: check + send FY/PR
three-panels; send brief; verify body-k5p2 diff (new files only?) and merge into body + keys-decide; user verdict on videos.

**2026-11-08 21:17:** PASS2 TRAINING DONE (hyst-wo14-a2 success, 977/977, 17.50 h compute, 'pass complete'). Validation ext/int:
r200 0.862/0.873, r400 0.895/0.921, r600 0.913/0.931 (BEST, best.pkl 13:47), r800 0.875/0.869, r977 0.784/0.880. Chain hyst-wo18-chain2
started check -> songs -> summary -> render on best.pkl (r600); out /secondary/hyst-data/body/k5p2/check/, video .../video/, log .../chain.log.
NEXT: when chain ends, verify (per-song paired bootstraps from eval JSON, check-csv per song, (e'1)/(e'2) per song vs
docs/hf_v47_eprime_reference.json, kappa0 control for 7.31.3 wording), check media, send 720p three-panels, write PLANNER_BRIEF_PASS2_RESULTS.md.
Note for the brief: validation peaked at r600 and fell at r800/r977 (ext 0.784 at the end).

**2026-11-08 ~16:05 (overseer restarted 14:55):** agent 1 finished WO18 code (body-k5p2 fd54a20; EndToEnd test OK, 866 s, log
`/secondary/hyst-data/body/k5p2/evaltest2.log`) and LAUNCHED the chain as unit `hyst-wo18-chain2` (`scripts/body/k5p2_chain.sh`, 14 GB cap,
log `/secondary/hyst-data/body/k5p2/chain.log`). It polls until progress.json `done` is set AND hyst-wo14-a2 is inactive, then runs
k5p2_eval.py check/songs/summary (6 thr, cores 6-11, out `/secondary/hyst-data/body/k5p2/check/`) and k5p2_render.sh (videos
`/secondary/hyst-data/body/k5p2/video/`, waits for mains). Read by overseer: correct. Caveat: if training crashes without `done`, the
chain waits forever (the overseer watcher catches the unit end). Training round 705/977 at 16:05, ~81 s/round (load ~69, Kabl),
round 800 validation ~18:15, training end ~22:20. Not yet verified by overseer: k5p2_eval.py content vs WO18 bar (do at the gate).

**Merged:** body 9b73365 contains body-m3f (WO14A-WO17: hinges, end stop, raised plane 0.053, contact-tc 0.006, smooth u, diag tools,
gates `m3f_gate17.py`). keys-decide merges body.

**WO17 result (verified):** both seeds pass 7.30.3 + 7.31.2 gates; 0 % on stops; vs kappa0 > 0 both decoders both seeds; only 2 programs
(top share 84 % / 98 %); longest still pose 0.02-0.04 s (no rests). Clips `/secondary/hyst-data/body/m3f/rerun4/clips/ep{0,1}-side-by-side-720p.mp4`
SENT to the user; **user verdict pending** (the user may stop pass2 after the clips).

**After pass2 training:** agent 1 runs the check (bar = full K5 bar + check-csv on Instant Crush / Five Years / Presence + (e'1)/(e'2) per
song vs `docs/hf_v47_eprime_reference.json`; report lines 7.28-7.31; kappa0 decides inner-rhythm wording 7.31.3), then videos (3 songs,
1080p + 720p < 30 MiB, three-panel v47 | fallback | pass2). Overseer verifies (recompute per-song paired bootstraps from eval JSON,
check-csv per song, (e') per song), sends videos, writes `docs/PLANNER_BRIEF_PASS2_RESULTS.md`. If a bar component fails: §7.26 round 2
(weights x <= 3 from those in force at launch: floor 1, acc 1), via the planner.

## Where things stand (2026-11-07, saved before an overseer context clear)

**Goal (user, BRAIN_SPEC 7.19):** a scale human, ONE arm, driven by the brain's own encodings (B7 epoch 6 lanes); it learns to move so its
inner state can be read from its body. ARGMAX for every claim. ONE arm permanently.

**Rules of record:** `docs/BRAIN_SPEC.md` §7.17-7.27; read **7.22-7.27 first** (7.22 K5 try 1; 7.23 pass2 required; 7.24 user verdict
"spastic" + pass2 body/movement design; 7.25 bar (e') hand-space; 7.26 pre-registered round-2 rule (user); 7.27 WO13 rulings: floor-margin and
hand-acc hinges weight 1, hard clip, keep changes 3/4, **pass2 box 30 h, launch without asking if projection <= 30 h**). Branch of record
`body` (origin f44a196 + prompts 819df88); `keys-decide` = body + overseer docs. Never master.

**Done and merged since K5 try 1:** WO12 (K5 videos; arm through the floor, check-csv refuses), WO11 (seed 2: none credited), WO13A (hf_share +
v47 refs), WO13B (new body v2f + movement changes; toy try 1 PASSES bar + (e'); controls above 0; changes 3/4 raise hand acc; floor margin
broken in 5/16 episodes, shoulder parked 0.1 deg past limit 19 % of rows). Details in the dated notes below.

**Running now (sent 2026-11-07, notify_when_idle on both):**
- **Agent 2 [730780]** (not cleared, ~40 % context; built m3f): **WO14A** `docs/BUILDER_PROMPT_WO14A_TOY_RERUN.md` in worktree
  `.claude/worktrees/body-m3f`, branch body-m3f, data `/secondary/hyst-data/body/m3f/rerun1/`, 8 thr / 14 GB. Adds the two §7.27 hinges + hard
  clip (pushes code early), reruns toy try 1 (jerk 0.03, switch 0.01) + WO7 controls + per-joint time within 2 deg of a limit. ~1-1.5 h.
- **Agent 1 [97e43a]** (freshly cleared): **WO14B** `docs/BUILDER_PROMPT_WO14B_K5_PASS2.md` in worktree `.claude/worktrees/body-k5video`,
  new branch body-k5p2, data `/secondary/hyst-data/body/k5p2/`, 6 thr / 10 GB. Builds k5p2_train.py on M3f + the 14A terms, times 3 rounds,
  **must NOT launch until the overseer tells it 14A's rerun passed and is merged**; then launches by itself if projection <= 30 h, reports each
  validation, runs the check (full K5 bar + check-csv on 3 danced songs + (e'1)/(e'2) per song), then 3-panel videos (v47 | fallback | pass2).

**Next for the overseer:**
1. Within ~30 min of sending: check both branches have a first push (body-m3f new commits; origin/body-k5p2 exists).
2. When 14A reports: verify (three-dot diff vs body: new options only, old paths bit-identical; tests; recompute try-1 intervals, controls,
   (e'1)/(e'2) means from `rerun1/.../result.json` per-episode values; check near-limit shares and clip max excess). If it passes: merge
   body-m3f into body (detached temp worktree, `git push origin HEAD:body`), merge keys-decide, then **tell agent 1 to launch**. If it fails:
   stop, brief the planner.
3. During pass2: Monitor/hourly checks; report validations with ETAs; the run may take up to 30 h of compute.
4. After the pass2 check: verify (recompute per-song bootstraps as for try 1, check-csv per song, (e') per song), send 720p videos, write the
   planner brief. If it fails on floor margin / (e'1) / (e'2) only, §7.26 round-2 applies (weights x <= 3, chosen on the toy).

**2026-11-07 ~12:45:** WO14A pushed (body-m3f 207ac3c code, c0c3f6b log); rerun unit hyst-wo14-m3f-rerun-1233 started 12:33, ETA ~13:35-14:00. Deviation: --hard-clip = targets 0.5 deg inside range + positions clipped after every substep with speed zeroed (hard end stop). USER ACCEPTED = BRAIN_SPEC 7.28 (body b53ea94): matches servo firmware angle limits; condition: report end-stop events per episode + hand acc/jerk in the 0.1 s around each; limit-proximity cost stays; pass2 uses exactly the rerun's body/terms. Sent (user OK) to agent 1 (options + deviation + 7.28, still no launch) and agent 2 (end-stop report condition), notify_when_idle both. Agent 1 pushed body-k5p2 c0f2c1e 12:20. Verify 14A also against 7.28.2 (end-stop event counts, acc/jerk near events, recompute from result.json).

**2026-11-07 ~14:20:** WO14A DONE (agent 2, body-m3f bf4037d), verified: 27 tests OK (old-path bit-identity, WO13B + M3e first-epoch reproduction), options default off, paired intervals recomputed (match). Argmax ext 1.010, int 1.018, e'1 3.42, e'2 0.0091; vs untrained +0.76/+0.76, vs kappa0 +0.21/+0.14. Joint-range breaches 0 (was 19 %); floor margin 9/16 eps (was 5/16), worst 0.051 m. End stops ~2.4/episode; near-stop acc p99 at 100 Hz: overseer pooled 6.85, builder per-episode 5.35; 50 Hz 3.45 vs 3.41 overall. NOT merged yet. USER RULING = BRAIN_SPEC 7.29 (body f41718e): stops accepted; floor hinge weight 3; one toy rerun (WO14C, agent 2, --w-floor option default 1, data m3f/rerun2/); PASS if bar + (e') pass and floor breaches <= 2/16 eps -> merge body-m3f into body, send agent 1 the terms (--w-floor 3 --floor-acc-hinges --hard-clip), launch pass2 without asking; else stop and report. 7.26 round-2 scaling relative to floor 3 / acc 1. Agent 1 told to wait + prepare (both methods at 100 Hz in the pass2 check). Overseer end-stop script: job tmp verify14a.py (not durable; logic: events = control step with a ranged joint within 1e-4 deg of +-110, window +-5 steps).

**2026-11-07 ~17:45:** WO14C (agent 2, body-m3f ad48642, floor weight 3, data m3f/rerun2/) FAILS the 7.29 gate: (e'2) 0.0188 > 0.0110; floor breaches 11/16 eps (WO14A 9/16); shoulder within 2 deg of limit 38.5 % (WO14A 3.9 %). Bar (a)(b)(c) pass; intervals recomputed (match). Cause found by overseer: floor hinge normalised by OLD-body untrained 0.117 m -> normalised term ~5e-4 vs limit-proximity 0.35-2.2, ~1000x too small to act. Pass2 NOT launched; agent 1 waiting (body-k5p2 5542992). body-m3f NOT merged into body (WO14A/C verified, waiting on planner). Brief `docs/PLANNER_BRIEF_WO14_RESULTS.md` sent (Q1 floor scale: recommend fixed 0.05 m normaliser, weight 1; Q2 two seeds; Q3 keep gate; Q4 shoulder parking report-only; Q5 record). Laptop was on battery 14:24-15:59 (unit waited); remind user about the charger.

**2026-11-07 ~18:30:** planner answered WO14 = BRAIN_SPEC 7.30 (raised contact plane at check-csv margin + floor hinge normalised by fixed 0.05 m, weight 1; two seeds 0/1, gate per seed; shoulder parking report-only; round-2 relative to weights at launch). User chose option A = 7.30.6 (body f6236d8): plane at 0.05 + d, d = deepest held-contact sinking rounded up to mm, <= 5 mm else stop; record d + real-arm clearance in hardware notes (memory hardware-target.md: TODO when d known). WO15A prompt `docs/BUILDER_PROMPT_WO15A_RAISED_PLANE.md` sent to agent 2 (data m3f/rerun3/seed{0,1}); agent 1 told new terms (--raised-plane), still wait. If both seeds pass: merge body-m3f into body, tell agent 1 to launch pass2 without asking.

**2026-11-07 ~19:00:** WO15A stopped at step 1: d = 45 mm at default contact (folded arm pressing ball, 39.9 mm settled; plane_test.json checked). User = BRAIN_SPEC 7.30.7 (body 9140845): --contact-tc 0.006 s (probe 2.3 mm -> d ~3 mm) after checks (i) stability (no NaN, no growth/oscillation, settled hand < 0.01 m/s, adversarial + 1 epoch clean) and (ii) cost (epoch <= 1.25x 62 s, pass2 projection <= 30 h); fallback ONLY if a check fails = option 4 (plane 0.055, default contact, contact-force hinge / m g, weight 1). Sent to agent 2 (report checks before seeds) and agent 1 (still wait). Hardware notes: record d + clearance when known.

**2026-11-07 ~20:35:** WO15A checks passed (d = 3 mm, plane 0.053, contact-tc 0.006 on ALL geoms; epoch 61.8 s; pass2 projection 20.6 h). Seed 0 PASS gate (ext 0.739, b 30.2, e'1 2.33, e'2 0.0002, floor 0/16) BUT argmax trained-kappa0 -0.036 [-0.086, 0.014] / -0.047 (overseer recomputed), elbow 48.5 % / wrist 60 % within 2 deg of limit, one program 79 %. Seed 1 trained argmax ext 0.948, int 1.024, b 40.9, e'1 2.89, e'2 0.0012, contact 0 (controls/gate pending). USER = BRAIN_SPEC 7.30.8 (body 59470b3): self-contacts accepted; pass2 auto-launch HELD; WO15B clips (4 x 60 s toy, seeds 0/1, + song-length if cheap) to /secondary/hyst-data/body/m3f/rerun3/clips/ with end-stop time, programs, trained-kappa0 per seed; then stop and ask user. Agent 1 told hold (may wire options). Hardware memory: d = 3 mm provisional -> final now (checks passed).

**2026-11-07 ~20:50:** both WO15A seeds PASS the gate (overseer recomputed). Seed 1 argmax ext 0.948, int 1.024, b 40.9, e'1 2.89, e'2 0.0012, floor 0/16; vs kappa0 ext +0.039 [-0.02, 0.10], int +0.105 [0.04, 0.18] (inner-rhythm wording needs both > 0: not met; seed 0 neither). Parking: seed 0 elbow ON limit 46.3 %; seed 1 shoulder ON limit 13.4 % (36 % within 2 deg). End stops 5.6 / 7.3 per episode. Pass2 HELD (7.30.8). Agent 2 rendering WO15B clips (~1 h) to rerun3/clips/; overseer must check media then SendUserFile and ask the user. 35 tests OK.

**2026-11-07 ~22:00:** WO15B DONE (agent 2, body-m3f d663a95): 4 x 60 s clips + 2 side-by-sides (720p < 30 MiB, 60.0 s, silent: toy input is synthetic) in /secondary/hyst-data/body/m3f/rerun3/clips/; checked (ffprobe, frames ep0@30 s, ep1@50 s); side-by-sides SENT to user. Song-length rollout skipped (toy policy reads toy brain state, needs a new feature mapping). Per clip on-limit share (sh/el/wr): s0e0 0.2/37.9/0, s0e1 5.1/43.5/3.2, s1e0 12.5/0/0, s1e1 15.4/20.3/4.7 %. WAITING for user verdict; pass2 HELD (7.30.8). body-m3f NOT yet merged into body.

**2026-11-07 ~22:30:** user verdict on WO15B clips = BRAIN_SPEC 7.30.9 (body 4883de7): seed 0 stuck "bowed down" (elbow on -110 stop) most of the time; seed 1 alive/smooth/varied in ep 0 but slumps into the same pose in ep 1 from ~42 s. Pass2 HELD. Brief `docs/PLANNER_BRIEF_WO15_RESULTS.md` sent (Q1 time-on-stop cost (a) recommended, (c) narrower commanded range as fallback; Q2 gate line: <= 10 % on a stop, no hold > 5 s; Q3 inner-rhythm left to pass2's kappa0 control; Q4 record). Overseer scripts (job tmp, not durable): park.py (on-stop intervals >= 2 s from rollouts q, |q| within 0.05 of 110).

**2026-11-07 ~23:00:** planner answered WO15 = BRAIN_SPEC 7.31 (body bacea5c): diagnose parking first (6 points per hold >= 2 s, re-sim with logging; verdicts H1-H6), no training/pass2 until user sees it; parking gate adopted for next toy rerun (<= 10 % on a stop per joint, no stop-hold > 5 s; report longest any-pose hold, hand < 2 cm/s); inner-rhythm wording by pass2's kappa0; Q4 record incl. user's "seed 1 ep 0 alive" and clipping reading. WO16 prompt `docs/BUILDER_PROMPT_WO16_PARK_DIAGNOSIS.md` (agent 2's worktree body-m3f, 6 thr/10 GB, output rerun3/diag/) written, NOT SENT: waiting for user's word (agent 2 may be cleared first; prompt is standalone). Agent 1 holding (pass2).

**2026-11-08 ~00:30:** WO16 DONE (agent 2, body-m3f d543db4), verified: additive default-off diag flag + new files, test_m3f_park 6 OK (overseer rerun), hold census recomputed (seed 0 46 holds 467.1 s, seed 1 32 holds 119.9 s, all on -110: match). Verdicts: H1 supported as generator-centre saturation at +-110 (amplitude cap -> ~0.04 deg), H4 pinned supported, H5 seed 0 only (program 2), H2/H3/H6 not supported (H6 borderline p 0.03). Brief `docs/PLANNER_BRIEF_WO16_RESULTS.md` sent (Q1 recommend gradient check then smooth centre map into +-(110-A_min); Q2 A_min 10; Q3 report-only; Q4 record). body-m3f still NOT merged into body. Pass2 held.

**2026-11-08 ~00:45:** planner's reply to the WO16 brief = additions (7.31.5: clip-boundary holds, H1b, H7), run as WO16b (agent 2, body-m3f 595cf39), verified: additive default-off torque logging, test_m3f_park 6 OK, boundary census recomputed (seed 0 38 holds 549.5 s wrist; seed 1 17 holds 82.8 s). H1b yes (centre u at bound 0 in 99.8 % of hold blocks, zero-grad clip), H7 torque no / gravity yes (droop 1.5-1.6 deg > 0.5 clip margin). Follow-up brief `docs/PLANNER_BRIEF_WO16B_RESULTS.md` sent (Q1 smooth centre map into +-(110-A_min), A_min 10; Q2 all u rows; Q3 report-only; Q4 record). body-m3f NOT merged. Pass2 held.

**2026-11-08 ~01:00:** planner answered WO16b = BRAIN_SPEC 7.32 (body 311e6d4): smooth map replaces every u clip (bend centres into +-100, A_min 10), gradient test; record chain + user's reading correct; two-seed toy rerun under 7.30.3 + 7.31.2 parking gate; BOTH PASS -> overseer verifies, merges body-m3f into body, tells agent 1 "launch" (pass2 options + --smooth-u), clips rendered in parallel; either fails -> stop, report with clips. WO17 prompt `docs/BUILDER_PROMPT_WO17_SMOOTH_U.md` sent to agent 2 (data m3f/rerun4/); agent 1 told to wire --smooth-u and wait for "launch".

**2026-11-08 ~01:20:** WO17 code pushed (body-m3f 09a870f option+tests, 7d8dfdb chain/gate17); unit hyst-wo17-rerun4-0015 started on mains (user plugged in). Map u = 0.5+0.5 tanh((s-0.5)/0.5): over s in (-0.2,1.2) centres reach +-88.5 (not +-100). Question to planner `docs/PLANNER_BRIEF_WO17_MAP_SCALE.md` (recommend keep run, decide from result). Run continues with c = 0.5. Not yet verified by overseer: smooth tests, bit-identity (verify at gate).

**2026-11-08 ~01:50:** 7.32.6 recorded (c = 0.5 kept, user). WO17 seed 0 PASS both gates (overseer recomputed): ext 1.050, int 1.072, b 52.0, e'1 3.35, e'2 0.0067, floor 0/16, on-stop 0 % all joints, stop-hold 0 s, end stops 0, longest any-pose hold 0.02 s; programs 2 (84 %); vs kappa0 argmax ext +0.155 [0.06, 0.26], int +0.086 [0.003, 0.18] (both > 0). test_m3f_smooth 5 OK (overseer). Seed 1 running (~03:00). If seed 1 passes: merge body-m3f into body (detached temp worktree, push HEAD:body), tell agent 1 "launch".

**2026-11-08 ~02:50 (usage limit reached; overseer stopped):** WO17 seed 1 trained argmax ext 1.016 [0.846, 1.189], int 1.214, b 52.1, e'1 2.69, e'2 0.0014, contact 0, programs 2; controls + gate17 still running (unit hyst-wo17-rerun4-0015). NEXT for a fresh overseer: read rerun4/seed1/gate17.json; recompute seed 1 controls (paired bootstrap from controls/*.json a_gaps) + parking from rollouts; if BOTH seeds PASS: merge origin/body-m3f into body (detached temp worktree, `git push origin HEAD:body`), merge keys-decide, SendMessage agent 1 [97e43a] "launch" with options --body v2f --hard-clip --floor-acc-hinges --contact-tc 0.006 --raised-plane --w-floor 1.0 --smooth-u (7.32.5, no need to ask); agent 2 renders clips -> check + send to user. If seed 1 FAILS: stop, report to user with clips, write planner brief.

**2026-11-08 ~03:35:** WO17 BOTH SEEDS PASS (overseer recomputed): seed 1 ext 1.016, int 1.214, e'1 2.69, e'2 0.0014, floor 0/16, 0 stop events, programs 2 (top 98 %), vs kappa0 argmax ext +0.238 [0.13, 0.36], int +0.197 [0.09, 0.33]. Merged body-m3f into body 9b73365 (11 tests OK on merge), keys-decide 4a35f10. Agent 1 told LAUNCH pass2 (options + --smooth-u). Agent 2 at usage limit (summary.json + night log WO17 section NOT written); overseer launched its clip script as unit hyst-wo17-clips-0332 (M3F_CLIPS_ROOT=rerun4, out rerun4/clips/). Next: check clips -> send user; confirm pass2 unit + projection; watch pass2.

**2026-11-08 ~03:50:** WO17 clips rendered by overseer (unit hyst-wo17-clips-0332, rerun4/clips/, 60.0 s, 720p 27.5-27.7 MB, frames checked) and SENT to user; awaiting user verdict (watch: no rests, longest hold 0.02-0.04 s; top program 84 %/98 %). PASS2 RUNNING: unit hyst-wo14-a2 (agent 1, body-k5p2 93e18bb, 10 GB cap, cores 6-11, data /secondary/hyst-data/body/k5p2/run/, train.log); first launch hyst-wo14-a1 failed (no working dir) and was reset. Pass2 options incl. --smooth-u. Next: projection from first rounds (box 30 h), validations with ETAs, user may stop after clips. Agent 2: summary.json + night-log WO17 section still owed when its limit resets.

**2026-11-08 07:08:** pass2 (hyst-wo14-a2) validation round 200: ext 0.862, int 0.873, b 37.2, 3.37 h compute (K5 try 1 at 200: 0.559/0.510). Rounds ~59.5 s; training end ~20:00-21:00. Overseer watcher = background bash loop on progress.json val count / unit / power (re-arm after each event). User verdict on WO17 clips still pending.

**2026-11-08 ~14:10:** pass2 round 606/977 (val 600: ext 0.913, int 0.931), end ~20:10. Builder sessions restarted ~13:54 (new refs agent 1 [9ae40e], agent 2 [071001], fresh). Agent 1 never wrote k5p2_eval.py / video scripts (worktree clean, pushed 53ff54e). WO18 prompt `docs/BUILDER_PROMPT_WO18_PASS2_CHECK.md` (body) written for fresh agent 1: build check + videos now, run on best.pkl when training ends. NOT SENT: waiting for user's word. Agent 2 still owes WO17 summary.json + night-log section (optional).

**Machine:** Kabl jobs share it (the user prefers sequential Hysteresis work; 14A and 14B's build phase overlap is light). Mains power was on.

**2026-11-06 ~12:00:** user: two fresh agents available; Kabl work will share this machine, so WO12 and WO11 run SEQUENTIALLY (WO11 only after WO12 reports). WO12 prompt written and pushed: `docs/BUILDER_PROMPT_WO12_K5_VIDEOS.md` (body 6e65bdf), share 6 threads / 6 GB, branch `body-k5video`, for a fresh agent (pasted by the user; agents offline in ListAgents). Found: no joint-CSV renderer exists; WO12 step 3 asks for the smallest additive one, v47 cmp required. Body worktree index slip FIXED (user OK, reset --hard HEAD, clean).

**2026-11-06 ~13:00:** WO12 DONE (agent 1 [c3fea2], body-k5video 722fe13), verified by overseer: test_k5_video OK (lanes bit-identical vs stored check song 009900; full-song first 60 s bit-identical vs K5 eval window), v47 regression identical 3/3 (fresh CARGO_TARGET_DIR), previz clippy/fmt clean; 9 videos durations = audio within one frame, 720p files < 30 MiB; frames looked at. Merged: body = 722fe13 (ff), keys-decide 86e782b. Side-by-sides sent to the user. FINDING: check-csv refuses all three songs; floor rule broken in 91-97 % of rows (worst -0.72 m), hand speed up to 2.4 m/s (limit 1.2). Overseer FK on instant-crush joints: hand z median -0.28 m, min -0.61, max +0.60 vs base; shoulder -91..+93 deg. Cause: MuJoCo arm has no floor; K5 has no floor/hand-speed term. Frames show the arm through the floor (Presence 200 s). Per-60 s (a) all 16 segments > 0 both decoders (lowest IC 0-60 ext 0.135). Outputs /secondary/hyst-data/body/k5/danced/. WO11 sent to agent 2 [4ae253] ~13:00 (sequential order met). Next: user verdict on videos; then planner brief on the floor finding (K5-pass2 needs a floor + hand-speed term, 7.22 point 3) if the user wants.

**2026-11-06 ~15:15:** WO11 DONE (agent 2 [4ae253], body-m3e 885a982), verified: paired try1-ablation intervals recomputed from a_gaps for both seeds (all match), diff = new files + run_m3e --seed (default 0 = try 1), tests 15 OK. Merged body 885a982, keys-decide. Verdict per 7.21: all three "present", none credited; dopamine not shown to lower. Seed-2 try 1 ext 0.763, int 0.602. Brief `docs/PLANNER_BRIEF_WO11_WO12_RESULTS.md` written and sent (Q1 record WO11, Q2 K5-pass2 floor/speed design, Q3 toy first, Q4 no 60 s wording). Agents 1 and 2 idle. Waiting: user verdict on videos, pass2 wish, planner answers.

**2026-11-06 ~15:40:** planner answered WO11/WO12 = BRAIN_SPEC 7.23 (body 457b06f): WO11 recorded (none credited); K5-pass2 REQUIRED (floor plane at mount height with contact, self-collision, check-csv hand-speed/jolt soft penalties weighted like energy, rig joint ranges); pass2 bar = full K5 bar + check-csv passing on the three danced songs; order: M3e toy with new body (2 h) first, then pass2 (24 h box). Mount question asked to the user (plinth/table/hanging + height); default floor z = 0. K5-only 720p videos sent. Next: WO13 prompt (new body + toy), waiting on the user's mount answer / go.

**2026-11-06 ~16:10:** user verdict on K5 try 1 videos ("something musical, but spastic"; arm through the base; mount = table or pillar) and the planner's pass2 design = BRAIN_SPEC 7.24 (body 9acbf19), with overseer defaults for (e) (Welch 4 s, >3 Hz share, four non-roll joints; v47 = mean over six arms; grid selection rule) flagged for planner confirmation. WO13 prompts (body 90607c5): 13A `BUILDER_PROMPT_WO13A_HF_REFERENCE.md` -> agent 1 [c3fea2] (branch body-hf, 4 thr/4 GB, hf_share.py pushed within 1 h), 13B `BUILDER_PROMPT_WO13B_M3F_TOY.md` -> agent 2 [4ae253] (branch body-m3f, 8 thr/14 GB; contact cost + pass2 projection first, report if > 22 h). Both sent ~15:45 (clock; an earlier note said 16:10 by mistake), notify_when_idle.

**2026-11-06 ~16:05:** WO13B contact cost: per toy epoch old body 39.4 s, v2 (friction, condim 3) 91.3 s, v2f (frictionless, condim 1) 62.9 s; pass2 upper-bound projection 30.6 h (v2) / 21.1 h (v2f). Overseer approved v2f as default (a passing policy keeps 5-11 cm clearance, contact is only a stop) - FOR USER/planner: friction off. Overseer ordered jerk/hand-speed/jolt normalisation by the untrained policy's OLD-body value (new-body untrained jerk ~1e9 is contact-spike dominated vs 2e6). One K5 round with v2f to be timed before pass2.

**2026-11-06 ~18:00:** WO13A DONE (agent 1, body-hf 731675f), verified: diff = new files only, test_hf_share 7 OK, K5 (e) values recomputed independently (match). Merged into body. v47 (e) reference 0.002970 (IC 0.002419, FY 0.002828, PR 0.003662), limit 0.003712. PROBLEM: K5 try 1, judged spastic by the user, has (e) 0.002660 < limit, so (e) as defined would pass it. Overseer exploration (report only, v47 arm 0 vs K5): joint-space measures (accel share >3 Hz, jerk/vel, speed peaks, reversals) do not separate; hand-space ones do: hand acceleration p99 K5 10.2/11.0 m/s2 vs v47 4.2/5.9 vs fallback 3.4/3.7 (IC/PR); share of time hand > 1 m/s K5 0.16/0.11 vs v47 0.01/0.014. Needs a planner/user ruling on (e) before the WO13B grid selection (grid ETA ~20:40).

**2026-11-06 ~18:30:** planner ruled on (e) = BRAIN_SPEC 7.25 (body f667d04): (e) replaced by (e'1) hand-acc p99 and (e'2) share hand speed > 1 m/s, each <= 1.25x v47 (limits computed by overseer: IC 5.320/0.01210, FY 5.182/0.00661, PR 7.501/0.01431, toy 6.001/0.01101; docs/hf_v47_eprime_reference.json); v2f and old-body normalisation confirmed; contact time reported. Overseer did not read grid (e') values before the ruling. Agent 2 told to select by 7.25 after the grid and continue to try 1, controls, ablations. Agent 1 idle.

**2026-11-06 22:15:** WO13B grid done (5.5 h; epochs 62-130 s under load). Overseer re-read selection.json (22:09): eligible only j0.03/s0.01 (ext a 1.019, e'1 3.46, e'2 0.0094) and j0.03/s0.05 (0.994, 3.21, 0.0038); others fail (c) (p 0.022/0.016/0.098) or e'2 (j0.01/s0.05 0.0415). Selected j0.03/s0.01 by 7.25 rule - correct. Contact 0 except j0.01/s0.01 (0.94 %). Main stage unit hyst-wo13-m3f-main-2210 (try 1 + controls + ablations), ETA ~03:15. Risks: e'2 margin 15 %, (c).

**2026-11-07 ~03:00:** WO13B DONE (agent 2, body-m3f d63a3e2), verified: three-dot diff = new files only, tests 20 OK, try 1 + controls + all four ablation paired intervals recomputed (match). Merged into body and keys-decide. Try 1 PASSES toy bar + (e') (ext 0.946, int 1.004, e'1 3.51, e'2 0.0107 / limit 0.0110); controls vs untrained +0.70/+0.75, vs kappa0 +0.14/+0.09; ablations: changes 3 and 4 RAISE hand acc; obs-LP off -> arm on table 93 %. Breaches: floor margin 5/16 eps, shoulder parked 0.1 deg past -110 for 19 % of rows. 7.26 (user, pre-registered round-2 rule) recorded on body d6f4539 with overseer note: no floor-margin or hand-acc term exists. Brief `docs/PLANNER_BRIEF_WO13_RESULTS.md` sent (Q1 add terms + toy rerun, Q2 hard joint clip, Q3 keep 3/4, Q5 time a K5 round). Pass2 prompt waits for answers. Agents 1 and 2 idle.

**2026-11-07 morning:** planner answered WO13 = BRAIN_SPEC 7.27 (body f44a196): floor-margin + hand-acc (>4.8) hinges, weight 1, normalised like hand-speed; hard clip all ranged joints; keep changes 3/4 (recorded they raise hand acc); pass2 box 30 h, launch without asking if projection <= 30 h; recorded obs-LP-off -> table 92.6 %. WO14 prompts (body 819df88): 14A toy rerun for agent 2 (body-m3f, data m3f/rerun1); 14B K5-pass2 trainer/timing/run/check/videos for agent 1 (branch body-k5p2 in its pinned body-k5video worktree, data body/k5p2). NOT SENT YET: both builder sessions were offline (ListAgents: agent 1 [2f4b5b], agent 2 [304914] offline). Send when they are back. Agent 1 must NOT launch until the overseer confirms 14A passed and is merged.

**Open overseer slip (FIXED 2026-11-06 ~11:55 with the user's OK; kept for the lesson):** on 2026-11-06 the overseer merged into body with `git checkout -B body` in a temp worktree; that
moved the branch under the existing worktree `.claude/worktrees/body`, whose index/files are still at d5a1fae (8 staged files = the exact reverse
of the K5 merge; no own changes). Fix: `git -C /secondary/Programming/Github/Hysteresis/.claude/worktrees/body reset --hard HEAD`
(auto mode refused it; ask the user, or the user runs it with `!`). Origin is correct. Lesson: write to body in a detached temp worktree and
`git push origin HEAD:body` (done that way for 7.22), never `checkout -B body` elsewhere.

**Planner briefs:** WO5–WO9 and K5_RESULTS sent and answered (7.17–7.22). No brief pending.

**Watching:** overseer's K5 watcher was job-tmp `k5watch.sh` (polls progress.json; the generic `watch_unit.sh` once missed a line). Hourly
session cron dies with the session; recreate (CronCreate `23 * * * *`) only when jobs run. Claude-independent watchdog: systemd timer
`hyst-overseer-watchdog.timer` every 15 min → `/secondary/hyst-data/overseer/watch.log`.

**User preferences this session:** ETAs (next milestone + finish, from live logs) on every progress update; compare new numbers to earlier
ones when asked.

### History of 2026-11-04/05 (dated notes, oldest first)


**Plan:** `docs/BODY_BRAIN_PLAN.md` version 2 plus the dated rulings in `docs/BRAIN_SPEC.md` §7.11–7.16 (read 7.14, 7.15, 7.16 first:
they replace parts of the plan). Branch of record: `body` (pushed); `keys-decide` = body + overseer docs. Never master.

**Closed:** B7 (epoch 6 = cortex of record); H1, H2, H3 (all fail T1b; T1a passes from H2 on); M1/K1 (fails, claim forbidden; cerebellum usable
as a mechanism); T-M3, M3b (retired), M3c (fails (a) twice). Results: briefs `docs/PLANNER_BRIEF_WO2_RESULTS.md`, `_WO4_RESULTS.md` (the
latter corrects WO2: "selection collapse" was an argmax evaluation artefact).

**Running now (work order 5, sent 2026-11-04 ~23:55; all agents fresh after a power-off at 19:36):**
| Agent | Order (prompt on origin/body) | Branch | Share |
|---|---|---|---|
| 5 | DONE 2026-11-05 ~00:30, verified (v47 cmp 3/3 identical, Rust 102+18 tests, clippy/fmt clean, Python tests, audio hashes match, self-surprisal recomputed, 12 frames looked at), merged into body d4c24e3 and keys-decide; videos too large to send (117-137 MiB, limit 30); local paths given to the user, waiting for their verdict. Was: fallback: authoring tool on B7 lanes for the 3 danced songs + full-song previz videos + self-surprisal export + mindState v2 + manifest.py skip + brainDump without crossings (`docs/BUILDER_PROMPT_WO3_FALLBACK.md` + previz addendum; **priority on the machine**) | body-fallback (not pushed yet at 00:00) | 6 thr / 6 GB |
| 1 | M3d toy (`docs/BUILDER_PROMPT_WO5_M3D.md`), re-sent fresh 23:40 after a clear (first session left nothing) | body-m3d | 8 thr / 10 GB |
| 2 | H4 toy (`docs/BUILDER_PROMPT_WO5_H4.md`), resumed 23:40 after a clear: branch at 8614dd7, try 1 rerun cleanly with committed parameters (design A had finished, B was killed) | body-h4 | 3 thr / 4 GB |
| 3 | DONE 2026-11-04 ~23:50, verified (JSON table recomputed, 34 tests pass), merged into body d1e6454 and keys-decide. Was: sampled re-evaluation of T-M3/M3b/M3c policies + program/state MI (`docs/BUILDER_PROMPT_WO5_REEVAL.md`) | body-reeval | 2 thr / 4 GB |
body-fallback pushed 02b724b at 23:30 (previews, self-surprisal, mindState v2, brainDump, manifest fix); recording videos (hyst-wo3b2-rec1). Machine load ~111 at 23:30, mostly a Kabl factory_bank process. Agent 4 is blank (spare). Units are named `hyst-wo3b2-*` (fallback) and `hyst-wo5-*`.

**When each reports:** verify (below), merge into body, push. For body-fallback also the v47 cmp (it touches crates/ and mindState). Then
the planner brief `docs/PLANNER_BRIEF_WO5_RESULTS.md` with: fallback preview/video paths, self-surprisal sizes, mindState v2 tests, v47 cmp;
the re-evaluation table (both modes, MI); M3d (a)-(c) per try; H4 T1a/T1b per try; FOR USER items. If M3d fails, the self-driven body is closed;
if H4 fails, memory is closed (both final items).

**Open with the user:** the fallback videos to watch (artistic mapping is the user's, by eye; starting map `scripts/author/mappings/example-sketch.json`);
the monitor build waits for the user's choice of the planner's mockups; Kaggle `manifest.py` fix is in the fallback order; the trace viewer
`/secondary/hyst-data/brain/braindump/instant-crush.view.html` was never opened in a browser.

**Overseer lessons from 2026-11-04:** (1) the laptop powers off when the lid closes or on battery; session crons die with the session; after any
restart all agents are fresh and must be re-sent their orders from the prompt files plus their night logs. (2) After sending an order, check
within ~30 min that the branch exists and has a first commit (the fallback produced nothing for hours unnoticed). (3) Read evaluation code, not
only result files: the argmax bug was visible in identical program counts across different rewards. (4) GitHub had server errors; origin is now
HTTPS with the gh credential helper (repo-local config); SSH publickey failed. (5) A shared CARGO_TARGET_DIR gave stale compile errors: use a
fresh one for verification. (6) `tm3_world` patches `core.N`/`core_b7.BLOCK` on import: run its tests in their own process.

**2026-11-05 ~00:30:** planner answered WO5 = BRAIN_SPEC 7.17 (body 1f8915c). Work order 6 prompts on body: `docs/BUILDER_PROMPT_WO6_H4DIAG.md` (agent 2),
`_WO6_M3D_RELAUNCH.md` (agent 1; agent 1 had already relaunched by itself at 00:16 as `hyst-wo5-m3d-grid`, sequential lambdas, 8 threads, 9 GB cap, anon ~1 GB),
`_WO6_TUNING.md` (agent 5: one-arm tuning loop, fast re-render of a song or a 20 s window, + self-surprisal lane). **User correction 2026-11-05: the installation is ONE arm; ensemble out of scope for good** (7.17.4 rewritten, plan §10). Sent 2026-11-05 ~00:45 to agents 2 (H4 diag), 5 (tuning, branch body-tuning), 1 (M3d note), notify_when_idle on all three. AGENTS.md now opens with the one-arm rule (body, keys-decide, dance-checkpoint c9bbf3c). H4 both tries fail T1b; diagnostic per 7.17.1 decides closure.

**2026-11-05 ~00:45:** agent 5 WO6 tuning DONE, verified (tests node 11, attach 5, build 1, serve 2; no crates change; clips 20.000 s; 720p copies <30 MiB), merged into body/keys-decide; 720p videos sent to user. Presence camera crops the hand at the top edge (FOR USER).

**2026-11-05 04:55 hourly check:** H4 diagnostic DONE (body-h4 6eaa9e6, tests h3+h4 OK, merged): top-k 4 confirmed; H4 control 1.000 is the true cortex-only; H3's reported cortex-only control (0.881|0.656|0.566) was really a w = 0.5 blend (mislabelled; correct the WO4 brief in the next one); replay MSE in the repeat about equal to the cortex's (A L1 0.627 vs 0.671), oracle ~0: retrieval returns the wrong content. No deviation -> memory closed for this plan. M3d chain (hyst-wo5-m3d-chain-0027, 9 GB) OOM-killed 01:27 AFTER try 1 finished: lambda 0.3, held eval argmax (a) 0.480 [0.422, 0.541], (b) 33.0, (c) MI 0.536 p 0.001; sampled (a) 0.498 [0.418, 0.583], (b) 39.3, (c) MI 0.055 p 0.001 -> builder claims pass on all three; NOT yet verified. Agent 1 told at 04:53 to finish the missing step (cap up to 14 GB) and report.

**2026-11-05 ~05:30:** M3d verified (test_m3d 10/10 rerun by overseer, numbers re-read from try1/result.json, no rules docs touched), merged body-m3d 3b8ef08. Try 1 passes the toy bar in both modes. Brief `docs/PLANNER_BRIEF_WO6_RESULTS.md` sent: Q1 report-only controls (untrained motor cortex, kappa = 0) before accepting; Q2 real M3d run after; Q3 memory closed + WO4 H3-control correction. All WO6 orders done; agents 1-5 idle.

**2026-11-05 ~10:00:** planner answered WO6 = BRAIN_SPEC 7.18 (body da08b4e). Work order 7 prompts on body: `BUILDER_PROMPT_WO7_M3D_CONTROLS.md` (agent 1), `_WO7_PARITY.md` (agent 3, branch body-parity), `_WO7_CAMERA.md` (agent 5, body-tuning). The K5 real-run prompt is written after the controls report (7.18 point 2: controls first). Sent 2026-11-05 ~11:05 to fresh agents 1, 3, 5 (notify_when_idle). Hourly cron now 2a6f5721 (WO7 prompt).

**2026-11-05 ~11:20:** WO7 camera (agent 5) verified (v47 cmp 3/3 identical, hyst-compile 102 + hyst-output 18 tests, clippy/fmt clean, Presence 110 s frame inside) and merged; its 720p renders, agent 1's controls and agent 3's parity are all armed to start on mains power (laptop on battery since ~10:45).

**2026-11-05 ~11:35:** WO7 parity (agent 3) verified (traj.npz recomputed: mjx1 vs MuJoCo max angle diff 7.2e-05 / 2.6e-03 / 2.8e-02 / 3.8e-03 / 3.6e-07 deg per joint, <= 6e-14 over the first 10 s, mjxfull 2.3e-13; 8 of 10 trajectories <= 1.1e-13, two diverge only at the elbow limit; tests 4 OK) and merged. Feeds K5 (7.18 point 2).

**2026-11-05 ~11:45:** WO7 camera renders done (720p in /secondary/hyst-data/brain/author/tuning/720p-cam/, 27 MiB each, durations match; Presence 110 s frame checked) and sent to the user; agent 5 done. Waiting: agent 1's M3d controls (evals finished, tests running).

**2026-11-05 ~12:10:** WO7 complete: M3d controls verified (paired CIs recomputed from per-episode values; code change is a default-off kappa_fix override + a_gaps output; 13 tests OK) and merged (body-m3d bc1d1c7). Untrained cortex passes the toy bar in argmax; trained beats untrained by ~0.26 both modes. Brief `docs/PLANNER_BRIEF_WO7_RESULTS.md` sent (K5 bar, size/budget, observer procedure). K5 prompt waits for the planner's answer to Q2/Q3. Agents 1-5 idle.

**2026-11-05 ~12:30:** planner + user answered WO7 = BRAIN_SPEC 7.19 (body 9dfbde8): goal = a scale human, one arm, brain's own encodings, learns to be legible; ARGMAX mode for every claim; K5 size fixed; first the M3e toy rerun (closed loop + cerebellum inputs, dopamine critic scaling BG learning rate, causal 30 s normalisation, self-observer), two tries, WO7 controls again; then K5. Work order 8 sent: agent 1 `BUILDER_PROMPT_WO8_M3E_TOY.md` (body-m3e), agent 3 `_WO8_K5_DATA.md` (body-k5data, splits + B7 lanes + K5 projection). Dropped for good: H1-H4, B1, M3/M3b, emotion decoding, ignition, ensemble. Data lanes only: self-similarity, self-surprisal, per-layer synchrony.

**2026-11-05 ~13:00:** K5 data (agent 3) verified and merged (body-k5data 9c9e139): splits recomputed from splits.json, train 2,602 songs / 650 artists / 162.0 h, val 217 / 72 / 12.7 h, check 357 / 73 / 20.1 h, zero artist and id overlap; 3,176 lane files; 15,624 train + 1,071 check windows; tests 7 OK. Projection: one pass over the train windows = 9.4 h at M3d cost (~19 h if M3e costs 2x) > 8 h box, so K5 needs Kaggle or a partial pass: question for the planner once M3e's cost is known. Lanes in /secondary/hyst-data/body/k5/ (311 MB).

**2026-11-05 ~14:30:** WO8 complete. M3e verified (paired CIs recomputed; test_m3e 12 + test_m3d 13 OK; new files only) and merged (body-m3e 2884e74): try 1 passes in argmax, ext (a) 0.991, int 0.951, beats untrained by 0.555/0.644 and kappa-0 by 0.188/0.193 (all intervals > 0). M3e costs ~2.2x M3d: one K5 pass ~20 h on the laptop. Brief `docs/PLANNER_BRIEF_WO8_RESULTS.md` sent (K5 compute, ablations, internal-observer input). Agents 1-5 idle.

**2026-11-05 ~15:00:** planner answered WO8 = BRAIN_SPEC 7.20 (body 17e739f): K5 = one full pass, 24 h compute box, Kaggle check first; ablations decide wording ("present" vs credited); internal-observer wording with the mandatory parenthesis; 60 s cerebellum check before K5. Work order 9 sent: agent 1 `BUILDER_PROMPT_WO9_M3E_ABLATIONS.md` (body-m3e: cb60 check, then A1-A3 ablations), agent 3 `_WO9_K5_TRAINER.md` (body-k5train: trainer, eval, Kaggle check; no launch). K5 launch decision is the overseer's after cb60 + Kaggle projections (tell the user).

**2026-11-05 ~15:20:** 60 s cerebellum check (7.20 point 4): rule verdict no growth; closed-loop held-out run shows a step up after ~25 s (0.0054 -> ~0.0087) that resets every 200 steps mostly remove (+10 %); clean open-loop check on 32 held-out babble trajectories (re-read open_loop_drift.json): continuous flat 0.0051-0.0054 over 60 s and below the reset run in every bin -> no state drift; the closed-loop rise is consistent with the policy's movements leaving the babble distribution. Report this in the WO9 brief (not a stop). Ablations A1-A3 running (hyst-wo9-m3e-chain-1449).

**2026-11-05 ~16:00:** K5 trainer (agent 3) verified (test_k5_train 9 OK rerun; bench files read: laptop 61.1 s/round, one pass + check 17.4 h; Kaggle T4 452 s/round, 7.4x slower at M3e's recipe) and merged (body-k5train 2793701). Path per 7.20.1: laptop. K5 launch prompt `docs/BUILDER_PROMPT_WO10_K5_RUN.md` sent to agent 3 at ~16:10 on the user's word, with the user's requirement: pause (freeze/thaw) and stop (graceful SIGTERM, per-round atomic checkpoint) at any moment, resume without loss. Kaggle large-batch/parallel path deferred (would change training; planner ruling needed). Ablations still running.

**2026-11-05 ~17:00:** M3e ablations (agent 1) verified (paired CIs recomputed; test_m3e 15 OK) and merged (body-m3e 7430377): none credited by the rule (external, argmax); internal decoding drops without closed-loop inputs (0.213) or internal observer (0.279); dopamine off slightly better (one seed). Brief `docs/PLANNER_BRIEF_WO9_RESULTS.md` sent. Agent 1 idle. K5: agent 3 still testing pause/stop before launch.

**Hourly wakeup:** session cron (WO8 prompt; see CronList) (fires ~:51 each hour after jitter; explicit resume/OOM-relaunch/handover prompt; dies with the session, recreate after restart). Claude-independent watchdog: systemd timer `hyst-overseer-watchdog.timer` every 15 min appends unit states, failures (oom-kill/exit-code), power and memory to `/secondary/hyst-data/overseer/watch.log` (script `watchdog.sh` there). Old handled failed units were reset-failed 2026-11-05 00:28, so any FAILED line after that is new. 00:25: builders 1, 2, 5 told to chain their remaining long runs into one detached service before the usage limit.

**Wakeups:** set a session cron after restart, e.g. hourly at :23: check agents/branches/units/uptime, resume stalled builders, hand dead ones
to blank agents, verify finished ones.

**2026-11-05 ~17:15:** K5 try 1 LAUNCHED by agent 3 (unit `hyst-wo10-k5run`, 6 threads, 8 GB cap, data `/secondary/hyst-data/body/k5/run1/`,
branch body-k5train 8092e21). Commands in `scripts/body/K5_RUN.md`: freeze/thaw/stop the unit; restart with
`.claude/worktrees/body-k5train/scripts/body/k5_run.sh start` (also after a reboot). Stops at the 24 h compute box, then k5_eval on best.pkl.
Deviation reported: cross-process runs differ by 4.0e-12 (XLA CPU float64 summation order); in-process resume bit-identical; test tolerance 1e-9.
Agent 3 reports at each validation (first ~round 200, ~3.4 h compute) and at the end. Planner WO9 rulings already in 7.21 (user re-pasted, matches).
Overseer watches with Monitor (watch_unit.sh), hourly cron at :23.

**2026-11-06 06:35:** K5 try 1 training pass complete (977/977 rounds, 13.15 h compute, early stop never fired). Validation ext (a) curve
(rounds 200/400/600/800/977): 0.5585, 0.5441, 0.5744, 0.5962, 0.6335; int (a) 0.510, 0.470, 0.539, 0.597, 0.639. best.pkl = round 977.
K5 check (1,071 windows; trained/untrained/kappa0; argmax+sampled) running in the same unit since 06:34. Next: verify per handoff step 1.
Overseer watcher: job tmp k5watch.sh (polls progress.json; the old watch_unit.sh missed a log line once).

**2026-11-06 07:25:** K5 check OOM-killed (hyst-wo10-k5run, 8 GB cap) during the kappa0 policy. best.pkl intact; eval/trained.json + untrained.json written. Agent 3 told to relaunch the check only (fresh unit, 14 GB), reuse cache only if resume-safe, reset-failed the old unit.

**2026-11-06 ~08:00:** K5 try 1 DONE and verified (per-song paired bootstraps recomputed from eval/*.json, all match; best.pkl round 977
was scored; test_k5_train OK). PASSES in argmax: ext 0.625 [0.603, 0.648], vs untrained +0.452, vs kappa0 +0.086; int 0.636, +0.496,
+0.177. Merged body-k5train e8cbba5 into body (b74da7d) and keys-decide. Brief `docs/PLANNER_BRIEF_K5_RESULTS.md` sent. Renders from
best.pkl NOT possible yet (no full-song rollout path; question 1 in the brief). WO11 seed 2 waits for the user's word.
Overseer slip: merging into body with `checkout -B body` in a temp worktree moved the branch under the existing `.claude/worktrees/body`
worktree; its index/tree are still at d5a1fae (staged reverse of the merge, no own changes). Fix needs `git -C .claude/worktrees/body
reset --hard HEAD`: ask the user (auto mode refused it). Lesson: merge into body inside the existing body worktree, never with -B elsewhere.

**2026-11-06 ~11:00:** planner answered K5_RESULTS = BRAIN_SPEC 7.22 (body 9f66459): K5 passes recorded, licensed wording, no program-choice wording (MI 0.037 < untrained 0.155); video path (WO12) before seed 2; toy seeds only; try 1 stands, K5-pass2 only on the user's wish. User: save state, DON'T START ANY WORK. WO12 prompt not written yet.

## When a builder says it finished

1. Check for new work: git log on the branch and on origin, the data folder, file times. A "finished" message can be stale.
2. git diff. Rules documents are unchanged, unless the user approved a note.
3. Run tests:
   - `cd scripts/brain && /secondary/hyst-env/brain/bin/python -m unittest` (about 150 tests, about 3 min);
   - for any Rust change: cargo test, clippy -D warnings and fmt --check on hyst-compile, hyst-output, hyst-previz and hyst-cli.
4. If dance code changed: v47 Off must be byte-identical. Run `bash $D/tracker-scratch/newsong/three.sh TAG`, and cmp against `$D/hexagon-47.html`, `$D/five-years-hexagon.html` and `$D/presence-hexagon.html`.
5. Recompute the key numbers yourself from the saved data. Never trust a report alone. Say plainly which numbers you could not recompute.
6. Check media before the user sees it, and send it with SendUserFile.
7. Merge into `keys-decide` and push.

## Open with the user

- **Go-ahead for work order 12 (K5 videos, 7.22 point 1), then WO11 seed 2.** Nothing starts before the user says so.
- The fallback videos (one arm, new camera): the user's verdict, and tuning the mapping by eye in the authoring tool.
- The monitor build waits for the user's choice of the planner's mockups; it shows only mechanisms in the loop plus labelled data lanes (7.19 D).
- The trace viewer `/secondary/hyst-data/brain/braindump/instant-crush.view.html` was never opened in a browser.
- Kaggle large-batch recipe: only as engineering, only if it first reproduces the toy result (7.21 point 4).
- **Housekeeping, only when the user says:** deleting merged branches (py-analyze, d3-layered, a-spread, b-clock, b1-pulse, b2-core, author-map,
  b3-corpus, b3-train, b3-pac, b3-round2, b7, body-h1..h4, body-m1m3, body-m3b, body-m3c, body-z, body-h2show, body-reeval, body-fallback,
  body-parity, body-k5data, body-tuning); fast-forwarding master; stale comments in `workspace.rs` and `lib.rs`.

## First reply

In a few lines:
- the state you found: git, running units (`systemctl --user list-units | grep hyst`), what is merged;
- what you are waiting for;
- what you need from the user.
