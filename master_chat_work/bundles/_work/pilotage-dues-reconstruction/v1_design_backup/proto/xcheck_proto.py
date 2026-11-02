"""Cross-check: every recomputed due in solve_proto output equals the generator's due (meta expect_due)."""
import json
import sys
R = sys.argv[1]
for c in ['shipped'] + ['h%d' % s for s in range(1101, 1107)]:
    exp = json.load(open(f'{R}/{c}_meta.json'))['expect_due']
    rows = json.load(open(f'{R}/out/{c}/policy_audit.json'))['rows']
    n = bad = 0
    for r in rows:
        if r['recomputed'] is None or r['invoice_id'] not in exp:
            continue
        n += 1
        s = r['recomputed']
        got = int(s.replace('-', '').replace('.', '')) * (-1 if s.startswith('-') else 1)
        bad += got != exp[r['invoice_id']]
    print(c, 'checked', n, 'mismatch', bad)
