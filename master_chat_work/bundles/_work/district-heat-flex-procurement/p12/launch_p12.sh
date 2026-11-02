#!/bin/bash
# chain: new tests (TAG p12new) then old tests (TAG p12old); variants always use the new reference (VTESTS)
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/district-heat-flex-procurement"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/district-heat-flex-procurement"
run() { TAG=$1; TESTS=$2; PROGS=$3
  while [ $(docker ps -q | wc -l) -ge 2 ]; do sleep 20; done
  echo "$(date +%H:%M:%S) start $TAG"
  docker run --rm --name dh_p12_$TAG --memory 4g --cpus 2 -e TAG=$TAG -e TESTS=$TESTS -e VTESTS=/k/p12/new_tests.py -e PROGS="$PROGS" \
    -v "$W":/k -v "$B":/b:ro w1env-dhfp:latest perl -e 'alarm 3000; exec @ARGV' bash /k/p12/trap2.sh
  echo "$(date +%H:%M:%S) end $TAG rc=$?"; }
run p12new /k/p12/new_tests.py "oracle UNIT10 CODESHIP ADDmiss GAPdrop LEDwithin ALWge CLAIMlt a12_agent a11_agent REENTRY CHAIN1 RELIEF greedy empty_portfolio"
run p12old /k/pushed_e9d91966ed25/tests/test_output.py "UNIT10 CODESHIP ADDmiss GAPdrop LEDwithin ALWge CLAIMlt a12_agent a11_agent"
echo ALL_DONE
