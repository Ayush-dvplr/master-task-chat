"""Write solution/TRUTH.md from the shipped bundle (run last, after every other edit).

usage: python3 -B write_truth.py <bundle>
"""
import ast
import hashlib
import sys
from pathlib import Path

bundle = Path(sys.argv[1])
slug = bundle.name
solve = bundle / "solution" / "solve.py"
tests = bundle / "tests" / "test_output.py"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


tree = ast.parse(tests.read_text())
blob = extracts = None
for node in tree.body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        if node.targets[0].id == "_EXPECTED_BLOB":
            blob = node.value.value
        if node.targets[0].id == "_EXTRACTS":
            extracts = {k.value: v.value for k, v in zip(node.value.keys, node.value.values)}
assert blob and extracts

TEXT = f"""# TRUTH.md - {slug}

## Defect

A reinsurance reserving desk carries five lines of business (`wc`, `cal`, `gl`, `cp`, `spec`), accident years AY2023 to AY2032 and twenty six semi-monthly cycles H01 to H26. The corpus in `environment/data/` is fifty seven files: claim transaction logs, a cession bordereau, a legacy fixed-width intake, reinsurer and alias masters, capacity, ceiling and commitment registers, endorsement circulars and their audit rotations, reserve events, two observation logs and the rule documents with four declaration files. The agent builds `reserving.py`, which rebuilds the per-LOB ledgers, the treaty working through a retention, two excess layers and a retro offset, the data-quality tallies and the methodology audit, and reports seven counterfactual quantities in its closing message.

What makes it hard is that the corpus offers a plausible wrong reading at every stage:

1. Paid to date. Each claim transaction log carries three columns titled `paid_to_date` (positions 4, 5 and 7). `source_manifest.md` says the leftmost governs; a dict reader keeps the last one. Defeats `ledger_backbone_exact`, `ledger_spine_exact` and both extract checks.
2. Admission instant. A source row recorded strictly after `2033-01-15T00:00:00Z` (`valuation_instant` in `derivation_policy.ini`) is dropped before every other stage. Defeats `data_quality_source_counts_exact`, `summary_claim_counts_exact` and the ledger digests.
3. Cross-source precedence. The governing row of a claim is chosen by the precedence lists under `[precedence]` in `derivation_policy.ini`, and the list in force flips at `cutover_instant`. A single fixed order changes the governing paid and incurred of many claims.
4. Chain-ladder factor. Per development year the factor is the sum of incurred over the sum of paid across admitted claim transaction rows, clipped to [1.0, 2.5] and rounded half-up to six places; ultimate is the governing paid times the factor of the claim's development year (governing instant year minus `accident_year` in `claim_master.csv`, whichever source governs), rounded half-up. Incurred runs above paid on the young accident years, so the factors are real development. Defeats `chain_ladder_development_exact` and every ledger digest.
5. Attachment. `errata_2032-04.md` replaces the handbook's per-claim retention with clash cover: within one `event_id` of `claim_master.csv` only the first claim in (claim_ref, reinsurer_canonical) order consumes the retention and the rest start at `working_excess`. Each claim books the `layer=` of its `claim_adjustment_log.log` line (the later line when two, `retention` when none) before clash cover applies. Defeats `ledger_backbone_exact`, `treaty_layer_breakdown_exact` and both extract checks; judge R18 grades reading the errata before the attachment code is written.
6. Reinsurer epochs. RE-0412 is reused across `2032-07-01T00:00:00Z`; rows before the boundary take `#1` and rows at or after it take `#2`. Defeats the backbone digest and both extract checks.
7. Two withheld readings settled by enumeration. The ALAE convention (`pro_rata` or `excess_only`, with the pro-rata fraction fitted from `claim_adjustment_log.log` to within one dollar) and the discount curve (`flat_10y` or `duration_matched`, from `treasury_curve_observations.log`) are each settled by the one candidate every observation line supports, and the module reports them as `alae_convention` and `discount_curve` under `methodology_audit.settlement`. Graded by the ledger spine and judge R16, R17, R25, R28 and R29.
8. Endorsements. A circular counts only when its claim appears in an `ENDORSE` line of one of the three audit rotations and its underwriter holds authority for its LOB in `authority_roles.csv`; its `cede_cap_raise` ALAE raise belongs to the unendorsed-amendments counterfactual only. Graded by `methodology_audit_remaining_sections_exact` and judge R13 and R14.
9. Hidden extracts. Extract A drops every fifth claim from every claim-keyed file; extract B replaces the claim transaction logs. Both carry rows that trigger the rarely firing rules (a parenthesised amount, a whole-thousands fixed-width amount, an identical duplicate row, a gap between cycle windows, a zero-capacity cell and a claim with nothing to cede); extract B also retracts the claim whose reinsurer cannot be resolved, so `RETRACTED` must win over `EXCLUDED`. Graded by `program_reproduces_unseen_extract_alpha`, `program_reproduces_unseen_extract_beta`, `row_order_permutation_changes_nothing`, `hidden_extract_outcomes_exact` and `hidden_extract_quality_tallies_exact`.

Out of bounds: hardcoding shipped answers or the epoch boundary instant, embedding corpus rows, output that ignores the corpus, a fixed corpus path, silent recovery from a missing source, writing into the corpus, and opening the network or starting processes. Each is a test negative.

## Load-bearing work

The reference (`solution/solve.py`) reads the four declaration files first: admission and cutover instants and the precedence lists from `derivation_policy.ini`, fixed-width offsets from `source_declarations.properties`, the closed vocabularies from `reason_codes.json`. It parses the three sources by position, drops rows after the admission instant, collapses each claim's admitted rows into one governing row, resolves the reinsurer through the alias map and the epoch boundary, builds the chain-ladder factors with each claim's accident year from `claim_master.csv`, settles the ALAE convention and the discount curve from the observation logs, books each claim on the layer of its later `claim_adjustment_log.log` line (else `retention`) and then applies clash cover, and allocates each (LOB, cycle) cell in three steps (commitment minimums, a shared fill level, one-dollar remainder by largest unmet). A claim whose reinsurer cannot be resolved keeps a ledger row with a null `reinsurer_canonical`, `EXCLUDED` and `UNRESOLVABLE_CHAIN`; a retracted claim keeps a `RETRACTED` row. A governing instant that falls between two cycle windows is placed in the next cycle and counted by `gap_shifted`. The counterfactual integers come from `compute_counterfactuals`, which follows `counterfactual_parameters.md` and reads its tenor, increment and multiplier from that file.

## Verification

The test channel registers twenty four positive checks with a total of sixty four and seven negative checks whose absolute values sum to twenty three. The judge channel registers twenty seven positive criteria with a total of sixty five and six negative criteria whose absolute values sum to twenty four. Reward weights are 0.5 divided by sixty four and 0.5 divided by sixty five, matching `tests/reward.toml`.

| Requirement in the instruction | Artifact | Test check | Judge criterion |
|---|---|---|---|
| Per-LOB ledger rows | `lob_<lob>.json` | `ledger_backbone_exact`, `ledger_spine_exact`, `outcome_and_reason_vocabulary_exact` | R19, R21 |
| Capacity, ceiling and remainder per cycle | `lob_<lob>.json` | `lob_cycle_capacity_and_fill_exact` | R22, R23 |
| Chain-ladder development | `lob_<lob>.json` | `chain_ladder_development_exact` | |
| Treaty working | `treaty_working.json` | `treaty_layer_breakdown_exact`, `cross_artifact_identity_triangle_holds` | R15, R32 |
| Data-quality tallies | `data_quality.json` | `data_quality_source_counts_exact`, `data_quality_anomaly_tallies_exact`, `hidden_extract_quality_tallies_exact` | R20 |
| Summary totals and treaty splits | `summary.json`, `treaty_working.json` | `summary_claim_counts_exact`, `summary_and_treaty_values_exact` | |
| Methodology audit | `methodology_audit.json` | `methodology_audit_attachment_exact`, `methodology_audit_holds_only_declared_sections`, `methodology_audit_remaining_sections_exact` | R16, R17, R18, R25, R28, R29 |
| Rules read at run time | `reserving.py` | `program_reproduces_unseen_extract_alpha`, `program_reproduces_unseen_extract_beta`, `row_order_permutation_changes_nothing`, `hidden_extract_outcomes_exact` | |
| Program runs and is deterministic | `reserving.py` | `program_runs_and_exits_clean`, `byte_identical_rerun`, `exact_serialization_format`, `artifacts_present_and_parse` | R24 |
| Standard library, clean code | `reserving.py` | `negative_module_opens_network_or_shells_out`, `module_imports_only_standard_library` | R31, R33 |
| Missing source stops the run | `reserving.py` | `negative_silent_recovery_from_missing_source` | |
| Seven counterfactual quantities | closing message | | R1 to R14, R26, R30 |
| No grader files | trajectory | | R27 |

Missing declared input raises `FileNotFoundError` naming the file.

## Root cause

Every graded figure is a whole number of dollars compared exactly, and every rule that produces one has a plausible wrong reading in the corpus, so one wrong reading moves many digests at once. Rules are read from the corpus at run time, so a module tuned to values seen once fails on the extracts.

## Solution shape

`solution/solve.sh` copies `solve.py` to `/app/out/reserving.py` and runs it over `/app/data`. The output directory then holds the nine documents and the program.

## Pitfalls

| Rank | Failure | Positive points it defeats (of 64) |
|---|---|---|
| 1 | One fixed precedence order for every row | 45 |
| 2 | No admission instant | 41 |
| 3 | Reading the last `paid_to_date` column | 39 |
| 4 | Unclipped chain-ladder factor | 22 |
| 5 | Per-claim retention instead of clash cover | 21 |
| 6 | No epoch split for RE-0412 | 19 |

Each figure is measured by running the reference with that one reading changed against the shipped tests.

## Provenance

```yaml
uuid: {slug}
instance_id: {slug}
task_name: terminal-bench/{slug}
language: python
status: sealed
solve_py_sha256: {sha(solve.read_bytes())}
expected_blob_sha256: {sha(blob.encode())}
extract_A_sha256: {sha(extracts["A"].encode())}
extract_B_sha256: {sha(extracts["B"].encode())}
```
"""

(bundle / "solution" / "TRUTH.md").write_text(TEXT)
print("TRUTH.md written", len(TEXT.splitlines()), "lines")
