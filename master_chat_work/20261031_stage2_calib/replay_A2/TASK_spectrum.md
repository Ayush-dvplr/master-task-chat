# Spectrum Mechanism Card

Task: `fa7c65bd-ff01-50e7-b3ba-34fbd5df860d`. Source references are relative to that original task. `QC/` means `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`.

## Observed Outcome

Recorded and replay tests: **12/52 = 23.08%**; oracle **52/52 = 100%**. Recorded judge **12/56 = 21.43%**; combined **22.25%**. Eight scenario checks lost five raw points each; no negative fired. On every hidden extract, **eight of nine complete reports are byte-identical** to the frozen oracle. Slices, geographic/time/frequency partitioning, winners, preemption, revenue, corrections, settlements, manifest, audit and quality issues all match. Only `grant_ledger.effective_grants` differs; its revision decisions match too. Evidence: `spectrum-instrument/*/diff.json`, `inventory.json $.spectrum.cases`.

## Hidden Extracts

Ten files: schema, policy, parties, seven JSONL families. Base counts: licenses 3, grant revisions 9, activations 3, exclusions 3, guards 2, auction revisions 4, corrections 3: **27 JSONL rows**. `_PACKED` at `tests/test_output.py:34` is a compressed literal corpus. `_write_variant` at line 185 decodes it and `_apply_scenario` at line 76 applies one fixed mutation. Seed constants at lines 21-23 are not used to generate the cases. Retained counts: `spectrum-instrument/summary.json $.input_counts`, `inventory.json $.spectrum.shipped_counts`.

| Hidden extract | Mutation and resulting row count | Intended contract rule | Actual differing paths |
|---|---|---|---:|
| revision_cells | Clone GR-1B as GR-1Z with reversed cells; grants 10, total 28 | Set-valued peer comparison, record-ID winner; schema:13 | 14 |
| revision_scalar | Clone GR-2A as GR-2Z with priority 4; grants 10, total 28 | Genuine scalar peer conflict; schema:13 | 12 |
| activation_identifier | Two grants plus activation PRIMARY-Z; grants 11, activations 4, total 30 | Unrestricted activation names and primary priority; schema:15,31 | 18 |
| half_open_boundary | LIC-B guard 0; adjacent C3 grants [3561000,3563000), [3563000,3565000); grants 11, total 29 | Frequency endpoint half-openness; schema:3,27,30 | 18 |
| guard_abutment | C2 grants meeting at 3555500 before guard shrink; grants 11, total 29 | Guard-adjusted usable endpoints, owner gap; schema:19,27 | 18 |
| correction_tie | LIC-C, 50/50 grant, +1 correction; licenses 4, grants 10, corrections 4, total 30 | Equal fractional remainders and party-ID residual tie; schema:43 | 15 |
| half_up_midpoint | LIC-D, 1000 kHz, 1800 seconds, rate 1; licenses 4, auctions 5, total 29 | Exact gross midpoint 0.5 rounds to 1; schema:37 | 12 |
| exclusion_span | Add EX-SPAN, all parties, C1, 3551500..3557500 across time cuts; exclusions 4, total 28 | Multi-dimensional exclusion and unassigned slices; schema:17,32 | 12 |

The targeted calculations pass the field comparison despite the eight failing check labels. Path counts measure missing keys and list positions, not domain error counts.

## Contract Density

The seven-line instruction delegates to a 59-line, 1,011-word contract. Rules are concentrated in long paragraphs and a five-step candidate list, not a hidden file. Roughly twelve interacting stages supply legitimate complexity: validation, revision resolution, Cartesian cuts, guard adjustment, activation, exclusions, winner precedence, auction selection, gross rounding, share rounding, signed correction allocation, settlement/audit. This is an analytical grouping. Schema:13,19,21,27-37,43 contain the most interacting arithmetic and precedence. Trajectory inspection and R1 pass establish that Opus read the material.

The omission is sharply localized: schema:13 defines fourteen **input** grant fields, but schema:53 specifies only the output container and the three revision-decision keys. It does not say whether effective grants must retain original revision metadata or normalize cell ordering. No shipped output example resolves that ambiguity.

## Exact Loss Mechanism

S-GRANT-ROW: oracle solve.py:130 retains the raw winning fourteen-field row and line 318 emits it. Captured clear_spectrum.py:927 projects eleven usable-grant fields, omitting `revision`, `recorded_at`, `status`. Four effective grants cause twelve missing-key paths in ordinary cases; six cause eighteen, and five cause fifteen. S-CELL-ORDER adds two positional differences in revision_cells: raw winning GR-1Z has `[C2,C1]`; agent emits normalized `[C1,C2]`. Cells are explicitly set-valued for comparison, and output cell ordering is unstated. This is not a failure to normalize cells for peer conflict detection: quality issues and revision decisions are identical.

**UNFAIR** is the contract-alignment classification: raw metadata retention and preserved cell order are not determinate output requirements. Missing keys are observable format differences, but calling them FORMAT alone would conceal the missing contract. `CAUSES.csv` includes full expected/actual rows and absolute doc/code references.

Execution uses Python `-I -S`, nobody, a minimal environment, seeded stale reports and 120-second timeout (`tests/test_output.py:235`). Each scenario compares one SHA-256 of all nine filenames, separators and raw reports (283-299). `_holds` catches all exceptions (275-280). Instrumented original comparisons raise empty-message `AssertionError` in 0.027-0.033 seconds. No crash/timeout occurred; regenerated oracle hashes match all eight frozen constants.

Weights: eight hashes x5 =40 lost; artifact set 1, canonical 3, safe source 3, deterministic/no mutation 5 =12 earned. Negatives -5/-5/-3 are false. The one-fact counterfactual changes only `manifest.engine_version` in otherwise exact oracle reports and fails every hash; with the four independent positives unchanged, total is still 12/52. Paid scenario units therefore repeatedly measure the same unrelated metadata error, violating proportional-credit expectations.

## Judge Loss

R2-R8 lose 35 raw points for insufficient independent expected-value probes. Do not say no tests were run. Step 14's verify.py actually asserts recomputed Decimal gross cents and `winner_cents + owner_cents == gross_cents` across slices. Its area comparisons print booleans and overlap findings print text rather than assert. R5 still loses its bundled auction-revision/rate-boundary/concrete worked-example requirement; R6 lacks a deliberately chosen half-up share result. Steps 25/26 construct and execute a fresh extract, then print its results; R8 requires independently asserted expectations. R7 lacks explicit signed floor/remainder/residual-order derivations. `JUDGE_LOSS.csv` records each exact reason and step.

R9-R11 lose nine raw points: not every field/order was independently checked, no independent digest/audit-chain recomputation, no original input-byte snapshot. Steps 30/34/37 do verify canonical JSON and ten artifacts. Step 31 compares eight report bytes and manifest semantic fields excluding raw input hashes; this exclusion is correct for reordered raw JSONL. Do not reproduce a criterion demanding unchanged raw-input hashes after reordering.

## QC Fit

| Gate | Assessment | Evidence |
|---|---|---|
| IN-8 | **LIKELY FAIL** | Every five-point hash requires unstated effective-grant row metadata and revision_cells also requires unstated cell order. Schema:13,53; QC/01_Instruction_QC.md:38. Conduct-probe criteria are a separate exempt kind, not an excuse for an underdefined output. |
| IN-17 | **PASS, scoped to this gate** | Instruction:1,5 delegates contract discovery and generically announces fresh extracts, without leaking answers. QC/01_Instruction_QC.md:47. Exact output schemas must still be stated because data cannot establish missing output requirements. |
| AL-1 | **LIKELY FAIL** | Neither instruction nor copied input determines the raw-versus-projected effective-grant output. Test/solution expectations are not a contract. QC/05_Alignment_Integrity_QC.md:21,27,34-35. |
| AL-27 | **LIKELY FAIL** | Some boundary witnesses are genuine (0.5 gross midpoint, equal-remainder correction). But removing party_id from the winner key at solve.py:258 changes no report for any hidden extract. `spectrum-instrument/trigger-probe.json` records all eight unchanged results. No discriminating same-priority/same-source/different-party candidate witness exercises that final tie-break. QC/05_Alignment_Integrity_QC.md:38 requires every link, not scenario names. |
| CL-4 | **LIKELY FAIL** | One changed engine-version field defeats all eight five-point scenario hashes, even with otherwise exact outputs. QC/Final_checklist.md:491 rejects independent facts collapsed into whole-object equality and repeated loss for one fact; no instruction opts into all-or-nothing credit. |

A careful engineer could reasonably emit semantic effective grants and sorted set-valued cells. That choice should not destroy credit for correct allocation and settlement. Missing independent expected-value probes is a real process weakness, but this captured run supplies no evidence of wrong spectrum business results on these inputs. Latent differences on unexercised guard/correction shapes were not charged as causes.

## Copy Into a New Domain

**Proposed recipe, not a demonstrated Opus-failure prediction:** use warehouse loading-bay allocation with time x zone x capacity rectangles, priority reservations, maintenance exclusions, owner fallback, tariff revisions, per-rectangle rounded revenue and signed rebates. Publish a complete output schema including projected-versus-raw rows, issue-ID scope and every array order. Keep about ten to twelve interacting stages in 800-1,100 words. Use one visible extract and eight hidden extracts matching set-order tie, scalar conflict, identifier-neutral activation, abutting endpoints, guard gap, residual-cent tie, half-up midpoint, multi-axis exclusion.

Make each adjacent precedence comparison decisive with conflicting alternatives; if source IDs may collide across candidate families, construct that collision and vary party IDs. Split correctness into independently weighted partition, winner, money, correction, schema and audit facts; eight rule families x2 plus three one-point integrity checks is a concrete starting budget. Repeated fixtures share a family budget rather than multiplying the same root penalty. Add only a small conduct channel: one three-point independent boundary/conservation verification criterion and one one-point honest preservation/repeatability criterion, allowing equivalent verification methods. Re-audit under JD-15 and demonstrate a proportional one-fact-wrong score. Do not copy raw-bundle hash cliffs, unannounced metadata, arbitrary mandatory probe counts, repeated near-identical conduct criteria or same-action penalties across channels.
