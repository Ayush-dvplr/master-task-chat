set -x
cd /w/proto
python3 -B build_ladder.py 71001 6000 2000 20000
python3 -B build_ladder.py 71002 6000 2000 30000
python3 -B build_ladder.py 71003 8000 2500 20000
echo ALL_DONE
