#!/bin/sh
# runs inside python:3.12-slim with /p = proto dir, /w = scratch
cd /w
CAP=${CAP:-300}
SOLVERS=${SOLVERS:-"greedy_id greedy_edf greedy_class greedy_swap depot_prorata depot_priority split_exact flow_plain flow_eps flow_post careful_resolve"}
INST=${INST:-"shipped:1 hidden:1 hidden:2 hidden:3 hidden:4 hidden:5 hidden:6"}
for spec in $INST; do
  kind=${spec%%:*}; seed=${spec##*:}
  python3 -B /p/gen_proto.py $seed $kind inst_${kind}_$seed.json
  perl -e "alarm $CAP; exec @ARGV" python3 -B /p/core.py ref inst_${kind}_$seed.json ref_${kind}_$seed.json
  python3 -B -c "import json;r=json.load(open('ref_${kind}_$seed.json'));print('REF',\"$kind:$seed\",r['sec'],r['obj'],'bindF',r['bind_feeder'],'bindC',r['bind_cap'])"
done
for sv in $SOLVERS; do
  for spec in $INST; do
    kind=${spec%%:*}; seed=${spec##*:}
    t0=$(date +%s)
    perl -e "alarm $CAP; exec @ARGV" python3 -B /p/core.py $sv inst_${kind}_$seed.json out_${sv}_${kind}_$seed.json 2>err_${sv}_${kind}_$seed.txt
    rc=$?
    t1=$(date +%s)
    python3 -B /p/compare.py $sv $kind:$seed ref_${kind}_$seed.json out_${sv}_${kind}_$seed.json $rc $((t1-t0))
  done
done
echo ALL_DONE
