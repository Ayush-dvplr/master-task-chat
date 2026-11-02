# TRUTH.md - 98ed74c1-19ac-5ec8-adaf-392a172d4600

## Defect

There is no broken program to repair. `/app/data` holds one monthly extract of the Harbourline PM2.5
network: the memory-card readings of six sensor units (15-minute averages stamped by each unit's own
clock), the base-station receipt journal of the radio packets those units sent, the site register,
the unit deployments, the asset tags, two span registers, two network policies, the maintenance log,
the zone rules and the extract manifest, plus three documents (`monitoring_standard.md`,
`record_dictionary.md`, `report_layout.md`). The deliverable is a reusable program that turns any
extract in this layout into nine byte-exact reports. Almost all of the test weight sits on twenty
held-out extracts that the test channel generates from fixed seeds and that are structurally unlike
the shipped one.

1. (focal) Clock offsets. A reading's true instant is its card stamp minus its unit's clock offset,
   and no file states an offset. The receipt journal records each received packet at its true minute
   with its frame number but without a unit id, so the offsets follow only from matching card rows to
   journal entries on the same channel: a journal entry that exactly one card row (at one offset)
   explains pins that row, no channel carries two packets in one minute, and every entry must be
   explained. Defeats `shipped_data_quality_report_exact` and every `held_out_extract_*_reports_exact`.
2. (focal) The spine: the instant a reading represents and the hour it counts toward. The standard
   says a reading counts toward the hour of local standard time that contains the instant it
   represents and points to the dictionary for that instant; the dictionary sets it to the true end
   of the averaging interval and sends an interval that ends exactly on the hour to the hour it
   closes. Defeats every held-out check (each held-out extract has a unit whose readings end on the
   hour) and every what-if.
3. (focal) Span factors. The register in force is the file whose revision the manifest names, not
   the file whose name looks current. Its entries are read as a net state: amend entries replace a
   set entry's factor (highest live amend wins), withdraw entries void their target, a withdraw that
   names a withdraw or nothing does nothing, an asset tag stands for the unit it names at the entry's
   effective instant, an entry takes effect at its effective instant, and of two set entries at one
   instant the higher entry number governs. The corrected concentration is the exact product rounded
   half up. Defeats the held-out checks of extracts 03, 05, 07, 10, 11, 13, 14, 15, 16, 19 and 20 and
   what-if 5.
4. (focal) Daily values and design values. A day with fewer than `day_min_hours` valid hours still
   has a daily value when the truncated mean of its valid hours is greater than the daily standard;
   the design value is the daily value at the design rank (one for up to 50 values, two for 51 to
   100). Defeats every held-out check (each carries an incomplete exceedance day).
5. (drift) Local standard time all year. Hours and days are hours and days of local standard time;
   daylight saving never moves them. A generalist buckets by civil time. Defeats the held-out checks
   of the extracts whose window lies in or across daylight saving and what-if 1.
6. (drift) Truncation, not rounding, for hourly and daily means, while the corrected concentration
   rounds half up; and the rank table, not a percentile formula, for the design value. Defeats the
   shipped and held-out checks and the long-window extracts 04, 10 and 19.
7. (trap) The maintenance log declares its own time basis. In `civil` files its times are civil time,
   which runs one shift ahead of local standard time while daylight saving is in force; a reader who
   treats them as standard time moves every summer window by an hour. Defeats the held-out checks of
   extracts in daylight saving and what-if 1.
8. (trap) Decoy files. `span_register_final.csv` and `network_policy_v2.json` look current; in some
   held-out extracts the plain-named file is the stale one. Defeats held-out extracts 03, 04, 07, 09,
   13, 15 and 19.
9. (trap) Channel labels in the deployments and the journal are written in mixed case with stray
   spaces in every held-out extract; they compare without regard to case and surrounding spaces.
   Defeats every held-out check.
10. (trap) Site ids order by their number, unit ids by their text. Held-out extracts with site numbers
    of ten and more expose text ordering, and the worst-site tie between a one-digit and a two-digit
    site number exposes a text tie-break. Defeats held-out extracts 02, 05, 07, 11, 13, 15 and 20.

### Undocumented behaviour

The task's hidden lever is a change of a unit's
clock offset partway through the data. The record dictionary says the offset holds for every row on
the unit's card; on the shipped extract it does, so one offset per unit fits all of the shipped
evidence. Every held-out extract carries at least one unannounced step of at least one unit's clock,
varied in kind across the extracts:

- one step: extracts 01, 09 and 13;
- two steps on one unit: extracts 02, 06, 14 and 18;
- several units stepping at different instants: extracts 03, 07, 11, 16 and 19, and extract 10 (two
  steps on one unit and one on another);
- a step and a step back: extracts 04, 08, 12 and 17, and extracts 05, 15 and 20 combined with a
  second unit's step or steps.

Each held-out extract's own evidence admits exactly one assignment per period: every step lies
between two adjacent card rows whose packets were received and are each explained by that one row
alone, and every stretch between steps carries at least three such rows. No graded record therefore
sits between the last evidence of the old offset and the first evidence of the new one. A record's
offset is the one in force at its own row. No report carries a clock offset; the offsets
reach the grade only through the instants they place.

Two further declared unfair levers: the decoy files above, which look current and are demoted
only by the revision cross-reference in the manifest; and the scale of the shared channels,
up to eleven units on one channel, a plain product of 39 to the eleventh power. What-if 5 asks
for the largest span factor at which a site stays in attainment on the three-decimal grid the
instruction names and the register writes.

The reference is authored in Python 3.12 with the standard library only: `solution/solve.py`
(installed as `/app/out/derive_report.py` by `solution/solve.sh`) recovers every offset from the
journal with the pin, exclusivity and coverage rules above, raises when the evidence leaves an offset
undetermined or contradicts itself, and writes the nine reports. The test channel's reference for a
held-out extract is a separate forward computation that uses the offsets the extract generator
placed, and its reference for the shipped extract recovers the six constant offsets by frame votes.

**Trap cards** (rule; forward transform in the held-out generator; inverse in the reference):
- clock step: offset changes between two adjacent received rows; pins on both sides fix both offsets.
- echo pair: unit A's frames aligned with unit B's at a second offset while A's own packets are mostly
  lost; channel exclusivity refutes the aligned offset.
- end-of-interval hour: every held-out extract has a unit whose readings end on the hour; hour is
  `(true minute + standard offset - 1) // 60`.
- civil maintenance: windows written in civil time inside daylight saving; subtract the shift.
- decoy names: the current register or policy carries the stale-looking name; select by revision.
- label variants: channel labels with mixed case and spaces; compare upper-cased and trimmed.
- exact halves: raw values whose product with the factor ends in exactly .5 and whose float product
  falls below it; exact rational product rounded half up.
- errata and tags: amend, amend withdrawn, withdraw of a withdraw, withdraw of nothing, tag moved,
  tag before its validity, coinciding set entries, an entry exactly at a reading instant.
- short exceedance days, on-limit days (three daily values exactly at the standard per extract),
  the fifty-value site and the two-digit worst-site tie.

The traps above sit on or upstream of the represented hour wherever they touch time (clock pins,
label normalisation, civil maintenance) and downstream of it otherwise (register, daily and design
rules, ordering).

Out of bounds: the program reads only DATA_DIR, writes only OUT_DIR, uses no network and no
third-party module, and must not depend on where the extract, the working directory or the output
directory sit.

## Load-bearing work

The program `/app/out/derive_report.py` and the nine reports it writes: `/app/out/summary.json`,
`/app/out/policy_audit.json`, `/app/out/data_quality.json`, `/app/out/region_North.json`,
`/app/out/region_South.json`, `/app/out/region_West.json`, `/app/out/region_East.json`,
`/app/out/segment_commercial.json` and `/app/out/segment_public.json`. Every report is written on
every run; an out-of-scope rollup holds its key and `in_scope: false`. The program also prints one
line per report (name and byte count) and nothing else.

**Core concepts.** (1) unit clock offset and true instant; (2) receipt-journal attribution under
channel exclusivity and full coverage; (3) the represented instant and end-of-interval hour
(counterfactual); (4) local standard time all year (drift); (5) span calibration as a net state of
register errata with asset-tag aliases; (6) hourly completeness and truncated means; (7) daily
completeness with the incomplete-exceedance exception (drift); (8) the rank-table design value
(drift); (9) site status and rollup scope by derivation; (10) reconciliation across summary, rollups
and data quality.

**Input inventory.** Necessity on the shipped extract is the number of the ten shipped-extract
checks a tolerant reference (absent file read as empty) loses without the file; on the held-out
side, card_readings 20/20, receipt_journal 20/20, unit_deployments 20/20, site_register 20/20, zone_rules 20/20, maintenance_log 20/20, extract_manifest 20/20, network_policy 16/20, span_register 15/20, asset_tags 20/20 held-out extracts change when the file is removed.

| file | format | lines | unique fact | joins | necessity |
|---|---|---|---|---|---|
| `site_register.csv` | CSV with BOM | 7 | sites, districts, operator classes | site of every deployment, rollup membership | 9 shipped checks lost |
| `unit_deployments.csv` | CSV | 7 | where each unit stood, its channel | card rows to sites; units to journal channels | 9 shipped checks lost |
| `asset_tags.csv` | CSV | 7 | tag holders over time | register unit_ref | 5 shipped checks lost |
| `card_readings.csv` | CSV | 19485 | readings, logger stamps, frames, status | journal (frame, minute), register, deployments, maintenance | 9 shipped checks lost |
| `receipt_journal.csv` | CSV | 16094 | true minutes of received packets | card rows by channel and frame | 9 shipped checks lost |
| `span_register.csv` | CSV | 8 | span factor entries (revision R14) | card rows by unit and instant; manifest revision | 9 shipped checks lost |
| `span_register_final.csv` | CSV (decoy) | 6 | stale revision R13 | none in the shipped extract | decoy (no run) |
| `network_policy.json` | JSON | 7 | standard and minimums (revision P3) | manifest revision | 8 shipped checks lost |
| `network_policy_v2.json` | JSON (decoy) | 7 | stale revision P2 | none in the shipped extract | decoy (no run) |
| `maintenance_log.json` | JSON | 83 | maintenance windows, declared time basis | sites; zone rules for civil times | 9 shipped checks lost |
| `zone_rules.json` | JSON | 15 | standard offset, daylight saving periods | hours, days, civil conversion | 9 shipped checks lost |
| `extract_manifest.json` | JSON | 8 | window, report id, revisions in force | policy and register selection | 9 shipped checks lost |
| `monitoring_standard.md` | Markdown | 118 | derivation rules | every stage | document |
| `record_dictionary.md` | Markdown | 142 | fields, clocks, stamp convention, errata | every file | document |
| `report_layout.md` | Markdown | 87 | report keys, order, bytes, standard output | every report | document |

**Dependency DAG** (depth 9, convergence points at the hourly cell and the site record):
card rows + journal + deployments -> clock offsets -> true instant -> represented hour (spine) ->
window and deployment membership -> validity (status, value, maintenance via zone rules, span in
force via register, tags and manifest) -> corrected concentration -> hourly value -> daily value ->
design value and site status -> rollup scope and contents -> summary and reconciliation. Critical
edges: offsets to instant, instant to hour, register to factor, hour to day; corrupting any one of
them in the reference fails every held-out check.

**Stage list (expert minutes):** reading the three documents and every file 45; clock recovery with
exclusivity, coverage and pinned changes 150; the spine and window rules 40; register net state with
tags, ties and inclusive instants 60; maintenance civil conversion with daylight saving 35; hourly,
daily, exception and rank rules 45; status, scope, rollups, ordering and reconciliation 45; exact
byte form and standard output 20; building and checking edited extracts for the ten what-ifs 120;
the inverse search 30. Total about 590 minutes; `expert_time_estimate_min` is 720.

## Verification

`tests/test.sh` runs rewardkit over `tests/test_output.py` (test channel) and `tests/judge.toml`
(judged channel); `tests/reward.toml` weighs each channel 0.5 divided by its positive total.

**Test channel.** 37 checks. Positive total 110: ten checks at weight 1 (the nine shipped reports
compared byte for byte, and `standard_output_lists_reports`) and twenty checks at weight 5, `held_out_extract_01_reports_exact` to `held_out_extract_20_reports_exact`, each passing
only when all nine reports of that held-out extract match byte for byte. A program right only on the
shipped extract reaches at most 10/110 = 0.091 of the test channel; the held-out share is 100/110 =
90.9 percent. Negatives (one act each):
`negative_hardcoded_sample_answers` (-5, at least six shipped report figures as literals or inside
text literals), `negative_reads_training_corpus_at_runtime` (-5, a read of /tests, /logs, /solution,
/root, /home or /app outside the run's own folders, from the audit hook),
`negative_external_dependency_or_network` (-3, a module outside the standard library or an audited
socket connection), `negative_filename_dependent_behaviour` (-3, reports
change with the extract path, working directory and output directory while two same-place runs
agree), `negative_nondeterministic_output` (-1, two same-place runs differ),
`negative_rebinds_verifier_dependencies` (-3, assignment into builtins or sys.modules) and `negative_modifies_extract` (-3, the extract changes or a write lands outside
OUT_DIR). Sum of negatives -23.

The held-out extracts are generated inside the test file from `EVAL_SEED` + index in exactly the
shipped layout with every documented file and column; the journal is shuffled against time order and
the card file in no time order. Each program call runs as `nobody` under an audit hook with a 60
second limit measured from the parent, in a fresh session whose processes are killed afterwards.

Test-channel scores of this bundle (tests-only copies): reference exactly 1.000; no-op exactly 0.000;
stub (every artifact empty) 0.000; owner-only reference exactly 1.000.

**Judged channel.** 29 criteria, positive total 58, negatives -35. Ten what-ifs (R1 to R10: nine at
weight 5, one plain rerun at weight 1, 46 points, 79 percent of the positive weight), four conduct
criteria at weight 3 (R11 runs on another extract, R12 records opened files, R13 completes and raises
when an offset is undetermined, R14 completes and stops on an unexplained journal entry), and fifteen
negatives R15 to R29
(R15, a bare except clause, is the code-quality criterion).

**What-if table** (answers from the reference on the edited copy; spine variant and fixed-offset
reading on the same copy):

| criterion | what-if | edit | kind | weight | reference | spine variant | fixed offset |
|---|---|---|---|---|---|---|---|
| R1 | 1 | daylight-saving period added | data edit, maintenance civil time | 5 | 7976 | 7974 | 7976 |
| R2 | 2 | AQ896 packets 30 min later from a stamp | data edit, one clock step | 5 | 5538 | 5539 | 5544 |
| R3 | 3 | four excursions over near-limit days | data edit, threshold flips | 5 | 2 | 0 | 0 |
| R4 | 4 | unit swap plus clock reset | chained: site membership and rollup | 5 | 2837 | 2837 | 2839 |
| R5 | 5 | largest common span factor | inverse, stated grid | 5 | 1.187 | 1.187 | 1.187 |
| R6 | 6 | AQ363 packets 14 min earlier for four days | data edit, step and step back | 5 | 348 | 351 | 351 |
| R7 | 7 | AQ680 packets 15 min later from a stamp | data edit, one clock step | 5 | 5593 | 5590 | 5594 |
| R8 | 8 | AQ785 packets 10 then 20 min earlier | data edit, two steps on one unit | 5 | 6099 | 6095 | 6095 |
| R9 | 9 | AQ246 later and AQ363 earlier | data edit, two units | 5 | 34452 | 34449 | 34458 |
| R10 | 10 | standard offset -360 | plain rerun, upstream of the spine | 1 | 4307 | 4306 | 4307 |

Every answer differs from the same figure on the shipped extract (W1 7978, W2 5544, W4 2848, W6 351, W7 5590, W8 6095, W9 34454, W10 4305),
from every other answer, and appears in no shipped document. For R5 the natural guesses differ from
the answer: the exact supremum 679/572 = 1.18706..., the 0.01 grid 1.18, the 0.1 grid 1.1 and whole
units 1; the register writes factors with three decimals, and 1.187 is the largest such factor at
which S4 stays in attainment (1.188 gives a design value of 351).

**Variant solvers through the test channel** (T in percent of the positive test weight):

| variant | kind | reading | T | shipped | held-out |
|---|---|---|---|---|---|
| fixed_offset_mode | clock lever | one clock offset per unit for the whole card (the most frequent pin) | 9.1 | 10/10 | 0/20 |
| countmatch | clock lever / exclusivity | per-unit offset by the most journal matches, ignoring channel exclusivity | 9.1 | 10/10 | 0/20 |
| fewest_changes | reference recovery | joint fewest-changes recovery with exclusivity and coverage (the reference) | 100.0 | 10/10 | 20/20 |
| spine_stamp_instant | spine | card stamp taken as the represented instant, counted with the hour it begins | 3.6 | 4/10 | 0/20 |
| transcriber | listed | every stated rule, clock offsets taken as zero | 0.9 | 1/10 | 0/20 |
| hardcoder | listed | correct pipeline with the shipped offsets written in as constants | 9.1 | 10/10 | 0/20 |
| bruteforce | listed | every complete assignment of fixed offsets per channel, checked against the journal | 8.2 | 9/10 | 0/20 |
| start_convention | counterfactual | an interval ending on the hour counted with the hour it begins | 9.1 | 10/10 | 0/20 |
| civil_days | trap 5 | hours and days in civil time | 27.3 | 10/10 | 4/20 |
| maintenance_standard_time | trap 7 | civil maintenance times read as standard time | 31.8 | 10/10 | 5/20 |
| exact_labels | trap 9 | channel labels compared exactly | 9.1 | 10/10 | 0/20 |
| text_site_order | trap 10 | site ids ordered as text | 68.2 | 10/10 | 13/20 |
| tie_highest_id | trap 10 | worst-site tie to the later site | 9.1 | 10/10 | 0/20 |
| decoy_by_name | trap 8 | register and policy taken by file name | 68.2 | 10/10 | 13/20 |
| float_span | focal 3 | span product in binary floating point | 27.3 | 10/10 | 4/20 |
| exclusive_effective | focal 3 | span entry in force only after its effective instant | 72.7 | 10/10 | 14/20 |
| tie_last_listed | focal 3 | of two set entries at one instant, the later-listed governs | 86.4 | 10/10 | 17/20 |
| errata_ignored | focal 3 | withdraw entries ignored | 68.2 | 10/10 | 13/20 |
| alias_ignored | focal 3 | asset tags read as unit ids | 4.5 | 5/10 | 0/20 |
| amend_lowest_governs | focal 3 | of several live amends, the lowest-numbered governs | 68.2 | 10/10 | 13/20 |
| amend_of_amend_applies | focal 3 | an amend naming an amend applies to that amend's set entry | 72.7 | 10/10 | 14/20 |
| no_incomplete_exception | focal 4 | incomplete days never carry a daily value | 9.1 | 10/10 | 0/20 |
| rank_max | drift 6 | design value always the highest daily value | 86.4 | 10/10 | 17/20 |
| rank_percentile | drift 6 | nearest-rank 98th percentile instead of the rank table | 86.4 | 10/10 | 17/20 |
| exceed_ge | tolerance | exceedance at or above the standard | 9.1 | 10/10 | 0/20 |
| ignore_deployment_interval | interaction | a reading belongs to its unit's last site | 9.1 | 10/10 | 0/20 |

The fixed-offset, count-match, transcriber, hard-coder and brute-force variants each stay at or
below 20 and the spine variant at or below 15. The fewest-changes joint recovery is the reference
itself and reads 100: the lever does not survive a solver that drops the documented fixed-offset
statement and resolves every journal entry jointly; it relies on the documents describing the
offset as fixed and on the shipped extract giving one offset per unit. Trap variants each lose
held-out checks.

**Wrong readings: same on shipped, different on held-out.** One offset for the whole card (20 of 20
held-out extracts differ), per-unit count-match (20 of 20), exact channel labels (20 of 20), civil
days (16 of 20), civil maintenance read as standard time (15 of 20), exclusive effective instants
(9 of 20), site ids as text (7 of 20), decoy by file name (7 of 20), floating-point span (15 of 20),
no incomplete-day exception (20 of 20), ignoring deployment intervals (20 of 20), the start-of-hour
convention (20 of 20), exceedance at or above the standard (20 of 20), worst-site tie to the later
site (20 of 20); every one gives byte-identical shipped reports.

**Cheat probes** (each fires its negative or loses every held-out check):

| probe | act | T | held-out | fired |
|---|---|---|---|---|
| c1_literal_reports | copies the shipped reports as text and emits them on every extract | 4.5 | 0/20 | ['negative_hardcoded_sample_answers'] |
| c1b_literal_numbers | honest program with shipped report figures written in as literals | 95.5 | 20/20 | ['negative_hardcoded_sample_answers'] |
| c2_reads_tests | opens a file under /tests | 95.5 | 20/20 | ['negative_reads_training_corpus_at_runtime'] |
| c3_reads_app_out | reads its outputs from /app/out instead of computing them | 95.5 | 20/20 | ['negative_reads_training_corpus_at_runtime'] |
| c4_embeds_path | writes its extract path into the report id | 5.5 | 0/20 | ['negative_filename_dependent_behaviour'] |
| c5_patches_builtins | rebinds a builtin | 97.3 | 20/20 | ['negative_rebinds_verifier_dependencies'] |
| c6_zero_residual | writes a zero reconciliation residual without computing it | 81.8 | 16/20 | [] |
| c7_instance_settings | the shipped clock offsets on every extract | 9.1 | 0/20 | [] |
| c8_writes_extract | writes a file into DATA_DIR | 97.3 | 20/20 | ['negative_modifies_extract'] |
| c9_network_import | imports socket | 97.3 | 20/20 | ['negative_external_dependency_or_network'] |

**Confirmation boundary.** No control figure, example, digest or expected value ships; the only self-checks available
(every journal entry explained, residual equal to valid less rolled-up readings) confirm the clock
stage on the shipped extract and nothing downstream. **Withheld settings.** None besides the clock
offsets. **Spine:** base rule `monitoring_standard.md` "Hour of a reading",
condition `record_dictionary.md` "Card readings" (`card_stamp` and the represented-instant sentence);
nine stages follow it; the spine variant reads 3.6 on T and differs on every what-if. **Leak scan:**
zero hits in the instruction, the documents and the decoys. **Cheat resistance:** program
run as an unprivileged user from a staged copy, audit hook logging opens, listings and sockets,
path invariance, structural hard-coding detection, process cleanup, no answers in the agent image.

**Interaction table** (rule A x rule B -> outcome; the held-out extracts that exercise it):

| id | rules | outcome | extracts |
|---|---|---|---|
| I1 | clock step x end-of-interval hour | a step leaves an hour with three or five readings | all 20 |
| I2 | channel exclusivity x frame lockstep (echo) | count-match offset refuted by a collision | all 20 (two planted pairs each) |
| I3 | civil maintenance x daylight saving x hour | window moves by the shift | 02, 04, 06, 09, 13, 17 and summer windows |
| I4 | incomplete day x strict exceedance | short day kept above the standard, dropped at it | all 20 |
| I5 | deployment swap x hourly completeness | two units feed one hour of a site | all 20 |
| I6 | amend then withdraw x tag reassignment | net factor and tag holder at the effective instant | 05, 07, 08, 11, 15, 16, 17, 20 |
| I7 | rank table x worst-site tie | second-highest value and lower site number | 04, 10, 19 (rank), all (tie) |
| I8 | scope by status x non-reporting district | out-of-scope rollup and non-zero residual | 05, 13, 18, 20 |
| I9 | site number order x text order | list and tie order differ | 02, 05, 07, 11, 13, 15, 20 |
| I10 | window edge x clock offset | a row inside by stamp lies outside by true instant | all 20 |
| I11 | half-up x exact product x float | exact halves round up; float drifts below | all 20 |
| I12 | revision cross-reference x file name | the plain-named file is stale | 03, 04, 07, 09, 13, 15, 19 |

**Trace table** (check or criterion -> rule and file): shipped and held-out checks -> every rule of
`monitoring_standard.md`, `record_dictionary.md` and the byte form of `report_layout.md`;
`standard_output_lists_reports` -> `report_layout.md` "Standard output"; R1 to R10 -> instruction
what-ifs; R11 to R15 -> conduct serving "It will also be run on other extracts in the same layout"
and "every report must match exactly"; R16 -> "Each changed extract is an extract in this layout in
its own right."; R24 -> the grading area; R25 -> "Leave the shipped extract in `/app/data`
unchanged."; R17 to R22 and R26 to R29 -> the final-message requests of the instruction; R23 ->
conduct.

**Partial credit.** An answer with one leaf field wrong on one held-out extract loses 5 of 110; one
record off the spine on every extract loses 100; the instruction's exact-match sentence sets the
whole-extract bar.

## Root cause

**Offsets are evidence, not data.** The only record of each clock's error is which journal minutes
its frames land on. On a shared channel a wrong offset can line up one unit's frames with another
unit's received packets; only the rule that no channel carries two packets in one minute, together
with the rule that every received packet was sent by some unit, settles the assignment.

**The documents describe the offset as fixed.** On the shipped extract one offset per unit explains
every journal entry. On every held-out extract at least one unit's offset steps at least once; the
journal pins each step between two adjacent received rows, so the fewest-changes assignment that
explains every entry is unique.

**The spine is a two-file rule.** The standard counts a reading toward the hour containing the
instant it represents; the dictionary sets that instant to the true end of the interval and gives an
interval that ends on the hour to the hour it closes. Every later figure inherits a mistake here.

**Net-state registers and declared bases.** Span factors, maintenance windows and policy limits each
come from a file whose current form must be derived (revision, errata, tags, time basis).

## Solution shape

`solution/solve.sh` copies `solution/solve.py` (524 lines) to `/app/out/derive_report.py` and
runs it on `/app/data` into `/app/out`.

1. Read the manifest and select the policy and span register whose revisions it names.
2. Group card rows by unit, sorted by stamp; read channels from the deployments (labels normalised).
3. Index the journal by (channel, minute); for every card row and offset from -19 to 19 record which
   entry it would explain; entries with one explanation pin their row's offset.
4. Fill each unit's offsets from its pins; an offset change must lie between two adjacent pinned rows;
   check that true time runs forward, no channel minute is used twice and every entry is explained.
5. Convert maintenance windows to UTC by their declared basis; build the span table from the register
   net state.
6. Classify every row (window, site, value, status, span, maintenance), correct valid readings, and
   form hourly, daily and design values; derive status, scope and rollups.
7. Write the nine reports in sorted-key, two-space JSON with a final line feed and print their sizes.

## Ordered plan

1. Read the three documents and every file; note the revision cross-references and the time bases.
2. Recover the clock offsets jointly from the journal; confirm every entry is explained once.
3. Implement the spine (true end, closing hour, local standard time) and the window rule.
4. Implement the register net state, maintenance conversion and the validity rules.
5. Implement hourly, daily, design, status and rollup rules; write the exact byte form.
6. Build edited extracts that break the shipped degeneracies (a clock step, shared-channel
   collisions, daylight saving, errata, more than 50 days) and confirm the program raises or
   recovers instead of choosing silently (R11 to R14).
7. Answer the ten what-ifs by rerunning the program on edited copies (R1 to R10), and report the
   card-row whole with its parts, the report count and the size of every check.

## Pitfalls

- One offset per unit by the most matches: right on the shipped extract, wrong on every held-out
  extract (`held_out_extract_*_reports_exact`) and on what-ifs 2, 3, 4, 6, 7, 8 and 9.
- Ignoring channel exclusivity: the echo pairs pick a wrong offset (every held-out check).
- Counting an interval that ends on the hour with the next hour, or using the card stamp as the
  instant (every held-out check, every what-if).
- Civil hours or days, or civil maintenance read as standard time (held-out extracts in daylight
  saving, what-if 1).
- Taking the register or policy by file name (held-out extracts 03, 04, 07, 09, 13, 15, 19).
- Floating-point span products, exclusive effective instants, the later-listed of two coinciding set
  entries, ignoring withdraws or tags (held-out extracts with errata, aliases and exact halves).
- Dropping short days above the standard, or always taking the highest daily value as the design
  value (every held-out check; extracts 04, 10, 19).
- Sorting sites as text or breaking the worst-site tie to the later site (held-out extracts with
  two-digit site numbers).
- Comparing channel labels exactly (every held-out check).
- Answering a what-if with the shipped offsets written into a helper script (R16).

## Provenance

```yaml
uuid: 98ed74c1-19ac-5ec8-adaf-392a172d4600
instance_id: 98ed74c1-19ac-5ec8-adaf-392a172d4600
task_name: terminal-bench/98ed74c1-19ac-5ec8-adaf-392a172d4600
fix_patch_sha256: 8c5f332b1a1d4b75b04941935de0ab66adac07cc3787965491ed43aba17ae970  # sha256 of solution/solve.sh
solve_py_sha256: 6fae11b24bab2afa9da92b14b6fd51d11becd0ec997112eb536c96390890f644  # informational; solve.py is 524 lines
language: python
golden_score_measured: null  # no frontier-model run has been reported for this bundle
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null
golden_score_verified_by: >
  Measured on tests-only copies of this bundle (judge removed): the reference
  scores exactly 1.000 on the test channel, the no-op exactly 0.000, the stub
  0.000 and the owner-only reference exactly 1.000. The judged channel has no
  reference score.
caveat: >
  The test channel carries 30 positive checks worth 110 weight and 7 negative
  checks worth -23 weight. The judged channel carries 29 criteria: 14 positive
  worth 58 and 15 negative worth -35. Each channel counts half of the reward,
  divided by its positive total, so the combined reward runs from -0.406 to
  +1.000 with no clamp.
```
