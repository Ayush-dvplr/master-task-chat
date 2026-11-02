set -x
cd /w/proto
python3 -B build_ladder.py 71001 6000 2000 20000
python3 -B build_ladder.py 71003 8000 2500 20000
python3 -B run_ladder.py ladder_71001 45 ref_solve s8_memo s10_tierscan s11_tierbreak s12_tierrev s13_tiermax blind_c60b blind_9d66 blind_d576 agent_p3
echo ALL_DONE
