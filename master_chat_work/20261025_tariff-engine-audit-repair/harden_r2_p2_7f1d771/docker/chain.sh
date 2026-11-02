#!/bin/zsh
R=/tmp/opencode-logs/tariff-engine-audit-repair-7f1d771-20261025T152406-748b
J=$R/jobs; mkdir -p $J
run() { echo "=== $1 $(date)"; shift; "$@"; echo "exit $?"; }
while [ $(docker ps -q | wc -l) -ge 2 ]; do sleep 15; done
run warm sh -c "cd $R/plain/tests && docker build --progress plain -t warm-tariff-engine-audit-repair . > $R/warm.log 2>&1"
for l in oracle-1 oracle-2 oracle-3 owner-1 nop-1 stub-1 forgery-1; do
  while [ $(docker ps -q | wc -l) -ge 2 ]; do sleep 15; done
  case $l in owner-1) c=$R/owner; a=oracle;; nop-1) c=$R/plain; a=nop;; stub-1) c=$R/stub; a=oracle;; forgery-1) c=$R/forgery; a=oracle;; *) c=$R/plain; a=oracle;; esac
  run $l harbor run --path $c --agent $a --env docker --job-name $l -y -o $J
done
echo ALL_DONE $(date)
