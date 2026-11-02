#!/bin/zsh
set -eu
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/sensor-network-lsq-correlated-adjustment"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/sensor-network-lsq-correlated-adjustment"
T="$B/tests/test_output.py"
D="$B/environment/data"
python3 "$W/trap/grade_local.py" "$T" "$B/solution/solve.py" "$D" > "$W/trap/oracle_after.json"
echo "DONE oracle"
for name in no_centring no_reduce centring_angles ignore_mount first_seen last_occurrence; do
  python3 "$W/trap/grade_local.py" "$T" "$W/wrong/$name.py" "$D" > "$W/trap/${name}_after.json"
  echo "DONE $name"
done
python3 "$W/trap/grade_local.py" "$T" "/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_sensor-network-lsq-correlated-adjustment/harden_r1/baseline_v0/trajectory_job_sensor-network-lsq-correlated-adjustment_4d7424/trajectory/claude-opus-5/Run 1/artifacts/app/out/derive_report.py" "$D" > "$W/trap/reflex_after.json"
echo "ALL_DONE"
