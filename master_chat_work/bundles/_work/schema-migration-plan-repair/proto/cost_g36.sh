#!/bin/sh
# Scratch: gate v3.6 cost table in the verifier image. usage: cost_g36.sh WHO...  (a5 | bl2 | abo)
set -u
export PYTHONDONTWRITEBYTECODE=1
for who in "$@"; do
  mkdir -p /tmp/$who
  case $who in
    a5) cp -a /a5out /tmp/a5/out ;;
    bl2) cp -a /bl2out /tmp/bl2/out ;;
    abo) mkdir -p /tmp/abo/out && cp -a /w/proto/g36_oracle_out/. /tmp/abo/out/ 2>/dev/null || true
         mkdir -p /tmp/o && cp -a /b/environment/repo /b/environment/ci /tmp/o/ && APP_ROOT=/tmp/o python3 -B /b/solution/solve.py > /tmp/o_solve.log 2>&1
         cp -a /tmp/o/out/. /tmp/abo/out/
         python3 -B - <<'PY'
import zipfile
src="/tmp/o/out/patched-repo.zip"; dst="/tmp/abo/out/patched-repo.zip"; new=open("/w/proto/abo_planner.py","rb").read()
with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst,"w",zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data=zin.read(item.filename)
        if item.filename.endswith("src/migrakit/core/planner.py"): data=new
        zout.writestr(item,data)
PY
         ;;
  esac
  s=$(date +%s)
  TEST_OUTPUT_FILE=/b/tests/test_output.py python3 -B /w/run_checks.py /tmp/$who /w/proto/g36_cost_$who.json > /w/proto/g36_cost_$who.txt 2>&1
  echo "RUN $who rc $? secs $(( $(date +%s) - s )) $(tail -1 /w/proto/g36_cost_$who.txt)"
done
echo ALL_DONE
