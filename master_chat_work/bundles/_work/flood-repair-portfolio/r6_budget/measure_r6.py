# How to run (inside the capped container only, one book per call):
#   python3 -B /w/r6_budget/measure_r6.py H1        (H2, H3, or SHIPPED)
"""r6 measurement on one book: reference + verifier ledger (oracle), then P, P_x4, P_inf and the
kill rows graded with r0_lever/measure.py's checks (copied, not imported), then the reference with
a CPU burner beside it.  Writes /w/r6_budget/results_<book>.json."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

sys.path.insert(0, '/w/r6_budget')
import gen_r6  # noqa: E402  (loads the verifier namespace from /b/tests/test_output.py)

namespace = gen_r6.namespace
BUNDLE = Path('/b')
RUN = Path('/run/measure')
NAME = sys.argv[1]
BOOKDIR = BUNDLE / 'environment/data' if NAME == 'SHIPPED' else Path('/w/r6_budget/books') / NAME


def module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = loaded
    spec.loader.exec_module(loaded)
    return loaded


ref = module(BUNDLE / 'solution/solve.py')
programs = [
    ('paid_a4', '/paid/derive_report.py', 20),
    ('p_x4', '/w/r6_budget/programs/p_x4.py', 120),
    ('p_inf', '/w/r6_budget/programs/p_inf.py', 1500),
    ('blind4_b1', '/w/h4_rule/programs/blind4_b1.py', 20),
    ('blind4_b2', '/w/h4_rule/programs/blind4_b2.py', 20),
    ('first_write', '/w/h2_a1/firstwrite_program.py', 20),
    ('all_but_one', '/w/h2_a1/allbutone_program.py', 20),
    ('lever_aware', '/b/solution/solve.py', 20),
]
if NAME == 'SHIPPED':
    programs = programs[:1]
weights = {'feasible': 3, 'optimal': 5, 'summary': 5, 'policy_audit': 3,
           'data_quality': 3, 'regions': 3, 'segments': 3}
groups = {'summary': ['summary.json'], 'policy_audit': ['policy_audit.json'],
          'data_quality': ['data_quality.json'],
          'regions': [f'region_{r}.json' for r in ('North', 'South', 'West', 'East')],
          'segments': ['segment_commercial.json', 'segment_public.json']}


def run(label, program, bookdir, cap=20):
    out = RUN / 'outputs' / label / NAME
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    for old in out.glob('*.json'):
        old.unlink()
    start = time.monotonic()
    with (out / 'stdout.log').open('w') as stdout, (out / 'stderr.log').open('w') as stderr:
        proc = subprocess.Popen([sys.executable, '-I', '-S', '-B', program, str(bookdir), str(out)],
                                stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            code = proc.wait(timeout=cap)
            verdict = 'EXACT' if code == 0 else 'CRASH'
        except subprocess.TimeoutExpired:
            verdict = 'TIMEOUT'
            code = -9
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
    return out, verdict, round(time.monotonic() - start, 4), code


files = {p.name: p.read_text() for p in sorted(BOOKDIR.iterdir()) if p.is_file()}
results = []
expected_dir, verdict, seconds, code = run('reference', '/b/solution/solve.py', BOOKDIR)
assert verdict == 'EXACT', (NAME, verdict)
expected = {p.name: json.loads(p.read_text()) for p in expected_dir.glob('*.json')}
t0 = time.monotonic()
independent = namespace['_Ledger'](files).documents()
assert independent == expected, NAME
print('ORACLE', NAME, 'reference_seconds', seconds, 'verifier_seconds', round(time.monotonic() - t0, 4),
      'EXACT', flush=True)
results.append({'program': 'reference', 'book': NAME, 'seconds': seconds, 'verdict': 'EXACT', 'points': 25})
bk = ref.load(str(BOOKDIR))
ref_rounds = ref.build(bk)
for label, program, cap in programs:
    out, verdict, seconds, code = run(label, program, BOOKDIR, cap)
    checks = {key: False for key in weights}
    difference = None
    if verdict == 'EXACT':
        got = {p.name: json.loads(p.read_text()) for p in out.glob('*.json')}
        for key, names in groups.items():
            checks[key] = all(got.get(n) == expected[n] for n in names)
        summary = got.get('summary.json', {})
        selected = {r['round']: r['selected'] for r in summary.get('rounds', [])}
        checks['optimal'] = all(selected.get(r['round']) == r['selected']
                                for r in expected['summary.json']['rounds'] if r['status'] == 'planned')
        feasible = len(selected) == len(ref_rounds)
        for r in ref_rounds:
            if r.fault is not None:
                continue
            chosen = selected.get(r.rid, [])
            taken = set(chosen)
            count = {}
            for p in taken:
                c = r.detail[p]['crew']
                if bk['crews'][c] == 'shared':
                    count[c] = count.get(c, 0) + 1
            adj = {p: set() for p in r.ids}
            for a, b in r.pairs:
                adj[a].add(b)
                adj[b].add(a)
            full = {c for c, n in count.items() if n >= 4}
            feasible &= (chosen == sorted(taken) and taken <= set(r.ids)
                         and not any(a in taken and b in taken for a, b in r.pairs)
                         and all(n <= 4 for n in count.values())
                         and not any(p not in taken and not adj[p] & taken and r.detail[p]['crew'] not in full
                                     for p in r.ids))
        checks['feasible'] = feasible
        if got != expected:
            verdict = 'WRONG'
            wrong_rounds = []
            for want, actual in zip(expected['summary.json']['rounds'], summary.get('rounds', [])):
                if want['selected'] != actual['selected'] or want['total_benefit'] != actual['total_benefit']:
                    wrong_rounds.append(want['round'])
                    if difference is None:
                        difference = {'expected': want, 'actual': actual}
            if difference is not None:
                difference['wrong_rounds'] = wrong_rounds
    row = {'program': label, 'book': NAME, 'verdict': verdict, 'seconds': seconds,
           'points': sum(weights[k] for k, ok in checks.items() if ok), 'checks': checks,
           'difference': difference, 'returncode': code}
    results.append(row)
    print('ROW', json.dumps(row), flush=True)
    Path(f'/w/r6_budget/results_{NAME}.json').write_text(json.dumps(results, indent=2))

busy = subprocess.Popen([sys.executable, '-c', 'while True: pass'], start_new_session=True)
try:
    _, verdict, seconds, _ = run('reference_busy', '/b/solution/solve.py', BOOKDIR)
    print('BUSY', NAME, verdict, seconds, flush=True)
    results.append({'program': 'reference_busy', 'book': NAME, 'verdict': verdict, 'seconds': seconds,
                    'points': 25})
finally:
    os.killpg(busy.pid, signal.SIGKILL)
    busy.wait()
Path(f'/w/r6_budget/results_{NAME}.json').write_text(json.dumps(results, indent=2))
print('ALL_DONE', flush=True)
