#!/usr/bin/env python3
"""Read-only audit of L1-L6 summary artifacts for the L7 synthesis."""

import csv
import json
import re
from collections import Counter
from pathlib import Path

base = Path(__file__).resolve().parents[2]
sessions = {p.name.split('_', 1)[0]: p for p in base.glob('L[1-6]_*') if p.is_dir()}
for label in sorted(sessions):
    root = sessions[label]
    result = json.loads((root / 'result.json').read_text())
    print(label, result['status'], 'findings', result['findings'], 'questions', result['questions'])
    checked = 0
    for name in result['files']:
        source = root / name
        if source.suffix == '.json':
            json.loads(source.read_text())
        elif source.suffix == '.csv':
            with source.open(newline='') as file:
                list(csv.DictReader(file))
        else:
            source.read_text()
        checked += 1
    print(label, 'listed files read', checked)

def rows(label, name):
    with (sessions[label] / name).open(newline='') as file:
        return list(csv.DictReader(file))

qc = rows('L1', 'QC_FINDINGS.csv')
print('L1', 'findings', len(qc), 'severity', dict(Counter(x['severity'] for x in qc)))
print('L1', 'statuses', dict(Counter(x['status_next'] for x in qc)))
print('L1', 'fix links', len(rows('L1', 'FIX_EFFECTS.csv')))
print('L2', 'kit rows', len(rows('L2', 'KIT_MAP.csv')))
poll = [x for x in rows('L3', 'POLL_STATS.csv') if x['auto_runs']]
print('L3', 'auto sessions', len(poll), 'sleep calls', sum(int(x['sleep_calls']) for x in poll),
      'sleep minutes', round(sum(float(x['sleep_elapsed_min']) for x in poll), 1),
      'docker sleep', sum(int(x['docker_ps_sleep_calls']) for x in poll))
print('L3', 'episodes', len(rows('L3', 'SLEEP_CASES.csv')))
images = rows('L4', 'IMAGES.csv')
print('L4', 'images', len(images), 'categories', dict(Counter(x['category'] for x in images)))
print('L5', 'top rows', len(rows('L5', 'BEST.csv')))

out = Path(__file__).resolve().parents[1]
missing_links = []
for document in (out / 'LEARNING_REPORT.md', out / 'FINDINGS.md', out / 'QUESTIONS.md'):
    for target in re.findall(r'\]\(([^)]+)\)', document.read_text()):
        if '://' not in target and not (document.parent / target.split('#', 1)[0]).exists():
            missing_links.append(f'{document.name}: {target}')
print('L7', 'missing local links', len(missing_links), missing_links)
