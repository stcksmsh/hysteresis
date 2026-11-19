# Night log: body-syncaudit-a (WO54 A1 + A4) — 2026-11-19

Rules `docs/SYNCAUDIT_RULES_A.md` pushed first. Report `docs/SYNCAUDIT_REPORT_A.md`. Out `/secondary/hyst-data/body/syncaudit/a/`.

- First measurement design (clicks every 0.5 s, +-0.75 s window) was contaminated by neighbouring impulses (sd 54 ms in the loaded motion itself). Redesigned: dense 3-8 s block (matched filter) + isolated clicks >= 1.7 s apart. Rules note deviation: irregular clicks are the isolated ones, not interleaved.
- Replicating `sim_file` needed three things: the per-window yaw/roll shift, `RR.patch_gates()` (WARM_S 1.5 s) and the float32 targets read from the T0 npz; the final replication equals the stored q50.
- V2 reads torso/head orientation, not the arm joints; pure yaw about y leaves the V2 up vector and the head unchanged, so the torso/pelvis/feet families use an off-axis rotation.
- Result: stages 1-6 add 0 ms, spinal layer +80-86 ms, limiter+servo q50 about +180-290 ms in total, rest exact (see report).
- Units: `hyst-wo54a-*`, MemoryMax 10G, cores 6-13. No pipeline code edited; no installs.
