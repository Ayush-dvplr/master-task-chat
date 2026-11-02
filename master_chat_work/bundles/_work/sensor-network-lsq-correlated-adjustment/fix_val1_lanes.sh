#!/bin/bash
set -eu
export OPENAI_API_KEY=unused PYTHONDONTWRITEBYTECODE=1
BASE='/Users/mac/Desktop/Terminal Bench'
RUN="$BASE/_runs/20261102/sensor-network-lsq-correlated-adjustment/fixv-20261102T224943"
WORK="$BASE/master_chat_work/bundles/_work/sensor-network-lsq-correlated-adjustment"
BUNDLE="$BASE/master_chat_work/bundles/sensor-network-lsq-correlated-adjustment"
capacity() {
    for attempt in $(seq 180); do
        if message=$(python3 "$BASE/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2); then
            printf '%s\n' "$message"
            return 0
        fi
        printf '%s\n' "$message"
        sleep 10
    done
    return 1
}
finish() { printf 'ALL_DONE exit=%s\n' "$?"; }
trap finish EXIT
capacity
perl -e 'alarm 1800; exec @ARGV' docker run --rm --name snlsq-fixv-witness-3302dbb --memory 4g --cpus 2 \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -v "$BUNDLE:/bundle:ro" -v "$BUNDLE/tests:/tests:ro" -v "$WORK:/work:ro" \
    snlsq-r2-verifier:local python3 -B /work/fix_val1_witness_driver.py > "$RUN/logs/witness.log" 2>&1
printf 'ALL_DONE exit=0\n' >> "$RUN/logs/witness.log"
for spec in oracle-1:plain:oracle oracle-2:plain:oracle oracle-3:plain:oracle owner:owner:oracle nop:plain:nop stub:stub:oracle forgery:forgery:oracle paid-fixed:paid:oracle; do
    IFS=: read -r name copy agent <<< "$spec"
    capacity
    printf 'START_LANE %s\n' "$name"
    yes | perl -e 'alarm 3000; exec @ARGV' harbor run --path "$RUN/copies/$copy" --agent "$agent" --env docker --job-name "$name" --jobs-dir "$RUN/jobs" -y > "$RUN/logs/$name.log" 2>&1
    printf 'ALL_DONE exit=0\n' >> "$RUN/logs/$name.log"
    printf 'END_LANE %s\n' "$name"
done
