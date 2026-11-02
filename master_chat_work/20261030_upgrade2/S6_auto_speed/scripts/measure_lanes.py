#!/usr/bin/env python3
"""Read saved Harbor logs only; print reported job runtimes and gate span."""
from pathlib import Path
import re

ROOT = Path('/tmp/opencode-logs')
CASES = {
    'nikhil_parallel': 'b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042-step10-20261030T163722-c7df',
    'warrant_earlier': 'warrant-asof-entitlement-compiler-step10-20261030T140824-f6b3',
    'warrant_parallel': 'warrant-asof-entitlement-compiler-step10-20261030T174955-6298',
    'cold_chain_serial': 'cold-chain-backbone-quote-step10-20261030T152505-b234',
}

def sec(s):
    m = re.fullmatch(r'(?:(\d+)m )?(\d+)s', s)
    return 60 * int(m.group(1) or 0) + int(m.group(2))

for name, rel in CASES.items():
    d = ROOT / rel
    logs = sorted(d.glob('lane*.log')) or [d / 'runs.log']
    print(name, rel)
    for p in logs:
        s = p.read_text(errors='replace')
        vals = [sec(x) for x in re.findall(r'Total runtime: ([0-9]+m [0-9]+s|[0-9]+s)', s)]
        print(' ', p.name, vals, 'sum_s', sum(vals))
    s = (d / 'runs.log').read_text(errors='replace')
    for ln in s.splitlines():
        if ln.startswith('start ') or ln.startswith('=== START oracle-1') or ln.startswith('ALL_DONE'):
            print(' ', ln)
