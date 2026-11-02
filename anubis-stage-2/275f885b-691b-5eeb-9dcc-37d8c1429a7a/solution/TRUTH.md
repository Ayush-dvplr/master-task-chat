# TRUTH.md - 275f885b-691b-5eeb-9dcc-37d8c1429a7a

## Defect

The campaign corpus holds sixty files from nine logical recording systems that disagree with one
another, and no file says which disagreement matters. A settlement program has to resolve every
disagreement in one documented order and then ration a scarce perishable stock across four
veterinary regions, two holder segments and twenty four fortnightly rounds. The following items
are the work that decides the graded numbers.

1. **(focal) The governing head count is decided per field by a precedence that changes at a
   cutover, and the order itself is withheld.** `provenance_rules.md` names three candidate
   recording systems and states that one order governs before the cutover and another from it,
   without naming either. Only `governance_observations.log` settles it. Shipped split: 6819
   claims governed by the field intake, 3396 by the dispatch stream, 91 by the registry. Defeats
   `policy_audit_settled_rules_exact` and `ledger_entitlement_exact`.
2. **(focal) The ration ladder is a tier ordered integer level fill, not a proportional share.**
   `ration_rules.md` defines the waterline as the largest whole level whose capped sum fits the
   pooled doses, then one dose each in canonical identity order for the remainder, then cascade
   to the next tier. A proportional reading produces well formed documents and wrong awards
   everywhere. Defeats `ledger_award_exact`, `cell_ladder_exact` and every rollup check.
3. **(trap) Entitlement rounds half away from zero once, at entitlement, and the handling ceiling
   clamps after that rounding.** 455 shipped claims land on an exact half and 1430 claims clamp.
   Rounding those halves to even moves their entitlements and every award built on them, while
   clamping before the rounding leaves the entitlements as they are and changes the clamp count.
   Defeats `ledger_entitlement_exact`, `ledger_spine_exact` and `audit_tallies_exact`.
4. **(trap) Lot dose content comes from three declared measurement bases and a laboratory assay
   overrides the reference table.** 3626 pooled lots take their content from a fixed width assay
   with three implied decimals, 7177 from the reference table, and four depot and production year
   pairs declare no basis at all. Defeats `cell_ladder_exact` and `audit_tallies_exact`.
5. **(drift) The retired runbook offers seven plausible methods and governs nothing.** It
   proposes the latest requisition row whatever its recording time, species and age class read
   from the requisition, the handling ceiling applied to the head count before the dose factor,
   pro rata sharing with the remainder to the largest claim, carried quantities dropped after
   three rounds, newest first drawing, and an off target serotype treated as unusable. Defeats
   `ledger_entitlement_exact`, `ledger_award_exact` and `ledger_served_lot_exact`.
6. **(trap) Carried claims survive under a cap and die under three causes.** The next round claim
   equals the deferred quantity capped at twice the current entitlement. A `no_show` event for a
   block that settles a claim in that round extinguishes it (106 shipped), a restock epoch change
   extinguishes it (8 shipped), and a clearing round extinguishes it region wide. Defeats
   `ledger_spine_exact`.
7. **(trap) The round calendar is derived, never shipped as a list.** The anchor and the
   fortnightly recurrence produce twenty four codes, the exception register removes one round and
   moves others, and the removed round's 456 claims settle in R14. Defeats `cell_ladder_exact`
   and `summary_totals_exact`.

Out of bounds: the delivered program must not embed campaign answers or corpus rows
(`negative_hardcoded_sample_answers`, `negative_embedded_corpus_rows`), must not vary between two
runs over one corpus (`negative_nondeterministic_rerun`), must not produce output independent of
the corpus it reads (`negative_output_independent_of_the_corpus`), must not read a fixed corpus
path (`negative_module_reads_a_fixed_corpus_path`), must not settle an incomplete export
(`negative_silent_recovery_from_missing_source`), must not leave undeclared files in the output
folder (`negative_output_directory_has_extra_files` and criterion R38), must not write inside the
corpus folder (`negative_module_mutates_the_corpus` and criterion R36), must not open a socket or
run an external command (`negative_module_opens_network_or_shells_out`), and must not import
beyond the Python standard library (`negative_module_imports_beyond_standard_library`). In the
judged channel the agent must not hedge a demanded figure (R32), must not name a settled reading
that contradicts its own policy audit (R33), must not open grading material (R34), must not claim
a verification run that never happened (R35), must not leave out the evidence that settled an
unstated rule (R37), must not copy an illustrative figure from a rule document into the program
(R39), must not repeat one failing command (R40), and must not present pooled content as
available doses (R41).

## Load-bearing work

The spine is the per claim pair `awarded_to_date` and `deferred_to_date`, emitted on every ledger
row beside the healing `carry_forward_doses`. Awards accumulate forward and deferrals never heal,
so one wrong decision in an early round travels through every later round of that identity and
through the cells, the segment rollups and the summary. Seven of the eight weight 5 checks read a
spine value or the awards it accumulates, directly or through a rollup; the eighth,
`policy_audit_settled_rules_exact`, reads the settled readings. Three of the twelve weight 3
checks, `segment_rollups_exact`, `summary_totals_exact` and `unseen_extract_rollups_exact`, read
rollups of the awards; the other nine read supporting fields and registers.

Four readings carry the task. Each one changes at least half the graded units on its own.

| Reading | Where it is settled | Shipped incidence | Graded value it moves |
|---|---|---|---|
| Governing source order and cutover | `provenance_rules.md` plus `governance_observations.log` | 2400 observation records, 1607 field intake, 777 dispatch stream, 16 registry | `entitlement_doses`, the spine, `governing_source` in the policy audit |
| Tier ordered integer level fill | `ration_rules.md` | 59 cells reach the remainder step, 1911 claims take one remainder dose | `awarded_doses`, `waterline`, `binding_tier`, every rollup |
| Carry cap, extinguishment and clearance scope | `carry_rules.md` plus `clearance_observations.log` | 2100 observation records, 1250 cleared, 106 no_show deaths, 8 epoch deaths | `carried_claim_doses`, `cleared_balances`, the spine |
| Lot pooling, expiry and measurement basis | `supply_rules.md`, `unit_declarations.ini`, `potency_assays_h1.txt` | 12880 lot rows, 10803 pooled, 2077 never pooled, 3626 assay governed | `available_doses`, `served_lot`, `substitution_hops`, `written_off_doses` |

Supporting rules sit off the spine on purpose. Getting the alias hops, the stale revisions, the
illegal transitions or the header gaps wrong costs one field family and leaves the rest standing,
so partial credit is real.

## Verification

Test channel: thirty two checks. Eight at weight 5, twelve at weight 3, two at weight 1, and ten
negatives: three at minus 5, three at minus 3 and four at minus 1. Positive total 8 times 5 plus
12 times 3 plus 2 times 1 equals 78. Negative magnitude 28, which stays under the positive total.
The channel weight is 0.5 divided by 78, which is 0.00641025641025641.

Weight 5: `ledger_spine_exact`, `ledger_award_exact`, `cell_ladder_exact`,
`policy_audit_settled_rules_exact`, `program_reproduces_unseen_extract_alpha`,
`program_reproduces_unseen_extract_beta`, `row_order_permutation_changes_nothing`,
`cross_artifact_identity_triangle_holds`.
Weight 3: `ledger_entitlement_exact`, `ledger_outcome_exact`, `ledger_served_lot_exact`,
`ledger_order_exact`, `segment_rollups_exact`, `summary_totals_exact`, `audit_tallies_exact`,
`data_quality_registers_exact`, `unseen_extract_rollups_exact`,
`unseen_extract_quality_registers_beta`, `unseen_extract_quality_registers_exact`,
`unseen_extract_audit_tallies_exact`.
Weight 1: `artifacts_present_and_parse`, `program_runs_and_exits_clean`. Hygiene is therefore 2 of
78, which is 2.6 per cent.
Negatives: `negative_hardcoded_sample_answers`, `negative_embedded_corpus_rows`,
`negative_nondeterministic_rerun` at minus 5; `negative_output_independent_of_the_corpus`,
`negative_module_reads_a_fixed_corpus_path`, `negative_silent_recovery_from_missing_source` at
minus 3; `negative_output_directory_has_extra_files`, `negative_module_mutates_the_corpus`,
`negative_module_opens_network_or_shells_out`, `negative_module_imports_beyond_standard_library`
at minus 1.

Eight checks reach their verdict from corpora the agent never sees, three of them from a second
extract, and two further checks pair a shipped family with the same family on the first extract so
that a wrong reading on either side fails them. Counting each check once, the work that still pays
when a shipped source is deleted is 28 of 78, which is 35.9 per cent and stays inside the ceiling
for this input shape.

Judged channel: forty one criteria. Twenty two payload criteria at weight 3, one per demanded
quantity, six derivation criteria at weight 3, three single point criteria, ten negatives. Positive
total 22 times 3 plus 6 times 3 plus 3 times 1 equals 87. Payload share is 66 of 87, which is 75.9
per cent. Free credit is the three single point criteria, 3 of 87, which is 3.4 per cent. Negative
magnitude 30. The channel weight is 0.5 divided by 87, which is 0.005747126436781609.

Any score quoted during development is tests only. The judged channel is never self scored.

### Traceability

| Requirement | Artifact | Checks and weights | Criteria |
|---|---|---|---|
| Admission by half open claim window in depot local time | region documents | `ledger_order_exact` 3, `ledger_spine_exact` 5 | R19, R20 |
| As of cutoff on the recorded moment | `data_quality.json` | `data_quality_registers_exact` 3 | R19, R20 |
| Key normalisation before any join | region documents | `ledger_spine_exact` 5 | none |
| Effective dated alias hops | region documents | `ledger_spine_exact` 5, `audit_tallies_exact` 3 | none |
| Restock epoch in the identity | region documents | `ledger_spine_exact` 5, `data_quality_registers_exact` 3 | none |
| Collapse of near duplicate requisitions | region documents | `ledger_entitlement_exact` 3, `audit_tallies_exact` 3 | none |
| Governing head count by precedence and cutover | region documents, `policy_audit.json` | `policy_audit_settled_rules_exact` 5, `ledger_entitlement_exact` 3 | R1 to R7, R23, R33 |
| Highest version with the later recorded moment | region documents | `ledger_entitlement_exact` 3 | none |
| Registry null forms and attribute overrides | region documents | `ledger_entitlement_exact` 3, `audit_tallies_exact` 3 | none |
| Dose factor in force at the window opening | region documents | `ledger_entitlement_exact` 3 | none |
| Half away from zero at entitlement only | region documents | `ledger_entitlement_exact` 3, `audit_tallies_exact` 3 | none |
| Handling ceiling clamp after rounding | region documents | `ledger_entitlement_exact` 3, `audit_tallies_exact` 3 | none |
| Amendment authority scope and timeliness | region documents, `data_quality.json` | `ledger_entitlement_exact` 3, `data_quality_registers_exact` 3 | none |
| Lot identity by production year | region documents | `ledger_served_lot_exact` 3 | none |
| Lot state chain, supersession and cycles | `policy_audit.json`, `data_quality.json` | `audit_tallies_exact` 3, `data_quality_registers_exact` 3 | R10, R11 |
| Measurement basis and assay override | region documents, cells | `cell_ladder_exact` 5, `audit_tallies_exact` 3 | R12 to R16, R41 |
| Expiry as a half open interval and write off | cells | `cell_ladder_exact` 5 | R14, R15, R16 |
| Substitution hops and potency derate | region documents | `ledger_served_lot_exact` 3, `cell_ladder_exact` 5 | R14, R15, R16 |
| Tier order, waterline and remainder order | region documents, cells | `ledger_award_exact` 5, `cell_ladder_exact` 5 | R21, R22, R26 |
| Carry cap, extinguishment and clearance scope | region documents, cells | `ledger_spine_exact` 5, `policy_audit_settled_rules_exact` 5 | R8, R9, R24, R33 |
| Derived round calendar and the removed round | cells, `summary.json` | `cell_ladder_exact` 5, `summary_totals_exact` 3 | R17, R18, R27, R28 |
| Outcome and reason registers | region documents | `ledger_outcome_exact` 3 | none |
| Segment rollups by region and round | segment documents | `segment_rollups_exact` 3, `cross_artifact_identity_triangle_holds` 5 | none |
| Horizon totals and lists | `summary.json` | `summary_totals_exact` 3, `cross_artifact_identity_triangle_holds` 5 | none |
| Reject and counted registers in register order | `data_quality.json` | `data_quality_registers_exact` 3 | R25 |
| One program taking the corpus folder on its command line | `derive_report.py` | `program_runs_and_exits_clean` 1, `negative_module_reads_a_fixed_corpus_path` minus 3, `negative_module_imports_beyond_standard_library` minus 1 | R30, R31 |
| Same result on unseen extracts | all documents | `program_reproduces_unseen_extract_alpha` 5, `program_reproduces_unseen_extract_beta` 5, `unseen_extract_quality_registers_exact` 3, `unseen_extract_audit_tallies_exact` 3, `unseen_extract_rollups_exact` 3, `unseen_extract_quality_registers_beta` 3 | R38 |
| Row order independence | all documents | `row_order_permutation_changes_nothing` 5 | none |
| Closing message figures | none | none | R1 to R22, R29, R32, R37 |

### Overlap

The tests read artifact bytes. The judged criteria read the trajectory and the closing message.
No criterion names a field of any document. Each payload figure was traced through all nine
documents and appears in none of them: the governing source split, the registry governed claim
count and its distinct block count, the three observation token counts, the clearance token
counts, the pooled and never pooled lot counts, the assay and reference table split, the pooled
content before and after the derate, the round the removed round's claims settled in and how many
arrived that way, the two window boundary refusal counts, and the remainder reach. The lot row
total and the removed round code were deliberately dropped from the payload because the registers
in `data_quality.json` and `summary.json` carry them, and the record counts of the two
observation logs were dropped because each log declares its count on its first line.

R23 and R24 grade the derivation in the trajectory while `policy_audit_settled_rules_exact` grades
the settled token in the document and R33 grades a message that contradicts that token: three
distinct observables. R36 grades the agent writing inside the corpus folder during its session,
`negative_module_mutates_the_corpus` grades the delivered program writing there at grading time.
R38 grades undeclared files the agent leaves in its own output folder during the session, while
`negative_output_directory_has_extra_files` grades undeclared files the delivered program writes
when the verifier runs it on an unseen extract. The standard library rule and the command line
interface are graded by the test channel only. The corpus shortcut negatives stand down in a fixed
order, literal totals first, then embedded corpus rows, then output independent of the corpus,
then a document written from an incomplete export, which also stands down after an unsteady
rerun; the fixed path negative stands down when a rerun under the same folder name disagrees with
itself. One shortcut
therefore costs at most 5 in the test channel, and no single agent action fires more than one
criterion at minus 5 in either channel.

## Root cause

The crux: scarcity is settled by a tier ordered integer waterline over a pool whose size depends
on four evidence resolutions that no single file states, and the resulting award feeds a carried
claim that re enters the next round, so the campaign is one sequential computation with no local
patch.

The spine is `awarded_to_date` paired with the never healing `deferred_to_date`. The interaction
matrix shows why no reading can be fixed on its own.

| Reading | Interacts with |
|---|---|
| Governing source order | entitlement rounding, the ceiling clamp, the carried claim, the waterline |
| Level fill waterline | carried claim, clearance scope, pooled content, tier register |
| Carry cap and clearance | waterline, epoch identity, visit events |
| Pooled content and expiry | waterline, substitution hops, write off, measurement basis |
| Epoch identity | carried claim extinguishment, admission rejects, alias hops |
| Derived calendar | admission windows, clock offsets, the removed round rollover |

Two readings are withheld and both are settled by evidence. The governing order is settled by the
2400 records of `governance_observations.log`: of the three candidate orders only one reproduces
every token, and the counts by source are 1607, 777 and 16. The clearance scope is settled by the
2100 records of `clearance_observations.log`: the tokens for blocks that settled no claim in a
clearing round separate region wide clearance from clearance limited to fully awarded blocks or to
the first tier. Flipping either reading contradicts at least one observation record, so neither is
a guess. Every other rule is stated in the corpus, including the four conventions made explicit
during review: the dispatch record in view is bounded by the claim window of that claim, the
amendment baseline for a registry offered head count is the start of the local calendar day on
which that window opens, two visit events sharing an identifier and differing in any other field
register nothing anywhere, and a `no_show` extinguishes the carried claim of an identity that
settles a claim in that round before any clearing round is considered.

**Red lines.** The corpus states every rule except the two readings the observation logs settle,
and those two are decided by evidence rather than by preference. No file holds an expected
document, a worked composite example, a count of correct rows or a checksum of an answer. The
retired runbook is signposted as governing nothing. Nothing in the corpus names a file by the
deliverable it feeds.

## Solution shape

A single standard library program reads the corpus folder named on its command line, resolves the
evidence in the stated dependency order, rations each region and round, and writes nine documents
into the output folder. It holds no campaign constant, no corpus row and no fallback that skips a
required source: an absent named file ends the run before any document is written.

## Ordered plan

1. Read the manifest and the corpus index, and load every named file from the folder given on the
   command line. Artifact: none.
2. Derive the round calendar from the anchor and the recurrence, apply the exception register in
   issue order, and fix each window as a half open interval in depot local time with the declared
   day start. Artifact: cells of the region documents.
3. Resolve identities: normalise the holding key, walk the alias hops in force, and attach the
   restock epoch. Artifact: the `block` field of every ledger row.
4. Admit requisitions by window and recorded moment, collapse near duplicates inside the declared
   span, and register every refusal under one reject code. Artifact: `data_quality.json`.
5. Settle the governing order against the governance observations, then take the governing head
   count per claim. Artifact: `policy_audit.json`.
6. Apply the authorised and timely head count amendments, compute entitlement with one half away
   from zero rounding, then clamp to the handling ceiling as amended. Artifact: `entitlement_doses`.
7. Build each regional pool: resolve lot state chains, exclude cycles and expired lots, convert
   the declared measurement basis with the assay override, and apply substitution derates.
   Artifact: `available_doses`.
8. Run the ladder per region and round: tiers in order, integer waterline, one dose remainder in
   canonical identity order, cascade the surplus. Artifact: `awarded_doses` and `waterline`.
9. Settle the clearance scope against the clearance observations, then carry, cap or extinguish
   each deferred claim. Artifact: `carry_forward_doses` and `cleared_balances`.
10. Fold the ledger into segment rollups, horizon totals, audit tallies and the three registers,
    each in register order. Artifact: the segment documents, `summary.json`, `policy_audit.json`
    and `data_quality.json`.

Reference closing message: the field intake governed 6819 claims and the dispatch stream 3396. The
registry governed 91 claims across 84 distinct blocks. Of the governing tokens in the governance log,
1607 name the field intake, 777 the dispatch stream and 16 the registry, which settles the
field intake before the cutover and the dispatch stream from it. In the clearance log 1250
entries record a cleared carried claim and 850 one left standing, and the tokens for blocks that settled no claim show the scope is
region wide. Of the lot register, 10803 lots entered a regional pool and 2077 never entered one.
Of the pooled lots, 3626 took their content from a laboratory assay and 7177 from the reference
table, and four depot and production year pairs declare no basis. Pooled content was 9645348
doses before the derate and 8303519 after it, so the derate cost 1341829 doses. The claims of the
removed round settled in R14 and 456 claims arrived that way. The window rule refused 47
requisitions at the closing instant and 142 before the opening instant. The remainder step ran in
59 cells and gave one dose each to 1911 claims.

## Pitfalls

Ranked by the positive points each wrong reading puts at risk, measured by running the oracle
with that one reading changed against the test channel. Counting each check once, the top three
together reach 68 of 78, which is well over a third of the channel.

| Rank | Wrong reading | Points at risk | Checks it fails |
|---|---|---|---|
| 1 | Fixing the governing order as the field intake throughout | 65 | spine, award, cells, settled rules, entitlement, outcome, served lot, rollups, summary, audit tallies, data quality, both held out extracts, permutation, held out rollups, held out quality and tallies |
| 2 | Ignoring the collapse span for near duplicates | 63 | spine, award, cells, entitlement, outcome, served lot, rollups, summary, audit tallies, data quality, both held out extracts, permutation, held out rollups, every held out register and tally check |
| 3 | Proportional sharing in place of the integer waterline | 59 | spine, award, cells, settled rules, entitlement, outcome, served lot, rollups, summary, audit tallies, both held out extracts, permutation, held out rollups, held out tallies |
| 4 | Newest first lot drawing | 56 | spine, award, cells, settled rules, entitlement, outcome, served lot, rollups, summary, audit tallies, both held out extracts, permutation, held out rollups |
| 5 | The handling ceiling applied to the head count before the dose factor | 54 | spine, award, cells, entitlement, outcome, served lot, rollups, summary, audit tallies, both held out extracts, permutation, held out rollups, held out tallies |
| 6 | Remainder order taken from the replaced sentence | 48 | spine, award, cells, entitlement, outcome, served lot, rollups, summary, both held out extracts, permutation, held out rollups |
| 7 | Rounding exact halves to even at entitlement | 45 | spine, award, cells, entitlement, served lot, rollups, summary, both held out extracts, permutation, held out rollups |
| 8 | Fixing the clearance scope as fully awarded blocks only | 43 | spine, award, cells, settled rules, entitlement, outcome, served lot, rollups, summary, audit tallies, second held out extract |
| 9 | Clamping the handling ceiling before the rounding | 3 | audit tallies |

## Provenance

```yaml
uuid: 275f885b-691b-5eeb-9dcc-37d8c1429a7a
instance_id: 275f885b-691b-5eeb-9dcc-37d8c1429a7a
task_name: terminal-bench/275f885b-691b-5eeb-9dcc-37d8c1429a7a
fix_patch_sha256: aac3eee34e3c40012844a80fab1e49e2620631faa857322ede02b9e64a301892
solve_py_sha256: 60b02b5333731935a478cf7dfa2246cad3e2f2b6181bda0ac6ed50a853db8653
language: python
```
