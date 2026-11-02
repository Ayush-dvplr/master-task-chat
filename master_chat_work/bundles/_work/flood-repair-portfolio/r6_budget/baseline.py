# How to run: python3 -B /w/r6_budget/baseline.py (inside the capped container).
"""Baseline timing of P, P_inf and the reference on the r5 books (r0_lever/books H1-H3)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

BOOKS = Path('/w/r0_lever/books')
RUN = Path('/run/baseline')
PROGRAMS = {
    'reference': '/b/solution/solve.py',
    'paid_a4': '/paid/derive_report.py',
    'p_inf': '/w/r6_budget/programs/p_inf.py',
}
CAPS = {'reference': 20, 'paid_a4': 20, 'p_inf': 900}


def run(label, program, book, cap):
    out = RUN / label / book
    out.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    proc = subprocess.Popen([sys.executable, '-I', '-S', '-B', program, str(BOOKS / book), str(out)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
    try:
        _, err = proc.communicate(timeout=cap)
        verdict = 'OK' if proc.returncode == 0 else 'CRASH'
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        verdict = 'TIMEOUT'
    return out, verdict, round(time.monotonic() - start, 4)


def docs(out):
    return {p.name: json.loads(p.read_text()) for p in sorted(out.glob('*.json'))}


rows = []
for book in ('H1', 'H2', 'H3'):
    expected = None
    for label in ('reference', 'paid_a4', 'p_inf'):
        out, verdict, seconds = run(label, PROGRAMS[label], book, CAPS[label])
        got = docs(out)
        if label == 'reference':
            expected = got
        same = verdict == 'OK' and got == expected
        row = {'book': book, 'program': label, 'verdict': verdict, 'seconds': seconds,
               'equals_reference': same}
        rows.append(row)
        print('ROW', json.dumps(row), flush=True)
Path('/w/r6_budget/baseline_results.json').write_text(json.dumps(rows, indent=1))
print('ALL_DONE', flush=True)
