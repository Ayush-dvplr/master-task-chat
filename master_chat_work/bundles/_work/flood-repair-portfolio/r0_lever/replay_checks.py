from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import time

root = Path('/w/r0_lever')
run = Path('/run')
source = Path('/b/tests/test_output.py')
tree = ast.parse(source.read_text())
tree.body = [node for node in tree.body if node.end_lineno <= 1590
             and not (isinstance(node, ast.ImportFrom) and node.module == 'rewardkit')]
ns = {'__name__': 'replay_verifier'}
exec(compile(tree, str(source), 'exec'), ns)
spec = importlib.util.spec_from_file_location('paid_replay', '/paid/derive_report.py')
assert spec is not None and spec.loader is not None
paid = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paid)
rows = json.loads((root / 'results.json').read_text())
groups = {'summary': ('summary.json',), 'policy_audit': ('policy_audit.json',),
          'data_quality': ('data_quality.json',), 'regions': ns['REGION_DOCS'],
          'segments': ns['SEGMENT_DOCS']}
weights = {'feasible': 3, 'optimal': 5, 'summary': 5, 'policy_audit': 3,
           'data_quality': 3, 'regions': 3, 'segments': 3}
replayed = []
for name in ('H1', 'H2', 'H3'):
    bookdir = root / 'books' / name
    files = {p.name: p.read_text() for p in sorted(bookdir.iterdir())}
    started = time.monotonic()
    ledger = ns['_Ledger'](files)
    expected = ledger.documents()
    elapsed = round(time.monotonic() - started, 4)
    ns['_EXPECTED'][name] = (ledger, expected)
    print('INDEPENDENT', name, elapsed, flush=True)
    meta = json.loads((root / f'{name}.meta.json').read_text())
    bk = paid.Book(str(bookdir))
    for rid, detail in meta['capped'].items():
        rnd = ledger.rounds[rid]
        assert rnd['fault'] is None
        members = detail['members']
        assert len(members) == 11
        assert all(frozenset((a, b)) not in rnd['joined'] for a in members for b in members if a != b)
        valued = paid.value_round(bk, rid)
        pairs, bycrew = paid.conflict_sources(bk, rid, valued)
        ids = sorted(x['proposal'] for x in valued)
        shared = [mem for crew, mem in bycrew.items() if bk.crews[crew] == 'shared' and len(mem) > 4]
        planner = paid.Planner(ids, {x['proposal']: x['benefit'] for x in valued}, pairs.keys(), shared)
        assert planner.capped_dp((1 << planner.count) - 1) is None
        print('CUTOFF', name, rid, 'shared=11 independent_members=11 capped_dp=None', flush=True)
    for row in (r for r in rows if r['book'] == name):
        label = row['program']
        checks = {k: False for k in weights}
        if row['verdict'] not in ('TIMEOUT', 'CRASH'):
            out = run / 'outputs' / label / name
            ns['_RUNS'][name] = {p.name: p.read_text() for p in sorted(out.glob('*.json'))}
            for key in weights:
                try:
                    match key:
                        case 'feasible':
                            ns['_feasible'](name)
                        case 'optimal':
                            ns['_optimal'](name)
                        case _:
                            ns['_hidden_documents'](name, groups[key])
                    checks[key] = True
                except AssertionError:
                    checks[key] = False
            assert checks == row.get('checks', {k: True for k in weights}), (name, label, checks, row)
        replayed.append({**row, 'checks': checks,
                         'points': sum(weights[k] for k, ok in checks.items() if ok)})
    paid_docs = {p.name: json.loads(p.read_text()) for p in (run / 'outputs/paid_a4' / name).glob('*.json')}
    assert paid_docs == expected

out = run / 'outputs/reference/data'
shipped = {p.name: json.loads(p.read_text()) for p in out.glob('*.json')}
published = {p.name: json.loads(p.read_text()) for p in Path('/paid').glob('*.json')}
assert len(shipped) == 9 and shipped == published
print('SHIPPED_REFERENCE_EQUALS_PAID_PASSED_ARTIFACTS', len(shipped), flush=True)
(root / 'replay_results.json').write_text(json.dumps(replayed, indent=2))
print('ALL_DONE', flush=True)
