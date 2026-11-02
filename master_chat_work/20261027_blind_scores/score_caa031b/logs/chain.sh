#!/bin/bash
OUT="/Users/mac/Desktop/Terminal Bench/master_chat_work/20261027_blind_scores/score_caa031b"
LOCK=/tmp/opencode-logs/locks/schema-migration-plan-repair.lock
export OPENAI_API_KEY=unused
waitslot() { while [ "$(docker ps -q | wc -l | tr -d ' ')" -ge 2 ]; do echo "$(date +%T) waiting for docker slot: $(docker ps --format '{{.Names}}' | tr '\n' ' ')"; sleep 20; done; }
exec 9>"$LOCK"
echo "caa031b $$ $(date)" >&9
waitslot
echo "$(date +%T) START blind"
yes | harbor run --path /tmp/score_caa031b/schema-migration-plan-repair --agent oracle --env docker --job-name caa031b-blind-1 -o "$OUT/jobs" -y > "$OUT/logs/blind_run.log" 2>&1
echo "$(date +%T) blind exit $?"
waitslot
echo "$(date +%T) START oracle"
yes | harbor run --path /tmp/score_caa031b/schema-migration-plan-repair-oracle --agent oracle --env docker --job-name caa031b-oracle-1 -o "$OUT/jobs" -y > "$OUT/logs/oracle_run.log" 2>&1
echo "$(date +%T) oracle exit $?"
rm -f "$LOCK"
echo ALL_DONE
