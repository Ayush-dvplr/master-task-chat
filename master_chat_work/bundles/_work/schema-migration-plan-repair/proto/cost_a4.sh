#!/bin/sh
# Scratch (gate v3.6 harden a4f790c): cost table on the final tests. usage: cost_a4.sh WHO...
# a6 / a5: the run's own /app/out. abo: oracle out with the pre-harden oracle planner. Others: oracle out with
# src/migrakit swapped for that program's package (metadata json files stay the oracle's).
set -u
export PYTHONDONTWRITEBYTECODE=1
mkdir -p /tmp/o && cp -a /b/environment/repo /b/environment/ci /tmp/o/ && APP_ROOT=/tmp/o python3 -B /b/solution/solve.py > /tmp/o_solve.log 2>&1
echo "oracle out rc $? $(ls /tmp/o/out | tr '\n' ' ')"
swap() { python3 -B - "$1" "$2" <<'PY'
import sys, zipfile
from pathlib import Path
dst, src = sys.argv[1], Path(sys.argv[2])
with zipfile.ZipFile("/tmp/o/out/patched-repo.zip") as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        if src.suffix == ".py":
            data = src.read_bytes() if item.filename.endswith("src/migrakit/core/planner.py") else zin.read(item.filename)
            zout.writestr(item, data)
        elif not item.filename.startswith("src/migrakit/"):
            zout.writestr(item, zin.read(item.filename))
    if src.suffix != ".py":
        for f in sorted(src.rglob("*.py")):
            if "__pycache__" not in f.parts:
                zout.writestr("src/migrakit/" + f.relative_to(src).as_posix(), f.read_bytes())
PY
}
for who in "$@"; do
  rm -rf /tmp/$who; mkdir -p /tmp/$who/out
  case $who in
    a6) cp -a /a6out/. /tmp/a6/out/ ;;
    a5) cp -a /a5out/. /tmp/a5/out/ ;;
    abo) cp -a /tmp/o/out/. /tmp/abo/out/; swap /tmp/abo/out/patched-repo.zip /s/planner_before.py ;;
    *) cp -a /tmp/o/out/. /tmp/$who/out/; swap /tmp/$who/out/patched-repo.zip /w/proto/$who/src/migrakit ;;
  esac
  s=$(date +%s)
  TEST_OUTPUT_FILE=/b/tests/test_output.py python3 -B /w/run_checks.py /tmp/$who /w/proto/a4_cost_$who.json > /w/proto/a4_cost_$who.txt 2>&1
  echo "RUN $who rc $? secs $(( $(date +%s) - s )) $(tail -1 /w/proto/a4_cost_$who.txt)"
done
echo ALL_DONE
