#!/bin/bash
set -uo pipefail
scratch="/Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/score-blinds-4653510"
blind="$1"
while ! python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2; do
    for i in $(seq 20); do
        sleep 10
        python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2 && break
    done
done
export OPENAI_API_KEY="${OPENAI_API_KEY:-unused}"
yes | harbor run -p "$scratch/$blind" --agent oracle -o "$scratch/jobs" --env docker -y --job-name "$blind" -n 1
status="${PIPESTATUS[1]}"
echo "HARBOR_EXIT=$status"
echo ALL_DONE
exit "$status"
