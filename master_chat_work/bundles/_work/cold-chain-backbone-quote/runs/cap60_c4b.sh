#!/bin/zsh
A=/tmp/ccq_cap60_20261030T120047-97ea
IMG=warm-cold-chain-backbone-quote:l1
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote"
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"
while ! grep -q ALL_DONE "$W/runs/cap60_c4.log"; do sleep 20; done
echo start $(date)
for v in kmb dw_global; do perl -e 'alarm 900; exec @ARGV' docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1 -v $A/oracle:/oracle:ro -v $A:/var_out -v "$W":/w:ro -w /w $IMG python -B /w/w1_variants.py /oracle $v /var_out/w_$v; echo variant $v rc $?; done
for p in w_kmb w_dw_global; do
  echo "== $p $(date)"
  perl -e 'alarm 2700; exec @ARGV' docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1 -e APP_ROOT=/app -v $A/$p:/app -v "$B/tests":/tests:ro -v "$W":/w:ro $IMG python -B /w/run_local_tests.py /app /tests/test_output.py > "$W/runs/cap60_score_$p.log" 2>&1; echo score $p rc $?; grep SCORE "$W/runs/cap60_score_$p.log"
done
echo ALL_DONE $(date)
