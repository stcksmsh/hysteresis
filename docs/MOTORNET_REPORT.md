# Motor-network toy test report

Kosta's labels next to the gain setting and the measured numbers. No verdict and no score here: what it means is Kosta's call.
Network and body parameters used: see `docs/MOTORNET_PARAMS.md`.

## Part 1: silent, every setting (lamp)

| setting | values | label | note | pr | regime | freq_hz | hand_speed | hand_height | straightness | straightness_min |
|---|---|---|---|---|---|---|---|---|---|---|
| S01 | 0.909, 0.742, 1.98, 0.611 | energetic | - | 2.21 | cycles | 0.416 | 0.526 | 0.508 | 0.87 | 0.702 |
| S02 | 1.34, 1.07, 1.41, 0.847 | energetic | - | 2.18 | cycles | 0.416 | 0.856 | 0.463 | 0.707 | 0.659 |
| S03 | 0.813, 0.847, 0.688, 1.65 | tense | - | 2.02 | cycles | 0.416 | 0.318 | 0.509 | 0.963 | 0.788 |
| S04 | 0.623, 1.5, 1.33, 1.56 | energetic | energetic, perhaps even angry? Depends on context... music is like 95% of the context it seems | 2.64 | cycles | 0.416 | 0.664 | 0.481 | 0.809 | 0.169 |
| S05 | 1.38, 1.28, 0.874, 0.907 | energetic | - | 2.17 | cycles | 0.499 | 0.855 | 0.476 | 0.836 | 0.751 |
| S06 | 1.63, 0.568, 1.3, 0.851 | light | The ones like this look most like dances, the entire "body" dances/moves/undulates idk, its energetic and light, could go with something like `loose yourself to dance`, like upbeat tempo right? | 2.18 | cycles | 0.416 | 0.338 | 0.517 | 0.944 | 0.839 |
| S07 | 1.49, 0.955, 0.997, 0.809 | energetic | - | 2.21 | cycles | 0.499 | 0.488 | 0.508 | 0.951 | 0.699 |
| S08 | 0.645, 1.11, 0.827, 1.39 | tense | tense but also perhaps a bit energetic? Like anxious almost, but not dark idk | 2.38 | cycles | 0.416 | 0.247 | 0.514 | 0.934 | 0.841 |
| S09 | 0.63, 0.654, 1.98, 1.29 | light | light/energetic, upbeat? | 1.97 | cycles | 0.25 | 0.391 | 0.278 | 0.887 | 0.516 |
| S10 | 0.588, 0.958, 1.56, 1.4 | energetic | - | 2.18 | cycles | 0.499 | 0.646 | 0.503 | 0.902 | 0.706 |

## Part 2: ball vs lamp

| setting | lamp label | lamp note | ball label | ball note |
|---|---|---|---|---|
| S01 | energetic | - | energetic | - |
| S02 | energetic | - | energetic | energetic again, light/happy song maybe?? idk |

## Part 3: which render fits the music

| song | settings as shown | pick | chosen setting | note | mean hand speed (m/s) | cortex arousal raw | arousal standardised |
|---|---|---|---|---|---|---|---|
| blue-lagoon | first S03, second S06 | first | S03 | Id say first (more "on the music" and less janky), but theyre both too simple/repetitive loops facing the same direction always? Takanaka is jazz fusion, the guitar melody here is more than just loops, it can be better and more on-point whilst keeping the energy and upbeat-ness, but its not too bad, its on beat mostly | first 0.365, second 0.473 | 0.485 | -0.227 |
| breathe | first S05, second S03 | second | S03 | And now for breathe it swings wildly (the first) why? The second is then ofcourse much better but even it is too loopy/swingy/fast idk | first 0.797, second 0.281 | 1.17 | 0.429 |
| epitaph | first S08, second S03 | second | S03 | Second is better, but still its too stationary, its in the same direction, almost no if any rotation of the base, little movement in the shoulder etc | first 0.184, second 0.273 | 0.106 | -0.592 |
| one-of-these-days | first S01, second S08 | neither | neither | both are too small/boring on this section, they seem to do something near the end but for now its neither, they dont match the musics energy at all, its not a ballad so they shouldnt be this droopy/sad | first 0.163, second 0.0633 | -0.733 | -1.4 |
| schizoid-man | first S01, second S07 | neither | neither | Not energetic enough on the "drop" or whatever this is called after the `21st century schizoid man` line, its too soft anyway, this is an angrier/more energetic song, again, little to no shoulder/base movement, too small  | first 0.297, second 0.292 | 1.4 | 0.659 |

## Settings that failed the gates with music (replaced, 7.46.7)

| song | slot | failed setting | failed gates | values | replacement |
|---|---|---|---|---|---|
| blue-lagoon | b | S04 | contact, limits | contact_substeps 13, accel_ratio 1.18 | S06 |
| epitaph | b | S02 | contact, limits | contact_substeps 339, accel_ratio 7.32 | S03 |
| one-of-these-days | a | S06 | contact, limits | contact_substeps 180, accel_ratio 1.96 | S08 |

## Part 4: round 1 vs now

| round-1 clip | round-1 label | label now | note now |
|---|---|---|---|
| A_lag_low | tense | sad | again, sad/tense |
| A_neutral | calm | calm | calm/sad? |
| A_posture_high | light | tense | perhaps sad/tense? |
| A_vigour_high | tense | tense | - |

