#!/bin/zsh
D="/tmp/opencode-logs/match-replay-desync-audit-p12v3r6-20261025T164537-9df7"
cd "$D/plain/tests" && docker build --progress plain -t warm-match-replay-desync-audit . > "$D/warm.log" 2>&1
echo "warm rc=$?" >> "$D/runs.log"
run() { label=$1; copy=$2; agent=$3
  echo "=== $label $(date)" >> "$D/runs.log"
  harbor run -p "$copy" --agent "$agent" -o "$D/jobs" --job-name "$label" --env docker -y --no-delete >> "$D/runs.log" 2>&1
  echo "rc=$?" >> "$D/runs.log"; }
run oracle-1 "$D/plain" oracle
run oracle-2 "$D/plain" oracle
run oracle-3 "$D/plain" oracle
run owner-only-1 "$D/owner" oracle
run nop-1 "$D/plain" nop
echo "ALL_DONE $(date)" >> "$D/runs.log"
