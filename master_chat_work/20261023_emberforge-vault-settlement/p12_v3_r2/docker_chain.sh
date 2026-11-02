#!/bin/bash
set -uo pipefail
OUT='/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_emberforge-vault-settlement/p12_v3_r2'
ROOT="$(cat "$OUT/docker_root.txt")"
JOBS="$ROOT/jobs"
mkdir -p "$JOBS"
echo "WARM BEGIN $(date)"
(cd "$ROOT/plain/tests" && docker build --progress plain -t warm-emberforge-vault-settlement . > "$OUT/warm.log" 2>&1); echo "WARM EXIT:$? $(date)"
for label in oracle-1 oracle-2 oracle-3 owner-1 nop-1 stub-1; do
  while [ "$(docker ps -q | wc -l | tr -d ' ')" -ge 2 ]; do sleep 20; done
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
