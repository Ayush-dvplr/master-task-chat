"""Score one program with the REAL bundle tests, locally.

usage: python3 score.py PROGRAM [JSON_OUT]
Runs PROGRAM on the shipped extract (as /app/out stand-in) and on the three
hidden extracts, then calls every weighted test of tests/test_output.py.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BUNDLE = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/"
              "sensor-network-lsq-correlated-adjustment")
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(BUNDLE / "tests"))
import test_output as T  # noqa: E402

prog = Path(sys.argv[1]).resolve()
work = Path(tempfile.mkdtemp(prefix="snlsq-score-"))
out = work / "app_out"
out.mkdir()
shutil.copy(prog, out / "derive_report.py")
T.OUT = out
T.SCRIPT = out / "derive_report.py"


def run_local(data_dir, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        return subprocess.run([sys.executable, str(T.SCRIPT), str(data_dir), str(out_dir)],
                              capture_output=True, timeout=120).returncode
    except subprocess.TimeoutExpired:
        return -9


T._run_agent_program = run_local
shipped = T._build_corpus(T.SAMPLE_SEED)
code = run_local(shipped, out)

src = (BUNDLE / "tests" / "test_output.py").read_text()
weights = [(m.group(1), int(m.group(2)))
           for m in re.finditer(r"^criteria\.(\w+)\(weight=(-?\d+)\)", src, re.M)]
total = sum(w for _, w in weights if w > 0)
earned, rows = 0, []
for name, w in weights:
    fn = getattr(T, "test_" + name, None) or getattr(T, "test_negative_weight_" + name.removeprefix("negative_"))
    ok = T._passes(fn)
    if ok:
        earned += w
    rows.append((name, w, ok))
score = max(0, earned) / total
res = {"program": str(prog), "shipped_code": code, "earned": earned, "total": total,
       "score": round(score, 4), "tests": rows}
for name, w, ok in rows:
    print(f"{'PASS' if ok else 'fail'} {w:+d} {name}")
print(f"SCORE {earned}/{total} = {score:.4f} shipped_code={code}")
if len(sys.argv) > 2:
    Path(sys.argv[2]).write_text(json.dumps(res, indent=1))
shutil.rmtree(work, ignore_errors=True)
