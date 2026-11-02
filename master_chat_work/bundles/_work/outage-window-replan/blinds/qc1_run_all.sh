#!/bin/bash
# P12 qc1: re-score the three blind programs on the fixed tests (BLIND_BRIEF scorer); before scores kept in blinds/qc1_before/
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/outage-window-replan"; B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/outage-window-replan"
for p in 9aaa86f:8352 25a31cb:2fd8 59480e5:273c; do SHA=${p%%:*}; BLIND_DIR=/tmp/blind/outage-window-replan-20261030T071801-${p##*:}
docker run --rm --init --memory 4g --cpus 2 --name owr_qc1score_${SHA}_$1 -v "$B/environment/data:/srcdata:ro" -v "$B/tests:/tests:ro" -v "$BLIND_DIR:/blind:ro" -v "$W:/d" python:3.12-slim perl -e 'alarm 1800; exec @ARGV' bash /d/proto/score_blind.sh > "$W/blinds/score_qc1_$SHA.txt" 2>&1
echo "DONE $SHA rc=$?"; done; echo ALL_SCORED
