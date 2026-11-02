# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
# How to run: python3 -B /w/r0_lever/measure.py (inside the capped container).
"""Measure the n=11 branch using the existing generator and verifier oracle."""
from __future__ import annotations

import ast
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Final

ROOT: Final = Path('/w/r0_lever')
RUN: Final = Path('/run')
BUNDLE: Final = Path('/b')


def module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = loaded
    spec.loader.exec_module(loaded)
    return loaded


source = BUNDLE / 'tests/test_output.py'
tree = ast.parse(source.read_text())
tree.body = [node for node in tree.body if node.end_lineno <= 1277
             and not (isinstance(node, ast.ImportFrom) and node.module == 'rewardkit')]
namespace = {'__name__': 'measurement_verifier'}
exec(compile(tree, str(source), 'exec'), namespace)
ref = module(BUNDLE / 'solution/solve.py')
original = namespace['_capped_round']


def crowded(book, rng):
    rnd = original(book, rng)
    crew = rnd['capped']['crew']
    members = rnd['capped']['members']
    for i in range(11 - len(members)):
        pid = namespace['_codes'](rng, 1, 'P', 6, book.taken)[0]
        sid = namespace['_codes'](rng, 1, 'S', 5, book.taken)[0]
        risk = book.neg
        premium = i + 1 - book.rates['residential'] - book.uplifts[risk]
        assert 0 <= premium <= 800
        site = {'site': sid, 'risk_class': risk, 'premium': premium,
                'region': rng.choice(namespace['REGIONS'])}
        book.sites.append(site)
        book.site_by_id[sid] = site
        book.all_pids.append(pid)
        rnd['prop_rows'].append([pid, sid, crew, '1', ''])
        rnd['seg_rows'].append([pid, 'residential'])
        rnd['pids'].append(pid)
        rnd['n'] += 1
        members.append(pid)
    rnd['capped']['k'] = 11
    rnd['audit'] = namespace['_audit'](book, rnd, book.spec['audit_small'])
    assert sum(row[2] == crew for row in rnd['prop_rows']) == 11
    return rnd


namespace['_capped_round'] = crowded
books = {}
for name in ('H1', 'H2', 'H3'):
    entry = namespace['_BOOKS'][name]
    files, meta = namespace['make_book'](entry['seed'], entry['spec'])
    bookdir = ROOT / 'books' / name
    bookdir.mkdir(parents=True, exist_ok=True)
    for filename, text in files.items():
        (bookdir / filename).write_text(text)
    (ROOT / f'{name}.meta.json').write_text(json.dumps(meta, indent=2))
    counts = {}
    for row in files['proposals.csv'].splitlines()[1:]:
        if row:
            rid = row.split(',')[0]
            counts[rid] = counts.get(rid, 0) + 1
    record_counts = {}
    for row in files['permits.csv'].splitlines()[1:]:
        if row:
            rid = row.split(',')[0]
            record_counts[rid] = record_counts.get(rid, 0) + 1
    for row in json.loads(files['exclusions.json']):
        rid = row['round']
        record_counts[rid] = record_counts.get(rid, 0) + 1
    print('SHAPE', name, 'rounds', len(counts), 'max_proposals', max(counts.values()),
          'max_records', max(record_counts.values()), 'shared', [x['k'] for x in meta['capped'].values()], flush=True)
    assert len(counts) <= 200 and max(counts.values()) <= 160 and max(record_counts.values()) <= 900
    books[name] = (bookdir, files)

programs = [
    ('paid_a4', '/paid/derive_report.py'),
    ('blind4_b1', '/w/h4_rule/programs/blind4_b1.py'),
    ('blind4_b2', '/w/h4_rule/programs/blind4_b2.py'),
    ('a3_natural', '/w/h4_rule/programs/a3_natural.py'),
    ('a3_correct', '/w/h4_rule/programs/a3_correct.py'),
    ('a3_prefilter', '/w/h4_rule/programs/a3_prefilter.py'),
    ('a3_unchanged', '/w/h4_rule/programs/a3_unchanged.py'),
    ('a1', '/w/h1_a1/a1_program/derive_report.py'),
    ('first_write', '/w/h2_a1/firstwrite_program.py'),
    ('all_but_one', '/w/h2_a1/allbutone_program.py'),
    ('lever_aware', '/b/solution/solve.py'),
]
results = []
weights = {'feasible': 3, 'optimal': 5, 'summary': 5, 'policy_audit': 3,
           'data_quality': 3, 'regions': 3, 'segments': 3}
groups = {'summary': ['summary.json'], 'policy_audit': ['policy_audit.json'],
          'data_quality': ['data_quality.json'],
          'regions': [f'region_{r}.json' for r in ('North', 'South', 'West', 'East')],
          'segments': ['segment_commercial.json', 'segment_public.json']}


def run(label: str, program: str, bookdir: Path):
    out = RUN / 'outputs' / label / bookdir.name
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    start = time.monotonic()
    with (out / 'stdout.log').open('w') as stdout, (out / 'stderr.log').open('w') as stderr:
        proc = subprocess.Popen([sys.executable, '-I', '-S', '-B', program, str(bookdir), str(out)],
                                stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            code = proc.wait(timeout=20)
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


for name, (bookdir, files) in books.items():
    expected_dir, verdict, seconds, code = run('reference', '/b/solution/solve.py', bookdir)
    assert verdict == 'EXACT', (name, verdict)
    expected = {p.name: json.loads(p.read_text()) for p in expected_dir.glob('*.json')}
    t0 = time.monotonic()
    ledger = namespace['_Ledger'](files)
    independent = ledger.documents()
    assert independent == expected, name
    print('ORACLE', name, 'reference_seconds', seconds, 'verifier_seconds', round(time.monotonic()-t0, 4), 'EXACT', flush=True)
    results.append({'program': 'reference', 'book': name, 'seconds': seconds, 'verdict': 'EXACT', 'points': 25})
    for label, program in programs:
        out, verdict, seconds, code = run(label, program, bookdir)
        checks = {key: False for key in weights}
        difference = None
        if verdict == 'EXACT':
            got = {p.name: json.loads(p.read_text()) for p in out.glob('*.json')}
            for key, names in groups.items():
                checks[key] = all(got.get(n) == expected[n] for n in names)
            summary = got.get('summary.json', {})
            selected = {r['round']: r['selected'] for r in summary.get('rounds', [])}
            checks['optimal'] = all(selected.get(r['round']) == r['selected'] for r in expected['summary.json']['rounds'] if r['status'] == 'planned')
            bk = ref.load(str(bookdir))
            rounds = ref.build(bk)
            feasible = len(selected) == len(rounds)
            for r in rounds:
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
                             and not any(p not in taken and not adj[p] & taken and r.detail[p]['crew'] not in full for p in r.ids))
            checks['feasible'] = feasible
            if got != expected:
                verdict = 'WRONG'
                for want, actual in zip(expected['summary.json']['rounds'], summary.get('rounds', [])):
                    if want['selected'] != actual['selected'] or want['total_benefit'] != actual['total_benefit']:
                        difference = {'expected': want, 'actual': actual}
                        break
        row = {'program': label, 'book': name, 'verdict': verdict, 'seconds': seconds,
               'points': sum(weights[k] for k, ok in checks.items() if ok), 'checks': checks, 'difference': difference, 'returncode': code}
        results.append(row)
        print('ROW', json.dumps(row), flush=True)
        (ROOT / 'results.json').write_text(json.dumps(results, indent=2))

for label, bookdir in [('shipped', BUNDLE/'environment/data')]:
    _, verdict, seconds, _ = run('reference', '/b/solution/solve.py', bookdir)
    print('SHIPPED', verdict, seconds, flush=True)

busy = subprocess.Popen([sys.executable, '-c', 'while True: pass'], start_new_session=True)
try:
    for name, (bookdir, _) in books.items():
        _, verdict, seconds, _ = run('reference_busy', '/b/solution/solve.py', bookdir)
        print('BUSY', name, verdict, seconds, flush=True)
        results.append({'program': 'reference_busy', 'book': name, 'verdict': verdict, 'seconds': seconds, 'points': 25})
finally:
    os.killpg(busy.pid, signal.SIGKILL)
    busy.wait()
(ROOT / 'results.json').write_text(json.dumps(results, indent=2))
print('ALL_DONE', flush=True)
