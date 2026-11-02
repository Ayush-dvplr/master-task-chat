#!/bin/bash
# Wave 1 measured cost table: full tests per delivery in the verifier image, two containers at a time.
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"
one() {
  for v in "$@"; do
    if [ "$v" = oracle ]; then app=/tmp/ccq_app; else app=/tmp/ccq_var/$v; fi
    echo "=== $v $(date +%H:%M:%S)"
    docker run --rm --cpus 2 --memory 4g -e PYTHONDONTWRITEBYTECODE=1 -v "$app":/app -v "$W":/w:ro \
      warm-cold-chain-backbone-quote:w1 python -B /w/run_local_tests.py /app /tests/test_output.py 2>&1 | tail -40
  done
}
one oracle lastuse_corridor frontier_corridor dw_global kmb greedy blind_2611_nospan probe_nospan > "$W/runs/cost_w1_a.log" 2>&1 &
one lastuse_greedy hybrid sph naive_subset blind_d7a0_nospan frontier_bfs > "$W/runs/cost_w1_b.log" 2>&1 &
wait
echo ALL_DONE >> "$W/runs/cost_w1_b.log"
rm -f /tmp/opencode-logs/locks/cold-chain-backbone-quote.lock
