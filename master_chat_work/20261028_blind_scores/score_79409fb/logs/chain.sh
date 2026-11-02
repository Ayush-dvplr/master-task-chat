#!/bin/bash
# Blind-score chain 79409fb: oracle sanity then three blind installs, one at a time, with a memory sampler.
LOCK=/tmp/opencode-logs/locks/metered-usage-rating-pipeline.lock
L=/tmp/opencode-logs/mu-79409fb-blind
J=/tmp/harbor-jobs-qc/mu-79409fb-blind
mkdir -p "$J"
echo "79409fb blind-score $(date)" > "$LOCK/owner"
export OPENAI_API_KEY=unused
cd /tmp/score_79409fb

sampler() {
  while true; do
    ts=$(date +%s)
    docker stats --no-stream --format '{{.Name}}|{{.MemUsage}}|{{.CPUPerc}}' 2>/dev/null | while IFS= read -r line; do
      name=${line%%|*}
      peak=$(docker exec "$name" cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo NA)
      limit=$(docker inspect -f '{{.HostConfig.Memory}}' "$name" 2>/dev/null || echo NA)
      echo "$ts|$line|peak=$peak|limit=$limit"
    done >> "$L/mem.log"
    sleep 10
  done
}

run() {
  name=$1; path=$2
  while [ "$(docker ps -q --filter name=mu-79409fb | wc -l)" -gt 0 ]; do sleep 30; done
  echo "DOCKER_PS before $name:"; docker ps --format '{{.Names}} {{.Image}} {{.Status}}'
  echo "RUN $name start $(date +%T) $(date +%s)"
  yes | harbor run --path "$path" --agent oracle --env docker --job-name "$name" --jobs-dir "$J" -y > "$L/$name.out" 2>&1
  echo "RUN $name rc=$? end $(date +%T) $(date +%s)"
}

sampler &
SPID=$!
run oracle-1 oracle
run blind-d5c7b9d d5c7b9d
run blind-f4f4ff5 f4f4ff5
run blind-4d36b26 4d36b26
kill $SPID
rm -rf "$LOCK"
echo ALL_DONE
