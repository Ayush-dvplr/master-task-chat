#!/bin/bash
export OPENAI_API_KEY=unused
cd "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/hardengate-20261101T121818/jobs"
yes | perl -e 'alarm 2400; exec @ARGV' harbor run --path "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/hardengate-20261101T121818/copies/plain" --agent nop --env docker --job-name nop-1 --jobs-dir "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/hardengate-20261101T121818/jobs" -y; echo "nop-1 rc $?"
yes | perl -e 'alarm 2400; exec @ARGV' harbor run --path "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/hardengate-20261101T121818/copies/stub" --agent oracle --env docker --job-name stub-1 --jobs-dir "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/hardengate-20261101T121818/jobs" -y; echo "stub-1 rc $?"
yes | perl -e 'alarm 2400; exec @ARGV' harbor run --path "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/hardengate-20261101T121818/copies/forgery" --agent oracle --env docker --job-name forgery-1 --jobs-dir "/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/hardengate-20261101T121818/jobs" -y; echo "forgery-1 rc $?"
echo LANE_DONE
echo ALL_DONE
