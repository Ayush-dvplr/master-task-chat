# TRUTH.md - 59417607-2254-5165-b703-0d5a4aeb7367

## Defect

The bureau's billing cycle run turns handset task closings into a normalized billable stream and into service-line, region, segment, summary and data-quality reports. A handset stamps each closing on its own clock. The exchange keeps UTC and registers one closing call per closing on the client's line, in one-minute slots. No file states any handset's clock offset. The program has to recover the offsets from the exchange register: every registered row needs at least as many closings landing in its slot as it counts, and lost calls are allowed. Everything downstream (local business day, cycle membership, tier, amendment effect, rate interval, allowance credit order, minimum-invoice scope) runs on the recovered completion instants.

Focal items (each named with the check it defeats):
1. (focal) Clock offset recovery per exchange day (the spine). Getting it wrong fails every `hidden_extract_NN_exact` check, because every hidden extract carries an offset change. The one-offset-per-handset reading and the per-day count-match reading both fail all 18.
2. (focal) Amendments issued before the completion instant have no effect, and an amendment issued exactly at it has effect. Ignoring the test fails 15 of 18 hidden checks (`hidden_extract_01`, `02`, `04` to `07`, `09` to `11`, `13` to `18`); treating the equal instant as earlier fails all 18.
3. (focal) Allowance credit tie-break: among one client's eligible closings with the same completion instant, the lower closing reference is credited first. Every hidden extract plants such ties where the allowance runs out; reversing the tie-break fails all 18 hidden checks.

Drift item:
- (drift) Zone rules change inside some cycles (daylight steps in hidden extracts 02, 08, 10, 16). Reading only the first rule of a zone fails `hidden_extract_02`, `08`, `10` and `16`.

Trap items:
- (trap) Authoritative decoy rate card: on the shipped extract the header names `rate_card_final.csv`; in 14 hidden extracts it names `rate_card.csv` while a `rate_card_final.csv` is present. Always reading the final card matches the shipped extract and fails 14 hidden checks (`01` to `04`, `06` to `08`, `10` to `13`, `15`, `16`, `18`).
- (trap) Minimum invoice operand twins: region scope reads gross, segment scope reads net. Using gross for segments fails 6 hidden checks (`05`, `07`, `12`, `15`, `16`, `18`).
- (trap) The 18:00 tier edge is excluded from standard, 08:00 is included. Making 18:00 inclusive fails all 18 hidden checks; making 08:00 exclusive fails all 18.
- (trap) Half-even cents. Half-up fails all 18 hidden checks (each carries a report total at an exact even half cent).

### Undocumented behaviour

Every hidden extract carries an undocumented change of one or more handset clock offsets, placed overnight between two exchange days. The record dictionary (closings.csv section, line 19) says a handset clock is set when the handset is issued and is never adjusted afterwards. The whole-cycle reading is defensible from that text; the per-day reading is not stated, and the register settles it on each extract. The shipped extract is degenerate: one offset per handset fits the whole cycle. Kinds across the 18 hidden extracts:
- K1, one change: extracts 01, 05, 09, 14, 18.
- K2, two changes in one direction: extracts 02, 08, 12, 16.
- K3, several handsets changing on different days: extracts 03, 06, 10, 13, 17.
- K4, a change and a change back: extracts 04, 07, 11, 15.

Each hidden extract's register admits exactly one offset assignment per exchange day, equal to the truth. Pooled over the cycle, no single assignment per handset fits. No graded record sits between two readings: each change happens between exchange days, so every closing's offset is the one of its own stamp day.

## Load-bearing work

Concept list: handset clock offset; exchange register coverage (never over-counts, may lose calls); completion instant; zone rules with daylight steps; local business day; cycle window; tiers with regional holidays; duplicates across main and legacy exports; legacy duration unit; service aliases with case folding; rejections; amendments (void, minutes, revert) with issue-time effect; billable minutes by increment; dated half-open rate intervals; plan allowance credit by latest completion; micro-unit money with half-even cents; minimum invoice twins; reconciliation residual.

Input inventory (format, lines, unique fact, joins, necessity: shipped checks lost with the file removed under the tolerant oracle, and hidden extracts whose oracle result changes with it removed):

| File | Format | Lines | Unique fact | Joins | Shipped lost | Hidden changed |
|---|---|---|---|---|---|---|
| amendments.jsonl | JSONL | 31 | voids, minutes, reverts | handset+seq | 7 of 7 | 18 of 18 |
| clients.csv | CSV | 41 | line, segment, region, plan, zone | client | 7 of 7 | 18 of 18 |
| closings.csv | CSV | 1153 | main closings | client, service | 7 of 7 | 18 of 18 |
| code_aliases.csv | CSV | 4 | old codes | service | 7 of 7 | 18 of 18 |
| cycle.json | JSON | 7 | window, card, minimum | rate card | 7 of 7 | 18 of 18 |
| exchange_register.csv | CSV | 1468 | calls per line slot | line, day | 7 of 7 | 18 of 18 |
| holidays.csv | CSV | 3 | regional holidays | region | 7 of 7 | 18 of 18 |
| legacy_closings.txt | pipe TXT | 391 | legacy closings, unit | handset+seq | 7 of 7 | 18 of 18 |
| plans.csv | CSV | 4 | allowance, credit tiers | plan | 7 of 7 | 18 of 18 |
| rate_card_final.csv | CSV | 41 | rates in force (named by the header) | service, tier | 7 of 7 | 18 of 18 |
| rate_card.csv | CSV | 41 | decoy on the shipped extract | none | decoy | decoy |
| service_catalog.csv | CSV | 11 | product line, increment | service | 7 of 7 | 18 of 18 |
| zone_rules.csv | CSV | 4 | UTC offsets over time | zone | 7 of 7 | 18 of 18 |

The documents (billing_standard.md, record_dictionary.md, report_layout.md) name every non-.md input.

DAG: closings.csv + legacy_closings.txt (duplicates, unit, aliases) -> clock offsets from exchange_register.csv + clients.csv lines -> completion instants -> amendments.jsonl effect -> zone_rules.csv local time -> local business day -> cycle.json window -> holidays.csv + tiers -> rate card named by cycle.json -> service_catalog.csv increments -> plans.csv allowance credit -> money -> region and segment scope against cycle.json minimum -> summary reconciliation.

Stage list (expert hours): reading the three documents and the 13 inputs (1.0); discovering that offsets must come from the register and building an exact coverage search with pruning, since a hit count is fooled by lost calls on shared lines (2.5); finding that offsets are per day, not per handset, on unseen extracts (2.0); duplicates, legacy units and aliases (0.5); amendments with issue-time effect and reverts (1.0); zone steps, local day, cycle, tiers and holidays (1.0); rates, increments, allowance credit order and tie-break (1.0); money, scope twins, reports, byte form, reconciliation (0.5); building edited extracts and answering eight what-ifs (0.5). Total about 10 hours, matching expert_time_estimate_min 600.

## Verification

Test channel: 31 checks. Positive total 97: easy_total 7 (six shipped-report checks and one stdout check at weight 1), hard_total 90 (18 hidden extracts at weight 5). Hidden share 90/97 = 92.8 percent. Negatives: negative_hardcoded_sample_answers (-5), negative_file_access_outside_run_paths (-5), negative_third_party_import (-3), negative_network_or_process (-3), negative_location_dependent_output (-3), negative_nondeterministic_output (-1); total 20. Judged channel: 27 criteria, positive total 58 (eight what-ifs carry 40), negative total 33.

Test-channel scores, each from a tests-only copy with the Docker scorer: oracle 1.0, owner-only oracle 1.0, nop 0.0, stub 0.0. No judged-channel oracle score exists.

### Offset recovery

No file ships an example output, digest, control total or expected figure. The only stated invariant, the reconciliation residual (report_layout.md line 70), holds under every wrong reading in the variant table (all reconcile to 0).

The offsets are never given; their domain, -19..19, is stated in record_dictionary.md line 19. The space per exchange day is 39^k for a coupled component of k handsets. Largest k per extract: shipped 2; hidden 01, 02, 04, 12, 14, 15, 17 2; 06, 08, 10 3; 03 5; 18 5; 07 6; 05 8; 13 8; 09 9; 16 10; 11 11. Plain enumeration at the measured rate needs 2.3e13 s per day on hidden 11, 5.0e11 s on hidden 16, 1.2e10 s on hidden 09 and about 2e8 s on hidden 05 and 13, against a 60 s call limit. Meet-in-the-middle needs a half table of 39^6 = 3.5e9 entries on hidden 11, over the 4096 MB container memory at any per-entry size. The pruned search (per-handset prefilter, then depth-first with an upper-bound coverage test) takes at most 0.197 s on any extract (hidden 11). The search is exhaustive over the stated class with a sound bound and returns exactly one assignment on every exchange day of the shipped extract (21 of 21) and of every hidden extract; plain enumeration over all 39^k members agrees on all 165 shipped components of size at most 2. A per-day count-match (the offset landing the most stamps on registered slots) picks a wrong offset on 2 or 3 handset-days in every extract, because one handset's closings land, under a wrong offset, on another handset's registered calls on a shared line while its own calls are lost; as a program it scores T = 6.2. A whole-cycle best fit scores 7.2.

Wrong members refuted on the shipped extract (2026-03-02): H-08 at 2 (truth 1) by line L-2013 slot 06:33, 1 call; H-11 at -6 (-7) by L-2093 05:33; H-13 at -6 (-7) by L-2355 09:06; H-15 at -10 (-11) by L-2029 07:35; H-18 at -2 (-3) by L-2096 16:48; H-25 at 8 (7) by L-2302 17:51; H-31 at -14 (-15) by L-2024 15:40; H-33 at 9 (8) by L-2453 06:50. Each named row counts more calls than the closings the wrong member lands in that slot.

Spine: record_dictionary.md line 19 (completion instant = stamp + clock offset) with record_dictionary.md line 31 (register: one call per closing, rows never over-count) and billing_standard.md line 31 (local day from the completion instant). Chain after it: billing_standard.md line 31 (local business day), 23 (cycle), 55 (tiers), 11 (amendments, issue-time effect), 43 (pricing), 15 (billable minutes), 7 (allowance credit), 35 (minimum invoice), 39 (money), report_layout.md summary section (reconciliation). The one-offset-per-handset reading by majority scores T = 7.2: 7 of 7 shipped checks, 0 of 18 hidden, every report well formed with residual 0. On the judge it gives the fixed-reading value on all eight what-ifs (0 of 40 what-if weight).

Every graded integer of at least 100000 and every what-if answer was token-matched against every agent-visible file and the instruction: the one hit is 850000, a rate in rate_card_final.csv that also appears as a graded micro amount (an input datum). No what-if answer appears anywhere.

The eight what-ifs are all data edits through the spine (each moves one handset's stamps from a named day), each at weight 5, 40 of 58 positive judge weight: one chained (3), one inverse sweep with a stated grid (4), two scope sums at a changed minimum (2, 8). Every what-if takes a different value under the fixed reading (table below).

### Interaction table

| Interaction | Deciding text | Hidden extracts |
|---|---|---|
| offset change x tier edge at 18:00 and 08:00 | record_dictionary.md 19, 31; billing_standard.md 55 | all 18 |
| offset change x allowance credit order and tie-break | billing_standard.md 7 | all 18 |
| offset change x amendment issue-time test (equal instant has effect) | billing_standard.md 11 | all 18 |
| revert issued with its target has no effect | billing_standard.md 11 | all 18 |
| shared lines x coupled offset search (echo runs, lost calls) | record_dictionary.md 31 | all 18 |
| daylight step x local day and tier | billing_standard.md 31; record_dictionary.md 55 | 02, 08, 10, 16 |
| rate boundary inside the cycle x local day | billing_standard.md 43 | 04, 09, 15, 17 |
| unrated closings | billing_standard.md 19, 43 | 06, 12, 17, 18 |
| legacy unit minutes | record_dictionary.md 39 | 06, 13, 17, 18 |
| byte order marks | record_dictionary.md 7 | 07, 12, 17 |
| header names the plain card, final card present | billing_standard.md 43; record_dictionary.md 27, 47 | 14 of 18 |
| new cycle period and codes | billing_standard.md 23 | 02, 04, 06, 10, 12, 14, 17 |
| revert naming a revert, revert naming no amendment | billing_standard.md 11 | all 18 |
| blank line inside the legacy export | record_dictionary.md 39 | all 18 |
| quoted holiday name holding a comma | record_dictionary.md 7 | all 18 |
| zone step at local midnight with a closing at the step instant | record_dictionary.md 55 | 10 |
| rejected and void closings after the cycle end (quality-list exclusion order) | report_layout.md 17 to 22 | all 18 |

Every row above has one reading under the instruction and the three documents, and that reading matches the reference.

Mutation families covered: ties in completion instants (all 18), values across the minimum (all, L2 flip per extract), temporal boundary shifts (tier edges, local midnight, issue instants), daylight transitions (02, 08, 10, 16), changed settings (all 18), new periods (02, 04, 06, 10, 12, 14, 17), rules that do not fire on the instance (reverts, outside-cycle, unrated, early amendments), changed number of in-scope partitions (each hidden minimum is chosen inside one partition's net-to-gross span).

### Constraint portfolio and variant table

Variant T from the same checks (local grading of the test channel; spine and offset variants confirmed by the Docker scorer):

| Wrong reading | Same on shipped | T | Hidden failed |
|---|---|---|---|
| one offset per handset by majority (spine variant) | yes | 7.2 | 18 of 18 |
| one offset per handset, exact pooled fit | yes | 7.2 | 18 of 18 |
| shipped offsets written as constants | yes | 7.2 | 18 of 18 |
| count-match offset per day | no (1 of 7) | 6.2 | 18 of 18 |
| legacy row wins a duplicate | yes | 7.2 | 18 of 18 |
| amendment issue time ignored | yes | 22.7 | 15 of 18 |
| revert naming a revert takes effect | yes | 7.2 | 18 of 18 |
| blank legacy line read as a closing | no (7 of 7) | 0.0 | 18 of 18 |
| zone step instant exclusive | yes | 94.8 | 1 of 18 (10) |
| amendment at the completion instant treated as earlier | yes | 7.2 | 18 of 18 |
| revert at the same instant takes effect | yes | 7.2 | 18 of 18 |
| 18:00 inclusive in standard | yes | 7.2 | 18 of 18 |
| 08:00 exclusive in standard | yes | 7.2 | 18 of 18 |
| allowance tie-break reversed | yes | 7.2 | 18 of 18 |
| stream tie order reversed | yes | 7.2 | 18 of 18 |
| cents half up | yes | 7.2 | 18 of 18 |
| segment scope on gross | yes | 69.1 | 6 of 18 |
| final rate card always read | yes | 27.8 | 14 of 18 |
| first zone rule only | yes | 79.4 | 4 of 18 |
| cycle includes the day after last_day | yes | 7.2 | 18 of 18 |
| rate effective_to inclusive | yes | 69.1 | 6 of 18 |
| allowance credit earliest first | no (6 of 7) | 1.0 | 18 of 18 |
| holidays ignored | no (6 of 7) | 1.0 | 18 of 18 |
| local day in UTC | no (6 of 7) | 1.0 | 18 of 18 |
| stamp used as completion | no (6 of 7) | 1.0 | 18 of 18 |
| register allowed one over-count | no (7 of 7) | 0.0 | 18 of 18 |

Every recovered-setting and tie-break reading (offset, allowance tie-break, stream order, half-even, issue-instant edges) gives byte-identical shipped reports and fails every hidden extract. Allowance order, holidays, local day and stamp-as-completion are documented rules whose wrong reading the shipped extract exposes; they are counted as constraints, not traps. A zone rule taking effect exactly at its from_utc instant binds hidden extract 10, whose step falls at local midnight with a closing completed at that instant (reading it as exclusive fails that check only); the void-before-minutes ordering variant gives identical output everywhere and is not a reading the text admits. One leaf field wrong in one report fails that extract's single check (weight 5) and, on the shipped extract, the one shipped check of that artifact (weight 1).

Spread of each reading (rows of closings.csv whose normalized record changes under the wrong reading, per 500-row band): offset change, 18:00 edge, allowance tie-break, equal-instant void and equal-instant revert hit every band in all 18 hidden extracts, except that the offset change reaches two of the three bands in extract 02; the decoy card hits every band in its 14; the zone rule in its 4. The amendment issue-time trap fires through amendments.jsonl (under 500 rows) in 15 extracts; segment scope and half-even fire at partition level, not on rows.

Strictness probes: self-consistent wrong outputs (every rate plus 500 micro, every worked minute plus 1) score T = 1.0. Each variant above violates one constraint and fails exactly its listed set. The happy-path reading (one offset per handset) passes only the 7 shipped checks. One defect planted in the oracle output: one value changed 6.2, a row dropped 5.2, a row added 5.2, two rows swapped 6.2, one net_cents rounded the wrong way 58.8 (8 hidden lost), a key renamed 5.2, a type changed 5.2; every defect fails at least one check.

What-if list and disclosure-difference table (oracle answer against the fixed-offset reading):

| What-if | Weight | Oracle | Fixed reading |
|---|---|---|---|
| 1 H-33 +9 min from 2026-03-12, P-BASIC 0, summary net | 5 | 96860261500 | 96945842500 |
| 2 H-08 +9 min from 2026-03-12, minimum 20000000000, in-scope segment net | 5 | 76399338500 | 76410003500 |
| 3 H-11 -6 min from 2026-03-16, chained minimum, in-scope region net | 5 | 66714709500 | 66678709500 |
| 4 H-31 -9 min from 2026-03-16, P-EXEC grid, threshold 93360000000 | 5 | 720 | 840 |
| 5 H-18 +6 min from 2026-03-09, rate_card.csv named, region_north net | 5 | 20295679500 | 20278774500 |
| 6 H-25 -12 min from 2026-03-09, west holiday 2026-03-11, after_hours | 5 | 34500454500 | 34371706500 |
| 7 H-13 +9 min from 2026-03-16, P-EXEC 0, credit | 5 | 5041886500 | 5077580500 |
| 8 H-15 -6 min from 2026-03-16, minimum 20000000000, in-scope report net | 5 | 143114048000 | 143108240000 |

No answer equals the shipped value of the same figure (shipped net 95969825500, credit 9865163000, in-scope count 7, P-EXEC allowance 480), and no answer appears in any agent-visible file. Each changed extract carries an overnight offset change and admits exactly one per-day assignment. Every shifted offset stays inside -19..19 (H-33 to -1, H-08 to -8, H-11 to -1, H-31 to -6, H-18 to -9, H-25 to 19, H-13 to -16, H-15 to -5).

Cheat-resistance measures, with probe results on the Docker scorer: literal shipped reports 0.0206 with negative_hardcoded_sample_answers fired; a program that opens /tests, /solution and /logs files 0.9485 with negative_file_access_outside_run_paths fired; a program that embeds its extract path 0.0206 with negative_location_dependent_output fired; a forged zero residual 1.0 (identical bytes, the true residual is 0); a program that copies reports found in /app/out 0.0722; shipped offsets on every extract 0.0722. The time-patching cheat does not apply (no performance check). Every run goes through an audit hook that logs opens, process starts and socket events, under a dropped uid with a 60 second limit timed from the parent.

Hardness sources: authoritative decoy (rate card, current on the shipped extract and decoy on 14 hidden), degenerate shipped extract, no examples, fixed-setting wording, scale (coupled components of 3 to 11 handsets), echo runs with lost calls against count-match, all-or-nothing hidden extracts.

### Trace table

| Item | Rule | Source |
|---|---|---|
| hidden_extract_01..18_exact | every report, every rule | record_dictionary.md 19, 31; billing_standard.md 7 to 55; report_layout.md 5 to 70 |
| shipped_normalized_stream_exact | record fields and order | report_layout.md 24 |
| shipped_product_lines_exact | product lines | report_layout.md 43 |
| shipped_region_invoices_exact | region reports, gross scope | report_layout.md 47; billing_standard.md 35 |
| shipped_segment_invoices_exact | segment reports, net scope | report_layout.md 59; billing_standard.md 35 |
| shipped_summary_exact | summary, reconciliation | report_layout.md 63 |
| shipped_data_quality_exact | data quality lists | report_layout.md 13 |
| run_output_lists_reports | stdout lines | report_layout.md 9 |
| negatives (test) | instruction contract sentences | instruction.md paragraph 2 |
| judge R1..R8 | what-ifs | instruction.md what-if list |
| judge R9..R11 | final-message disclosures present | instruction.md final paragraph |
| judge R12..R16 | conduct, code quality | instruction.md paragraph 2 and 3 |
| judge R17..R27 | negatives | instruction.md sentences quoted in each |

Ownership between the two channels: the delivered program's file access, network, location and nondeterminism belong to the test negatives; the agent's own writes into /app/data by a command other than a run of its delivered program belong to judge R26; reading /tests or /logs by the agent belongs to judge R25, while the program opening them belongs to the test negative. R18 owns the hard-coded helper script; R20 owns a what-if with no run of any script or program. R12 rewards running on an extract other than the what-if copies. The location negative fires only when the two same-path runs agree, so a nondeterministic program pays only the nondeterminism negative.

## Root cause

The documents describe each handset as keeping one clock offset, and the shipped register is consistent with that. A solver that fits one offset per handset matches every shipped figure. On other extracts, offsets change between days, and only a per-day exact coverage search over the register (rows never over-count) recovers the completion instants; a per-day hit count is misled where a handset's calls were lost on a line another handset also serves. The register is the only stated evidence, and its invariant is a hard constraint.

## Solution shape

solve.py reads every input with BOM-tolerant, space-trimmed CSV parsing. It drops legacy duplicates and converts legacy durations by the header unit. It groups closings by stamp day and handset. For each day it solves the register coverage problem: a per-handset prefilter over -19..19, then a depth-first search over handsets ordered by domain size, with an optimistic upper bound per registered cell. It raises when zero or more than one assignment fits. It then applies amendments in issue order, with the issue-time test and reverts, and computes local time from the zone rules at the completion instant, the local day, cycle membership, tier, rate interval, billable minutes and allowance credit from the latest completion. Last it writes the reports in compact sorted ASCII JSON with one wrote line per report.

## Ordered plan

1. Parse inputs, normalise codes, resolve duplicates and the legacy unit.
2. Recover per-day clock offsets from the register; fail loudly on zero or several fits.
3. Apply amendments with the issue-time test.
4. Local time, local day, cycle, tier.
5. Service, rate, billable minutes, allowance credit.
6. Money, cents, scope, reports, reconciliation.

## Pitfalls

- Fitting one offset per handset over the whole cycle.
- Scoring offsets by hit counts instead of the register's never-over-counts constraint.
- Reading rate_card_final.csv when the header names rate_card.csv.
- Testing segment scope on gross.
- Crediting earliest first, ordering credit by stamp instead of completion, or breaking credit ties the wrong way.
- Counting a void or minutes amendment issued before completion, or ignoring one issued exactly at it.
- Taking the zone offset at the stamp, or only the first zone rule.
- Rounding cents half up.

## Provenance

```yaml
uuid: 59417607-2254-5165-b703-0d5a4aeb7367
instance_id: 59417607-2254-5165-b703-0d5a4aeb7367
task_name: terminal-bench/59417607-2254-5165-b703-0d5a4aeb7367
fix_patch_sha256: 63739885be29c54fabce9758bea9586b1899213106673c63c5d7516ae2a86076  # sha256 of solution/solve.sh
solve_py_sha256: 61a92fbe485c0ee68245622b4aedff2d8057a39e47caf8709b3601af5144d43f  # informational; solve.py is 407 lines
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: >
  Test channel only, on tests-only copies with the Docker scorer: oracle
  1.000, owner-only oracle 1.000, nop 0.000, stub 0.000. Harbor oracle and
  nop runs are recorded separately. The judged channel has no oracle score.
caveat: >
  The test channel carries 25 positive checks worth 97 weight and 6
  negative checks worth -20 weight, so on its own it ranges -20/97 = -0.206
  to +1.000. The judged channel carries 27 criteria, 16 positive worth 58
  points and 11 negative worth -33 points. tests/reward.toml divides each
  channel's weighted sum by its positive total and gives each half of the
  reward.
```
