#!/usr/bin/env bash
set -eu
S="/Users/mac/Desktop/Terminal Bench/_runs/20261102/hangar-check-replan/fix3-20261102T235955"
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/hangar-check-replan"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/hangar-check-replan"
trap 'rc=$?; printf "EXIT=%s\nALL_DONE\n" "$rc"' EXIT
for i in $(seq 180); do
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2 | tee "$S/diagnostic_dockfree.log"
  if grep -q 'START=yes' "$S/diagnostic_dockfree.log"; then break; fi
  sleep 20
done
grep -q 'START=yes' "$S/diagnostic_dockfree.log"
perl -e 'alarm 4200; exec @ARGV' docker run --rm --name dabfeb4-resume-diagnostic --memory 4g --cpus 2 --network none \
  -e PYTHONDONTWRITEBYTECODE=1 -v "$S/plain/tests:/tests:ro" -v "$W:/work:ro" \
  -v "$B/environment/data/docs:/source_docs:ro" -v "$B/solution:/solution:ro" -v "$B/environment/data:/app/data:ro" \
  -v "/Users/mac/Desktop/Terminal Bench/_runs/20261102/hangar-check-replan/fix3-20261102T225013:/old_results:ro" \
  -v "$S:/results" --entrypoint python3 qc-warm-hangar-tests-7463:latest -B /work/resume_score.py
