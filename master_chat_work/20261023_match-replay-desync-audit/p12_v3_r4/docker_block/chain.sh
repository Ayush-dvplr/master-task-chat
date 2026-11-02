#!/bin/zsh
D="/tmp/opencode-logs/match-replay-desync-audit-p12v3r4-20261024T211754-b81f"
cd "$D/plain/tests" && docker build --progress plain -t warm-match-replay-desync-audit . > "$D/warm.log" 2>&1
echo "warm rc=$?" >> "$D/runs.log"
run() { label=$1; copy=$2; agent=$3
  echo "=== $label $(date)" >> "$D/runs.log"
  harbor run --path "$copy" --agent "$agent" --env docker --job-name "$label" -y -o "$D/jobs" >> "$D/runs.log" 2>&1
  echo "rc=$?" >> "$D/runs.log"; }
run oracle-1 "$D/plain" oracle
run oracle-2 "$D/plain" oracle
run oracle-3 "$D/plain" oracle
run owner-only-1 "$D/owner" oracle
run nop-1 "$D/plain" nop
run stub-1 "$D/stub" oracle
echo "ALL_DONE $(date)" >> "$D/runs.log"
