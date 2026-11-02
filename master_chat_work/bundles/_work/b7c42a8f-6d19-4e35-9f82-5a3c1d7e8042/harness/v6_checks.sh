#!/bin/sh
# inside container: v6_checks.sh  (BUNDLE at /b read-only, WORK at /w)
# trap survival, vacuity, settlement word mutants and hard-coded settlement mutants (AL-27 bite proof)
set -u
R=/w/runs
rm -rf $R/trap_v6_after $R/vacuity_v6 $R/hyg_v6 $R/cov_v6
sh /w/harness/trap.sh /b/tests /b/solution/solve.py /b/environment/data $R/trap_v6_after
mkdir -p $R/vacuity_v6/ws/out
python3 -B /w/harness/grade.py /b/tests $R/vacuity_v6/ws vacuity > $R/vacuity_v6/grade.json
mkdir -p $R/hyg_v6
S=/b/solution/solve.py
for m in word_alae word_curve hard_words hard_alae hard_curve hard_both; do
  ws=$R/hyg_v6/ws_$m; mkdir -p $ws/out
  case $m in
    word_alae)  sed 's/"alae_convention": alae_convention,/"alae_convention": "excess_only",/' $S > $ws/mut.py ;;
    word_curve) sed 's/"discount_curve": discount_curve_mode,/"discount_curve": "flat_10y",/' $S > $ws/mut.py ;;
    hard_words) sed -e 's/"alae_convention": alae_convention,/"alae_convention": "pro_rata",/' \
                    -e 's/"discount_curve": discount_curve_mode,/"discount_curve": "duration_matched",/' $S > $ws/mut.py ;;
    hard_alae)  sed 's/^    alae_convention, alae_fraction = settle_alae_convention(data)$/    alae_convention, alae_fraction = "pro_rata", 0.08/' $S > $ws/mut.py ;;
    hard_curve) sed 's/^    discount_curve_mode = settle_discount_curve(data)$/    discount_curve_mode = "duration_matched"/' $S > $ws/mut.py ;;
    hard_both)  sed -e 's/^    alae_convention, alae_fraction = settle_alae_convention(data)$/    alae_convention, alae_fraction = "pro_rata", 0.08/' \
                    -e 's/^    discount_curve_mode = settle_discount_curve(data)$/    discount_curve_mode = "duration_matched"/' $S > $ws/mut.py ;;
  esac
  echo "$m changed_lines=$(diff $S $ws/mut.py | grep -c '^>')"
  cp $ws/mut.py $ws/out/reserving.py
  PYTHONHASHSEED=0 python3 -I -B $ws/out/reserving.py --data /b/environment/data --out $ws/out > $ws/run.log 2>&1 || echo "RUNFAIL $m"
  cp $ws/mut.py $ws/out/reserving.py; rm $ws/mut.py
  python3 -B /w/harness/grade.py /b/tests $ws $m >> $R/hyg_v6/grades.jsonl
done
sh /w/harness/cov.sh /b/tests /b/solution/solve.py /b/environment/data $R/cov_v6
echo ALL_DONE
