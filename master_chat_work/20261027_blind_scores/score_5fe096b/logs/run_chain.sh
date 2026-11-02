#!/bin/bash
# 5fe096b blind-score chain: oracle sanity + 3 blinds, tests-only exe_copy copies, serial.
set -u
export OPENAI_API_KEY=unused
export PYTHONDONTWRITEBYTECODE=1
S=/tmp/score_5fe096b
OUT="/Users/mac/Desktop/Terminal Bench/master_chat_work/20261027_blind_scores/score_5fe096b"
LOG="$OUT/logs/chain.log"
: > "$LOG"
echo "5fe096b $$" > /tmp/opencode-logs/locks/cold-chain-backbone-quote.lock
find "$S" -name __pycache__ -prune -exec rm -rf {} +
run() {
  local label="$1"
  echo "=== $label start $(date +%H:%M:%S)" >> "$LOG"
  yes | harbor run -p "$S/$label/cold-chain-backbone-quote" -o "$S/jobs_$label" -y --agent oracle >> "$LOG" 2>&1
  local r
  r=$(find "$S/jobs_$label" -path '*verifier*' -name reward.json | head -1)
  echo "REWARD $label $(cat "$r" 2>/dev/null | tr -d '\n ')" >> "$LOG"
  rm -rf "$OUT/logs/jobs_$label"; cp -Rp "$S/jobs_$label" "$OUT/logs/jobs_$label"
  echo "=== $label end $(date +%H:%M:%S)" >> "$LOG"
}
run oracle
run 2cbd32a
run 23bef90
run 9387727
echo ALL_DONE >> "$LOG"
rm -f /tmp/opencode-logs/locks/cold-chain-backbone-quote.lock
