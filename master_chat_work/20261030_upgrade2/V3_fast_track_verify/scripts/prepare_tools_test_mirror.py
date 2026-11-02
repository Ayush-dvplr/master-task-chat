#!/usr/bin/env python3
"""Constrain hard-coded /tmp writes in a disposable OUT-only test mirror."""
from pathlib import Path

out = Path(__file__).resolve().parents[1]
root = out / 'mirror/master_chat_tasks/tools'
for rel in ('tests/test_upgrade_tools.py', 'tests/test_e3_e6_tools.py', 'repackage_one.py'):
    p = root / rel
    s = p.read_text()
    p.write_text(s.replace('/tmp', str(out / 'tmp')))
