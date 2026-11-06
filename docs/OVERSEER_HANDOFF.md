# Overseer handoff — 2026-11-06

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

## Where things stand (2026-11-06 ~11:00, saved on the user's word: "don't start any work")

**Goal (user, BRAIN_SPEC 7.19):** a scale human, ONE arm. The brain's own encodings (B7 epoch 6 lanes) drive it, no emotion decoding. It learns to
move so that its inner state can be read from its body. Every mechanism shown or claimed is in the loop that moves the arm, or is a labelled data
lane. ARGMAX mode for every claim (sampled reported only). The installation is ONE arm, permanently (no hexagon, no ensemble; v47 hexagon files
are only the byte-identical regression reference).

**Rules of record:** `docs/BRAIN_SPEC.md` §7.17–7.22 (read all six first; 7.19 = goal, K5 bar and claims; 7.20 = K5 compute and ablation
wording; 7.21 = seed-2 credit rule; **7.22 = K5 try 1 rulings, the current orders**). Branch of record `body` (origin 9f66459);
`keys-decide` = body + overseer docs. Never master.

**K5 try 1: DONE, PASSES, verified, merged (body b74da7d, 7.22 recorded in 9f66459).**
- One full pass, 977 rounds, 13.15 h of the 24 h box; early stop never fired; best.pkl = round 977. Validation ext (a) at rounds
  200/400/600/800/977: 0.558, 0.544, 0.574, 0.596, 0.634 (still rising).
- Check on 357 held-out songs, argmax: ext (a) 0.625 [0.603, 0.648], vs untrained +0.452 [0.435, 0.470], vs kappa 0 +0.086 [0.073, 0.099];
  int 0.636 [0.613, 0.659], +0.496, +0.177. MI 0.037 (untrained 0.155). Overseer recomputed all paired per-song bootstraps from
  `/secondary/hyst-data/body/k5/run1/eval/{trained,untrained,trained_kappa0}.json` (script was job-tmp `k5verify.py`: per_song lists, paired
  difference, 10,000 resamples). Brief `docs/PLANNER_BRIEF_K5_RESULTS.md` sent and answered (= 7.22).
- Licensed wording (7.22): "It learned to move so that its inner state can be read from its body, by you and by itself" (record: both read the
  same joint positions); "it moves in time with its own inner rhythm". NO wording that its choice of movement follows its inner state.
- Data: `/secondary/hyst-data/body/k5/run1/` (best.pkl, ckpt.pkl, progress.json, run.log, check.log, eval/). Run/check commands in
  `scripts/body/K5_RUN.md` (`k5_run.sh start|check`). The check OOM'd once at 8 GB (trainer alive in the same cap); fixed (chain now exec()s).

**Running now:** nothing. Agents 1–5 idle (agent 3 asked for a render order; not answered on purpose). User said: DON'T START ANY WORK until
they say so.

**Next, in order (only when the user says go):**
1. **Work order 12: the video path (7.22 point 1), before seed 2.** Write `docs/BUILDER_PROMPT_WO12_K5_VIDEOS.md` (not written yet), for agent 3
   (knows K5 code; branch e.g. `body-k5video` from body). Contents from agent 3's FOR OVERSEER: (1) export the three danced songs' B7 lanes in
   K5 format (the danced songs are Instant Crush, Five Years, Presence; their fallback 720p videos are in
   `/secondary/hyst-data/brain/author/tuning/720p-cam/`); (2) full-song rollout of best.pkl, carry kept continuously across the whole song
   (no resets), 30 s causal normalisation running throughout, write the joint CSV (`arm_sim.csv_text` exists); (3) render with the one-arm
   camera of the authoring tool (agent 5 built it in WO6/WO7 tuning: `scripts/author/retune.sh`; find the render entry point there and name
   it in the prompt), next to the fallback videos; (4) report-only: external and internal (a) per 60 s segment across each song.
   Pausable/stoppable runs, mains only, own memory cap, push before long runs. Verify: CSV durations = song durations, videos looked at,
   720p copies < 30 MiB for SendUserFile.
2. Then send agent 1 `docs/BUILDER_PROMPT_WO11_SEED2.md` as written (toy seeds only: seed 2 of M3e try 1 and A1–A3), apply the 7.21 credit
   rule. No second K5 seed unless wording needs it.
3. K5-pass2 only if the user, after watching, wants better movement (7.22 point 3): separately labelled, own full K5 check, never replaces try 1.

**2026-11-06 ~12:00:** user: two fresh agents available; Kabl work will share this machine, so WO12 and WO11 run SEQUENTIALLY (WO11 only after WO12 reports). WO12 prompt written and pushed: `docs/BUILDER_PROMPT_WO12_K5_VIDEOS.md` (body 6e65bdf), share 6 threads / 6 GB, branch `body-k5video`, for a fresh agent (pasted by the user; agents offline in ListAgents). Found: no joint-CSV renderer exists; WO12 step 3 asks for the smallest additive one, v47 cmp required. Body worktree index slip FIXED (user OK, reset --hard HEAD, clean).

**2026-11-06 ~13:00:** WO12 DONE (agent 1 [c3fea2], body-k5video 722fe13), verified by overseer: test_k5_video OK (lanes bit-identical vs stored check song 009900; full-song first 60 s bit-identical vs K5 eval window), v47 regression identical 3/3 (fresh CARGO_TARGET_DIR), previz clippy/fmt clean; 9 videos durations = audio within one frame, 720p files < 30 MiB; frames looked at. Merged: body = 722fe13 (ff), keys-decide 86e782b. Side-by-sides sent to the user. FINDING: check-csv refuses all three songs; floor rule broken in 91-97 % of rows (worst -0.72 m), hand speed up to 2.4 m/s (limit 1.2). Overseer FK on instant-crush joints: hand z median -0.28 m, min -0.61, max +0.60 vs base; shoulder -91..+93 deg. Cause: MuJoCo arm has no floor; K5 has no floor/hand-speed term. Frames show the arm through the floor (Presence 200 s). Per-60 s (a) all 16 segments > 0 both decoders (lowest IC 0-60 ext 0.135). Outputs /secondary/hyst-data/body/k5/danced/. WO11 sent to agent 2 [4ae253] ~13:00 (sequential order met). Next: user verdict on videos; then planner brief on the floor finding (K5-pass2 needs a floor + hand-speed term, 7.22 point 3) if the user wants.

**2026-11-06 ~15:15:** WO11 DONE (agent 2 [4ae253], body-m3e 885a982), verified: paired try1-ablation intervals recomputed from a_gaps for both seeds (all match), diff = new files + run_m3e --seed (default 0 = try 1), tests 15 OK. Merged body 885a982, keys-decide. Verdict per 7.21: all three "present", none credited; dopamine not shown to lower. Seed-2 try 1 ext 0.763, int 0.602. Brief `docs/PLANNER_BRIEF_WO11_WO12_RESULTS.md` written and sent (Q1 record WO11, Q2 K5-pass2 floor/speed design, Q3 toy first, Q4 no 60 s wording). Agents 1 and 2 idle. Waiting: user verdict on videos, pass2 wish, planner answers.

**2026-11-06 ~15:40:** planner answered WO11/WO12 = BRAIN_SPEC 7.23 (body 457b06f): WO11 recorded (none credited); K5-pass2 REQUIRED (floor plane at mount height with contact, self-collision, check-csv hand-speed/jolt soft penalties weighted like energy, rig joint ranges); pass2 bar = full K5 bar + check-csv passing on the three danced songs; order: M3e toy with new body (2 h) first, then pass2 (24 h box). Mount question asked to the user (plinth/table/hanging + height); default floor z = 0. K5-only 720p videos sent. Next: WO13 prompt (new body + toy), waiting on the user's mount answer / go.

**2026-11-06 ~16:10:** user verdict on K5 try 1 videos ("something musical, but spastic"; arm through the base; mount = table or pillar) and the planner's pass2 design = BRAIN_SPEC 7.24 (body 9acbf19), with overseer defaults for (e) (Welch 4 s, >3 Hz share, four non-roll joints; v47 = mean over six arms; grid selection rule) flagged for planner confirmation. WO13 prompts (body 90607c5): 13A `BUILDER_PROMPT_WO13A_HF_REFERENCE.md` -> agent 1 [c3fea2] (branch body-hf, 4 thr/4 GB, hf_share.py pushed within 1 h), 13B `BUILDER_PROMPT_WO13B_M3F_TOY.md` -> agent 2 [4ae253] (branch body-m3f, 8 thr/14 GB; contact cost + pass2 projection first, report if > 22 h). Both sent ~15:45 (clock; an earlier note said 16:10 by mistake), notify_when_idle.

**2026-11-06 ~16:05:** WO13B contact cost: per toy epoch old body 39.4 s, v2 (friction, condim 3) 91.3 s, v2f (frictionless, condim 1) 62.9 s; pass2 upper-bound projection 30.6 h (v2) / 21.1 h (v2f). Overseer approved v2f as default (a passing policy keeps 5-11 cm clearance, contact is only a stop) - FOR USER/planner: friction off. Overseer ordered jerk/hand-speed/jolt normalisation by the untrained policy's OLD-body value (new-body untrained jerk ~1e9 is contact-spike dominated vs 2e6). One K5 round with v2f to be timed before pass2.

**2026-11-06 ~18:00:** WO13A DONE (agent 1, body-hf 731675f), verified: diff = new files only, test_hf_share 7 OK, K5 (e) values recomputed independently (match). Merged into body. v47 (e) reference 0.002970 (IC 0.002419, FY 0.002828, PR 0.003662), limit 0.003712. PROBLEM: K5 try 1, judged spastic by the user, has (e) 0.002660 < limit, so (e) as defined would pass it. Overseer exploration (report only, v47 arm 0 vs K5): joint-space measures (accel share >3 Hz, jerk/vel, speed peaks, reversals) do not separate; hand-space ones do: hand acceleration p99 K5 10.2/11.0 m/s2 vs v47 4.2/5.9 vs fallback 3.4/3.7 (IC/PR); share of time hand > 1 m/s K5 0.16/0.11 vs v47 0.01/0.014. Needs a planner/user ruling on (e) before the WO13B grid selection (grid ETA ~20:40).

**2026-11-06 ~18:30:** planner ruled on (e) = BRAIN_SPEC 7.25 (body f667d04): (e) replaced by (e'1) hand-acc p99 and (e'2) share hand speed > 1 m/s, each <= 1.25x v47 (limits computed by overseer: IC 5.320/0.01210, FY 5.182/0.00661, PR 7.501/0.01431, toy 6.001/0.01101; docs/hf_v47_eprime_reference.json); v2f and old-body normalisation confirmed; contact time reported. Overseer did not read grid (e') values before the ruling. Agent 2 told to select by 7.25 after the grid and continue to try 1, controls, ablations. Agent 1 idle.

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
