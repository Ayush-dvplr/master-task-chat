# TRUTH.md - 92dd0b24-4f27-5ec2-9084-7bcc527d2e05

## Defect

The circuit ships an open slate, `GC31-S6`, and 57 files of evidence about it.
Nothing in the corpus says which readings an engineer habitually gets wrong, and
nothing counts the pockets. The work is to adjudicate every submission the slate
names, carry the season strike history into it, drive the arbiter so the service
journal records the outcome, and publish seven files whose every value is exact.

Defect items, each naming the check it defeats:

- (focal) The pre cutover ordering of `point_charge` across the three
  restriction sources is withheld by `slate_contract.md` section 8.2 and settled
  only by the two adjudication observation logs. The stated post cutover order is
  rider, global, addendum and the stated pre cutover order for `allowed_copies`
  is rider, addendum, global, so every available analogy points away from the
  true reading, addendum then global then rider. A wrong ordering moves point
  totals on hundreds of entries and flips verdicts through the ladder. Defeats
  `report_points_totals`, `report_governing_sources`, `report_verdicts`,
  `summary_distributions`, `summary_totals` and all three scenario checks.
- (focal) The stage at which `charge_ceiling_cpt` binds is withheld by section
  10 and settled by the same observations. The true reading clamps a single copy
  before the counted copies multiply it. Clamping the card contribution or the
  deck total are both plausible and both silent. Defeats
  `report_points_totals`, `summary_totals`, `scenario_mode_payload` and, through
  the ladder, `report_verdicts`.
- (focal) The strike carry is the running spine. It accumulates over the whole
  season in effective order with recorded instant and submission id as
  tiebreaks, absorbs an absorbed carry at a merge, decays by one at a stage close
  for a player who submitted during the stage and drew no weight, and caps at
  six. One early mistake rewrites `carry_before`, `carry_after`, `tier` and every
  `tier_bar` verdict that follows. Defeats `report_carry_spine`,
  `report_verdicts` and `summary_distributions`.
- (drift) The entry headers carry the column title `venue` twice. The fourth
  field is the venue of play that governs offsets, windows, regions and standing
  entries; the sixth is the venue of record. A mapping reader silently takes the
  second one. Defeats `report_player_and_format` and fires
  `negative_record_venue_reported`.
- (drift) Intake receipt instants are lane timestamps in each host's own clock
  and must be corrected by `host_clock_offsets.csv` for the calendar date of the
  lane timestamp, with the earliest admitted receipt governing and an indented
  `recorded_override=` continuation replacing the computed instant. Defeats
  `report_instants` and fires `negative_latest_receipt_instants`.
- (trap) The arbiter advertises caps at `GET /advice` that disagree with
  `format_rules.ini` and `slate_window.ini` on all four settings. Fires
  `negative_advisory_budget_applied`.
- (trap) Set codes need normalising on both sides of the join, so `s7*` and
  `S07` are the same set as `S7`, and reprint links consolidate two canonical
  keys into the one with the earlier first release. Defeats
  `report_points_totals` and `summary_totals`.
- (trap) `register` is the only operation that creates an entry, `bar` and
  `reinstate` are console only, relic writes answer 202 and land on a poll, and
  the first conditional write to a contested entry answers 409. Defeats
  `final_state_entry_map`, `journal_digest_identity` and
  `transcript_operations`.

Out of bounds: editing any file under the data mount (judged criterion
`shipped-feed-edited`, since the grading container never receives the data
mount); publishing invented submission ids
(`negative_hardcoded_sample_answers`); leaving spare files at the output paths
(judged criterion `extra-output-file-left`, for the same reason); taking caps from the advice endpoint
(`negative_advisory_budget_applied`); reading the last uncorrected receipt
(`negative_latest_receipt_instants`); reporting the venue of record
(`negative_record_venue_reported`); writing the state file from local
bookkeeping (`negative_state_not_read_back`); quoting verifier or log paths in a
published file (`negative_verifier_paths_quoted`); publishing closed stage
submissions (`negative_closed_stage_entries`); and emitting numeric fields as
anything other than integers (`negative_numbers_not_integers`), departing from
the fixed entry key set (`negative_entry_keys_wrong`), trimming the service
snapshot (`negative_state_snapshot_trimmed`) and disagreeing with the report on
the slate id (`negative_slate_id_mismatched`).

## Load-bearing work

| trap | firing records | graded value that changes |
| --- | --- | --- |
| pre cutover charge ordering | 1346 settled observations pin it; wrong orders contradict 94 to 615 of them | `points_total` on 64 to 272 of 1482 entries, 7 to 18 verdicts, `points_total_sum`, every scenario |
| ceiling binds one copy | 719 prior stage rows discriminate | `points_total` on 108 to 414 entries, 42 to 107 verdicts |
| carry spine | 85 cap hits, 38 `tier_bar` bars, relief at six stage closes | `carry_before`, `carry_after`, `tier` on every entry of an affected player |
| observation authority | 82 submissions carry disagreeing observations | which reading survives at all |
| duplicated venue title | 2041 header rows per file, play and record venues differ on most | `venue`, offsets, windows, region, addendum choice |
| host clock offsets | 8150 submissions with 1 to 3 receipts each | `recorded_at`, admission, processing order |
| recorded override continuations | every 73rd submission | `recorded_at` |
| as of recorded admission | 36 handle hops, 720 renames with every ninth late, post cutoff addendum and rider rows | identity, card match, restriction values |
| supersedes chains and cycles | 9020 revisions, retractions at one in 23, cycles at one in 149 | `chain_cycle` on 10 entries, `allowed_copies` elsewhere |
| mirror charge chains and rings | one in 97 revisions, rings at one in 131 | `charge_cycle` on 10 entries, charges downstream |
| rider authority rank | 901 of 2104 rider rows turned away | `governing_source` on 301 rider entries, charges |
| decimal comma addendum | 2204 rows per region | charges on addendum governed keys |
| fixed width release board | 3000 lines, three implied decimals | fallback charges, `base` source on 519 entries |
| reprint consolidation | 564 keys absorbed in the open stage | `copies_counted`, breach counts, charges |
| set code normalisation | three variant forms at strides 37, 41 and 53 | card match, `unknown_printing` on 21 entries |
| amendment version order | 1450 accepted amendments outranked | governing list, `amended` on 110 entries |
| null, absent and empty line lists | one in 11, one in 17, one in 13 amendments | governing list |
| duplicate event ids | 40 identical, 26 conflicting | `rejected_events` 52, slate membership |
| inclusive standing until date | one in six live rows ends on an occurrence | `materialized_entry_count` 165 |
| exception suppression | 3 occurrences suppressed of 168 admitted | `materialized_entry_count` |
| no prior list | 9 reserved entrants hold standing rows | `no_prior_list` on 29 entries |
| half open windows published as of the cutoff | 240 venue stage pairs, one in eight governed by R8 | stage membership, 48 stageless submissions |
| 04:00 competition day start | boundary rows at prime strides | standing suppression, stage membership |
| offset fold and gap | 14 shifting venues | effective instants |
| merge survivor by earlier join | 90 merges | holder, carry absorption, 171 redirected submissions across the season |
| splits transfer no carry | 60 splits | carry |
| nearest first inherits chains | eight per stage overrides | budgets, caps, ceilings |
| exemptions | 2159 rows | allowances, ceiling relief |
| empty listing pages | 4 of 22 pages | `pages_walked`, `empty_pages` |
| console only operations | 77 console operations | `channel`, the state channel map |
| deferred relic writes | 576 parked operations | journal order, digest |
| contested etag revision | 39 entries | `conflicts_met`, `refusals`, digest |
| listing lag | three requests | pre seeded overlap |
| scope equals governing source | every write | the state scope map |
| request budget | 400 requests | renewals during the drive |
| advisory caps | four settings disagree | budgets and ceilings |
| legacy runbook habits | fourteen recorded habits | every graded family |
| late errata | two recorded after the cutoff | day start, rounding |
| retracted erratum | one retracted before effect | window reading |

## Verification

Test channel: 31 checks. Positive total 72 from eight at weight 5, ten at
weight 3 and two at weight 1. Negative magnitudes total 23 across eleven
checks: `negative_hardcoded_sample_answers` 3,
`negative_advisory_budget_applied` 3, `negative_latest_receipt_instants` 3,
`negative_record_venue_reported` 3, `negative_state_not_read_back` 3,
`negative_verifier_paths_quoted` 1, `negative_closed_stage_entries` 3,
`negative_numbers_not_integers` 1, `negative_entry_keys_wrong` 1,
`negative_state_snapshot_trimmed` 1, `negative_slate_id_mismatched` 1.

Grading compares the published files against the adjudication recorded inside
`test_output.py`, which the verifier carries beside its own copy of the corpus.
The two are sealed together: where the corpus copy and the recorded adjudication
disagree by one byte the verifier declines the comparison and every positive
check reads false, so an edited corpus can never be graded against a stale
answer. The verifier holds no second implementation of the adjudication rules,
so no reading of the contract is graded twice from the same code. The recorded
answer is the one `solve.py` publishes while driving the live service, and every
figure in this file was checked against it.

Judge channel: 34 criteria. Positive total 84 from eleven closing counts at
weight 5, nine criteria at weight 3 and two light criteria at weight 1. Twelve
negatives total 30. The closing counts carry 69.0 percent of the judge total;
the light criteria carry 2.4 percent.

The reference run scores 72 of 72 on the test channel and an empty workspace
scores 0 of 72. Both figures are tests only; the judge channel is scored by
model.

| requirement | artifact | checks | criteria |
| --- | --- | --- | --- |
| slate roster and order | report.json | report_entry_roster w5 | none |
| carry and tier per entry | report.json | report_carry_spine w5 | none |
| point totals in centipoints | report.json | report_points_totals w5 | R13 and R14 |
| governing source per entry | report.json | report_governing_sources w5 | R13 |
| verdict and reason per entry | report.json | report_verdicts w5 | none |
| service record per entry, state map and report channel | final_state.json plus report.json | final_state_entry_map w5 | R19 |
| journal sequence and digest | final_state.json plus transcript_summary.json | journal_digest_identity w5 | R20 |
| single format scenario | scenario_mode.json | scenario_mode_payload w5 | none |
| slate header | report.json | report_header_fields w3 | none |
| entrant, format and venue | report.json | report_player_and_format w3 | R18 |
| effective and recorded instants | report.json | report_instants w3 | R16 and R17 |
| copy breach count per entry | report.json | report_copy_breaches w3 | none |
| verdict and tier distributions | summary.json | summary_distributions w3 | none |
| slate scalar totals | summary.json | summary_totals w3 | none |
| listing walk tallies | transcript_summary.json | transcript_paging w3 | R25 |
| operation and refusal tallies | transcript_summary.json | transcript_operations w3 | R20 |
| earlier cutoff scenario | scenario_alpha.json | scenario_alpha_payload w3 | none |
| withdrawn source scenario | scenario_beta.json | scenario_beta_payload w3 | none |
| seven files published | all seven | artifacts_readable w1 | R33 |
| closed vocabularies | report.json | report_vocabulary w1 | none |
| corpus left as shipped | none | none | R23 |
| derived rather than invented ids | report.json | negative_hardcoded_sample_answers | none |
| published caps govern | summary.json | negative_advisory_budget_applied | R31 |
| earliest corrected receipt | report.json | negative_latest_receipt_instants | R17 |
| venue of play reported | report.json | negative_record_venue_reported | R18 |
| state read back from the service | final_state.json | negative_state_not_read_back | R20 |
| open slate only | report.json | negative_closed_stage_entries | R11 |
| integer numeric fields | report.json | negative_numbers_not_integers | none |
| fixed entry key set | report.json | negative_entry_keys_wrong | none |
| whole service snapshot | final_state.json | negative_state_snapshot_trimmed | none |
| one slate id across the files | four of the seven | negative_slate_id_mismatched | none |
| grading paths left alone | all seven | negative_verifier_paths_quoted | R28 |
| no spare output files | the trajectory | none | R34 |
| eleven labelled closing counts | the closing message | none | R1 to R12 |
| two conventions settled from the observations | the closing message | none | R13 and R14 |

Overlap analysis. The test channel reads published bytes only and the judge
channel reads the trajectory and the closing message only, so no criterion and
no check pay for one observable. Within the test channel each weight 3 or
weight 5 check compares one field family and no field appears in two positive
checks: roster, carry triple, points, source, verdict pair, state map, digest
identity, mode scenario, header, entrant triple, instant pair, copy breach
count, four distributions, eight scalars, three paging counts, six drive
tallies, alpha payload, beta payload. Within the judge channel the twelve
closing counts name twelve disjoint quantities, the eight derivation criteria
name eight disjoint derivations, and each negative names one action. No action
fires more than one weight 5 penalty and the summed penalty for any single
action stays at or below five: editing the corpus fires the judged criterion at
5 and nothing else, since the grading container never receives the data mount;
quoting a grading path fires the test negative at 1 and the judge negative at
3; taking caps from the advice endpoint fires the test negative at 3 and the
judge negative at 1.

Rule fixtures. Three further tie breaks each carry a fixture that costs a solver that reads the rule the other way: the merge of PL0521 into PL0501 has equal joined_at values, so the smaller player id survives, and a solver that keeps the larger id scores 66 of 72; CK0001 and CK1101 share an earliest release date, so the smaller canonical key survives, and a solver that keeps the larger key scores 40 of 72; and SB000008 appears in both the entry headers and the season legacy feed with instants that would place it inside the open stage window, so a solver that fails to prefer the header instants publishes a slate of 1483 entries and scores 5 of 72. Two admitted head revisions of one format and key also share an effective instant, so the later recorded instant decides between them (GR000001 against GR009021 on CK0347), but no graded value turns on that choice: a solver that reverses the recorded instant step still scores 72 of 72. No pair of season submissions shares both an effective and a recorded instant, so the submission id that closes the entry order never decides a position, and no two head revisions share both instants, so the revision id that closes section eight's tie break never decides one either. Every adjacent pair of the verdict ladder in section fifteen is constructed by at least one
graded submission, so a solver that reorders the ladder publishes different bytes: charge_cycle over chain_cycle
on SB007693, chain_cycle over unknown_printing on SB007730, unknown_printing over tier_bar on SB007060,
tier_bar over card_barred on four entries, card_barred over copy_breach on 184, copy_breach over points_over
on 105 and points_over over amended on 107. Section seven's lowest printing id rule is constructed by the
printing registry row PR03001, which repeats the normalised set code and printed name of PR00001 under a
different canonical key, so a solver that keeps the highest matching id resolves that line to the wrong key.

Three more rules the contract states are constructed by this corpus as well. SB006974 and SB006975
share one effective instant at V06, so the recorded instant decides which of them comes first and it
places the later submission id ahead of the earlier one; a solver that settles that tie on the
submission id alone publishes a different roster order and scores 28 of 72. The offset shift V04 takes
at 2031-06-08T18:00:00Z carries the venue an hour forward, so the local entry time SB006926 holds never
occurs and section three resolves it to the instant the shift begins; a solver that converts it with the
base offset instead reports an effective instant fifty one minutes late and scores 28 of 72. The
singleton copies exemption recorded for CK0128 in the open stage releases that key from the copies cap
for SB006987, so its counted copies sit inside its own allowance; a solver that lets the cap bind anyway
reports one copy breach too many and scores 66 of 72.

## Root cause

The corpus is internally consistent and the contract is complete except at two
points it openly delegates to the observations. Every other wrong answer comes
from a habitual reading that the contract states plainly in a place the reader
skipped: the positional field order of the entry headers, the direction of the
host clock correction, the earliest rather than latest receipt, the admitted
rather than newest revision, the survivor rather than the named key, the
inclusive rather than exclusive until date, the caps in the published files
rather than the caps the service volunteers. The legacy runbook collects
fourteen of those habits and says in its own header that it yields to the
contract, so the corpus signposts the wrong path as wrong.

**Red lines.** No answer key, no worked artifact, no checksum of a correct file
and no count of defects appears anywhere the agent can read. The two withheld
readings are decided by 1346 settled observations whose single surviving
candidate reproduces all of them; each wrong candidate is contradicted by 94 or
more. No rule is hidden, no data is corrupt, nothing requires decoding, and
every graded fact follows from the instruction plus the shipped corpus.

## Solution shape

`solve.py` loads the corpus once, indexes every feed, resolves identity, cards,
restrictions, units, dependencies, windows, receipts, events, amendments and
standing commitments, settles the two withheld readings by replaying the
closed stages under all twelve candidate pairs against the rank resolved
observations, walks the season once to carry strikes, applies the
verdict ladder, scripts the operation sequence, launches the arbiter on
loopback, drives it over both channels with idempotency keys, etag re reads and
deferred completion polls, reads the state back and publishes the seven files.
The three scenarios re run the whole season under the brief's three bases.

## Ordered plan

1. Read `slate_contract.md`, `api_contract.md` and `source_index.md`, then read
   `rules_committee_notes.md` and admit only errata recorded at or before the
   cutoff.
2. Load `slate_window.ini` and `format_rules.ini`, resolving the nearest first
   `inherits` chains, to advance every budget, cap and ceiling.
3. Build the venue clock from `venue_clocks.ini` and `venue_offset_shifts.csv`
   to turn header wall time into instants.
4. Read the governing window for each venue and stage from
   `stage_calendar.csv` as of the cutoff.
5. Correct each receipt in `intake_journal.log` and `intake_journal.log.1` with
   `host_clock_offsets.csv` to fix every recorded instant.
6. Assemble submissions from `entry_header_01..04.csv` and the `GC31` rows of
   `legacy_entries.tsv`, taking the venue of play from the fourth field.
7. Resolve entrants through `handle_changes.csv`, `identity_events.csv` and
   `player_registry.csv` to fix the holder of every submission.
8. Index printings from `printing_registry.csv`, `card_renames.csv` and
   `reprint_links.tsv` to match every deck line in `deck_lines_01..06.csv`.
9. Resolve restrictions from `global_restrictions_01..04.jsonl`, the three
   addendum files and `event_rider.tsv`, gated by `authority_roster.csv`, to fix
   allowances and charges.
10. Fall back to `printing_release_board.txt` for keys that no source charges.
11. Parse `judge_log_a.log` and `judge_log_b.log`, resolve each disagreement
    by the judge's rank at the observation timestamp in `authority_roster.csv`
    (equal ranks go to the later timestamp), then replay the closed stages under
    the six pre cutover charge orders and both ceiling stages and keep the one
    pair that no settled observation contradicts.
12. Apply `format_exemptions.csv` to lift allowances and ceilings.
13. Apply `amendments_01/02.jsonl` and `entry_events_01/02.jsonl` to fix the
    governing list and slate membership.
14. Materialise `standing_entries.csv` against `entry_exceptions.csv` inside the
    open window.
15. Walk the season to carry strikes, then apply the verdict ladder, producing
    `report.json` and `summary.json`.
16. Script the operations, consult `reinstatement_grants.csv` and
    `contested_entries.csv`, and drive the arbiter from `registry_seed.json`,
    `service_token.json` and `channel_policy.ini`, producing
    `transcript_summary.json` and `final_state.json`.
17. Re run the season under `scenario_brief.ini` to produce the three scenario
    files.

Reference closing message:

> Across the whole season 35 submissions carry no admitted intake receipt
> (`intake_journal.log` with `intake_journal.log.1`, read against the published
> legality cutoff). 171 submissions are held by an entrant other than the one
> the handle assignment alone would name (`handle_changes.csv` with
> `identity_events.csv`). 140 deck lines name a printing that no admitted
> registry row matches (`deck_lines_01..06.csv` and `amendments_01..02.jsonl`
> against `printing_registry.csv` with `card_renames.csv`). 564 canonical keys,
> counted separately in each of the three formats the slate uses, lose their
> identity to an admitted reprint link as at the published close of the open
> stage (`reprint_links.tsv` with `printing_registry.csv`). 51 reprint links are
> withdrawn by the token their recorded instant column carries in place of a
> date (`reprint_links.tsv`). 2665 restriction revisions are retracted among
> those that would otherwise be admitted (`global_restrictions_01..04.jsonl`).
> 901 of the 2104 event rider rows are turned away because the judge
> authorising them held a rank below three when the row was recorded
> (`event_rider.tsv` against `authority_roster.csv`). 82 of the 1346 observed
> submissions carry an observation that disagrees with another observation of
> the same submission (`judge_log_a.log` with `judge_log_b.log`). The open
> stage window admits 168 standing occurrences and an exception suppresses 3 of
> them (`standing_entries.csv` with `entry_exceptions.csv` and
> `stage_calendar.csv`). 1450 accepted amendments are outranked by a higher
> accepted version of the same submission (`amendments_01..02.jsonl`). 48
> submissions fall in no governing stage window (`stage_calendar.csv` with
> `venue_clocks.ini`). Two conventions came from the observations, each
> disagreement settled by the judge of higher rank at the observation's
> timestamp in `authority_roster.csv`, equal ranks going to the later
> timestamp. Before the cutover the point charge follows the addendum, then the
> global feed, then the rider: replaying the closed stages under all six
> orderings, it is the only one that contradicts none of the 1346 settled
> adjudications, and the other five contradict between 94 and 615. The format
> charge ceiling binds a single copy before the counted copies multiply it,
> since clamping the whole card contribution instead contradicts 183 of them.

## Pitfalls

| rank | failure | share of the test total |
| --- | --- | --- |
| 1 | pre cutover charge ordering taken from the post cutover sentence | 53 of 72 |
| 2 | amendment chosen by recorded order rather than version | 53 of 72 |
| 3 | equal effective instants separated by submission id rather than by recorded instant | 44 of 72 |
| 4 | a local entry time inside an offset gap converted with the base offset | 44 of 72 |
| 5 | charge ceiling clamped on the card contribution or the deck total | 31 of 72 |
| 6 | carry reset at a stage opening or never absorbed at a merge | 28 of 72 |
| 7 | reprint survivor ignored so copies counted per key | 21 of 72 |
| 8 | venue read from the sixth header field | 14 of 72 |
| 9 | bar sent over the api so the entry stays unbarred | 13 of 72 |
| 10 | receipt instants left uncorrected or taken from the last receipt | 11 of 72 |
| 11 | state file written from local bookkeeping | 10 of 72 |
| 12 | listing walk stopped at the first empty page | 8 of 72 |
| 13 | singleton copies exemption ignored so the copies cap binds anyway | 6 of 72 |

The top three together carry more than a third of the test total.

## Provenance

```yaml
uuid: 92dd0b24-4f27-5ec2-9084-7bcc527d2e05
instance_id: 92dd0b24-4f27-5ec2-9084-7bcc527d2e05
task_name: terminal-bench/92dd0b24-4f27-5ec2-9084-7bcc527d2e05
fix_patch_sha256: 5dd6bb914a8e7666d90c23f68a7aa07f1642a92a96b2c0e62bfee43cdca35a36
solve_py_sha256: 14b309eb55f8bf81dfca3faec678811b554b8d46ee7d85c304e88532d6aa9bb9
language: python
```
