# C card: restoration-cadence-settlement

Base `T=.../Perfect_for_Delivery/Dinshi_Jain/restoration-cadence-settlement`. QC report `Kunwar_Singh_restoration-cadence-settlement_QC_Report.md` (WARN).

## 1 Scores and verdict
- Recorded overall 53.38, tests 25.62, rubric 81.13. QC re-grade: 31 of 124 = 0.2500 against the recorded 31 of 121 (QC :56); the H6 flag was a false positive (QC :41/:57).
- Verdict **GENUINE** (A file). Lost 90/121 recorded (93/124 re-graded). One stage error (cadence conversion) breaks every check that touches converted figures, including all 11 generalisation checks. This is a natural cascade, not a separate gate.

## 2 Inventory
- Domain: film restoration lab, frame cadence conversion, defect clipping, impairment, repair ceilings, programme settlement, vault admission and seating. Archetype: **constant recovery** (three unwritten conventions fitted from a calibration page) + reusable settlement program run on 13 mutated catalogues.
- Data: 6 rulebooks (allocation, cadence, conform, defect, identity, repair), invariants.md, delivery_schedule.md 11.8 KB, calibration_slice.md, a calibration_* mirror of every data file, example_vault_report.json.
- Instruction 697 words.
- Tests (stacking_check, current): 34 checks, positive 124, negatives -10 (4). Judge 21 criteria, positive 57, batched. Reward = (tests + rubric)/2.
- Shares: stacking reports isolated 99.2% / mutation 0%, but by reading the code the 11 `generalises_*` checks (55/124 = 44.4%, QC :52) run the program on mutated catalogues, so the real mutation share is 44%.

## 3 Test architecture
- Expected values: **reference implementation inside the test file** (quantise 62, canonicalise 109, usable_spans 177, conform 226, governing 294, impairment 331, repairs_applied 374, band_of 451, compose 464-484, settle_programmes 487, admit 537, seat 594, settle 685, build_reports 724). True conventions `TRUE_ROUNDING half_even`, `TRUE_ORDER (impair, cadence, credit)`, `TRUE_DECAY (3,5)` (:23-25); candidate sets ROUNDINGS 4, ORDERS 6, DECAYS 8 (:27-36) – not shipped.
- Catalogue embedded `CATALOGUE_ARCHIVE` 1076, `_materialise_catalogue` 1296.
- Mutation tier: `_write_corpus` 1455 copies every file then overwrites the mutated ones; calibration files are not mutated (docstring: punishing a program for reading what it was told to read). 13 mutators (1670-1917), each targets one rule (tie configuration, value across a cap, precedence inverted, group emptied, cycle introduced, temporal boundary, entity added, non-applying rule, print governs, prefix binding, counterfactual boundary, partition count, every void reason). `_generalises` 1626 compares all core reports + partitions (whole set).
- Isolated stage checks on the shipped catalogue via `_agrees` per key (1442), e.g. `cadence_converted` 2203 also asserts at least 3 programmes diverge from source.
- Sandbox `_privilege_drop_prefix` 1495, `_grant_access` 1515, `_run_program` 1560 (300 s, killpg).
- Negatives: hardcoded -5 (2595), filename -3 (2617, takes two same-path runs first, QC W3 fix), nondeterministic -1 (2665), catalogue_modified -1 (2692). Cheat acts only.

## 4 Lever table (failed checks)
Root rule: conversion of each addend is quantised half-even after impair, with the conversion in the middle (impair, cadence, credit) and carry 3/5 (test :23-25).

| id | w | locations (quotes) | form | agent reading | why self-test missed | fully stated? | nearest |
|---|---|---|---|---|---|---|---|
| cadence_converted | 5 | rulebook_cadence.md:30-31 "the converted count is quantised to a whole frame under the lab's standing quantisation convention. That convention is not written down here"; :71-72 order "is not written down here ... quantisation does not commute, so the order is recoverable"; calibration_slice.md "Exactly one combination of the three reproduces every figure on this page" | **constant withheld, recoverable by fit; candidate space unstated** | cadence_settle.py:9-15 quantise "toward the count it was converted from", impair+credit first, conversion last, carry 3/5 | step 24 "FULL MATCH ... total 30115": its out-of-candidate model reproduced every calibration figure; step 29 replay byte-identical to example_vault_report | Stated that a convention exists and that one combination fits; the space it ranges over is not stated, and the agent's model fits too | L1 green control wrong answer; NEW: calibration unique only inside an unstated candidate set |
| settled_frames_fixed, admission_settled, vaults_seated, cascade_and_ledger_closed, governing_element_excludes_print, admission_closes_as_a_prefix | 5 each | downstream stages | cascade (converted counts feed all) | same | same | cascade | cascade |
| generalises_* (11) | 5 each | `_generalises` whole-report equality on mutated catalogues | cascade, no partial credit inside (QC W3) | same | same | cascade | G1 amplification by whole-set compare |

Carry 3/5 was right (agent step 24 matched f=3/5); the wrong part is the quantisation rule and the order.

## 5 How tests handle QC
- TS-13 ✅ after M1 (QC :34): `cascade_and_ledger_closed` split into w5 + w3.
- TS-16 ✅ after W3 (QC :38): filename negative now first checks same-path determinism so nondeterminism is priced once.
- TS-19 ✅ (QC :182). TS-20 ✅ (QC :183): six w1 presence/format checks.
- TS-26 ✅ after F4 (QC :33): two generalisation mutators had collapsed to the same logic; F3 repair separated them. Stacking still groups them (same observable), by hand each uses a different catalogue.
- IN-15 ✅ / IN-16 ✅ (QC :124-125). Risky per our rulings: the candidate space for the unwritten conventions is not stated, so two "fits" exist (the agent's and the reference); QC treated "exactly one combination reproduces" as settling it.
- AL-28 ✅ (QC :98, single-member groups); stacking flags catalogue_modified + R19 as unmatched 6, by hand distinct acts.
- CL-4 ✅ with warn W3 (QC :52): 44.4% of tests have no partial credit; "a correct engine with only the repair ceiling carry wrong scores 30 of 124"; QC :86 one-fact-wrong 104/124. Accepted because the 11 checks key off 11 catalogues (AL-27).
- JD-7 ✅ after M4 (QC :37).

## 6 Leak avoidance
- W1/W3: rulebook_cadence.md:30-31 and :71-72 say the convention "is not written down here" – names the gap, never the value or the candidates.
- W7 honest control: calibration_slice.md publishes figures and claims uniqueness. It is honest within the authors' candidate set, but the agent found a model outside it that also fits (a control green under a wrong reading).
- Mutation tier keeps calibration files fixed, so the agent cannot learn the conventions from mutated data.
- Expected values from reference code in hidden tests; candidate lists only in tests.
- LEAK_LIBRARY: avoids "trap spelled out"; uses the "calibration page" pattern similar to vendor rows, but no shipped boundary rows let the agent watch the quantisation fire per addend.

## 7 Agent behaviour
- Read every file in steps 2-11 (first 30 s); 13-minute think gap (step 12, 10:56:14).
- Calibration fitting cal.py..cal6.py steps 13-24 ("FULL MATCH" at 11:02:52, minute 20). Program at step 25 (11:07:23, minute 25).
- Self-tests: byte-identical calibration replay (29), verify.py 0 errors (36), sensitivity test (39) showed "toward" vs floor differ, synthetic catalogue (50).
- Graded logic not changed after step 25 (INFERRED).
- Final claim (step 52): "truncating the *change* is the only convention that reproduces all" – false outside its own model space.

## 8 Passed checks
- Identity resolution, usable spans, shot conformance, defect clipping, impairment, repair adjudication, condition grades, serialisation: all upstream of or independent from the cadence conversion; their rules are written plainly in rulebooks.

## 9 Take-aways
- SAFE adopt: mutation tier with one mutator per rule and calibration files held fixed.
- RISKY (very strong): unwritten convention + "exactly one combination fits" without stating the space; Opus found a different fitting model. Close to our L1 but relies on an unstated candidate set (IN-16 risk).
- Avoid: whole-set equality in every generalisation check (44% with no internal partial credit); pass a report subset per mutator instead.
