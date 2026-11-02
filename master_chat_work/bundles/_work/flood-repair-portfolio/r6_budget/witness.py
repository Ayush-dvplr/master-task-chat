# How to run (inside the capped container only):
#   python3 -B /w/r6_budget/witness.py
"""Smallest r6 witness: one 150-lattice round + 10-member shared crew, plus 2 small rounds.
Writes /w/r6_budget/witness/book, runs reference, oracle ledger and P (shipped budgets),
and traces which P branch produced the crowd round's portfolio."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, '/w/r6_budget')
import gen_r6  # noqa: E402

ns = gen_r6.ns
WIT = Path('/w/r6_budget/witness')
BOOK = WIT / 'book'
SEED = 815301
spec = {'small': 2, 'sites': 900, 'crews': 1500, 'permits': 1200, 'faults': 0, 'ties': 0,
        'audit_small': 12, 'audit_large': 60, 'order': 'shuffle', 'blank_row': 50, 'capped': 0,
        'large': [[gen_r6.LATTICE_N, 13]], 'crowd': [0], 'crowd_k': gen_r6.CROWD}
files, meta = gen_r6.make_book_r6(SEED, spec)
print('SHAPE', gen_r6.shape(files), 'crowd', meta['crowd'], flush=True)
BOOK.mkdir(parents=True, exist_ok=True)
for name, text in files.items():
    (BOOK / name).write_text(text)
(WIT / 'book.meta.json').write_text(json.dumps(meta, indent=2))


def run(label, program):
    out = WIT / 'outputs' / label
    out.mkdir(parents=True, exist_ok=True)
    t = time.monotonic()
    proc = subprocess.run([sys.executable, '-I', '-S', '-B', program, str(BOOK), str(out)], timeout=600)
    sec = round(time.monotonic() - t, 4)
    return {p.name: json.loads(p.read_text()) for p in out.glob('*.json')}, sec, proc.returncode


ref_docs, ref_sec, code = run('reference', '/b/solution/solve.py')
assert code == 0
t = time.monotonic()
ledger = ns['_Ledger']({k: (BOOK / k).read_text() for k in files}).documents()
print('ORACLE equals reference', ledger == ref_docs, 'verifier_seconds', round(time.monotonic() - t, 3), flush=True)
p_docs, p_sec, p_code = run('paid_a4', '/paid/derive_report.py')
print('REFERENCE seconds', ref_sec, 'P seconds', p_sec, 'P code', p_code, flush=True)
crowd_rid = next(iter(meta['crowd']))
exp = {r['round']: r for r in ref_docs['summary.json']['rounds']}
got = {r['round']: r for r in p_docs['summary.json']['rounds']}
diff = [rid for rid in exp if (exp[rid].get('selected'), exp[rid].get('total_benefit'))
        != (got[rid].get('selected'), got[rid].get('total_benefit'))]
print('DIFF rounds', diff, 'crowd round', crowd_rid, flush=True)
for rid in diff:
    print('ROUND', rid, 'oracle total', exp[rid]['total_benefit'], 'P total', got[rid]['total_benefit'],
          'oracle-only', sorted(set(exp[rid]['selected']) - set(got[rid]['selected']))[:6],
          'P-only', sorted(set(got[rid]['selected']) - set(exp[rid]['selected']))[:6], flush=True)
bad = sorted(name for name in ref_docs if ref_docs[name] != p_docs.get(name))
print('DOCS differing', bad, flush=True)

# Branch trace on an imported copy of P (shipped budgets, unchanged source).
spec_p = importlib.util.spec_from_file_location('pcopy', '/paid/derive_report.py')
P = importlib.util.module_from_spec(spec_p)
spec_p.loader.exec_module(P)
sys.setrecursionlimit(10000)
trace = []
orig_capped, orig_greedy = P.Planner.capped_dp, P.Planner.greedy


def capped_dp(self, *a, **k):
    start = time.monotonic()
    try:
        return orig_capped(self, *a, **k)
    except P.Timeout:
        trace.append(('capped_dp Timeout after', round(time.monotonic() - start, 3), 'groups',
                      [bin(m).count('1') for m in self.group_masks]))
        raise


def greedy(self, *a, **k):
    trace.append(('greedy called', len(self.ids)))
    return orig_greedy(self, *a, **k)


P.Planner.capped_dp, P.Planner.greedy = capped_dp, greedy
P.set_book_budget(P.BOOK_BUDGET)
book = P.Book(str(BOOK))
rounds = P.derive(book)
print('TRACE', trace, flush=True)
print('TRACE crowd selected equals subprocess P', rounds[crowd_rid]['selected'] == got[crowd_rid]['selected'], flush=True)
(WIT / 'witness.json').write_text(json.dumps({'crowd_round': crowd_rid, 'diff_rounds': diff, 'docs_differing': bad,
                                              'reference_seconds': ref_sec, 'p_seconds': p_sec, 'trace': trace,
                                              'oracle_total': exp[crowd_rid]['total_benefit'],
                                              'p_total': got[crowd_rid]['total_benefit']}, indent=2))
print('ALL_DONE', flush=True)
