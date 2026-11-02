#!/bin/sh
for p in /p/ref.py /p/kill/K1.py /p/kill/K2.py /p/kill/K3.py /p/kill/K4.py /p/kill/K5.py /p/kill/K6.py /p/kill/K7.py; do
  n=$(basename $p .py)
  python3 /p/score.py $p /c > /o/score_$n.txt 2>&1
  echo "$n done $(grep -E '^(TOTAL|LEVER)' /o/score_$n.txt | tr '\n' ' ')"
done
