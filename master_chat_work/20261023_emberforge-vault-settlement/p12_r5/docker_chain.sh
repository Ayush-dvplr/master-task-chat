#!/bin/bash
set -uo pipefail
ROOT="$(cat '/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_emberforge-vault-settlement/p12_r5/docker_root.txt')"
JOBS="$ROOT/jobs"
mkdir -p "$JOBS"
while [ "$(docker ps -q | wc -l | tr -d ' ')" -ge 2 ]; do sleep 20; done
for label in oracle-1 oracle-2 oracle-3 owner-1 nop-1 stub-1; do
  echo "BEGIN $label $(date)"
  case $label in
    owner-1) copy="$ROOT/owner"; agent=oracle;;
    nop-1) copy="$ROOT/plain"; agent=nop;;
    stub-1) copy="$ROOT/stub"; agent=oracle;;
    *) copy="$ROOT/plain"; agent=oracle;;
  esac
  harbor run --path "$copy" --agent "$agent" --env docker --job-name "$label" -y -o "$JOBS"
  echo "END $label EXIT:$? $(date)"
done
echo ALL_DONE
