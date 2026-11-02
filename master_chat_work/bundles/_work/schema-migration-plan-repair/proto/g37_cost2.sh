#!/bin/sh
# g37 resume: final-test cost for each program, one after another. usage: g37_cost2.sh WHO...
# blind programs and opus: oracle out with src/migrakit swapped; abo and gen_<variant>: planner file swapped.
set -u
export PYTHONDONTWRITEBYTECODE=1
swap() { python3 -B - "$1" "$2" <<'PY'
import sys, zipfile
from pathlib import Path
dst, src = sys.argv[1], Path(sys.argv[2])
with zipfile.ZipFile("/w/proto/g37_oracle_out/patched-repo.zip") as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
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
  rm -rf "/tmp/$who"; mkdir -p "/tmp/$who/out"
  cp -a /w/proto/g37_oracle_out/. "/tmp/$who/out/"
  case $who in
    abo) swap "/tmp/$who/out/patched-repo.zip" /w/proto/abo_planner.py ;;
    gen_*) sed "s/^VARIANT = \"astar\"/VARIANT = \"${who#gen_}\"/" /w/proto/g37_generic_planner.py > "/tmp/$who.py"
           swap "/tmp/$who/out/patched-repo.zip" "/tmp/$who.py" ;;
    *) swap "/tmp/$who/out/patched-repo.zip" "/w/proto/$who/src/migrakit" ;;
  esac
  s=$(date +%s)
  TEST_OUTPUT_FILE=/b/tests/test_output.py python3 -B /w/run_checks.py "/tmp/$who" "/w/proto/g37_cost_$who.json" > "/w/proto/g37_cost_$who.txt" 2>&1
  secs=$(( $(date +%s) - s ))
  python3 -B -c "import json,sys;p='/w/proto/g37_cost_$who.json';r=json.load(open(p));r['wall_seconds']=$secs;json.dump(r,open(p,'w'),indent=1);print('RUN',sys.argv[1],$secs,r['earned'],r['positive'],flush=True)" "$who"
  rm -rf "/tmp/$who"
done
echo ALL_DONE
