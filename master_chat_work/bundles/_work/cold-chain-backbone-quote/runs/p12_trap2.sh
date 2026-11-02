#!/bin/bash
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"; B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote"; A=/tmp/ccq_p12_app; V=/tmp/ccq_p12_var; IMG=warm-cold-chain-backbone-quote:w1
DR="docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1"
until grep -q ALL_DONE "$W/runs/p12_trap.log" 2>/dev/null; do sleep 20; done
perl -e 'alarm 900; exec @ARGV' $DR -v $A:/oracle:ro -v $V:/var_out -v "$W":/w:ro -w /w $IMG python -B /w/w1_variants.py /oracle kmb /var_out/kmb > /dev/null 2>&1; echo "kmb rc=$?"
perl -e 'alarm 900; exec @ARGV' $DR -v $A:/oracle:ro -v $V:/var_out -v "$W":/w:ro -w /w $IMG python -B -c "import sys; sys.path.insert(0,'/w'); import mutants; from pathlib import Path; mutants.build(Path('/oracle'), 'unknown_before_dup', Path('/var_out/unknown_before_dup'))" ; echo "mutant rc=$?"
find $V -name __pycache__ -prune -exec rm -rf {} +
for pair in "kmb new" "kmb old" "unknown_before_dup new"; do
  set -- $pair
  if [ $2 = new ]; then T="$B/tests"; else T="$W/p12_before/tests"; fi
  echo "=== $1 $2 $(date +%H:%M:%S)"
  perl -e 'alarm 2400; exec @ARGV' $DR -v $V/$1:/app -v "$T":/tests:ro -v "$W":/w:ro $IMG python -B /w/run_local_tests.py /app /tests/test_output.py 2>&1 | grep -v "^_check\|^  " | tail -45
done
echo ALL_DONE
