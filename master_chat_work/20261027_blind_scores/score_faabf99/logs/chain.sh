#!/bin/bash
export OPENAI_API_KEY=unused
LOG="/Users/mac/Desktop/Terminal Bench/master_chat_work/20261027_blind_scores/score_faabf99/logs/chain.log"
LOCK=/tmp/opencode-logs/locks/district-heat-flex-procurement.lock
echo "faabf99 blind-score $$" > $LOCK
heavy() { docker ps --format '{{.Names}}' | grep -v -c sidecar; }
for name in oracle ef9234c d62d21c 7dd7290; do
  w=0; while [ "$(heavy)" -ge 2 ]; do sleep 20; w=$((w+20)); done
  echo "START $name $(date +%T) heavy=$(heavy) waited=${w}s" >> "$LOG"
  yes | harbor run --agent oracle --env docker -p /tmp/score_faabf99/$name/district-heat-flex-procurement -o /tmp/score_faabf99/jobs --job-name faabf99-$name > "/Users/mac/Desktop/Terminal Bench/master_chat_work/20261027_blind_scores/score_faabf99/logs/$name.harbor.log" 2>&1
  echo "END $name rc=$? $(date +%T)" >> "$LOG"
done
rm -f $LOCK
echo "ALL_DONE $(date +%T)" >> "$LOG"
