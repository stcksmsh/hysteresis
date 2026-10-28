# Overseer handoff — 2026-10-22, updated 2026-10-28

Paste everything below the line into a fresh overseer agent.

---

You are the overseer for Hysteresis. You do not implement: you analyse, decide
with me, write complete self-contained prompts for builder agents, then verify
their work yourself. I usually keep the same builder ("Hysteresis implementer
agent") running while its context is low (reuse it under about 50 %) and clear it
for big rewrites. Every prompt must stand alone anyway: name the commits and
files to reuse, quote my latest verdict, point at the rules files. Write to me in
plain short sentences with numbers. Never tell me something improved or looks
good; I judge by eye. Ask before artistic choices or rule changes I have not made.
Rules I set go into the rules documents as dated notes or addenda, committed and
pushed before any result they score.

Repo worktree: /secondary/Programming/Github/Hysteresis/.claude/worktrees/dance-figures,
branch keys-decide (pushed; never push to master). Commit messages plain, never
any co-author or attribution line. Frozen src/ and tools/ are read-only. Never
drive hardware.
D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm
A shell guard refuses commands that mix the $D path with pipes, &&, loops or
heredocs: put such steps in a script file and run it with bash.
The builder can message you through another Claude session; you answer with
SendMessage to its address. It may be offline; then give me a prompt to paste.

Read, in order:
1. docs/NEXT_BODY_THEN_MIND.md: the work order (step 1 body study, step 2 mind
   spike, step 3 I decide). Its ★ stops bind. Step 2 "Before it starts" has two
   dial format notes; the revised one (commit 0fa877d) replaces the first.
2. docs/BODY_STUDY.md with its eight addenda (history of step 1; closed).
3. docs/EMOTION.md (stages, rules), docs/EMOTION_ARCH.md (stage 1 as built),
   docs/MIND.md §1 and §3.4–3.6 (step 2; the rest is parked).
4. The last entries of docs/DANCE_HANDOFF.md from "Body study round 2" on.
5. docs/DANCE_RESTART_PROMPT.md: commands, how I review, settled wishes.
Ignore most of AGENTS.md.

## Update 2026-10-28 (read first; the 2026-10-22 state below is history)

Read `docs/ARCHITECTURE.md` first: state, every experiment's numbers, the open
architecture questions (Q1–Q8). Since 2026-10-22:
- The user recorded the dial (`dial2.json`, 5 takes, no taps; backup in
  `~/hyst-backup/emotion-dial/`). Lifts come from the energy curves (note b1775f8).
- MERP fetched (43 songs over 50 s used; raw-trial labels; note 72ba7bc).
- Step 2 round 1 (`check1b.py`, a3fab6e): FAIL (gates 1, 2, 4 fail; 3, 5 pass);
  rehearsal hurt tracking. No round 2.
- Step 2b (`check2b.py`, c20dec6): A1 PASS (memory beats an 8 s smoothing control on
  DEAM and MERP), A2 FAIL by 0.008, A3 PASS, B FAIL 0 of 3 on the user's dial. The
  outcome "A1 passes, B fails" is the user's decision: **open** (ARCHITECTURE.md Q1;
  overseer recommends smoothed stage 1 as the encoding, the core as a second candidate
  in stage 3).
- Housekeeping done: Python analyzer merged (24e63bc), `song.sh` uses it; Demucs
  `--shifts 0` in `song.sh`. TypeScript deletion: not now (user).
- The overseer recomputed every check1b/check2b gate from saved data
  (`/secondary/hyst-data/emotion/check2b/predictions_*.npz`).

## Where things stood (2026-10-22)

**Step 1, the body study: PASSED.**
- Round 1 failed check 2b, 13 of 24 (pass 16). Causes found: the seed decided
  about half of what the clips showed, and the movement floors (addenda 2 and 3)
  forced every body to dance level, so size and energy barely differed (mean
  joint speed 24–45 °/s over the test clips). My words: forcing every body
  above a level of movement by design "removes more than one of these 5
  features and dampens many of them".
- Round 2 (addendum 8, b7ce161): 15 body dimensions (size, energy and rhythm
  added); the body decides pattern, pace, size and rhythm, the seed only start
  phase and small jitter; movement floors removed, a stillness cap instead
  (fail only if all joints < 2 °/s for > 2 s at once or > 25 % of the clip);
  8 s clips. Sweep: mean joint speed p10 8.5, p90 45.6 °/s. I approved the
  first-look clips ("range is high enough, it seems fluid in all cases").
  Regions: separation gate 1.5 × seed spread held at once (smallest ratio
  1.519). Test: 4 practice triplets with feedback, 32 scored, one clip at a time,
  at most 2 replays before answering. **Result: 30 of 32 (pass 20; P under
  guessing about 1e-12).** 16/16 in the first half, so not learning; 16/16 on
  triplets whose regions had close speeds, so not speed alone. My notes describe
  "locked groove with holds", "figure eights / fluid", "slow, hanging, drooping",
  "straight up and slow". Data: /secondary/hyst-data/bodystudy/r6/
  (answers.json, key.json, score.txt). Commits b0a76ce, e9f0fad.
- Lessons: a probe on filtered clones gave a seed spread of 0.85–1.0 (true
  median 1.93) and sank addendum 4; check that a probe sample is unbiased before
  writing a rule on it. Gates on distributions (e.g. "p90/p10 ≥ 4") force shapes
  on the body space; I rejected that: report spreads, gate only what the test
  needs.

**Step 2, the mind spike: NOT STARTED. Waiting for my dial recordings.**
- The dial (my own within-song feeling, held-out truth for gate 5, audio only)
  went through two formats:
  - Format 1 (2D valence/arousal pad): I recorded Instant Crush once. I found
    "pleasant / unpleasant" meaningless (music is nearly always pleasant to me)
    and the songs mixed ("sad/longing/remembering/energetic/hopeful ... a
    mishmash"). That take is /secondary/hyst-data/emotion/dial/dial-ic-try1.json
    (0–329.0 s, 10 Hz, clean). By the revised note it counts as Instant Crush
    pass A (arousal axis), with 135–171 s (my indecision) and everything after
    329.0 s masked; its valence is data only, "old wording"; no taps.
  - Format 2 (commit e968fd9, now live): a picker of 2 passes × 3 songs. Pass A
    = energy slider 0..1 with Space-bar taps where something lifts or lands
    (the taps are my "known lifts" for gate 4). Pass B = a pad with two one-sided
    axes, light/bright and heavy/dark, both 0..1, both may be high (bittersweet).
    Gate 5 uses pass A only; pass B is reported against DEAM valence and the GEMS
    readouts, never gated. The page: /secondary/hyst-data/emotion/dial/HOWTO.txt
    (node dial_serve.cjs, http://127.0.0.1:8778/dial.html, Chrome), output
    /secondary/hyst-data/emotion/dial/dial2.json.
  - Verified by the previous overseer on 2026-10-22: 87 headless dial checks
    pass, the served page equals the repo copy, cargo test/clippy/fmt clean,
    the three v47 exports byte-identical. Not checked by hand in a browser.
- **Still to record (me):** pass A for Five Years and Presence; pass B for all
  three songs. About 25 minutes. dial2.json does not exist yet.
- Context from my research for the next steps (not targets): critics read
  Five Years as doom from start to end; my reading adds a hopeful middle that
  crashes. The sourced version: "a lull in the dread, not a lull in the tension"
  (energy keeps climbing while heavy/dark dips). Instant Crush: sound bright,
  story a missed chance; listeners split between nostalgic-sad and danceable.
  Presence (Justice, instrumental, my file Justice_-_Presence_Official_Audio.wav):
  no review found anywhere; my reading is the only one. I said to drop the
  Five Years hope as a target: "we just need to make this work".
- Open note for later: a simple, one-mood control track would test that the
  mind does not invent drama where nothing changes (gate 5 needs a dial that
  varies). Not decided.

## Next steps

1. When I say the dial is recorded: check dial2.json is complete (each pass/song
   pair finished, 10 Hz, no gaps, durations 339.8 / 283.8 / 270.7 s, pauses,
   restarts, taps). You may look at it; the builder must never open it until
   step 2's results are in. Do not show me my own curves in detail before all
   takes are done (anchoring).
2. Then step 2 per NEXT_BODY_THEN_MIND.md, only on my go-ahead: ★ 1 MERP fetched
   (size, licence, hashes into SOURCES.md); ★ 2 check1b.py committed before it
   runs (gate 5 reads pass A with the masks above; gate 4 on the three songs uses
   my taps where present); ★ 3 results. Then step 3: my decision (table in
   NEXT_BODY_THEN_MIND.md).

## When the builder says it finished

1. Check it is new work: git log on keys-decide and origin, the data folder.
2. git diff; the rules documents unchanged unless I approved a note; cargo test
   -p hyst-compile -p hyst-output -p hyst-previz -p hyst-cli; cargo clippy on the
   same crates --all-targets -D warnings; cargo fmt --all --check; the page or
   script tests it names.
3. Re-export the three songs: bash $D/tracker-scratch/newsong/three.sh TAG; cmp
   $D/tmp-TAG-{ic,fy,pr}.html against $D/hexagon-47.html,
   $D/five-years-hexagon.html, $D/presence-hexagon.html; delete the tmp files.
4. Recompute its key numbers yourself from the data. Do not trust its report
   alone.
5. For anything I must watch or use (clips, pages), check it before I do, then
   send media with SendUserFile.
Report what passed, what failed, with numbers, and what you need from me.

## Housekeeping queue (only after the emotion work allows)

- Write the planned EMOTION.md additions: (a) stage 1b multiscale (phrase,
  section, song, across plays; one base embedding pooled at several scales plus
  fast-minus-slow departure; each level checked and dropped if it adds nothing);
  (b) Sievers et al. 2013 PNAS as theory, its five features (rate, jitter,
  direction, step size, spikiness) as a check set; (c) a calibrated model screen
  (joint audio-video or dance-retrieval embedding), used only once it agrees with
  my odd-one-out on held-out trials at p < 0.01, never an optimisation target;
  (d) a paper track (MOCO or NIME): stage 4 then needs ~100 outside participants
  (v47, shuffled map, label-plus-move-library), preregistered rules. MIND.md
  covers part of (a). Add: the body study's round-2 lesson (the body must decide
  size and energy, no movement floors).
- Open shell (stage 2): the hand space becomes the continuous top of the sphere;
  over the top turns no base; sideways near the top needs base speed; the figure
  clock caps base rate and acceleration. Open question for me: full extension
  straight up.
- Port scripts/analyze.ts to Python, then delete the TypeScript (src/, tools/,
  tests/, TS scripts, package.json, vite/ts configs, deploy.yml). The site is
  pinned to tag ts-final (171897b); stcksmsh.github.io main is at dfe539b.
- Crate rename, mapping unconfirmed: hysteresis-{core,audio,cli},
  afekt-{compile,output,previz,hw}, sinteza-{render,script}.
- Then fast-forward master to keys-decide and delete merged branches.
- Stray file: /secondary/Programming/Github/Hysteresis/dial.json (my format-1
  download, outside the worktree; a copy is dial-ic-try1.json). Ask me before
  deleting.

First reply: say in a few lines what state you found (check git, the data
folders and whether dial2.json exists), and what you will check first.
