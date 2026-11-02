#!/bin/bash
# P12 gate block: oracle x3, nop, owner-only from exe_copy.py copies.
set -u
export OPENAI_API_KEY=unused
export PYTHONDONTWRITEBYTECODE=1
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote"
KIT="/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC"
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"
G=/tmp/ccq_p12_gate_20261028T041718-d097
LOG="$W/runs/p12_gates.log"
rm -rf "$G"; mkdir -p "$G"
: > "$LOG"
python3 -B "$KIT/exe_copy.py" "$B" "$G/main/cold-chain-backbone-quote" >> "$LOG" 2>&1
python3 -B "$KIT/exe_copy.py" "$B" "$G/owner/cold-chain-backbone-quote" --owner-only >> "$LOG" 2>&1
find "$G" -name __pycache__ -prune -exec rm -rf {} +
run() {
  local label="$1" path="$2" agent="$3"
  echo "=== $label $(date +%H:%M:%S)" >> "$LOG"
  yes | harbor run -p "$path" -a "$agent" -o "$G/jobs_$label" -y >> "$LOG" 2>&1
  local r
  r=$(find "$G/jobs_$label" -path '*verifier*' -name reward.json | head -1)
  echo "REWARD $label $(cat "$r" 2>/dev/null | tr -d '\n ')" >> "$LOG"
}
run oracle_1 "$G/main/cold-chain-backbone-quote" oracle
run oracle_2 "$G/main/cold-chain-backbone-quote" oracle
run oracle_3 "$G/main/cold-chain-backbone-quote" oracle
run nop "$G/main/cold-chain-backbone-quote" nop
run owner "$G/owner/cold-chain-backbone-quote" oracle
find "$G" -name __pycache__ -prune -exec rm -rf {} +
echo ALL_DONE >> "$LOG"
rm -f /tmp/opencode-logs/locks/cold-chain-backbone-quote.lock
