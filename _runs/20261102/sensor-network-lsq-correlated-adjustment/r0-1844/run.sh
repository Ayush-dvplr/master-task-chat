set -u
python3 /work/measure.py /bundle /work/programs /run/s1 plain,sk_csv,sk_csv_tsv,sk_csv_swap,plain_swap,dir_csv,kind_csv,unit_csv,id_csv,epoch_csv,region_csv paid,oracle
python3 /work/measure.py /bundle /work/programs /run/s2 plain,sk_csv_swap,sk_csv_tsv paid_first_write,paid_lever_aware,oracle_all_but_one,a2_r2,wrong_centring_angles,wrong_first_seen,wrong_ignore_mount,wrong_last_occurrence,wrong_no_centring,wrong_no_reduce
echo STAGES_DONE
