# TEST_DEPTH (board 840adf9, 24 Oct 2026)

Scratch: `/tmp/test_depth-20261024T2141` (copies hashed in `INPUTS.md`). Method and every run: `LOG.md`. All programs ran inside each task's verifier image (`td840-<slug>-verifier`, python 3.12), as `nobody`, `--network none`. No harbor run, no model call.

## Method in one paragraph
P0: the real `tests/test.sh` (rewardkit, judge stripped) with the agent program in place reproduced every run's test score (match-replay 75/160, the other five 100%), oracle 100% on all six. P1: each driver (`W/fz/fz_<task>.py`) imports the task's own `tests/test_output.py` and drives its hidden-tier generator and reference (`replay_plan`/`expected_reports`, `gen_month`/`ref_compute`, `build_variant`/`reference_documents`, `_corpus`/`_Ledger`, `gen_corpus`/`ref_compute`, `build_all`/`compute`), adds edge mutations (P2) and structural changes (P3), runs agent and oracle on every corpus and diffs every graded document at every path, type-strict exact (the tests' tolerance). Corpora the generator or contract bounds reject are dropped and counted (OUT OF BOUNDS / generator reject).

## Table

| task | valid corpora (P1/P2/P3) | % agent differing P1 / P2 / P3 | classes G / A / OW | tests % with new families | overall at measured judge | gate (tests<100, overall<70) |
|---|---|---|---|---|---|---|
| control match-replay | 306 (148/75/83) | 51.4 / 22.7 / 43.4 | 2 / 0 / 0 (both known, already tested) | 46.9 (75/160, unchanged) | UNVERIFIED (judge not re-measured) | already met (tests<100) |
| metered | 303 (131/107/65) | 0 / 0 / 0 | 0 / 0 / 0 | 100 (no family possible) | 87.5 (judge 21/28) | NO |
| sentinel | 310 (150/100/60) | 0 / 0 / 0 | 0 / 0 / 0 | 100 | 71.62 (16/37) | NO |
| tariff | 334 (157/105/72) | 0 / 0 / 0 | 0 / 0 / 0 | 100 | 81.25 (15/24) | NO |
| config | 322 (149/108/65) | 0 / 0 / 0 | 0 / 0 / 0 | 100 | 94.64 (25/28) | NO |
| caldermoor | 314 (150/100/64) | 0 / 9.0 / 0 | 1 / 1 / 0 | 95.29 (162/170) owned rows; 74.12 (126/170) whole documents | 49.92 owned; 39.33 whole (judge 1/22) | YES |

Overall = 0.5 x tests + 0.5 x judge share (reward.toml weights 0.5/N each layer). Oracle differed on 0 of 1889 valid corpora.

### Difference classes (smallest input each)
- **Control R (runtime, known slip a)**: 84 corpora exit -9 'ran past 120 seconds', every single-bit trap-only corpus (bits 0x1..0x800); smallest `P1-023` (`('only',0x100)`, seed 884346, 207 entries). Solo rerun with 2 cpus: still -9 at 120.1 s (`fz/mr_solo_out.jsonl`), so not contention. Agent `optimize.py:795-830` keeps every surviving branch.
- **Control S (settlement, known slip b)**: 45 corpora exit 1 `calibration failed at CTRL-J (cadence_modulus)`; smallest `P1-124` (`('class','steady')`, seed 475709, 209 entries). Same failure as `PROBE_DIAGNOSIS.md`. **control_found_known_slips = true.**
- **CM-B GENUINE (caldermoor second-pass allocation)**: 2 corpora (P2-022, P2-072), code 0, 9-10 artifacts differ. Shrunk: one principal-month (2032-09, ACT-0013), envelope 30, reserve 0, open efforts CMT-01276=20, CMT-01686=15. First pass 17/13, CMT-01686 drops below 15; survivor gets 30 in the reference, 20 from the agent. Contract `commitment-protocol.md:207-209`: "A commitment whose share then falls below fifteen minutes receives zero, and the whole of the distributable minutes is distributed again by the same rule across only the commitments that held fifteen or more." The agent's second pass (`reconcile.py:663-677`, via `largest_remainder` L646-648) re-enters the at-or-below branch of L201-202 ("each commitment receives its own clamped effort and the rest is left undistributed"), which contradicts "the whole of the distributable minutes is distributed". Reference: `tests/test_output.py:3020-3031`. Note: "by the same rule" is the only hook for the agent's reading; I rule it GENUINE because "the whole" fixes the amount (judgement, listed in unverified).
- **CM-A AMBIGUOUS (caldermoor malformed budget line)**: 7 corpora (all with a blank or short line in `budget_overrides.psv`); agent crashes `KeyError: 'monthly_minutes'` at `reconcile.py:1243`; reference skips the line (`tests/test_output.py:2263-2280`). `record-layouts.md:7-10` makes such a line `MALFORMED_ROW` but no sentence says what a malformed line in a reference table (attention_budget / budget_overrides) does (skip, or reject the pair, or zero envelope). The crash is wrong under any reading but the expected output is not pinned, so a test would be an IN-16 fail. Probe `fz/cm_probe.py malformed`: blank -> agent exit 1, short row -> exit 1, long row -> exit 0; oracle exit 0 in all three.
- No ORACLE WRONG class. The test reference itself crashes on contract-valid integer `standing_charge` in tariff (`tests/test_output.py:5526`, 18 corpora; there agent was compared with oracle, 0 diffs) and the metered generator loops forever in `_gen_rate` (`tests/test_output.py:341-348`) for about 45% of fresh seeds. Both are latent test defects that today's hidden seeds avoid.

## Existing levers (tasks 1-5): 17 REVEALING, 0 SILENT-RIGHT

| task | lever | rule (file:line) | agent code | read at | verdict |
|---|---|---|---|---|---|
| metered | MU-1 north units JSON int | rating_contract.md:62-66 enumerates the malformed values, :75-76 carve-out "except north" | transform.py:167 | steps 10-16 (DIAGNOSIS) | REVEALING |
| metered | MU-2 Decimal half-even per line | :149-152 | transform.py:434 | steps 44-45 | REVEALING |
| metered | MU-3 credit base at line timestamp | glossary :22-24, :156-158 | transform.py:446-458 | step 16 | REVEALING |
| metered | MU-4 canonical id | global :83-84 | transform.py:52-53 | step 40 | REVEALING |
| sentinel | L3 allowance across principals | override_deltas.json conventions "whichever principal they name" | cli.py:309-320 | step 14, self-test 47-50 | REVEALING |
| sentinel | L2 rev-1 seconds | conventions line 6 | cli.py:269-272 | steps 14, 27 | REVEALING |
| sentinel | L7 per-term rounding | risk_weight_rounding.txt:2-3 | cli.py:349-352 | step 9 | REVEALING |
| tariff | TR-4 quantity JSON int | api_contract.md:56 + enumeration :77-79 | parser.py:18-25 | steps 4, 22 | REVEALING |
| tariff | TR-3 month = billing period | glossary :43-44, :108-109 | report.py:70 | step 4 | REVEALING |
| tariff | TR-2 line half-even | :42 + :117-119 | core.py:7-9, 37 | steps 4, 25 | REVEALING |
| tariff | TR-2 credit rounding | :121-125 | core.py:49-62 | steps 4, 25 | REVEALING |
| config | CC-1 owner retired by log | config_contract.md:38-40 + :63-65 | resolve.py:4-12, loaders.py:145-148 | steps 6, 15 | REVEALING |
| config | CC-2 JSON keeps type | :92-93 + enumeration :104-106 | resolve.py:40-55 | steps 6, 20 | REVEALING |
| config | CC-4 canonical ids in log | global :28 | loaders.py:36-38, 141 | steps 15-16 | REVEALING |
| caldermoor | A blocked | dependency-semantics.md:50-51 | reconcile.py:1026-1031 | step 6 | REVEALING |
| caldermoor | B periods_waived | cadence-register.md:58-67 | reconcile.py:1186-1199 | steps 6, 29 | REVEALING |
| caldermoor | C allowance per principal | cadence-register.md:49-54 | reconcile.py:29, 1162-1180 | steps 6, 29 | REVEALING |

Amplifiers (sentinel L1, tariff TR-1) and couplings (config quota, caldermoor reserve) have no wrong reading of their own and are not counted. Every REVEALING row matches a LEVER_RULES_v1 1b trip condition that the bundle broke: an enumeration of malformed values (LEVER_RULES_v1.md:37), a rounding step at the point of use (:38), a scope equal to a per-line field (:39), a global Identifiers section (:40), or a sentence naming its separating case (:42).

## H1 verdict: PARTLY
GENUINE classes on contract-valid inputs in 1 of tasks 1-5 (caldermoor: 2 of 314 corpora, 9% of P2). Tasks 1-4: 0 differing corpora in 1269 valid corpora, including edge-dense and structural profiles. So deeper tests catch a slip only in caldermoor. In the other four the final program matches the oracle everywhere the generators and contract bounds reach. The control shows the method finds slips (both known slips, 129 corpora).

## H2 verdict: revealing (17 REVEALING vs 1 AMBIGUOUS)
The real problem is that the instructions are too loud. All 17 levers trace to a contract sentence that enumerates or names its separating case, and the agent turned each one into a code line right after reading it. Its program then agreed with the oracle on 1269 corpora built to break it. Looseness shows up only once (CM-A), on a reference-table path that is not a lever.

## Recommendations (at most 6)
1. `LEVER_RULES_v1.md:37` (rows metered, tariff, config): make the enumeration ban a precheck. Fail the build when the contract lists the rejected values of a lever field (rating_contract.md:62-66, api_contract.md:77-79, config_contract.md:104-106 all did, and all three levers held 0%).
2. `LEVER_RULES_v1.md:41` (row caldermoor): add H7 "re-entry branch" to the 1b bank. A second pass "by the same rule" that must not take the first rule's early-exit branch is the only habit Opus missed in 1889 corpora (CM-B).
3. `LEVER_RULES_v1.md:71` G12 (row caldermoor): the hidden generator must plant every branch of each multi-branch rule. Today no seed produces "survivors' effort below the distributable minutes", so 162/162 passed while 9% of edge corpora differ. Use `W/fam/cm_family.py` `_add_survivor_envelopes` as the template.
4. `LEVER_RULES_v1.md:24` never-used list (row caldermoor, CM-A): add "a malformed line in a reference or lookup table with no stated outcome". `record-layouts.md:7-10` needs one sentence on what a malformed `attention_budget.csv`/`budget_overrides.psv` line does before any test may touch it.
5. `LEVER_RULES_v1.md:69` G10 (all rows): add a differential-fuzz gate. Run the last real agent program against the oracle on at least 300 generator corpora (this board's drivers). A lever whose run shows 0% differing is recorded as REVEALING and replaced, not kept as `held`.
6. `LEVER_RULES_v1.md:60` G1 (row caldermoor): owned-row families cost 8 points per GENUINE slip (95.29%). Whole documents would cost 44 points (74.12%) for the same slip, so the CL-4 rule keeps the owned-row score as the honest measure. Also fuzz the reference over contract bounds: the tariff reference crashes on integer `standing_charge` (`tests/test_output.py:5526`) and the metered `_gen_rate` loops forever (`tests/test_output.py:341-348`).

## Gate candidate
**caldermoor-commitment-closure** passes the gate with only new hidden families (no new lever). Add `allocation_survivor_redistribution_exact` (w3) and `_hard` (w5) owning `attention_allocation.csv` and `month_load_index.csv` rows on a survivor fixture. Expected tests 95.29% (162/170) and overall 49.92 at the measured judge 1/22. Oracle stays at 100% on the scratch copy (`p3/fam/.../oracle/logs/reward.json` 0.5 = full tests share). No other task has a GENUINE class, so new families alone cannot move them below 100.
