#!/bin/sh
# inside container: v4_checks.sh  (BUNDLE at /b read-only, WORK at /w)
set -u
R=/w/runs
rm -rf $R/trap_v4_after $R/vacuity_v4 $R/hyg_v4
sh /w/harness/trap.sh /b/tests /b/solution/solve.py /b/environment/data $R/trap_v4_after
mkdir -p $R/vacuity_v4/ws/out
python3 -B /w/harness/grade.py /b/tests $R/vacuity_v4/ws vacuity > $R/vacuity_v4/grade.json
mkdir -p $R/hyg_v4
for m in alae curve; do
  ws=$R/hyg_v4/ws_$m; mkdir -p $ws/out
  if [ $m = alae ]; then
    sed 's/"alae_convention": alae_convention,/"alae_convention": "excess_only",/' /b/solution/solve.py > $ws/mut.py
  else
    sed 's/"discount_curve": discount_curve_mode,/"discount_curve": "flat_10y",/' /b/solution/solve.py > $ws/mut.py
  fi
  grep -c 'excess_only",\|"flat_10y",' $ws/mut.py
  cp $ws/mut.py $ws/out/reserving.py
  PYTHONHASHSEED=0 python3 -I -B $ws/out/reserving.py --data /b/environment/data --out $ws/out > $ws/run.log 2>&1 || echo "RUNFAIL $m"
  cp $ws/mut.py $ws/out/reserving.py; rm $ws/mut.py
  python3 -B /w/harness/grade.py /b/tests $ws hyg_$m >> $R/hyg_v4/grades.jsonl
done
echo ALL_DONE
