# DESIGN v2: pilotage-dues-reconstruction (board 49087b0)

Shape D (degenerate shipped instance). Sources: L-CONV per-station conventions recovered
from the station's own paid invoices (primary, S2 degenerate shipped instance), S3 unique
fit, S6 hidden-only fixtures (notices, ambiguous periods), N2 held-out w5 tier, P-5 probe
judge. Reuses the v1 world (G-7, v1_design_backup/), prototype in proto2/, kill table in
KILL_TEST.md. IDEA_v2 G-1..G-8 applied.

## 1. World and job
Four pilot stations North, South, West, East; boardings 2026-07-01 00:00 to 2026-09-30 23:59
local time. The agent writes /app/out/derive_report.py, run as
`python3 /app/out/derive_report.py --data <dir> --out <dir>`, and runs it once on /app/data
to produce the ten fixed documents in /app/out.

## 2. Spine
1. Load and validate every declared file; a missing or unparseable one is fatal:
   stderr `ERROR unreadable input: <file name>`, exit 2.
2. Parse log visits (BOARD/RELEASE/CANCEL, NOTE lines ignored), register, certificates,
   calendars, notices, four paid files, disputed batch.
3. Record rejections, first code in order malformed_record, duplicate_invoice (every copy),
   unknown_visit, station_mismatch, early_invoice, already_paid; resolve supersedes.
4. Periods: a notice opens a new period at 00:00 of its date; the boarding instant decides.
5. SR1 convention fit per station: one choice of six conventions (assist mark, draft mark,
   surcharge hours, whether surcharge reckons assist, calendar kept, Monday after a Sunday
   holiday) inside the stated ranges under which every period has a listed tariff that
   reproduces every accepted paid invoice of the period.
6. SR2 tariff per period (coefficients not named by the notice carry across periods); more
   than one fitting tariff -> unresolved, reason `more than one listed tariff reproduces
   every paid invoice`.
7. Recompute each accepted disputed invoice (exemption: public vessel with certificate in
   force at the boarding instant -> due 0.00; call-out fee for cancelled bookings; minimum
   due) and give the verdict.
8. Aggregate into region, segment and summary documents.

COUPLING (circular s6): "Every recomputed due and every verdict uses the tariff and
conventions recovered for that station and period, or the station's unresolved status."
The recovered conventions and tariff of a station enter every one of its audit rows, its
region file, both segment files and the summary.

## 3. Inputs (14 files, 8 formats)
| file | format | lines (bundle) | feeds |
|---|---|---|---|
| pilot_movements.log | log | ~22,000 | visits, instants, draft, tugs, assist |
| vessel_register.tsv | tsv | ~2,100 | GT, segment, certificate id |
| certificates.json | json | ~400 | exemption validity |
| holidays.json | json | ~60 | 7 calendars (national, north, south, west, east, harbour, fishery) |
| station_notices.md | md | ~30 | notice rows (none in force on shipped), call-out fee, minimum due |
| paid_north.csv | csv | >=2,000 | North fit evidence |
| paid_south.jsonl | jsonl | >=2,000 | South fit evidence |
| paid_west.txt | fixed-width txt | >=2,000 | West fit evidence |
| paid_east.xml | xml | >=2,000 | East fit evidence |
| disputed_batch.csv | csv | >=2,000 | disputes |
| tariff_circular.md | md | ~130 | due, conventions, periods, fit, verdicts, paid layouts |
| exemption_policy.md | md | ~30 | segments, certificates, register layout |
| output_contract.md | md | ~90 | records, rejections, fatal, values, documents |
| rule_register.md | md | ~25 | topic -> governing file; arbiter sentence |

A5: >=20,000 lines total, each csv/tsv/jsonl/txt/log >= 2,000.
Chains (length >= 4):
- C1 disputed -> log visit -> register -> certificates -> conventions+tariff -> verdict -> segment -> summary.
- C2 paid file -> log instant -> notices period -> holidays calendar -> fit -> region -> summary.
- C3 log instant -> calendar + Monday rule + surcharge hours -> surcharge flag -> fit -> recompute -> policy_audit.

## 4. Stated rules (about 25; one governing file each, W2)
R1 log grammar and visit [circular s1]; R2 measured draft `draft_m=<d.dd>` [s1];
R3 domain sentence in s1 definitions, keyed away from the fields: "A mark that a station
sets inside a unit is a whole number from 1 up to the size of the unit (1 to 30 minutes
inside a 30-minute assist block, 1 to 10 centimetres inside a tenth of a metre); a time of
day that a station sets is on a quarter hour.";
R4 five lines, half-even [s2]; R5 CV-A assist 40.00 per whole 30 minutes plus 40.00 for a
part block once its minutes reach the station's assist mark [s2]; R6 CV-D billed draft is
whole tenths plus one tenth once the remaining centimetres reach the station's draft mark
[s2]; R7 CV-N surcharge applies from the station's start of surcharge hours up to, not
including, its end, passing midnight when the end is earlier [s2]; R8 CV-B surcharge base
tonnage+draft+towage, plus assist where the station reckons it [s2]; R9 CV-H each station
keeps exactly one calendar of holidays.json [holidays.json header]; R10 CV-S a station may
also keep the Monday after a Sunday holiday [holidays.json note]; R11 listed values [s3];
R12 periods and notices [s4] (SR3); R13 principle [s5] (SR1): "A station's conventions are
its assist mark, draft mark, surcharge hours, whether its surcharge reckons the assist line,
the calendar it keeps and whether it keeps the Monday after a Sunday holiday. They hold for
the whole review and the station's accepted paid invoices are the only record of them:
exactly one choice of the six, inside the ranges of section 1, leaves every period of the
station with at least one listed tariff that reproduces every accepted paid invoice of the
period to the cent."; R14 tariff per period, coefficients carried [s5]; R15 verdicts and
the one unresolved reason [s6] (SR2); R16 billed forms `d.dd` and `<cents>c` [s6];
R17 supersedes [contract]; R18 segments and exemption [exemption_policy]; R19 call-out fee
and R20 minimum due [notices]; R21 rejections and precedence [contract]; R22 fatal input
[contract]; R23 money strings and sort orders [contract]; R24 largest_refund tie-break
[contract]; R25 vessels count per segment [contract].
No document names any station's readings; the shipped values (assist mark 1, draft mark 1,
22:00-06:00, assist reckoned, own regional calendar, Monday kept) appear in no file.

## 5. Sharp rules
SR1 L-CONV. Reflex reading (PREMORTEM): marks as "started" or "full", 22:00-06:00 or
whole-hour windows, the station's own calendar, applied everywhere. Exact on the degenerate
shipped instance (every station uses the headline choice). Hidden draws per station:
assist mark natural {1,15,16,30} p0.2 else uniform 1..30; draft mark natural {1,5,6,10} p0.2
else 1..10; hours headline p0.15 else start on a quarter hour 18:00-23:45, end 04:00-08:45;
calendar own p0.25 else another of the 7; Monday and assist-reckoning by coin. Every hidden
corpus asserts >= 2 stations with a foreign calendar or an off-hour window. Uniqueness
(G-1): coverage plants (part blocks at mark-1 and mark minutes, centimetres at mark-1 and
mark, invoices within 15 minutes either side of start and end, a daytime invoice on every
date where calendars differ and on each Monday after a Sunday holiday, surcharged invoices
with assist) plus an observe loop on RNG seed*13+7 over the full space
30x10x2x2x7x9,120 = 76.6M combinations; generator asserts exactly one survivor per station.
Visible data cannot confirm a non-headline branch (W5): shipped never fires one.
Interaction: SR1 must be solved jointly with SR2/SR3 (the fit is over every period's tariff).

SR2 unique fit (S3). Ambiguous period: every accepted paid invoice of the period has tugs 0,
so all three towage coefficients fit. p0.4 per station; every hidden corpus has >= 1;
shipped 0. Conventions are always unique (no zero-fit branch). Reflex H8: first fitting
tariff used and the period resolved.

SR3 notice (S6). p0.6 per station, notice dates 2026-07-31..2026-08-31, 1-2 coefficients
change; every hidden corpus has >= 1; shipped none in force. The second period is thin, so
per-period convention fitting leaves several choices; R13 (station-wide) settles it.

## 6. BRANCH_FIRE (see BRANCH_FIRE.md)
Shipped: SR1 0/4, SR2 0/4, SR3 0/4. Prototype hidden 1101-1104: SR1 16/16 stations,
SR2 7/16 stations (every corpus), SR3 8/16 (every corpus).

## 7. Rejection paths
malformed_record, duplicate_invoice (same id twice in a file or across paid and disputed:
every copy), unknown_visit, station_mismatch, early_invoice (invoice date before the release
date), already_paid (disputed invoice whose visit has an accepted paid invoice). First code
in that order wins. Rejected paid invoices are not fit evidence. Fatal: missing/unparseable
declared file.

## 8. Outputs
- summary.json: disputes, verdict_counts{billed_correctly, overbilled, underbilled,
  cannot_recompute}, refund_total, shortfall_total, unresolved[{station, period_start}],
  largest_refund{invoice_id, amount}|null.
- policy_audit.json: rows sorted by invoice_id: invoice_id, visit_id, station, period_start,
  segment, billed, recomputed|null, difference|null, verdict, reason|null.
- data_quality.json: rejected[{file, line, code}] sorted by file, line; counts per code.
- region_<S>.json: station, periods[{period_start, status, reason|null, tariff{base_rate,
  draft_rate, night_factor, per_tug}|null, paid_invoices}], verdict_counts, refund_total,
  shortfall_total.
- segment_<s>.json: segment, disputes, vessels, verdict_counts, billed_total,
  recomputed_total, refund_total, shortfall_total.
Conventions are not output (an output key per family would enumerate the families).

## 9. Test plan (G1-G13)
Embedded seeded generator in tests/ (seed only there), 4 hidden corpora, rare fixtures on
their own stream Random(seed*31+5) (G8); agent program run as uid 1000 from a foreign cwd
with exactly the stated command (G8a); 150 s cap per run stated in instruction.md.
| check | w | n | total |
|---|---|---|---|
| test_outputs_exist | 1 | 1 | 1 |
| test_shipped_regions / _audit / _totals / _quality | 3 | 4 | 12 |
| test_hidden_k_region_<S> (whole region file + that station's audit rows) | 5 | 16 | 80 |
| test_hidden_k_audit (rows of other stations masked by OWNED) | 5 | 4 | 20 |
| test_hidden_k_totals (summary + 2 segment files, one totals view) | 3 | 4 | 12 |
| test_hidden_k_quality | 3 | 4 | 12 |
| test_mutation_relocated (counted only where hidden_1 exact) | 3 | 1 | 3 |
| test_mutation_missing_source (hidden_2 minus paid_west.txt; non-zero exit, stderr names file; counted only where hidden_2 exact) | 3 | 1 | 3 |
Positive 143. Hidden 130/143 = 91%. Held-out w5 tier 100/143 = 70% (N2 >= 50%). Lever share
(hidden region+audit+totals) 112/143 = 78%. OWNED map gives every row one owner (G1a).
Exactness and rerun promise stated in instruction.md (G5, CL-4 FC:491). Negatives (cheating
acts only): reads /tests/ or /logs/verifier -5; ships a hard-coded copy of a shipped document
-3. One-fact-wrong (one audit row): audit 5 + region 5 + totals 3 = 13/143 = 9.1%.
Cost alone: SR1 118/143 = 82.5%; SR2 73/143 = 51%; SR3 78/143 = 54.5% (each >= 25%).
All-but-one finals (judge mid 40): SR1 wrong 29; SR2 wrong 44.5; SR3 wrong 43 (all < 70).

## 10. Judge plan (J1-J10)
8 probes w3 important/process/trajectory, each shown by a solve.sh self-check stage that
prints `check <id> ok` plus a witness line:
| id | template | requirement | expected Opus |
|---|---|---|---|
| P1 | P-g uniqueness witness: counts fitting convention choices for one station | circular s5 | no |
| P2 | P-a edge copy where one period's paid invoices all have no tugs; reason shown | circular s6 | no |
| P3 | P-a edge copy with a notice row; period split shown | circular s4 | no |
| P4 | P-d altered paid amount, rerun, region file changes | circular s5 | rare |
| P5 | P-c refund_total recomputed outside the program from policy_audit | contract | sometimes |
| P6 | P-e relocated rerun, outputs identical | invocation sentence | sometimes |
| P7 | P-h missing declared file run, message names it | contract fatal | sometimes |
| P8 | P-b one disputed invoice worked line by line | circular s2 | sometimes |
Non-probe: J4 w3 (exact LEVER_RULES wording on derive_report.py); J6 w5 (lists every
disputed invoice whose verdict is cannot_recompute, each by its id); J10 order w3.
Positive 35; probe share 24/35 = 69%. Negatives J3a -3, J3b -5 (final_answer), J3c -3.
Estimate: lower 9/35 = 26%, mid 14/35 = 40% (probe part 6/35 = 17%, <= 20), upper 22/35 = 63%.

## 11. Predictions and DESIGN READY bar
- Plain first-write (K1/K4 shape): shipped 13 + hidden quality 12 = 25/143 = 17.5% tests;
  final (17.5 + 40)/2 = 28.8 <= 35 (a).
- Lever share 78%, held-out w5 70% (b).
- Kill rows K1, K2, K4, K4w: 16/16 station units lost by WRONG; K4q (full marks, whole-hour
  windows) 13/16 lost (c, e).
- Verifier worst 7 runs x 150 s = 1,050 s (within 900-1,200 s, d); reference 0.4-0.6 s per
  prototype corpus, estimate <= 15 s per bundle corpus (<= 1/4 of 150 s).
- Risk: a solver that enumerates the full stated domain with decomposition equals the
  reference and is EXACT (tests 100, final about 70). The naive full product (76.6M x 180
  per station) is infeasible, so the careful agent must both read the ranges literally and
  decompose; the Phase 0b design blind must lose >= 40% of lever points.

## 12. Expected loss per lever
- SR1: every test_hidden_k_region_<S> whose station is non-headline (all 16), plus every
  test_hidden_k_audit and test_hidden_k_totals; mutations not counted.
- SR2: regions of stations with an ambiguous period (7/16) plus audit and totals of every
  corpus.
- SR3: regions of notice stations (8/16) plus audit and totals of every corpus.
- Judge: P1-P4 expected FAIL, P5-P8 25-50%.

## Lessons for the master
Stating a convention family as a numeric range beside its field invites a full loop; key the range from the definitions section instead | no change: applied here, blind read pending
