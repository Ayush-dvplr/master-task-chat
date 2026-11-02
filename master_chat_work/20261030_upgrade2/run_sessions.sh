#!/bin/zsh
# Runs Upgrade-2 research sessions with codex exec, at most 4 at a time.
# Usage: run_sessions.sh S1_memory S2_folders ...   (names = prompt file stems)
# Each session: prompt = COMMON.md + <name>.md; cwd/writable = OUT (<name>/); log OUT/codex.log; last message OUT/last.txt
BASE="/Users/mac/Desktop/Terminal Bench/master_chat_work/20261030_upgrade2"
CODEX="$HOME/.local/bin/codex"

run_one() {
  local name="$1"
  local out="$BASE/$name"
  mkdir -p "$out/scripts"
  local prompt="$(cat "$BASE/prompts/COMMON.md")

---

$(cat "$BASE/prompts/$name.md")"
  echo "START $(date '+%H:%M:%S')" > "$out/status.txt"
  "$CODEX" exec -s workspace-write -C "$out" --skip-git-repo-check \
    -c model_reasoning_effort=high -o "$out/last.txt" "$prompt" \
    < /dev/null > "$out/codex.log" 2>&1
  echo "END $(date '+%H:%M:%S') rc=$?" >> "$out/status.txt"
}

running=0
for name in "$@"; do
  run_one "$name" &
  running=$((running + 1))
  if [ $running -ge 4 ]; then
    wait -n 2>/dev/null || wait
    running=$((running - 1))
  fi
  sleep 5
done
wait
echo "ALL_DONE $(date '+%H:%M:%S')" > "$BASE/ALL_DONE.txt"
