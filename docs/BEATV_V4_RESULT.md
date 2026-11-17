# V4 result: Kosta's beat-grid flash check (7.77 V4), 2026-11-17, overseer scoring

Session `/secondary/hyst-data/body/beatv/clicks_visual/session_2026-11-17` (seed 47202): 10 songs (FineDance 3, AIOZ 2, PhantomDance 3,
Motorica 2) x 2 grids (project = `analyze_mix`, librosa `beat_track`), 30 s excerpts at or above the song's median RMS, a white disc
flashing at each beat over the music (Kosta found audio clicks hard to hear; one earlier audio-click answer discarded, not counted).
Blind, random order. Question "Is the flash on the beat?".

| grid | yes | partly | no |
|---|---|---|---|
| librosa | 8 | 2 | 0 |
| project | 3 | 6 | 1 |

Per song (project / librosa): fd_018 no / yes; fd_053 yes / yes; fd_183 partly / yes; aioz_8JQ0 yes / yes; aioz_SZhU partly / partly;
ph_084 partly / yes; ph_102 partly / yes; ph_137 yes / yes; Motorica jazz partly / partly; Motorica street partly / yes.

Kosta's notes (verbatim):
- librosa: "Hits the 4/4 perfectly, misses the drop doubling of kicks, but thats ok, cant hit that speed anyway on servos"; "Perfect 4/4
  basically"; "It finds the 4/4" (x2); "Its on the kick pattern when it exists, when it doesnt it catches the percs or whatever is there,
  if no tempo-setting thing is there its a bit worse (which makes sense, theres no beat)".
- librosa, metrical level: fd_018 "It finds the `hats` and follows them due to not having a kick but only a rim or smth, the rim is 1/4
  the hats and is perhaps a better thing to track. ... this IS on beat, but perhaps not the perfect beat since it is a slow song but we
  follow the FASTEST element (hats are always fast)"; aioz_SZhU "It basically tries to hit every hit of fast percs instead of focusing on
  drums, its too fast?".
- librosa, jazz: "Mostly in the second half which has drums/percs".
- project: fd_018 "Doesnt find the rhythm, tries to follow the vocals as a beat, becomes WAY too fast"; ph_084 "Has entire sections/part
  without anything in them, some of them are deserved, some are not"; ph_102 "It has misses and entire sections without anything...";
  fd_183 "hits WAY less but 'more correctly' ... it just looks empty and not correct due to the dropouts"; Motorica street "Perhaps dropped
  a few important blips?"; fd_053 "not perfectly on beat for the first half but it is 'artistically on beat' ... The other half it hits the
  4/4"; aioz_SZhU "Sortof? Not perfect but it isnt too bad either?"; jazz "a difficult example of freeform music like jazz".
