#!/bin/bash
# g36 cost table: runs inside env image, /k = WORK (rw), /b = BUNDLE (ro). One grader at a time in this container.
cd /k/proto
export PYTHONDONTWRITEBYTECODE=1
CF=${CF:?}
mk() {
  v=$1; ws=/k/g36/cost/ws/$v; rm -rf $ws; mkdir -p $ws/out
  case $v in
    solve) cp /b/solution/solve.py $ws/out/derive_report.py ;;
    old) cp progs/old_solve.py $ws/out/derive_report.py ;;
    opus) cp progs/opus_derive_report.py $ws/out/derive_report.py ;;
    blind) cp progs/blind_derive_report.py $ws/out/derive_report.py ;;
    a10) cp g36/progs/a10_derive_report.py $ws/out/derive_report.py ;;
    b_*) cp g36/progs/$v.py $ws/out/derive_report.py ;;
    *) printf 'import runpy\nimport sys\nsys.dont_write_bytecode = True\nsys.argv = ["run_prog.py", "%s"] + sys.argv[1:3] + ["/b/solution/solve.py"]\nrunpy.run_path("/k/proto/run_prog.py", run_name="__main__")\n' $v > $ws/out/derive_report.py ;;
  esac
  timeout 120 python3 -B $ws/out/derive_report.py /b/environment/data $ws/out > $ws.ship.log 2>&1
  t0=$(date +%s); python3 -B /k/grade.py /b/tests/test_output.py $ws --json > /k/g36/cost/cost_$v.txt 2>&1; t1=$(date +%s)
  echo "$v sec=$((t1-t0)) $(tail -1 /k/g36/cost/cost_$v.txt)" >> $CF
}
rm -f $CF
for v in $PROGS; do mk $v; done
echo ALL_DONE >> $CF
