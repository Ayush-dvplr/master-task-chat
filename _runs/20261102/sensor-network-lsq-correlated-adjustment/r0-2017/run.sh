set -u
echo "== verify_build"; python3 /work/verify_build.py /bundle /work/before/test_output.py /run/verify_build.json
echo "== measure"; python3 /work/measure.py /bundle /work/programs /run/m plain oracle,paid,paid_first_write,oracle_all_but_one,paid_lever_aware,a2_r2,wrong_centring_angles,wrong_first_seen,wrong_ignore_mount,wrong_last_occurrence,wrong_no_centring,wrong_no_reduce
echo STAGES_DONE
