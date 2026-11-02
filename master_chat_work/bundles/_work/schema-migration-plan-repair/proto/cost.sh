#!/bin/sh
# Cost table runs inside the verifier image: oracle, all-but-one (oracle with the earlier plain planner), blind cee149a.
# Mounts: /w = WORK, /b = bundle copy (ro), /t = tests copy (ro), /blind = blind out (ro).
set -u
export PYTHONDONTWRITEBYTECODE=1
mkdir -p /tmp/o && cp -a /b/environment/repo /b/environment/ci /tmp/o/
APP_ROOT=/tmp/o python3 -B /b/solution/solve.py > /tmp/o_solve.log 2>&1; echo "oracle solve rc $?"
mkdir -p /tmp/abo && cp -a /tmp/o/out /tmp/abo/out
mkdir -p /tmp/abo_zip && cd /tmp/abo_zip && python3 -B - <<'EOF'
import zipfile, shutil
src = "/tmp/o/out/patched-repo.zip"; dst = "/tmp/abo/out/patched-repo.zip"
new = open("/w/proto/abo_planner.py", "rb").read()
with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename.endswith("src/migrakit/core/planner.py"):
            data = new
            print("replaced", item.filename)
        zout.writestr(item, data)
EOF
mkdir -p /tmp/bl && cp -a /blind /tmp/bl/out
mkdir -p /tmp/mem && cp -a /tmp/abo/out /tmp/mem/out && python3 -B - <<'EOF2'
import zipfile
src = "/tmp/o/out/patched-repo.zip"; dst = "/tmp/mem/out/patched-repo.zip"
new = open("/w/proto/mem_planner.py", "rb").read()
with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename.endswith("src/migrakit/core/planner.py"):
            data = new
        zout.writestr(item, data)
EOF2
for who in o abo bl mem; do
  s=$(date +%s)
  TEST_OUTPUT_FILE=/t/test_output.py python3 -B /w/run_checks.py /tmp/$who /w/proto/cost_$who.json > /w/proto/cost_$who.txt 2>&1
  echo "RUN $who rc $? secs $(( $(date +%s) - s )) $(tail -1 /w/proto/cost_$who.txt)"
done
echo ALL_DONE
