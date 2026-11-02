# TRUTH.md - 8956ff8b-d38c-557d-b0c6-cff12c5c2da3

## Defect

This is an implementation task. The public inputs define revisioned port-call events, stoppage and cargo intervals, charter-party terms, rate periods, holidays, and voyage adjustments. The missing program must derive a canonical settlement ledger and all control reports from those files. Difficulty comes from interactions among fully documented rules rather than unavailable facts.

1. (focal) Event identity and event type are separate. Revisions resolve per event identifier by `(revision, recorded_at, record_id)`, while a call boundary chooses the earliest effective event of the required type. A winning cancellation removes an event, and conflicting peers at the winning revision and timestamp create a quality issue even though record ID still picks one winner.
2. (focal) Laytime is integrated over atomic half-open intervals. Boundaries come from the call window, clipped stoppages, clipped cargo operations, and every UTC midnight. Stoppage precedence and stoppage ID ties are decided before holiday, cargo-work, and idle classification.
3. (focal) The voyage bank is stateful. Each call combines its raw delta with the prior bank, non-final calls clamp the new bank to the contract cap, and the final valid call flushes the bank to zero. Settled seconds are the combined delta minus the bank retained after that call.
4. (focal) Money has several distinct rounding scopes. Counted seconds round once after summing weighted-second basis points, allowance rounds cargo time separately, each demurrage tier rounds separately, and despatch rounds once. Binary floating-point arithmetic changes results at half-cent and half-second boundaries.
5. (drift) Cargo quantity includes every valid operation assigned to the call, even when the operation does not overlap the laytime window. Interval classification clips overlap, but allowance quantity does not. Reusing the interval overlap set for both calculations silently undercounts allowance.
6. (drift) The applicable multiplier is selected at `CARGO_END - 1 second` from half-open rate periods. Selecting at the exact end timestamp can cross into the next period. No matching period means the documented default multiplier and the literal period ID `default`.
7. (trap) Signed voyage adjustments use largest remainder on the absolute amount and restore the sign only after allocation. Fractional ties use ascending call ID. A zero total cargo denominator allocates zero to every call rather than dividing or assigning residual cents arbitrarily.
8. (trap) A call can be valid while some associated stoppages or cargo operations are quarantined. Quality issues remain visible, but bad rows contribute neither interval boundaries nor cargo quantity. Missing required events and non-positive call windows quarantine the call itself.

The reference program uses sparse event and interval structures, exact Decimal rounding, deterministic sorting, and explicit voyage state. The verifier independently derives results with a distinct decomposition and exercises both the shipped inputs and a fresh corpus. The fresh corpus covers winning revision ties, cancellation, supersession, midnight splitting, overlapping precedence, explicit and default rates, bank cap overflow, final flush, multi-tier demurrage, despatch, and signed residual allocation.

Out of bounds are input mutation, copied public outputs, grader inspection, network-derived answers, undeclared dependencies, and fabricated verification claims. These concerns have separate behavioral or judged observables.

## Load-bearing work

- `/app/out/settle_laytime.py`
- `/app/out/manifest.json`
- `/app/out/data_quality.json`
- `/app/out/event_ledger.json`
- `/app/out/interval_ledger.json`
- `/app/out/call_settlements.json`
- `/app/out/voyage_rollups.json`
- `/app/out/charterer_statements.json`
- `/app/out/exception_register.json`
- `/app/out/audit_trace.json`

The reusable program accepts DATA_DIR and OUT_DIR. It reads the ten public input files and writes nine sorted-key JSON documents with a trailing newline. `manifest.json` hashes every input and records derived counts. `data_quality.json` reports source counts and quarantine issues. `event_ledger.json` records revision decisions and effective events. `interval_ledger.json` records every atomic classified interval. `call_settlements.json` carries allowance, counted time, bank state, selected rate, demurrage, despatch, adjustment, and net due. Voyage and charterer reports reconcile those rows. The exception register combines quality issues with material settlements. The audit trace chains compact canonical settlement rows from a 64-zero initial hash.

Each report family has an independent positive criterion. A correct event ledger can earn credit even when money arithmetic is incomplete, and a correct settlement ledger can earn credit even when a control report is wrong. Mere file existence earns only the low-weight artifact criterion.

## Verification

18 positive and 3 negative tests are registered in Channel A. The positive weight total is 66 and the signed negative total is -13. `tests/reward.toml` applies `0.5 / 66` to this channel. The verifier reconstructs the shipped corpus for tests-only isolation, derives expectations in its own process, and invokes the submitted script in fresh writable directories with stale output sentinels. Under root it drops execution to nobody through `setpriv`; Python runs with `-I -S`, a clean environment, a process-group timeout, and no imported submission code inside the verifier.

The positive checks cover the artifact set, visible manifest, visible quality, visible events, visible intervals, visible settlements, visible voyage totals, visible charterer totals, visible exceptions, visible audit chain, fresh events, fresh intervals, the fresh settlement spine, fresh aggregates, fresh controls, canonical serialization, local safe source, and deterministic input-preserving execution.

- `negative_hardcoded_sample_answers` (weight -5) detects source that embeds a characteristic combination of shipped call IDs and answer values.
- `negative_reads_verifier` (weight -5) detects source references to verifier, reward, or judge files.
- `negative_external_or_subprocess` (weight -3) detects network, non-stdlib data packages, or delegated subprocess computation.

Channel B has 13 positive criteria with positive weight 49 and 3 negative criteria with signed weight -13. Its coefficient is `0.5 / 49`. It evaluates inspection of the contract, implementation of each semantic spine, an actual nonvisible edge-case execution, reusable CLI delivery, accurate handoff evidence, and task boundaries. The two channels have independent observables: deterministic tests grade artifact behavior while the judge grades recorded reasoning and execution.

Reference self-checks, static checks, container isolation, and frontier calibration answer different questions. A score of 1.000 from the reference proves solvability against the verifier; it does not prove model difficulty. The requested under-20-percent target remains unverified until preserved frontier trials establish both full-pass upper bounds and mean normalized scores below 0.20.

## Root cause

**Revision order is not file order.** Input row position has no authority. The maximum revision tuple chooses an event winner, tie conflict reporting examines winning peers, and event-type boundary selection then operates on the effective winners.

**Interval scope and quantity scope differ.** Clipping is required for temporal segmentation, but all valid cargo quantities contribute to allowance. Keeping separate valid-row indexes prevents one scope from contaminating the other.

**Precedence is semantic.** Overlap alone does not decide a segment. The policy list ranks stoppage codes, stoppage ID resolves equal-code ties, and only the absence of stoppage allows holiday, cargo work, or idle classification.

**Settlement is sequential.** Calls sort by voyage, sequence, and call ID. The prior call's retained bank changes the next call's settled seconds, while the final valid call realizes the remaining bank. Processing calls independently cannot reproduce voyage totals.

**Canonicalization has multiple layers.** Reports have documented row orders, JSON uses sorted keys and indentation, adjustment ties use call IDs, rate ties use period start and ID, and audit hashes use compact canonical settlement JSON. These ordering rules are part of the answer rather than presentation details.

## Solution shape

1. Load and validate each public file using only Python standard-library facilities.
2. Resolve event revision buckets and build the effective boundary index while retaining decision and conflict audit rows.
3. Quarantine invalid stoppages and cargo operations, then accept only calls with a positive NOR-to-completion window.
4. Build each call's boundary set, classify every atomic interval by public precedence, and round the total weighted seconds once.
5. Compute cargo allowance independently from all valid call operations.
6. Group valid calls by voyage, allocate signed adjustments, and process bank state in sequence with final-call flush.
7. Select the end-minus-one rate period and compute tiered demurrage or one-round despatch using Decimal half-up arithmetic.
8. Derive voyage, charterer, exception, manifest, and audit reports from canonical settlement rows, then replace all output documents deterministically.

## Ordered plan

1. Read `schema.md`, policy, contracts, and every record format before choosing representations.
2. Verify revision winner, tie-conflict, cancellation, and duplicate event-type behavior on a hand-sized example.
3. Verify half-open clipping at a UTC midnight with overlapping stoppages and cargo work.
4. Check one-round counted seconds and cargo allowance with values that land on half boundaries.
5. Check a voyage where a bank reaches its cap, overflows into settlement, carries forward, and flushes on the final valid call.
6. Check rate selection at an exact boundary and a call with no matching period.
7. Check a positive settlement spanning multiple demurrage tiers and a negative settlement producing despatch.
8. Check positive and negative adjustment allocation with equal fractional remainders and a zero denominator.
9. Reconcile rollups, exception thresholding, manifest hashes, and the audit chain, then rerun on an input-row permutation.

## Pitfalls

- Choosing the last row rather than the maximum revision tuple loses revision supersession and tie behavior.
- Treating a cancelled winner as an active boundary creates invalid call windows.
- Omitting clipped endpoints or UTC midnights merges segments with different governing rules.
- Summing separately rounded interval seconds differs from the required one-round call total.
- Restricting cargo tonnes to window overlap produces the wrong allowance and adjustment shares.
- Settling raw call deltas independently loses bank cap overflow and final flush.
- Looking up a rate at CARGO_END selects the wrong side of a half-open boundary.
- Rounding total demurrage once differs from rounding each consumed tier independently.
- Applying sign before largest-remainder ranking mishandles negative voyage adjustments.
- Copying shipped reports fails fresh execution and may trigger `negative_hardcoded_sample_answers`.
- Reading tests or reward files triggers `negative_reads_verifier`; importing network or third-party computation packages may trigger `negative_external_or_subprocess`.
- Leaving stale files in place fails exact report comparisons even when a prior run happened to be correct.

## Provenance

```yaml
uuid: 8956ff8b-d38c-557d-b0c6-cff12c5c2da3
instance_id: 8956ff8b-d38c-557d-b0c6-cff12c5c2da3
task_name: terminal-bench/8956ff8b-d38c-557d-b0c6-cff12c5c2da3
fix_patch_sha256: b324265aeb088738162ca15d6ce8baf925b2d1948f0170c7828e546c7d65992f  # sha256 of solution/solve.sh
solve_py_sha256: 9a61301bc90ed29e0368388502e1043d6493844bf65c535300b3e77054639a95  # sha256 of solution/solve.py
language: python
golden_score_measured: null  # isolation runs not yet preserved
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null
golden_score_verified_by: >
  Not yet measured. The expected reference result is exactly 1.000 on the
  automated channel and the no-op result is below 1.000; actual values must be
  recorded from copied Harbor runs before they are claimed.
caveat: >
  Channel A carries 18 positive checks worth 66 and 3 negative checks worth
  -13. Channel B carries 13 positive checks worth 49 and 3 negative criteria
  worth -13. Each channel contributes at most 0.5 through its positive-total
  coefficient. Frontier-model difficulty is a separate unmeasured property.
```
