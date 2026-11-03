# Overseer handoff — 2026-11-03

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

## Where things stand (2026-11-03, after the planner's new plan)

**New direction (user, 2026-11-03): `docs/BODY_BRAIN_PLAN.md` is the work order.** It wins over NEXT_DECODER's next steps. Goal: a scaled
human brain + body that drives itself (cortex = B7 epoch 6, frozen; MuJoCo body; cerebellum; spinal oscillators; basal ganglia/dopamine via
PPO; monitor B5). The authoring tool is the last-resort fallback only. Order: Z -> M0 -> M2 -> M1 -> T-M3 -> M3 -> M4; H1 and B5 in parallel.

- **Branch `body`** (cut from keys-decide, which = b7 + docs; pushed). keys-decide is fast-forwarded to it. Holds the plan, `scripts/compute/`
  (test_compute 12/12 pass), BRAIN_SPEC §7.11 (B7 close-out: round 2 not taken, epoch 6 is the cortex of record, warm-start LR rule).
- **Builder prompts ready, not sent:** `docs/BUILDER_PROMPT_Z_M0_M2.md` (branch `body-z`; user tasks at top: Kaggle account, phone, token),
  `docs/BUILDER_PROMPT_H1.md` (branch `body-h1`, toy only, 2 x 3 h). Send only when the user says, to the agent they name.
- **Planner brief sent to the user:** `docs/PLANNER_BRIEF_BODY_PLAN_CHECK.md` (11 mismatches, 3 questions: implement mass, ±180° cap, B7 lane
  export timing). Defaults are in the prompts. Waiting for the answer.
- Nothing running. B7 results are in BRAIN_SPEC §7.11 and the plan §2/§10. `docs/BUILDER_PROMPT_AUTHORING.md` is obsolete (plan §0.2).
- The planner's zip is at the repo root (`hysteresis_body_brain_2026-11-03.zip`, untracked); its content is committed on `body`.

## Your first job

- When the user says go: send the two prompts. Verify each report as below, recomputing M0 numbers (sag, torque margins, CPU/MJX parity) and
  benchmark numbers from the saved files.
- Record the planner's answer to the plan-check brief as a dated note in BODY_BRAIN_PLAN or BRAIN_SPEC before any result it scores.
- Report back to the planner after the first work order (OVERSEER_PROMPT_2026-11-03.md lists what it wants).

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

- The planner's answer on B7 (above).
- The B3 round-2 rulings text, if it exists.
- The watch verdict on `$D/watch/`.
- When to start the authoring tool. Also the blind second viewer (ruled as advice only, informal protocol in NEXT_DECODER §2): the user may bring someone in.
- **Housekeeping, only when the user says:**
  - deleting merged branches: py-analyze, d3-layered, a-spread, b-clock, b1-pulse, b2-core, author-map, b3-corpus, b3-train, b3-pac, b3-round2, b7;
  - fast-forwarding master;
  - the stale comments in `workspace.rs` and `lib.rs`.

## First reply

In a few lines:
- the state you found: git, running units (`systemctl --user list-units | grep hyst`), what is merged;
- what you are waiting for;
- what you need from the user.
