set -u
mkdir -p /app/data /app/out /solution
cp -r /bundle/environment/data/. /app/data/
cp -r /bundle/solution/. /solution/
echo "== solve.sh"; s=$(date +%s); bash /solution/solve.sh; echo "SOLVE_EXIT=$? SOLVE_SECONDS=$(( $(date +%s) - s ))"
echo "== verify_build"; python3 /work/verify_build.py /bundle /work/before/test_output.py /run/verify_build.json
echo "== measure"; python3 /work/measure.py /bundle /work/programs /run/m plain oracle,paid,paid_first_write,oracle_all_but_one,paid_lever_aware,a2_r2,wrong_centring_angles,wrong_first_seen,wrong_ignore_mount,wrong_last_occurrence,wrong_no_centring,wrong_no_reduce
echo STAGES_DONE
