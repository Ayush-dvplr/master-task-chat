#!/usr/bin/env bash
set -eu
export OPENAI_API_KEY=unused
S="/Users/mac/Desktop/Terminal Bench/_runs/20261102/hangar-check-replan/fix3-20261102T235955"
trap 'rc=$?; printf "EXIT=%s\nALL_DONE\n" "$rc"' EXIT
lane() {
  name="$1"; copy="$2"; agent="$3"
  for i in $(seq 180); do
    python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2 | tee "$S/dockfree-$name.log"
    if grep -q 'START=yes' "$S/dockfree-$name.log"; then break; fi
    sleep 20
  done
  grep -q 'START=yes' "$S/dockfree-$name.log"
  printf 'LANE %s START %s\n' "$name" "$(date +%H:%M:%S)"
  set +e
  yes | perl -e 'alarm 4200; exec @ARGV' harbor run -p "$S/$copy" -a "$agent" -k 1 -n 1 -o "$S/jobs" --job-name "$name" -q -y > "$S/$name.log" 2>&1
  rc=$?
  set -e
  printf 'LANE %s EXIT=%s END %s\n' "$name" "$rc" "$(date +%H:%M:%S)"
  test "$rc" -eq 0
}
lane oracle-1 plain oracle
lane oracle-2 plain oracle
lane oracle-3 plain oracle
lane owner owner oracle
lane nop plain nop
lane stub stub oracle
lane forgery forgery oracle
lane a1 a1 oracle
