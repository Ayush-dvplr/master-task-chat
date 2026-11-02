set -x
cd /w/proto
python3 -B build_ladder.py 72002 13000 76000 50000 11000
python3 -B run_ladder.py ladder_72002 60 ref_solve s11_tierbreak s12_tierrev s13_tiermax s10_tierscan
echo ALL_DONE
