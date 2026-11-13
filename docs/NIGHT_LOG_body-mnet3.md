# Night log, body-mnet3 (WO29C, motor-network toy test Part 3)

## MORNING SUMMARY

STOPPED FOR THE OVERSEER: 3 of 10 Part 3 sims failed the gates (limits and contact). Per the work order there is no redraw and no render yet.

- Prep done (5 songs): beat grids via `analyze_mix` (same as the corpus grids), cortex lanes via `k5_video_lanes` model (frozen B7 epoch 6), 12 s audio excerpts. Cores 6-11, 6 threads (torch), simulations single-threaded.
- Draw (seed 29031, shown S01-S10): 1 blue-lagoon S03 / S04; 2 schizoid-man S01 / S07; 3 epitaph S08 / S02; 4 breathe S03 / S05; 5 one-of-these-days S06 / S01.
- Failed: P3_1b (S04, blue-lagoon: contact 13 substeps, accel_ratio 1.18), P3_3b (S02, epitaph: contact 339, accel_ratio 7.32), P3_5a (S06, one-of-these-days: contact 180, accel_ratio 1.96, speed_ratio 0.55). Failed parts: contact and limits; clearance, end stop, hf, reversals and motion pass. Floor clearance 2-3 mm in all three.
- Passed: P3_1a, 2a, 2b, 3a, 4a, 4b, 5b.
- FOR USER/overseer: how to proceed (render the 7 and report the 3, change a gate, or a fixed redraw). Nothing was redrawn or changed. Part 3 is not complete, "PART3 READY" is not claimed.
- Not done: renders, manifest, part3_numbers.json, frame checks.

Code: `scripts/body/motornet_part3.py` (prep, clips, manifest), `motornet_part3_job.sh`. Data: `/secondary/hyst-data/body/motornet_toy/work3/` (outside git; no audio in git).
