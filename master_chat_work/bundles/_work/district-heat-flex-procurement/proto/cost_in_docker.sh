#!/bin/bash
# runs inside the env image: /k = WORK (rw), /b = BUNDLE (ro). Grades each program with the real tests (stub rewardkit).
cd /k/proto
export PYTHONDONTWRITEBYTECODE=1
PROGS="${PROGS:-solve old opus blind greedy merit naive dp bnb bnb_ord ref ref3}"
CF=${CF:-dout/COST.txt}
mk() {
  v=$1; ws=costws/$v; rm -rf $ws; mkdir -p $ws/out
  case $v in
    solve) cp /b/solution/solve.py $ws/out/derive_report.py ;;
    old) cp progs/old_solve.py $ws/out/derive_report.py ;;
    opus) cp progs/opus_derive_report.py $ws/out/derive_report.py ;;
    blind) cp progs/blind_derive_report.py $ws/out/derive_report.py ;;
    *) printf 'import runpy\nimport sys\nsys.dont_write_bytecode = True\nsys.argv = ["run_prog.py", "%s"] + sys.argv[1:3] + ["/b/solution/solve.py"]\nrunpy.run_path("/k/proto/run_prog.py", run_name="__main__")\n' $v > $ws/out/derive_report.py ;;
  esac
  timeout 120 python3 -B $ws/out/derive_report.py /b/environment/data $ws/out > $ws.ship.log 2>&1
  t0=$(date +%s); python3 -B /k/grade.py /b/tests/test_output.py $ws --json > dout/cost_$v.txt 2>&1; t1=$(date +%s)
  echo "$v sec=$((t1-t0)) $(tail -1 dout/cost_$v.txt)" >> $CF
}
mkdir -p dout costws; rm -f $CF
for v in $PROGS; do mk $v; done
echo ALL_DONE >> $CF
