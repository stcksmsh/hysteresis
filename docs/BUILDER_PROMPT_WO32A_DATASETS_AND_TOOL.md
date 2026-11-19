# Builder prompt: work order 32A, dance dataset downloads and look-test session tool (2026-11-13)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER" instead of
waiting. You start with no context: everything you need is named below.

One arm only (permanent rule). No training of any kind, no verdict. Kosta (the user) judges blind. A second builder (32B) retargets FineDance
motion onto the arm and **waits for your step 1**.

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works. Retry on a GitHub server
  error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:**
  - `src/` and `tools/` are read-only. Never drive hardware.
  - Data, audio, video and models stay outside git. Never upload or redistribute any dataset content (BRAIN_SPEC 7.50.3).
  - No accounts, logins, forms, agreements, emails or client installs. Never send the user's name, email or project details anywhere.
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-data origin/body`, then push `body-data`.
- **Jobs:** long downloads or tests run detached and memory-capped:
  `systemd-run --user --unit=hyst-wo32a-<fresh-name> -p MemoryMax=6G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`.
  Cores **12-17** (`taskset -c 12-17`), never 6-11 (32B's). Check free disk on `/secondary` before each download and log it.
- **Push** within 30 minutes and after every phase. Log: `docs/NIGHT_LOG_body-data.md` (new; MORNING SUMMARY on top).
- **Environments:** body `/secondary/hyst-env/body` (numpy, scipy). Install nothing. If a download needs a package that is not installed
  (e.g. `gdown`, `huggingface_hub`), STOP and log FOR USER.

## Read first

- `docs/BRAIN_SPEC.md` **§7.50** (binding: approved downloads, the STOP rule, storage, obligations) and §7.49.
- `docs/DATASET_LICENCES.md` (official links for every dataset).
- `scripts/body/dialstudy_session.py`, `motornet_report.py`, `test_dialstudy.py`, `test_motornet2.py` (the blind session tool to extend).

## The work

1. **FineDance first** (32B waits on it): the public part (7.7 h) from the official links in the FineDance README
   (github.com/li-ronghui/FineDance).
   - **STOP rule (7.50.5):** if the download needs an account, login, a form, Baidu NetDisk, a client install, or anything beyond a plain
     HTTP(S) fetch or a public Google Drive file reachable without login, STOP and log FOR USER. Write "FINEDANCE BLOCKED <reason>" in the
     night log and push, so 32B switches to Motorica. Then go on with the next dataset.
   - Store under `/secondary/hyst-data/datasets/finedance/`: the data as published, the LICENSE text saved as `LICENSE.txt`, and
     `SOURCE.txt` with the URLs, the download date and time, file sizes and sha256 of every downloaded archive.
   - Unpack and list what is there: number of sequences, genres (from the official metadata, if any), frame rate, the motion array shapes and
     what each column holds, music files. Write it to `/secondary/hyst-data/datasets/finedance/INVENTORY.md`.
   - Commit and push a short summary (no data) in the night log, then **"FINEDANCE READY <commit>"**.
2. **Then, in this order, with the same STOP rule, storage and inventory:** Motorica Dance (github.com/simonalexanderson/MotoricaDanceDataset; its
   own download link; the music it includes; do NOT run its YouTube scripts), AIOZ-GDANCE (official Hugging Face page; stop if gated), AIST++
   motion annotations only (google.github.io/aistplusplus_dataset; annotations only, no videos, no music, nothing behind the AIST form).
   "<NAME> READY" or "<NAME> BLOCKED <reason>" for each.
3. **Look-test session tool** (for 32B's clips; 32B writes its manifest format into `docs/RETARGET_RULES.md` on `body-retarget`; read it when
   pushed and match it):
   - singles: one question "does this look like dancing?" with answers **yes / sort of / no** and an optional note;
   - pairs (V1 vs V2 of the same clip): "which looks more like a person dancing?" with **first / second / neither**;
   - pair order is taken from the manifest (32B sets it, balanced by design: V1 first in exactly 2 or 3 of the 5 pairs); the tool must not
     reshuffle within a pair; singles and pairs are shuffled together by the session seed, as before; coded names, key not served, loopback
     only;
   - report script: `docs/RETARGET_REPORT.md` with clip -> variant -> answer -> note, per-variant counts, the pairs with their order, per-joint
     limiter cuts and gate values from 32B's `numbers.json`. No verdict. Generate it on a synthetic session and READ the generated file.
   - Tests for all of it. Push, **"TOOL READY <commit>"**.
4. **Done when:** every dataset is READY or BLOCKED, and TOOL READY is pushed, with MORNING SUMMARY. Then stop. Do not start a session.

**Out of scope (stop and ask; log FOR USER):** any account, login, form, gated page or install; AIST Dance DB videos or music; any retargeting or
clips (32B's); training; uploading anything.
