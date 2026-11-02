#!/bin/zsh
cd /tmp/cohort-p12r2-20261023T105600-904b/run/tests && docker build --progress plain -t warm-cohort-retention-reconciliation . > /tmp/opencode-logs/cohort-retention-reconciliation-p12r2-20261023T105600-904b/warm.log 2>&1; echo WARM_RC=$? >> /tmp/opencode-logs/cohort-retention-reconciliation-p12r2-20261023T105600-904b/warm.log
for n in 1 2 3; do echo "=== oracle-$n $(date)"; harbor run --path /tmp/cohort-p12r2-20261023T105600-904b/run --agent oracle --env docker --jobs-dir /tmp/harbor-jobs-p12r2/cohort-retention-reconciliation-20261023T105600-904b --job-name oracle-$n -y; echo rc=$?; done
echo "=== owner-only-1 $(date)"; harbor run --path /tmp/cohort-p12r2-20261023T105600-904b/owner --agent oracle --env docker --jobs-dir /tmp/harbor-jobs-p12r2/cohort-retention-reconciliation-20261023T105600-904b --job-name owner-only-1 -y; echo rc=$?
echo "=== nop-1 $(date)"; harbor run --path /tmp/cohort-p12r2-20261023T105600-904b/run --agent nop --env docker --jobs-dir /tmp/harbor-jobs-p12r2/cohort-retention-reconciliation-20261023T105600-904b --job-name nop-1 -y; echo rc=$?
echo ALL_DONE $(date)
