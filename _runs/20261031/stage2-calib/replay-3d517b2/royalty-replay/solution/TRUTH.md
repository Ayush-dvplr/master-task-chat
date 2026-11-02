# TRUTH.md - 75407a55-6665-505e-95d8-5ff9bdb3384f

## Defect

- (focal) Effective royalty statements come from a revision ledger. Revision, recording timestamp, and record ID form the winner key. Equal-rank disagreement is reported, cancellation removes the effective statement, and every decision remains visible.
- (focal) Currency conversion, territory withholding, and distributor fee are three ordered calculations. Conversion, withholding, and fee each use the contract's separate ROUND_HALF_UP boundary; aggregating first changes cents.
- (focal) Project recoupment pools are stateful across policy periods. Priority order and prior closing balances determine which pool receives each cent and how much remains distributable.
- (focal) Participant allocation is not ordinary integer division. Floors are assigned first, residual cents follow descending fractional remainder and participant-ID tie break, and the result must conserve distributable cents exactly.
- (focal) Participant advances form a second stateful priority waterfall after allocation. Adjustments are signed and apply only after advance recoupment, so they never replenish project pools or advances.
- (focal) Nine reports must agree on effective statements, project-period balances, participant payments, rollups, exceptions, input digests, and a canonical audit chain.
- (drift) A shipped-only implementation can appear correct while failing revised statements, midpoint rounding, changed priorities, allocation ties, and signed adjustments.
- (drift) Binary floating point, aggregate-before-rounding, or resetting balances every period silently changes exact cents.
- (trap) Parseable JSON can still violate exact top-level keys, row keys, sorting, canonical formatting, or audit provenance.
- (trap) Printed synthetic output is not independent validation; load-bearing interactions require explicit expected-value assertions.

## Load-bearing work

The delivered program is `/app/out/calculate_royalties.py`. It accepts exactly `DATA_DIR OUT_DIR` and writes nine JSON reports. `manifest.json` inventories all ten input files and core counts. `data_quality.json` reports raw-family counts and deterministic quarantine issues. `statement_ledger.json` preserves revision decisions and exposes exact per-statement arithmetic. `waterfall_ledger.json` records every project-period from gross through distributable cents. `recoupment_ledger.json` exposes opening, recouped, and closing balances for both stateful waterfalls. `participant_statements.json` shows allocation, advance, adjustment, and final payable arithmetic. `project_rollups.json` reconciles all periods. `exception_register.json` combines quality findings with material payments. `audit_trace.json` chains canonical participant statements.

Channel A has twelve positive criteria totaling 52. `artifact_set` has weight 1. Eight independent fresh scenarios each have weight 5 and compare one complete nine-report bundle: `scenario_revision_tie`, `scenario_fx_half_up`, `scenario_withholding_half_up`, `scenario_pool_priority`, `scenario_largest_remainder`, `scenario_advance_priority`, `scenario_period_carry`, and `scenario_signed_adjustment`. `canonical_serialization` and `local_safe_source` each have weight 3. `deterministic_no_mutation` has weight 5. One whole-bundle observable per scenario prevents correlated report fragments from multiplying a single defect.

Channel A also has three behavioral negatives: `negative_hardcoded_sample_answers` at -5, `negative_reads_verifier` at -5, and `negative_external_or_subprocess` at -3. The test coefficient is 0.5/52.

Channel B has fourteen positive criteria totaling 56 and three negatives with magnitude 13. It evaluates trajectory evidence rather than report bytes. Positives cover contract inspection, revisions, per-statement arithmetic, project recoupment, largest remainder, advance recoupment, signed adjustments, fresh expected-value assertions, exact report schemas, manifest and audit recomputation, immutable deterministic execution, reusable CLI delivery, local standard-library work, and factual completion reporting. Negatives cover sample-specific hardcoding, grader access, and unsupported validation claims. The judge coefficient is 0.5/56.

## Verification

The owner solution must compile in memory and run on shipped data. It must create the reusable script and exactly nine reports. Wrong arity prints usage and exits 2. Every report must parse and equal sorted-key, two-space, newline-terminated serialization.

The independent verifier embeds all ten input bytes and creates eight contract-grounded extracts. Each runs in a fresh directory under isolated Python with `-I -S`, clean environment, stale-output sentinels, process-group timeout, and privilege drop when available. Each scenario hash covers report names and every report byte. Determinism runs the same fresh case twice and verifies every input digest is unchanged.

Mechanical acceptance requires structure, instruction, tests, and judge QC exit zero. Generator static validation must recognize the registered artifact manifest. Semantic validation must yield nop 0 and oracle 1. Step 10 requires five oracle scores of 1, nop 0, owner-only 1, and a meaningfully low stub. A model score is evidence only when trajectory, both reward channels, and null exception exist; infrastructure failures are excluded.

No model difficulty score is claimed in this truth record. Calibration is established only by valid post-QC trajectories and exact stored evidence.

## Root cause

Difficulty comes from documented interactions. Revision resolution determines which amounts enter conversion. Per-statement rounding determines period net receipts. Period receipts enter priority project pools whose closing balances feed later periods. Remaining cents enter a largest-remainder allocator, then participant-specific priority advances, then signed adjustments. Every stage must reconcile across ledgers, rollups, exceptions, and hashes.

A shallow implementation often gets total revenue close while missing one explicit boundary. A robust implementation models statement arithmetic and both state machines separately, conserves cents after allocation, and validates independent scenarios. No external royalty-accounting knowledge is needed because every rule and schema is in `schema.md`.

## Solution shape

The reference uses only Python standard-library JSON, Decimal, datetime, hashing, collections, and paths. It groups revisions, resolves deterministic winners, validates all boundary inputs, and derives statement rows. It processes projects and every policy period in stable order, mutating pool balances only through explicit priority loops.

For each project-period it computes allocation floors and fractional remainders, distributes residual cents deterministically, then walks each participant's advances. Adjustments are looked up after recoupment. Rollups derive from final ledgers rather than separate formulas. The audit chain hashes compact canonical participant rows after prefixing the previous hash.

The verifier has a different decomposition and never imports the owner solution. Frozen hashes are generated only after direct reference execution against documented scenario mutations. Each scenario receives one score regardless of how many reports expose its behavior.

## Ordered plan

1. Read `schema.md`, inventory ten inputs, and record exact nine-report schemas.
2. Parse contracts, FX, territory rules, and policy periods.
3. Resolve statement revisions and preserve decisions and conflicts.
4. Validate and quarantine statements, pools, allocations, advances, and adjustments.
5. Perform conversion, withholding, and fee arithmetic at separate rounding boundaries.
6. Process project pools chronologically by explicit priority.
7. Allocate distributable cents with floor, fractional rank, and residual conservation.
8. Process participant advances, then apply signed adjustments.
9. Build rollups, exceptions, manifest, and canonical audit chain.
10. Serialize deterministically and execute the reusable CLI on shipped data.
11. Assert independent expected values for fresh revision, midpoint, priority, carry, allocation, and adjustment cases.
12. Reorder JSONL rows, compare every output byte, and verify every input byte.

## Pitfalls

- Comparing timestamps as local time instead of parsed UTC can select the wrong revision.
- Treating a cancelled winner as an effective zero row changes counts and decisions.
- Aggregating foreign amounts before conversion removes per-statement rounding.
- Charging the distributor fee on gross instead of gross minus withholding changes cents.
- Processing only periods containing statements loses zero-period balance evidence.
- Resetting a pool or advance each period defeats recoupment state.
- Rounding proportional shares independently can create or destroy cents.
- Sorting largest-remainder ties by input order is nondeterministic.
- Applying adjustments before advances incorrectly recoups an adjustment.
- Omitting zero participant rows breaks period completeness and audit order.
- Hashing pretty JSON rather than compact canonical JSON breaks the audit chain.
- Claiming broad validation from printed values without assertions is insufficient evidence.

## Provenance

```yaml
uuid: 75407a55-6665-505e-95d8-5ff9bdb3384f
instance_id: 75407a55-6665-505e-95d8-5ff9bdb3384f
task_name: terminal-bench/75407a55-6665-505e-95d8-5ff9bdb3384f
fix_patch_sha256: 6c07d2afec9db3bb4813fade96f0c81892e5b56508593b0cb55982ed84fdb2e1
solve_py_sha256: 9b72a95467ba956606519624e10f7835ce58afef1dc7a5c8ba0a425633614cad
language: python
golden_test_score: 1.0
golden_judge_score: 1.0
calibration_status: unmeasured
calibration_caveat: No model difficulty claim is made until valid post-QC trajectories are measured.
```
