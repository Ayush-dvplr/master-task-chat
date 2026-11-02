#!/bin/bash
# inside env image: /k = WORK (rw), /b = BUNDLE (ro). TESTS = path of test_output.py to grade with. TAG = before|after
cd /k/p12; export PYTHONDONTWRITEBYTECODE=1
CF=dout/TRAP_$TAG.txt; mkdir -p dout ws_$TAG; rm -f $CF
mk() { v=$1; ws=ws_$TAG/$v; rm -rf $ws; mkdir -p $ws/out
  case $v in
    oracle) cp /b/solution/solve.py $ws/out/derive_report.py ;;
    plain) cp /k/proto/progs/old_solve.py $ws/out/derive_report.py ;;
    greedy) printf 'import runpy\nimport sys\nsys.dont_write_bytecode = True\nsys.argv = ["run_prog.py", "greedy"] + sys.argv[1:3] + ["/b/solution/solve.py"]\nrunpy.run_path("/k/proto/run_prog.py", run_name="__main__")\n' > $ws/out/derive_report.py ;;
    blind_*) cp progs/$v.py $ws/out/derive_report.py ;;
    *) printf 'import os, runpy, sys\nos.environ["VARIANT_FLAG"] = "%s"\nos.environ["VARIANT_TESTS"] = "%s"\nrunpy.run_path("/k/p12/variant.py", run_name="__main__")\n' $v $TESTS > $ws/out/derive_report.py ;;
  esac
  timeout 120 python3 -B $ws/out/derive_report.py /b/environment/data $ws/out > $ws.ship.log 2>&1
  chmod -R a+rX $ws
  t0=$(date +%s); python3 -B /k/grade.py $TESTS $ws --json > dout/trap_${TAG}_$v.txt 2>&1; t1=$(date +%s)
  echo "$v sec=$((t1-t0)) $(tail -1 dout/trap_${TAG}_$v.txt)" >> $CF; }
for v in ${PROGS:-oracle REENTRY CHAIN1 RELIEF plain greedy blind_ef9234c blind_d62d21c blind_7dd7290}; do mk $v; done
echo ALL_DONE >> $CF
