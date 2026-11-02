#!/bin/sh
# inside container: trap.sh <tests_dir> <solve.py> <data_dir> <dest>
T=$1; S=$2; D=$3; O=$4
mkdir -p $O
python3 -B /w/harness/variants.py $S $O/variants
for v in oracle $(ls $O/variants | sed 's/\.py$//'); do
  if [ $v = oracle ]; then mod=$S; else mod=$O/variants/$v.py; fi
  ws=$O/ws_$v; rm -rf $ws; mkdir -p $ws/out
  cp $mod $ws/out/reserving.py
  PYTHONHASHSEED=0 python3 -I -B $ws/out/reserving.py --data $D --out $ws/out > $ws/run.log 2>&1 || echo "RUNFAIL $v"
  cp $mod $ws/out/reserving.py
  python3 -B /w/harness/grade.py $T $ws $v >> $O/grades.jsonl
done
echo TRAP_DONE
