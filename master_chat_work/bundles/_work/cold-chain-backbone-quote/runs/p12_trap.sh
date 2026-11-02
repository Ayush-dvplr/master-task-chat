#!/bin/bash
# P12 trap survival: oracle + dw_global + kmb + perlink + report_only + nop, scored on OLD and NEW tests.
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"; B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote"; IMG=warm-cold-chain-backbone-quote:w1
DR="docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1"
A=/tmp/ccq_p12_app; V=/tmp/ccq_p12_var
rm -rf $A $V; mkdir -p $A $V
cp -Rp "$B/environment/repo" $A/repo; cp -Rp "$B/environment/ci" $A/ci
echo "=== oracle build $(date +%H:%M:%S)"
perl -e 'alarm 600; exec @ARGV' $DR -e APP_ROOT=/app -v $A:/app -v "$B/solution":/solution:ro $IMG python -B /solution/solve.py > "$W/runs/p12_oracle_build.log" 2>&1; echo "oracle rc=$?"
find $A -name __pycache__ -prune -exec rm -rf {} +
perl -e 'alarm 900; exec @ARGV' $DR -v $A:/oracle:ro -v $V:/var_out -v "$W":/w:ro -w /w $IMG python -B /w/w1_variants.py /oracle dw_global /var_out/dw_global > /dev/null 2>&1; echo "dw_global rc=$?"
for v in kmb perlink report_only nop; do
  perl -e 'alarm 900; exec @ARGV' $DR -v $A:/oracle:ro -v $V:/var_out -v "$W":/w:ro -w /w $IMG python -B /w/variants.py /oracle $v /var_out/$v > /dev/null 2>&1; echo "$v rc=$?"
done
find $V -name __pycache__ -prune -exec rm -rf {} +
for v in oracle dw_global kmb perlink report_only nop; do
  if [ $v = oracle ]; then app=$A; else app=$V/$v; fi
  for t in new old; do
    if [ $t = new ]; then tests="$B/tests"; else tests="$W/p12_before/tests"; fi
    echo "=== $v $t $(date +%H:%M:%S)"
    perl -e 'alarm 2400; exec @ARGV' $DR -v "$app":/app -v "$tests":/tests:ro -v "$W":/w:ro $IMG python -B /w/run_local_tests.py /app /tests/test_output.py 2>&1 | grep -v "^  " | tail -48
  done
done
echo ALL_DONE
