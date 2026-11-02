#!/bin/bash
# fix1 kill table: oracle, 16 wrong programs and the design-blind program on the final tests.
S="/Users/mac/Desktop/Terminal Bench/_runs/20261101/hangar-check-replan/fix1-20261101T1639"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/hangar-check-replan"
DF="/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py"
N="oracle s_cap_not_subtracted s_per_base_cap s_unordered s_whole_only s_granted_not_used s_start_key p_pool_per_base p_no_revised p_defer_no_slot_only p_first_found_tie p_earliest_only u_from_records x_ids_from_ignored q_line_from_one c_no_clip e8e9c82_adapted blind_c2c1"
for i in $(seq 360); do
  python3 "$DF" --need-mb 4096 --cpus 2 | tail -1 | grep -q START=yes && break
  sleep 20
done
python3 "$DF" --need-mb 4096 --cpus 2 | tail -1
echo "kill start $(date +%H:%M:%S)"
perl -e 'alarm 2700; exec @ARGV' docker run --rm --name hangar-fix1-kill --memory 4g --cpus 2 \
  -e PYTHONDONTWRITEBYTECODE=1 -v "$B/tests:/tests:ro" -v "$B/environment/data:/app/data:ro" \
  -v "$B/solution:/solution:ro" -v "$S/kill:/kill" hangar-tests \
  python3 -B /kill/score_many.py /tests/test_output.py /kill/progs $N
echo "kill rc=$? end $(date +%H:%M:%S)"
