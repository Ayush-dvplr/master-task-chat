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
echo "######## SETUP_STEPS step 1 (planning clone; the GitHub URL is mapped to the simulated planning repo)"
PLANURL="$E2/plan_origin.git"
rm -rf "$E2/Desktop/mc2_upgrade" "$E2/Desktop/mc2_root" "$E2/Desktop/mc2_backup" "$E2/Desktop/mc2_worktree"
git clone -q -b claude/youthful-feynman-zug0uq "$PLANURL" "$E2/Desktop/mc2_upgrade"; echo "    [exit $?]"
for k in 1 2 3 4 5 6 7.3 7.4 7.5 8 9; do step $k; done
echo "(mapping only: settings.local.json also gets the mapped old_root, standing in for /Users/mac/Desktop/Terminal Bench)"
python3 - "$ROOT/master_chat_tasks/settings.local.json" "$OLD" <<'PY'
import json,sys; p,old=sys.argv[1:]; d=json.load(open(p)); d["upgrade"]["old_root"]=old; json.dump(d,open(p,"w"),indent=2)
PY
n=0
while [ $n -lt 10 ]; do
  n=$((n+1))
  step 10.1 | tee "$E2/logs/loop_$n.txt"
  if grep -q "^UP TO DATE" "$E2/logs/loop_$n.txt"; then echo "==== loop ends: UP TO DATE"; break; fi
  grep -q "^VERDICT: READY" "$E2/logs/loop_$n.txt" || { echo "==== NOT READY, stop"; break; }
  paste_block "$E2/logs/loop_$n.txt" "^VERDICT: READY" | tee "$E2/logs/loop_${n}_paste.txt"
  v=$(sed -n 's/^version = //p' "$ROOT/SYSTEM_VERSION")
  echo "==== now at $v; recheck verdict: $(grep -E '^(VERDICT|ROLLBACK DONE)' "$E2/logs/loop_${n}_paste.txt" | head -1)"
  if [ "$v" = v2.3 ]; then step 10.4; fi
done
echo "TRAILING COMMENTS SEEN: $(cat "$E2"/logs/loop_*_paste.txt 2>/dev/null | grep -c "TRAILING COMMENT")"
