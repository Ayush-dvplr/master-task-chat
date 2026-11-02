"""Scratch: P-4 candidate behaviour checks on one repo's CLI.

    python3 -B p4.py REPO_SRC CORPORA_DIR

a) nested relative --out that does not exist yet (K10: creates the output folder if needed)
b) rerun into an --out folder holding a previous larger run: files equal a fresh run (K10 writes the files)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO, CORPORA = sys.argv[1], Path(sys.argv[2])


def cli(job: dict, out: str, cwd: str) -> int:
    env = dict(os.environ, PYTHONPATH=REPO, PYTHONDONTWRITEBYTECODE="1")
    cmd = [sys.executable, "-B", "-m", "migrakit", "run", "--contracts", job["contracts"], "--feed", job["feed"],
           "--corrections", job["corrections"], "--manifest", job["manifest"], "--out", out]
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=300).returncode


jobs = [json.loads((f / "job.json").read_text()) for f in sorted(CORPORA.iterdir()) if (f / "job.json").exists()]
small, big = jobs[0], jobs[1]
with tempfile.TemporaryDirectory() as tmp:
    rc = cli(small, "n1/n2/n3", tmp)
    nested = rc == 0 and (Path(tmp) / "n1/n2/n3/records.jsonl").exists() and (Path(tmp) / "n1/n2/n3/run_summary.json").exists()
    print("P4a nested_out", "PASS" if nested else f"FAIL rc={rc}")
    fresh = Path(tmp) / "fresh"
    cli(small, str(fresh), tmp)
    reuse = Path(tmp) / "reuse"
    cli(big, str(reuse), tmp)
    (reuse / "records.jsonl").write_text((reuse / "records.jsonl").read_text() + "\n" * 3)
    cli(small, str(reuse), tmp)
    same = all((fresh / n).read_bytes() == (reuse / n).read_bytes() for n in ("records.jsonl", "run_summary.json"))
    print("P4b rerun_over_old_output", "PASS" if same else "FAIL")
