"""Inside the task image: time the statements CLI of the oracle repo and of solver variants on every corpus.

usage: python3 -B dock_time.py DUMP_DIR [variant ...]   (variants: ref greedy setdp naive)
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import measure_variants as mv  # noqa: E402

dump = Path(sys.argv[1])
names = sys.argv[2:] or ["ref", "greedy", "setdp", "naive"]
LIMIT = 30
corpora = ["shipped", "fresh", "rescaled", "relocated", "rotated", "api", "recoded", "renamed"]
for name in names:
    repo = Path(f"/tmp/variant-{name}")
    shutil.rmtree(repo, ignore_errors=True)
    shutil.copytree(dump / "oracle_repo", repo)
    report = repo / "src" / "tariff" / "report.py"
    text = report.read_text()
    for old, new in ([] if name == "ref" else mv.VARIANTS["S_" + name]):
        assert text.count(old) == 1, (name, old)
        text = text.replace(old, new)
    report.write_text(text)
    env = dict(os.environ, PYTHONPATH=str(repo / "src"), PYTHONDONTWRITEBYTECODE="1")
    for corpus in corpora:
        want = json.loads((dump / "corpora" / f"{corpus}.want.json").read_text())
        started = time.time()
        try:
            proc = subprocess.run([sys.executable, "-B", "-m", "tariff", "--statements",
                                   str(dump / "corpora" / corpus)], env=env, capture_output=True,
                                  text=True, timeout=LIMIT)
            seconds = round(time.time() - started, 2)
            got = json.loads(proc.stdout)
            same = sum(a == b for a, b in zip(got["statements"], want["statements"]))
            verdict = f"exact={got == want} rows_same={same}/{len(want['statements'])}"
        except subprocess.TimeoutExpired:
            seconds, verdict = f">{LIMIT}", "TIMEOUT"
        print(name, corpus, seconds, verdict, flush=True)
print("ALL_DONE")
