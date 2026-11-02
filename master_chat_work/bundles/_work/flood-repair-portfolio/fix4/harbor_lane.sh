#!/bin/bash
set -u
lane=$1
copy=$2
agent=$3
R='/Users/mac/Desktop/Terminal Bench/_runs/20261102/flood-repair-portfolio/fix4-20261102T2359'
export OPENAI_API_KEY=unused PYTHONDONTWRITEBYTECODE=1
python3 '/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py' --need-mb 4096 --cpus 2 | tee "$R/logs/free-$lane.log"
if ! grep -q 'START=yes' "$R/logs/free-$lane.log"; then exit 3; fi
yes | perl -e 'alarm 4200; exec @ARGV' harbor run --path "$copy" --agent "$agent" --env docker --job-name "fix4-$lane" --jobs-dir "$R/scratch/jobs" --n-concurrent 1 --n-attempts 1 --override-cpus 2 --override-memory-mb 4096 --ve OPENAI_API_KEY=unused --yes
rc=$?
echo "HARBOR_RC $rc"
echo ALL_DONE
exit "$rc"
