#!/bin/bash
# P12 qc1 TS-24 probe: reference program plus two leftover children (one in its
# own session, one in the program's group); count uid-nobody processes after the
# tests return. Usage: qc1_ts24.sh <label>
mkdir -p /app && cp -r /srcdata /app/data
rm -rf /app/out && mkdir -p /app/out
python3 - <<'EOF'
src = open("/d/qc1_probe_solve.py").read()
hook = (
    "import subprocess as _sp\n"
    "_sp.Popen(['sleep', '600'], start_new_session=True, stdin=_sp.DEVNULL, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)\n"
    "_sp.Popen(['sleep', '601'], stdin=_sp.DEVNULL, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)\n"
)
src = src.replace("from pathlib import Path\n", "from pathlib import Path\n" + hook, 1)
open("/app/out/derive_report.py", "w").write(src)
EOF
python3 -B /app/out/derive_report.py --data /app/data --out /app/out > /dev/null 2>&1
python3 -B /d/proto/drive_tests.py /tests/test_output.py > /tmp/ts24.log 2>/dev/null
echo "LABEL $1 | $(grep '^SCORE' /tmp/ts24.log)"
sleep 2
n=0
for p in /proc/[0-9]*; do
  u=$(awk '/^Uid:/{print $2}' "$p/status" 2>/dev/null)
  if [ "$u" = "65534" ]; then n=$((n+1)); echo "LEFT $(tr '\0' ' ' < $p/cmdline)"; fi
done
echo "LEFTOVER_NOBODY $1 $n"
echo ALL_DONE
