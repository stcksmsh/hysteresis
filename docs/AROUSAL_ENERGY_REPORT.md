# Arousal and ear energy against Kosta's dials and the five excerpts (WO30A, BRAIN_SPEC 7.47)

Numbers only. No verdict, no interpretation. Formula of ear energy: `docs/EAR_ENERGY_RULES.md`. Method: each signal and each dial axis is smoothed with a 2 s moving mean and taken at 2 Hz; Pearson and Spearman at every lag from -2 s to +4 s in 0.5 s steps (positive lag = dial behind the music). All lags are listed; none is picked. n is the number of 2 Hz pairs.

**Instant Crush pass A is the first try on the older pad (file `dial-ic-try1.json`, arousal axis, take stopped at about 329 s): it is marked TRY1 in every table.**

## five-years, pass A, energy

| lag s | arousal_b7 Pearson | arousal_b7 Spearman | ear energy Pearson | ear energy Spearman | n |
|---|---|---|---|---|---|
| -2.0 | -0.803 | -0.820 | 0.750 | 0.683 | 563 |
| -1.5 | -0.798 | -0.815 | 0.759 | 0.690 | 564 |
| -1.0 | -0.791 | -0.809 | 0.766 | 0.696 | 565 |
| -0.5 | -0.783 | -0.801 | 0.772 | 0.700 | 566 |
| +0.0 | -0.772 | -0.791 | 0.776 | 0.703 | 567 |
| +0.5 | -0.769 | -0.786 | 0.776 | 0.702 | 566 |
| +1.0 | -0.766 | -0.781 | 0.775 | 0.700 | 565 |
| +1.5 | -0.762 | -0.775 | 0.772 | 0.698 | 564 |
| +2.0 | -0.756 | -0.768 | 0.769 | 0.696 | 563 |
| +2.5 | -0.750 | -0.761 | 0.765 | 0.693 | 562 |
| +3.0 | -0.743 | -0.753 | 0.760 | 0.689 | 561 |
| +3.5 | -0.735 | -0.744 | 0.755 | 0.685 | 560 |
| +4.0 | -0.727 | -0.735 | 0.750 | 0.680 | 559 |

## presence, pass A, energy

| lag s | arousal_b7 Pearson | arousal_b7 Spearman | ear energy Pearson | ear energy Spearman | n |
|---|---|---|---|---|---|
| -2.0 | 0.024 | -0.223 | 0.756 | 0.826 | 537 |
| -1.5 | 0.043 | -0.224 | 0.772 | 0.839 | 538 |
| -1.0 | 0.062 | -0.223 | 0.786 | 0.850 | 539 |
| -0.5 | 0.078 | -0.218 | 0.797 | 0.860 | 540 |
| +0.0 | 0.092 | -0.209 | 0.804 | 0.866 | 541 |
| +0.5 | 0.116 | -0.191 | 0.816 | 0.867 | 540 |
| +1.0 | 0.135 | -0.169 | 0.819 | 0.864 | 539 |
| +1.5 | 0.149 | -0.147 | 0.812 | 0.857 | 538 |
| +2.0 | 0.158 | -0.125 | 0.798 | 0.845 | 537 |
| +2.5 | 0.164 | -0.106 | 0.782 | 0.831 | 536 |
| +3.0 | 0.168 | -0.089 | 0.766 | 0.818 | 535 |
| +3.5 | 0.173 | -0.073 | 0.751 | 0.805 | 534 |
| +4.0 | 0.177 | -0.057 | 0.737 | 0.792 | 533 |

## instant-crush, pass B, light

| lag s | arousal_b7 Pearson | arousal_b7 Spearman | ear energy Pearson | ear energy Spearman | n |
|---|---|---|---|---|---|
| -2.0 | -0.560 | -0.507 | 0.581 | 0.708 | 675 |
| -1.5 | -0.529 | -0.502 | 0.630 | 0.718 | 676 |
| -1.0 | -0.494 | -0.497 | 0.673 | 0.725 | 677 |
| -0.5 | -0.460 | -0.490 | 0.709 | 0.729 | 678 |
| +0.0 | -0.427 | -0.483 | 0.736 | 0.731 | 679 |
| +0.5 | -0.398 | -0.482 | 0.745 | 0.729 | 678 |
| +1.0 | -0.385 | -0.481 | 0.747 | 0.726 | 677 |
| +1.5 | -0.389 | -0.488 | 0.740 | 0.722 | 676 |
| +2.0 | -0.396 | -0.495 | 0.726 | 0.716 | 675 |
| +2.5 | -0.404 | -0.499 | 0.707 | 0.710 | 674 |
| +3.0 | -0.409 | -0.500 | 0.686 | 0.703 | 673 |
| +3.5 | -0.411 | -0.499 | 0.665 | 0.695 | 672 |
| +4.0 | -0.410 | -0.496 | 0.647 | 0.686 | 671 |

## instant-crush, pass B, heavy

| lag s | arousal_b7 Pearson | arousal_b7 Spearman | ear energy Pearson | ear energy Spearman | n |
|---|---|---|---|---|---|
| -2.0 | -0.292 | -0.046 | 0.253 | 0.117 | 675 |
| -1.5 | -0.260 | -0.033 | 0.278 | 0.107 | 676 |
| -1.0 | -0.228 | -0.021 | 0.303 | 0.096 | 677 |
| -0.5 | -0.194 | -0.007 | 0.326 | 0.087 | 678 |
| +0.0 | -0.160 | 0.008 | 0.346 | 0.080 | 679 |
| +0.5 | -0.121 | 0.021 | 0.327 | 0.066 | 678 |
| +1.0 | -0.094 | 0.032 | 0.305 | 0.053 | 677 |
| +1.5 | -0.081 | 0.033 | 0.278 | 0.042 | 676 |
| +2.0 | -0.071 | 0.033 | 0.248 | 0.033 | 675 |
| +2.5 | -0.065 | 0.032 | 0.213 | 0.026 | 674 |
| +3.0 | -0.061 | 0.030 | 0.175 | 0.019 | 673 |
| +3.5 | -0.059 | 0.028 | 0.136 | 0.013 | 672 |
| +4.0 | -0.057 | 0.025 | 0.097 | 0.006 | 671 |

## presence, pass B, light

| lag s | arousal_b7 Pearson | arousal_b7 Spearman | ear energy Pearson | ear energy Spearman | n |
|---|---|---|---|---|---|
| -2.0 | -0.064 | -0.136 | 0.625 | 0.622 | 537 |
| -1.5 | -0.070 | -0.141 | 0.637 | 0.637 | 538 |
| -1.0 | -0.070 | -0.144 | 0.642 | 0.648 | 539 |
| -0.5 | -0.065 | -0.143 | 0.642 | 0.654 | 540 |
| +0.0 | -0.056 | -0.141 | 0.638 | 0.660 | 541 |
| +0.5 | -0.068 | -0.144 | 0.671 | 0.672 | 540 |
| +1.0 | -0.079 | -0.149 | 0.703 | 0.684 | 539 |
| +1.5 | -0.087 | -0.155 | 0.728 | 0.695 | 538 |
| +2.0 | -0.090 | -0.161 | 0.743 | 0.706 | 537 |
| +2.5 | -0.089 | -0.162 | 0.752 | 0.715 | 536 |
| +3.0 | -0.087 | -0.156 | 0.757 | 0.722 | 535 |
| +3.5 | -0.086 | -0.149 | 0.760 | 0.726 | 534 |
| +4.0 | -0.084 | -0.140 | 0.763 | 0.729 | 533 |

## presence, pass B, heavy

| lag s | arousal_b7 Pearson | arousal_b7 Spearman | ear energy Pearson | ear energy Spearman | n |
|---|---|---|---|---|---|
| -2.0 | -0.075 | -0.291 | 0.432 | 0.441 | 537 |
| -1.5 | -0.057 | -0.280 | 0.448 | 0.448 | 538 |
| -1.0 | -0.038 | -0.268 | 0.460 | 0.453 | 539 |
| -0.5 | -0.017 | -0.254 | 0.470 | 0.458 | 540 |
| +0.0 | 0.004 | -0.238 | 0.476 | 0.460 | 541 |
| +0.5 | 0.036 | -0.217 | 0.469 | 0.455 | 540 |
| +1.0 | 0.064 | -0.196 | 0.459 | 0.448 | 539 |
| +1.5 | 0.086 | -0.177 | 0.445 | 0.441 | 538 |
| +2.0 | 0.103 | -0.157 | 0.429 | 0.433 | 537 |
| +2.5 | 0.116 | -0.136 | 0.412 | 0.423 | 536 |
| +3.0 | 0.126 | -0.118 | 0.395 | 0.412 | 535 |
| +3.5 | 0.135 | -0.098 | 0.377 | 0.400 | 534 |
| +4.0 | 0.143 | -0.077 | 0.359 | 0.385 | 533 |

## five-years, pass B, light

| lag s | arousal_b7 Pearson | arousal_b7 Spearman | ear energy Pearson | ear energy Spearman | n |
|---|---|---|---|---|---|
| -2.0 | -0.233 | -0.192 | 0.480 | 0.492 | 563 |
| -1.5 | -0.228 | -0.189 | 0.481 | 0.493 | 564 |
| -1.0 | -0.223 | -0.185 | 0.481 | 0.492 | 565 |
| -0.5 | -0.216 | -0.180 | 0.480 | 0.488 | 566 |
| +0.0 | -0.209 | -0.172 | 0.478 | 0.482 | 567 |
| +0.5 | -0.205 | -0.166 | 0.468 | 0.471 | 566 |
| +1.0 | -0.201 | -0.160 | 0.457 | 0.460 | 565 |
| +1.5 | -0.197 | -0.153 | 0.445 | 0.450 | 564 |
| +2.0 | -0.193 | -0.146 | 0.433 | 0.439 | 563 |
| +2.5 | -0.190 | -0.138 | 0.421 | 0.429 | 562 |
| +3.0 | -0.187 | -0.131 | 0.409 | 0.420 | 561 |
| +3.5 | -0.184 | -0.123 | 0.399 | 0.412 | 560 |
| +4.0 | -0.180 | -0.115 | 0.390 | 0.405 | 559 |

## five-years, pass B, heavy

| lag s | arousal_b7 Pearson | arousal_b7 Spearman | ear energy Pearson | ear energy Spearman | n |
|---|---|---|---|---|---|
| -2.0 | -0.701 | -0.732 | 0.755 | 0.555 | 563 |
| -1.5 | -0.692 | -0.723 | 0.763 | 0.562 | 564 |
| -1.0 | -0.682 | -0.714 | 0.769 | 0.566 | 565 |
| -0.5 | -0.669 | -0.704 | 0.774 | 0.567 | 566 |
| +0.0 | -0.655 | -0.692 | 0.777 | 0.564 | 567 |
| +0.5 | -0.651 | -0.685 | 0.774 | 0.555 | 566 |
| +1.0 | -0.648 | -0.677 | 0.769 | 0.546 | 565 |
| +1.5 | -0.643 | -0.667 | 0.763 | 0.537 | 564 |
| +2.0 | -0.638 | -0.658 | 0.756 | 0.529 | 563 |
| +2.5 | -0.632 | -0.647 | 0.747 | 0.522 | 562 |
| +3.0 | -0.624 | -0.636 | 0.736 | 0.513 | 561 |
| +3.5 | -0.613 | -0.624 | 0.726 | 0.504 | 560 |
| +4.0 | -0.600 | -0.610 | 0.715 | 0.494 | 559 |

## instant-crush, pass A, energy (TRY1, older pad)

| lag s | arousal_b7 Pearson | arousal_b7 Spearman | ear energy Pearson | ear energy Spearman | n |
|---|---|---|---|---|---|
| -2.0 | -0.471 | -0.593 | 0.347 | 0.609 | 675 |
| -1.5 | -0.462 | -0.591 | 0.361 | 0.619 | 676 |
| -1.0 | -0.453 | -0.588 | 0.374 | 0.629 | 677 |
| -0.5 | -0.443 | -0.581 | 0.387 | 0.637 | 678 |
| +0.0 | -0.430 | -0.572 | 0.396 | 0.644 | 679 |
| +0.5 | -0.432 | -0.573 | 0.416 | 0.648 | 678 |
| +1.0 | -0.428 | -0.573 | 0.433 | 0.650 | 677 |
| +1.5 | -0.424 | -0.572 | 0.445 | 0.648 | 676 |
| +2.0 | -0.421 | -0.571 | 0.454 | 0.644 | 675 |
| +2.5 | -0.419 | -0.571 | 0.459 | 0.637 | 674 |
| +3.0 | -0.419 | -0.571 | 0.461 | 0.629 | 673 |
| +3.5 | -0.421 | -0.570 | 0.462 | 0.619 | 672 |
| +4.0 | -0.423 | -0.568 | 0.463 | 0.609 | 671 |

## arousal_b7 against ear energy, lag 0, per song

| song | n | Pearson | Spearman |
|---|---|---|---|
| instant-crush | 679 | -0.234 | -0.407 |
| five-years | 567 | -0.552 | -0.583 |
| presence | 541 | -0.027 | -0.096 |
| blue-lagoon | 610 | -0.536 | -0.302 |
| schizoid-man | 885 | -0.007 | 0.000 |
| epitaph | 1053 | -0.303 | -0.415 |
| breathe | 331 | -0.119 | -0.075 |
| one-of-these-days | 711 | 0.070 | 0.267 |

## The five excerpts (12 s shown in round 1), mean of each signal, ranked, beside Kosta's Part 3 notes

| song | start s | arousal_b7 raw | arousal_b7 std | rank | ear energy raw | ear energy std | rank | settings first / second | pick | Kosta's note |
|---|---|---|---|---|---|---|---|---|---|---|
| blue-lagoon | 20.000 | 0.485 | -0.227 | 3 | 1.273 | 1.590 | 1 | S03 / S06 | first | Id say first (more "on the music" and less janky), but theyre both too simple/repetitive loops facing the same direction always? Takanaka is jazz fusion, the guitar melody here is more than just loops, it can be better and more on-point whilst keeping the energy and upbeat-ness, but its not too bad, its on beat mostly |
| schizoid-man | 58.000 | 1.405 | 0.659 | 1 | 0.342 | 0.427 | 2 | S01 / S07 | neither | Not energetic enough on the "drop" or whatever this is called after the `21st century schizoid man` line, its too soft anyway, this is an angrier/more energetic song, again, little to no shoulder/base movement, too small  |
| epitaph | 345.000 | 0.106 | -0.592 | 4 | -0.016 | -0.021 | 3 | S08 / S03 | second | Second is better, but still its too stationary, its in the same direction, almost no if any rotation of the base, little movement in the shoulder etc |
| breathe | 77.000 | 1.166 | 0.429 | 2 | -0.399 | -0.499 | 5 | S05 / S03 | second | And now for breathe it swings wildly (the first) why? The second is then ofcourse much better but even it is too loopy/swingy/fast idk |
| one-of-these-days | 237.000 | -0.733 | -1.401 | 5 | -0.153 | -0.192 | 4 | S01 / S08 | neither | both are too small/boring on this section, they seem to do something near the end but for now its neither, they dont match the musics energy at all, its not a ballad so they shouldnt be this droopy/sad |
