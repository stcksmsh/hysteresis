# Overseer handoff — 2026-11-09

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

## CURRENT STATE (2026-11-09 ~03:00, saved for an overseer clear) — read this first, then the dated notes below

**Rules of record:** `docs/BRAIN_SPEC.md` on body, latest **7.33-7.36** (7.33 pass2 rulings + user verdict "same shape repeated"; 7.34 new
direction: diagnosis + Stage 0 + Stage 1 + overseer operationalisation; 7.35 Stage 1 toy rulings (5 s z-score, arm 0, collapse
precondition); 7.36 Stage 0 rulings (closed; occupied cells replace dwell postures; Stage 3 2AFC interleaved; ceiling diagnosis)).
Reference only: `docs/RESEARCH_2026-11-08.md`. Toy rules: `docs/STAGE1_RULES.md`. Decisions go to the planner as briefs.

**Nothing is running.** Both builders idle: agent 1 [9ae40e] (did WO19 Stage 0 + WO21 ceiling), agent 2 [4cd51a] (did WO20 Stage 1).
Refs change on restart: use ListAgents. All builder branches verified and merged: body = 918f10a (body-k5p2, body-s0, body-s0b, body-s1),
keys-decide merged.

**WAITING: planner answers to `docs/PLANNER_BRIEF_STAGE1_RESULTS.md`** (sent to user ~02:50). Summary:
- Stage 1 (12 runs, `/secondary/hyst-data/body/s1/`): precondition NOT MET (occupied cells fail because the untrained toy arm is nearly
  still) -> no verdict. Informational: arms 0/i between-song JS ~ half-song control (pass2 signature); arm ii JS 0.77 (3.7x i) with D
  0.73/0.77; iii doubles cells; iv D 0.65-0.69 < 0.7. Toy arm i only partly collapsed (2AFC 0.70-0.86 vs pass2 0.49).
- Q1 recommends: pre-register collapse = between/half JS ratio <= 1.5 on both seeds, rerun all arms on FRESH seeds 2/3 (~1 h, agent 2,
  `scripts/body/s1_chain.sh` resume-safe; new seeds need a new output dir or seed option). Q2 ingredients after rerun (default ii + iii).
  Q3 report-only ACC_SHARE probe (generator acceleration cap 0.25 binds pitch joints 99.8 %). Q4 record partial-collapse caveat.
- When answers arrive: record as BRAIN_SPEC 7.37 on body (detached temp worktree, `git push origin HEAD:body`), BEFORE any run; then
  message agent 2 (rerun) / agent 1 (probe) only with the user's word.

**2026-11-09 ~09:20 — CURRENT (supersedes the WAITING item above):** planner answered the Stage 1 results brief = BRAIN_SPEC **7.37**
(body c013514): Q1 (a) rerun all 6 arms on fresh seeds 2/3, pre-registered precondition = arm 0 or i between/half JS <= 1.5 on both seeds
(cells + 2AFC reported only), pass rule = smallest of ii/iii/iv reaching >= 2x arm i JS with D >= 0.7 (iv >= 3x reported), seeds 0/1
informational; overseer operationalisation in 7.37.1 (seed means, D per seed) flagged amendable. Q2 default ii + iii. Q3 report-only
ACC_SHARE 0.25->0.4 / speed share 0.8->0.95 / both probe on M3f toy, hypothesis "cap sets the shape" untested, report vs per-joint servo
limits. Q4 partial-collapse caveat recorded. Prompts on body 7f1baee: `docs/BUILDER_PROMPT_WO22_STAGE1_RERUN.md` (agent 2, branch
body-s1r, cores 6-11, data /secondary/hyst-data/body/s1r/, ~1 h) and `docs/BUILDER_PROMPT_WO23_ACC_CAP_PROBE.md` (agent 1, branch
body-acc, cores 12-17, data /secondary/hyst-data/body/acc/, baseline = m3f/rerun4/seed0, 3 new seed-0 runs ~45 min each). SENT 2026-11-09 ~09:30 (user cleared both):
WO22 -> agent 2 [4cd51a], WO23 -> agent 1 [9ae40e], notify_when_idle both. Check first pushes of body-s1r / body-acc by ~10:00. Verify: WO22 rules section 11 + verdict script pushed before launch; WO23 default bit-identity, realised
joint acc/speed vs limits recomputed from rollouts.

**2026-11-09 ~09:45:** WO22 running (hyst-wo22-s1r, pre-run commit 3de54c7 checked: --seeds default 0,1; verdict script = 7.37.1, ref i
else 0). Seed 2 done: arm 0 JS ratio 0.93 (collapse ok), arm i 4.8 (not collapsed); D ii 0.689, iii 0.643, iv(.05) 0.589, iv(.5) 0.643 (all
< 0.7 on seed 2); seed 3 running, ETA ~10:15. WO23: identity control verified by overseer (origin/body vs body-acc epoch 0 identical except
secs); B retrained (overseer ruling: same code/threads/cores for all four); chain hyst-wo23-chain launched 09:41, ETA ~14:05.
LESSON: M3f training numerics depend on thread count (epoch-0 dec_e 1.9956 at 3 thr, 1.9924 at 6, 1.9983 at 8; calibration identical) -
never compare runs at different thread counts; retrain baselines at the probe's thread count.

**2026-11-09 ~10:20 — CURRENT:** WO22 DONE (agent 2, body-s1r 261c760, verified: diff = seeds option + new files + rules s11 + log;
test_s1r_verdict + test_s1_toy OK in separate processes; all 12 numbers recomputed, match), MERGED body 261c760, keys-decide. NO VERDICT
under 7.37.1 (arm 0 ratio 0.93/4.84, arm i 4.82/1.21). Brief `docs/PLANNER_BRIEF_STAGE1_RERUN.md` SENT (Q1 close Stage 1 informational,
Q2 ii alone default / D hinge for iii, Q3 record seed dependence). WAITING: planner answers; WO23 chain (hyst-wo23-chain, ETA ~14:05) ->
verify (recompute cap shares + realised joint acc/speed vs limits from rollouts) -> own brief. Agent 2 idle.

**2026-11-09 ~13:45 — CURRENT:** planner ruled the Stage 1 rerun = BRAIN_SPEC **7.38** (body f8eee24): Stage 1 closed without verdict
(four-seed table informational); forward = arm ii; route to iii = ii + iii with D >= 0.7 hinge (dual multiplier), toy check seeds 4/5
report-only; seed dependence recorded; thread-count rule (fix and state threads, compare only at equal counts). Next per planner: WO23
brief, then Stage 3 design (5-DoF run, human real-vs-swapped-music test) ruled with both. Prompt `docs/BUILDER_PROMPT_WO24_D_HINGE_TOY.md`
(agent 2, branch body-s1d, cores 6-11, data /secondary/hyst-data/body/s1d/, ~30 min) written, NOT SENT (waiting for the user's word).
WO23 chain: A1 + B done (B argmax ext 1.172 int 1.174 e'1 2.55 e'2 0.0013 programs 2; A1 ext 1.098 int 1.129 e'1 3.86 e'2 0.0334
programs 1), S1 running, AS next, ETA ~16:15.

**2026-11-09 ~14:30 — CURRENT:** WO24 DONE (agent 2, body-s1d 37080a3, verified: s1_toy.py diff keeps old path (dw None default), test_s1d
OK by overseer, all 6 result.json recomputed = builder's report), MERGED body 37080a3 + keys-decide. Held-out D ii .780/.767, iii .737/.752,
iii+D .790/.769 (s4/s5); cells ii 21/24, iii 44.5/44.8, iii+D 47.3/46.9; JS ratio ii 24/20.5, iii 11.2/11.9, iii+D 11.6/11.9; 2AFC iii+D
0.967; MMD ii .45/.51, iii .31/.32, iii+D .21/.22; mu_D only rises (ends 8.45/10.21). Plain iii also >= 0.7 on these seeds -> the hinge's
own effect is not isolated. NOT yet briefed: goes into ONE brief with WO23 (planner: WO23 brief, then Stage 3 design). WO23 S1 running,
AS next, ETA ~16:40. Both builders idle.

**2026-11-09 ~17:00 — CURRENT:** WO23 DONE (agent 1, body-acc 7d7c9d3; chain 09:41-16:23, report step crashed on rerun4_ref getattr, fixed +
rerun), verified (overseer recomputed realised joint speed/acc from rollouts with np.diff: speed + acc p99 match; acc single-sample max
method-dependent, B shoulder 1.008x by 2nd difference vs 0.805 central), merged body caca60d + keys-decide. Within limits on acc
everywhere; speed max 1.006 (A1) / 1.001 (AS). Raising ACC_SHARE moves joints acc-cap -> speed-cap; shoulder 99.6 % on acc cap always;
JS ratio 0.78-0.81 all settings; e'2 A1 .033 AS .048. Combined brief `docs/PLANNER_BRIEF_WO23_WO24_RESULTS.md` SENT (Q1 keep caps,
Q2 ii+iii+D with descending mu_D toy check, Q3 limit-check reporting, Q4 rule Stage 3). WAITING: planner. Nothing running; agents idle.

**Key verified results of this session:** pass2 (K5-pass2, best r600) passed its numeric bar (7.33) but the user rejected the videos;
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
