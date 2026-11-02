#!/bin/sh
# usage inside container: seal_all.sh <tests_dir> <solve.py> <ext_dir with A B> <shipped data> <dest>
T=$1; S=$2; E=$3; D=$4; O=$5
mkdir -p $O
for c in shipped A B; do
  if [ $c = shipped ]; then src=$D; else src=$E/$c; fi
  python3 -B /w/harness/seal.py $T $S $src $O/out_$c > $O/seal_$c.json || echo FAIL $c
done
