import ast
import configparser
import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

bundle = Path('/Users/mac/Desktop/Terminal Bench/QC/copies/688700c/flood-repair-portfolio')
source = bundle / 'tests/test_output.py'
tree = ast.parse(source.read_text())
tree.body = [node for node in tree.body if not (
    isinstance(node, ast.ImportFrom) and node.module == 'rewardkit'
) and not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
           and isinstance(node.value.func, ast.Attribute) and isinstance(node.value.func.value, ast.Name)
           and node.value.func.value.id == 'criteria')]
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        node.decorator_list = []
namespace = {'__name__': 'fixture_audit'}
exec(compile(tree, str(source), 'exec'), namespace)

total = Counter()
for name in ('SHIPPED', 'H1', 'H2', 'H3', 'M', 'MS', 'MR'):
    files = namespace['book_files'](name)
    def records(filename, delimiter=','):
        return list(csv.DictReader(io.StringIO(files[filename]), delimiter=delimiter))
    props = records('proposals.csv')
    segments = records('segment_codes.tsv', '\t')
    permits = records('permits.csv')
    exclusions = json.loads(files['exclusions.json'])
    sites = {r['site']: r for r in map(json.loads, files['sites.jsonl'].splitlines()) if r}
    crews = {r['crew']: r['mode'] for r in records('crews.tsv', '\t')}
    cfg = configparser.ConfigParser()
    cfg.read_string(files['benefits.ini'])
    groups = defaultdict(list)
    for row in props:
        groups[row['round']].append(row)
    counts = Counter()
    examples = {}
    for rid, rows in groups.items():
        ids = {r['proposal'] for r in rows}
        names = ids | {r['site'] for r in rows}
        seen = set()
        for row in rows:
            invalid = not (row['households'].isascii() and row['households'].isdigit()
                           and 1 <= int(row['households']) <= 60 and row['site'] in sites
                           and row['crew'] in crews and row['risk_override'] in ('', 'A', 'B', 'C', 'D'))
            if row['proposal'] in seen and invalid:
                counts['proposal_duplicate_and_invalid'] += 1
                examples.setdefault('proposal_duplicate_and_invalid', (rid, row))
            seen.add(row['proposal'])
        for row in segments:
            if row['round'] == rid and row['proposal'] not in ids and row['segment'] not in cfg['segment_rate']:
                counts['segment_unknown_and_invalid'] += 1
        for row in permits:
            if row['round'] == rid and row['proposal'] not in ids and row['status'] not in ('held', 'applied', 'withdrawn'):
                counts['permit_unknown_and_invalid'] += 1
        for row in exclusions:
            if row['round'] == rid and row['first'] == row['second'] and row['first'] not in names:
                counts['exclusion_unknown_and_same'] += 1
        if any(r['risk_override'] and r['site'] in sites and r['risk_override'] != sites[r['site']]['risk_class'] for r in rows):
            counts['override_differs_site_rounds'] += 1
    total.update(counts)
    print('FIXTURE', name, 'files', sorted(files), 'rounds', len(groups), 'max_n', max(map(len, groups.values())), 'counts', dict(counts))
    print('MANIFEST_ORDER', name, json.loads(files['manifest.json'])['files'])
print('ALL_FIXTURE_COUNTS', dict(total))

out = Path('/Users/mac/Desktop/Terminal Bench/_runs/20261102/flood-repair-portfolio/scratch-20261102T225248-e100/negative-probe-output')
def leaves(value):
    if isinstance(value, dict):
        return sum(leaves(v) for v in value.values())
    if isinstance(value, list):
        return sum(leaves(v) for v in value)
    return 1
counts = {p.name: leaves(json.loads(p.read_text())) for p in sorted(out.glob('*.json'))}
print('SHIPPED_SCALAR_LEAVES', counts, 'total', sum(counts.values()))
print('ONE_SHIPPED_QUALITY_FACT_WRONG', 'test', 105 / 108, 'full_if_judge_max', .5 * 105 / 108 + .5)
