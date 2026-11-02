#!/bin/zsh
# P12 v13 tests-only Harbor gates on exe_copy copies; two runs at a time; agents oracle and nop only.
D=$1
cd $D
export OPENAI_API_KEY=unused
others() { docker ps --format '{{.Names}}' | grep -v -E '^smpr13' | grep -v -E '^warm' | sed 's/__.*//' | sort -u | wc -l | tr -d ' '; }
waitslot() {
  local n=0
  while [ $(others) -gt 2 ] && [ $n -lt 30 ]; do sleep 60; n=$((n+1)); done
  echo "slot others=$(others) waited=${n}m $(date)" >> chain.log
}
waitslot
echo "START warm $(date)" >> chain.log
(cd $D/smpr13plain/tests && docker build --progress plain -t warm-schema-migration-plan-repair . > $D/logs/warm_tests.log 2>&1)
(cd $D/smpr13plain/environment && docker build --progress plain -t warm-schema-migration-plan-repair-agent . > $D/logs/warm_environment.log 2>&1)
echo "DONE warm rc=$? $(date)" >> chain.log
oracle_step() {
  local name=$1 copy=$2
  waitslot
  echo "START $name $(date)" >> chain.log
  yes | perl -e 'alarm shift; exec @ARGV' 4000 harbor run --path $copy --agent oracle --env docker --job-name $name -o $D/jobs -y > logs/$name.log 2>&1
  echo "DONE $name rc=$? $(date)" >> chain.log
}
nop_step() {
  local name=$1 copy=$2
  waitslot
  echo "START $name $(date)" >> chain.log
  yes | perl -e 'alarm shift; exec @ARGV' 4000 harbor run --path $copy --agent nop --env docker --job-name $name -o $D/jobs -y > logs/$name.log 2>&1
  echo "DONE $name rc=$? $(date)" >> chain.log
}
oracle_step oracle-1 $D/smpr13plain & sleep 20; oracle_step oracle-2 $D/smpr13plain; wait
oracle_step oracle-3 $D/smpr13plain & sleep 20; oracle_step owner-1 $D/smpr13owner; wait
nop_step nop-1 $D/smpr13plain
echo ALL_DONE $(date) >> chain.log
