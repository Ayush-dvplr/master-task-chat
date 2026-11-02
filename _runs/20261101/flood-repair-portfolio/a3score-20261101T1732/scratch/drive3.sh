#!/bin/bash
# Copy of h2_a1/drive2.sh for the a3 program (mounted /a3out read-only). Inside Docker.
set -u
H=/w/h1_a1; H2=/w/h2_a1; A3=/a3out/derive_report.py
mkdir -p /tmp/books /tmp/ref /tmp/out
python3 -B $H/timer.py 60 a3_shipped_vs_1519 /b/environment/data /tmp/out/shipped.a3 /a3out $A3
for spec in $BOOKS; do
  IFS=: read -r name seed base rep <<< "$spec"
  python3 -B $H2/proto_gen2.py /tmp/books "$name" "$seed" "$base" "$rep" || echo "GENFAIL $name"
done
for spec in $BOOKS; do
  name=${spec%%:*}
  python3 -B $H/timer.py 600 ref_unbusy /tmp/books/$name /tmp/ref/$name - /b/solution/solve.py
  rm -rf /tmp/out/$name.a3u
  python3 -B $H/timer.py "$CAP" a3_unbusy /tmp/books/$name /tmp/out/$name.a3u /tmp/ref/$name $A3
done
python3 -c 'while True: pass' & BPID=$!; echo "busy core pid $BPID"
for spec in $BOOKS; do
  name=${spec%%:*}
  python3 -B $H/timer.py 600 ref_busy /tmp/books/$name /tmp/refb_$name - /b/solution/solve.py
  for k in 1 2; do
    rm -rf /tmp/out/$name.a3b
    python3 -B $H/timer.py "$CAP" a3_busy$k /tmp/books/$name /tmp/out/$name.a3b /tmp/ref/$name $A3
  done
done
kill $BPID
echo ALL_DONE
