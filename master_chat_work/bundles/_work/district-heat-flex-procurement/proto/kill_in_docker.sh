#!/bin/bash
# runs inside the env image: /w = proto (rw), /b = BUNDLE (ro). Two programs at a time, 120 s each.
cd /w
export PYTHONDONTWRITEBYTECODE=1
EXTS="${EXTS:-e6_31 e6_33 e6_34}"; KF=${KF:-dout/KILL.txt}
cmd() {
  case "$1" in
    solve) echo "python3 -B /b/solution/solve.py" ;;
    opus) echo "python3 -B progs/opus_derive_report.py" ;;
    old) echo "python3 -B progs/old_solve.py" ;;
    *) echo "python3 -B run_prog.py $1 __D__ __O__ /b/solution/solve.py" ;;
  esac
}
one() {
  v=$1; e=$2; o=dout/${v}_$e; rm -rf $o; mkdir -p $o
  c=$(cmd $v)
  if [[ $c == *__D__* ]]; then c=${c/__D__/ex\/$e}; c=${c/__O__/$o}; else c="$c ex/$e $o"; fi
  t0=$(date +%s.%N); timeout 120 $c > $o.log 2>&1; rc=$?; t1=$(date +%s.%N)
  sec=$(python3 -c "print(round($t1-$t0,2))")
  if [ $rc -eq 124 ]; then pts="0 0 0 0 0 LATE"; else pts=$(python3 -B score.py dout/ref2_$e $o p_$e.json); fi
  echo "$v $e rc=$rc sec=$sec score=$pts" >> $KF
}
mkdir -p dout; rm -f $KF
for e in $EXTS; do one ref2 $e; done
for e in $EXTS; do
  for pair in "greedy merit" "naive dp" "bnb blind" "solve old" "opus bnb_ord" "ref ref3"; do
    set -- $pair
    one $1 $e & one $2 $e & wait
  done
done
echo ALL_DONE >> $KF
