set -x
cd /w/proto
python3 -B build_ladder.py 72001 13000 76000 20000 11000
python3 -B run_ladder.py ladder_72001 45 ref_solve s8_memo s11_tierbreak s13_tiermax s10_tierscan s12_tierrev agent_p3 blind_c60b blind_9d66 blind_d576
echo ALL_DONE
