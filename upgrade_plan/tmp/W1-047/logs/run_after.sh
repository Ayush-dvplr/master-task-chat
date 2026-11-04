#!/bin/bash
# run_install.sh: follow the INSTALL guide literally in E2 (bash stands in for zsh, which is not installed here).
# Guide command lines run with eval in this one shell (variables persist); printed blocks are pasted the same way
# after a comment check (a # must start the line). Every command and its exit code go to the log.
S=/tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad; E2="$S/e2e2"
G="$E2/Desktop/mc2_upgrade/upgrade_plan/delivery/README.md"
export PATH="$E2/bin:$PATH"
TRAILING=0
step() {  # step KEY: run the guide's commands of that step
  echo; echo "######## GUIDE STEP $1"
  while IFS= read -r c; do
    [ -z "$c" ] && continue
    echo "\$ $c"; eval "$c"; echo "    [exit $?]"
  done < <(python3 "$E2/guide_cmds.py" "$G" "$1")
}
paste_block() {  # paste_block FILE MARKER: paste the two space indented lines printed after MARKER
  echo "---- pasting the printed block after: $2"
  local blk; blk=$(sed -n "/$2/,\$p" "$1" | tail -n +2 | sed '/^    \[exit/,$d' | grep '^  ' | sed 's/^  //')
  while IFS= read -r c; do
    [ -z "$c" ] && continue
    case "$c" in \#*) ;; *\#*) echo "!!!! TRAILING COMMENT: $c"; TRAILING=$((TRAILING+1));; esac
    echo "\$ $c"; eval "$c"; echo "    [exit $?]"
  done <<< "$blk"
}
echo "######## a new Terminal window: step 1 again"
step 1
step 12.1 | tee "$E2/logs/after_cold.txt"
paste_block "$E2/logs/after_cold.txt" "^VERDICT: UPGRADE GOOD"
echo "==== mc2-stable now: $(git -C "$ROOT" rev-parse --short=8 mc2-stable), mc2-v2.5.1 is $(git -C "$ROOT" rev-parse --short=8 mc2-v2.5.1)"
step 13 | tee "$E2/logs/after_rollback.txt"
paste_block "$E2/logs/after_rollback.txt" "^ROLLBACK mc2" | tee "$E2/logs/after_rollback_paste.txt"
echo "==== after rollback: $(sed -n 's/^version = //p' "$ROOT/SYSTEM_VERSION")"
echo "==== forward again"
step 10.1 | tee "$E2/logs/after_fwd.txt"
paste_block "$E2/logs/after_fwd.txt" "^VERDICT: READY" | tee "$E2/logs/after_fwd_paste.txt"
echo "==== now: $(sed -n 's/^version = //p' "$ROOT/SYSTEM_VERSION")"
step 12.3
rm -rf "$E2/github.git"; git init -q --bare "$E2/github.git"
step 14
echo "==== refs on the simulated GitHub:"; git -C "$E2/github.git" for-each-ref --format='%(refname)'
echo "==== git status in ROOT (must be empty):"; git -C "$ROOT" status --porcelain; echo "[end status]"
echo "TRAILING COMMENTS SEEN: $(cat "$E2"/logs/after_*paste*.txt 2>/dev/null | grep -c "TRAILING COMMENT")"
