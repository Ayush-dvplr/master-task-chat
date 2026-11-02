import sys, os, tempfile
sys.path.insert(0, sys.argv[1])
import gen, ref
bad = 0
for k in ['shipped'] + gen.KINDS:
    for s in (101, 102, 103):
        d = tempfile.mkdtemp()
        b = gen.write(k, s, d)
        try:
            p = ref.read_params(d)
        except Exception as e:
            print('ERR', k, s, repr(e)); bad += 1; continue
        t = b['truth']
        for f in ('tariff_reference','levy_reference','levy_pct','free_days','call_adjustment'):
            if p[f] != t[f]:
                print('DIFF', k, s, f, p[f], t[f]); bad += 1
        tc = sorted(t['classes'], key=lambda c: c['code'])
        if [(c['code'],c['name'],c['rate'],c['minimum']) for c in p['classes']] != [(c['code'],c['name'],c['rate'],c['minimum']) for c in tc]:
            print('DIFFC', k, s, p['classes'], tc); bad += 1
print('bad', bad)
