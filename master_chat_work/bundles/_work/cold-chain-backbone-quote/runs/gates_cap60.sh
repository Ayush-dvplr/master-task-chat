#!/bin/bash
# Cap-60 gate block (board b223662): oracle x3, nop, owner-only, stub, forgery from exe_copy.py copies.
set -u
export OPENAI_API_KEY=unused
export PYTHONDONTWRITEBYTECODE=1
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote"
KIT="/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC"
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"
G="/tmp/ccq_gate_$(date +%Y%m%dT%H%M%S)-$(openssl rand -hex 2)"
LOG="$W/runs/gates_cap60.log"
: > "$LOG"
echo "gate dir $G" >> "$LOG"
while ! grep -q ALL_DONE "$W/runs/cap60_c5.log" 2>/dev/null; do sleep 30; done
echo "start $(date)" >> "$LOG"
mkdir -p "$G"
python3 -B "$KIT/exe_copy.py" "$B" "$G/main/cold-chain-backbone-quote" >> "$LOG" 2>&1
python3 -B "$KIT/exe_copy.py" "$B" "$G/owner/cold-chain-backbone-quote" --owner-only >> "$LOG" 2>&1
python3 -B "$KIT/exe_copy.py" "$B" "$G/stub/cold-chain-backbone-quote" --stub >> "$LOG" 2>&1
cp -Rp "$G/main" "$G/forgery"
cat > "$G/forgery/cold-chain-backbone-quote/solution/solve.sh" <<'EOF'
#!/bin/bash
set -euo pipefail
rm -rf /tmp/shipped && cp -Rp /app/repo /tmp/shipped
python3 "${SOLUTION_ROOT:-/solution}/solve.py"
python3 - <<'PY'
import os, zipfile
root = "/tmp/shipped"
names = []
for d, _, fs in os.walk(root):
    for f in fs:
        names.append(os.path.relpath(os.path.join(d, f), root))
with zipfile.ZipFile("/app/out/patched-repo.zip", "w", zipfile.ZIP_STORED) as z:
    for n in sorted(names):
        z.write(os.path.join(root, n), n)
PY
EOF
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
run stub "$G/stub/cold-chain-backbone-quote" oracle
run forgery "$G/forgery/cold-chain-backbone-quote" oracle
find "$G" -name __pycache__ -prune -exec rm -rf {} +
echo "end $(date)" >> "$LOG"
echo ALL_DONE >> "$LOG"
