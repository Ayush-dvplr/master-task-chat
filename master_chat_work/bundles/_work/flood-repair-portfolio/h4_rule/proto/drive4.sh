#!/bin/bash
# Inside Docker: /w=WORK, /b=BUNDLE (ro). env PROGS, CAP, KH, KM.
set -u
H=/w/h1_a1; H2=/w/h2_a1; X=/w/h4_rule
declare -A P=([ref]=$X/proto/solve.py [oldref]=/b/solution/solve.py [a3nat]=$X/programs/a3_natural.py [a3cor]=$X/programs/a3_correct.py [a3pre]=$X/programs/a3_prefilter.py [a3unc]=$X/programs/a3_unchanged.py [a1]=$H/a1_program/derive_report.py [fw]=$H2/firstwrite_program.py [abo]=$H2/allbutone_program.py)
mkdir -p /tmp/books /tmp/ref /tmp/out
python3 -B $X/proto/proto_books.py /b/tests/test_output.py /tmp/books "$KH" "$KM" || echo GENFAIL
cp /tmp/books/*.meta.json /w/h4_rule/proto/ 2>/dev/null
BOOKS="H1c H2c H3c Mc"
for name in $BOOKS; do python3 -B $H/timer.py 600 ref_unbusy /tmp/books/$name /tmp/ref/$name - ${P[ref]}; done
python3 -c 'while True: pass' & BPID=$!; echo "busy core pid $BPID"
for name in $BOOKS; do
  python3 -B $H/timer.py 600 ref_busy /tmp/books/$name /tmp/refb_$name - ${P[ref]}
  for prog in $PROGS; do
    rm -rf /tmp/out/$name.$prog
    line=$(python3 -B $H/timer.py "$CAP" "$prog" /tmp/books/$name /tmp/out/$name.$prog /tmp/ref/$name ${P[$prog]})
    echo "$line"
    v=$(echo "$line" | awk '{print $6}')
    python3 -B $X/proto/docscore.py "$prog" /tmp/books/$name /tmp/ref/$name /tmp/out/$name.$prog "$v"
  done
done
kill $BPID
echo ALL_DONE
