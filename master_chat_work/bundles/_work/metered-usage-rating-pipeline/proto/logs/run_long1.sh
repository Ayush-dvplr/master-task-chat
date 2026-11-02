set -x
cd /w/proto
python3 -B build_long.py 70213 6000 52000 9000
python3 -B build_long.py 70214 7000 58000 10500
python3 -B build_long.py 70215 8000 66000 12000
for c in long_70213 long_70214 long_70215; do python3 -B run_kill.py $c 150 ref_solve s1_probe s2_perline s3_label s5_greedy s7_recursive s8_memo; done
echo ALL_DONE
