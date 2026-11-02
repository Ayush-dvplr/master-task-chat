#!/bin/bash
# P12 4989b35 final gate block on the final BUNDLE: tests-only Harbor runs from kit exe_copy.py copies.
# oracle x3, owner-only x1, nop x1, stub x1, forgery x1; two lanes, so at most two runs at once.
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
LOG="$W/p12/runs/gate4.log"
mkdir -p "$G/logs" "$G/jobs"
echo "TS $TS G $G $(date +%H:%M:%S)" > "$LOG"
python3 -B "$KIT/exe_copy.py" "$B" "$G/plain/$SLUG" >> "$LOG" 2>&1
echo "exe_copy plain rc=$?" >> "$LOG"
python3 -B "$KIT/exe_copy.py" "$B" "$G/owner/$SLUG" --owner-only >> "$LOG" 2>&1
echo "exe_copy owner rc=$?" >> "$LOG"
python3 -B "$KIT/exe_copy.py" "$B" "$G/stub/$SLUG" --stub >> "$LOG" 2>&1
echo "exe_copy stub rc=$?" >> "$LOG"
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
run() {
  local name=$1 agent=$2 copy=$3 t0
  waitswap
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
lane_a() {
  run oracle-1 oracle "$G/plain/$SLUG"
  run oracle-3 oracle "$G/plain/$SLUG"
  run forgery-1 oracle "$G/forgery/$SLUG"
  run stub-1 oracle "$G/stub/$SLUG"
}
lane_b() {
  sleep 30
  run oracle-2 oracle "$G/plain/$SLUG"
  run owner-1 oracle "$G/owner/$SLUG"
  run nop-1 nop "$G/plain/$SLUG"
}
lane_a &
lane_b &
wait
find "$G" -name __pycache__ -prune -exec rm -rf {} +
echo "ALL_DONE $(date +%H:%M:%S)" >> "$LOG"
