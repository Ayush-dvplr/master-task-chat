cd "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cleanroom-window-schedule"
for m in greedy greedy_ls lane_by_lane flow_relax no_crew naive_collapse reset_nightly no_initial touching_only raw_tuned raw_exact; do
  echo "== $m $(date +%T)"
  python3 -B run_tests.py mutants/$m.py --json tmp/cost/$m.json > tmp/cost/$m.log 2>&1
  tail -1 tmp/cost/$m.log
done
echo ALL_DONE
