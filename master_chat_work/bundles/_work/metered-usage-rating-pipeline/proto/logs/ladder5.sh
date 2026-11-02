set -x
cd /w/proto
python3 -B build_ladder.py 72003 15000 84000 50000 12000
python3 -B run_ladder.py ladder_72003 45 ref_solve s1_probe s2_perline s3_label s4_endonly s5_greedy s6_naive s7_recursive s8_memo s9_plainwalk s10_tierscan s11_tierbreak s12_tierrev s13_tiermax agent_p3 blind_c60b blind_9d66 blind_d576
echo ALL_DONE
