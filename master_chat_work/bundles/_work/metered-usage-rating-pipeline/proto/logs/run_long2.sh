set -x
cd /w/proto
python3 -B check_gen.py old 2>&1 | tail -3
python3 -B build_long.py 70213 13000 76000 11000
python3 -B run_kill.py long_70213 200 ref_solve s2_perline s1_probe
echo ALL_DONE
