#!/bin/bash
# Supervisor for the night learning run (Ayush 31 Oct ~01:35: 2 tries, stuck = 30 min no log growth,
# usage limit -> wait and resume (not a try), L7 only after L1-L6 are DONE or FAILED, let it finish).
# No AI here. Checks every 10 min. Log: supervisor.log
BASE="/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_learning"
CODEX="$HOME/.local/bin/codex"
LOG="$BASE/supervisor.log"
MAIN="L1_qc_fixes L2_qc_kit_map L3_auto_problems L4_docker L5_stage2_study L6_web_ideas"
MAXPAR=3; MAXTRIES=2; STUCK_S=1800; LIMIT_WAIT_S=1800

log() { echo "$(date '+%H:%M:%S') $*" >> "$LOG"; }
out_of() { echo "$BASE/$1"; }
search_flag() { [ "$1" = "L6_web_ideas" ] && echo "--search"; }

is_done() {  # result.json parses with status DONE/PARTIAL and FINDINGS.md (or LEARNING_REPORT.md for L7) exists
  local o; o=$(out_of "$1")
  python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d.get('status') in ('DONE','PARTIAL') else 1)" "$o/result.json" 2>/dev/null || return 1
  [ -f "$o/FINDINGS.md" ] || [ -f "$o/LEARNING_REPORT.md" ]
}
is_alive() {
  local o pid; o=$(out_of "$1")
  pid=$(cat "$o/sup.pid" 2>/dev/null); [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && return 0
  pgrep -f -- "-C $o" >/dev/null 2>&1
}
tries() { cat "$(out_of "$1")/sup_tries" 2>/dev/null || echo 0; }
started() { [ -f "$(out_of "$1")/status.txt" ]; }
newest_log_age() {  # seconds since any codex*.log in OUT last grew
  local o m; o=$(out_of "$1"); m=$(stat -f %m "$o"/codex*.log 2>/dev/null | sort -n | tail -1)
  [ -z "$m" ] && echo 0 || echo $(( $(date +%s) - m ))
}
hit_limit() { tail -c 4000 "$(out_of "$1")"/codex*.log 2>/dev/null | grep -qi -E "usage limit|rate limit|hit your limit|try again (at|in)|quota"; }

prompt_text() { cat "$BASE/prompts/COMMON.md"; printf "\n\n---\n\n"; cat "$BASE/prompts/$1.md"; }

launch_fresh() {  # $1 name, $2 note (optional, for a restart on partial files)
  local n=$1 o; o=$(out_of "$n"); mkdir -p "$o/scripts"
  local p; p="$(prompt_text "$n")"; [ -n "$2" ] && p="$p

NOTE (supervisor): $2"
  echo "START $(date '+%H:%M:%S') (supervisor)" >> "$o/status.txt"
  ( "$CODEX" $(search_flag "$n") exec -s workspace-write -C "$o" --skip-git-repo-check --disable multi_agent \
      -c model_reasoning_effort=high -o "$o/last.txt" "$p" < /dev/null >> "$o/codex.log" 2>&1
    echo "END $(date '+%H:%M:%S') rc=$?" >> "$o/status.txt" ) &
  echo $! > "$o/sup.pid"; log "launch $n fresh${2:+ (restart)}"
}
launch_resume() {  # resume the same Codex conversation in OUT
  local n=$1 o sid k; o=$(out_of "$n")
  sid=$(grep -m1 "session id:" "$o/codex.log" 2>/dev/null | awk '{print $3}')
  if [ -z "$sid" ]; then launch_fresh "$n" "An earlier attempt stopped early. OUT already has partial files: read them and continue from where it left; finish every deliverable."; return; fi
  k=$(( $(ls "$o"/codex_resume_*.log 2>/dev/null | wc -l) + 1 ))
  local msg="You stopped before finishing ($2). Same rules as your first prompt: main chat only, no sub-agents, never run claude/opencode/harbor/codex, read-only outside OUT, no Docker. Read your files in OUT, continue from where you left, and finish every deliverable (FINDINGS.md, QUESTIONS.md, result.json and the extra files)."
  echo "RESUME $(date '+%H:%M:%S') ($2)" >> "$o/status.txt"
  ( cd "$o" && "$CODEX" $(search_flag "$n") exec resume "$sid" --skip-git-repo-check --disable multi_agent \
      -c sandbox_mode='"workspace-write"' -c model_reasoning_effort=high -o "$o/last.txt" "$msg" \
      < /dev/null > "$o/codex_resume_$k.log" 2>&1
    echo "END $(date '+%H:%M:%S') rc=$? (resume $k)" >> "$o/status.txt" ) &
  echo $! > "$o/sup.pid"; log "resume $n session $sid ($2)"
}

handle_stopped() {  # session not alive and not done
  local n=$1 o t; o=$(out_of "$n")
  if hit_limit "$n"; then
    local w; w=$(cat "$o/sup_wait_until" 2>/dev/null || echo 0)
    if [ "$w" = 0 ]; then echo $(( $(date +%s) + LIMIT_WAIT_S )) > "$o/sup_wait_until"; log "$n hit usage limit; waiting"; return; fi
    [ "$(date +%s)" -lt "$w" ] && return
    rm -f "$o/sup_wait_until"; launch_resume "$n" "usage limit, after waiting"; return
  fi
  t=$(tries "$n")
  if [ "$t" -ge "$MAXTRIES" ]; then
    [ -f "$o/sup_failed" ] || { touch "$o/sup_failed"; log "$n FAILED after $t tries"; }
    return
  fi
  echo $(( t + 1 )) > "$o/sup_tries"; launch_resume "$n" "stopped without finishing, try $(( t + 1 ))"
}

check_one() {  # prints state: done|failed|running|stopped|new
  local n=$1 o; o=$(out_of "$n")
  if is_done "$n"; then echo done; return; fi
  [ -f "$o/sup_failed" ] && { echo failed; return; }
  if ! started "$n"; then echo new; return; fi
  if is_alive "$n"; then
    if [ "$(newest_log_age "$n")" -ge "$STUCK_S" ]; then
      log "$n stuck (no log growth for 30 min): stopping it"
      pkill -f -- "-C $o" 2>/dev/null; pid=$(cat "$o/sup.pid" 2>/dev/null); [ -n "$pid" ] && pkill -P "$pid" 2>/dev/null && kill "$pid" 2>/dev/null
      sleep 5; echo stopped; return
    fi
    echo running; return
  fi
  echo stopped
}

log "supervisor start (pid $$)"
while true; do
  running=0; finished=0; summary=""
  for n in $MAIN; do
    s=$(check_one "$n"); summary="$summary $n=$s"
    case $s in
      running) running=$((running + 1)) ;;
      done|failed) finished=$((finished + 1)) ;;
      stopped) handle_stopped "$n"; is_alive "$n" && running=$((running + 1)) ;;
    esac
  done
  for n in $MAIN; do  # start new ones up to MAXPAR
    [ "$running" -ge "$MAXPAR" ] && break
    if [ "$(check_one "$n")" = new ]; then launch_fresh "$n"; running=$((running + 1)); sleep 5; fi
  done
  if [ "$finished" -eq 6 ]; then
    s=$(check_one L7_synthesis); summary="$summary L7=$s"
    case $s in
      new) launch_fresh L7_synthesis ;;
      stopped) handle_stopped L7_synthesis ;;
      done|failed) log "ALL FINISHED:$summary"; echo "ALL_DONE $(date '+%H:%M:%S')" > "$BASE/ALL_DONE.txt"; exit 0 ;;
    esac
  fi
  log "tick:$summary"
  sleep 600
done
