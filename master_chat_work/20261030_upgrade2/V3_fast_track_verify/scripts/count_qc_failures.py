#!/usr/bin/env python3
"""Count distinct task directories where a ❌ line mentions a QC check ID."""
from collections import defaultdict
from pathlib import Path
import re

ROOT = Path('/Users/mac/Desktop/Terminal Bench/QC/reports')
ids = defaultdict(set)
files = sorted(ROOT.glob('*/v*.md'))
fail_lines = 0
for path in files:
    for line in path.read_text(errors='replace').splitlines():
        # Same report-mention measure as v1: any line with the fail glyph
        # and a check ID. De-duplicate by task, not report or line.
        if '❌' not in line:
            continue
        fail_lines += 1
        for check in set(re.findall(r'\b(?:AL|DS|TS|CL|JD|IN)-\d+\b', line)):
            ids[check].add(path.parent.name)

print(f'files={len(files)} task_dirs={len({p.parent.name for p in files})} fail_lines={fail_lines} check_ids={len(ids)}')
for check, tasks in sorted(ids.items(), key=lambda kv: (-len(kv[1]), kv[0])):
    print(f'{check}\t{len(tasks)}')
