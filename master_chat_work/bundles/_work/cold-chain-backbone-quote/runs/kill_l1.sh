#!/bin/bash
# 25c745d Phase 3 kill table: every KILL_TEST row + blind eac8712, full final tests in Docker, 2 lanes.
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote"
BL="/tmp/blind/cold-chain-backbone-quote-20261027T144736-9cb7"
IMG=warm-cold-chain-backbone-quote:w1
DR="docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1"
until grep -q ALL_DONE "$W/runs/sweep_l1.log" 2>/dev/null; do sleep 20; done
echo "=== build oracle $(date +%H:%M:%S)"
rm -rf /tmp/ccq_app /tmp/ccq_var; mkdir -p /tmp/ccq_app /tmp/ccq_var
cp -Rp "$B/environment/repo" /tmp/ccq_app/repo; cp -Rp "$B/environment/ci" /tmp/ccq_app/ci
perl -e 'alarm 600; exec @ARGV' $DR -e APP_ROOT=/app -v /tmp/ccq_app:/app -v "$B/solution":/solution:ro $IMG python -B /solution/solve.py > "$W/runs/kill_l1_oracle_build.log" 2>&1
echo "oracle build rc=$?"
mkdir -p /tmp/ccq_var/eac8712
cp -Rp "$BL/app/." /tmp/ccq_var/eac8712/; cp -Rp "$BL/out" /tmp/ccq_var/eac8712/out; cp -Rp "$B/environment/ci" /tmp/ccq_var/eac8712/ci
find /tmp/ccq_app /tmp/ccq_var -name __pycache__ -prune -exec rm -rf {} +
build() {
  for v in "$@"; do
    perl -e 'alarm 900; exec @ARGV' $DR -v /tmp/ccq_app:/oracle:ro -v /tmp/ccq_var:/var_out -v "$W":/w:ro -w /w $IMG \
      python -B /w/w1_variants.py /oracle "$v" "/var_out/$v" > /dev/null 2>&1
    echo "build $v rc=$? $(date +%H:%M:%S)"
  done
}
test_lane() {
  for v in "$@"; do
    if [ "$v" = oracle ]; then app=/tmp/ccq_app; else app=/tmp/ccq_var/$v; fi
    echo "=== $v $(date +%H:%M:%S)"
    perl -e 'alarm 2400; exec @ARGV' $DR -v "$app":/app -v "$B/tests":/tests:ro -v "$W":/w:ro $IMG \
      python -B /w/run_local_tests.py /app /tests/test_output.py 2>&1 | tail -45
  done
}
A="dw_global hybrid lastuse_corridor kmb greedy blind_2611_nospan blind_2611"
Bv="lastuse_greedy frontier_corridor frontier_bfs naive_subset sph blind_d7a0_nospan probe_nospan blind_d7a0 probe"
build $A > "$W/runs/kill_l1_build_a.log" 2>&1 &
build $Bv > "$W/runs/kill_l1_build_b.log" 2>&1 &
wait
find /tmp/ccq_var -name __pycache__ -prune -exec rm -rf {} +
test_lane oracle eac8712 dw_global hybrid lastuse_corridor kmb greedy blind_2611_nospan blind_2611 > "$W/runs/kill_l1_a.log" 2>&1 &
test_lane $Bv > "$W/runs/kill_l1_b.log" 2>&1 &
wait
echo ALL_DONE >> "$W/runs/kill_l1_b.log"
echo ALL_DONE
