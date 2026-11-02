import sys, time, tempfile
from pathlib import Path
sys.path.insert(0,'.')
import oracle_r2 as R
T=R.T
d=Path(tempfile.mkdtemp(dir='/tmp/snlsq-r2-005932-81af55'))/'ship'
t=time.time(); info=R.emit_r2(d, T.SAMPLE_SEED); print('emit',time.time()-t, info)
C={'A':'correct','B':'correct','C':'correct'}
ref=R.solve_r2(d,C); print('vtpv',float(ref['vtpv']),'blunders',len(ref['removed_ids']))
for L in 'ABC':
    m=dict(C); m[L]='reflex'; r=R.solve_r2(d,m)
    same = r['vtpv']==ref['vtpv'] and r['residuals']==ref['residuals'] and r['weights_final']==ref['weights_final'] and [o.region for o in r['obs']]==[o.region for o in ref['obs']]
    print(L,'same under reflex:',same)
