set -e
for t in before after; do rm -rf /tmp/o_$t; mkdir -p /tmp/o_$t/out; cp /progs/oracle/solve.py /tmp/o_$t/out/reconcile.py; cd /tmp/o_$t; python3 -B /tmp/o_$t/out/reconcile.py /d_$t /tmp/o_$t/out >/dev/null 2>&1 || python3 -B /tmp/o_$t/out/reconcile.py >/dev/null; done
