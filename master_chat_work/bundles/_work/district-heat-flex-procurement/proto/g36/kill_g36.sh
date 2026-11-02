#!/bin/bash
# g36 kill test, runs inside env image with /x layout: /x/district-heat-flex-procurement = BUNDLE (ro), proto = /x/_work/district-heat-flex-procurement/proto (rw)
cd /x/_work/district-heat-flex-procurement/proto
export PYTHONDONTWRITEBYTECODE=1
B=/x/district-heat-flex-procurement; KF=g36/dout/KILL36.txt; SH=$B/environment/data
cmd() {
  case "$1" in
    solve) echo "python3 -B $B/solution/solve.py" ;;
    opus) echo "python3 -B progs/opus_derive_report.py" ;;
    old) echo "python3 -B progs/old_solve.py" ;;
    blind) echo "python3 -B progs/blind_derive_report.py" ;;
    a10) echo "python3 -B g36/progs/a10_derive_report.py" ;;
    b_*) echo "python3 -B g36/progs/$1.py" ;;
    *) echo "python3 -B run_prog.py $1 __D__ __O__ $B/solution/solve.py" ;;
  esac
}
one() {  # prog extract-name data-dir
  v=$1; e=$2; d=$3; o=g36/dout/${v}_$e; rm -rf $o; mkdir -p $o
  c=$(cmd $v)
  if [[ $c == *__D__* ]]; then c=${c/__D__/$d}; c=${c/__O__/$o}; else c="$c $d $o"; fi
  t0=$(date +%s.%N); timeout 120 $c > $o.log 2>&1; rc=$?; t1=$(date +%s.%N)
  sec=$(python3 -c "print(round($t1-$t0,2))")
  if [ "$e" = shipped ]; then pts="-"; elif [ $rc -eq 124 ]; then pts="0 0 0 0 0 LATE"; else pts=$(python3 -B g36/score36.py g36/dout/ref2_$e $o g36/p_$e.json); fi
  echo "$v $e rc=$rc sec=$sec score=$pts" >> $KF
}
mkdir -p g36/dout; rm -f $KF
for e in wide2 wide3; do one ref2 $e g36/ex/$e; done
PAIRS=("solve a10" "b_ef9234c b_d62d21c" "b_7dd7290 blind" "greedy merit" "naive dp" "bnb bnb_ord" "old opus" "ref ref3")
for pair in "${PAIRS[@]}"; do set -- $pair; one $1 shipped $SH & one $2 shipped $SH & wait; done
for e in wide2 wide3; do
  for pair in "${PAIRS[@]}"; do set -- $pair; one $1 $e g36/ex/$e & one $2 $e g36/ex/$e & wait; done
done
echo ALL_DONE >> $KF
