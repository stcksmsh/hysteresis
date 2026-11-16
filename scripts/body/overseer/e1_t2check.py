import json, numpy as np
B='/secondary/hyst-data/body/t1b/e1/'
for seed in (41101,41102,41103):
    d=json.load(open(f'{B}seed{seed}/t2/swap.json')); S=d['songs']; S=S.values() if isinstance(S,dict) else S
    g=np.array([np.mean(x['swapped'])-x['true'] for x in S if x['swapped']])
    rng=np.random.default_rng(0); bs=[rng.choice(g,len(g)).mean() for _ in range(10000)]
    m=json.load(open(f'{B}seed{seed}/t2/measures.json'))
    keys=[k for k in next(iter(m.values())) if not k.startswith('human')]
    mk=keys[0]
    fr=sum(1 for v in m.values() if v[mk]['frozen_longest_s']>3)
    hs=np.mean([v[mk]['hand_speed_mean'] for v in m.values()])
    hh=np.mean([np.mean([v[h]['hand_speed_mean'] for h in v if h.startswith('human')]) for v in m.values()])
    print(seed,'n',len(g),'gap %.3f ci [%.3f, %.3f]'%(g.mean(),*np.percentile(bs,[2.5,97.5])),'| frozen>3s songs',fr,'of',len(m),'| hand speed model %.2f human %.2f'%(hs,hh),'| model key',mk, 'keys',keys)
print('--- controls (seed 41101 file; controls do not depend on seed)')
m=json.load(open(f'{B}seed41101/t2/measures.json'))
for k in ('model','retrieval','random'):
    fr=sum(1 for v in m.values() if v[k]['frozen_longest_s']>3)
    hs=np.mean([v[k]['hand_speed_mean'] for v in m.values()])
    sv=np.mean([v[k].get('selfsim_16tok',np.nan) for v in m.values()])
    p3=np.mean([np.mean([v[k]['jitter'][j]['p_gt3'] for j in v[k]['jitter']]) for v in m.values()])
    print(k,'frozen songs',fr,'hand speed %.2f'%hs,'selfsim16 %.3f'%sv,'mean p_gt3 %.2e'%p3)
hh=np.mean([np.mean([np.mean([v[h]['jitter'][j]['p_gt3'] for j in v[h]['jitter']]) for h in v if h.startswith('human')]) for v in m.values()])
print('human mean p_gt3 %.2e'%hh)
