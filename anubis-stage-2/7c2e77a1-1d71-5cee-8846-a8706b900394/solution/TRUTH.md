# TRUTH.md - 7c2e77a1-1d71-5cee-8846-a8706b900394

## Defect

The post house ships a legacy conform engine and a contract that disagree. The
engine at `/app/data/reference_conform.py` predates `conform_contract.md`, and
only its `STAGES` list and its `profile()` visit counter carry house sign off.
Every frame number it produces departs from the contract in places the material
never lists. A senior engineer must rebuild the engine from the contract and the
corpus, not from the legacy code.

1. (focal) The cadence phase is a running quantity per timeline, so record span
   is `floor((p+n)*num/den) - floor(p*num/den)` and the phase leaves as
   `(p+n) mod den`. The legacy engine restarts the phase at every event and
   takes a ceiling. Defeats `visible_spine_totals`, `latency_phase_totals`,
   `cursor_identity_all_scenarios`, `heldout_extract_first` and
   `heldout_extract_second`.
2. (focal) Recorded time comes from the ingest logs when a log names the event.
   The rotated file is read before the live file, the last record naming the
   event wins, and the host reading converts by subtracting `offset_minutes`
   from the window containing that reading. The legacy engine never opens a log.
   Defeats `visible_spine_totals`, `perf_report_counts` and
   `heldout_extract_first`.
3. (focal) Exactly one correction applies per event, the highest revision above
   the event row revision. A lower revision contributes nothing whatever its op,
   so a `delete` under an `amend` is stale. Defeats `quality_rejected_map` and
   `quality_audited_map`.
4. (focal) The tape index supplies in timecode, out timecode and speed while the
   event effective instant stands before the scenario cutover, with
   `tape_index_v2.txt` over `tape_index_v1.txt`, and the tape states speed in
   parts per billion against the event row in parts per million. Defeats
   `layered_delivery_totals` and `heldout_extract_second`.
5. (focal) Field ten of the event row is the speed the contract reads. Field
   nineteen shares the title and holds an illustrative percentage with a comma
   decimal mark. A title keyed reader keeps the last column and is silently
   wrong everywhere. Defeats every weight five check and fires
   `negative_percent_speed_column`.
6. (drift) The nesting file is the only statement of the timeline a nest event
   requires. Timelines resolve in dependency order, and a closed ring plus every
   timeline depending on one carries zero record frames and `NEST_CYCLE` on
   every event. Defeats `peak_nest_cycle_poisoning`.
7. (trap) `exclude_classes` distinguishes an absent key and a null value, which
   both defer to the defaults list, from an empty list, which excludes nothing.
   The steady scenario therefore records no `CLASS_EXCLUDED` at all. Defeats
   `quality_audited_map` and `recommendations_global`.
8. (trap) The cadence map is keyed by site code as well as the family pair, and
   nine sites carry doubled numerator and denominator, the same ratio with
   different phase arithmetic. Joining on the family pair alone passes a spot
   check and shifts every later event of the timeline. Defeats
   `visible_spine_totals` and `bottleneck_hot_and_carry`.

### Trap record incidence

| Trap | Firing records | Graded value that changes |
| --- | --- | --- |
| Phase carried, no restart | 11739 applied events across five scenarios | `record_out_frames`, `exit_phase`, `record_frames`, `exit_phase_sum` |
| Ingest log recorded time | 2500 events, 195 pushed past a cutoff | `totals.events`, `admitted_events` |
| Cutoff inclusive at the instant | 90 events exactly on a cutoff | `totals.events` |
| Highest revision only | 1170 stale deletes superseded | `reason_code`, `rejected` map |
| Identical correction is one record | 870 repeated records | `reason_code`, `TIE_UNRESOLVED` count |
| Revision contest ordering | 494 settled on tier, 286 on time | `reason_code`, `source_frames` |
| Undecided contest | 95 events at `TIE_UNRESOLVED` | `rejected` map |
| Tape measurements before cutover | 5933 events, 3869 from the later index | `source_frames`, `record_frames` |
| Parts per billion against parts per million | every tape sourced event | `source_frames` |
| Field ten against field nineteen | every event | every frame figure |
| Parenthesised negative offset | roughly one event in twenty three | `source_frames` |
| Half up once at the speed stage | 257 exact halves | `source_frames`, `record_out_frames` |
| Effective dated alias hops | 263 unknown, 341 ring or overlong | `canonical_code`, `reason_code` |
| Identity is code with generation | 45 absent pairs | `reason_code` |
| Effective dated rate family | 145 gaps | `reason_code` |
| Cadence keyed by site | 160 absent triples, nine deviant sites | `record_out_frames` |
| Effective dated handle policy | every event reaching the handle stage | `source_frames` |
| Transition legality per triple | 305 absent, 789 audit rows | `outcome`, `reason_code` |
| Terminal withdrawn absorbs | 2007 events | `outcome` |
| Nesting ring poisoning | 137 events over five timelines | `record_frames` |
| Missing nest edge | 2 events | `reason_code` |
| Delivery suppression with weekly recurrence | 70 events | `outcome` |
| Phase cleared only by exception | the clear rows of each scenario | `exit_phase` |
| Empty against null against absent class list | steady holds zero exclusions | `audited` map |
| Configuration layer order and decoy ring | latency to F50, steady and burst to F25 | `delivery_family`, every frame figure |
| Properties continuation and colon separator | `suppress.window.hours`, `alias.key.pad.width` | suppression window, identity padding |
| Fixed width tape layout | 2100 tape records | `source_frames` |
| Inert archive rows | most exception and nesting rows | nothing, by design |
| Event order by effective time | every timeline | `record_in_frames` |

Out of bounds: writing artifact figures as literals rather than deriving them
(`negative_hardcoded_sample_answers`); ignoring the folder handed to the engine
(`negative_ignores_data_dir_argument`); letting iteration order decide the walk
(`negative_nondeterministic_resolution`); restarting the cadence phase at every
event (`negative_phase_reset_each_event`); reading the illustrative percentage
column as the speed (`negative_percent_speed_column`); editing the shipped
corpus (`negative_inputs_modified`); leaving scratch files beside the ten
delivery paths (`negative_extra_delivery_files`); shelling out or reaching the
network (`negative_network_or_shell_out`); pasting shipped rows into the engine
(`negative_embedded_corpus_records`).

## Load-bearing work

The engine reads 51 non document files. Fifty one are load bearing: the ten
event shards carry the units, the ten correction parts and four override streams
decide each unit's field values, the fourteen reference tables decide identity,
rate, cadence, handling, legality, tier and authority, the five configuration
layers decide the scenario settings, the four host logs and the arbitration log
settle recorded time and the contest ordering, the two tape indexes supply
measurements before each cutover, and `reference_conform.py` supplies the stage
list and the signed off visit counts that `bottleneck_analysis.json` needs.
Removing any one of them changes a graded figure, so every shipped file is
load bearing.

Three rules are withheld from the contract text and derivable only from
evidence. The ordering that settles a same revision contest is fitted from the
320 arbitration records read against `source_tiers.csv`: greater tier wins in
194 cases with no counterexample, equal tiers fall to the later recorded instant
in 93 cases with no counterexample, and the 33 fully equal cases are declined.
The rotation order of the ingest logs is settled by the contract naming the
rotated file first while the corpus plants stale records whose wall clock is
later, so a maximum timestamp reading diverges. The direction of the clock
conversion is settled by `provenance_spec.md` stating that the offset is how far
the host reading stands ahead of coordinated time.

Out of bounds by design: an engine that works only against `/app/data`; an
engine whose answer depends on file order; an engine that trusts any frame
number the legacy module produces.

## Verification

The test channel registers 18 positive checks worth 64 weight and 9 negative
checks worth 21 weight. Seven checks carry weight 5, nine carry weight 3, two
carry weight 1, so hygiene is 2 of 64, under three percent. `tests/reward.toml`
divides each channel by its positive total and gives each half the reward.

Negative checks, each firing on one shortcut: `negative_hardcoded_sample_answers`
at -5; `negative_ignores_data_dir_argument`, `negative_nondeterministic_resolution`,
`negative_phase_reset_each_event` and `negative_percent_speed_column` at -3;
`negative_inputs_modified`, `negative_extra_delivery_files`,
`negative_network_or_shell_out` and `negative_embedded_corpus_records` at -1.
The judged channel registers 18 positive criteria worth 60 points and 9 negative
criteria worth 17 points.

| Requirement | Artifact | Checks | Criteria |
| --- | --- | --- | --- |
| Expose a scenario entry point | `optimize.py` | `artifacts_present_and_parse` w1 | R16 |
| Accept a folder, a scenario and an output path | `optimize.py` | `cli_matches_module` w1 | R16 |
| Resolve against an unseen folder | `optimize.py` | `heldout_extract_first` w5 | R16 |
| Resolve unseen configuration values | `optimize.py` | `heldout_extract_second` w5 | R13 |
| Visible scenario record | `scenario_visible.json` | `visible_spine_totals` w5 | R1 |
| Peak scenario record | `scenario_peak.json` | `peak_nest_cycle_poisoning` w5 | R6 |
| Steady scenario record | `scenario_steady.json` | `layered_delivery_totals` w5 | R13 |
| Burst scenario record | `scenario_burst.json` | `layered_delivery_totals` w5 | R13 |
| Latency scenario record | `scenario_latency.json` | `latency_phase_totals` w5 | R13 |
| Cursor continuity per timeline | all five records | `cursor_identity_all_scenarios` w5 | R1 |
| Timelines ordered by identifier | all five records | `visible_spine_totals` w5 | none |
| Admission counts | `perf_report.json` | `perf_report_counts` w3 | R5 |
| Median and speedup relation | `perf_report.json` | `perf_report_relation` w3 | none |
| Stage list and visits | `bottleneck_analysis.json` | `bottleneck_stage_visits` w3 | R19 |
| Dominant stage | `bottleneck_analysis.json` | `bottleneck_stage_visits` w3 | R19 |
| Busiest timelines | `bottleneck_analysis.json` | `bottleneck_hot_and_carry` w3 | none |
| Phase carrying timelines | `bottleneck_analysis.json` | `bottleneck_hot_and_carry` w3 | R1 |
| Leading reasons per scenario | `recommendations.json` | `recommendations_ranking` w3 | none |
| Global reason counts | `recommendations.json` | `recommendations_global` w3 | none |
| Rejection tallies | `data_quality.json` | `quality_rejected_map` w3 | R3 |
| Audit tallies | `data_quality.json` | `quality_audited_map` w3 | R3 |
| Summed tallies | `data_quality.json` | `quality_totals` w3 | none |
| Evidence folder untouched | none | `negative_inputs_modified` w-1 | R22 |
| Only ten delivery paths | none | `negative_extra_delivery_files` w-1 | none |
| No partial record when resolution stops | none | none | R14 |
| Counterfactual closing figures | none | none | R1 to R9 |
| Withheld rules attributed | none | none | R10, R15, R23 |
| Legacy module carries no authority | none | none | R18, R19 |

Overlap analysis. Every test check reads artifact bytes under `/app/out` or runs
the delivered engine on a folder the verifier built. Every judged criterion reads
the trajectory or the closing message. No judged criterion restates a figure the
artifacts carry: the ten closing quantities are absent from all ten artifacts by
construction, since `data_quality.json` carries only reason code tallies and
`perf_report.json` carries only admission counts. R1 through R9 each name a
distinct quantity. R10 through R13 each name a distinct derivation. R14, R21 and
R22 are the constraint criteria; each carries the type instruction following
and enforces one sentence of instruction.md. R16 is the only
code quality criterion. No two criteria grade symptoms of one behaviour, and no
single agent action fires more than one penalty of magnitude 5 across the two
channels: a baked in answer fires only `negative_hardcoded_sample_answers`,
since `negative_ignores_data_dir_argument` returns false whenever the shipped
totals come back, and R17 grades a message that disagrees with the artifacts the
same agent wrote.

## Root cause

The crux is that a delivery timeline is a running state machine whose cursor and
cadence phase both accumulate, while every input that feeds one event arrives
from a different source with its own notion of time and authority. Resolving one
event correctly requires settling identity across effective dated alias hops,
settling recorded time between an event row and a rotated host log, settling
measurements between an event row and two tape indexes under a per scenario
cutover, settling field values between a correction stream ordered by revision
and an override stream gated by authority, and settling legality against a
transition matrix. Only then does the cadence arithmetic run, and its output
feeds the next event of the same timeline.

The spine is the pair of running quantities per timeline: the record cursor and
the cadence phase. Both are emitted on every event record as `record_in_frames`,
`record_out_frames`, `phase_in` and `phase_out`, and both are summed into
`record_frames` and `exit_phase_sum`. Neither ever heals. An event resolved with
the wrong speed, the wrong handle rule, the wrong cadence row or the wrong phase
shifts every later event of that timeline, which is why a trap firing on one
event in fifty changes well over half the graded units.

Interaction matrix. Identity feeds the family code, which feeds the rate family,
which feeds both the timecode conversion and the cadence source family. The
cutover feeds whether the tape or the event row supplies the measurements, and
the tape also replaces the speed, so a correction to the speed is inert while the
tape is authoritative. The site code, which corrections and overrides may change,
feeds both the handle policy and the cadence row. The scenario settings come from
two configuration layers over an inherits chain, and the delivery family they
yield feeds every cadence row. Nest events take their net frames from another
timeline's resolved total, so the dependency order decides the arithmetic. The
delivery exceptions feed both the audit outcome and the only phase reset.

Withheld rule evidence. The contest ordering sits in `arbitration_notes.log`
read with `source_tiers.csv`. The log rotation order and the stale later
timestamps sit in the four host logs read with `provenance_spec.md`. The clock
direction sits in section two of `provenance_spec.md`. The inert decoy ring sits
in the `site.block.west` and `site.block.east` sections of `conform.ini`, which
no scenario reaches, so a live `CFG_CYCLE` count of zero is correct and
resolving the ring into a scenario costs as much as missing it.

**Red lines.** Never trust a frame number, phase or reason code from the legacy
module. Never read the event speed from the last column sharing its title. Never
restart the cadence phase outside a clear exception. Never merge two correction
revisions. Never write into the evidence folder.

## Solution shape

The engine loads every shared table once per folder into effective dated banks
keyed for a window lookup, resolves the ingest logs into a recorded time per
event, fits the contest ordering from the arbitration log, then resolves one
scenario by preparing every admitted event row, grouping rows by timeline,
ordering them by effective instant then sequence then identifier, computing the
nest dependency graph, walking the timelines in dependency order, and emitting
the running cursor and phase on every event. The driver then assembles the five
scenario records, the performance report built from medians of eleven interleaved rounds
against the legacy module after one untimed warm up call of each, the bottleneck record built from the signed off stage counter,
the recommendation record and the data quality record.

## Ordered plan

1. Read `index.md` and `conform_contract.md`; take the contract as authoritative.
2. Read `format_notes.md`; fix the event row as 23 positional fields.
3. Read `timecode_spec.md`; implement the drop frame subtraction.
4. Read `tape_layout.md`; implement the 69 character fixed width record.
5. Read `provenance_spec.md`; settle rotation order, clock direction and tape
   precedence.
6. Load `house.properties` with continuation lines and both separators.
7. Resolve the scenario settings through `site_overrides.ini` over `conform.ini`
   along the inherits chain; advance `delivery_family` and `tape_cutover_utc`.
8. Load `scenario_cutoffs.json`; distinguish absent, null and empty class lists.
9. Build the effective dated banks from the fourteen reference tables.
10. Resolve the ingest logs with `host_clock_offsets.csv` into a recorded time
    per event; advance admission.
11. Fit the contest ordering from `arbitration_notes.log` and `source_tiers.csv`.
12. Fold each correction stream to one record per event at the highest revision
    above the event row revision; advance the field values.
13. Apply the override streams gated by `authority_roles.csv` and the strictly
    later recording time; advance the field values.
14. Resolve identity through the two alias tables and the three asset tables;
    advance `canonical_code` and `generation`.
15. Resolve the rate family, the measurements, the span and the handling;
    advance `source_frames` through the single half up rounding.
16. Resolve the cadence row by site and family pair; advance the cursor and the
    phase.
17. Resolve legality, terminal absorption, class exclusion and suppression;
    advance `outcome` and `reason_code`.
18. Walk the timelines in dependency order with ring poisoning; advance
    `record_frames` and `exit_phase`.
19. Write the five scenario records, then the report, bottleneck, recommendation
    and quality records.

Reference closing message. The visible scenario holds 2203 applied events whose
record out frame would land elsewhere under a per event phase restart, and the
five scenarios hold 11739. Across the five scenarios 5933 events took their
measurements from the tape index, 3869 of them from `tape_index_v2.txt`. The
correction streams carried 1170 deletes superseded by a higher revision and 870
records that changed nothing because an identical record already stood. Of the
settled revision contests 494 turned on source standing and 286 on recording
time, while 95 stayed undecided. The ingest logs carried 195 events past a
scenario cutoff and 90 events landed exactly on one. The longest closed nesting
ring holds 3 timelines, the lowest being TL-0001, and poisons two more. Overrides
turned away for want of approval scope number 1074, of which the visible
scenario holds 278, with AP-0092 accounting for 32 of them. Recorded time came from an
ingest log rather than the event row for 2500 events, cf-ing-10 contributing 109.
Speed conversion landed exactly on a half frame 257 times, peak holding 72. The
ordering that settles a same revision contest is greater source tier first and
later recording time second, declining when both match, fitted against 320
recorded contests in `arbitration_notes.log` read with `source_tiers.csv`.

## Pitfalls

| Failure mode | Rule violated | Caught by | Weight at stake |
| --- | --- | --- | --- |
| Cadence phase restarted per event | Contract section 7 | `visible_spine_totals`, `cursor_identity_all_scenarios`, `latency_phase_totals`, `heldout_extract_first`, `heldout_extract_second`, `negative_phase_reset_each_event` | 25 positive and 3 negative |
| Speed read from field nineteen | Contract section 2 | every weight five check, `negative_percent_speed_column` | 35 positive and 3 negative |
| Recorded time taken from the event row | Contract section 2 | `visible_spine_totals`, `perf_report_counts`, `heldout_extract_first` | 13 |
| Corrections merged across revisions | Contract section 3 | `quality_rejected_map`, `quality_audited_map` | 6 |
| Tape precedence ignored | `provenance_spec.md` section 3 | `layered_delivery_totals`, `heldout_extract_second` | 10 |
| Cadence joined without the site code | Contract section 7 | `visible_spine_totals`, `bottleneck_hot_and_carry` | 8 |
| Nest ring resolved as ordinary nests | Contract section 9 | `peak_nest_cycle_poisoning` | 5 |
| Empty class list treated as absent | Contract section 1 | `quality_audited_map`, `recommendations_global` | 6 |
| Overrides applied without authority | Contract section 4 | `quality_rejected_map`, `heldout_extract_first` | 8 |
| Events ordered by file position | Contract section 10 | `cursor_identity_all_scenarios` | 5 |
| Decoy configuration ring resolved | Contract section 1 | `layered_delivery_totals` | 5 |
| Closing figures left unstated | Instruction closing paragraph | R1 to R9 | 45 positive |

Each of the first two modes alone puts at least 25 of the 64 point test
channel at stake through
overlapping checks, which is well over a third of the channel.

Reason codes cascade by design. A single wrong code on a single peak ring event
moves `peak_nest_cycle_poisoning` at weight 5, `quality_rejected_map` at weight
3, `quality_audited_map` at weight 3, `quality_totals` at weight 3 and
`recommendations_global` at weight 3, so one fact can cost 17 of the 64 point
channel. That concentration is intended: the reason code is the published
outcome of the whole resolution chain, and the exactness bar in the prompt says
an artifact counts only where every unit is exact. Partial credit still tracks
partial correctness because the four scenarios that carry no ring are graded by
`visible_spine_totals`, `layered_delivery_totals`, `latency_phase_totals` and
`cursor_identity_all_scenarios`, and the two held out extracts are graded apart
from the shipped corpus, so an engine wrong only on ring poisoning still keeps
the 15 points of `visible_spine_totals`, `layered_delivery_totals` and
`latency_phase_totals` and the 3 points of `bottleneck_stage_visits`.

## Provenance

```yaml
uuid: 7c2e77a1-1d71-5cee-8846-a8706b900394
instance_id: 7c2e77a1-1d71-5cee-8846-a8706b900394
task_name: terminal-bench/7c2e77a1-1d71-5cee-8846-a8706b900394
category: Video Processing
fix_patch_sha256: bf4a6b14ccaf27804fa279b67efc3bc834201d1375c9df0fe7908fcbaabefe32
solve_py_sha256: 60f015beb422aeb08a237be5598e2336944ff1b653522ba8f06dd26ed24485ba
language: python
data_files: 58
data_record_lines: 98290
artifacts: 10
test_positive_total: 64
judge_positive_total: 60
golden_score_measured: null
golden_score_runs: 0
golden_score_verified_by: >
  Expected figures on the test channel alone are exactly 1.000 on each oracle run and exactly
  0.000 on a no-op run. The test channel carries 18 positive checks worth 64
  weight and 9 negative checks worth 21 weight, so alone it runs from -0.328 to
  1.000. The judged channel carries 18 positive criteria worth 60 points and 9
  negative criteria worth 17 points, while the test channel carries 21 points of
  negative weight. tests/reward.toml divides each channel by
  its positive total and gives each half the reward, so the combined reward runs
  from -1.000 to 1.000 with no clamp.
```
