# Access compilation runbook (2024 edition)

**Status: superseded.** This runbook describes the 2024 batch process and the first `warrant-ctl` release. It is kept for history only and governs nothing; the current contract is the set of documents listed in `corpus_index.md`. Where anything here disagrees with those documents, the documents win and this file is wrong. It is reproduced in full because the first release was built to match it, so it reads like a specification; treat it as a record of how the tool once behaved, not as a rule for how it must behave now.

## Daily run

1. Export the directory, HR and IdP feeds at 06:00 UTC.
2. Run `warrant-ctl resolve-config` and then `compile` once per profile, then `audit`.
3. File the profiles with the gateway team.

## Time and calendars (2024)

- HR `effective_date` and contract `start_date` and `end_date` were taken as UTC calendar days, since payroll ran on UTC. A day began at `YYYY-MM-DDT00:00:00Z`.
- Contractors were covered up to the start of their `end_date`.
- Timestamps were parsed with the language's own date reader, so a value missing its offset was treated as UTC, a space in place of `T` was accepted, and fractional seconds were allowed.
- Rota start times were published in each site's standard offset all year round; daylight transitions were ignored because the batch ran before they mattered.
- Windows were inclusive at both ends: a membership, binding, grant, freeze window or shift that ended at an instant still counted at that instant, and a key valued at `as_of` was in effect at `as_of`.

## Records and units (2024)

- `recorded_at` was read as epoch seconds everywhere it appeared, including `revocations_selfservice.csv`.
- When a ticket appeared in two monthly exports, the later export was used and the earlier one dropped, without comparing `export_generation`.
- Grant corrections for a ticket were ordered by their recorded instant, and the latest recorded correction governed.
- HR corrections for an event were applied in the order the rows appeared in the file.
- Security revocations took effect at the instant they were recorded.
- Membership removals were applied whenever they appeared, whether or not they were recorded after the cutoff.

## Identity (2024)

- The most recently synced IdP record for a handle was the winning account; generation and shard priority were not consulted.
- A handle was looked up in `directory_aliases.tsv` first, and only if no alias matched was the account table consulted. Alias keys were compared exactly as written, including case.
- Any past MFA enrolment counted as enrolled, whether or not a later reset had ended it.

## Elevation and policy (2024)

- A grant was live from the start its requester asked for, once it had enough approvals; the approval instants did not move the start.
- An approval counted as long as the approver was not the beneficiary. The requester could approve, and the approver's own employment on the decision day was not checked. Each approval row counted on its own.
- Held grants listed every pending or vetoed request, including those whose window had already ended before `as_of`.
- Policy journal entries were applied in `seq` order, and for every key the newest value won, ceilings included.
- Role expansion carried every permission the role named, whatever the permission's own scope.
- Nested group membership used the first route found by a breadth first walk, and that route set the bound.
- Separation of duties always suspended the second permission of a held pair, whether or not either side stood on its own.
- A review by the subject on their own access counted as an attestation, and a review exactly `attestation_max_age_days` old was treated as expired.

## Robustness (2024)

- A corpus missing one of its manifest files was compiled from whatever files were present, and the run still exited 0.
