# Batch Operations Runbook

Maintained by the on-call rotation of Legacy Batch and Platform Reliability. Last reviewed before settlement
contract revision 7.

## Who to page

The owning team of a job is whatever CODEOWNERS says for `jobs/<job name>`. Page the on-call person of that team from
the rota calendar. If the rota has no one for the slot, escalate to the team lead listed in the directory.

## Clock changes

Twice a year the scheduler hosts change their wall clocks. Jobs scheduled inside the hour that is skipped in spring do
not run that day, so do not chase a missing run for them. In autumn the repeated hour runs twice, and both runs are
expected; the second run normally overwrites the first partition.

## Clock drift on worker hosts

Worker hosts drift. The drift exporter publishes `node_timex_offset_seconds`, and heartbeats give the same thing for
the pools that do not run the exporter. When comparing a worker log line with the scheduler, subtract the host offset
from the worker stamp.

## Re-landed partitions

A partition that lands again after a failed quality check is judged on the latest landing, because the latest landing
is the data consumers actually read. Deletions from the admin console are housekeeping and do not change availability
on their own.

## Manual completion

When a run cannot finish but the data is known to be good, an operator may record `mark_success` in the audit tool.
Get an approval on the mail thread for the interval first. Any approval on the thread is enough for settlement to
accept the mark.

## Dependency waits

A downstream run waits for the upstream run scheduled at or before its own scheduled time. With a lag of one it waits
for the run before that.

## Pauses

Pause a job from the console before maintenance and unpause it afterwards. Pausing a job that is already paused does
nothing. Settlement does not charge intervals whose nominal time falls while the job is paused.

## Backfills

Backfill runs are requested from the console and listed in the backfill export. Their landings are real landings. Do
not use a backfill's worker commit or scheduler success as proof that the scheduled run finished.

## Outages

Status page items are revised in place: always read the latest revision. A retracted outage excuses nothing.
