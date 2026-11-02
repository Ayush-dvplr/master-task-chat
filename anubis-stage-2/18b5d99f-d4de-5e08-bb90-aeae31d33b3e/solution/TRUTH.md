# TRUTH.md - 18b5d99f-d4de-5e08-bb90-aeae31d33b3e

## Defect

The extract is a metered cloud billing extract: five scenario workloads rated under one rules file, an identity registry with a FINAL export snapshot, merge records, errata, a per-extract rate card with published batch figures, and two closing journals of the retired legacy engine. Four things are never written down: the kind weights (2 to 40 per kind), the cancellation table of the extract, the withdrawal rule and the standing rule. The documents state only the form of each (rate_card.md, legacy_notes.md); they never say which file decides which unknown, never say that a unique configuration exists, and list no candidate menu. The weights and the table differ in every extract and must be settled at run time from that extract's own rate card and both journals; the two rules are the same in every extract.

The shipped extract is deliberately degenerate: its rate card fixes the weights alone, and its workloads exercise none of the distinctions below, so a model that checks itself only against the shipped reports cannot see its wrong readings. The hidden extracts break every degeneracy at once and carry 92.2% of the test weight.

Graded items and the checks they defeat:

- (focal) Spine: the carried value. scoring_rules.md (Carried value) states the carry arithmetic and points to the record dictionary; schema.md (Carry chain) states that only processed ordinary rows are chain rows, that control rows take no carry and keep their base value, and that there is one chain per billing region of the booked account. One global chain defeats every report and every extract.
- (focal) Kind weights with absent kinds. On the shipped card (8 batches over all 8 kinds) the figures fix the weights; every hidden extract has six to twelve kinds (fourteen of them ten to twelve) with two to eight kinds absent from a card of few batches, so the figures leave 39^5 to 39^11 assignments; plain enumeration of the free weights exceeds the 60 s per-call limit on the weak extracts, and only a search pruned by the withdrawal journal passes.
- (focal) Joint settlement by two journals. The withdrawal journal (close states only, lines shuffled, variable-width row ids) leaves 3 complete (weights, table) candidates on every hidden extract (5 on wk11a); only the raw-row standing journal, re-rated with no carry and floor 2000, keeps one.
- (focal) Cancellation table, per extract, recovered by a search that replays each journal account with backtracking over unsettled pairs.
- (focal) Withdrawal rule, from the family stated in legacy_notes.md: split own kind first; own-kind rows by largest metered charge, latest of equal charges; other-kind rows by smallest metered charge, earliest of equal charges.
- (focal) Standing rule, from the family stated in legacy_notes.md: the least fixed point of: an account passes when U, plus W if its sponsor is in the set, is at least floor x O.
- (stated, exercised on the hidden extracts) Control rows rated 0/0 whatever their cells; erratum numbers compared as integers; rescued accounts (recommendations.json).
- (drift) Counterfactual billing freeze (amendments.md): the first-issued amendment of a cell governs. Merge boundary exclusive (identity_rules.md).
- (trap) Registry over the FINAL export for listed accounts; equal stamps by the integer after the id letter; latency_us half-up (the one exact half in the shipped latency workload, l7271 at 554500 us, crosses no quantum boundary; the standing hidden extract carries its latency in microseconds, with 65 exact halves on rows whose half-up millisecond is an odd multiple of its latency_quantum 11, so truncation, half-to-even and half-down each change its result); errata named by booked account; loose cells; byte-order mark; decoy amendment by written account; reactivation at a row's stamp; the decoy files.

## Load-bearing work

Concepts (category Data Processing, billing domain): identity resolution with time-dependent merges and reactivation; authority between a system of record and a FINAL snapshot; errata net state with a counterfactual precedence and integer numbering; calibration of withheld tariff weights from an underdetermined system with unpriced kinds; joint recovery of weights and a cancellation table by constraint search over close-state evidence, finished by a raw-row journal re-rated through the whole withdrawal and standing pipeline; recovery of a withdrawal ranking and a standing fixpoint rule from stated families; per-region carry chains; checksum folding; single-pass optimisation against a re-walking baseline.

Input inventory (environment/data):

| file | format | lines | unique fact | joins |
|---|---|---|---|---|
| manifest.json | JSON | 25 | scenario names and sources | rules file |
| rules.json | JSON | 39 | offsets, penalties, modulus, quantum, floor, kinds, eight file keys | every file |
| events.csv | CSV | 1298 | visible workload | identity, errata |
| workload_peak.csv | CSV | 2289 | peak workload | identity, errata |
| workload_steady.csv | CSV | 1893 | steady workload | identity, errata |
| workload_burst.csv | CSV | 1691 | burst workload (byte-order mark) | identity, errata |
| workload_latency.csv | CSV | 1482 | latency workload in microseconds (byte-order mark) | identity, errata |
| account_registry.csv | CSV | 95 | governing home regions and sponsors (no sponsor cycle or chain of standing-relevant depth) | merges, export |
| registry_export.json | JSON | 425 | export-only accounts | registry |
| account_merges.csv | CSV | 11 | bookings over time | registry, errata |
| errata.jsonl | JSONL | 100 | amended cells, ids written ER-00089 style (five digits) | booked accounts |
| rate_card.csv | CSV | 40 | 8 calibration batches over all 8 kinds | rate_figures.json |
| rate_figures.json | JSON | 12 | batch metered charges | rate_card.csv |
| legacy_withdrawals.csv | CSV | 523 | 68 accounts, 522 shuffled lines of close states | rate card, standing journal |
| legacy_standing.csv | CSV | 317 | 43 accounts, 316 raw rows with sponsors and recorded standing | withdrawal journal, rules values |
| legacy_withdrawals_v2.csv | CSV | 523 | decoy: the withdrawal journal with about 8% of close states flipped (41 of 522 lines); named by no rules key | none |
| rate_figures_final.json | JSON | 12 | decoy: batch figures off by small amounts; named by no rules key | none |
| rules_corrected.json | JSON | 39 | decoy: premium_floor 2400, carry_modulus 1009; named by nothing | none |
| expected_totals.json | JSON | 37 | decoy: stale control totals, none equal to a graded value | none |
| calibration_README_2023.txt | text | 16 | decoy: fixed weights (none of cache/compute/egress/ingress/queue/search/storage equal to the true weight; stream 38 vs 39), own-kind-only voids, a live-row standing test | none |

Documents: schema.md, identity_rules.md, amendments.md, ledger_rules.md, scoring_rules.md, rate_card.md, legacy_notes.md, performance_contract.md. No document carries a worked example, an example report, a candidate list, a statement of uniqueness or a statement of which file settles which unknown.

Shipped configuration: weights {"cache": 10, "compute": 26, "egress": 3, "ingress": 34, "queue": 3, "search": 29, "storage": 24, "stream": 39}; the table allows 26 of the 56 ordered pairs.

Dependency chain: manifest -> rules -> rate card (+ absent kinds in the box) -> withdrawal journal (weights, table, ranking) -> standing journal re-rated (no carry, floor 2000) -> one configuration and the standing rule; registry + export -> governing records; merges -> booking; booking + errata (integer numbers) -> amended cells -> rejection -> processing order -> base values (control rows 0/0) -> carried values per region chain -> withdrawals -> live set -> standing -> final values -> totals, ranking, checksum -> reports.

## Verification

### Test channel

33 checks: 27 positive, 6 negative. Positive total 103; reward.toml normalises the test channel by 0.5 / 103.

- EASY, weight 1 (8 checks, 8 of 103 = 7.8%): json_reports_canonical_form, module_and_cli_contract, bottleneck_analysis_exact, perf_report_exact, command_line_output_form_exact (grades only the single-line json.dumps form and the key set of the printed object; no value is compared, so a wrong value is never charged twice), scenario_reports_exact (the five scenario files together), data_quality_report_exact, recommendations_report_exact.
- HARD, weight 5, hidden extracts (19 checks, 95 of 103 = 92.2%), all-or-nothing on the whole result object: identity, standing, wide_kinds, errata, boundary, weak11, weak12, wk10b, wk11a, wk11b, wk11d, wk11f, wk12d, wk12e, wk12f, wk12g, wk12i, wk12j, and timed_extract_exact_and_fast. standing, wide_kinds and boundary are run through the command line.

The test file embeds the shipped extract and 20 other extracts (the 19 graded above plus rerated, used only by a negative). Its reference settles each extract at grade time and raises unless exactly one configuration fits both journals. Partial-solver ceiling: every EASY check and no hidden extract scores 8 / 103 = 0.078.

Negatives (6, total 22): negative_hardcoded_sample_answers (-5), negative_opens_files_outside_extract (-5), negative_third_party_or_network_use (-3), negative_output_depends_on_location (-3), negative_shipped_settings_on_other_extract (-5), negative_nondeterministic_result (-1).

### Degeneracy of the shipped extract

Each reading below gives byte-identical shipped reports (all five scenario files, data_quality.json, recommendations.json, bottleneck_analysis.json) to the oracle, and changes the result object of the hidden extracts listed.

| wrong reading | same on shipped | differs on hidden extracts |
|---|---|---|
| D1 greatest fixed point for standing | yes (no sponsor cycle of waiver-only qualifiers) | 20 of 20 |
| D2 strict `>` instead of at-least | yes (no account exactly on the floor) | 20 of 20 |
| D3 two evaluations instead of the fixed point | yes (no sponsor chain of depth 2 or more that matters) | 20 of 20 |
| D4 erratum ids compared as text | yes (every id has five digits) | 17 of 20 |
| D5 control rows rated from their cells | yes (every control cell of the shipped graded workloads is 0; the journals' non-zero control cells reach no shipped report) | 20 of 20 |
| D6 own-kind-only cancellation (no cross-kind withdrawal) | yes (no void withdraws a row of another kind) | 20 of 20 |
| D7 own-first ranking with other-kind rows by largest charge, latest | yes (other-kind group never reached) | 20 of 20 |
| D8 own-first ranking with other-kind rows by smallest charge, latest | yes (other-kind group never reached) | 20 of 20 |
| D9 weights from the rate figures alone (no journal) | yes (8 batches fix all 8 weights) | 20 of 20 (figures leave free weights everywhere) |
| D10 first withdrawal-journal survivor, standing journal ignored | yes (one survivor on the shipped card) | 20 of 20 (3 to 5 survivors) |
| D11 plain product enumeration of the free weights | yes (no free weight; instant) | exceeds the 60 s per-call limit on the weak extracts |

Counts were computed with each extract's own settled configuration, comparing the whole result object.

### Recovered settings and rules: family and uniqueness

legacy_notes.md admits 666 withdrawal rankings (unsplit, or split own/other with either group first; each part ordered by at most one of charge, amount, units, kind weight, larger or smaller first, then position, earlier or later first) and 16 standing rules (count O or L; at-least or strict; total U, C, or U+W when the sponsor is in the set with the least or the greatest fixed point). An exhaustive proof (every ranking; for each, every in-box weight assignment and every table consistent with the withdrawal journal, depth-first with no cap reached; every open pair; every standing rule against the standing journal) finds exactly 1 joint fit on the shipped extract and on each of the 20 embedded extracts, always the stated ranking and least/O/at-least with the extract's own weights and table.

| extract | rankings with any withdrawal survivor | (survivor, rule) pairs checked | joint fits |
|---|---|---|---|
| shipped | 1 of 666 | 16 | 1 |
| boundary, errata, identity, rerated, standing, timed, weak11, weak12, wide_kinds, wk10b, wk11b, wk11d, wk11f, wk12d, wk12e, wk12f, wk12g, wk12i, wk12j | 1 of 666 each | 48 each | 1 each |
| wk11a | 1 of 666 | 80 | 1 |

Hidden extracts obey every documented constraint: at most 12 kinds and 15,000 workload rows, at most 2,000 lines in either journal, weights in 2 to 40, the oracle well under the per-call limit.

### Judge channel

20 criteria, positive total 41: eight what-if answers at weight 5 and R9 (no leftover debug prints and no bare except clauses in optimize.py) at weight 1; eleven negatives, total 33. Each what-if describes a small edited extract showing a situation the shipped extract never shows. Answers computed by solve.py on the edited extract.

| criterion | question | oracle | wrong reading |
|---|---|---|---|
| R1 | rate card cut to RB01-RB03 (weakened evidence) and M4415 recorded standard: visible checksum | 46218576 | shipped configuration kept: 3050494516 |
| R2 | rate card RB01 only, figure 15716 (weakened evidence): visible checksum | 1605984208 | shipped configuration kept: 3050494516 |
| R3 | largest floor holding C1788 in burst (a floor search) | 4344 | - |
| R4 | rate card RB01 only, figure 15716: latency total_score | 3674669 | shipped configuration kept: 3705054 |
| R5 | new erratum ER-7 sets units of C1648 at ts 736 to 2, contesting ER-00183 (integer versus text order) | 1220833675 | text order: 3050494516 |
| R6 | void e548 given kind stream (a cross-kind withdrawal) : visible total_score | 3226166 | own-kind-only: 3254940 |
| R7 | C1320 names C1694 as sponsor (a sponsor 2-cycle): visible standing flips | 0 | greatest fixed point: 2 |
| R8 | carry_modulus 1034: latency total_score | 3741165 | - |

On R2 and R4 the one-batch card leaves seven free weights; a program that enumerates them before pruning by the withdrawal journal ran for over 20 minutes on the same edit.

Negatives on how the program settles the weights and how the response reports its checks (a correct solver triggers none):

| criterion | weight | fires when |
|---|---|---|
| R17 | -5 | the final optimize.py builds complete assignments of the free weights over 2..40 before replaying the withdrawal journal, so its cost grows as 39 to the number of free weights, against the per-call time the documents allow |
| R18 | -3 | a changed-card what-if (questions 1, 2, 4) is answered with weights chosen by a helper script other than optimize.py that hard-codes the shipped weights |
| R19 | -3 | the response states a size, line count or row count for one of its own checks (not a report figure) that differs from what that check printed |
| R20 | -3 | the response presents the module as recovering other extracts' configuration, but the trajectory contains no run at all of the module's own weight recovery on a card that leaves a weight undetermined |

Each negative is a separate decision, so no single choice is charged twice: report figures are R10's, module-level hard-coding is the tests' shipped-settings negative, R18 covers only a separate helper, and a weak-card check that was run but failed is R15's while R20 covers only a weak-card check never run.

### Shipped figures and confirmation

The only figures shipped are the batch charges; the withdrawal journal confirms close states and the standing journal recorded standings. No carry, region, latency, identity, errata, ranking or checksum figure is shipped. No graded value of the tests and none of the judged values appear in the documents or the instruction.

### Interactions planted in the graded extracts

| id | rules | outcome | graded extracts |
|---|---|---|---|
| I1 | merge boundary x errata by booked account | amendment named at the target on the merge stamp matches nothing | identity, errata |
| I2 | reactivation x region chains | rows after reactivation join another region's chain | identity, timed, boundary |
| I3 | sponsor through merges x standing | waivers follow the merge target's standing | identity, standing |
| I4 | billing freeze x revert | the second-issued amendment governs | standing, wide_kinds, errata |
| I5 | withdrawal rule x amendment-unpriced row | the void chooses among the rows still processed | timed, errata |
| I6 | orphan void x later revive | the revive restores the earlier withdrawal | wide_kinds |
| I7 | sponsor cycle with a qualifier | standing propagates round the cycle | standing, timed |
| I9 | export-only sponsor x standing | an export-governed account waives a listed one | standing |
| I10 | standing condition exactly on the floor | equality holds standing | standing |
| I11 | unregistered account merged into a registered one | later rows are processed | identity, boundary |
| I12 | drained sponsor x ordinary-row count | a sponsor with every row withdrawn keeps its count and holds no standing | wide_kinds |
| I14 | equal metered charges among allowed rows x withdrawal tie-break | the earliest of the tied rows is withdrawn | every graded extract |
| I15 | cross-kind cancellation x revive of another kind x kind totals | a restored row of another kind returns to its kind total | wide_kinds |
| I16 | mutual sponsors that qualify only with waivers x least set | neither holds standing | every graded extract |
| I17 | weight family with absent kinds x two journals | the withdrawal journal leaves 3 to 5 complete candidates (window w-1, w, w+1 on one absent kind); the raw-row standing journal keeps one | every graded extract |
| I18 | amendment of amount x metered charge x withdrawal rule | the amended charge decides which row is withdrawn | errata |
| I19 | loose flag cell x control rows | a ` VOID` or `Revive` cell is a control row, takes no carry and withdraws or restores | every graded extract with loose cells |
| I20 | loose account cell x booking x rebooked count x amendment matching | the normalised account is booked, compared with its booking and named by errata | every graded extract with loose cells, errata |
| I21 | byte-order mark x id column x ordering | the first column is still `id`, so ordering and checksums use the row numbers | timed, wide_kinds, errata |
| I22 | decoy amendment x merge x booked-account naming | the amendment naming the written account matches nothing, the one naming the booked account applies | every graded extract |
| I23 | reactivation at a row's stamp x strict boundary x amendment matching | the row at the stamp stays booked to the merge target; the next stamp is the account's own and its amendment applies | every graded extract |
| I24 | sponsor 3-cycle of waiver-only qualifiers x least set | none of the three holds standing | every graded extract (planted cycle structure) |
| I25 | sponsor chain of five x fixpoint depth | standing propagates four hops; two- and three-pass readings stop short | every graded extract (planted chain structure) |
| I26 | control row with non-zero cells x carry chain x checksum | the control row is rated 0/0, keeps base value offset minus latency and takes no carry | every graded extract |
| I27 | mixed-width erratum ids x billing freeze | the lowest integer number governs over a text-earlier id | every graded extract; the result object changes under text order on 17 of the 20 (not errata, weak11, wk11f) |
| I28 | account exactly on the floor x comparison | equality holds standing; a strict comparison drops it | every graded extract |
| I29 | account between floor x live rows and floor x ordinary rows | the ordinary-row count denies standing | every graded extract |

Each outcome follows from the stated rules and the recovered ones; no rule contradicts another on it.

Grading hardening: submitted code runs only as a subprocess under setpriv as nobody, with an audit hook installed before it loads; the negatives scan the audit records of every memoized module run; timing is child CPU from getrusage against the reference's own re-walking engine; every extract is unpacked at fresh paths and moved for the location check; hard-coding is detected by AST literal count and by the rerated extract.

## Traps

- Isolation-breaker: the carried value of every chain row depends on the previous chain row of its region, so no row, account or extract can be rated in isolation.
- Stale authoritative note: calibration_README_2023.txt states fixed weights, own-kind-only voids and a live-row standing test; the rate figures refute the weights and the journals refute the rules.
- Near-duplicate files: legacy_withdrawals_v2.csv, rate_figures_final.json and rules_corrected.json sit next to the real files; rules.json and manifest.json name only the real ones.
- Stale summary block: expected_totals.json lists wrong totals, checksums, counts and premium counts.
- Degenerate shipped extract: the eleven readings D1 to D11 pass every shipped check and fail the hidden extracts.
- Scale: the weak-evidence extracts leave seven to eleven weights free, so product enumeration of the weight box exceeds the per-call limit.

## Known hard edges

- The decoy files are not mentioned by any document; the README presents itself as approved. Every graded value is settled by the files the rules file names.
- The shipped extract cannot reveal the readings D1 to D11; the documents state every rule that separates them.
- The partial-solver ceiling is low by design.

## Root cause

Every rule needed is stated, or stated as a family whose member the evidence fixes, but nothing shipped confirms the distinctions that matter: the shipped extract is degenerate, and the hidden extracts, which carry 92% of the weight, have weak rate cards, several withdrawal-journal survivors, cycles, chains, floor equalities, contested erratum ids, non-zero control cells and cross-kind cancellations. Twenty extracts with their own configuration defeat hand deduction plus hard-coding.

## Solution shape

solution/solve.py (623 lines) is the delivered module, installed unchanged as /app/out/optimize.py. On every call it reduces the rate card to integer pivots, then runs a constraint search over the free weights: each keeps a domain of allowed values, the search branches on the open weight with the fewest values left, narrows the other domains after every choice, and replays each withdrawal-journal account as soon as its kinds' weights are known, extending the table jointly, with no cap on the candidates it collects. It re-rates the standing journal for every complete survivor and requires exactly one fit. It rates control rows 0/0, compares erratum numbers as integers and carries no clock and no randomness. solve.sh installs the module, writes every report and times it against a re-walking implementation.

## Ordered plan

1. Read the documents; build the identity directory (registry over export, merges with exclusive boundary).
2. Net-state errata with the billing freeze, by booked account, integer erratum numbers.
3. Reject unregistered and unpriced rows; sort by stamp then integer id; control rows 0/0.
4. Reduce the rate card; leave absent kinds free in the 2 to 40 box.
5. Search weights, table and ranking jointly against the withdrawal journal.
6. Re-rate the standing journal (no carry, floor 2000) for every survivor and standing rule; keep the one fit.
7. Base values; carried values on per-region chains of ordinary rows.
8. Withdrawals by the ranking and table; revives restore the latest withdrawal.
9. Standing; waivers; final values.
10. Totals, ranking, checksum, reports; perf report from an external timing script.
11. Answer the what-ifs on edited copies, re-settling the configuration for Q1, Q2 and Q4 and searching the floor for Q3.

## Pitfalls

Trusting the shipped reports as proof of the hidden rules (D1 to D11); taking the first withdrawal survivor; skipping the standing journal; rating the journal period with carry; ordering journal lines by text id or file order; rating control rows from their cells; text comparison of erratum ids; greatest or strict standing; one global carry chain; inclusive merge boundary; last-write-wins errata; trusting the FINAL export; hard-coding the shipped configuration; enumerating free weights by product.

## Provenance

```yaml
uuid: 18b5d99f-d4de-5e08-bb90-aeae31d33b3e
instance_id: 18b5d99f-d4de-5e08-bb90-aeae31d33b3e
task_name: terminal-bench/18b5d99f-d4de-5e08-bb90-aeae31d33b3e
fix_patch_sha256: 85d03ee94ad6073336176898b34aa59c16d2bd84a1930c930a3196b3e0388c4e
solve_py_sha256: 73e1394ec4896e5dcb7ed96b37a56731b54c60e2cc9c3dc698d66660ae14accd
language: python
```
