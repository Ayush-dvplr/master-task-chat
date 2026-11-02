"""Blind e8e9c82 program behind the bundle command line and file names (no change to its logic)."""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.join(HERE, "..", "progs_raw", "blind_r1.py")
NAMES = {"check_plan.json": "policy_audit.json", "plan_summary.json": "summary.json",
         "data_quality.json": "data_quality.json"}
for base in ("North", "South", "West", "East"):
    NAMES[os.path.join("regions", "region_%s.json" % base.lower())] = "region_%s.json" % base
for segment in ("commercial", "public"):
    NAMES[os.path.join("segments", "segment_%s.json" % segment)] = "segment_%s.json" % segment

data, out = sys.argv[1], sys.argv[2]
tmp = tempfile.mkdtemp()
done = subprocess.run([sys.executable, PROGRAM, "--data", data, "--out", tmp])
os.makedirs(out, exist_ok=True)
for old, new in NAMES.items():
    if os.path.exists(os.path.join(tmp, old)):
        shutil.copyfile(os.path.join(tmp, old), os.path.join(out, new))
sys.exit(done.returncode)
