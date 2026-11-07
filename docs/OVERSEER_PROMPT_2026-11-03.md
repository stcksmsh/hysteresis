Paste this to the overseer.

---

New direction from the user, 2026-11-03. Everything you need is in the repo package I am giving you:

- `docs/BODY_BRAIN_PLAN.md`: the work order from here on (decisions, rules, B7 close-out, the target machine, every step
  with its toy tests and checks fixed in advance, the truth table, the story, the unattended-work template). It wins over
  `NEXT_DECODER_THEN_BRAIN.md` and reopens nothing in BRAIN_SPEC B1–B7 except what its §2 records.
- `scripts/compute/`: tested scaffolding for running jobs on the laptop, Kaggle (free GPU) and later Modal: job runner,
  manifests, feature packing, code snapshots, Kaggle kernel builder. `python -m unittest -v test_compute` passes.

Do this, in order:

1. Cut branch `body` from `b7`. Copy the package files in at the same paths. Run the compute tests. Commit (plain message).
2. Write §2 of the plan into BRAIN_SPEC §7 as a dated note (B7 close-out). Commit and push `body`.
3. Read the whole plan. If anything in it is wrong against the code as it stands (paths, names, shapes, a rule that
   cannot be met), write it as a short list for me before building. Do not silently change a rule.
4. Write the builder prompt for the first work order: **step Z (Z1–Z5) and M0 + M2, locally**, using the plan's §12
   template. Everything in it runs on the laptop CPU except the two Kaggle benchmark jobs, which need my Kaggle account
   first. Give me the list of user tasks (Kaggle account, phone verification, API token) at the top, so I can do them
   while the builder works.
5. In parallel, if a second builder is free: H1 (plan §5), toy only, 2 × 3 h.

Report back after the first work order with: the compute test results, the two benchmark numbers (or what blocked them),
M0's numbers (masses with their basis, gravity sag, limit tests, CPU/MJX parity), M2's tests, and any FOR USER items.
Same rules as always: no claims without a passed check, never say it looks better, recompute the builder's key numbers,
no spending, no attribution lines.
