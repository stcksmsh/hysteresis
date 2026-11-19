"""B3 corpus, steps 1-5 (docs/BRAIN_SPEC.md 1.4): licence filter, artist split, BY-SA rule, selection order.

Everything here is a pure function of fma_metadata/tracks.csv, the DEAM-overlap CSV and the constants below.
Rules fixed before the split was looked at:
  licence    CC BY, CC BY-SA, CC0, PD; any NC/ND string out; mapping copied from measure/scripts/m2b.py
  split      SEED_SPLIT shuffles the sorted artist ids of the whole licence-passing pool; first 10 % (rounded) are held out.
             The split ignores duration, genre and the BY-SA decision, so those cannot move an artist.
  window     60 s <= duration <= 600 s (a choice, reported for ruling)
  BY-SA      if BY+CC0+PD alone give 200 h of training-side tracks with E/P/R (recorded genre_top) >= 100 h, BY-SA is out
  order      (user ruling b, 2026-10-30, BRAIN_SPEC 1.4) training = every E/P/R track (recorded genre_top) plus "other"
             tracks from one seeded order until their hours reach (never pass) the E/P/R hours: N = 2 x E/P/R.
             Excluded tracks are skipped, so after exclusions "other" is cut at the end of the order or topped up
             from it, and E/P/R is never topped up from inferred genres.
  held-out   all window tracks of held-out artists, seeded order, until HELD_OUT_HOURS
"""
import re
import sys
import numpy as np
import pandas as pd

M = "/secondary/hyst-data/brain/measure/"
OUT = "/secondary/hyst-data/brain/corpus/"
ZIP_URL = "https://os.unil.cloud.switch.ch/fma/fma_full.zip"
SEED_SPLIT = 20261030
SEED_A = 20261031  # unused since ruling b
N_HOURS = 200.0   # BY-SA rule only (BRAIN_SPEC 1.4)
EPR_HOURS = 100.0
SEED_B = 20261032
SEED_HELD = 20261033
HELD_FRACTION = 0.10
HELD_OUT_HOURS = 20.0
DUR_MIN, DUR_MAX = 60.0, 600.0
EPR = ("Electronic", "Pop", "Rock")
_BAD = re.compile(r"non ?commercial|no ?deriv|no derivative", re.I)


def licence_class(s):
    if _BAD.search(s):
        return None
    low = s.lower().strip()
    if low == "cc0 1.0 universal":
        return "CC0"
    if low.startswith("public domain"):
        return "PD"
    m = re.match(r"^(creative commons )?attribution([- ]share ?alike)?( [\d.]+.*)?$", low)
    if m:
        return "BY-SA" if m.group(2) else "BY"
    return None


def load():
    t = pd.read_pickle(M + "tracks.pkl")
    t.index.name = "id"
    t["licence"] = t["track.license"].fillna("<missing>")
    t["cls"] = t["licence"].map(licence_class)
    t["hours"] = t["track.duration"] / 3600.0
    t["genre"] = t["track.genre_top"].fillna("other").where(t["track.genre_top"].notna(), "other")
    t["epr"] = t["track.genre_top"].isin(EPR)
    names = set(pd.read_csv(M + "fma_full_names.csv").iloc[:, 0])
    t["member"] = [f"fma_full/{i // 1000:03d}/{i:06d}.mp3" for i in t.index]
    t["in_zip"] = t["member"].isin(names)
    return t


def deam_ids():
    d = pd.read_csv(M + "m5_deam_fma_id_overlap.csv")
    return set(int(i) for i in d["index"])


def split_artists(pool):
    artists = np.array(sorted(pool["artist.id"].unique()))
    np.random.default_rng(SEED_SPLIT).shuffle(artists)
    k = int(round(HELD_FRACTION * len(artists)))
    return set(artists[:k].tolist())


def take(frame, seed, hours_cap, skip=frozenset(), strict=False):
    """Seeded order over `frame`; take until the hours reach the cap (strict: never pass it); skip IDs in `skip`."""
    order = frame.index.to_numpy().copy()
    np.random.default_rng(seed).shuffle(order)
    got, h = [], 0.0
    for i in order:
        if h >= hours_cap:
            break
        if i in skip:
            continue
        if strict and h + frame.at[i, "hours"] > hours_cap:
            break
        got.append(i)
        h += frame.at[i, "hours"]
    return got


def select(pool, held, skip=frozenset()):
    """pool: licence-passing, window, in-zip, DEAM-excluded tracks (BY-SA already decided). Returns (train_ids, held_ids)."""
    train = pool[~pool["artist.id"].isin(held)]
    a = [i for i in train[train["epr"]].index if i not in skip]          # all E/P/R (recorded genre_top)
    h = train.loc[a, "hours"].sum()
    b = take(train[~train["epr"]], SEED_B, h, skip, strict=True)         # "other" never above E/P/R hours
    hold = take(pool[pool["artist.id"].isin(held)], SEED_HELD, HELD_OUT_HOURS, skip)
    return a + b, hold


def main():
    t = load()
    pdam = deam_ids()
    lic = t[t.cls.notna()]
    held = split_artists(lic)
    lic = lic.assign(split=np.where(lic["artist.id"].isin(held), "heldout", "train"))
    win = lic[lic["track.duration"].between(DUR_MIN, DUR_MAX) & lic.in_zip]
    excl_id = win[win.index.isin(pdam)]
    pool_all = win.drop(index=excl_id.index)
    tr = pool_all[pool_all.split == "train"]
    # BY-SA rule: BY + CC0 + PD only
    nosa = tr[tr.cls != "BY-SA"]
    h_nosa, h_nosa_epr = nosa.hours.sum(), nosa[nosa.epr].hours.sum()
    by_sa_out = h_nosa >= N_HOURS and h_nosa_epr >= EPR_HOURS
    pool = pool_all[pool_all.cls != "BY-SA"] if by_sa_out else pool_all
    tr_ids, ho_ids = select(pool, held)
    sel = pool.loc[tr_ids + ho_ids]

    L = []
    L.append(f"licence-passing tracks {len(lic)} ({lic.hours.sum():.1f} h), artists {lic['artist.id'].nunique()}")
    L.append(f"held-out artists {len(held)} of {lic['artist.id'].nunique()}; seed {SEED_SPLIT}")
    for s in ("train", "heldout"):
        x = lic[lic.split == s]
        L.append(f"  split {s}: artists {x['artist.id'].nunique()}, tracks {len(x)}, hours {x.hours.sum():.1f}")
    L.append(f"window {DUR_MIN:.0f}-{DUR_MAX:.0f} s and in zip: {len(win)} tracks, {win.hours.sum():.1f} h")
    L.append(f"DEAM-ID exclusion: {len(excl_id)} of the {len(pdam)} overlap IDs fall in the windowed pool")
    L.append("training side after window and DEAM IDs, hours by class: "
             + ", ".join(f"{c} {tr[tr.cls == c].hours.sum():.1f} (E/P/R {tr[(tr.cls == c) & tr.epr].hours.sum():.1f})" for c in ("BY", "CC0", "PD", "BY-SA")))
    L.append(f"BY+CC0+PD alone: {h_nosa:.1f} h, E/P/R {h_nosa_epr:.1f} h -> BY-SA {'EXCLUDED' if by_sa_out else 'INCLUDED'}")
    L.append(f"selected: train {len(tr_ids)} tracks {sel.loc[tr_ids].hours.sum():.1f} h; heldout {len(ho_ids)} tracks {sel.loc[ho_ids].hours.sum():.1f} h")
    L.append("train by genre_top (hours): " + ", ".join(f"{g} {h:.1f}" for g, h in sel.loc[tr_ids].groupby("genre").hours.sum().sort_values(ascending=False).items()))
    L.append("train by class (hours): " + ", ".join(f"{g} {h:.1f}" for g, h in sel.loc[tr_ids].groupby("cls").hours.sum().items()))
    ta = sel.loc[tr_ids].groupby("artist.id").hours.sum().sort_values(ascending=False)
    L.append(f"train artists {len(ta)}; largest artist {ta.iloc[0]:.1f} h; top 5 {ta.head(5).sum():.1f} h")
    print("\n".join(L))

    cols = ["artist.id", "artist.name", "track.title", "licence", "cls", "track.duration", "hours", "genre", "epr", "member"]
    sel2 = sel[cols].copy()
    sel2["split"] = ["train"] * len(tr_ids) + ["heldout"] * len(ho_ids)
    sel2["rank"] = list(range(len(tr_ids))) + list(range(len(ho_ids)))
    sel2.to_csv(OUT + "selection.csv")
    excl_id[["artist.name", "track.title"]].to_csv(OUT + "excluded_by_id.csv")
    # SOURCES.md: every licence-passing track
    with open(OUT + "SOURCES.md", "w") as f:
        f.write("# B3 corpus sources (FMA fma_full)\n\n")
        f.write("Licence filter: CC BY, CC BY-SA, CC0, public domain. Any NC or ND string, Free Music Philosophy, Art Libre,\n")
        f.write("Sampling Plus, CopyrightPlus, EFF Open Audio, missing and other unclear strings are out.\n")
        f.write(f"FMA metadata has no per-track page URL, only the licence string; URL below is the member of `{ZIP_URL}`.\n\n")
        f.write("## Licence strings (all FMA tracks)\n\n| tracks | class | string |\n|---|---|---|\n")
        vc = t.groupby(["licence"]).size().sort_values(ascending=False)
        for s, n in vc.items():
            f.write(f"| {n} | {licence_class(s) or 'out'} | {s} |\n")
        f.write(f"\n## Tracks with passing licence ({len(lic)}); selected ones are marked in selection.csv\n\n")
        f.write("id | artist | title | licence string | class | URL\n---|---|---|---|---|---\n")
        for i, r in lic.iterrows():
            f.write(f"{i} | {r['artist.name']} | {r['track.title']} | {r['licence']} | {r['cls']} | {ZIP_URL}#{r['member']}\n")
    open(OUT + "selection_report.txt", "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
