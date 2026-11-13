# Motor-network toy test, round 2: report

Kosta's labels next to the setting and the measured numbers. No verdict and no score here: what it means is Kosta's call.

## Part A: silent, 30 s

| setting | label | note | pr_slow | pr_fast | yaw_range | shoulder_range | drift | drift_range | hand_speed | hand_height | freq_hz | straightness |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S01 | something, can't name it | Again with the micro-movements, as I said they are usefull, but they seem to be more usefull like here ~14-~16 and ~20-~25 with the "in place bobbing", if we have micro-movements whilst moving (e.g. sweeping with these bobbs/circles) it seems like glitching, similar issues as the others | 2.32 | 3.12 | 30.8 | 9.73 | -1.82 | 16.9 | 0.16 | 0.52 | 0.133 | 0.692 |
| S02 | nothing, glitching | Micro movements again, glitchy, similar as the ones before it | 3.41 | 3.75 | 66.5 | 9.69 | -35.9 | 61 | 0.157 | 0.573 | 0.133 | 0.734 |
| S03 | tense | Same micro-stuff, though a bit better and more legible as it doesnt interfere with the sweep (perhaps the issue is if the micros are in the same plane as the sweep, causing it to stutter?) | 1.87 | 2.69 | 51.2 | 6.3 | -5.9 | 46.8 | 0.119 | 0.528 | 0.167 | 0.766 |
| S04 | nothing, glitching | Again, micro movements, these are more glitchy somehow? Theres less in-place movement and more sweeps with them, thats possibly it, it almost makes it look like the motors are stalling, stopping midway or getting stuck | 3.03 | 3.36 | 73.8 | 11.9 | -38.1 | 56.7 | 0.231 | 0.519 | 0.133 | 0.795 |
| S05 | nothing, glitching | - | 2.21 | 3.66 | 31.4 | 5.54 | 11.3 | 30.8 | 0.0967 | 0.487 | 0.133 | 0.478 |
| S06 | energetic | Its tense/anxious/energetic maybe? Its jittery almost glitching but maybe it could be kept for smth? | 2.07 | 2.34 | 61.5 | 16.5 | 2.18 | 59.2 | 0.204 | 0.514 | 0.167 | 0.729 |
| S07 | nothing, glitching | again, many micro-movements, almost glitchy again, definitely too long for such a style? This type of thing could work as part of smth else like flourishes/details etc, but if it just does this for a long time its glitchy | 1.96 | 2.78 | 41 | 6.85 | 12.9 | 38.7 | 0.102 | 0.515 | 0.133 | 0.758 |
| S08 | energetic | Similar as 4, sortof erratic/micro-movements, though this one can be used more (it locks in at ~5s and stays in the same position bobbing up and down, I can see that as being something usefull in some songs, like head-bobbing, but itd need some dynamism, like bobbing, then turning , then bobbing again, etc? | 3.82 | 4.68 | 27.2 | 4.48 | -0.334 | 22.7 | 0.167 | 0.448 | 1.67 | 0.242 |

## Part B: which render fits the music

| song | settings as shown | pick | chosen setting | note | mean hand speed (m/s) | mean ear energy | mean arousal_b7 raw | arousal_b7 standardised |
|---|---|---|---|---|---|---|---|---|
| blue-lagoon | first S06, second R1_S03 | second | R1_S03 | 1st is too small, at points like ~12, ~23, ~26 for example its almost stuck, 2nd is a lot better with bigger more energetic and happy movements but its still lacking something? Again all the videos are `pointed` at the same starting point in terms of base rotation and shoulder, we dont need to face the audience always, we can use rotation as a tool? Second is better, bigger movements, more happy and fitting | first 0.172, second 0.332 | 1.34 | 0.415 | -0.294 |
| breathe | first S03, second R1_S03 | second | R1_S03 | First is ok energywise but its almost glitchy and doesnt track music perfectly (it has nice moments like ~23-~26 where it almost follows the vocals). 2nd is better, not glitchy, though its a bit too active at ~17 for instance and doesnt have that nice `vocal following` piece. Perhaps the issue here is that they shouldnt be across the whole 30s, if it was 2nd then 1st at the ~23s vocal part, then itd be better? Still altogether 2nd is maybe better? Its pretty close | first 0.117, second 0.294 | -0.388 | 0.997 | 0.266 |
| epitaph | first S05, second R1_S03 | second | R1_S03 | First is too static to be "to the music", so its an automatic second (second does match the song well actually, though it could "rise" more vertically at ~14s - ~20 as thats the vocal highpoint but thats nitpicky?) | first 0.0728, second 0.247 | -0.0545 | 0.0138 | -0.681 |
| one-of-these-days | first S01, second R1_S03 | second | R1_S03 | 1st is too small/slow for the song until ~10s and then goes back to slow at ~15 until the end. 2nd is also too small/slow but bigger than 1st, doesnt match the song well, id say netiher here possibly (2nd has a good moment at ~25 with a loop timed to the guitar though so thats why I said 2nd | first 0.0708, second 0.126 | -0.3 | -0.694 | -1.36 |
| schizoid-man | first S07, second R1_S03 | second | R1_S03 | at ~5s the `21st century schizoid man` line ends and we get STRONG AGGRESSIVE music, and ~26 we get aggressive vocals, the first is minimally moving and very slow, bad, the second is a lot better, though it could use more energy still? | first 0.0585, second 0.232 | 0.0804 | 0.757 | 0.0351 |

## Discards by gate

Stop rule hit: False. Draws: 17, kept: 8.

Discards per gate:

| gate | count |
|---|---|
| contact | 3 |
| limits | 2 |
| motion | 6 |

Discards per run:

| run | count |
|---|---|
| blue-lagoon | 3 |
| silent | 6 |

| draw | values | run | failed gates | extent m |
|---|---|---|---|---|
| 1 | 0.739, 0.934, 0.771, 0.933 | silent | motion | 0.019 |
| 3 | 1.02, 0.689, 1.72, 1.47 | blue-lagoon | contact | 0.742 |
| 4 | 0.802, 0.615, 0.588, 0.969 | silent | motion | 0.0178 |
| 7 | 1.32, 2, 0.809, 1.35 | blue-lagoon | contact, limits | 0.396 |
| 8 | 0.643, 1.13, 1.59, 1.99 | blue-lagoon | contact, limits | 0.674 |
| 10 | 1.02, 0.617, 0.643, 1.99 | silent | motion | 0.016 |
| 12 | 0.964, 1.27, 0.805, 1.68 | silent | motion | 0.0938 |
| 13 | 1.12, 0.623, 0.724, 0.698 | silent | motion | 0.0262 |
| 16 | 0.799, 1.12, 0.689, 1.29 | silent | motion | 0.0145 |

Round-1 S03 gates (rendered as the reference):

| song | passed | failed |
|---|---|---|
| blue-lagoon | True | - |
| schizoid-man | True | - |
| epitaph | True | - |
| breathe | True | - |
| one-of-these-days | True | - |

## Network and body parameters

Rules and every fixed number: `docs/MOTORNET2_RULES.md` (round 1: `docs/MOTORNET_PARAMS.md`).

| setting | values | draw index |
|---|---|---|
| S01 | 0.682, 1.88, 0.877, 0.686 | 2 |
| S02 | 1.69, 1.62, 0.527, 0.941 | 5 |
| S03 | 0.609, 0.541, 0.568, 1.83 | 6 |
| S04 | 1.09, 1.79, 0.869, 0.921 | 9 |
| S05 | 0.657, 1.11, 0.692, 0.922 | 11 |
| S06 | 1.31, 1.35, 0.93, 0.916 | 14 |
| S07 | 0.62, 1.36, 0.514, 0.886 | 15 |
| S08 | 0.682, 1.32, 1.49, 1.42 | 17 |

