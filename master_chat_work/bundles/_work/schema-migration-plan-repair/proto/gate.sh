#!/bin/bash
# Phase 3 gate block: tests-only copies from the live kit's exe_copy.py.
# usage: gate.sh DIR   (DIR already holds plain/ owner/ stub/ forgery/ copies)
D=$1
export OPENAI_API_KEY=unused
cd "$D"
mkdir -p "$D/logs" "$D/jobs"
L=/tmp/opencode-logs/locks/schema-migration-plan-repair.lock
echo "gate $(date) $$" > $L
echo "START warm $(date)" >> "$D/chain.log"
(cd "$D/plain/tests" && docker build --progress plain -t warm-schema-migration-plan-repair . > "$D/logs/warm_tests.log" 2>&1)
(cd "$D/plain/environment" && docker build --progress plain -t warm-schema-migration-plan-repair-agent . > "$D/logs/warm_environment.log" 2>&1)
echo "DONE warm rc=$? $(date)" >> "$D/chain.log"
run() { name=$1; path=$2; agent=$3
  echo "START $name $(date)" >> "$D/chain.log"
  yes | harbor run --path "$path" --agent "$agent" --env docker --job-name "$name" --jobs-dir "$D/jobs" -y > "$D/logs/$name.log" 2>&1
  echo "DONE $name rc=$? $(date)" >> "$D/chain.log"; }
run oracle-1 "$D/plain" oracle
run oracle-2 "$D/plain" oracle
run oracle-3 "$D/plain" oracle
run owner-1 "$D/owner" oracle
run nop-1 "$D/plain" nop
run stub-1 "$D/stub" oracle
run forgery-1 "$D/forgery" oracle
rm -f $L
echo ALL_DONE >> "$D/chain.log"
