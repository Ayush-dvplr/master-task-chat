#!/bin/sh
# inside container: BUNDLE /b ro, WORK /w; saved agent out at /w/runs/replay_v3/ws/out (copy of original_backup artifacts/app/out)
set -u
R=/w/runs/replay_v4; rm -rf $R; mkdir -p $R
for side in before after; do
  ws=$R/ws_$side; mkdir -p $ws/out; cp /w/runs/replay_v3/ws/out/* $ws/out/
  if [ $side = before ]; then T=/w/qc4_b5dd7c985e44/tests; else T=/b/tests; fi
  python3 -B /w/harness/grade.py $T $ws replay_$side >> $R/grades.jsonl
done
echo ALL_DONE
