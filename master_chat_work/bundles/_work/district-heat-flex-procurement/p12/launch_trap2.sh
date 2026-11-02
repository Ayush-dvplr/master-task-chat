#!/bin/bash
# waits for a Docker slot (< 2 heavy containers), then runs trap.sh TAG in the env image
TAG=$1; TESTS=$2
while [ $(docker ps -q | wc -l) -ge 2 ]; do sleep 30; done
docker run --rm --name dh_p12_trap2_$TAG --memory 4g --cpus 2 -e TAG=$TAG -e TESTS=$TESTS -e PROGS="$PROGS"   -v "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/district-heat-flex-procurement":/k -v "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/district-heat-flex-procurement":/b:ro w1env-dhfp:latest perl -e 'alarm 5400; exec @ARGV' bash /k/p12/trap2.sh
echo LAUNCH_DONE
