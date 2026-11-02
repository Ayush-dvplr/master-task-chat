#!/bin/bash
# G5 vacuity: the shipped package unedited, archived per build_config, its own command run on /app/ci; scored on the fixed tests.
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"; B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote"
IMG=warm-cold-chain-backbone-quote:w1
DR="docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1"
until grep -q ALL_DONE "$W/runs/p12_trap2.log" 2>/dev/null; do sleep 15; done
V=/tmp/ccq_p12_var/shipped; rm -rf $V; mkdir -p $V/out; cp -Rp "$B/environment/repo" $V/repo; cp -Rp "$B/environment/ci" $V/ci
$DR -v $V:/app -v "$W":/w:ro -w /w $IMG python -B -c "import sys; sys.path.insert(0,'/w'); import variants; from pathlib import Path; p=Path('/app/out/patched-repo.zip'); p.write_bytes(b''); variants.rezip(Path('/app'))"; echo "zip rc=$?"
perl -e 'alarm 600; exec @ARGV' $DR -v $V:/app -w /app -e PYTHONPATH=/app/repo/src $IMG python -B -m task --book /app/ci --out /app/out; echo "shipped run rc=$?"
ls $V/out
echo "=== shipped new $(date +%H:%M:%S)"
perl -e 'alarm 2400; exec @ARGV' $DR -v $V:/app -v "$B/tests":/tests:ro -v "$W":/w:ro $IMG python -B /w/run_local_tests.py /app /tests/test_output.py 2>&1 | tail -45
echo ALL_DONE
