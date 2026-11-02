# QC_DEFENCE 44635de pilotage-dues-reconstruction

Live rule text quoted from checks.json (qc_reverse/A). Fallbacks are QC_FIX_PLAYBOOK_v2 rows; none of
them softens a lever.

## LV-1 R-FIT unique fit and unresolved verdict
| rule | live text (quoted) | why it passes | fallback (playbook row: DO) |
|---|---|---|---|
| IN-15 | "A rule that is graded but appears in no file the agent can read costs the honest agent reward" | fit sentence, closed lists, the `cannot_recompute` clause and both reason strings are in tariff_circular.md "Recovering a tariff"/"Verdicts" and output_contract.md; rule_register.md names both files | IN-15: add the missing sentence to tariff_circular.md, never to instruction.md |
| IN-16 | "A finding without both readings written out is not usable" | readings: (a) first combination that fits, (b) the one combination; the clause "has no such combination, or has more than one" gives one reading: >= 2 fits is unresolved | IN-16: rewrite the one clause with "two or more" spelled out |
| IN-17 | no sentence announces what input establishes | circular states the rule; nothing says some station is ambiguous or that coefficients go unexercised | IN-17: delete the announcing clause |
| AL-1 | "Everything graded is promised." | instruction promises fresh data of the same layout, graded whole, exact match only; the unresolved branch is stated in the circular (degenerate shipped instance, LEVER_RULES 0b) | AL-1: add the promise sentence to instruction.md |
| AL-27 | "a rule only counts as graded when the test's input actually constructs the situation" | generator asserts on every hidden corpus one 2+-fit and one 0-fit station-period (BRANCH_FIRE) | AL-27: add the generator assert and plant |
| CL-4 | "Partial credit tracks partial correctness." | REBUT with FC:491 "An instruction that states out loud that only an exact match counts has set that bar deliberately"; documents split per family and corpus; one-fact-wrong score in COST_TABLE.md | CL-4: partition hidden checks by document family (already), never relax exactness |
| TS-13 | "A test asserting two unrelated properties hides which one failed" | one whole document (or one document family) per check | TS-13: split along document lines |
| TS-19 | "every promise made to the agent must be graded by something" | generator asserts every drawn value in stated bounds (closed lists, draft range, GT range, window) | TS-19: tighten generator asserts, never widen the contract silently |
| TS-20 | "a core-deliverable test carrying weight 1, or an existence/formatting check carrying 5, is wrong" | hidden summary/audit 5, regions/segments/mutations 3, existence and quality 1 | TS-20: reweight to 5/3/1 |
| TS-26 | "Two tests reading the same observable with the same decisive logic pay (or punish) one behaviour twice." | summary, audit, regions, segments, quality are different documents; per-row ownership in audit | TS-26/JD-14: merge the overlapping check and move its weight |
| AL-28 | "name the single concrete agent action that triggers it" | test negatives: program reads /tests (-5), program holds shipped answers (-3); judge negatives J3a/J3b/J3c, one act each | AL-28: one negative per act |
| JD-7 | "Every criterion must be satisfied ... by the shipped oracle" | solve.sh self-check prints `check P1 ok` (fit counts per station-period) and the two-fit/no-fit probe runs | JD-7: add the self-check stage line |
| JD-15 | what a criterion may require | probes are acts on the trajectory; no figure criteria, no absence positives | JD-15/16: relabel or drop the criterion |

## LV-2 R-CHANGE tariff change on the notice date
IN-15 (definitions sentence "every date rule in this circular reads the boarding instant" and the period
sentence "A notice starts a new period at 00:00 on its notice date" in tariff_circular.md; notices data in
station_notices.md, named in rule_register.md), IN-16 (readings: invoice date / strict after / release
instant vs boarding instant on or after 00:00; the definition sentence settles all three), IN-17 (no
"some visits straddle" sentence), AL-27 (each hidden corpus plants notice-day, eve-23:xx and
invoiced-after visits; asserted), W6 one toy example on an invented station and date. Fallback: IN-16 row,
rewrite the sentence with "on or after 00:00 of the notice date"; AL-27 add the plant.

## LV-3 R-EXEMPT partial visit ending at midnight
IN-15 (exemption_policy.md: "A certificate covers on-board time before 00:00 on its expiry date"; pro-rata
per rounded line, half-even again; wholly-covered visit due 0.00), IN-16 (readings: expiry day inclusive /
all-or-nothing by boarding / pro-rata of the total vs per line; text names each step once), AL-27 (own RNG
stream plants across-midnight, on-expiry-day and ending-before visits per hidden corpus; asserted),
DS-25 (`billed_minutes`, `onboard_minutes`, `exempt_minutes` in output_contract.md). Fallback: IN-16 row,
rewrite the one sentence; AL-27 add the plant.

## Cascade (COUPLING G1)
"Every recomputed due and every verdict uses the tariff recovered for that station and period, or the
station's unresolved status." A wrong fit or period or exemption fails summary, audit, regions and
segments of the same corpus. Rules: CL-4 (REBUT, FC:491), TS-26 (each document a different observable),
AL-28 (cascade is positive checks failing, never stacked penalties). Fallback: CL-4 row, partition by
document family; never drop exactness.

## Other gates touched
DS-4/W11 (no answers in environment/: no tariff table, no verdict list, no totals), DS-24/TS-S13 (solve.py
vs test_output.py overlap < 20%), DS-25 (every key, code, reason and the fatal message form in
output_contract.md), DS-27 (TRUTH narration; OPEN CONFLICT Q18 if VB 15.5 disagrees), JD-12 (8 to 35
criteria, sum of negatives <= positives), TS-23 (31 checks, under 35), validator 7.4
(`negative_hardcoded_sample_answers` present with negative weight).

## v2 rows (redesign after the blind read)
| rule | live text (quoted) | why it passes | fallback (playbook row: DO) |
|---|---|---|---|
| IN-15 | "A rule that is graded but appears in no file the agent can read costs the honest agent reward" | joint tariff sentence in circular section 5; notice sentence in station_notices.md, named as governing in rule_register.md; allowance and draw order in exemption_policy.md | IN-15: add the sentence to its governing file, never to instruction.md |
| IN-16 | "A finding without both readings written out is not usable" | LV-1/LV-2 readings: (a) each period fitted alone, (b) one value per unnamed coefficient over both periods; "gives new values only to the coefficients its row names" picks (b). LV-3 readings: (a) per vessel, (b) per certificate over all its vessels; "up to its allowance_minutes in total" and "the vessels registered under it" pick (b) | IN-16: add "over both periods" / "over all its vessels" to the one sentence |
| IN-17 | no sentence announces what input establishes | no sentence says a period may stay open, that a notice may leave coefficients unchanged on purpose, or that certificates are shared | IN-17: delete the announcing clause |
| AL-27 | "a rule only counts as graded when the test's input actually constructs the situation" | generator asserts per hidden seed the Y1/Y2/Z/W joint counts, >= 2 shared certificates with exhausted allowance, >= 2 uninvoiced draws | AL-27: add the plant and the assert |
| TS-19 | "every promise made to the agent must be graded by something" | certificates.json values asserted in bounds (allowance 60..6000, expiry within 2026-05-01..2027-01-01) | TS-19: tighten asserts |
| JD-7 | "Every criterion must be satisfied ... by the shipped oracle" | solve.sh self-check prints per-period and joint candidate counts (P1, P7) and one certificate's draw list (P8) | JD-7: add the stage line |

## Lessons for the master
- validator 7.4 needs `negative_hardcoded_sample_answers`; add it to the DESIGN test plan up front | no change: recorded in sibling QC_DEFENCE already
