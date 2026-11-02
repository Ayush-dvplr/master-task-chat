#!/bin/bash
C=ql1fc-verifier
L="$1"
while [ "$(docker inspect -f '{{.State.Running}}' $C 2>/dev/null)" = "true" ]; do
  { echo "== $(date -u +%H:%M:%SZ)"; docker stats --no-stream --format '{{.CPUPerc}} {{.MemUsage}}' $C;
    docker exec $C sh -c 'ls -d /tmp/rerun-*/extract-* 2>/dev/null | sed "s#.*/extract-##" | sort | uniq -c | tr "\n" ";"'; echo; } >> "$L/mon.log" 2>&1
  docker exec $C sh -c 'ls -d --full-time /tmp/rerun-*/extract-* 2>/dev/null' > "$L/last_ls.txt" 2>&1
  sleep 30
done
echo "EXIT $(date -u +%H:%M:%SZ) $(docker inspect -f '{{.State.StartedAt}} {{.State.FinishedAt}} {{.State.ExitCode}}' $C)" >> "$L/mon.log"
docker logs $C > "$L/verifier_stdout.txt" 2>&1
docker cp $C:/logs/verifier "$L/verifier_logs" >/dev/null 2>&1
echo MON_DONE >> "$L/mon.log"
