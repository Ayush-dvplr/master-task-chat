#!/bin/bash
# P12 d872b22 gate: tests-only Harbor runs from kit exe_copy.py copies: oracle x3, owner-only x1, nop x1; two lanes.
set -u
export OPENAI_API_KEY=unused
export PYTHONDONTWRITEBYTECODE=1
export PATH="/Users/mac/.local/bin:$PATH"
SLUG=warrant-asof-entitlement-compiler
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/$SLUG"
KIT="/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC"
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/$SLUG"
TS=$(date +%Y%m%dT%H%M%S)-$(openssl rand -hex 2)
G=/tmp/wae_d872b22_gate_$TS
LOG="$W/p12v2/gate.log"
L=/tmp/opencode-logs/locks/$SLUG.lock
mkdir -p /tmp/opencode-logs/locks "$L"
echo "d872b22 P12v2 gate $TS $$" > "$L/owner"
mkdir -p "$G/logs" "$G/jobs"
echo "TS $TS G $G $(date +%H:%M:%S)" > "$LOG"
python3 -B "$KIT/exe_copy.py" "$B" "$G/plain/$SLUG" >> "$LOG" 2>&1
python3 -B "$KIT/exe_copy.py" "$B" "$G/owner/$SLUG" --owner-only >> "$LOG" 2>&1
find "$G" -name __pycache__ -prune -exec rm -rf {} +
reward() {
  local name=$1 rc=$2 t0=$3 r
  r=$(find "$G/jobs/$name" -path '*verifier*' -name reward.json 2>/dev/null | head -1)
  echo "REWARD $name rc=$rc $(tr -d '\n ' < "$r" 2>/dev/null) wall=$(( $(date +%s) - t0 ))s $(date +%H:%M:%S)" >> "$LOG"
}
run() {
  local name=$1 copy=$2 agent=$3 t0
  echo "START $name $(date +%H:%M:%S)" >> "$LOG"
  t0=$(date +%s)
  yes | perl -e 'alarm shift; exec @ARGV' 10800 harbor run --path "$copy" --agent "$agent" --env docker --job-name "$name-$TS" --jobs-dir "$G/jobs" -y > "$G/logs/$name.log" 2>&1
  reward "$name-$TS" $? "$t0"
}
echo "START warm $(date +%H:%M:%S)" >> "$LOG"
(cd "$G/plain/$SLUG/tests" && docker build --progress plain -t "warm-$SLUG" . > "$G/logs/warm_tests.log" 2>&1)
echo "DONE warm tests rc=$? $(date +%H:%M:%S)" >> "$LOG"
(cd "$G/plain/$SLUG/environment" && docker build --progress plain -t "warm-$SLUG-agent" . > "$G/logs/warm_environment.log" 2>&1)
echo "DONE warm environment rc=$? $(date +%H:%M:%S)" >> "$LOG"
lane_a() { run oracle-1 "$G/plain/$SLUG" oracle; run oracle-3 "$G/plain/$SLUG" oracle; run nop-1 "$G/plain/$SLUG" nop; }
lane_b() { sleep 30; run oracle-2 "$G/plain/$SLUG" oracle; run owner-1 "$G/owner/$SLUG" oracle; }
lane_a &
lane_b &
wait
find "$G" -name __pycache__ -prune -exec rm -rf {} +
rm -rf "$L"
echo "ALL_DONE $(date +%H:%M:%S)" >> "$LOG"
