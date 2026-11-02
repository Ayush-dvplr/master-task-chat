#!/bin/zsh
# g37 tests-only Harbor gate chain on exe_copy copies; two runs at a time.
D=$1
cd $D
export OPENAI_API_KEY=unused
L=/tmp/opencode-logs/locks/schema-migration-plan-repair.lock
mkdir -p /tmp/opencode-logs/locks
echo "g37 9111ecc $(date) $$" > $L
others() { docker ps --format '{{.Names}}' | grep -v '^g37_9111ecc' | grep -v -E '^(plain|owner|stub|forgery)__' | sed 's/__.*//' | sort -u | wc -l | tr -d ' '; }
waitslot() {
  local n=0
  while [ $(others) -gt 1 ] && [ $n -lt 30 ]; do sleep 60; n=$((n+1)); done
  echo "slot others=$(others) waited=${n}m $(date)" >> chain.log
}
waitslot
echo "START warm $(date)" >> chain.log
(cd $D/plain/tests && docker build --progress plain -t warm-schema-migration-plan-repair . > $D/logs/warm_tests.log 2>&1)
(cd $D/plain/environment && docker build --progress plain -t warm-schema-migration-plan-repair-agent . > $D/logs/warm_environment.log 2>&1)
echo "DONE warm rc=$? $(date)" >> chain.log
step() {
  local name=$1 copy=$2 agent=$3
  waitslot
  echo "START $name $(date)" >> chain.log
  yes | perl -e 'alarm shift; exec @ARGV' 4000 harbor run --path $copy --agent $agent --env docker --job-name $name -o $D/jobs -y > logs/$name.log 2>&1
  echo "DONE $name rc=$? $(date)" >> chain.log
}
step oracle-1 $D/plain oracle & sleep 20; step oracle-2 $D/plain oracle; wait
step oracle-3 $D/plain oracle & sleep 20; step owner-1 $D/owner oracle; wait
step nop-1 $D/plain nop & sleep 20; step stub-1 $D/stub oracle; wait
step forgery-1 $D/forgery oracle
rm -f $L
echo ALL_DONE $(date) >> chain.log
