"""B3 corpus step 7, rounds: apply the fingerprint exclusions to the selection and report what still has to be fetched.

usage: corpus_finalize.py            -> reads fp_matches.csv (union kept in excluded_by_fingerprint.csv), re-runs the
                                        selection with every excluded ID skipped (ruling b: other cut or topped up from
                                        its seeded order, E/P/R never topped up), writes selection_round.csv and
                                        dl_list.csv (the tracks of the new selection not yet on disk).
       corpus_finalize.py final      -> when nothing is missing and nothing new matched: final_corpus.csv with sha256
                                        per audio file, written for the committed lists.
"""
import csv
import hashlib
import os
import sys

import numpy as np
import pandas as pd

import corpus_select as cs

C = cs.OUT


def pools():
    t = cs.load()
    lic = t[t.cls.notna()]
    held = cs.split_artists(lic)
    lic = lic.assign(split=np.where(lic["artist.id"].isin(held), "heldout", "train"))
    win = lic[lic["track.duration"].between(cs.DUR_MIN, cs.DUR_MAX) & lic.in_zip]
    win = win.drop(index=win[win.index.isin(cs.deam_ids())].index)
    return win, held                       # BY-SA included (corpus_select report)


def excluded_fp():
    path = C + "excluded_by_fingerprint.csv"
    old = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame(columns=["id", "ber", "reference"])
    new = pd.read_csv(C + "fp_matches.csv")
    new = pd.DataFrame({"id": new["file"].str.replace(".mp3", "", regex=False).astype(int), "ber": new["ber"], "reference": new["reference"]})
    both = pd.concat([old, new]).sort_values("ber").drop_duplicates("id").sort_values("id")
    both.to_csv(path, index=False)
    return both


def main():
    pool, held = pools()
    if len(sys.argv) > 1 and sys.argv[1] == "final":
        sel = pd.read_csv(C + "selection_round.csv", index_col="id")
        rows = []
        for i, r in sel.iterrows():
            h = hashlib.sha256(open(f"{C}audio/{i:06d}.mp3", "rb").read()).hexdigest()
            rows.append((i, r["split"], r["genre"], r["cls"], round(r["hours"], 5), r["artist.id"], h))
        pd.DataFrame(rows, columns=["id", "split", "genre", "cls", "hours", "artist_id", "sha256"]).to_csv(C + "final_corpus.csv", index=False)
        print("final_corpus.csv", len(rows))
        return 0
    ex = excluded_fp()
    skip = set(int(i) for i in ex["id"])
    tr_ids, ho_ids = cs.select(pool, held, skip)
    sel = pool.loc[tr_ids + ho_ids]
    sel = sel.assign(split=["train"] * len(tr_ids) + ["heldout"] * len(ho_ids))
    sel[["artist.id", "artist.name", "track.title", "licence", "cls", "hours", "genre", "epr", "member", "split"]].to_csv(C + "selection_round.csv")
    have = set(int(f[:6]) for f in os.listdir(C + "audio") if f.endswith(".mp3"))
    miss = sel[~sel.index.isin(have)]
    miss[["member"]].to_csv(C + "dl_list.csv", index_label="id")
    tr = sel[sel.split == "train"]
    epr = tr[tr.epr].hours.sum()
    print(f"fingerprint-excluded IDs {len(skip)}; in selection before: {len(skip & set(pool.index))}")
    print(f"train {len(tr)} tracks {tr.hours.sum():.2f} h (E/P/R {epr:.2f} h, other {tr[~tr.epr].hours.sum():.2f} h); heldout {(sel.split == 'heldout').sum()} tracks {sel[sel.split == 'heldout'].hours.sum():.2f} h")
    print(f"to fetch: {len(miss)} tracks {miss.hours.sum():.2f} h")
    return 0


if __name__ == "__main__":
    sys.exit(main())
