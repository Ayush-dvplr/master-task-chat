#!/bin/bash
# Phase 3 gate block (step harden-g37-a1-opt1-build): tests-only Harbor runs from kit exe_copy.py copies.
# oracle x3, owner-only, nop, stub, forgery; two lanes, so at most two runs at once.
set -u
export OPENAI_API_KEY=unused
export PYTHONDONTWRITEBYTECODE=1
export PATH="/Users/mac/.local/bin:$PATH"
SLUG=warrant-asof-entitlement-compiler
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/$SLUG"
KIT="/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC"
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/$SLUG"
G=/tmp/wae6740572_gate
LOG="$W/gate/chain.log"
L=/tmp/opencode-logs/locks/$SLUG.lock
mkdir -p /tmp/opencode-logs/locks
echo "6740572 harden-g37-a1-opt1-build $(date) $$" > "$L"
rm -rf "$G"; mkdir -p "$G/logs" "$G/jobs"
: > "$LOG"
python3 -B "$KIT/exe_copy.py" "$B" "$G/plain/$SLUG" >> "$LOG" 2>&1
python3 -B "$KIT/exe_copy.py" "$B" "$G/owner/$SLUG" --owner-only >> "$LOG" 2>&1
python3 -B "$KIT/exe_copy.py" "$B" "$G/stub/$SLUG" --stub >> "$LOG" 2>&1
cp -Rp "$G/plain" "$G/forgery"
cat > "$G/forgery/$SLUG/solution/solve.sh" <<'EOF'
#!/bin/bash
# Forgery: artifacts from the repaired compiler, then the unrepaired shipped tool delivered in its place.
set -euo pipefail
python3 /solution/solve.py
cp /app/data/tool.zip /app/out/tool.zip
EOF
find "$G" -name __pycache__ -prune -exec rm -rf {} +
waitswap() {
  local n=0
  while [ "$(sysctl -n vm.swapusage | awk '{print int($6)}')" -gt 20480 ] && [ $n -lt 30 ]; do sleep 60; n=$((n+1)); done
  [ $n -gt 0 ] && echo "swap wait ${n}m $(date +%H:%M:%S)" >> "$LOG"
  return 0
}
reward() {
  local name=$1 rc=$2 t0=$3 r
  r=$(find "$G/jobs/$name" -path '*verifier*' -name reward.json 2>/dev/null | head -1)
  echo "REWARD $name rc=$rc $(tr -d '\n ' < "$r" 2>/dev/null) wall=$(( $(date +%s) - t0 ))s $(date +%H:%M:%S)" >> "$LOG"
}
oracle_run() {
  local name=$1 copy=$2 t0
  waitswap
  echo "START $name $(date +%H:%M:%S)" >> "$LOG"
  t0=$(date +%s)
  yes | perl -e 'alarm shift; exec @ARGV' 10800 harbor run --path "$copy" --agent oracle --env docker --job-name "$name" --jobs-dir "$G/jobs" -y > "$G/logs/$name.log" 2>&1
  reward "$name" $? "$t0"
}
nop_run() {
  local name=$1 copy=$2 t0
  waitswap
  echo "START $name $(date +%H:%M:%S)" >> "$LOG"
  t0=$(date +%s)
  yes | perl -e 'alarm shift; exec @ARGV' 10800 harbor run --path "$copy" --agent nop --env docker --job-name "$name" --jobs-dir "$G/jobs" -y > "$G/logs/$name.log" 2>&1
  reward "$name" $? "$t0"
}
echo "START warm $(date +%H:%M:%S)" >> "$LOG"
(cd "$G/plain/$SLUG/tests" && docker build --progress plain -t "warm-$SLUG" . > "$G/logs/warm_tests.log" 2>&1)
echo "DONE warm tests rc=$? $(date +%H:%M:%S)" >> "$LOG"
(cd "$G/plain/$SLUG/environment" && docker build --progress plain -t "warm-$SLUG-agent" . > "$G/logs/warm_environment.log" 2>&1)
echo "DONE warm environment rc=$? $(date +%H:%M:%S)" >> "$LOG"
lane_a() {
  oracle_run oracle-1 "$G/plain/$SLUG"
  oracle_run oracle-3 "$G/plain/$SLUG"
  oracle_run forgery-1 "$G/forgery/$SLUG"
}
lane_b() {
  sleep 30
  oracle_run oracle-2 "$G/plain/$SLUG"
  oracle_run owner-1 "$G/owner/$SLUG"
  nop_run nop-1 "$G/plain/$SLUG"
  oracle_run stub-1 "$G/stub/$SLUG"
}
lane_a &
lane_b &
wait
find "$G" -name __pycache__ -prune -exec rm -rf {} +
rm -f "$L"
echo "ALL_DONE $(date +%H:%M:%S)" >> "$LOG"
