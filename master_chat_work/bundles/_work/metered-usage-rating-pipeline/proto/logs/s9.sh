cd /w/proto
for k in 1 2 3; do python3 -B final_kill.py $k 150 ref_solve s9_plainwalk; done
echo ALL_DONE
