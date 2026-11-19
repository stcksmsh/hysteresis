# Dance dataset licences (WO31, read 2026-11-13)

Reading task only. No dataset file was downloaded, no form filled, no account made, nothing sent. **No verdict**: Kosta decides.
All quotes are from primary sources (official site or official repository), read on **2026-11-13**. Where a fetch tool paraphrased a page, the
page was re-read as raw text and the quote below is from the raw text. Nothing here is legal advice; "unclear" marks where the wording does not
answer the question.

Restriction classes follow the wording: *commercial allowed* / *non-commercial only* / *research/academic only* / *other (quote)*.
"Exhibition" = a public, non-commercial art exhibition of a model trained on the data, no tickets sold.

## Table

| Dataset | Size | Motion format | Motion licence (class) | Music licence (class) | Video licence | Local training allowed? | Public exhibition of trained model allowed? | Registration / agreement? |
|---|---|---|---|---|---|---|---|---|
| **AIST++** (Google, derived from AIST DB) | 1,408 sequences, 10 genres, 30 subjects, 10.1M frames, 7.4-48.0 s per sequence (A1) | joint rotations + root trajectory (SMPL-style), 3D keypoints (A1) | CC BY 4.0 for the annotations, "licensed by Google LLC" (A1). **Commercial allowed** with attribution (class from the CC name; the CC legal text itself was not re-read) | AIST's own terms apply (A3); AIST++ site gives no music terms (A2) | AIST's own terms (A3); AIST++ page: none stated (A2) | motion: yes (A1). Music/video: see AIST row | motion: yes by CC BY 4.0 wording. Music/video: see AIST row | AIST++ page: "read and agree with the Terms of Use of the AIST Dance Video Database" before downloading the videos (A2); for annotations alone: none stated |
| **AIST Dance Video Database** (music, videos) | not read from a primary page this session (home page and terms give no counts); AIST++ says it uses its multi-view videos (A2) | n/a (video, audio) | n/a | "free to use for academic research" and "for research purposes by academic institutions, companies, and individuals". **Research/academic only** wording (B1). Music is described as "copyright-cleared dance music" (B2) | same terms (B1). **Research/academic only** | yes: "free to use for research purposes" (B1) | **unclear.** Terms speak of research; they do not mention exhibition. They bar use in "any product or service" without a commercial licence (B1) | yes: "Please fill in the Application Form before using" (B1). Form asks Name, Affiliation, Email, all required (B3). Who may apply: wording says institutions, companies and individuals (B1); whether a student needs a supervisor: **unclear**, not stated |
| **AIST DB derived data** (keypoints, SMPL fits, trained model) | n/a | n/a | "any output developed or obtained through its use (including results, models, systems, and technologies)" is covered by the product/service clause (B1) | n/a | n/a | yes if research (B1) | **unclear**: depends whether an exhibition counts as "provision, operation, or offering of any product or service" (B1) | same form |
| **FineDance** (Tsinghua) | 14.6 h, 346 song/dance pairs, 22 genres, 27 dancers (C3); public download is only part, 7.7 h (C1) | SMPL-H `.npy` (also FBX in the paper) (C1) | **non-commercial only**, wording includes "non-commercial scientific research, non-commercial education, or non-commercial artistic projects" (C2) | no separate music licence in the repo; covered by the one licence "Data & Software" (C2); music source/rights **unclear** (C3 silent) | repo licence names "images, videos" in scope (C2) | yes (C2) | **yes by wording** if the exhibition is a "non-commercial artistic project" (C2); training for "commercial ... use" prohibited (C2); sharing with third parties needs permission (C2) | no form; acceptance is by downloading/using ("By downloading and/or using ... you agree") (C2) |
| **Motorica Dance Dataset** (KTH / Alexanderson) | 6 h mocap, 8 styles, about 460 min listed, 17-camera OptiTrack, 120 fps (D1) | BVH, one skeleton (D1) | "free to use for research purposes"; commercial not permitted without written consent (D1). **Research/academic only** (plus no commercial). Non-research use needs contact (D1) | "all MUSIC AUDIO has its own Copyright Holders and is not subjected to this license" (D1). **other**: separate holders, per-track attribution (D1). Some sessions' music is from Spotify/YouTube and not in the download (D1) | none (mocap only; video not mentioned) | yes for research (D1); music: depends on its holders, **unclear** | **unclear**: only "research purposes" is licensed; non-research use needs written contact (D1) | no form; download link on the repo; acceptance by downloading (D1) |
| **AIOZ-GDANCE** (AIOZ) | 16.7 h, 7 dance styles, 16 music genres, group dance from in-the-wild video (E2) | SMPL poses `.pkl` (24 joints) + root translation, `.wav` music (E2) | **non-commercial only**: "non-commercial scientific research, non-commercial education, or non-commercial artistic projects" (E1) | same single licence over "Data & Software" (E1); the underlying in-the-wild music/video copyright holders are not discussed: **unclear** | same licence; source videos from the internet, rights **unclear** | yes (E1) | **yes by wording** for a "non-commercial artistic project" (E1); no training "for commercial ... use" (E1) | no form found; acceptance by downloading (E1) |

## Sources and quotes

### A. AIST++ (Google)

- **A1.** https://google.github.io/aistplusplus_dataset/factsfigures.html, read 2026-11-13. Quote: "The annotations are licensed by Google LLC under"
  CC BY 4.0 (link to https://creativecommons.org/licenses/by/4.0/). Same page: "1,408 sequences of 3D human dance motion", "10.1M images, covering 30
  different subjects in 9 views", motions "equally distributed among 10 dance genres", sequences 7.4 to 48.0 s, "Motions are represented as joint
  rotations with root trajectories". The page also asks users to cite the original AIST Dance Video Database (a citation request, not a licence term).
- **A2.** https://google.github.io/aistplusplus_dataset/download.html, read 2026-11-13. Quote: "Before the downloading, please make sure you have read
  and agree with the Terms of Use of the AIST Dance Video Database." Also: "If you only need to download the subset of AIST Dance Videos that we
  annotated, we provide a Python script that downloads the videos (with music) from their website." The page states no licence conditions for the
  annotation files.
- **A3.** Official code repository https://github.com/google/aistplusplus_api: `LICENSE` is **Apache License, Version 2.0** (the code, not the data).
  The README says "To download the dataset or explore details of this dataset, please go to our dataset website." It does **not** mention CC BY 4.0.
  **Result of the check Kosta asked for:** there is no data licence *file*; the CC BY 4.0 statement exists only on the dataset website page A1. The
  Apache-2.0 file covers the API code only. Not checked: whether a separate data licence file sits elsewhere in the repo (only `LICENSE` and the README
  were read).
- Any term about the videos or music: A2 above, nothing else.

### B. AIST Dance Video Database (music and videos)

- **B1.** https://aistdancedb.ongaaccel.jp/terms_of_use/, read 2026-11-13, raw text:
  - "Please fill in the Application Form before using AIST Dance Video Database (AIST Dance DB)."
  - "This database is brought to you as a part of a research project conducted by AIST Media Interaction Group."
  - "AIST Dance DB is free to use for academic research. It is free to use for research purposes by academic institutions, companies, and individuals."
  - "If AIST Dance DB itself or any output developed or obtained through its use (including results, models, systems, and technologies) is
    subsequently incorporated into, deployed in, or otherwise used for the provision, operation, or offering of any product or service, you must
    contact aistdancedb-ml@aist.go.jp and enter into a commercial license agreement with AIST before such use. Unauthorized redistribution of any
    content of AIST Dance DB is prohibited."
  - "Please note that it is necessary for you to clearly indicate the name of the database, "AIST Dance Video Database" or "AIST Dance DB", when
    using the database. When mentioning this database in an academic paper, please cite the following paper as a reference" (ISMIR 2019, Tsuchida et al.).
  - "when such a citation is difficult for a non-academic article, please insert the following or similar text: "We have used the AIST Dance Video
    Database (https://aistdancedb.ongaaccel.jp)."" (so non-academic use is contemplated).
  - Disclaimers: "Any use of this website or any use of AIST Dance DB provided by this website is at your own risk."
  - The terms do **not** say separately "music", "videos" or "derived data" are treated differently: one set of terms for everything, music
    included. They do not say "local training" or "exhibition" either.
- **B2.** https://aistdancedb.ongaaccel.jp/ , read 2026-11-13: "original street dance videos with copyright-cleared dance music"; music is available
  separately ("Get Only Music Data", https://aistdancedb.ongaaccel.jp/getting_the_database/: "You can download audio files of musical pieces used in
  the videos."). Copyright line: "Copyright © 2019 National Institute of Advanced Industrial Science and Technology (AIST)".
- **B3.** Application form, https://forms.gle/9nVAxPFUhXNPrKQ5A (linked from the terms page), read as a page only, not filled: "Application to use the
  AIST Dance Video Database." Fields: Name *, Affiliation *, Email * (required). No mention of supervisor, signature, or institutional email.
- **B4.** FAQ, https://aistdancedb.ongaaccel.jp/faq/, read 2026-11-13: "Can I use AIST Dance Video Database (AIST Dance DB) in research and publish a
  paper? ... Yes, you can." Also: research demonstration with a video or music piece: "Yes, you can ... do not forget to include the following or
  similar text". Presentation video-streamed over the internet with a video or music piece: "Yes, you can." These say public showing of material **in
  research presentations** is allowed; they say nothing about an art exhibition.
- **Does research use allow a public showing of a trained model?** B4 allows demonstrations and streamed presentations in a *research* context.
  Whether an exhibition outside research counts: **unclear** (B1 is silent).
- **What research use requires:** the form (B3), the database name shown when used, and a citation (B1). **Who may apply:** "academic institutions,
  companies, and individuals" (B1). Supervisor / institutional signature / institutional email: **not stated** in B1 or B3; the form's Affiliation
  field is required, what an individual with no institution writes there is **unclear**.

### C. FineDance

- **C1.** https://github.com/li-ronghui/FineDance (README), read 2026-11-13: "The part(7.7 hours) of FineDance dataset can be downloaded at Google
  Drive or 百度云." "motion: contains the SMPLH format motion data." "music_wav: contains the music data in 'wav' format." "When using the
  code/figures/data/video/etc., please cite our work".
- **C2.** https://github.com/li-ronghui/FineDance/blob/main/LICENSE (GitHub marks it "Other", NOASSERTION), read 2026-11-13: "License. Software
  Copyright License for non-commercial scientific research purposes." Grant: "Licensor grants you (Licensee) personally a single-user, non-exclusive,
  non-transferable, free of charge right: To install the Data & Software on computers owned, leased or otherwise controlled by you and/or your
  organization; To use the Data & Software for the sole purpose of performing non-commercial scientific research, non-commercial education, or
  non-commercial artistic projects; Any other use, in particular any use for commercial, pornographic, military, or surveillance, purposes is
  prohibited. This includes, without limitation, incorporation in a commercial product, use in a commercial service, or production of other
  artifacts for commercial purposes. ... The Data & Software may not be reproduced, modified and/or made available in any form to any third party
  without Xiu Li's prior written permission." Also: "This license also prohibits the use of the Software to train methods/algorithms/neural
  networks/etc. for commercial, pornographic, military, surveillance, or defamatory use of any kind." "No Distribution ... shall not be copied,
  shared, distributed, re-sold ... except that you may make one copy for archive purposes only." Acceptance: "By downloading and/or using the Data &
  Software ... you acknowledge that you have read these terms ... and agree to be bound by them." Owner: "Professor Xiu Li, Tsinghua University."
  - **Unclear:** "made available ... to any third party" could include showing a trained model's output publicly; whether an exhibition "makes
    available" the Data & Software is a lawyer's reading. The licence names "non-commercial artistic projects" as permitted.
  - **Unclear:** music rights. The licence text and README do not say where the music comes from or who holds its copyright.
- **C3.** Paper abstract https://arxiv.org/abs/2212.03741: "contains 14.6 hours of music-dance paired data ... 22 dance genres". The 346 pairs and 27
  dancers figures come from a search summary of the ICCV paper (https://openaccess.thecvf.com/content/ICCV2023/papers/Li_FineDance_A_Fine-grained_Choreography_Dataset_for_3D_Full_Body_Dance_ICCV_2023_paper.pdf),
  not re-read in the paper itself: treat as unconfirmed. Project page https://li-ronghui.github.io/finedance: the *website* is CC BY-SA 4.0, not the data.

### D. Motorica Dance Dataset

- **D1.** https://github.com/simonalexanderson/MotoricaDanceDataset (README, raw), read 2026-11-13:
  - "This dataset consists of 6 hours of motion capture and audio for dancing in 8 different styles." "17 Prime41 cameras from OptiTrack, operating at
    120 fps. All motion is in BVH format and retargeted to a single skeleton."
  - "This data download link contains all BVH files as well as the music with cleared rights (see terms below). Additional music from Session 4 can
    be downloaded from YouTube using the provided scripts. For the pop songs from Session 2, we provide extracted features ... in pkl format."
  - "You also acknowledge that all MUSIC AUDIO has its own Copyright Holders and is not subjected to this license."
  - "Non-commercial use: The Motorica Dance Dataset is free to use for research purposes by academic institutes, companies, and individuals. Use for
    commercial purposes is not permitted without prior written consent. This includes, without limitation, incorporation in a commercial product, use
    in a commercial service, or training machine-learning algorithms for commercial purposes. If you are interested in using Motorica Dance Dataset
    for commercial purposes or non-research purposes, please contact simonal@kth.se."
  - "No redistribution: Unauthorised redistribution of any content from the database is prohibited without written approval from its respective
    copyright holder(s)."
  - "Attribution: Please clearly indicate the name of the dataset ... and provide a link to this repository." Music: attribute "music by M.P.A Mario
    Perez Amigo" and "music by Stockholm Swing All Stars" "when using the music in video presentations".
  - Wording of the licence is research-purposes. "non-research purposes" need contact. An art exhibition is neither named as allowed nor as barred:
    **unclear**; the heading says "Non-commercial use" while the text says "research purposes" and "non-research purposes" need contact, so the two
    do not align (**unclear**).
  - Registration: none; no form, supervisor or institutional requirement stated. Download is a SharePoint link (not opened).

### E. AIOZ-GDANCE

- **E1.** https://huggingface.co/datasets/aiozai/AIOZ-GDANCE/raw/main/LICENSE (official AIOZ organisation page), read 2026-11-13: "Software Copyright
  License for non-commercial scientific research purposes." Same grant text as FineDance C2 (the FineDance licence is evidently a copy of the same
  template): "To use the Data & Software for the sole purpose of performing non-commercial scientific research, non-commercial education, or
  non-commercial artistic projects"; "Any other use, in particular any use for commercial, pornographic, military, or surveillance, purposes is
  prohibited"; "The Data & Software may not be reproduced, modified and/or made available in any form to any third party without AIOZ's prior written
  permission"; "This license also prohibits the use of the Software to train methods/algorithms/neural networks/etc. for commercial, pornographic,
  military, surveillance, or defamatory use of any kind."
  Licensee: "you (Licensee) personally a single-user, non-exclusive, non-transferable". The README front matter says `license: other`.
- **E2.** README, same host, read 2026-11-13: "16.7 hours of paired music and 3D motion from in-the-wild videos, covering 7 dance styles and 16 music
  genres." Format: "`smpl_poses`: shape[num_persons x num_frames x 72] ... SMPL pose format (24 joints)", "`root_trans`", music as ".wav". Group (multi-person)
  dances, not single-dancer. Official GitHub repo: https://github.com/aioz-ai/AIOZ-GDANCE (not separately read).
- Registration: none found; download links are direct. Music/video copyright of the in-the-wild sources is not addressed: **unclear**.

## Terms that could not be answered without registering or asking the owners (not done)

1. AIST DB: does a non-commercial art exhibition of a trained model count as "provision, operation, or offering of any product or service"? Ask
   aistdancedb-ml@aist.go.jp. Also: may a student with no institution apply, and what goes in "Affiliation"?
2. AIST DB: music terms specifically. The terms page treats music like the rest; the music's own copyright holders are not named. "copyright-cleared"
   is not a licence text.
3. AIST++: whether CC BY 4.0 on annotations is enough when the annotations are only useful with the AIST videos/music under AIST's terms (A2).
4. FineDance: music provenance and rights; what the 7.7 h public part contains versus the 14.6 h; whether a public showing counts as "made available
   to any third party". Contact: the licensor named in the licence (Prof. Xiu Li, Tsinghua).
5. Motorica: whether an art exhibition is "research purposes"; the heading "Non-commercial use" suggests the intent but the text says research. Contact
   in the README.
6. AIOZ-GDANCE: rights in the in-the-wild source music; no registration found, but the project page / download host was not opened.
7. Not read: the CC BY 4.0 legal text itself (only the licence name and link); the ISMIR 2019 AIST paper (fetch failed); the AIST DB size figures.
