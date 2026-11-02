# TRUTH.md - 9bb234eb-e964-5e0b-b8a9-37e9d58b887c

## Defect

- (focal) A solver must reconstruct effective service from a revision ledger. Maximum revision, UTC recording time, and record ID form the winner key. Equal-rank payload disagreement is reported while the record-ID tie break remains deterministic. Cancellation removes the service from accrual without removing its decision history.
- (focal) Service accrual is not a row total. Each effective interval is partitioned at salary, leave, calendar-year, valuation, and service boundaries. Half-open containment and missing-salary quarantine determine which atoms survive.
- (focal) Credited days and atom accrual cents have separate ROUND_HALF_UP boundaries. Salary is capped before accrual, overlapping leave uses the minimum factor, and every atom is rounded independently.
- (focal) Accrual, plan COLA, and member rebase events share one chronological state machine. Equal-date ordering is ACCRUAL, then COLA, then REBASE. Each multiplier rounds the current balance before the next event.
- (focal) Retirement age is measured in completed calendar months with a day-of-month correction. Early reduction and election option factors are applied sequentially with independent cent rounding.
- (focal) Nine reports must agree on effective service, atom counts, member balances, plan totals, exceptions, and a canonical audit chain while the manifest hashes every input byte.
- (drift) Hardcoded shipped members can appear plausible but fail new revision peers, leave overlaps, election changes, salary caps, and valuation dates.
- (drift) Floating point, inclusive date ends, aggregate-before-rounding, or revaluation after all accruals silently changes exact cents.
- (trap) A program can emit parseable JSON and still violate exact top-level keys, row keys, ordering, canonical formatting, or audit provenance.
- (trap) A solution may validate only the supplied extract and overstate generality without independent expected-value checks on fresh interactions.

## Load-bearing work

The delivered program is `/app/out/calculate_pension.py`. It accepts exactly `DATA_DIR OUT_DIR` and writes the nine required JSON reports. `manifest.json` inventories all ten regular input files and records valid-member, effective-service, and atom counts. `data_quality.json` reports raw-family counts and sorted issues. `service_ledger.json` preserves revision decisions separately from exact-schema effective rows. `accrual_ledger.json` records every partitioned atom and both rounding stages. `cola_ledger.json` exposes every multiplier transition. `member_benefits.json` connects credited service, base accrual, revaluation, election arithmetic, and payable cents. `plan_rollups.json` aggregates the final member rows. `exception_register.json` combines quality findings with material benefits. `audit_trace.json` chains canonical member rows.

Channel A contains twelve positive criteria with total weight 52. `artifact_set` has weight 1. Eight independent fresh scenarios each have weight 5 and each compares one complete nine-report bundle: `scenario_revision_tie`, `scenario_overlapping_leave`, `scenario_missing_salary`, `scenario_same_day_order`, `scenario_salary_cap`, `scenario_election_day`, `scenario_multiple_elections`, and `scenario_valuation_clip`. `canonical_serialization` and `local_safe_source` each have weight 3. `deterministic_no_mutation` has weight 5. The one-observable-per-scenario design prevents a single fixture from being split into many correlated scoring events.

Channel A also has three behavioral negatives: `negative_hardcoded_sample_answers` at -5, `negative_reads_verifier` at -5, and `negative_external_or_subprocess` at -3. These penalize actual prohibited behavior rather than ordinary implementation choices. The test channel coefficient is 0.5/52.

Channel B contains fourteen positive criteria with total weight 56 and three negatives with magnitude 13. It evaluates trajectory evidence, not report bytes. The positives cover contract inspection, revision reasoning, half-open partitioning, leave precedence, accrual arithmetic, event ordering, election arithmetic, fresh expected-value assertions, exact schema checks, manifest and audit recomputation, deterministic immutable execution, reusable CLI delivery, local standard-library work, and factual reporting. The negatives cover sample-specific hardcoding, grader access, and unsupported validation claims. The judge coefficient is 0.5/56.

## Verification

The owner solution must first compile in memory and run against the shipped data. It must create exactly the nine reports and the reusable script. Wrong arity must print usage and exit 2. Each report must parse and must equal its canonical sorted-key, two-space, newline-terminated serialization.

The independent verifier embeds the input bytes and creates eight contract-grounded extracts. Every scenario is run in a fresh temporary directory under isolated Python with `-I -S`, a clean environment, stale output sentinels, process-group timeout, and privilege drop to nobody when available. The scenario hash covers report names and all nine report bytes. Determinism runs the same fresh case twice and checks that every input digest remains unchanged.

Mechanical acceptance requires structure, instruction, tests, and judge QC to return zero. Generator static validation must accept the registered artifact manifest. Semantic validation must yield nop 0 and oracle 1. Step 10 requires five independent oracle scores of 1, nop 0, owner-only 1, and a meaningfully low stub. A real model score is evidence only when the trajectory, both reward channels, and null exception are present. Infrastructure failures are exclusions.

No frontier score is claimed in this truth record. Difficulty is established only by measured valid trajectories after all fairness and QC gates pass.

## Root cause

The difficulty comes from interacting documented rules rather than missing information. Revision selection changes the service intervals that enter partitioning. Partitioning changes which salary and leave rows cover an atom. Atom-level rounding changes the base amounts that enter a chronological state machine. Event order changes the balance that later factors multiply. Election day arithmetic changes completed age months, early-reduction basis points, and two subsequent roundings. Finally, all those decisions must remain mutually consistent across ledgers, rollups, exceptions, hashes, and manifests.

A shallow implementation often gets the supplied totals near the reference while losing exactness at one of these seams. A robust implementation must model each stage explicitly and validate it with independent calculations. The task does not require external pension knowledge: every rule, schema, and precedence is in `schema.md`.

## Solution shape

The reference reads JSON and JSONL with the Python standard library. It resolves services by a grouped deterministic ordering and stores both decisions and active winners. It validates members and every non-revision input family at the boundary. For each service it constructs a set of cut dates, sorts them, selects fully covering salary and leave rows, and computes atom fields with Decimal half-up rounding.

The reference then builds a per-member event stream. Accrual posts at atom end; COLA and rebase rows multiply the balance. A numeric kind order guarantees equal-date semantics. The final member calculation chooses the latest election, computes completed age months, applies capped early reduction, applies the election option, and emits one exact row. Plan aggregation and material exceptions derive only from those rows. The audit chain hashes compact canonical member JSON after prefixing the previous hash.

The verifier deliberately has a different decomposition and never imports the owner solution. Fresh expected hashes are derived from the documented contract and frozen only after direct oracle execution. A scenario is scored once as one whole-bundle observable.

## Ordered plan

1. Read `schema.md`, then inventory all ten inputs and exact nine report schemas.
2. Parse and validate plans and members; preserve stable string identifiers.
3. Resolve service revisions and record deterministic decisions and conflicts.
4. Validate salaries, leaves, COLAs, rebases, and elections; quarantine invalid rows.
5. Partition service into half-open atoms and perform both named rounding operations.
6. Process each member event stream with the required same-date kind order.
7. Select elections and independently apply age, reduction, and option arithmetic.
8. Build benefits, rollups, exceptions, manifest, and audit trace from canonical rows.
9. Serialize every report deterministically and run the reusable CLI on the shipped extract.
10. Validate fresh revision, overlap, missing-data, ordering, cap, election, and valuation cases with independently calculated expected values.
11. Repeat with reordered JSONL data and compare every output and input byte.

## Pitfalls

- Treating date ends as inclusive creates duplicate days at boundaries.
- Selecting any overlapping salary rather than a fully covering latest-start salary changes atoms.
- Summing fractional credited days before rounding violates the per-atom boundary.
- Applying COLA to final total rather than the balance at its effective date changes results.
- Sorting equal-date events alphabetically places COLA before ACCRUAL.
- Computing age months without the retirement-day comparison overstates age near birthdays.
- Combining reduction and option into one fraction removes an explicit cent rounding.
- Omitting cancelled service decisions makes the ledger incomplete.
- Hashing pretty JSON rather than compact canonical JSON breaks the audit chain.
- Assuming row order conveys precedence makes fresh reordered extracts nondeterministic.
- Claiming verification from printed outputs without explicit expected-value assertions is insufficient trajectory evidence.

## Provenance

```yaml
uuid: 9bb234eb-e964-5e0b-b8a9-37e9d58b887c
instance_id: 9bb234eb-e964-5e0b-b8a9-37e9d58b887c
task_name: terminal-bench/9bb234eb-e964-5e0b-b8a9-37e9d58b887c
fix_patch_sha256: 03e366e50c5334068ad183728dd4aa6448bba18b1d0e59ee0703df4936144510
solve_py_sha256: 54d769f930f60f85de338e72246bc0e3e3de5f6da0157712f51a939fcc2cfc23
language: python
golden_test_score: 1.0
golden_judge_score: 1.0
calibration_status: unmeasured
calibration_caveat: No model difficulty claim is made until valid post-QC trajectories are measured.
```
