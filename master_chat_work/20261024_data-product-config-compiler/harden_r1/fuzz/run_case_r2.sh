#!/bin/bash
# adapted copy of test_depth kit run_case.sh for e317de1: run_case.sh driver cases results workers [name] [cpus] [agentdir]
W=/tmp/fz-e317de1-20261025T010107-0f84
docker run --rm --name ${5:-fz-e317de1-cf} --network none --cpus ${6:-4} -m 6g -v $W/nj/cf:/tests:ro -v $W/fz:/fz -v ${7:-$W/agent/out}:/progs/agent:ro fz-e317de1-cf-verifier python3 /fz/$1 /fz/$2 /fz/$3 $4
