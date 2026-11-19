"""WO55 B (BRAIN_SPEC 7.87 Q3): arm-only page patch. Usage: armonly_page.py IN.html OUT.html

The round-1 pillar patch (retarget_page.patch), then the hand-path trail (4 s ribbon) and the look-ahead hint (1.5 s ahead) are
switched off by setting both drawing loops to zero iterations. crates/hyst-previz/src/ensemble.html is not edited; every
replacement must match exactly once, else the script stops.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retarget_page as RP  # noqa: E402

TRAIL = ("for(let k=-120;k<0;k++) {", "for(let k=-120;k<-120;k++) {")
HINT = ("for(let k=0;k<22;k++) {", "for(let k=0;k<0;k++) {")


def patch(s):
    s = RP.patch(s)
    for old, new in (TRAIL, HINT):
        s = RP.rep(s, old, new)
    return s


def is_arm_only(s):
    return s.count(TRAIL[1]) == 1 and s.count(HINT[1]) == 1 and TRAIL[0] not in s and HINT[0] not in s


if __name__ == "__main__":
    src, dst = sys.argv[1:3]
    open(dst, "w").write(patch(open(src).read()))
