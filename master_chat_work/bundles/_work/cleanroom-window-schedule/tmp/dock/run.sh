set -u
cd /w
python3 -B timing.py /sol/solve.py ref 60
python3 -B timing.py /w/mutants/raw_exact.py raw_exact 20
python3 -B timing.py /w/mutants/raw_tuned.py raw_tuned 20
