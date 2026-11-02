#!/bin/bash
# P12 d872b22 gate lane: lane.sh <n> <G> <TS> <name:copy:agent>... ; tests-only Harbor runs from exe_copy.py copies.
set -u
export OPENAI_API_KEY=unused PYTHONDONTWRITEBYTECODE=1 PATH="/Users/mac/.local/bin:$PATH"
SLUG=warrant-asof-entitlement-compiler
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/$SLUG"
N=$1; G=$2; TS=$3; shift 3
LOG="$W/p12v2/gate_lane$N.log"
echo "LANE$N TS $TS G $G $(date +%H:%M:%S)" > "$LOG"
for spec in "$@"; do
  name=${spec%%:*}; rest=${spec#*:}; copy=${rest%%:*}; agent=${rest#*:}
  n=0; while [ "$(sysctl -n vm.swapusage | awk '{print int($6)}')" -gt 2048 ] && [ $n -lt 10 ]; do sleep 60; n=$((n+1)); done
  [ $n -gt 0 ] && echo "swap wait ${n}m" >> "$LOG"
  echo "START $name $(date +%H:%M:%S)" >> "$LOG"; t0=$(date +%s)
  yes | perl -e 'alarm shift; exec @ARGV' 10800 harbor run --path "$G/$copy/$SLUG" --agent "$agent" --env docker --job-name "$name-$TS" --jobs-dir "$G/jobs" -y > "$G/logs/$name.log" 2>&1
  rc=$?; r=$(find "$G/jobs/$name-$TS" -path '*verifier*' -name reward.json 2>/dev/null | head -1)
  echo "REWARD $name rc=$rc $(tr -d '\n ' < "$r" 2>/dev/null) wall=$(( $(date +%s) - t0 ))s $(date +%H:%M:%S)" >> "$LOG"
done
echo "LANE${N}_DONE $(date +%H:%M:%S)" >> "$LOG"
