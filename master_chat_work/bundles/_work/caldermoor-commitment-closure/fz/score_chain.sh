#!/bin/bash
# usage: score_chain.sh <tests_dir> <tag> <labels...>
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/caldermoor-commitment-closure"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/caldermoor-commitment-closure"
T="$1"; tag="$2"; shift 2
for lab in "$@"; do
  docker run --rm --name cm5f2e-$tag-$lab-$RANDOM --network none --cpus 4 -m 6g -e PYTHONDONTWRITEBYTECODE=1 \
    -v "$T":/tests:ro -v "$W/fz":/fz:ro -v "$B/environment/data":/app/data:ro \
    warm-caldermoor-commitment-closure python3 /fz/score.py /fz/mut/$lab/reconcile.py /tests $lab \
    >> "$W/fz/score_$tag.jsonl" 2>> "$W/fz/score_$tag.err"
done
echo ALL_DONE >> "$W/fz/score_$tag.err"
