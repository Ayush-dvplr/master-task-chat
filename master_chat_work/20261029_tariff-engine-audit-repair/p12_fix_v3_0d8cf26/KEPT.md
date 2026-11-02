# KEPT — tariff-engine-audit-repair (P12 0d8cf26, for QC recheck of v3 / a4ffe55)

| finding id | file:line | reason | kit line it rests on |
|---|---|---|---|
| TS-20 | tests/test_output.py:8576-8784 (batch/cycle check bodies), :8911-8952 (registrations) | 369/670 on `--statements` (shipped 5 + 4 hidden sets x 7 x 13) is the approved lever weight (Ayush 29 Oct 09:12 "C. Raise the limit for tariff only.: okay", CRASH+TIMEOUT cap 60%). Ordering is right: whole-document due/redeemed w5, feasible w3; QC v3:142 "Not an ordering contradiction". Dropping batch/cycle or weight 1 cuts 182 lever points (HARDEN_REPORT kill table: agent_program loses all 364 lever points). | Input_Bundle_QC 03_Tests_QC.md:51 ("Mild imbalance within the right ordering is a minor"); QC_FIX_PLAYBOOK_v3 TS-20 NEVER "lowering a lever check" |
| TS-26 | tests/test_output.py:7548 `_SCALE_RNG` (53,29)/(61,37)/(67,41); registrations :8911-8952 | statement / batch / cycle grade three different seeded hidden documents (different 36-voucher accounts and tie positions per corpus); QC v3:144 "Different inputs, so not the kit's strict 'same observable' duplicate (03:53)". | 03_Tests_QC.md:53 ("What is NOT a duplicate ..."); QC_RULINGS TS-26 cohort v2:183, district-heat v3:185 PASS |
| DS-21 (F08, carried) | environment/ci/api_contract.md:25-28 | unchanged from previous KEPT (QC/reports/tariff-engine-audit-repair/KEPT.md F08). | 02_Data_Solution_QC.md:70, :107 |
| TS-23 / A3 (F09, carried) | tests/test_output.py:8797-8954 (158 registrations) | unchanged from previous KEPT F09; count needed by the lever (7 corpora x 4 sets x 3 fields). | 03_Tests_QC.md:62 ("at least 10 checks (fail), at most 35 (warn)") |

Line numbers are after the TS-11 lock (+12 lines above :5589); QC v3 cited the same code at 8563-8772 / 8899-8940.

## Lessons for the master
- none new | no change: both keeps rest on QC v3's own wording (v3:142, v3:144).
