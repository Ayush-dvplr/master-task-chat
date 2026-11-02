# QC_DEFENCE (v2, IMPROVEMENT_PLAN C1)

## SR1 L-CONV per-station conventions
Rules touched: IN-15, IN-16, IN-17, AL-1, AL-27, TS-19, TS-20.
- IN-15 (rules of engagement stated in a readable file, 01:45): the six families are stated in
  their governing files (circular s2 assist, draft, surcharge hours, surcharge base;
  holidays.json header calendar and note on Mondays), their ranges in circular s1, the
  principle in circular s5. rule_register.md maps each topic to its file.
- IN-16 (one reading, three parts): each family sentence names the quantity, the unit and the
  station-set parameter with its range; the principle states that exactly one choice fits.
  A careful agent finds each family from the invoices alone (G-2): fit the six parameters
  inside the stated ranges against every accepted paid invoice; the generator plants
  invoices that kill every rival (UNIQUENESS.md), so the fit has one answer.
- AL-1 (deliverable property stated or settled by one determinate shipped fact, 05:21): the
  station's choice is settled by its paid invoices; EVIDENCE_MAP rows SR1 x 6 families.
  REBUT quote: 05:21 and FC:492, with EVIDENCE_MAP.md and UNIQUENESS.md.
- IN-17: no sentence announces a station's reading; the principle sentence states a rule
  (how conventions are fixed), not a finding. Default to keeping the sentence (playbook IN-17).
- AL-27 (rule graded only where test input constructs it): every family branch fires on the
  hidden corpora (BRANCH_FIRE.md); RULE_COVERAGE in Phase 4.
- TS-19 (hidden inputs inside stated bounds): generator asserts every mark in 1..30 / 1..10,
  every window time on a quarter hour, calendars from holidays.json only.
- TS-20: per-station region checks are core w5.
Fallback if QC flags IN-16 or AL-1: playbook row 4b (ship one determinate fact): add, in
  the station's paid file, one more planted invoice that kills the rival QC names, and an
  EVIDENCE_MAP row citing its line. If QC still flags: playbook row 5, state the missing
  family property once, neutrally, in its governing file (circular s2), never a station's
  reading and never beside the paid file field. NEVER: list the readings per station, add a
  worked example where readings differ, or move the rule to instruction.md.

## SR2 unique fit / unresolved period (S3)
Rules touched: IN-16, AL-27, TS-26, CL-4.
- Stated in circular s6: a period with more than one fitting listed tariff is unresolved;
  its disputed invoices are cannot_recompute with the stated reason. One reading.
- AL-27: ambiguous periods on every hidden corpus (generator assert), never shipped.
- TS-26: region checks read region_<S>.json; audit checks read policy_audit rows of other
  stations (OWNED masks); totals read summary and segments. Different observables.
Fallback: playbook AL-27 DO: add hidden reseeded rows inside bounds (more ambiguous
  periods); TS-26 DO: narrow each check to its OWNED rows. NEVER drop the check.

## SR3 notice period split (S6)
Rules touched: IN-15, IN-16, AL-27, TS-19.
- Stated in circular s4: a notice row opens a new period at 00:00 of its date; the boarding
  instant decides; coefficients not named carry across (s5).
- Hidden only; notice dates inside the review window (TS-19 assert).
Fallback: playbook AL-27 DO (more notice stations per hidden corpus); IN-16 DO: one
  settling clause in circular s4 for the general case.

## Cascade: COUPLING through whole documents (G1, G1a)
Rules touched: CL-4, TS-13, AL-28, TS-20.
- CL-4 (partial credit): REBUT with FC:491 "An instruction that states out loud that only an
  exact match counts has set that bar deliberately"; instruction.md states whole-document
  exactness and the rerun promise; one-fact-wrong score 13/143 = 9.1% reported.
- TS-13 (one property per check): each check owns one document view (region of one station,
  audit rows outside owned stations, totals view = summary + 2 segment files as one view,
  QC_RULINGS PASS "whole-doc per view per extract"). Fallback: split the totals check into
  summary and segment checks (TS-13 DO), weight unchanged.
- AL-28: negatives are cheating acts only (reads /tests/ or /logs/verifier -5; ships a
  hard-coded copy of a shipped document -3), each one layer; J3a/J3b/J3c on the judge side
  are distinct acts.

## Judge probes
Rules touched: JD-7, JD-15, JD-8.
- JD-7: every probe is shown by a solve.sh self-check stage printing `check <id> ok` and a
  witness line (QL 26 Oct: trajectory criterion allowed when the oracle shows it).
- JD-15: type process, target trajectory for probes; J3b final_answer; J4 code quality.
- JD-8: no probe reads a document a test grades (probes grade acts in the trajectory).
Fallback: JD-7 DO fix the oracle (add the stage); JD-15 DO relabel; JD-8 DO delete the
  overlapping criterion and renumber.

## Lessons for the master
Pairing each lever with its playbook DO row before Phase 1 keeps fixes off the NEVER column | no change: prompt already asks for it

## Blind 5456c27 lessons: items the full build must state or grade
| item | where to state it | how graded |
|---|---|---|
| shortfall sign: refund_total and shortfall_total are positive amounts; difference = billed - recomputed keeps its sign | output_contract.md Values | summary/region/segment whole-doc tests |
| segment `vessels` is the count of distinct vessels with an accepted disputed invoice | output_contract.md segment file | segment whole-doc tests |
| one unparseable line in paid_south.jsonl is malformed_record; only a missing or wholly unreadable file is fatal (state "a JSON file" means certificates.json / holidays.json) | output_contract.md Rejected records + Fatal inputs | data_quality tests + mutation missing_source |
| surcharge hours are pinned by the paid invoices (generator plants s-1, s, e-1, e); no loose-window rule needed, uniqueness sentence covers it | tariff_circular.md s5 (exactly one choice) | EVIDENCE_MAP fact, region tests |
| marks are at least 1 ("a whole number of minutes from 1"), and a certificate exempts only the vessel the register names it on (holder not compared, or state holder must match) | tariff_circular.md s2, exemption_policy.md | audit tests (hidden fixtures with holder mismatch if graded) |

## Blind 529e4de lessons (try 4): items a full build must state, vary or grade
| lesson | action for a full build |
|---|---|
| All shipped stations share one convention set, and it is the first in a natural enumeration | Vary: shipped stations would need different conventions; in Shape D that conflicts with the degenerate shipped instance, so record it as a design tension, not a fix |
| station_notices.md ships empty (two-period and unresolved paths never visible) | Vary/grade: ship at least one notice row, or keep it hidden-only (S6) and grade it on hidden corpora with the rule stated in circular s4 |
| 6 rejections per paid file, evenly over 4 codes | Vary: draw rejection counts and codes per file from the generator's own RNG stream |
| Section 6 is silent on exempt visits in unresolved periods (due 0 under any tariff) | State: one sentence in circular s6 deciding whether an exempt visit in an unresolved period is recomputed at 0.00 or cannot_recompute, plus a hidden fixture that grades it |
