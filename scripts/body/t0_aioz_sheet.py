"""draw contact_sheet.json -> contact_sheet.png (system python3 with matplotlib; no numpy needed): python3 t0_aioz_sheet.py DIR"""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

d = json.load(open(sys.argv[1] + "/contact_sheet.json"))
fig, ax = plt.subplots(2, 3, figsize=(9, 6))
for a, s in zip(ax.flat, d["sheet"]):
    P = s["P"]
    for c in range(1, 22):
        p = d["parent"][c]
        a.plot([P[p][0], P[c][0]], [P[p][1], P[c][1]], "k-")
    a.set_aspect("equal")
    a.set_title(s["title"], fontsize=7)
fig.savefig(sys.argv[1] + "/contact_sheet.png", dpi=90)
