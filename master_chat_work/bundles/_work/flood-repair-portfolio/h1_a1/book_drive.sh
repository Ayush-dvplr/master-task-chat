#!/bin/bash
# Inside Docker. env BOOKS="name:seed:k:n:rows ...", PROGS="a1 elim dae", CAP seconds, BUSY 0|1.
set -u
H=/w/h1_a1
declare -A P=([ref]=/b/solution/solve.py [a1]=$H/a1_program/derive_report.py [elim]=$H/elim_program.py [dae]=$H/dae9563_program.py [vebest]=$H/vebest_program.py)
mkdir -p /tmp/books /tmp/ref /tmp/out
[ "${HIDDEN:-0}" = 1 ] && python3 -B $H/hidden_books.py /tmp/books
for spec in $BOOKS; do
  case $spec in *:*) ;; *) continue ;; esac
  IFS=: read -r name seed k n rows <<< "$spec"
  python3 -B $H/proto_gen.py /tmp/books "$name" "$seed" "$k" "$n" "$rows" || echo "GENFAIL $name"
done
if [ "${BUSY:-0}" = 1 ]; then python3 -c 'while True: pass' & BPID=$!; echo "busy core pid $BPID"; fi
for spec in $BOOKS; do
  name=${spec%%:*}
  python3 -B $H/timer.py 600 ref /tmp/books/$name /tmp/ref/$name - ${P[ref]}
  for prog in $PROGS; do
    rm -rf /tmp/out/$name.$prog
    python3 -B $H/timer.py "$CAP" "$prog" /tmp/books/$name /tmp/out/$name.$prog /tmp/ref/$name ${P[$prog]}
  done
done
[ -n "${BPID:-}" ] && kill $BPID
echo ALL_DONE
