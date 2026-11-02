# TRUTH.md - b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042

## Defect

The corpus describes year-end 2032 IBNR reserving for a mid-size property and casualty carrier across five lines of business (`wc`, `cal`, `gl`, `cp`, `spec`), ten accident years (AY2023 through AY2032) and twenty six semi-monthly booking cycles (H01 through H26), and asks for the chain-ladder ultimates, the treaty cession through three excess layers and a retro offset, and the resulting IBNR ledger. The evidence that fixes every input to that allocation is spread across fifty six record and declaration files written by eleven different systems, and several of those systems disagree. The work is wrong in a believable way unless each of the following is handled.

1. (focal) Chain-ladder shared development spine. Age-to-ultimate development factors are volume-weighted across LOBs within each development year over the admitted claim transaction rows only, then applied to immature AYs to project to ultimate. The habitual reading (simple arithmetic average of age-to-age ratios) is written down in `treaty_handbook.md` and is withdrawn; it differs from the governed reading by 0.3-1.2 percent per factor. Rounding is half-up to a whole dollar on the per-claim ultimate and to six decimal places on the factor. Defeats `development_spine_exact` and `lob_cycle_capacity_and_fill_exact`.
2. (focal) Running cumulative IBNR carryforward. Reserve adjustments carry forward across the twenty six half-month cycles that make up the year; a wrong AY2024 estimate at Q1 is still visible at year-end Q4. Running totals never heal, so one wrong decision at cycle five is still visible at cycle twenty six. Defeats `ibnr_carryforward_exact`.
3. (focal) Two withheld rules. Neither the ALAE allocation convention (`pro_rata` vs `excess_only`) nor the treasury discounting curve (`flat_10y` vs `duration_matched`) is stated in the contract. Each is settled only by enumeration against the two settlement logs, and the surviving reading must be reported in `methodology_audit.json` under `settlement.alae_convention` and `settlement.discount_curve`. A reading that fits only some observations is wrong. Defeats judge criteria R16, R17, R26, R29 and R30.
4. (drift) Clash cover vs individual excess. `treaty_handbook.md` section 3 describes individual-risk excess attachment with each claim piercing its own retention; `errata_2032-04.md` replaces it with clash-cover attachment under which two or more claims from one event share one retention. Per-event clash attachment moves a small share of claims by one dollar of retention and nothing else, which looks like a clean result. Defeats `treaty_cession_walk_exact` and judge R18.
5. (drift) Duplicate `paid_to_date` column. Every claim transaction log carries three columns titled `paid_to_date` (positions 4, 5 and 7). Position 4 governs: it is the cumulative-paid amount at the recorded instant. Position 5 carries the incurred figure despite the header string. Position 7 is a later audit restatement. A dictionary reader keyed by column name keeps the final position (7) and loses position 4. `source_manifest.md` allows the governing column to be reached either by positional access or by first-match header lookup; a reader that silently overwrites earlier matches of a repeated header fails. Defeats the backbone through governing cumulative paid.
6. (trap) Admission by valuation date. Rows recorded after `2033-01-15T00:00:00Z` are evidence of nothing, including treaty endorsements, retro notices, reserve-state events and the chain-ladder factor computation. Defeats `data_quality_source_counts_exact` and the backbone.
7. (trap) Reinsurer identity across epochs. A reinsurer merged mid-year (pre-Q3 the identifier `RE-0412` carried Munich Re Capital and post-Q3 the same identifier carried Hannover Re Specialty) and the two epochs share no treaty layer, no commitment and no carried offset. Defeats `treaty_layer_breakdown_exact` and `cross_artifact_identity_triangle_holds`.
8. (trap) Treaty attachment walk. A claim exceeding its booked LOB's working-excess retention walks the ceded path retention then working excess then cat excess then retro, at most three layers, and two LOBs close a cycle between them on a clash-trigger event. The shortest path to any attachment-qualified layer is a different answer. Defeats `treaty_cession_walk_exact`.
9. (trap) Endorsement scope and authority. A treaty endorsement counts only when it was recorded after the row it amends and signed by an underwriter holding that LOB's authority at the audit instant, across three rotated endorsement logs whose stamps carry a per-LOB recorder skew of up to ninety seconds. Defeats the `unendorsed_honoured_alae_differs` and `unendorsed_honoured_fill_cycles` counterfactuals (R13 and R14).
10. (trap) Reserve state machine. Reserve-change events apply by ascending version rather than file order; a stale version is ignored; an illegal move (CLOSED to NOTED without ESTIMATED-REOPENED) leaves state unchanged and still counts; only ADJUSTED claims claim an IBNR increment while NOTED, ESTIMATED and CLOSED claims keep a ledger row of zeros. Defeats `outcome_and_reason_vocabulary_exact`.

Out of bounds: the delivered module must not hold any figure of the shipped corpus as a constant (`negative_hardcoded_sample_answers`), must not embed corpus rows (`negative_embedded_corpus_rows`), must give byte-identical bytes on a rerun (`byte_identical_rerun`), must derive its answers from the corpus it is handed rather than from stored results (`negative_output_independent_of_the_corpus`), must leave the corpus untouched (`negative_module_mutates_the_corpus`), must raise rather than skip a stage when a source is missing (`negative_silent_recovery_from_missing_source`), must behave the same whatever the directory is called (`negative_module_reads_a_fixed_corpus_path`), must stay offline and inside the interpreter (`negative_module_opens_network_or_shells_out`), and must serialise every artifact with `sort_keys=True, indent=1`, UTF-8 without BOM and a single trailing newline (`exact_serialization_format`).

## Load-bearing work

The spine is one quantity, the whole dollar of ceded recoverable, carried on every ledger row of every LOB document and accumulated per (reinsurer, LOB) in `ceded_by_reinsurer_canonical` and per LOB in `ceded_by_lob`. Every load-bearing decision moves it.

Sixteen stages produce it. Admission filters every source file by recorded instant against `2033-01-15T00:00:00Z`. Identity resolution maps three reinsurer spellings and two alias prefixes onto a canonical identifier of the form `RE-NNNN#E` (where E is 1 for pre-Q3 and 2 for post-Q3) and attaches the epoch in force at the record instant. Claims whose reinsurer cannot be resolved to a canonical identifier do not enter any ledger. Collapse groups the rows of one claim across sources inside the declared window and settles each field by the precedence in force on its side of the April cutover, with the ALAE allocation convention settled from `claim_adjustment_log.log` by enumerating `pro_rata` and `excess_only` against every observation. Endorsement and reserve-state resolution then decide whether the claim claims at all: a treaty endorsement counts only when recorded after the row it amends and signed by an underwriter holding that LOB's authority at the audit instant, and reserve state events apply by ascending version with illegal moves leaving state unchanged. The treaty attachment walk fixes the retention gate at claim level, the three-layer attachment ceiling (retention, working excess, cat excess) and the single clash-cover attachment per `errata_2032-04.md`. Chain-ladder age-to-ultimate factors are computed volume-weighted across LOBs within each development year on the admitted rows only, then applied in one multiplication to project immature accident years to ultimate. Rounding is half-up on both the per-factor six-decimal result and the per-claim whole-dollar ultimate. The discount curve is settled from `treasury_curve_observations.log` by enumerating `flat_10y` and `duration_matched` and applied to the three long-tail LOBs (wc, cal, gl). Carry forward adds the surviving IBNR lots to the claim under the ceiling and clears the lot of a LOB cycle whose capacity ended unused. Allocation pays the honoured minimums in commitment order, raises the shared fill level to the greatest whole dollar capacity allows, and hands the indivisible remainder out one dollar at a time by unmet-amount tie-break. Retracted claims keep a ledger row with `outcome = "RETRACTED"`, `reason = "RETRACTED"`, `ceded_hours = 0`, `alae = 0` and do not pass through the three-step allocation. Counterfactual parameters (the ALAE pro-rata fraction `0.08`, the extra tenor `15y` at `max(curve) + 0.5`, and the retro multiplier `1.10` on cat-excess rows) are read from `counterfactual_parameters.md` at run time.

## Verification

The test channel registers twenty one positive checks with a total of sixty seven and seven negative checks whose absolute values sum to twenty three. The judge channel registers twenty eight positive criteria with a total of sixty six and seven negative criteria whose absolute values sum to twenty nine. Reward weights are 0.5 divided by sixty seven and 0.5 divided by sixty six, matching `tests/reward.toml`.

| Requirement in the instruction | Artifact | Test check | Judge criterion |
| --- | --- | --- | --- |
| Ledger rows ordered by cycle, canonical reinsurer, claim ref | lob documents | ledger_order_exact | none |
| Grants satisfy the four stated properties | lob documents | lob_cycle_capacity_and_fill_exact | R23 |
| Fill level reported per LOB cycle | lob documents | lob_cycle_capacity_and_fill_exact | none |
| Running totals never heal | lob documents | ibnr_carryforward_exact | none |
| Carried amounts survive a settled number of cycles | lob documents | ibnr_carryforward_exact | none |
| Capacity built from layer declarations | lob documents | lob_cycle_capacity_and_fill_exact | R22 |
| Pierced layer and hops reported | lob documents | treaty_cession_walk_exact | R18 |
| Ceded dollar figure derived by truncation | lob documents | paid_to_date_dollars_exact | none |
| One outcome and one reason per row | lob documents | outcome_and_reason_vocabulary_exact | none |
| Out-of-scope rows kept apart | summary.json | summary_claim_counts_exact | none |
| Identity carries its epoch | all documents | cross_artifact_identity_triangle_holds | R21 |
| Treaty layer breakdown totals exact | treaty_working.json | treaty_layer_breakdown_exact | none |
| Rule firings counted | methodology_audit.json | methodology_audit_attachment_exact | none |
| Attachment rule reported (authority prose) | methodology_audit.json | methodology_audit_attachment_exact | R18 |
| Attachment rule implemented (module code path) | reserving.py | treaty_cession_walk_exact | R33 |
| Settled readings reported | methodology_audit.json | none | R16, R17, R26, R29 and R30 |
| Source counts per declaration | data_quality.json | data_quality_source_counts_exact | none |
| Anomaly tallies | data_quality.json | data_quality_anomaly_tallies_exact | R20 |
| Totals and residuals agree | summary.json | cross_artifact_identity_triangle_holds | none |
| Module reruns on unseen extracts | module | program_reproduces_unseen_extract_alpha and beta | none |
| Module reads as clean code | module | none | R25 |
| Module ignores row order | module | row_order_permutation_changes_nothing | none |
| Module raises on a missing source | module | negative_silent_recovery_from_missing_source | none |
| Corpus left as found | corpus | negative_module_mutates_the_corpus | none |
| Byte-identical reruns | artifacts | byte_identical_rerun | none |
| Exact serialisation format | artifacts | exact_serialization_format | none |
| Closing message states fourteen counterfactual integers | message | none | R1 through R14 |
| Closing message names the observation logs | message | none | R16 and R17 (via R26 cross-check) |
| Figures come from a real run | message | none | R24 |
| Claim transaction log read by position or first-match header | module | development_spine_exact | R19 |
| No two checks and no two criteria grade the same behaviour | spec | by construction below | by construction below |

No check and no judge criterion grade the same behaviour twice. Settlement convention values (`alae_convention`, `discount_curve`) are graded only on the judge side via R16, R17, R26, R29 and R30; the test channel reads `attachment` fields only. The fourteen counterfactual-integer criteria R1-R14 grade integers that appear in none of the nine artifacts, so no part of the judge channel can be satisfied by reading a document the test channel already graded. Each judge negative names a distinct action and no action carries more than five points of penalty across both channels.

## Root cause

Layer capacity is binding in ninety five of the ninety six (LOB, cycle) cells that carry claims, so the allocation is almost always binding and almost every figure in the output is the result of an interaction rather than a lookup. The corpus is arranged so that the ordinary habits of a careful reserving actuary give a wrong answer quietly. Sources disagree and the contract settles each field differently on each side of a cutover. One document is withdrawn and still describes the practice most people would expect. One errata item replaces a rule that reads perfectly well on its own. Two rules are absent and must be recovered from observation. IBNR accumulates, so an early mistake is carried to the end of the horizon rather than being averaged away.

**Red lines.** The contract documents and the four declaration files are the only authority. No figure of the shipped corpus may appear as a constant in the delivered module. The withdrawn handbook governs nothing. The settled readings must be reported rather than assumed. The counterfactual parameters are read from `counterfactual_parameters.md` at run time. The corpus is read only, the output directory holds exactly ten documents, every artifact is serialised byte-identical across reruns, and the module reproduces itself on an unseen extract.

## Solution shape

`solve.py` is one standard-library program with no network access and no state outside its arguments. It takes `--data` and `--out`, loads the four declaration files, then `counterfactual_parameters.md`, then the cycle marks, the claim master, the alias map, the underwriter authority roles, the retraction notices, the layer capacity declarations, the attachment factors, the curve marks, the attachment windows, the ceilings, the commitment agreements, the register, the exceptions, the two settlement logs, and the seven claim transaction logs, four cession bordereau parts, two fixed-width intake parts, five reserve event parts, three endorsement circular parts and three audit rotations. It settles the two withheld readings by enumeration, builds the claim population, resolves identity, drops rows whose reinsurer does not resolve, collapses cross-source rows, governs each field, applies endorsed circulars, replays the reserve state machine, walks the attachment graph under clash-cover, develops the chain-ladder spine over admitted rows with half-up rounding, converts once into whole dollars, applies the discount curve, carries lots forward, allocates each LOB cycle, honours retracted claims as frozen zero rows, and writes the ten documents with one space of indentation and sorted keys. A missing file raises `FileNotFoundError`. There is no fallback path that skips a stage. Nothing is printed to stderr during a successful run.

## Pitfalls

| Rank | Failure | Weight of the checks it defeats directly |
| --- | --- | --- |
| 1 | Sharing cession in proportion to the claim asked for rather than raising one fill level | 16 of 67 |
| 2 | Treating each cycle as independent and dropping the carried IBNR | 13 of 67 |
| 3 | Guessing a withheld reading rather than settling it from the observations | 10 of 67 |
| 4 | Reading the second paid_to_date column (position 5 or 7) of the claim transaction log | 11 of 67 |
| 5 | Applying individual-risk excess attachment at every pierced layer | 8 of 67 |
| 6 | Admitting rows recorded after the valuation date | 6 of 67 |
| 7 | Merging the two epochs of a reused reinsurer identifier | 6 of 67 |
| 8 | Honouring a treaty endorsement that nobody with the authority endorsed | 3 of 67 |

The top three carry thirty nine of the sixty seven positive points, which is more than half of the test total. Every one of these failures moves the ledger spine, and so carries into the IBNR carryforward, the cross-artifact identities, both unseen extracts and every rollup. A reference program carrying one of them on its own and nothing else earns between 2 and 13 of the 67 positive points.

## Provenance

```yaml
uuid: b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042
instance_id: b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042
task_name: terminal-bench/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042
language: python
status: sealed
solve_py_sha256: 8425798f118166bb3654a14caab6060f363f8692799aeac3d222667aa4568c39
expected_blob_sha256: 97ebd556d2ac8a1cf2be448ab33219a31e5779579b17509ad026f797e8db5d82
extract_A_sha256: e638e6c1d31a842cb8c91d233e39bef1b324c4a7c60f6e246ef53bb54c108a23
extract_B_sha256: 595622a032a860e8f2fff0efafed5c0d16e688414cb79b35a9a5729a8933cc0b
```


