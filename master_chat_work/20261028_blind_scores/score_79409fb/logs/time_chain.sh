#!/bin/bash
S=/tmp/score_79409fb
docker build -q -t mu79409fb-tests:latest $S/oracle/tests
IMG=mu79409fb-tests:latest
for b in d5c7b9d f4f4ff5 4d36b26; do
  echo "== $b $(date +%T)"; docker ps --format '{{.Names}}'
  docker run --rm --name mu79409fb-time-$b --memory 8192m --memory-swap 8192m --cpus 2 \
    -v $S/oracle/tests:/t:ro -v $S/$b/solution/blind/out/transform.py:/app/out/transform.py:ro \
    -v $S/time_ladder.py:/time_ladder.py:ro $IMG python3 /time_ladder.py 100 ladder:1 long:1
done
rmdir /tmp/opencode-logs/locks/metered-usage-rating-pipeline.lock
echo ALL_DONE
