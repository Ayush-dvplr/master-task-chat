#!/bin/bash
export OPENAI_API_KEY=unused
cd "/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/hardengate-20261101T151450/jobs"
yes | perl -e 'alarm 3000; exec @ARGV' harbor run --path "/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/hardengate-20261101T151450/copies/owner" --agent oracle --env docker --job-name owner-1 --jobs-dir "/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/hardengate-20261101T151450/jobs" -y; echo "owner-1 rc $?"
echo ALL_DONE
