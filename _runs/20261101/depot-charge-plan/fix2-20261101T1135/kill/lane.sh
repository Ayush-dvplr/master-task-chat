#!/bin/bash
# kill lane: one container per program, final bundle tests (tests-only reward 1/P)
R="/Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/fix2-20261101T1135"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/depot-charge-plan"
for p in "$@"; do
  until python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2 | grep -q START=yes; do sleep 15; done
  echo "START $p $(date +%T)"
  perl -e 'alarm 2400; exec @ARGV' docker run --rm --name "dcpkill-$p" --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1 -v "$B:/b:ro" -v "$R/kill/progs:/p:ro" -v "$R/kill/w:/w" -v "$R/kill:/k:ro" dcp-verifier:1 bash /k/run.sh "$p.py" "$p"
  echo "EXIT $p rc=$? $(date +%T)"
done
echo ALL_DONE
