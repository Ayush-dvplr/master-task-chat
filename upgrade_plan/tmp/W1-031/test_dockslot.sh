#!/bin/bash
# Dry test of dockslot.py with a fake capacity: VM 11264 MB - 3072 headroom = 8192 MB = two 4096 MB jobs.
HERE="$(cd "$(dirname "$0")" && pwd)"
export DOCKSLOT_SETTINGS="$HERE/test_settings.json"
export DOCKSLOT_DIR="${DOCKSLOT_DIR:-$(mktemp -d)}"
export DOCKSLOT_FAKE="vm_mb=11264,cpus=8"
DS="python3 $HERE/dockslot.py"
job() { echo "$(date +%T) $1 START lease=$DOCKSLOT_LEASE"; sleep "$2"; echo "$(date +%T) $1 END"; }
export -f job

echo "== T1 and T2: two small jobs start together, a third waits and starts when one releases"
$DS run --kind kill -- bash -c 'job A 4' &
$DS run --kind kill -- bash -c 'job B 6' &
sleep 1
$DS run --kind kill -- bash -c 'job C 1' &
sleep 1
$DS status
wait
echo
echo "== T3: a dead lease (fake owner pid 999999) is freed and reported"
$DS acquire --kind kill --owner-pid 999999
$DS status
sleep 3
$DS daemon --once
$DS status
echo
echo "== T4: a paid run jumps the queue"
$DS run --kind kill -- bash -c 'job K1 3' &
$DS run --kind kill -- bash -c 'job K2 6' &
sleep 1
$DS run --kind kill -- bash -c 'job K3-older-waiter 1' &
sleep 1
$DS run --kind paid -- bash -c 'job PAID 1' &
sleep 0.5
$DS status
wait
echo
echo "== T5: fast lane: oracle and nop pass a paid run that is waiting for room"
$DS run --kind kill -- bash -c 'job KILL 6' &
sleep 1
$DS run --kind paid --mb 8192 -- bash -c 'job PAID2 1' &
sleep 1
$DS run --kind oracle -- bash -c 'job ORACLE 1' &
$DS run --kind nop -- bash -c 'job NOP 1' &
wait
echo
echo "== events.log"
cut -c1-160 "$DOCKSLOT_DIR/events.log"
