#!/bin/bash
# usage: p0.sh slug agent|oracle
t=$1; m=$2; W=/tmp/test_depth-20261024T2141; cd $W
rm -rf p0/$t/$m; mkdir -p p0/$t/$m/logs p0/$t/$m/app
if [ -d tasks/$t/environment/data ]; then cp -R tasks/$t/environment/data p0/$t/$m/app/data; fi
for d in ci repo; do [ -d tasks/$t/environment/$d ] && cp -R tasks/$t/environment/$d p0/$t/$m/app/$d; done
if [ $m = agent ]; then cp -R agent/$t/out p0/$t/$m/app/out; PRE=true; else mkdir -p p0/$t/$m/app/out; PRE="bash /solution/solve.sh"; fi
chmod -R a+rwX p0/$t/$m/app
docker run --rm --network none --cpus 2 -m 4g -v $W/nj/$t:/tests_src:ro -v $W/tasks/$t/solution:/solution:ro -v $W/p0/$t/$m/app:/app -v $W/p0/$t/$m/logs:/logs/verifier td840-$t-verifier bash -c "cd /app && $PRE > /logs/verifier/solve.log 2>&1; rm -rf /tests && cp -R /tests_src /tests && bash /tests/test.sh" > p0/$t/$m/run.log 2>&1
echo "$t $m exit $? reward=$(cat p0/$t/$m/logs/reward.json 2>/dev/null)"
