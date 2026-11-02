set -u
for p in paid oracle; do for d in plain sk; do
  src=/bundle/environment/data; [ $d = sk ] && src=/work/witness/data_sk
  mkdir -p /run/wit/$p-$d; python3 /work/programs/$p.py $src /run/wit/$p-$d > /run/wit/$p-$d.log 2>&1; echo "wit $p $d exit $?"
done; done
for p in paid oracle; do echo "== diff $p plain vs sk"; diff -rq /run/wit/$p-plain /run/wit/$p-sk; done
echo "== oracle-sk vs paid-sk residuals OB00001"; grep -h "^OB00001," /run/wit/oracle-sk/residuals.csv /run/wit/paid-sk/residuals.csv
python3 /work/measure.py /bundle /work/programs /run/s4 rng_csv paid,oracle,paid_first_write,paid_lever_aware,oracle_all_but_one,a2_r2,wrong_centring_angles,wrong_first_seen,wrong_ignore_mount,wrong_last_occurrence,wrong_no_centring,wrong_no_reduce
echo STAGES_DONE
