#!/bin/bash
OUT="/Users/mac/Desktop/Terminal Bench/master_chat_work/20261027_blind_scores/score_faabf99/logs"
LOCK=/tmp/opencode-logs/locks/district-heat-flex-procurement.lock
heavy() { docker ps --format '{{.Names}}' | grep -v -c sidecar; }
w=0; while [ "$(heavy)" -ge 2 ]; do sleep 20; w=$((w+20)); done
echo "faabf99 timing-diag $$" > $LOCK
echo "START diag $(date +%T) heavy=$(heavy) waited=${w}s" >> "$OUT/chain.log"
docker run --rm --name faabf99-timing --network none --cpus 4 \
  -v /tmp/score_faabf99/oracle/district-heat-flex-procurement/tests:/tests:ro \
  -v /tmp/score_faabf99/diag:/diag:ro \
  warm-district-heat-flex-procurement-tests:latest \
  bash -c 'CAP=400 python3 /diag/time_wide.py /diag/blinds/reference.py /diag/blinds/ef9234c.py /diag/blinds/d62d21c.py /diag/blinds/7dd7290.py' > "$OUT/timing_diag.log" 2>&1
echo "END diag rc=$? $(date +%T)" >> "$OUT/chain.log"
rm -f $LOCK
echo "ALL_DONE diag $(date +%T)" >> "$OUT/chain.log"
