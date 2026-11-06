# K5 run: the four commands (WO10)

Run directory `/secondary/hyst-data/body/k5/run1/` (log `run.log`, `progress.json`, `ckpt.pkl`, `best.pkl`, then `eval/`). Unit `hyst-wo10-k5run`. Provisional servo model: Feetech STS3215 12 V assumed. One arm.

| Want | Command | What happens |
|---|---|---|
| **Pause** (now) | `systemctl --user freeze hyst-wo10-k5run` | Instant. The CPU is free, the 8 GB stays held. Paused time is not counted as compute. |
| **Continue** | `systemctl --user thaw hyst-wo10-k5run` | It carries on exactly where it was. |
| **Stop** | `systemctl --user stop hyst-wo10-k5run` | It finishes the round in progress (about 60 s), writes the checkpoint and exits cleanly. In a validation or in the K5 check it stops after the current 64-window batch (up to about 1 min); an unfinished validation is run again on the next start. Waits up to 180 s, then kills; even a kill loses at most the round in progress. |
| **Start again** | `/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-k5train/scripts/body/k5_run.sh start` | Reads the last checkpoint (`ckpt.pkl`, else `ckpt.prev.pkl`) and goes on. The result is bit-identical to a run that was never stopped (tested). Safe to repeat: after the pass it runs the K5 check; when everything is finished it only reruns the check from its saved parts. |

The same four are `k5_run.sh pause | continue | stop | start`; `k5_run.sh status` shows the state, the log tail and `progress.json`.

- Checkpoint after **every** round (about 61 s): written to a temp file, fsynced, renamed; the previous one is kept as `ckpt.prev.pkl`.
- On battery the run waits at the next round boundary and goes on when the charger is back; it also refuses to start on battery. That time is not counted.
- Compute spent (`progress.json` `spent_h`, and in each checkpoint) counts wall seconds while running on mains; frozen or waiting time is excluded. The run stops at 24 h (BRAIN_SPEC 7.20 point 1) and then runs the check on `best.pkl`.
- After a reboot or a session loss: run `k5_run.sh start`.
