#!/bin/bash
# run_case.sh slug driver cases results workers [name]
W=/tmp/test_depth-20261024T2141; t=$1
docker run --rm --name ${6:-td840-fz-$t} --network none --cpus ${7:-4} -m 6g -v $W/nj/$t:/tests:ro -v $W/fz:/fz -v $W/agent/$t/out:/progs/agent:ro -v $W/tasks/$t/solution:/progs/oracle:ro td840-$t-verifier python3 /fz/$2 /fz/$3 /fz/$4 $5
