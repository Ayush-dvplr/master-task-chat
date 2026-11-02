#!/bin/bash
cd /tmp/score_d07903b
echo "d07903b $$ $(date)" > /tmp/opencode-logs/locks/metered-usage-rating-pipeline.lock
export OPENAI_API_KEY=unused
for s in oracle 6f5046a 204228e ebaba1c; do
  echo "=== START $s $(date +%T)"
  yes | harbor run --path /tmp/score_d07903b/$s --agent oracle --env docker --job-name d07903b-$s -y > run_$s.log 2>&1
  echo "=== END $s rc=$? $(date +%T)"
done
rm -f /tmp/opencode-logs/locks/metered-usage-rating-pipeline.lock
echo ALL_DONE
