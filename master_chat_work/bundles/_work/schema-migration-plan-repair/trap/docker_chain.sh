#!/bin/zsh
set -e
D="$(cat "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/schema-migration-plan-repair/trap/docker_dir.txt")"
mkdir -p "$D/jobs"
for n in 1 2 3; do
  echo "START oracle-$n $(date)"
  harbor run --path "$D/plain" --agent oracle --env docker --job-name "oracle-$n" -y -o "$D/jobs" > "$D/oracle-$n.log" 2>&1
  echo "DONE oracle-$n rc=0 $(date)"
done
echo "START owner-1 $(date)"
harbor run --path "$D/owner" --agent oracle --env docker --job-name owner-1 -y -o "$D/jobs" > "$D/owner-1.log" 2>&1
echo "DONE owner-1 rc=0 $(date)"
echo "START nop-1 $(date)"
harbor run --path "$D/plain" --agent nop --env docker --job-name nop-1 -y -o "$D/jobs" > "$D/nop-1.log" 2>&1
echo "DONE nop-1 rc=0 $(date)"
echo ALL_DONE
