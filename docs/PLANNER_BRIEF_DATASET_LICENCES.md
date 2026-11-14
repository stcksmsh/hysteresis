# Planner brief: dance dataset licences (BRAIN_SPEC 7.49.4, step 1), 2026-11-13

TO: planner. FROM: overseer. Full report with every quote and link: `docs/DATASET_LICENCES.md` (body). No verdict from the builder or the
overseer; Kosta decides which source is usable. Nothing here is legal advice.

## What ran

- Agent 2 read the primary sources only: official sites, official licence files, terms pages and the FAQ. No download, no form, no
  account, no email.
- **Overseer check:** fetched the raw text of 7 pages myself (AIST terms, AIST FAQ, AIST++ facts and download pages, FineDance LICENSE,
  Motorica README, AIOZ-GDANCE LICENSE).
  - All 20 key quotes in the report appear verbatim.
  - AIST++'s annotations link to CC BY 4.0.
  - The AIST terms and FAQ contain no mention of "exhibit", "art" or "non-commercial".
- Context given to the builder: the work is never sold or ticketed; Kosta is a software engineering student.

## Results

| Dataset | Size, format | Motion terms | Music terms | Local training | Public non-commercial art exhibition of a trained model | Registration |
|---|---|---|---|---|---|---|
| **FineDance** | 14.6 h, 22 genres, single dancer (public part 7.7 h), SMPL-H + wav | non-commercial: "non-commercial scientific research, non-commercial education, or non-commercial artistic projects" | same licence; music provenance not stated: unclear | yes | yes by wording ("non-commercial artistic projects"); unclear whether showing output counts as "made available ... to any third party" | none; accepted by downloading |
| **AIOZ-GDANCE** | 16.7 h, group dance from internet videos, SMPL + wav | same licence wording as FineDance | rights of the internet source music not addressed: unclear | yes | yes by wording; same third-party caveat | none found |
| **AIST++ motion** | 1,408 sequences, 10 genres, 30 dancers, SMPL-style | CC BY 4.0 (stated on the website; the repo's LICENSE file is Apache-2.0 for code only) | n/a: music and videos come from the AIST Dance DB | yes | yes for the motion annotations by CC BY 4.0 | download page asks to agree to AIST's terms before downloading videos |
| **AIST Dance Video DB** (music, videos) | dance videos + "copyright-cleared dance music" | research: "free to use for research purposes by academic institutions, companies, and individuals" | same terms | yes (research) | unclear: any "output ... (including ... models ...)" used for "the provision, operation, or offering of any product or service" needs a commercial licence; the FAQ allows research presentations, streamed ones included | application form (Name, Affiliation, Email, all required); student / supervisor rules not stated |
| **Motorica Dance** | 6 h mocap, 8 styles, BVH | "free to use for research purposes"; "non-research purposes" need contact | "all MUSIC AUDIO has its own Copyright Holders and is not subjected to this license" | yes (research) | unclear: an exhibition is not named | none |

- Step 2 (the retarget look test) is local only. All five sources allow local research use.
- The exhibition question matters only later, when anything trained on the data is shown in public.

## Questions

1. **Source for the step-2 look test.**
   - (a) **FineDance [recommended]:** its licence names "non-commercial artistic projects"; no registration is needed; single dancers;
     22 genres, the widest spread for a seeded pick.
   - (b) AIST++ motion (CC BY 4.0) with silent clips. Music would need the AIST form (a registration, which needs Kosta's go-ahead).
   - (c) Both: FineDance for the clips, AIST++ held as a second source.
   - (d) Other.
2. **Exhibition questions to the owners.** Unclear points: FineDance's "made available to any third party" and its music provenance;
   AIST's "product or service".
   - (a) Kosta emails the licensors later, before any public showing. **[Recommended: not needed for local step 2]**
   - (b) Now.
   - (c) Not at all.
   Emailing is Kosta's own action; the overseer sends nothing.
3. **Music in step 2.** FineDance's licence covers its wav files as "Data & Software" for local use, but the music's origin is not stated.
   - (a) Use its music locally in the look test, flagged in the report. **[Recommended]**
   - (b) Silent clips only.
4. **Record** as BRAIN_SPEC 7.50.
