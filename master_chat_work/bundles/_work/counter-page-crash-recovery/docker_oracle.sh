#!/bin/bash
# Usage: docker_oracle.sh <mode: oracle|nop|app DIR>  -> runs solve (oracle) then the local stub grader as root.
set -euo pipefail
WORK="$(cd "$(dirname "$0")" && pwd)"
BUNDLE="$WORK/../../counter-page-crash-recovery"
T=/var/folders/13/lkwk3zl54tvf9xz694_t4rvm0000gn/T/opencode/cpcr_run
MODE="${1:-oracle}"
rm -rf "$T"; mkdir -p "$T/app/out" "$T/tests"
cp -R "$BUNDLE/environment/data" "$T/app/data"
cp -R "$BUNDLE/tests/." "$T/tests/"
cp "$WORK/run_local_tests.py" "$T/run_local_tests.py"
chmod -R a+rwX "$T"
IMG=public.ecr.aws/docker/library/python@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b
if [ "$MODE" = oracle ]; then
  S=$(date +%s)
  docker run --rm --network none -u 1000:1000 -e HOME=/tmp -v "$T/app:/app" -v "$BUNDLE/solution:/solution:ro" "$IMG" bash /solution/solve.sh > "$T/solve.log" 2>&1
  echo "solve rc=0 seconds=$(( $(date +%s) - S ))"
  tail -12 "$T/solve.log"
elif [ "$MODE" = app ]; then
  rm -rf "$T/app/out"; cp -R "$2" "$T/app/out"; chmod -R a+rwX "$T/app"
fi
docker run --rm --network none -v "$T/app:/app" -v "$T/tests:/tests" -v "$T/run_local_tests.py:/r.py:ro" qc-warm-evs-tests:latest python3 -B /r.py /app /tests/test_output.py
