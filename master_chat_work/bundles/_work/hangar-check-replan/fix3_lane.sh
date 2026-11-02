#!/usr/bin/env bash
set -eu
S="/Users/mac/Desktop/Terminal Bench/_runs/20261102/hangar-check-replan/fix3-20261102T225013"
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/hangar-check-replan"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/hangar-check-replan"
trap 'rc=$?; printf "EXIT=%s\nALL_DONE\n" "$rc"' EXIT
for i in $(seq 60); do
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2 | tee "$S/dockfree.log"
  if grep -q 'START=yes' "$S/dockfree.log"; then break; fi
  sleep 20
done
grep -q 'START=yes' "$S/dockfree.log"
rc=0
perl -e 'alarm 2100; exec @ARGV' docker run --rm --name dabfeb4-fix3-diagnostic --memory 4g --cpus 2 --network none \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$W/fix3_exec_final/tests:/tests:ro" -v "$W/fix3_pre/tests:/before_tests:ro" \
  -v "$W:/work:ro" -v "$B/environment/data/docs:/source_docs:ro" \
  -v "$B/solution:/solution:ro" -v "$B/environment/data:/app/data:ro" \
  -v "$S:/results" --entrypoint bash qc-warm-hangar-tests-7463:latest -c \
  'set -eu; python3 -B /work/fix3_expected.py /before_tests /results/expected_before.json; python3 -B /work/fix3_score.py /results/scores.jsonl /solution/solve.py /work/h1_a1/a1_program.py' || rc=$?
exit "$rc"
