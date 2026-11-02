#!/bin/bash
# Apply the bundle's declared limits (memory_mb 8192, cpus 2) to each of this chain's verifier containers.
L=/tmp/opencode-logs/mu-79409fb-blind
until grep -q ALL_DONE "$L/runs.log"; do
  for c in $(docker ps --format '{{.Names}}' | grep -E '^(oracle|d5c7b9d|f4f4ff5|4d36b26)__.*__verifier__'); do
    if [ "$(docker inspect -f '{{.HostConfig.Memory}}' "$c")" = "0" ]; then
      docker update --memory 8192m --memory-swap 8192m --cpus 2 "$c" >/dev/null 2>&1
      echo "$(date +%T) $c -> $(docker inspect -f 'mem={{.HostConfig.Memory}} swap={{.HostConfig.MemorySwap}} nanocpus={{.HostConfig.NanoCpus}}' "$c")" >> "$L/enforce.log"
    fi
  done
  sleep 3
done
echo ENFORCE_DONE >> "$L/enforce.log"
