#!/bin/bash
# runs baselines on candidates, 4 containers at a time
cd "$(dirname "$0")/.."
run() { docker run --rm --cpus=2 -v "$PWD":/w -w /w frp-premortem python3 -B baselines.py "tmp/cand/$1" 20 10 large > "logs/base_$1.log" 2>&1; }
set -- h1_1 h1_3 h1_4 h2_1 h2_2 h2_3 h2_4 h3_1 h3_2
i=0
for c in "$@"; do run "$c" & i=$((i+1)); if [ $((i % 4)) -eq 0 ]; then wait; fi; done
wait
echo ALL_DONE > logs/base_all.done
