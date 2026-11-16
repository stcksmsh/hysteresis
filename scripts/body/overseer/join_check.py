import json, numpy as np
m=json.load(open('/secondary/hyst-data/body/join/measures.json'))
def val(c,k,key):
    if key in ('H','HJ|blocks','HJ|overlap'):
        return np.mean([c[f'{key}|{v}'][k] for v in ('V1','V2','V1m','V2m')])
    return c[key][k] if key in c else np.nan
songs=sorted(m)
H=np.array([val(m[s]['cond'],'lamp_p_gt3','H') for s in songs])
print('H P10/P90/mean %.4f %.4f %.4f'%(*np.percentile(H,[10,90]),H.mean()))
keys=['HJ|blocks','HJ|overlap','RT|raw','RT|ramp','RT|blocks','RT|overlap','RN|raw','RN|ramp','RN|blocks','RN|overlap']
mk=sorted({k for s in songs for k in m[s]['cond'] if k.startswith('M')})
for k in keys+mk:
    x=np.array([val(m[s]['cond'],'lamp_p_gt3',k) for s in songs]); ok=~np.isnan(x)
    print(k, 'n',ok.sum(),'mean ratio %.2f'%np.mean(x[ok]/H[ok]),'ratio of means %.2f'%(x[ok].mean()/H[ok].mean()))
