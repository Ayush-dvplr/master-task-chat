#!/bin/bash
# usage: runprinted.sh LOGFILE: runs the indented lines printed after "VERDICT: READY" (or any marker in $2) literally, in one bash, reporting each exit code
LOG=$1; MARK=${2:-^VERDICT: READY}
S=$(mktemp -p "$(dirname $LOG)" cmds.XXXX)
sed -n "/$MARK/,\$p" "$LOG" | tail -n +2 | sed 's/^  //' | grep -v '^$' | while IFS= read -r line; do
  printf 'echo %q\n%s\necho "    [exit $?]"\n' ">>> $line" "$line" >> "$S"
done
bash "$S" 2>&1
rm -f "$S"
