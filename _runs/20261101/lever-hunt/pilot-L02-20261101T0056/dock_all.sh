#!/bin/zsh
L="/Users/mac/Desktop/Terminal Bench/_tester/lever_hunt/E_pilot/L02"; S="/Users/mac/Desktop/Terminal Bench/_runs/20261101/lever-hunt/pilot-L02-20261101T0056"
DF="/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py"
for row in ref K1 K2 K3a K3b K4 K5 K6 K7 K8; do
  for i in $(seq 20); do python3 "$DF" --need-mb 4096 --cpus 2 >/dev/null && break; sleep 10; done; echo "poll $row $i"
  python3 "$DF" --need-mb 4096 --cpus 2 | grep START
  if [ $row = ref ]; then prog=/p/ref.py; else prog=/p/kill/$row.py; fi
  /usr/bin/time -p docker run --rm --memory 4g --cpus 2 -v "$L/proto:/p:ro" -v "$S/corpora:/c:ro" python:3.12-slim python3 /p/score.py $prog /c > "$L/proto/kill/scores/score_$row.txt" 2> "$S/err_$row.txt"
  echo "done $row rc=$?"
done
echo ALLDONE
