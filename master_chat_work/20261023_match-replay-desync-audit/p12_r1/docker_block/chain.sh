#!/bin/zsh
cd "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/plain/tests" && docker build --progress plain -t warm-match-replay-desync-audit . > "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/warm.log" 2>&1
echo "warm rc=$?" >> "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/runs.log"
run() { label=$1; copy=$2; agent=$3
  echo "=== $label $(date)" >> "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/runs.log"
  harbor run --path "$copy" --agent "$agent" --env docker --job-name "$label" -y -o "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/jobs" >> "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/runs.log" 2>&1
  echo "rc=$?" >> "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/runs.log"; }
run oracle-1 "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/plain" oracle
run oracle-2 "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/plain" oracle
run oracle-3 "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/plain" oracle
run owner-only-1 "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/owner" oracle
run chmod600-1 "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/chmod600" oracle
run nop-1 "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/plain" nop
run stub-1 "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/stub" oracle
run forgery-1 "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/forgery" oracle
echo "ALL_DONE $(date)" >> "/tmp/opencode-logs/match-replay-desync-audit-p12-20261023T213805-77e9/runs.log"
