#!/bin/bash
export OPENAI_API_KEY=unused
cd "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/hardengate4-20261101T230955/jobs"
yes | perl -e 'alarm 2400; exec @ARGV' harbor run --path "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/hardengate4-20261101T230955/copies/owner" --agent oracle --env docker --job-name owner-1 --jobs-dir "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/hardengate4-20261101T230955/jobs" -y; echo "owner-1 rc $?"
echo LANE_DONE
echo ALL_DONE
