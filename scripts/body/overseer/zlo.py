import sys, numpy as np, itertools
sys.path.insert(0,'scripts/body'); import make_arm_v2p as P, m3f_report as R
g=np.arange(-110,111,5.0); best=(9,-9)
for y in (0.0,45.0,90.0):
    Q=np.array([(y,s,e,w,0.0) for s,e,w in itertools.product(g,g,g)])
    ok=P.margins(Q)>=0; z=R.fk_points(Q)[:,5,2][ok]
    best=(min(best[0],z.min()),max(best[1],z.max()))
print('z_lo %.3f z_hi %.3f'%best)
T=np.load('/secondary/hyst-data/body/controls/tables/finedance.npz')
h=np.clip((T['z_mean']+0.569)/(0.770+0.569),0,1); print('height max abs diff %.2e'%np.abs(h-T['height']).max(), 'share at 0: %.4f'%(T['height']==0).mean(), 'p1/p99 z %.3f %.3f'%tuple(np.percentile(T['z_mean'],[1,99])))
