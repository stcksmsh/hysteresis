# Pulse v2 viewing (7.80 Q1, Kosta, 2026-11-18)

Session `/secondary/hyst-data/body/pulse2/view/session_2026-11-17`: 40 items, 20 excerpts × (pulse v2, librosa). The session was re-served
after a reboot, with no answers lost. All 40 were answered. Scored with `scripts/body/pulse2_score.py`. Server stopped.

## Decision rule (7.80): NOT MET

| source | right | too fast | too slow | steady | switches |
|---|---|---|---|---|---|
| pulse v2 | 15 | 2 | 3 | 19 | 1 |
| librosa | 18 | 2 | 0 | 20 | 0 |

Pulse v2 is below librosa on both counts (right speed 15 vs 18, steady 19 vs 20). By 7.80: stop tuning the oscillator bank, and report for a
Kosta ruling on the tempo source.

## Consistency (overseer)

Same excerpt, same tempo as an earlier check, answered again:
- **librosa,** identical beats on the same excerpts: the speed answer changed on 5 of 20. All 5 went from "too fast" to "right": aioz_SZhU ×2,
  fd_018, ph_084, ph_224.
  - On fd_018 the new note says "its on beat just perhaps 2x faster than it should be?", with the answer "right".
- **pulse v2 on the 15 excerpts where its tempo equals v1's:** the speed answer changed on 5. Three went right → wrong (fd_018 too fast,
  fd_100 too fast, ph_224 too slow), two wrong → right (ph_157, aioz_ULrc).
- **The margin:** right-speed differs by 3 items. That is less than the 10 answer changes on identical tempo between sessions.

## Notes (verbatim, selected)

- **Pulse v2:**
  - aioz_8JQ0: "better than before by a lot";
  - ph_102: "It catches the dropout";
  - mo_gPO: "Why are the blips less white now?" (confidence brightness);
  - aioz_SZhU (flash2): "Its not on beat", switches.
- **librosa:**
  - fd_034: "Double/quadruple speed, not good, the song is a slow ambient";
  - fd_100 and fd_183: does not follow the break or drop.

## Full table

| id | check | song | source | speed | steady | note | earlier (source) | earlier answer (on beat / speed) | earlier note |
|---|---|---|---|---|---|---|---|---|---|
| Q08 | flash | aioz_8JQ0zHmZBIg_05_0_1950 | lib | right | yes |  | lib | yes|right | finds the 4/4 well, doesnt catch the pre-drop doubling and quadrupling  |
| Q37 | flash | aioz_8JQ0zHmZBIg_05_0_1950 | pulse2 | right | yes | Its good except for the pre-drop doubling/quadrupling of the beat, it tries to catch that part too, and it almost  succeeds but it drops some beats there and it looks weird because of that, but its better than before by a lot | pulse v1 | partly|too slow | a bit too slow and not right on beat |
| Q27 | flash | aioz_SZhU9XTCUiM_13_0_1950 | lib | right | yes |  | lib | partly|too fast |  |
| Q13 | flash | aioz_SZhU9XTCUiM_13_0_1950 | pulse2 | too slow | yes |  | pulse v1 | no|too slow | not catching it almost at all, idk why |
| Q24 | flash | fd_018 | lib | right | yes | Its catching the "hats" instead of beat, its on beat just perhaps 2x faster than it should be? | lib | partly|too fast | Again, its on beat but follows fast element not the beat |
| Q06 | flash | fd_018 | pulse2 | too fast | yes |  | pulse v1 | partly|right | Its about correct? |
| Q16 | flash | fd_053 | lib | right | yes |  | lib | yes|right | matches the 4/4, doesnt find the beat dropout |
| Q38 | flash | fd_053 | pulse2 | right | yes |  | pulse v1 | yes|right | Finds the beat, doesnt catch the short beat dropouts or the pre-drop changes |
| Q20 | flash | fd_183 | lib | right | yes | It doesnt follow drop/break | lib | yes|right |  |
| Q09 | flash | fd_183 | pulse2 | right | yes | Doesnt catch drop and its beatlessness | pulse v1 | yes|right | Its a bit off beat and slow sometimes (SLIGHTLY) but usable and ok |
| Q34 | flash | mo_kthjazz_gJZ_sFM_sngl_d0 | lib | right | yes |  | lib | yes|right | freeform music, finds the main beat somewhat, jittery intervals somewhat but its ok? |
| Q14 | flash | mo_kthjazz_gJZ_sFM_sngl_d0 | pulse2 | right | yes | Freeform, before drums really kick in its a bit off, then it catches them and is ok | pulse v1 | partly|right | Its a freeform song, it matches it sometimes, when theres a concrete beat its ok, but it fucksup sometimes, probably usable, mostly right speed, though it does "double rapid detections" sometimes |
| Q22 | flash | mo_kthstreet_gLH_sFM_cAll_ | lib | right | yes |  | lib | yes|right | finds the beat well (the purpose isnt to find the beat, but possible end locations to match music, so it isnt just flashing on beat, but flashing at oportune moments e.g. beat/dropout/accent whatever right?) |
| Q05 | flash | mo_kthstreet_gLH_sFM_cAll_ | pulse2 | right | yes | Doesnt catch the break well but otherwise good | pulse v1 | yes|right | mostly right, def usable, though it doesnt catch the "dropout section" as having no beat |
| Q26 | flash | ph_084 | lib | right | yes |  | lib | partly|too fast | The very beginning has no real beat and it imagines it |
| Q31 | flash | ph_084 | pulse2 | right | yes |  | pulse v1 | yes|right | start it finds a beat that isnt there somewhat, finds the 4/4 |
| Q35 | flash | ph_102 | lib | right | yes |  | lib | yes|right | A tadd too fast maybe, though it seems ok? It just seems "jittery" in its inter-click timings, like theyre not uniform or smth, also when the beat dropsout it continues |
| Q18 | flash | ph_102 | pulse2 | right | yes | It catches the dropout, only issue is it continue with the same BPM after the dropout ends and the vocals and some shit begin though it couldve gone slower but its ok | pulse v1 | yes|right |  |
| Q04 | flash | ph_137 | lib | right | yes |  | lib | yes|right | caught the 4/4 |
| Q15 | flash | ph_137 | pulse2 | right | yes |  | pulse v1 | yes|right |  |
| Q19 | flash2 | aioz_8JQ0zHmZBIg_05_0_1950 | lib | right | yes |  | lib | yes|right | its just a uniform 4/4, the other one had accents which were nice sometimes but it over-doubled |
| Q17 | flash2 | aioz_8JQ0zHmZBIg_05_0_1950 | pulse2 | right | yes | It seems to catch more than 4/4 after drop its just the 4/4, so its a bit chaotic before it the first half | pulse v1 | partly|right | Starts ok, then starts double flashing, then ok again, then doubles, then ok,  |
| Q11 | flash2 | aioz_SZhU9XTCUiM_13_0_1950 | lib | right | yes |  | lib | partly|too fast | Seems like a beat clock, and its fast |
| Q33 | flash2 | aioz_SZhU9XTCUiM_13_0_1950 | pulse2 | too slow | switches | Its not on beat | pulse v1 | partly|right | It starts uniform on a totaly wrong beat, then catches it after a while and gets ok |
| Q28 | flash2 | aioz_ULrcDcQabdA_07_0_1950 | lib | right | yes |  | lib | yes|right | Its on beat |
| Q00 | flash2 | aioz_ULrcDcQabdA_07_0_1950 | pulse2 | right | yes |  | pulse v1 | partly|too fast | Gets the beat uniformly for first some time, then speeds up a lot for some reason before it should, like precognition or something |
| Q23 | flash2 | aioz_iOoW_Y_lto8_05_0_1680 | lib | right | yes |  | lib | yes|right | more beat than accent signal (the accent/moment stuff should have a limit sortof? It should catch the distinct stuff or smth?) also it continues blinking uniformly during a COMPLETELY SILENT period obviously between songs |
| Q21 | flash2 | aioz_iOoW_Y_lto8_05_0_1680 | pulse2 | right | yes |  | pulse v1 | yes|right | Except for the end where it is NOTHING and it continues flashing |
| Q10 | flash2 | fd_034 | lib | too fast | yes | Double/quadruple speed, not good, the song is a slow ambient, same one it messed up before by doubling | lib | no|too fast | extremely fast, the piece is slow and ambient, no vocals, traditional and calming, the signal is like a rave, total missmatch |
| Q02 | flash2 | fd_034 | pulse2 | right | yes |  | pulse v1 | no|too fast | beat clock on a beatless melodz |
| Q30 | flash2 | fd_100 | lib | right | yes | Doesnt catch the beatless break in the later section | lib | yes|right | 4/4 beat uniform, its on beat, beat signal continues during break with no beat |
| Q25 | flash2 | fd_100 | pulse2 | too fast | yes |  | pulse v1 | partly|right | Too fast, 4/4 uniform  no accenting or whatever, when the beat drops out it continues |
| Q29 | flash2 | mo_kthstreet_gLH_sFM_cAll_ | lib | too fast | yes | too fast | lib | partly|too fast | The same as the one before, but its second worse half, even faster, its not good, technically on beat, but not like the song, too fast |
| Q12 | flash2 | mo_kthstreet_gLH_sFM_cAll_ | pulse2 | right | yes | Perhaps a tad lat on some downbeats? Gets the flourishes too later, its good | pulse v1 | partly|right | In the middle of the sound it just switches up without reason to a faster more uniform one, why |
| Q01 | flash2 | mo_kthstreet_gPO_sFM_cAll_ | lib | right | yes |  | lib | yes|right | Ok, just 4/4 beat lock, no accents but good |
| Q36 | flash2 | mo_kthstreet_gPO_sFM_cAll_ | pulse2 | right | yes | Why are the blips less white now? | pulse v1 | partly|too fast | ok, then too fast, then slows back down etc,  |
| Q07 | flash2 | ph_157 | lib | right | yes |  | lib | yes|right | starts ok 4/4 uniform,  |
| Q39 | flash2 | ph_157 | pulse2 | right | yes | It looks fast but maybe its just a tad out of sync or its that its a flashing light to this song that makes it look that way | pulse v1 | partly|too fast | 4/4 uniform, offbeat and imperfect |
| Q32 | flash2 | ph_224 | lib | right | yes |  | lib | partly|too fast | Its uniform, not accents, beat? Its not too good, too fast |
| Q03 | flash2 | ph_224 | pulse2 | too slow | yes |  | pulse v1 | partly|right | Its a uniform beat counter |
