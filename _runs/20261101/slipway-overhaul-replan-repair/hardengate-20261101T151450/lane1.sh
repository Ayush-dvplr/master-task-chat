#!/bin/bash
export OPENAI_API_KEY=unused
cd "/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/hardengate-20261101T151450/jobs"
for i in 1 2 3; do yes | perl -e 'alarm 3000; exec @ARGV' harbor run --path "/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/hardengate-20261101T151450/copies/plain" --agent oracle --env docker --job-name oracle-$i --jobs-dir "/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/hardengate-20261101T151450/jobs" -y; echo "oracle-$i rc $?"; done
echo ALL_DONE
