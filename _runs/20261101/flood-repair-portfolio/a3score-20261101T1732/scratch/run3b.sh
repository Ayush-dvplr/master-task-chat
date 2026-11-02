#!/bin/bash
L="/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/a3score-20261101T1732/logs/kill_a3.log"
python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2 > "$L" 2>&1
grep -q START=yes "$L" || { echo "NO_START ALL_DONE" >> "$L"; exit 1; }
perl -e 'alarm 1800; exec @ARGV' docker run --rm --name a3s_kill --memory 4g --cpus 2 -e BOOKS="N1:815301:H1:30 N2:822402:H2:30 N3:833503:H3:30" -e CAP=60 -v "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/flood-repair-portfolio:/w:ro" -v "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/flood-repair-portfolio:/b:ro" -v "/Users/mac/Desktop/Terminal Bench/master_chat_work/20261101_flood-repair-portfolio/a3_score/a3_out:/a3out:ro" -v "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/a3score-20261101T1732/scratch/drive3.sh:/drive3.sh:ro" a3s_verif bash /drive3.sh >> "$L" 2>&1
echo "container_rc $?" >> "$L"
