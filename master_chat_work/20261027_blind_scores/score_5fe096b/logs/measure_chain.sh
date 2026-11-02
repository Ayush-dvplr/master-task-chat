#!/bin/bash
# Timing/memory of each blind archive on the wide books (+ fresh_1 control), Docker 4g/2cpu as task.toml, cap 200 s.
S=/tmp/score_5fe096b
OUT="/Users/mac/Desktop/Terminal Bench/master_chat_work/20261027_blind_scores/score_5fe096b"
IMG=warm-cold-chain-backbone-quote:l1
echo "5fe096b measure $$" > /tmp/opencode-logs/locks/cold-chain-backbone-quote.lock
lane() {
  for sha in "$@"; do
    echo "=== $sha $(date +%H:%M:%S)"
    perl -e 'alarm 900; exec @ARGV' docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1 \
      -v "$S/$sha/cold-chain-backbone-quote/solution/blind/out":/app/out:ro \
      -v "$S/oracle/cold-chain-backbone-quote/tests":/tests:ro -v "$OUT/logs":/m:ro $IMG \
      python -B /m/measure_wide.py "$sha" 200 fresh_1 wide_1 wide_2 wide_3 2>&1
    echo "rc=$? $(date +%H:%M:%S)"
  done
}
lane 2cbd32a 9387727 > "$OUT/logs/measure_a.log" 2>&1 &
lane 23bef90 > "$OUT/logs/measure_b.log" 2>&1 &
wait
echo ALL_DONE >> "$OUT/logs/measure_b.log"
rm -f /tmp/opencode-logs/locks/cold-chain-backbone-quote.lock
