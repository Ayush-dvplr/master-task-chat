#!/bin/bash
# Docker only. Mounts: /src = BUNDLE/tests (ro), /bdata = BUNDLE/environment/data (ro), /w = WORK/h1_a1 (ro), /r = run dir.
# Rebuilds /tests as test.sh leaves it (root only), writes the attack programs, runs the fork probe first
# (fresh container), then scores the attacks. The overwrite attack's /app/out is the a1 shipped output it would deliver.
set -u
rm -rf /tests && cp -r /src /tests && chmod -R go-rwx /tests
export PYTHONDONTWRITEBYTECODE=1
mkdir -p /tmp/ship && python3 -B /w/a1_program.py /bdata /tmp/ship
python3 -B /w/attacks/make_attacks.py /tmp/ship /tmp/att
rm -rf /tmp/lifted /tmp/alive_*
python3 -B /w/attacks/fork_probe.py /tests /tmp/att/overwrite.py built
echo "lifted dirs after built probe: $(ls /tmp/lifted 2>/dev/null | wc -l)"
sleep 2; rm -rf /tmp/lifted /tmp/alive_*
python3 -B /w/attacks/fork_probe.py /w/pre_build/tests /tmp/att/overwrite.py pre_build
sleep 2; rm -rf /tmp/lifted /tmp/alive_*
DELIVER=overwrite.py=/tmp/ship python3 -B /w/score_all.py /r/attacks.jsonl /tmp/att/lift.py /tmp/att/overwrite.py /tmp/att/stub.py /tmp/att/forgery.py /tmp/att/hardcoded.py
echo "lift_found: $(cat /tmp/lift_found.txt 2>/dev/null | wc -l)"; cat /tmp/lift_found.txt 2>/dev/null | head
echo "lifted dirs after scoring: $(ls /tmp/lifted 2>/dev/null | wc -l)"
echo "alive markers after scoring: $(ls /tmp/alive_* 2>/dev/null | wc -l)"
echo ATTACKS_ALL_DONE
