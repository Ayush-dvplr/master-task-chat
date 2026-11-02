from __future__ import annotations

import ast
import json
from pathlib import Path

root = Path('/w/r0_lever')
timers = ast.parse((root / 'measure.py').read_text())
timers.body = [n for n in timers.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.AnnAssign))
               or (isinstance(n, ast.FunctionDef) and n.name == 'run')]
timer = {'__name__': 'saved_timer'}
exec(compile(timers, str(root / 'measure.py'), 'exec'), timer)
source = Path('/b/tests/test_output.py')
tree = ast.parse(source.read_text())
tree.body = [n for n in tree.body if n.end_lineno <= 1590
             and not (isinstance(n, ast.ImportFrom) and n.module == 'rewardkit')]
ns = {'__name__': 'extra_baseline_verifier'}
exec(compile(tree, str(source), 'exec'), ns)
groups = {'summary': ('summary.json',), 'policy_audit': ('policy_audit.json',),
          'data_quality': ('data_quality.json',), 'regions': ns['REGION_DOCS'],
          'segments': ns['SEGMENT_DOCS']}
weights = {'feasible': 3, 'optimal': 5, 'summary': 5, 'policy_audit': 3,
           'data_quality': 3, 'regions': 3, 'segments': 3}
results = []
for name in ('H1', 'H2', 'H3'):
    bookdir = root / 'books' / name
    files = {p.name: p.read_text() for p in sorted(bookdir.iterdir())}
    led = ns['_Ledger'](files)
    ns['_EXPECTED'][name] = (led, led.documents())
    for label in ('dae9563', 'elim', 'vebest'):
        program = f'/w/h1_a1/{label}_program.py'
        out, verdict, seconds, code = timer['run'](label, program, bookdir)
        checks = {k: False for k in weights}
        if verdict == 'EXACT':
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
            if not all(checks.values()):
                verdict = 'WRONG'
        row = {'program': label, 'book': name, 'verdict': verdict, 'seconds': seconds,
               'checks': checks, 'points': sum(weights[k] for k, ok in checks.items() if ok),
               'returncode': code}
        results.append(row)
        (root / 'extra_results.json').write_text(json.dumps(results, indent=2))
        print('EXTRA', json.dumps(row), flush=True)
print('ALL_DONE', flush=True)
