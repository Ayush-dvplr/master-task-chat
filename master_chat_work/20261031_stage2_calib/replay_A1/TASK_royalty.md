# Royalty Mechanism Card

Task: `75407a55-6665-505e-95d8-5ff9bdb3384f`. Relative task references resolve under `/Users/mac/Desktop/Terminal Bench/anubis-stage-2/75407a55-6665-505e-95d8-5ff9bdb3384f/`. Evidence: `evidence/royalty/` beside this report.

## Actual Cause

All eight financial scenario tests fail because of **one unresolved issue-identity convention**, not eight financial errors. In every case, `data_quality.json $.issues[2].record_id` and `exception_register.json $.exceptions[2].record_id` are `ST-BAD-A` rather than oracle `ST-BAD`. The other seven report files are byte-identical, including every financial ledger, rollup, manifest, and audit chain (`case_01.json` through `case_08.json`).

`environment/data/schema.md:9` explicitly assigns `statement_id` to REVISION_TIE_CONFLICT issues, but merely says emit INVALID_STATEMENT and quarantine invalid active winners. Line 39 gives an issue sort key, not its identity semantics. Two defensible readings remain: identify the offending winner by globally unique `record_id`, as Opus does at captured `calculate_royalties.py:315`, or identify the statement aggregate, as oracle `solution/solve.py:51` does. Nothing in shipped input supplies expected output issues to disambiguate. Line 51 requires copying quality issues into exceptions, so the second differing field is mandatory propagation of the same choice.

Every oracle bundle was checked against the test's fixed SHA256 before treating it as truth: all eight match (`case_NN.json $.oracle_hash_valid`). The one-expression counterfactual changes only INVALID_STATEMENT identity from `winner["record_id"]` to `statement_id`; all eight scenario bundles then match exactly (`counterfactual_summary.json`). This isolates the cause without changing any financial algorithm. Allocate the 40 raw lost test weight once to UNFAIR; whole-bundle AMPLIFIED is a modifier, not another 40 points.

## Hidden Inputs

There are eight fixed variants of a compressed baseline, not eight randomized unseen financial worlds. `_BLOB` at `tests/test_output.py:14` contains ten input files. `_variant` at 40-45 decompresses them and applies one mutation. All variants retain invalid statement `ST-BAD` / winner record `ST-BAD-A`, project `MISSING`. Hidden schema differs from shipped schema only in its title, not substantive rules. `_EXPECTED` holds eight full-nine-report bundle hashes at line 16.

| Scenario | Mutation | Stated Rule Actually Targeted |
|---|---|---|
| revision_tie | Add ST-3Z with the same revision/time as ST-3A, different amount 9600001 | Compare equal-rank payloads; report conflict; record ID selects winner (`schema.md:9`) |
| fx_half_up | ST-2A amount 1, GBP rate 1/2 | Exact half-up conversion of 0.5 (`schema.md:11`) |
| withholding_half_up | ST-1B amount 10001, US withholding 5000 bps | Per-statement withholding half-up, fee after withholding (`schema.md:13`) |
| pool_priority | A marketing opening 1,000,000; production 20,000,000 | Stateful pool order and depletion (`schema.md:27`) |
| largest_remainder | PROJ-B shares 3333/3333/3334; remove its advances and adjustments | Floors, fractional ordering, conservation (`schema.md:29`) |
| advance_priority | A first advance 250,000; add same participant priority-2 advance 700,000 | Multi-advance state/order/depletion (`schema.md:31`) |
| period_carry | ST-1B amount 1,000,000; ST-2A zero | Cross-period balances and zero-flow periods (`schema.md:25-27`) |
| signed_adjustment | ADJ-1 becomes -975001 | Signed adjustment after recoupment (`schema.md:21,31`) |

Mutations: `tests/test_output.py:19-38`. Their names describe fixture intent, not the actual source of this run's failure. The financial comparisons show Opus already handles all eight targeted interactions.

## Rule Density And Burial

One 53-line authoritative schema packs at least 14 operational families: revision ranking, equal-rank conflict, cancellation, reference validation/quarantine, FX rounding, withholding/fee sequencing, chronological pool state, allocation validity, largest-remainder ties, participant advance state, post-recoupment signed adjustments, report schemas/order, raw input digest provenance, and chained output hashing. This count groups rules by operational responsibility rather than claiming an exact number of independent facts.

The densest interactions are on single long lines: revision/conflict/cancellation/validation at 9; two per-statement half-up checkpoints and fee base at 13; state, depletion, ordering and zero rows at 27/31. These are legitimate precision demands. A missing identity convention in line 9 is not a legitimate hidden rule. The same schema also creates a determinism tension: JSONL row order is non-semantic (3), but manifest must hash every raw input byte (37), so a row shuffle necessarily changes manifest bytes.

## Checks And Lost Weight

Positive weights total 52: artifact presence/parse +1, eight whole-bundle scenario hashes +5 each, canonical serialization +3, local source +3, deterministic/no-mutation +5. Three negatives do not fire. Opus earns 12/52 = 23.076923%, exported as 23.08%. The +40 loss is 76.923077 percentage points for this one identity decision.

`_run` at `tests/test_output.py:61-67` executes the reusable program in isolated stdlib mode under an unprivileged child, 120-second timeout, and stale output files. `_bundle` at 74-77 hashes each filename, NUL, and report bytes. `_exact` at 85 compares only the full digest. `_holds` at 78-81 catches every exception and returns False. The driver preserves that exact input/byte comparison and adds field-level output, exception details and timing. All eight captured-agent executions succeed quickly; no crash or timeout is involved.

Judge earns only 6/56 after a -3 penalty. R2-R8 lose 35 because independently calculated expected-value assertions were not demonstrated, even though financial outputs are correct. R9-R11 lose 9 for partial schema checking, no independently checked input digest, and incomplete shuffle/immutability evidence. R14 loses 3 for overstatement; R17 fires -3 for unsupported validation claims. These twelve rows are in `JUDGE_LOSS.csv`, with verbatim reasoning and step references. Do not interpret low rubric score as further arithmetic evidence.

Original trajectory: step_id 13 compares eight shuffled reports and explicitly removes manifest input metadata before a core comparison (`steps[12]`); step_id 15 prints a purpose-built synthetic 4/3/4 split but no independent expected-value assertions (`steps[14]`); step_id 16 validates serialization and independently recomputes the audit chain, not a manifest input digest (`steps[15]`); step_id 17 overclaims hand-checking and all-output byte identity (`steps[16]`). The absence of formal assertions alone is not proof that no mental arithmetic occurred; the judge's recorded reason is missing **executed independent evidence**.

## Careful Engineer Versus Trap

A careful engineer can reasonably choose the winning revision's record ID for an invalid record. Penalizing that choice across every named financial scenario is a trap. Excluding the raw-input manifest from a row-shuffle byte comparison is also mathematically justified; the broader claim of all-output identity is not. Independent expected arithmetic, schema validation, digest recomputation and truthful validation summaries are useful conduct standards, but their weights should not be mistaken for measured defects in the financial results.

## QC Fit

Kit root: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`.

| Gate | Fit | Evidence And Reason |
|---|---|---|
| IN-8 | LIKELY FAIL | `01_Instruction_QC.md:38`: no reachable rule selects statement ID rather than winner record ID for INVALID_STATEMENT. Line 9 specifies the former only for a different issue code. |
| IN-17 | PASS | `01_Instruction_QC.md:47`: pointing to the schema is legitimate orientation; explicitly specifying issue identity would settle an ambiguity, not pre-announce an input discovery. |
| AL-1 | LIKELY FAIL | `05_Alignment_Integrity_QC.md:21`: raw input with both IDs does not establish which identifier a newly emitted error must use. Oracle code is not agent-visible authority. |
| AL-27 | LIKELY FAIL | `05_Alignment_Integrity_QC.md:38`: schema 17 grades invalid allocation rows/totals and schema 21 invalid adjustments, but baseline allocations sum to 10000, all adjustment references are valid, and the only relevant variant replaces allocations with another valid 10000 total. No variant triggers those quarantine branches. The eight named financial interactions themselves do have concrete trigger fixtures. |
| CL-4 | LIKELY FAIL | `Final_checklist.md:491`: one identity choice, copied to two reports, zeros eight +5 bundle gates. All financial outputs remain correct; score is 12/52 = 23.076923% rather than 100%. Unlike billing/PM2.5, instruction does not explicitly say that only a full exact match counts. Serialization requirements alone are not that exception. |

R11's demand for every output byte unchanged after reordering conflicts with raw-input manifest hashes. The agent also omitted all-input immutability verification, so that entire 3-point loss is not attributed solely to the impossible part. Positive R14 loss plus negative R17 is not automatically AL-28 stacking: that gate concerns multiple negative penalties, not every positive/negative overlap (`05_Alignment_Integrity_QC.md:39`).

## Copy Into Another Domain

For insurance/escrow settlement, keep the eight financial interactions above but create 8-12 independent fixtures with explicit invalid-record identity, period order, rounding boundaries, and tie semantics. Add a ninth invalid-reference fixture and a tenth duplicate-priority/allocation-total fixture so every quarantine rule actually fires. Grade revision decisions, FX/tax/fee arithmetic, pool state, allocation conservation, advances, adjustments, and provenance separately; never put all financial points behind an unrelated common issue ID. Define semantic row-shuffle invariance separately from raw-byte provenance. Three copyable conduct probes are an independently computed midpoint, an explicit multi-priority state transition, and a digest/audit-chain recomputation; require the evidence, not a particular testing framework.
