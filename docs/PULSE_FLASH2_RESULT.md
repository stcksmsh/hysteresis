# Second pulse flash check (7.79 Q1 (d), Kosta, 2026-11-17)

Session `/secondary/hyst-data/body/pulse/flash2/session_2026-11-17`: 20 items, 10 songs × (pulse, librosa). 8 songs whose whole-song pulse
level is 2/3 or 3/2 of librosa, plus the 2 failures from the first check. All 20 answered. Scored by the overseer against
`pulse/flash2/key.json`. Server stopped.

## Totals

| source | on beat: yes / partly / no | speed: right / too fast / too slow |
|---|---|---|
| pulse | 1 / 8 / 1 | 6 / 4 / 0 |
| librosa | 6 / 3 / 1 | 6 / 4 / 0 |

## By group

| group (pulse / librosa) | pulse speed right | librosa speed right | pulse on beat yes / partly / no |
|---|---|---|---|
| 3/2: pulse faster (fd_100, aioz_ULrc, ph_157, mo_funk) | 1 / 4 (3 too fast) | 4 / 4 | 0 / 4 / 0 |
| 2/3: pulse slower (fd_034, aioz_iOoW, ph_224, mo_LH6) | 3 / 4 (fd_034 too fast) | 1 / 4 (3 too fast) | 1 / 2 / 1 |
| first-check failures (aioz_8JQ0, aioz_SZhU) | 2 / 2 | 1 / 2 | 0 / 2 / 0 |

## Answers and notes (verbatim)

```
aioz_8JQ0zHmZBIg_05_0_ lib    yes|right        lvl=1 | its just a uniform 4/4, the other one had accents which were nice sometimes but it over-doubled
aioz_8JQ0zHmZBIg_05_0_ pulse  partly|right     lvl=1 | Starts ok, then starts double flashing, then ok again, then doubles, then ok, 
aioz_SZhU9XTCUiM_13_0_ lib    partly|too fast  lvl=1/2 | Seems like a beat clock, and its fast
aioz_SZhU9XTCUiM_13_0_ pulse  partly|right     lvl=1/2 | It starts uniform on a totaly wrong beat, then catches it after a while and gets ok
aioz_ULrcDcQabdA_07_0_ lib    yes|right        lvl=3/2 | Its on beat
aioz_ULrcDcQabdA_07_0_ pulse  partly|too fast  lvl=3/2 | Gets the beat uniformly for first some time, then speeds up a lot for some reason before it should, like precognition or something
aioz_iOoW_Y_lto8_05_0_ lib    yes|right        lvl=2/3 | more beat than accent signal (the accent/moment stuff should have a limit sortof? It should catch the distinct stuff or smth?) also it continues blinking uniformly during a COMPLETELY SILENT period obviously between songs
aioz_iOoW_Y_lto8_05_0_ pulse  yes|right        lvl=2/3 | Except for the end where it is NOTHING and it continues flashing
fd_034                 lib    no|too fast      lvl=2/3 | extremely fast, the piece is slow and ambient, no vocals, traditional and calming, the signal is like a rave, total missmatch
fd_034                 pulse  no|too fast      lvl=2/3 | beat clock on a beatless melodz
fd_100                 lib    yes|right        lvl=3/2 | 4/4 beat uniform, its on beat, beat signal continues during break with no beat
fd_100                 pulse  partly|right     lvl=3/2 | Too fast, 4/4 uniform  no accenting or whatever, when the beat drops out it continues
mo_kthstreet_gLH_sFM_c lib    partly|too fast  lvl=2/3 | The same as the one before, but its second worse half, even faster, its not good, technically on beat, but not like the song, too fast
mo_kthstreet_gLH_sFM_c pulse  partly|right     lvl=2/3 | In the middle of the sound it just switches up without reason to a faster more uniform one, why
mo_kthstreet_gPO_sFM_c lib    yes|right        lvl=3/2 | Ok, just 4/4 beat lock, no accents but good
mo_kthstreet_gPO_sFM_c pulse  partly|too fast  lvl=3/2 | ok, then too fast, then slows back down etc, 
ph_157                 lib    yes|right        lvl=3/2 | starts ok 4/4 uniform, 
ph_157                 pulse  partly|too fast  lvl=3/2 | 4/4 uniform, offbeat and imperfect
ph_224                 lib    partly|too fast  lvl=2/3 | Its uniform, not accents, beat? Its not too good, too fast
ph_224                 pulse  partly|right     lvl=2/3 | Its a uniform beat counter
```

## Reading (overseer, numbers only)

- **The 3/2 group fails** under 7.79 Q1's condition: the pulse is too fast on 3 of 4 songs, and librosa is right on all 4.
- **The 2/3 group favours the pulse level:** right on 3 of 4, against librosa's 1 of 4. The one miss, fd_034, is a beatless ambient piece
  where both fail.
- **Recurring note, the pulse switches level mid-excerpt** (5 items): "double flashing", "speeds up before it should", "switches up without
  reason", "too fast, then slows back down".
- **Recurring note, both sources keep flashing through silence, beatless music and breaks** (4 items: aioz_iOoW, fd_034, fd_100,
  mo_LH6).
- **Kosta on the purpose, again:** "more beat than accent signal (the accent/moment stuff should have a limit sortof? It should catch the
  distinct stuff or smth?)".
