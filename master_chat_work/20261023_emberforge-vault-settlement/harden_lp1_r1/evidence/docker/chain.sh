#!/bin/zsh
J=/tmp/opencode-logs/emberforge-vault-settlement-lp1r1-20261023T131949-9ac6/jobs
mkdir -p $J
run() { echo "=== $1 $(date)"; shift; "$@"; echo "exit $?"; }
while [ $(docker ps -q | wc -l) -ge 3 ]; do sleep 15; done
run warm sh -c "cd /tmp/lp1r1-20261023T131949-9ac6/plain/tests && docker build --progress plain -t warm-emberforge-vault-settlement . > /tmp/opencode-logs/emberforge-vault-settlement-lp1r1-20261023T131949-9ac6/warm.log 2>&1"
run oracle-1 harbor run --path /tmp/lp1r1-20261023T131949-9ac6/plain --agent oracle --env docker --job-name oracle-1 -y -o $J
run oracle-2 harbor run --path /tmp/lp1r1-20261023T131949-9ac6/plain --agent oracle --env docker --job-name oracle-2 -y -o $J
run oracle-3 harbor run --path /tmp/lp1r1-20261023T131949-9ac6/plain --agent oracle --env docker --job-name oracle-3 -y -o $J
run owner-1 harbor run --path /tmp/lp1r1-20261023T131949-9ac6/owner --agent oracle --env docker --job-name owner-1 -y -o $J
run nop-1 harbor run --path /tmp/lp1r1-20261023T131949-9ac6/plain --agent nop --env docker --job-name nop-1 -y -o $J
run stub-1 harbor run --path /tmp/lp1r1-20261023T131949-9ac6/stub --agent oracle --env docker --job-name stub-1 -y -o $J
run forgery-1 harbor run --path /tmp/lp1r1-20261023T131949-9ac6/forgery --agent oracle --env docker --job-name forgery-1 -y -o $J
echo ALL_DONE
