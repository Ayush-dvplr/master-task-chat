#!/bin/bash
cd "$(dirname "$0")"
for s in 41 42 43; do TOTAL=1 python3 -B bench.py ref p_e10_$s.json 120 > log_ref_e10_$s.txt & done
for s in 41 42 43; do TOTAL=1 python3 -B bench.py ref3 p_e10_$s.json 120 > log_ref3_e10_$s.txt & done
wait; echo done > e10.done
