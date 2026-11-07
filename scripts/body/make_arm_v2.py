"""The M3f body (docs/BRAIN_SPEC.md 7.24 "Body"): make_arm.py's M0 arm plus a table plane at z = 0 (the base's mounting plane, the plane score_csv.rs uses) with contact and
self-collision. Provisional servo model (Feetech STS3215 12 V assumed). make_arm.py and arm.xml are unchanged; this file edits their text.

Collision geometry (contype/conaffinity bits: 1 table, 2 arm parts, 4 base column):
  * the five link capsules of the arm (radius 0.01 = half the 0.02 m tube), the base column (capsule, z 0 .. 0.08) and the mirror ball (sphere, radius DISC_M = 0.06, the hand
    disc check-csv uses) collide with each other; MuJoCo skips parent-child body pairs on its own;
  * the table collides with every arm part except the column (which stands on it);
  * the servo boxes stay non-colliding (they are the joints' own housings; their box-box contacts are not modelled): flagged, not hidden.
Joint ranges are those of make_arm.py (+-110 deg on the three bends; the base yaw and the roll are continuous).
"""
import re

import make_arm as MA

DISC_M = 0.06            # score_csv.rs / body.rs DISC_M: the mirror ball's check disc
LIMIT_MARGIN_DEG = 10.0  # BRAIN_SPEC 7.24: a small cost within this angle of any joint limit
TABLE_Z = 0.0


def xml_v2(kv=None, table=True, self_collision=True, condim=3, table_z=TABLE_Z):
    xml = MA.build_xml(kv) if kv is not None else MA.final_xml()
    n = [0]

    def caps(m):
        n[0] += 1
        col = n[0] == 1                                              # the first capsule is the base column
        bits = 'contype="4" conaffinity="2"' if col else 'contype="2" conaffinity="3"'
        if not self_collision:
            bits = 'contype="0" conaffinity="0"' if col else 'contype="2" conaffinity="1"'
        return m.group(1) + bits + m.group(2)
    xml = re.sub(r'(<geom type="capsule"[^>]*?)contype="0" conaffinity="0"([^>]*>)', caps, xml)
    assert n[0] == 5, n[0]
    sphere = f'<geom type="sphere" size="{DISC_M}" contype="2" conaffinity="3" rgba="0.7 0.7 0.9 0.5"/>' if self_collision else \
        f'<geom type="sphere" size="{DISC_M}" contype="2" conaffinity="1" rgba="0.7 0.7 0.9 0.5"/>'
    xml = xml.replace('<site name="hand"', sphere + '\n                  <site name="hand"', 1)
    if table:
        xml = xml.replace("<worldbody>", f'<worldbody>\n    <geom name="table" type="plane" size="2 2 0.1" pos="0 0 {table_z}" contype="1" conaffinity="0" rgba="0.4 0.4 0.4 1"/>', 1)
    if condim != 3:                                                  # frictionless contacts (condim 1): one constraint row per contact instead of four
        xml = re.sub(r'(<geom [^>]*contype="[1-4]"[^>]*?)(/?>)', lambda m: m.group(1) + f' condim="{condim}"' + m.group(2), xml)
    return xml
