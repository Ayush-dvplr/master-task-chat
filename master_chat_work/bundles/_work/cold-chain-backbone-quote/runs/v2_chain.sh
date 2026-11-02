#!/bin/bash
# P12 v2 (905cf6e): oracle build, timing, after-digests, vacuity (unedited), trap variants; all on the fixed tests.
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"; B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote"; IMG=warm-cold-chain-backbone-quote:w1
DR="docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1"
TS=$(date +%Y%m%dT%H%M%S)-$(openssl rand -hex 2)
A=/tmp/ccq_v2_app_$TS; V=/tmp/ccq_v2_var_$TS
mkdir -p $A $V; echo "TMP $A $V"
cp -Rp "$B/environment/repo" $A/repo; cp -Rp "$B/environment/ci" $A/ci
echo "=== oracle build $(date +%H:%M:%S)"
perl -e 'alarm 600; exec @ARGV' $DR -e APP_ROOT=/app -v $A:/app -v "$B/solution":/solution:ro $IMG python -B /solution/solve.py > "$W/runs/v2_oracle_build.log" 2>&1; echo "oracle rc=$?"
find $A -name __pycache__ -prune -exec rm -rf {} +
echo "=== timing $(date +%H:%M:%S)"
perl -e 'alarm 1500; exec @ARGV' $DR -v $A:/app -v "$B/tests":/tests:ro -v "$W":/w:ro $IMG python -B /w/time_books.py /tests/test_output.py > "$W/runs/v2_time_books.json" 2> "$W/runs/v2_time_books.err"; echo "timing rc=$?"
echo "=== after digest $(date +%H:%M:%S)"
perl -e 'alarm 1500; exec @ARGV' $DR -v "$W":/w -v "$B/environment/ci":/ci:ro $IMG python -B /w/v2_digest.py /w/test_template.py /ci /w/runs/v2_digest_after.json > "$W/runs/v2_digest_after.log" 2>&1; echo "digest rc=$?"
perl -e 'alarm 900; exec @ARGV' $DR -v $A:/oracle:ro -v $V:/var_out -v "$W":/w:ro -w /w $IMG python -B /w/w1_variants.py /oracle dw_global /var_out/dw_global > /dev/null 2>&1; echo "dw_global rc=$?"
for v in kmb perlink report_only nop; do
  perl -e 'alarm 900; exec @ARGV' $DR -v $A:/oracle:ro -v $V:/var_out -v "$W":/w:ro -w /w $IMG python -B /w/variants.py /oracle $v /var_out/$v > /dev/null 2>&1; echo "$v rc=$?"
done
S=$V/shipped; mkdir -p $S/out; cp -Rp "$B/environment/repo" $S/repo; cp -Rp "$B/environment/ci" $S/ci
$DR -v $S:/app -v "$W":/w:ro -w /w $IMG python -B -c "import sys; sys.path.insert(0,'/w'); import variants; from pathlib import Path; p=Path('/app/out/patched-repo.zip'); p.write_bytes(b''); variants.rezip(Path('/app'))"; echo "zip rc=$?"
perl -e 'alarm 600; exec @ARGV' $DR -v $S:/app -w /app -e PYTHONPATH=/app/repo/src $IMG python -B -m task --book /app/ci --out /app/out; echo "shipped run rc=$?"
find $V -name __pycache__ -prune -exec rm -rf {} +
for v in oracle shipped nop perlink kmb dw_global report_only; do
  if [ $v = oracle ]; then app=$A; else app=$V/$v; fi
  echo "=== $v new $(date +%H:%M:%S)"
  perl -e 'alarm 2400; exec @ARGV' $DR -v "$app":/app -v "$B/tests":/tests:ro -v "$W":/w:ro $IMG python -B /w/run_local_tests.py /app /tests/test_output.py 2>&1 | grep -v "^ *$" | tail -48
done
echo ALL_DONE
