#!/bin/bash
# Wave-1 cost table + kill test on the built bundle, one container (python:3.12-slim, 2 cpus, 4 GB).
# usage: nohup bash cost_docker.sh > LOG 2>&1 &
set -u
BUNDLES="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles"
OUT="$BUNDLES/_work/tariff-engine-audit-repair/t4_results"
chmod 777 "$OUT"
rm -f "$OUT/cost_docker.json"
docker run --rm --name w1_d11904c_cost --cpus 2 --memory 4g --user 1000:1000 -e HOME=/tmp \
  -e PYTHONDONTWRITEBYTECODE=1 -v "$BUNDLES":/b:ro -v "$OUT":/out -w /b/_work/tariff-engine-audit-repair \
  python:3.12-slim python3 -B t4_scripts/cost_t4.py /out/cost_docker.json \
  oracle solver:reference \
  blind_r3 blind_r3+solver:reference \
  solver:blind_r3 solver:bitset solver:bitset_sum_only solver:table solver:pareto solver:mitm \
  solver:mitm_dedupe solver:mitm_dedupe_sorted solver:branch_bound solver:greedy solver:naive \
  Q1_off Q2_off Q3_off Q4_off Q5_off U1_off D1_off D2_off \
  first_write first_write+solver:bitset first_write+solver:greedy
echo "EXIT $?"
