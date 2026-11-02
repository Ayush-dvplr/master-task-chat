#!/bin/bash
set -euo pipefail
ROOT="$(cat '/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_emberforge-vault-settlement/p12_r4/final_docker_root.txt')"
JOBS="$ROOT/jobs"
mkdir -p "$JOBS"
while [ "$(docker ps -q | wc -l | tr -d ' ')" -ge 2 ]; do sleep 20; done
for label in oracle-1 oracle-2 oracle-3 owner-1 nop-1; do
  echo "BEGIN $label $(date)"
  if [ "$label" = owner-1 ]; then copy="$ROOT/owner"; agent=oracle
  elif [ "$label" = nop-1 ]; then copy="$ROOT/plain"; agent=nop
  else copy="$ROOT/plain"; agent=oracle; fi
  harbor run --path "$copy" --agent "$agent" --env docker --job-name "$label" -y -o "$JOBS"
  echo "END $label EXIT:0 $(date)"
done
echo ALL_DONE
