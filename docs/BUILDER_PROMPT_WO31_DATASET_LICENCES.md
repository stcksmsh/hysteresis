# Builder prompt: work order 31, dance dataset licence check (2026-11-13)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER" instead of
waiting. You start with no context: everything you need is named below.

**This is a reading task.** No data downloads, no code, no training, no verdict. Kosta (the user) decides which source is usable.

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works. Retry on a GitHub server
  error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-licence origin/body`, then push `body-licence`.
- **Forbidden:** downloading any dataset file (motion, audio, video, archives); creating accounts; filling in or submitting any form, agreement
  or registration; emailing or posting anything; spending anything. Reading web pages and licence files in the browser-free fetch tools
  (WebFetch, WebSearch) is allowed. Never send the user's name, email or project details to any site.
- **Push** within 30 minutes and when done. Log: `docs/NIGHT_LOG_body-licence.md` (new; MORNING SUMMARY on top).

## Read first

- `docs/BRAIN_SPEC.md` **§7.49** (binding; point 4 is this work order).

## The work

1. **Primary sources only:** the dataset's official site, its official repository's LICENSE / README / terms files, the publisher's terms-of-use
   page, the paper's data statement. A third-party blog, a mirror, a Kaggle copy or a forum answer does not count. For each quote, record the URL
   and the date you read it.
2. **Datasets:**
   - **AIST++** (google.github.io/aistplusplus_dataset and its official GitHub repository): the motion annotations are stated as CC BY 4.0.
     Confirm from the licence file itself and quote it. Note any term about the videos or music it points to.
   - **AIST Dance Video Database** (the source of the videos AND the music used by AIST++): terms of use for (1) the music audio, (2) the
     videos, (3) derived data (e.g. keypoints, SMPL fits, a trained model). Answer each of:
     - is local use for training a model allowed;
     - is public exhibition of a model trained on it allowed (a non-commercial art exhibition, no ticket sales expected);
     - is any registration, application or agreement required, and by whom (individual / institution).
   - **2-3 alternative public music-dance datasets with 3D motion AND music** (e.g. FineDance; find others from primary sources, prefer ones
     with a real licence file). For each: size (hours, number of sequences, dancers, genres), motion format (e.g. SMPL, joint positions, BVH),
     licence of the motion, licence of the music, and the same three questions.
   - **Scope of licences (Kosta, 2026-11-13):** the work is never sold or ticketed. Include datasets under non-commercial licences (e.g. CC
     BY-NC) and research-only or academic-only terms, not only open ones. For each, classify the restriction exactly as worded:
     "commercial allowed", "non-commercial only", "research/academic only", "other (quote)". Do not treat "non-commercial" and "research
     only" as the same: report whether the wording covers a public, non-commercial art exhibition, or "unclear" if it does not say.
3. **Output: `docs/DATASET_LICENCES.md`:**
   - one table: dataset | size | motion format | motion licence (with restriction class) | music licence (with restriction class) | video
     licence | local training allowed? | public exhibition of a trained model allowed? | registration/agreement required? Each cell says
     "yes", "no" or "unclear" plus a short pointer to the quote;
   - then, per dataset, the exact quotes (verbatim, in quotation marks, with the URL and date read);
   - where terms are silent, contradictory, or need a lawyer's reading, write "unclear" and say why. **Do not guess and do not give a verdict**;
   - a short list of what could only be answered by registering or asking the dataset owners (not done).
4. **Done when:** the file is pushed with MORNING SUMMARY and "LICENCES READY <commit>" in the night log. Then stop.

**Out of scope (stop and ask; log FOR USER):** any download, registration, form, email or account; any retargeting, code or training (step 2
waits for Kosta's ruling on this report).
