#!/bin/bash
# Inside Docker. env BOOKS="name:seed:base:rep ...", PROGS, CAP, BUSY 0|1, REFONLY 0|1.
set -u
H=/w/h1_a1; H2=/w/h2_a1
declare -A P=([ref]=/b/solution/solve.py [a1]=$H/a1_program/derive_report.py [elim]=$H/elim_program.py [dae]=$H/dae9563_program.py [vebest]=$H/vebest_program.py [fw]=$H2/firstwrite_program.py [abo]=$H2/allbutone_program.py)
mkdir -p /tmp/books /tmp/ref /tmp/out
for spec in $BOOKS; do
  IFS=: read -r name seed base rep <<< "$spec"
  python3 -B $H2/proto_gen2.py /tmp/books "$name" "$seed" "$base" "$rep" || echo "GENFAIL $name"
done
for spec in $BOOKS; do
  name=${spec%%:*}
  python3 -B $H/timer.py 600 ref_unbusy /tmp/books/$name /tmp/ref/$name - ${P[ref]}
done
python3 -c 'while True: pass' & BPID=$!; echo "busy core pid $BPID"
for spec in $BOOKS; do
  name=${spec%%:*}
  python3 -B $H/timer.py 600 ref_busy /tmp/books/$name /tmp/refb_$name - ${P[ref]}
  for prog in $PROGS; do
    rm -rf /tmp/out/$name.$prog
    python3 -B $H/timer.py "$CAP" "$prog" /tmp/books/$name /tmp/out/$name.$prog /tmp/ref/$name ${P[$prog]}
  done
done
kill $BPID
echo ALL_DONE
