#!/usr/bin/env python3
"""Independent score sampling and real-track musical evidence.

Usage: dance_acceptance.py SCORE GROOVE_SCORE MEMORY_SIDECAR BASELINE_SCORE OUTPUT
This reports software evidence; it does not judge whether motion looks like dance.
"""
import bisect
import json
import math
import pathlib
import sys

import numpy as np


def sample(score, time):
    time = min(max(time, 0.0), score['duration'])
    cue = score['cues'][min(bisect.bisect_left([c['end'] for c in score['cues']], time), len(score['cues']) - 1)]
    knots = cue['knots']
    index = min(max(bisect.bisect_left([k['time'] for k in knots], time) - 1, 0), len(knots) - 2)
    a, b = knots[index:index + 2]
    dt = b['time'] - a['time']
    x = min(max((time - a['time']) / dt, 0.0), 1.0)
    p, q = np.array(a['joints']), np.array(b['joints'])
    va, vb = np.array(a.get('velocity', [0]*3)), np.array(b.get('velocity', [0]*3))
    aa, ab = np.array(a.get('acceleration', [0]*3)), np.array(b.get('acceleration', [0]*3))
    control = np.array([p, p + va*dt/5, p + 2*va*dt/5 + aa*dt*dt/20,
                        q - 2*vb*dt/5 + ab*dt*dt/20, q - vb*dt/5, q])
    for width in range(5, 0, -1):
        control[:width] += (control[1:width+1] - control[:width]) * x
    return control[0]


def window(score, start, end):
    times = np.arange(start, min(end, score['duration']), 1/120)
    poses = np.array([sample(score, t) for t in times])
    speed = np.linalg.norm(np.diff(poses, axis=0)*120, axis=1)
    return {'jointRangeDegrees': np.ptp(poses, axis=0).tolist(),
            'pathDegrees': float(np.sum(speed)/120),
            'medianSpeedDegreesPerSecond': float(np.median(speed)),
            'p95SpeedDegreesPerSecond': float(np.percentile(speed, 95)),
            'fractionBelow2DegreesPerSecond': float(np.mean(speed < 2))}


def analyze(score, groove, sidecar, baseline):
    assert score['duration'] == groove['duration']
    memory = sidecar['musicalMemory']
    annotated = {e['time']: e for e in memory['events']}
    arrivals = []
    for cue in score['cues']:
        anchor = cue.get('arrivalAnchor')
        if anchor is None:
            continue
        event = min(annotated.values(), key=lambda e: abs(e['time']-anchor))
        assert abs(anchor-event['time']) < 1e-9, f'unsupported arrival {anchor}'
        assert any(k['time'] == anchor and k['phase'] == 'arrival' for k in cue['knots'])
        before = np.arange(max(cue['start'], anchor-1.4), anchor-.05, 1/120)
        deviations = [(float(t), float(np.linalg.norm(sample(score, t)-sample(groove, t)))) for t in before]
        noticeable = [t for t, d in deviations if d > .5]
        arrivals.append({'time': anchor, 'source': event['source'],
                         'kind': event['kind'],
                         'preparationLeadSeconds': anchor - min(noticeable) if noticeable else 0,
                         'peakPreparationDifferenceDegrees': max((d for _, d in deviations), default=0)})
    windows = []
    for label, start, end in [('opening', 0, 2), ('sustained groove', 60, 68),
                             ('louder passage', 96, 104), ('lower level',128,136),
                             ('dense transients',264,272), ('fade',320,328), ('rest',336,339.8)]:
        if start >= score['duration']:
            continue
        r = sidecar['envelopeRate']
        rms = sidecar.get('rmsEnvelope', [])
        samples = rms[int(start*r):int(min(end,score['duration'])*r)]
        windows.append({'label': label, 'start':start,'end':end,
                        'absoluteRms': sum(samples)/max(1,len(samples)),
                        'onsetCount': sum(start <= o['t'] < end for o in sidecar['onsets']),
                        'new':window(score,start,end),'grooveOnly':window(groove,start,end),
                        'rejected':window(baseline,start,end)})
    recalls = []
    for i,p in enumerate(memory['phrases']):
        source = p.get('repeatOf')
        if source is None:
            continue
        a = memory['phrases'][source]
        u = np.linspace(.2,.8,240)
        earlier = np.array([sample(groove,a['start']+x*(a['end']-a['start'])) for x in u])
        later = np.array([sample(groove,p['start']+x*(p['end']-p['start'])) for x in u])
        earlier -= earlier.mean(axis=0)
        later -= later.mean(axis=0)
        denom = np.linalg.norm(earlier)*np.linalg.norm(later)
        recalls.append({'phrase':i,'sourcePhrase':source,'similarity':p['similarity'],
                        'sourceInterval':[a['start'],a['end']], 'targetInterval':[p['start'],p['end']],
                        'centeredMotionCosine':float(np.sum(earlier*later)/denom) if denom else None})
    active_knots = [k for c in groove['cues'] if c['gesture'] != 'hold' for k in c['knots'][1:-1]]
    through = sum(np.linalg.norm(k.get('velocity',[0]*3)) > 2 for k in active_knots)
    for c in score['cues']:
        if c['gesture'] == 'hold':
            assert all(k['joints']==c['knots'][0]['joints'] and
                       k.get('velocity',[0]*3)==[0]*3 and k.get('acceleration',[0]*3)==[0]*3 for k in c['knots'])
    return {'scope':'independent numeric musical evidence; human dance acceptance remains open',
            'windows':windows,'anticipatedEvents':arrivals,'recurrence':recalls,
            'grooveOnlyAnchors':sum(c.get('arrivalAnchor') is not None for c in groove['cues']),
            'activeInternalKnots':len(active_knots),
            'fractionMovingThroughInternalKnots':through/max(1,len(active_knots)),
            'holdsImmutable':True}


if __name__ == '__main__':
    if len(sys.argv) != 6:
        raise SystemExit(__doc__)
    data = [json.loads(pathlib.Path(p).read_text()) for p in sys.argv[1:5]]
    result = analyze(*data)
    pathlib.Path(sys.argv[5]).write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k != 'windows'},indent=2))
