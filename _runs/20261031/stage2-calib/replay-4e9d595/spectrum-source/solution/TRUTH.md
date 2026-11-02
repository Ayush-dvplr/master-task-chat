# TRUTH.md - fa7c65bd-ff01-50e7-b3ba-34fbd5df860d

## Defect

This task is a greenfield deterministic data-processing contract rather than a repair of a broken application. The implementation must transform ten flat files into a reusable command and nine exact reports. Difficulty comes from the interaction of revisioned records, half-open geometry in three dimensions, precedence, and exact money allocation. Every rule is documented in `environment/data/schema.md`; hidden evaluation changes values and row order but introduces no hidden semantics.

0. (focal) Grant and auction rows are revisioned. A winner is selected by `(revision, recorded_at, record_id)`, cancellation removes the effective object, and equal revision plus timestamp peers with different semantic payloads produce a tie-conflict issue even though record ID still resolves the winner. Grant cells are set-valued, so list order alone is not a conflict. Treating the last physical row as authoritative makes results row-order dependent.

1. (focal) A usable license is a half-open time-by-frequency rectangle attached to explicit geographic cells. Guard bands shrink the frequency interval before grants are intersected. Every clipped grant, exclusion, activation, and license boundary contributes cuts. Correct slices conserve the parent rectangle and never double-count a boundary.

2. (focal) Occupancy is selected by documented precedence. Exclusions suppress use, active primary rights preempt subleases, and remaining eligible subleases use the deterministic priority and identifier tie break. A plausible solver that only resolves overlapping grants misses activation windows and produces incorrect preemption rows.

3. (focal) Rates are revisioned and selected using the slice instant and the half-open auction period. Gross cents are derived from integer duration, bandwidth, geographic weight, and the selected cents-per-MHz-hour rate with Decimal `ROUND_HALF_UP` at the contract boundary. Floating point or premature per-factor rounding moves settlement cents.

4. (focal) Winner and owner shares are rounded per slice, not after aggregation. Conservation is defined by the documented residual treatment. Aggregating exact fractions and rounding once can look financially reasonable while disagreeing with every downstream settlement and audit hash.

5. (focal) Corrections are signed and allocated with the absolute largest-remainder method. Floor shares use absolute values, residual cents follow descending fractional remainder and then ascending party ID, and the original sign is restored. Python truncation on negative numbers and signed-remainder sorting both produce subtle errors.

6. (drift) Cargo-like interval intuition is insufficient because spectrum uses frequency and cell dimensions in addition to time. Intersecting only time windows or computing bandwidth at grant level silently bills unusable guard-band spectrum and ignores cell-specific exclusions.

7. (drift) Report order is semantic. Effective grants, slices, preemptions, parties, issues, exceptions, and audit rows each have explicit stable keys. Preserving input order passes casual visible inspection but fails on the reversed fresh JSONL corpus.

8. (trap) Manifest hashes describe the actual input bytes. Most report families are invariant under logically equivalent JSONL row reorderings, while `manifest.json` must change when input bytes change. A blanket byte-identity claim across all reports is therefore false.

9. (trap) Quarantined records remain visible through quality and exception reporting but cannot contribute slices or money. Silently dropping issues, or allowing invalid geometry to reach the cut set, produces internally consistent yet contract-invalid totals.

## Load-bearing work

The delivered command is `/app/out/clear_spectrum.py DATA_DIR OUT_DIR`. `solution/solve.sh` installs the Python reference and invokes it against `/app/data`. The Python implementation uses only the standard library and writes sorted, indented JSON with one trailing newline.

The ten collected artifacts are the reusable command plus:

1. `manifest.json`, containing sorted input file names, byte sizes, SHA-256 digests, and model counts.
2. `data_quality.json`, containing deterministic quarantine and revision-conflict issues.
3. `grant_ledger.json`, containing effective, clipped grant facts.
4. `spectrum_slice_ledger.json`, containing the canonical atomic time-frequency-cell partition and exact financial facts.
5. `preemption_ledger.json`, explaining primary, exclusion, and competing-grant displacement.
6. `party_settlements.json`, aggregating earned, owner, correction, and net cents by party.
7. `auction_adjustments.json`, exposing signed largest-remainder allocations.
8. `exception_register.json`, combining quality issues and material financial exceptions.
9. `audit_trace.json`, forming a SHA-256 chain over canonical compact settlement rows.

Channel A is implemented in `tests/test_output.py`. It contains 12 positive criteria with total weight 52 and three negative criteria with total magnitude 13. Eight independent fresh scenarios each compare the complete nine-report bundle: equal-rank cells-order equivalence, a scalar-field revision conflict, prefix-independent primary activation with two same-party grants counted once per preempted slice, half-open adjacent grants, guard-adjusted abutting grants, a signed correction tie, an exact-half monetary midpoint, and a multi-atom exclusion span. The remaining positives observe the artifact set, canonical serialization, local safe source, and deterministic input-immutable execution. The coefficient in `tests/reward.toml` is `0.5 / 52 = 0.009615384615384616`.

Channel B is implemented in `tests/judge.toml`. It contains 14 positive criteria with total weight 56 and three negative criteria with total magnitude 13. The coefficient is `0.5 / 56 = 0.008928571428571428`. Its positives require trajectory evidence for contract inspection, revision resolution, three-dimensional partitioning, preemption and guard bands, auction and gross arithmetic, share rounding, signed largest remainder, fresh-fixture expectations, artifact schemas, manifest and audit verification, determinism and immutability, the reusable CLI, local standard-library execution, and factual completion reporting. These process observables do not duplicate Channel A's report-byte comparisons.

The automated negative criteria are `negative_hardcoded_sample_answers`, `negative_reads_verifier`, and `negative_external_or_subprocess`. The judged negative criteria are `hardcodes_sample_specific_answers`, `reads_or_modifies_grader_material`, and `claims_unexecuted_validation`. Each penalizes a concrete bypass or unsupported claim; none supplies a hidden implementation rule.

## Verification

The reference verification order is intentionally layered:

1. Compile `solution/solve.py` and `tests/test_output.py` in memory and require clean language-server diagnostics.
2. Execute the reference command on the shipped corpus and require exactly nine nonempty reports.
3. Run the independent behavioral verifier on the reference output and on all eight purpose-built fresh scenarios.
4. Run `structure_qc.py`, `instruction_qc.py`, `tests_qc.py`, and `judge_qc.py`; every script must exit zero.
5. Run generator static and semantic validation. The semantic gate must report a zero no-op floor and a 1.0 oracle score.
6. Create tests-only, stub, and owner-only copies with `Input_Bundle_QC/exe_copy.py`. Five independent oracle runs must score 1.0, nop must score 0.0, owner-only must score 1.0, and the stub must remain meaningfully low.
7. Run a real OpenHands frontier trajectory and inspect both the deterministic and judged channels. Provider failures are infrastructure exclusions, never model failures.

The verifier does not import the reference solver. It embeds input bytes and independently generated complete-bundle hashes, runs the submitted command as an unprivileged user in an isolated process group, pre-populates stale outputs, enforces a timeout, checks source restrictions, and verifies that inputs remain unchanged. Each fresh scenario changes a different documented boundary while retaining the complete contract and all nine reports. This rejects visible-answer replay and checks revision payload identity, identifier independence, half-open geometry, guard bands, signed residual ties, exact half-up rounding, and multi-atom exclusions without introducing hidden semantics.

No frontier difficulty claim is part of the golden truth record. A below-threshold claim is valid only after a complete trajectory produces both channels without infrastructure exceptions and the recorded scores satisfy the requested bounds.

## Root cause

Weak solutions usually flatten one of four independent dimensions. They resolve revisions from physical order, partition only time, aggregate money before rounding, or allocate signed corrections with ordinary division. Each shortcut produces believable summaries because totals remain near the correct values. The reports are deliberately redundant so those shortcuts become observable: the grant ledger explains source state, the slice ledger explains geometry and money, preemptions explain precedence, adjustments explain residual cents, settlements aggregate results, and the audit chain binds the final order.

The task remains fair because the exact order of operations, tie breaks, interval conventions, issue codes, schemas, and serialization rules are all agent-visible. Hidden inputs vary records rather than requirements. There is no dependency on proprietary spectrum knowledge; the domain vocabulary is defined by the schema.

## Solution shape

The reference implementation parses JSON and JSONL with explicit timestamp and Decimal helpers. It first resolves revision families and records quality issues. It validates licenses, grants, exclusions, activations, auctions, and corrections at the ingestion boundary. It then derives clipped effective grants.

For every license and cell, the implementation creates sorted time and frequency cut sets from all overlapping effective records after applying guard bands. Adjacent cuts form atomic half-open rectangles. Empty and out-of-license rectangles are discarded. Each remaining slice is classified by exclusion, active primary use, or deterministic sublease selection. Preemption reasons are recorded from the same classification decision.

Financial calculation happens only after classification. The applicable auction rate is selected, gross cents are rounded at the documented boundary, winner and owner shares are rounded per slice, and party subtotals are accumulated. Corrections are allocated independently by signed largest remainder and merged into final settlements. Material exceptions, canonical audit hashes, and manifest counts are derived last.

The verifier uses a different decomposition: it treats the complete nine-report bundle for each independent fresh scenario as one observable, then supplements those scenario observables with source inspection, serialization, determinism, and immutability. This avoids substantive shared-code coupling and avoids multiplying one scenario into sibling report-level criteria.

## Ordered plan

1. Read `schema.md`, then inventory every data file and output schema.
2. Implement deterministic revision resolution and issue collection.
3. Validate and clip licenses, grants, activations, exclusions, guard bands, and auctions.
4. Build complete time and frequency cuts for each licensed cell.
5. Classify each atomic slice using exclusion, activation, and grant precedence.
6. Select rates and compute per-slice gross and revenue shares with exact rounding.
7. Allocate signed corrections with largest remainder and deterministic ties.
8. Aggregate settlements, preemptions, exceptions, audit rows, and manifest metadata.
9. Serialize every report canonically and expose the reusable CLI.
10. Validate shipped and purpose-built fresh cases with independently calculated expectations before claiming completion.

## Pitfalls

- Do not use JSONL physical order as revision precedence.
- Do not treat closed interval endpoints as overlapping.
- Do not forget that guard bands change billable bandwidth before partitioning.
- Do not apply primary activation globally when it is scoped by license, time, frequency, and cell.
- Do not round using binary floating point.
- Do not aggregate unrounded shares before applying the specified per-slice rounding.
- Do not distribute negative corrections using signed floor division.
- Do not let quarantined rows contribute geometry or cents.
- Do not promise row-order byte identity for the manifest, whose hashes intentionally observe input bytes.
- Do not claim fresh or arithmetic verification without explicit assertions and expected values in the trajectory.

## Provenance

```yaml
uuid: fa7c65bd-ff01-50e7-b3ba-34fbd5df860d
instance_id: fa7c65bd-ff01-50e7-b3ba-34fbd5df860d
task_name: terminal-bench/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d
fix_patch_sha256: 3946dfa50cf21470676a48b4f3e26fc70a173e4de0dccae9e840db0762c1bddc
solve_py_sha256: 0376842b77ea5f59008bc0271a5ee7dd3535512e3d3cc766795c899c4142b9c2
language: python
golden_test_score: 1.0
golden_judge_score: 1.0
calibration_status: unmeasured
calibration_caveat: Frontier difficulty requires a valid measured trajectory; no below-threshold claim is encoded here.
```
