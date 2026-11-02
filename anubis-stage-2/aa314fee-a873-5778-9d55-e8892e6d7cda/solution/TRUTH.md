# TRUTH.md - aa314fee-a873-5778-9d55-e8892e6d7cda

## Defect

The corpus describes twenty four semi monthly wafer start cycles at four fabrication sites and asks for an apportionment of scarce capacity, yet the evidence that fixes every input to that apportionment is spread across forty two record and declaration files written by thirteen different systems, and several of those systems disagree. The work is wrong in a believable way unless each of the following is handled.

1. (focal) The shared fill level. Capacity is handed out by raising one level across every claiming request of a site cycle after the committed minimums are paid, so the grant of any request depends on the claims of all the others in that cell. The habitual reading, sharing capacity in proportion to the quantities asked for, is written down in `legacy_runbook.md` and is withdrawn. Defeats `region_ledger_backbone_exact` and `site_cycle_capacity_and_fill_exact`.
2. (focal) The carried shortfall. An unmet claim becomes a lot that attaches to the same identity and site, survives a withheld number of cycles, is cut before the current quantity when a ceiling binds, is discharged oldest first when a grant arrives, and is cleared outright at a site whose cycle ends with capacity unused. The running totals never heal, so one wrong decision at cycle five is still visible at cycle twenty four. Defeats `cumulative_shortfall_spine_exact`.
3. (focal) The two withheld rules. Neither the governor of quantity before the July cutover nor the survival age of a carried lot is stated anywhere in the contract. Each has to be settled by testing the candidate readings against a settlement log, and the surviving reading has to be reported in `policy_audit.json`. A guess that fits part of the log is wrong. Defeats the backbone checks and judge criteria R9 and R10.
4. (drift) The single conversion stage. `rounding_rules.md` section 2 describes a conversion that rounds at every substitution hop; `errata_2031-07.md` replaces that section with one conversion for the whole walk. Rounding per hop moves a small share of rows by one wafer equivalent and nothing else, which looks like a clean result. Defeats `substitution_served_node_and_hops_exact` and `granted_wafers_truncation_exact`.
5. (drift) The duplicate column title. Every order book part carries two columns titled `quantity`. The first governs. A dictionary reader keeps the second, which agrees with the first on roughly four rows in five. Defeats the backbone checks through the governing quantity.
6. (trap) Admission by recorded instant. Rows recorded after `2032-01-10T00:00:00Z` are evidence of nothing, including capacity revisions, ceilings, exceptions, state events and amendment notices. Defeats `data_quality_source_counts_exact` and the backbone.
7. (trap) Identity across epochs. A reused customer identifier carries two epochs with different segments, and the two epochs share no ceiling, no commitment and no carried lot. Defeats `segment_rollups_exact` and `cross_artifact_identity_triangle_holds`.
8. (trap) The substitution walk. A request for an unqualified node walks the cheapest edge in force at the cycle start, at most three hops, and two nodes close a cycle between them. The shortest path to any qualified node is a different answer. Defeats `substitution_served_node_and_hops_exact`.
9. (trap) Endorsement of amendments. A notice counts only when it was recorded after the row it amends and an approver holding that scope endorsed it at the audit instant, across three rotated log files whose stamps carry a per site recorder skew. Defeats `policy_audit_state_and_floor_tallies_exact`.
10. (trap) The state machine. Events apply by ascending version rather than file order, a stale version is ignored, an illegal move leaves the state unchanged and still counts, and only an approved request claims capacity while held, withdrawn and rejected requests keep a ledger row of zeros. Defeats `outcome_and_reason_vocabulary_exact`.

Out of bounds: the delivered module must not hold any figure of the shipped corpus as a constant (`negative_hardcoded_sample_answers`), must not embed corpus rows (`negative_embedded_corpus_rows`), must give the same answer twice (`negative_nondeterministic_rerun`), must derive its answers from the corpus it is handed rather than from stored results (`negative_output_independent_of_the_corpus`), must leave the corpus untouched (`negative_module_mutates_the_corpus`), must raise rather than skip a stage when a source is missing (`negative_silent_recovery_from_missing_source`), must write only the nine documents (`negative_output_directory_has_extra_files`), must behave the same whatever the directory is called (`negative_module_reads_a_fixed_corpus_path`), and must stay offline and inside the interpreter (`negative_module_opens_network_or_shells_out`).

## Load-bearing work

The spine is one quantity, the wafer equivalent, carried on every ledger row of every site document and accumulated per identity and site in `granted_to_date_equiv` and `deficit_to_date_equiv`. Every load bearing decision moves it.

Eight stages produce it. Admission filters every file by recorded instant. Identity resolution maps three spellings and three alias prefixes onto a canonical identifier and attaches the epoch in force at the record instant. Collapse groups the rows of one request across sources inside the declared window and settles each field by the precedence in force on its side of the cutover, with the governor of quantity before the cutover settled from `governance_observations.log`. Amendment and state resolution then decide whether the request claims at all. The substitution walk fixes the served node and the conversion path. One conversion stage turns wafers, ceilings and floors into wafer equivalents with a half up rounding. Carry forward adds the surviving lots to the claim under the ceiling. Apportionment pays the honoured minimums in register order, raises the shared fill level to the greatest whole number the capacity allows, and hands the indivisible remainder out one equivalent at a time by unmet claim, governing instant, identity and reference.

Trap incidence over the shipped corpus:

| Trap | Firing records | Graded value that changes |
| --- | --- | --- |
| Quantity disagreement between sources | 4032 | governing quantity, claim, grant, both running totals |
| Node disagreement between sources | 2017 | served node, hops, conversion, grant |
| Rows recorded after the admission instant | 483 | admitted counts, claims, grants, late tallies |
| Rows one second inside a cycle start | 399 | cycle placement, fill level of two cells |
| Quantities declared in lots of twenty five | 1140 | quantity in equivalents, claim, grant |
| Audit restatement differing from the governing column | 5366 | governing quantity when the second column is read |
| Identical duplicates inside one source | 386 | duplicate tallies only |
| Conflicting duplicates inside one source | 277 | governing row, grant |
| Rows ninety one minutes apart | 130 | request count of a cell, fill level |
| Requests outside the horizon | 118 | out of scope placement |
| Unresolved customer references | 88 | out of scope placement, unknown tallies |
| Stamps inside a missing local hour | 93 | cycle placement |
| Stamps inside a repeated local hour | 92 | cycle placement |
| Parenthesised negative capacity deltas | 123 | capacity, fill level, grants of a whole cell |
| Continuation lines in the audit logs | 1552 | endorsement of amendments |
| Alias coded intake rows | 3404 | identity, epoch, carried lots |

## Verification

The test channel registers twenty seven checks with a positive total of sixty six: eight at weight five, eight at weight three, two at weight one, and nine negative checks whose magnitudes total twenty seven. The judge channel registers twenty nine criteria with a positive total of sixty two: eight payload criteria at weight five, five derivation criteria at weight three, seven criteria at weight one, and nine negative criteria whose magnitudes total twenty seven. Reward weights are 0.5 divided by sixty six and 0.5 divided by sixty two.

| Requirement in the instruction | Artifact | Test check | Judge criterion |
| --- | --- | --- | --- |
| Ledger rows ordered by cycle, identity, reference | region documents | region_ledger_backbone_exact | none |
| Grants satisfy the four stated properties | region documents | site_cycle_capacity_and_fill_exact | R16 |
| Fill level reported per site cycle | region documents | site_cycle_capacity_and_fill_exact | none |
| Running totals never heal | region documents | cumulative_shortfall_spine_exact | none |
| Carried amounts survive a settled number of cycles | region documents | cumulative_shortfall_spine_exact | R10 |
| Capacity built from the tool group declarations | region documents | site_cycle_capacity_and_fill_exact | R15 |
| Served node and hops reported | region documents | substitution_served_node_and_hops_exact | R11 |
| Wafer figure derived by truncation | region documents | granted_wafers_truncation_exact | none |
| One outcome and one reason per row | region documents | outcome_and_reason_vocabulary_exact | none |
| Out of scope rows kept apart | region documents | summary_spine_and_out_of_scope_exact | none |
| Identity carries its epoch | all documents | cross_artifact_identity_triangle_holds | R14 |
| Segment rollups agree with the ledger | segment documents | segment_rollups_exact | none |
| Rule firings counted | policy_audit.json | policy_audit_state_and_floor_tallies_exact | none |
| Substitution and clearing counted | policy_audit.json | policy_audit_substitution_and_clearing_exact | none |
| Settled readings reported | policy_audit.json | policy_audit_substitution_and_clearing_exact | R9 and R10 |
| Source counts per declaration | data_quality.json | data_quality_source_counts_exact | none |
| Anomaly tallies | data_quality.json | data_quality_anomaly_tallies_exact | R13 |
| Totals and residuals agree | summary.json | cross_artifact_identity_triangle_holds | none |
| Module reruns on unseen extracts | module | program_reproduces_unseen_extract_alpha and beta | none |
| Module reads as clean code | module | none | R18 |
| Module ignores row order | module | row_order_permutation_changes_nothing | none |
| Module raises on a missing source | module | negative_silent_recovery_from_missing_source | none |
| Corpus left as found | corpus | negative_module_mutates_the_corpus | R27 |
| Closing message states eight pairs of figures | message | none | R1 through R8 |
| Closing message names the evidence that settled each absent rule | message | none | R28 and R29 |
| Figures come from a real run | message | none | R17, R19 and R21 |
| Order book read by position | module | region_ledger_backbone_exact | R12 |

No check and no criterion grade the same behaviour twice. The test channel reads artifact bytes and the behaviour of the delivered module; the judge channel reads the trajectory and the closing message. The eight payload criteria grade sixteen integers that appear in none of the nine artifacts, so no part of the judge channel can be satisfied by reading a document the test channel already graded. Each judge negative names a distinct action, and no action carries more than five points of penalty across both channels.

## Root cause

Capacity is scarce in ninety five of the ninety six site cycles, so the apportionment is almost always binding and almost every figure in the output is the result of an interaction rather than a lookup. The corpus is arranged so that the ordinary habits of a careful engineer give a wrong answer quietly. Sources disagree and the contract settles each field differently on each side of a cutover. One document is withdrawn and still describes the practice most people would expect. One errata item replaces a rule that reads perfectly well on its own. Two rules are absent and must be recovered from observation. Shortfalls accumulate, so an early mistake is carried to the end of the horizon rather than being averaged away.

**Red lines.** The contract documents and the four declaration files are the only authority. No figure of the shipped corpus may appear as a constant in the delivered module. The withdrawn runbook governs nothing. The settled readings must be reported rather than assumed. The corpus is read only, the output directory holds exactly nine documents, and the module must reproduce itself on an unseen extract.

## Solution shape

`solve.py` is one standard library program with no network access and no state outside its arguments. It takes `--data` and `--out`, loads the four declaration files, then the clock marks, the customer master, the alias map, the authority roles, the retractions, the capacity declarations, the substitution factors, the ceilings, the agreements, the register, the exceptions, the two settlement logs, and the six order book parts, four registry parts, two intake parts, five event parts, three notice parts and three audit rotations. It settles the two withheld readings by enumeration, builds the request population, resolves identity, collapses cross source rows, governs each field, applies endorsed amendments, replays the state machine, walks the substitution graph, converts once into wafer equivalents, carries lots forward, apportions each site cycle, and writes the nine documents with one space of indentation and sorted keys. A missing file raises. There is no fallback path that skips a stage.

## Ordered plan

1. Read `corpus_index.md` and `source_manifest.md` and list every file with its row layout.
2. Load the four declaration files, resolving the inheritance chains of the policy file nearest first.
3. Build the site clock from `site_clock_marks.csv` and place the forty eight cycle boundaries.
4. Filter every source by recorded instant against the admission instant and tally what was dropped.
5. Resolve identity across the three spellings and the alias prefixes, attaching the epoch in force.
6. Collapse cross source rows inside the declared window and settle each field by the precedence in force.
7. Settle the governor of quantity before the cutover from `governance_observations.log` by enumeration.
8. Apply endorsed amendment notices and resolve the supersedes chains.
9. Replay the state events by version and decide which requests claim.
10. Walk the substitution graph at each cycle start and record the served node, the hops and the factor product.
11. Convert quantities, ceilings and floors once into wafer equivalents with a half up rounding.
12. Settle the survival age from `deficit_observations.log` by enumeration and carry the surviving lots in.
13. Pay the honoured minimums in register order, then raise the shared fill level, then hand out the remainder.
14. Accumulate the running totals and clear the lots of a site whose cycle ended with capacity unused.
15. Emit the four site documents, the two segment documents, the summary, the audit and the quality report.
16. Rerun the module on a second directory and compare the bytes.

Reference closing message:

The derivation is complete and the nine documents are in `/app/out`. Across the four site documents the ledger carries 23022 rows, 2639795 wafer equivalents were handed out, and the running shortfall totals 1690162 wafer equivalents. The governor of quantity before the cutover is the order book, settled from `governance_observations.log` because every settlement line names the order book even where the registry carries the later recorded instant. A carried lot survives two cycles, settled from `deficit_observations.log` because every line of age one or two is carried and every line of age three or more is expired. First, holding every carried amount at zero hands out 2628151 wafer equivalents and moves 851 ledger rows to a different outcome. Second, reading the contract registry as the governor before the cutover moves the governing quantity of 1877 requests and gives a granted total of 2639801. Third, a survival age of three cycles expires 2823 lots and leaves a running shortfall of 1853621. Fourth, leaving the clearing rule unused raises the running shortfall to 1697490 and alters 205 grants. Fifth, the one at a time remainder step hands out 3221 wafer equivalents across 95 site cycles. Sixth, with the admission instant lifted for every file, 171 requests whose every source row was recorded after the admission instant would have claimed, totalling 49249 wafer equivalents of claim. Seventh, honouring every amendment whatever its endorsement moves 239 governing quantities and shifts the fill level in 39 site cycles. Eighth, the withdrawn proportional practice hands out 2626670 wafer equivalents and alters 14832 grants.

## Pitfalls

| Rank | Failure | Weight of the checks it defeats directly |
| --- | --- | --- |
| 1 | Sharing capacity in proportion to the quantities asked for rather than raising one fill level | 16 of 66 |
| 2 | Treating each cycle as independent and dropping the carried shortfall | 13 of 66 |
| 3 | Guessing a withheld reading rather than settling it from the observations | 13 of 66 |
| 4 | Reading the second quantity column of the order book | 11 of 66 |
| 5 | Rounding at every substitution hop | 8 of 66 |
| 6 | Admitting rows recorded after the admission instant | 6 of 66 |
| 7 | Merging the two epochs of a reused identifier | 6 of 66 |
| 8 | Honouring an amendment that nobody with the scope endorsed | 3 of 66 |

The top three carry forty two of the sixty six positive points, which is more than one third of the test total.

The column counts only the checks each failure defeats directly, so it understates what a run actually scores. Every one of these failures moves the ledger spine, and so carries into the cumulative shortfall, the cross artifact identities, both unseen extracts and every rollup. A reference program carrying one of them on its own and nothing else earns between 2 and 13 of the 66 positive points, so none of the eight is a local slip that costs only the checks named beside it.

## Provenance

```yaml
uuid: aa314fee-a873-5778-9d55-e8892e6d7cda
instance_id: aa314fee-a873-5778-9d55-e8892e6d7cda
task_name: terminal-bench/aa314fee-a873-5778-9d55-e8892e6d7cda
fix_patch_sha256: fce3d354282829f77c17bc36291e621ee506ddaaa07a4cac43ca433f673100b3
solve_py_sha256: fce3d354282829f77c17bc36291e621ee506ddaaa07a4cac43ca433f673100b3
language: python
status: complete
```
