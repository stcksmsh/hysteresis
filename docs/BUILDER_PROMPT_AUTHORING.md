Your next task from the Hysteresis overseer: the authoring tool on B3's lanes. This is design work, with no rules and no claims. If a brain training job is running (check `systemctl --user list-units | grep hyst`), do not touch it.

Repo /secondary/Programming/Github/Hysteresis, remote branch keys-decide at 46194d9 or later.
- Make a new worktree and branch `author-b3` from origin/keys-decide, separate from your B7 worktree.
- Never touch master, frozen src/ or tools/.
- Commit messages plain, no co-author or attribution lines. Push your branch; do not merge.
- Do not edit rules documents.

Read first:
- docs/NEXT_DECODER_THEN_BRAIN.md §2, the note "The authoring tool on B3's lanes (… 2026-11-01)". It is your spec; follow it point by point. Also the pivot text just above it.
- scripts/author/README.md and the code in scripts/author/: the existing page, built on B2's lanes.
- The mindState field and how lanes reach a sidecar: grep for mindState in scripts/ and crates/hyst-compile.
- docs/BRAIN_SPEC.md §5 and §7.6 for lane names.
- B3 lanes come from /secondary/hyst-data/brain/b3r2/ckpt/phase/best.pt (round 2, epoch 12), through scripts/brain (check_b3.py / b2.py surprisal_lanes and band power).

Deliver, per the ruling:
1. **Re-point the page** to B3 round-2 lanes, computed for Instant Crush, Five Years and Presence from their audio. Find the audio and sidecars the B2 build used.
   - Inputs: smoothed surprisal, L4 predicted variance, surprisal slope (30 s), raw surprisal, the surprisal spike with a source selector (total / L1 / L2 / L1+L2, default L2), band power L1..L4, and mood.energy from core-2b.
   - Write the lanes into each song's sidecar `mindState` with mechanism names, rate and source.
2. **Data-driven input list:** the page builds its sliders from the lanes present in `mindState` (name, rate, source). No hard-coded list and no empty slots.
3. **Names:** on the page, the mechanism name first and the nickname in brackets, exactly as the ruling lists. Exported JSON and mindState use mechanism names only.
4. **Per-input response curve:** gamma 0.3–3, default 1, applied after normalisation and before the weights.
5. **"Render window" button:** compiles the arm preview for the current 20 s window only (Layered + Music, current mapping) and shows it in the page. Reuse the existing export/attach/ensemble_preview path, restricted to the window. Measure the round-trip time, from slider change to visible window preview, on this machine.
6. **One global mapping preset** for all songs, with save and load (JSON). Per-song tweaks go through the existing `authored` field.
7. **A five-line how-to** at the top of the page.
8. **Tests:** extend test_author.cjs and test_attach.py for every change, including a mindState with an extra unknown lane (it must appear as a slider) and the gamma curve. Run the node and Python tests. If Rust changes, run cargo test, clippy -D warnings and fmt --check on hyst-compile, hyst-output, hyst-previz and hyst-cli.
9. **Version 47 untouched:** run `bash $D/tracker-scratch/newsong/three.sh TAG` and cmp the three outputs against $D/hexagon-47.html, $D/five-years-hexagon.html and $D/presence-hexagon.html.
   - D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm.
   - A shell guard refuses commands that mix the $D path with pipes, &&, loops or heredocs: put such steps in a script file.
10. **Proof of the path:** one exported full-song arm preview per song from the neutral mapping. Put outputs under /secondary/hyst-data/brain/author/; data stays outside git.

Machine rules:
- If training runs, use at most 4 threads for the lane computation.
- Any job longer than a minute runs in a scope: `systemd-run --user --scope -p MemoryMax=6G -p MemorySwapMax=0 --unit=hyst-author-<name> bash script.sh`.
- Python env for brain code: /secondary/hyst-env/brain/bin/python.

When done, report to the overseer (SendMessage to "Hysteresis ovserseer") in a few lines:
- the commit hash and test counts;
- the round-trip time;
- the paths of the page and the three previews;
- the v47 cmp result;
- anything in the ruling you could not do, and why.
