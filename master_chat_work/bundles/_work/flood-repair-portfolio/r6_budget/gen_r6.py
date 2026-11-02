# How to run (inside the capped container only):
#   python3 -B /w/r6_budget/gen_r6.py books K        -> writes /w/r6_budget/books/H1-H3 (+ meta)
#   python3 -B /w/r6_budget/gen_r6.py shape300 K     -> 300 seeds of a reduced spec, all assertions
"""r6 generator: the hidden H1-H3 specs, with K lattice rounds per book carrying one shared crew
of CROWD members (no conflicts among them or with the lattice).  Copies r0_lever/measure.py's
header (verifier generator loaded from BUNDLE/tests/test_output.py:1-1277); r0_lever is untouched."""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys

BUNDLE = Path('/b')
OUT = Path('/w/r6_budget')
CROWD = 10           # C(10, 6) = 210 drop combinations: P runs capped_dp (cap 256, P:303, P:376)
LATTICE_N = 150      # 150 lattice proposals + 10 crowd members = 160 (contract limit)


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
ns = namespace


def add_crowd(book, rnd, k):
    """Append k proposals of one shared crew that is new to the round; no conflict records."""
    rng = book.rng
    before = book.derive(rnd)
    used = {row[2] for row in rnd['prop_rows']}
    crew = rng.choice([c for c in book.shared if c not in used])
    t = rng.randint(1000, 1300)
    lo, hi = t * 92 // 100, t * 108 // 100
    members = []
    while len(members) < k:
        sid = ns['_codes'](rng, 1, 'S', 5, book.taken)[0]
        site = {'site': sid, 'risk_class': rng.choice(ns['CLASSES']),
                'premium': rng.randint(0, 800), 'region': rng.choice(ns['REGIONS'])}
        try:
            seg, override, h = book.value_large(site, lo, hi)
        except ValueError:
            continue
        pid = book.new_pids(1)[0]
        book.sites.append(site)
        book.site_by_id[sid] = site
        v = rnd['n']
        rnd['pids'].append(pid)
        rnd['site_of'][v] = site
        rnd['val'][v] = (seg, override, h)
        rnd['crew_of'][v] = crew
        rnd['prop_rows'].append([pid, sid, crew, str(h), override])
        rnd['seg_rows'].append([pid, seg])
        rnd['n'] += 1
        members.append(pid)
    rng.shuffle(rnd['prop_rows'])
    rng.shuffle(rnd['seg_rows'])
    assert book.derive(rnd) == before, 'crowd added a conflict'
    assert sum(row[2] == crew for row in rnd['prop_rows']) == k
    assert dict(book.crews)[crew] == 'shared'
    rnd['crowd'] = {'crew': crew, 'k': k, 'members': members}


def make_book_r6(seed, spec):
    """make_book (test_output.py:762-795) with add_crowd on the large entries in spec['crowd']."""
    book = ns['_Book'](seed, spec)
    rng = book.rng
    rounds = []
    for idx, (n, rows) in enumerate(spec['large']):
        while True:
            edges = ns['_lattice'](rng, n, rows, 0.7)
            try:
                rnd = book.build_round(n, edges, True)
                break
            except ValueError:
                continue
        if idx in spec['crowd']:
            add_crowd(book, rnd, spec['crowd_k'])
        rounds.append(rnd)
    kinds = list(ns['FAULT_KINDS'])
    rng.shuffle(kinds)
    faults = [kinds[i % len(kinds)] for i in range(spec['faults'])]
    for i in range(spec['small']):
        tie = 'twin' if i < spec['ties'] // 2 else ''
        n, edges, gadgets = ns['_small_graph'](book, tie)
        rnd = book.build_round(n, edges, False, gadgets)
        if gadgets:
            rnd['tie'] = ('twin',)
        if spec['ties'] // 2 <= i < spec['ties']:
            assert ns['_path_tie'](book, rnd), 'path tie not placed'
        rounds.append(rnd)
    small = [r for r in rounds if not r['large'] and 'tie' not in r]
    for kind, rnd in zip(faults, rng.sample(small, len(faults))):
        book.plant(rnd, kind)
    for rnd in rounds:
        rnd['audit'] = ns['_audit'](book, rnd, spec['audit_large'] if rnd['large'] else spec['audit_small'])
    crng = ns['_Rng'](seed * 31 + 7177)
    capped = [ns['_capped_round'](book, crng) for _ in range(spec.get('capped', 0))]
    files, meta = ns['_assemble'](book, rounds + capped)
    meta['capped'] = {r['round']: r['capped'] for r in capped}
    meta['crowd'] = {r['round']: r['crowd'] for r in rounds if 'crowd' in r}
    return files, meta


def hidden_spec(name, k_rounds):
    spec = json.loads(json.dumps(ns['_BOOKS'][name]['spec']))
    step = len(spec['large']) // k_rounds
    crowd = [i * step for i in range(k_rounds)]
    for i in crowd:
        spec['large'][i] = [LATTICE_N, spec['large'][i][1]]
    spec['crowd'] = crowd
    spec['crowd_k'] = CROWD
    return spec


def shape(files):
    counts, records = {}, {}
    for row in files['proposals.csv'].splitlines()[1:]:
        if row:
            rid = row.split(',')[0]
            counts[rid] = counts.get(rid, 0) + 1
    for row in files['permits.csv'].splitlines()[1:]:
        if row:
            rid = row.split(',')[0]
            records[rid] = records.get(rid, 0) + 1
    for row in json.loads(files['exclusions.json']):
        records[row['round']] = records.get(row['round'], 0) + 1
    assert len(counts) <= 200 and max(counts.values()) <= 160 and max(records.values()) <= 900
    return len(counts), max(counts.values()), max(records.values())


def write_books(k_rounds):
    for name in ('H1', 'H2', 'H3'):
        seed = ns['_BOOKS'][name]['seed']
        files, meta = make_book_r6(seed, hidden_spec(name, k_rounds))
        bookdir = OUT / 'books' / name
        bookdir.mkdir(parents=True, exist_ok=True)
        for filename, text in files.items():
            (bookdir / filename).write_text(text)
        (OUT / 'books' / f'{name}.meta.json').write_text(json.dumps(meta, indent=2))
        rounds, props, recs = shape(files)
        print('SHAPE', name, 'seed', seed, 'rounds', rounds, 'max_proposals', props, 'max_records', recs,
              'crowd_rounds', len(meta['crowd']), 'crowd_k', sorted({c['k'] for c in meta['crowd'].values()}),
              'capped_k', [c['k'] for c in meta['capped'].values()], flush=True)


def one_seed(seed):
    large = ([[156, 13], [160, 14]], [[148, 12], [160, 13]], [[152, 14], [144, 12]])[seed % 3]
    spec = {'small': 40, 'sites': 900, 'crews': 1500, 'permits': 1200, 'faults': 12, 'ties': 8,
            'audit_small': 12, 'audit_large': 60, 'order': 'shuffle', 'blank_row': 50, 'capped': 3,
            'large': [list(large[i % 2]) for i in range(4)], 'crowd': [0, 2], 'crowd_k': CROWD}
    for i in spec['crowd']:
        spec['large'][i][0] = LATTICE_N
    try:
        files, meta = make_book_r6(9000 + seed, spec)
        shape(files)
        assert len(meta['crowd']) == 2
        return seed, None
    except Exception as exc:  # recorded and reported, never swallowed
        return seed, repr(exc)


if __name__ == '__main__':
    mode, k_rounds = sys.argv[1], int(sys.argv[2])
    if mode == 'books':
        write_books(k_rounds)
    else:
        from multiprocessing import Pool
        with Pool(2) as pool:
            res = pool.map(one_seed, range(1, 301))
        errs = [r for r in res if r[1]]
        print('SEEDS 300 errors', len(errs), errs[:3], flush=True)
    print('ALL_DONE', flush=True)
