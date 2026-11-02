#!/bin/bash
# P12 v3 (b0aca9b) gate block: oracle x3, owner-only x1, nop x1 from exe_copy.py copies (made earlier in $G).
set -u
export OPENAI_API_KEY=unused
export PYTHONDONTWRITEBYTECODE=1
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"
G=/tmp/ccq_v3_gate_20261028T155638-6577
LOG="$W/runs/v3_chain.log"
: > "$LOG"
find "$G" -name __pycache__ -prune -exec rm -rf {} +
run() {
  local label="$1" path="$2" agent="$3"
  echo "=== $label start $(date +%H:%M:%S)" >> "$LOG"
  yes | perl -e 'alarm 1500; exec @ARGV' harbor run -p "$path" -a "$agent" --env docker --job-name "$label" -o "$G/jobs_$label" -y > "$W/runs/v3_gate_$label.log" 2>&1
  echo "rc $label $?" >> "$LOG"
  for r in $(find "$G/jobs_$label" -name result.json -path '*__*' | sort); do
    echo "RESULT $label $r" >> "$LOG"
    python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('REWARD', sys.argv[2], (d.get('verifier_result') or {}).get('rewards'), 'exc', d.get('exception_info') and str(d.get('exception_info'))[:200])" "$r" "$label" >> "$LOG" 2>&1
  done
  echo "=== $label end $(date +%H:%M:%S)" >> "$LOG"
}
run oracle-1 "$G/main" oracle
run oracle-2 "$G/main" oracle
run oracle-3 "$G/main" oracle
run owner-1 "$G/owner" oracle
run nop-1 "$G/main" nop
find "$G" -name __pycache__ -prune -exec rm -rf {} +
echo ALL_DONE >> "$LOG"
rm -f /tmp/opencode-logs/locks/cold-chain-backbone-quote.lock
