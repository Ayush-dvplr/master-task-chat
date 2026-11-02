#!/bin/bash
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/warrant-asof-entitlement-compiler"; B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/warrant-asof-entitlement-compiler"
TS=20261030T0920-s2
# run <name> <host prog dir> <arg inside container> [extra -e]
run() {
  perl -e 'alarm 3000; exec @ARGV' docker run --rm --name c4989b35_$1_$TS --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1 -e TESTS=/p12/t3.py $4 \
    -v "$W/harness":/h:ro -v "$W/p12":/p12:ro -v "$B/tests":/tests:ro -v "$2":/prog:ro python:3.12-slim python3 /h/score.py $3 > "$W/p12/runs/s2_$1.txt" 2>&1
  echo "$1 rc=$? $(date +%H:%M:%S)"
}
uniq() {
  perl -e 'alarm 3000; exec @ARGV' docker run --rm --name c4989b35_uniq_$TS --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1 -e REF=/p12/t3.py -e UNIQ=1 -e STARTS=requested,decided,recorded,latest \
    -v "$W/harness":/h:ro -v "$W/p12":/p12:ro -v "$W":/w:ro python:3.12-slim python3 /h/conv_sweep.py - \
    85041:0.05:conv:zone=Site/Dune:requested:closed 98053:0.05:conv:zone=Site/Brisk:requested:closed 99061:0.05:conv:zone=Site/Arden:requested:closed > "$W/p12/runs/s2_uniq.txt" 2>&1
  echo "uniq rc=$? $(date +%H:%M:%S)"
}
laneA() {
  run eng1 "$W/p12/eng1" /prog
  run legacy "$B/environment/data" /prog/tool.zip
  run a1 "$W/a1_program" /prog
  run P0s "$W/kill/P0s" /prog
  run P2n "$W/kill/P2n" /prog
  run P3b "$W/kill/P3b" /prog
  run P7w "$W/kill/P7w" /prog
}
laneB() {
  uniq
  run b92419ce /tmp/blind/warrant-asof-entitlement-compiler-20261030T060705-9b7d/out /prog "-e DELIVERED=1"
  run b787e598 /tmp/blind/warrant-asof-entitlement-compiler-20261030T060705-9992/out /prog "-e DELIVERED=1"
  run bb6c896c /tmp/blind/warrant-asof-entitlement-compiler-20261030T060705-cee9/out /prog "-e DELIVERED=1"
  run P4o "$W/kill/P4o" /prog
  run P6o "$W/kill/P6o" /prog
}
laneA & laneB & wait
echo ALL_DONE
