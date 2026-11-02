#!/bin/bash
# usage: lane.sh NAME "PROGS"
S="/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/harden4-20261101T2000/scratch"
L="/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/harden4-20261101T2000/logs/verif_$1.log"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/flood-repair-portfolio"
python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2 > "$L" 2>&1
grep -q START=yes "$L" || { echo "NO_START ALL_DONE" >> "$L"; exit 1; }
perl -e 'alarm 7000; exec @ARGV' docker run --rm --name h4v_$1 --memory 4g --cpus 2 -e PROGS="$2" -v "$S/copy4/tests:/tests0:ro" -v "$B/environment/data:/data0:ro" -v "$B/solution:/solution:ro" -v "$S/progs4:/progs:ro" -v "$S/vrun4.sh:/vrun.sh:ro" a3s_verif bash /vrun.sh >> "$L" 2>&1
echo "container_rc $?" >> "$L"
