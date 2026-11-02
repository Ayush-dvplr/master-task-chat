#!/bin/bash
L="/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/a3score-20261101T1732/logs/v_a3.log"
docker build -q -t a3s_verif "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/a3score-20261101T1732/scratch/copy/tests" > "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/a3score-20261101T1732/logs/build.log" 2>&1; echo "build_rc $?" >> "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/a3score-20261101T1732/logs/build.log"
python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2 > "$L" 2>&1
grep -q START=yes "$L" || { echo "NO_START ALL_DONE" >> "$L"; exit 1; }
perl -e 'alarm 2700; exec @ARGV' docker run --rm --name a3s_v --memory 4g --cpus 2 -v "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/a3score-20261101T1732/scratch/v_a3/tests:/tests" -v "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/a3score-20261101T1732/scratch/v_a3/app:/app" -v "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/a3score-20261101T1732/scratch/v_a3/logs:/logs" -v "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/a3score-20261101T1732/scratch/vrun3.sh:/vrun.sh:ro" a3s_verif bash /vrun.sh >> "$L" 2>&1
echo "container_rc $?" >> "$L"
