#!/usr/bin/env python3
"""Independent numeric audit of three resolved ensemble scores.

Usage: ensemble_acceptance.py SCORE GROOVE_SCORE NO_REUSE_SCORE REFERENCE_JSON OUTPUT
References name review windows only; compilation never reads this file.
"""

from __future__ import annotations

import bisect
import json
import math
import sys
from pathlib import Path

EPS = 1e-6
SAMPLE_HZ = 60


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def rotate(vector, axis, degrees):
    radians = math.radians(degrees)
    c, s = math.cos(radians), math.sin(radians)
    k = cross(axis, vector)
    parallel = dot(axis, vector) * (1 - c)
    return [vector[i] * c + k[i] * s + axis[i] * parallel for i in range(3)]


def fk(rig, placement, joints):
    """Carry each local basis through upstream rotations; metres, Z up."""
    origin = placement["originM"]
    yaw = placement["yawDegrees"]
    basis = [rotate(v, [0, 0, 1], yaw) for v in ([1, 0, 0], [0, 1, 0], [0, 0, 1])]
    point = list(origin)
    points = [point[:]]
    for channel, angle in zip(rig["channels"], joints):
        axis = [sum(basis[j][i] * channel["axisLocal"][j] for j in range(3)) for i in range(3)]
        basis = [rotate(v, axis, angle) for v in basis]
        link = [sum(basis[j][i] * channel["linkM"][j] for j in range(3)) for i in range(3)]
        point = [point[i] + link[i] for i in range(3)]
        points.append(point)
    return points


def hermite(a, b, time):
    """Quintic Hermite with supplied endpoint velocity and zero acceleration."""
    dt = b["time"] - a["time"]
    u = (time - a["time"]) / dt
    u2, u3, u4, u5 = u * u, u**3, u**4, u**5
    h0 = 1 - 10 * u3 + 15 * u4 - 6 * u5
    h1 = 10 * u3 - 15 * u4 + 6 * u5
    hv0 = u - 6 * u3 + 8 * u4 - 3 * u5
    hv1 = -4 * u3 + 7 * u4 - 3 * u5
    d0 = -30 * u2 + 60 * u3 - 30 * u4
    d1 = -d0
    dv0 = 1 - 18 * u2 + 32 * u3 - 15 * u4
    dv1 = -12 * u2 + 28 * u3 - 15 * u4
    dd0 = -60 * u + 180 * u2 - 120 * u3
    dd1 = -dd0
    ddv0 = -36 * u + 96 * u2 - 60 * u3
    ddv1 = -24 * u + 84 * u2 - 60 * u3
    q, v, acc = [], [], []
    for qa, qb, va, vb in zip(a["jointsDegrees"], b["jointsDegrees"], a["velocityDegreesPerSecond"], b["velocityDegreesPerSecond"]):
        q.append(h0 * qa + h1 * qb + dt * (hv0 * va + hv1 * vb))
        v.append((d0 * qa + d1 * qb) / dt + dv0 * va + dv1 * vb)
        acc.append((dd0 * qa + dd1 * qb) / dt**2 + (ddv0 * va + ddv1 * vb) / dt)
    return q, v, acc


class Sampler:
    def __init__(self, score):
        self.score = score
        self.times = [[k["time"] for k in track["knots"]] for track in score["tracks"]]

    def sample(self, agent, time):
        knots = self.score["tracks"][agent]["knots"]
        times = self.times[agent]
        t = max(0.0, min(self.score["duration"], time))
        i = max(0, min(len(knots) - 2, bisect.bisect_right(times, t) - 1))
        return hermite(knots[i], knots[i + 1], t)

    def points(self, agent, time):
        return fk(self.score["rig"], self.score["placements"][agent], self.sample(agent, time)[0])


def finite_tree(value):
    if isinstance(value, dict):
        return all(finite_tree(v) for v in value.values())
    if isinstance(value, list):
        return all(finite_tree(v) for v in value)
    return not isinstance(value, (int, float)) or math.isfinite(value)


def validate_shape(score):
    errors = []
    duration = score.get("duration")
    rig = score.get("rig", {}).get("channels", [])
    cues = score.get("cues", [])
    tracks = score.get("tracks", [])
    placements = score.get("placements", [])
    if not finite_tree(score):
        errors.append("nonfinite score value")
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        return ["invalid duration"]
    if not rig or not tracks or len(placements) != len(tracks) or not cues:
        return ["empty/mismatched rig, agents, placements or cues"]
    expected = 0.0
    for i, cue in enumerate(cues):
        if abs(cue["start"] - expected) > EPS or cue["end"] <= cue["start"]:
            errors.append(f"cue {i} gap/overlap")
        if len(cue.get("profile", [])) < 2:
            errors.append(f"cue {i} missing profile")
        expected = cue["end"]
    if abs(expected - duration) > EPS:
        errors.append("cue coverage ends before/after score")
    reference_times = None
    for i, (track, placement) in enumerate(zip(tracks, placements)):
        knots = track.get("knots", [])
        if track.get("id") != i or len(knots) < 2:
            errors.append(f"agent {i} id/knot count")
            continue
        if not all(math.isfinite(x) for x in placement["originM"] + [placement["yawDegrees"]]):
            errors.append(f"agent {i} placement nonfinite")
        times = [k["time"] for k in knots]
        if abs(times[0]) > EPS or abs(times[-1] - duration) > EPS or any(b <= a for a, b in zip(times, times[1:])):
            errors.append(f"agent {i} knot coverage/order")
        if reference_times is None:
            reference_times = times
        elif len(times) != len(reference_times) or any(abs(a - b) > EPS for a, b in zip(times, reference_times)):
            errors.append(f"agent {i} clock differs")
        for k in knots:
            if len(k["jointsDegrees"]) != len(rig) or len(k["velocityDegreesPerSecond"]) != len(rig):
                errors.append(f"agent {i} knot channel count")
                break
    for i, channel in enumerate(rig):
        axis = channel["axisLocal"]
        if abs(math.sqrt(dot(axis, axis)) - 1) > EPS:
            errors.append(f"channel {i} axis not unit")
        if channel["minDegrees"] >= channel["maxDegrees"] or channel["maxSpeedDegreesPerSecond"] <= 0 or channel["maxAccelerationDegreesPerSecond2"] <= 0:
            errors.append(f"channel {i} limits invalid")
    return errors


def audit_motion(score):
    """Sample every segment densely; independent from Rust Bezier bounds."""
    errors = validate_shape(score)
    if errors:
        return {"errors": errors}
    sampler = Sampler(score)
    rig = score["rig"]["channels"]
    min_floor = [float("inf"), None, None, None]
    max_speed = [0.0] * len(rig)
    max_accel = [0.0] * len(rig)
    samples = 0
    for agent, track in enumerate(score["tracks"]):
        knots = track["knots"]
        for n, (a, b) in enumerate(zip(knots, knots[1:])):
            # Each shared knot supplies one q/v and zero a to both neighbours.
            if n:
                left = hermite(knots[n - 1], a, a["time"])
                right = hermite(a, b, a["time"])
                if any(abs(x - y) > 1e-5 for la, ra in zip(left, right) for x, y in zip(la, ra)):
                    errors.append(f"agent {agent} derivative discontinuity knot {n}")
            steps = max(16, math.ceil((b["time"] - a["time"]) * SAMPLE_HZ))
            for j in range(steps + 1):
                time = a["time"] + (b["time"] - a["time"]) * j / steps
                q, v, acc = hermite(a, b, time)
                samples += 1
                for c, channel in enumerate(rig):
                    max_speed[c] = max(max_speed[c], abs(v[c]))
                    max_accel[c] = max(max_accel[c], abs(acc[c]))
                    if q[c] < channel["minDegrees"] - 1e-4 or q[c] > channel["maxDegrees"] + 1e-4:
                        errors.append(f"agent {agent} channel {c} position limit at {time:.3f}s")
                    if abs(v[c]) > channel["maxSpeedDegreesPerSecond"] + 1e-4:
                        errors.append(f"agent {agent} channel {c} speed limit at {time:.3f}s")
                    if abs(acc[c]) > channel["maxAccelerationDegreesPerSecond2"] + 1e-3:
                        errors.append(f"agent {agent} channel {c} acceleration limit at {time:.3f}s")
                points = fk(score["rig"], score["placements"][agent], q)
                for link, point in enumerate(points):
                    if point[2] < min_floor[0]:
                        min_floor = [point[2], time, agent, link]
                if len(errors) > 30:
                    break
            if len(errors) > 30:
                break
    if min_floor[0] < -1e-4:
        errors.append(f"illustrative rig below floor by {-min_floor[0]:.4f}m at {min_floor[1]:.3f}s agent {min_floor[2]} link {min_floor[3]}")
    return {"errors": errors, "samples": samples, "minimumFloorM": min_floor, "maxSpeedDegreesPerSecond": max_speed, "maxAccelerationDegreesPerSecond2": max_accel}


def region_metrics(score, sampler, start, end):
    count = len(score["tracks"])
    steps = max(2, math.ceil((end - start) * 30))
    tips = [[] for _ in range(count)]
    joint_values = [[[] for _ in score["rig"]["channels"]] for _ in range(count)]
    for step in range(steps + 1):
        time = start + (end - start) * step / steps
        for agent in range(count):
            q = sampler.sample(agent, time)[0]
            tips[agent].append(fk(score["rig"], score["placements"][agent], q)[-1])
            for channel, value in enumerate(q):
                joint_values[agent][channel].append(value)
    travels = []
    speeds = []
    tip_ranges = []
    joint_ranges = []
    for agent in range(count):
        travel = sum(math.dist(a, b) for a, b in zip(tips[agent], tips[agent][1:]))
        travels.append(travel)
        speeds.append(travel / (end - start))
        tip_ranges.append([max(p[i] for p in tips[agent]) - min(p[i] for p in tips[agent]) for i in range(3)])
        joint_ranges.append([max(v) - min(v) for v in joint_values[agent]])
    chars = {}
    formations = {}
    source = [0.0] * 4
    recall = 0.0
    anticipated = []
    for cue in score["cues"]:
        overlap = max(0.0, min(end, cue["end"]) - max(start, cue["start"]))
        if not overlap:
            continue
        chars[cue["character"]] = chars.get(cue["character"], 0.0) + overlap
        formations[cue["formation"]] = formations.get(cue["formation"], 0.0) + overlap
        for i in range(4):
            source[i] += cue["sourceActivity"][i] * overlap / (end - start)
        if cue.get("recallFrom") is not None:
            recall += overlap
        if cue.get("anticipation") is not None and cue["anticipation"] not in anticipated:
            anticipated.append(cue["anticipation"])
    holds = []
    for track in score["tracks"]:
        current = 0.0
        longest = 0.0
        for a, b in zip(track["knots"], track["knots"][1:]):
            overlap = max(0.0, min(end, b["time"]) - max(start, a["time"]))
            if overlap and max(abs(x-y) for x,y in zip(a["jointsDegrees"],b["jointsDegrees"])) < 1e-5 and max(map(abs,a["velocityDegreesPerSecond"]+b["velocityDegreesPerSecond"])) < 1e-5:
                current += overlap
                longest = max(longest, current)
            elif overlap:
                current = 0.0
        holds.append(longest)
    return {"start":start,"end":end,"sourceActivityMean":{"bass":source[0],"drums":source[1],"vocals":source[2],"other":source[3]},"characterSeconds":chars,"formationSeconds":formations,"recallSeconds":recall,"anticipatedArrivals":sorted(anticipated),"tipTravelM":travels,"tipMeanSpeedMPerSecond":speeds,"tipAxisRangeM":tip_ranges,"jointRangeDegrees":joint_ranges,"longestExactHoldSeconds":holds}


def difference(a, b, start, end):
    sa, sb = Sampler(a), Sampler(b)
    steps = max(2, math.ceil((end - start) * 20))
    total = 0.0
    largest = 0.0
    count = 0
    for i in range(steps + 1):
        t = start + (end - start) * i / steps
        for agent in range(len(a["tracks"])):
            qa = sa.sample(agent, t)[0]
            qb = sb.sample(agent, t)[0]
            for x, y in zip(qa, qb):
                delta = abs(x - y)
                total += delta
                largest = max(largest, delta)
                count += 1
    return {"meanAbsoluteJointDegrees":total/count,"maxAbsoluteJointDegrees":largest}


def self_test():
    a = {"time":0.0,"jointsDegrees":[0.0],"velocityDegreesPerSecond":[0.0]}
    b = {"time":2.0,"jointsDegrees":[1.0],"velocityDegreesPerSecond":[0.0]}
    q, v, acc = hermite(a, b, 0.5)
    assert abs(q[0] - 0.103515625) < 1e-12
    assert abs(v[0] - 0.52734375) < 1e-12
    assert abs(acc[0] - 1.40625) < 1e-12
    rig = {"channels":[{"axisLocal":[0,1,0],"linkM":[0,0,0]},{"axisLocal":[0,0,1],"linkM":[1,0,0]}]}
    point = fk(rig,{"originM":[0,0,0],"yawDegrees":0},[90,90])[-1]
    rotated = fk(rig,{"originM":[0,0,0],"yawDegrees":90},[90,90])[-1]
    assert math.dist(point,[0,1,0]) < 1e-12
    assert math.dist(rotated,[-1,0,0]) < 1e-12


def main(argv):
    if len(argv) != 5:
        raise SystemExit("usage: ensemble_acceptance.py SCORE GROOVE_SCORE NO_REUSE_SCORE REFERENCE_JSON OUTPUT")
    self_test()
    score, groove, no_reuse = [json.loads(Path(path).read_text()) for path in argv[:3]]
    references = json.loads(Path(argv[3]).read_text())  # Validation labels only, after score loading.
    reports = {name:audit_motion(s) for name,s in [("score",score),("groove",groove),("noReuse",no_reuse)]}
    errors = [f"{name}: {error}" for name,report in reports.items() for error in report["errors"]]
    for name,s in [("groove",groove),("noReuse",no_reuse)]:
        if s["duration"] != score["duration"] or s["rig"] != score["rig"] or s["placements"] != score["placements"] or len(s["tracks"]) != len(score["tracks"]):
            errors.append(f"{name}: score geometry/duration differs")
    sampler = Sampler(score)
    seek = [score["duration"]*0.7, score["duration"]*0.2, score["duration"]*0.7]
    deterministic = all(sampler.sample(agent, seek[0]) == sampler.sample(agent, seek[2]) for agent in range(len(score["tracks"])))
    if not deterministic:
        errors.append("absolute-time seek not deterministic")
    windows=[]
    for region in references["regions"]:
        start,end=region["start"],region["end"]
        if start < 0 or end > score["duration"] or end <= start:
            errors.append(f"reference window invalid: {region['label']}")
            continue
        metrics=region_metrics(score,sampler,start,end)
        metrics["referenceLabel"]=region["label"]
        metrics["specialsDifference"]=difference(score,groove,start,end)
        metrics["reuseDifference"]=difference(score,no_reuse,start,end)
        windows.append(metrics)
    report={"version":1,"status":"blocked" if errors else "numeric_checks_passed_human_review_pending","sampleHz":SAMPLE_HZ,"scores":reports,"seekDeterministic":deterministic,"referenceSource":references.get("source"),"windows":windows,"errors":errors,"limits":"Numeric sampling is not physical safety proof or human dance acceptance; rig axes and geometry provisional."}
    Path(argv[4]).write_text(json.dumps(report,indent=2)+"\n")
    print(f"{report['status']}: {len(windows)} windows; {len(errors)} blockers → {argv[4]}")
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
