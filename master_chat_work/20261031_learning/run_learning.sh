#!/bin/bash
# Night learning run: L1-L6 at most 3 at a time, then L7. Codex main-chat only (multi_agent disabled).
BASE="/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_learning"
CODEX="$HOME/.local/bin/codex"
run_one() {
  name="$1"; out="$BASE/$name"; mkdir -p "$out/scripts"
  search=""; [ "$name" = "L6_web_ideas" ] && search="--search"
  prompt="$(cat "$BASE/prompts/COMMON.md")

---

$(cat "$BASE/prompts/$name.md")"
  echo "START $(date '+%H:%M:%S')" > "$out/status.txt"
  "$CODEX" $search exec -s workspace-write -C "$out" --skip-git-repo-check \
    --disable multi_agent -c model_reasoning_effort=high -o "$out/last.txt" "$prompt" \
    < /dev/null > "$out/codex.log" 2>&1
  echo "END $(date '+%H:%M:%S') rc=$?" >> "$out/status.txt"
}
for name in L1_qc_fixes L2_qc_kit_map L3_auto_problems L4_docker L5_stage2_study L6_web_ideas; do
  while [ "$(jobs -rp | wc -l)" -ge 3 ]; do sleep 30; done
  run_one "$name" &
  sleep 5
done
wait
run_one L7_synthesis
echo "ALL_DONE $(date '+%H:%M:%S')" > "$BASE/ALL_DONE.txt"
