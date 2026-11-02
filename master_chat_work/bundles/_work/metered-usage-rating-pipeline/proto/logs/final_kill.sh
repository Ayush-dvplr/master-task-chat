set -x
cd /w/proto
for k in 1 2 3; do
  python3 -B final_kill.py $k 60 ref_solve s8_memo s9_plainwalk s3_label s5_greedy s7_recursive s1_probe s2_perline s4_endonly s6_naive
done
echo ALL_DONE
