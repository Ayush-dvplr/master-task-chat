#!/bin/bash
set -euo pipefail

mkdir -p /app/out
python3 -B - <<'PY'
from pathlib import Path

data = Path('/app/data')
print((data / 'brassmoor_rules.md').read_text())
print((data / 'errata.md').read_text())
PY
install -m 0644 /solution/solve.py /app/out/optimize.py
python3 -B /app/out/optimize.py /app/data /app/out
python3 -B - <<'PY'
import json
import re
import runpy
from pathlib import Path

data = Path('/app/data')
out = Path('/app/out')
engine_path = out / 'optimize.py'

# Book check: section 14 demo replayed by the installed engine file itself.
engine = runpy.run_path(str(engine_path), run_name='book_check')
book = (data / 'brassmoor_rules.md').read_text()
demo = book.split('## 14. Worked example:', 1)[1].split('## 15.', 1)[0]
blocks = re.findall(r'```\n(.*?)\n```', demo, re.S)
assert len(blocks) == 3, 'section 14 should hold a grid, a log and the expected digests'
grid, log, expected_text = blocks
expected = json.loads(expected_text)['digests']
rules = engine['Rules'](data)
rows = grid.splitlines()
rules.maps['demo-1'] = {'name': 'demo-1', 'w': len(rows[0]), 'h': len(rows), 'rows': rows}
matches, _ = engine['read_log'](log, rules.units)
_, digests, _ = engine['replay_match'](rules, matches[0])
for index, (got, want) in enumerate(zip(digests, expected)):
    print('demo digest', index, 'computed', got, 'expected', want)
assert len(digests) == len(expected) == 4, (digests, expected)
assert digests == expected, (digests, expected)
demo_outcome = 'matched' if digests == expected else 'mismatched'
print('Book section 14 demo digests', demo_outcome + ':', digests)

# Report inspection: every report written by the run above.
reports = {}
for path in sorted(out.glob('*.json')):
    report = json.loads(path.read_text())
    reports[path.name] = report
    if 'matches' in report:
        print(path.name, 'matches:', len(report['matches']), 'first:', report['matches'][0])
    else:
        print(path.name, report)
assert len(reports) == 9, sorted(reports)

quality = reports['data_quality.json']['scenarios']
keyframe_parts = []
for name, row in quality.items():
    hit = sorted({match_id for match_id, _ in row['divergences']})
    keyframe_parts.append('%s %d divergences in %d matches' % (name, len(row['divergences']), len(hit)))
amend = {key: sum(row['amendments'][key] for row in quality.values()) for key in ('applied', 'stale', 'unknown')}

print()
print('Built /app/out/optimize.py, a single standard-library engine run as python3 /app/out/optimize.py '
      '<data_dir> <out_dir>. It implements the section 16 recovery: revision-checked amendments on '
      'immutable order slots with DROP tombstones, a full-match replay after each applied amendment and a '
      'per-revision audit with timeline fingerprints and signed deltas. It also implements section 7 '
      'keyframe compare and adopt, section 6.4 lag resolution and ruleset 2 reseeding.')
print('Keyframes: the final run compared every keyframe and found ' + '; '.join(keyframe_parts) +
      ', as listed in data_quality.json above. Amendments across all exports: %d applied, %d stale, '
      '%d unknown.' % (amend['applied'], amend['stale'], amend['unknown']))
print('Book: running the section 14 demo through /app/out/optimize.py gave the four digests %s, which %s '
      'the book vector %s.' % (', '.join(digests), demo_outcome, ', '.join(expected)))
print('Unclear points: none remain after applying the documented precedence rules.')
PY
