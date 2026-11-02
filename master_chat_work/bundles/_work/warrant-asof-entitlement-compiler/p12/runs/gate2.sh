#!/bin/bash
# P12 4989b35 gate block: tests-only Harbor runs from kit exe_copy.py copies.
# oracle x3, owner-only x1, nop x1; two lanes, so at most two runs at once.
# Starts the Harbor runs only after the s3 scoring chain printed ALL_DONE.
set -u
export OPENAI_API_KEY=unused
export PYTHONDONTWRITEBYTECODE=1
export PATH="/Users/mac/.local/bin:$PATH"
SLUG=warrant-asof-entitlement-compiler
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/$SLUG"
KIT="/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC"
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/$SLUG"
TS=$(date +%Y%m%dT%H%M%S)-$(openssl rand -hex 2)
G=/tmp/wae4989b35_gate_$TS
LOG="$W/p12/runs/gate2.log"
mkdir -p "$G/logs" "$G/jobs"
echo "TS $TS G $G $(date +%H:%M:%S)" > "$LOG"
python3 -B "$KIT/exe_copy.py" "$B" "$G/plain/$SLUG" >> "$LOG" 2>&1
echo "exe_copy plain rc=$?" >> "$LOG"
python3 -B "$KIT/exe_copy.py" "$B" "$G/owner/$SLUG" --owner-only >> "$LOG" 2>&1
echo "exe_copy owner rc=$?" >> "$LOG"
echo "START warm $(date +%H:%M:%S)" >> "$LOG"
(cd "$G/plain/$SLUG/tests" && docker build --progress plain -t "warm-$SLUG" . > "$G/logs/warm_tests.log" 2>&1)
echo "DONE warm tests rc=$? $(date +%H:%M:%S)" >> "$LOG"
(cd "$G/plain/$SLUG/environment" && docker build --progress plain -t "warm-$SLUG-agent" . > "$G/logs/warm_environment.log" 2>&1)
echo "DONE warm environment rc=$? $(date +%H:%M:%S)" >> "$LOG"
n=0
until grep -q ALL_DONE "$W/p12/runs/s3.log" 2>/dev/null; do sleep 60; n=$((n+1)); done
echo "s3 done after ${n}m wait $(date +%H:%M:%S)" >> "$LOG"
reward() {
  local name=$1 rc=$2 t0=$3 r
  r=$(find "$G/jobs/$name" -path '*verifier*' -name reward.json 2>/dev/null | head -1)
  echo "REWARD $name rc=$rc $(tr -d '\n ' < "$r" 2>/dev/null) wall=$(( $(date +%s) - t0 ))s $(date +%H:%M:%S)" >> "$LOG"
}
run() {
  local name=$1 agent=$2 copy=$3 t0
  echo "START $name $(date +%H:%M:%S)" >> "$LOG"
  t0=$(date +%s)
  yes | perl -e 'alarm shift; exec @ARGV' 10800 harbor run --path "$copy" --agent "$agent" --env docker --job-name "$name-$TS" --jobs-dir "$G/jobs" -y > "$G/logs/$name.log" 2>&1
  reward "$name-$TS" $? "$t0"
}
lane_a() {
  run oracle-1 oracle "$G/plain/$SLUG"
  run oracle-3 oracle "$G/plain/$SLUG"
  run nop-1 nop "$G/plain/$SLUG"
}
lane_b() {
  sleep 30
  run oracle-2 oracle "$G/plain/$SLUG"
  run owner-1 oracle "$G/owner/$SLUG"
}
lane_a &
lane_b &
wait
echo "ALL_DONE $(date +%H:%M:%S)" >> "$LOG"
