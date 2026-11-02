#!/bin/bash
R="/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/harden2-20261101T1130"
for p in oracle a1; do
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2 > "$R/logs/v_$p.log" 2>&1
  perl -e 'alarm 2700; exec @ARGV' docker run --rm --name cb8dada_v_$p --memory 4g --cpus 2 -v "$R/scratch/vt_$p/tests:/tests" -v "$R/scratch/vt_$p/app:/app" -v "$R/scratch/vt_$p/logs:/logs" -v "$R/scratch/vrun.sh:/vrun.sh:ro" cb8dada_verif bash /vrun.sh >> "$R/logs/v_$p.log" 2>&1
  echo "container_rc $?" >> "$R/logs/v_$p.log"
done
echo BOTH_DONE >> "$R/logs/v_a1.log"
