# 6cd567a P12 v3 r2: recheck and fix of QC v6 (board c2cde12), dispatch-plan-reoptimization

Tree sha at issue `cc3a0ebba1cb` (verified at start). Live kit HEAD 71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e. Rule lines from the live kit (`Input_Bundle_QC/`), cross checked against `qc_reverse/A/checks.json`.
Levers (WORK/LEVERS.md): LV-DPR-01 lot tie, LV-DPR-02 setup fallback, LV-DPR-03 amendment dedupe, LV-DPR-04 rejection/void accounting, LV-EF-L7/V0-18 shipped K13 tie. V0-01..V0-17 are LEAKED and not graded as levers.
Noise check: every flagged line below is also present in the 2966bb2 copy (`QC/copies/2966bb2/...`: handbook and glossary identical; solve.py:486/:643/:697 same `active` tests; TRUTH.md:150 "four optimality checks"; test_output.py:18225 counts only `write_outside`; judge.toml:85 `agent behavior`). None is noise from r1; all persisted.

## Phase 1 recheck

| ID | Label | Rule quote (live kit) | Evidence quote (bundle) | Decision | Playbook row | Effect per lever (01/02/03/04/L7) | Files changed |
|---|---|---|---|---|---|---|---|
| F1 DS-20 | REAL | 02_Data_Solution_QC.md:68 "The oracle obeys the contract, independently of the tests. ... including rules no test exercises." | handbook_ops_v9.md:80-82 "An item whose live status in the item status register is `retired` is out of scope"; :331-332 "a demand row whose item is retired is rejected as `retired_item`"; solve.py:507 `elif item_status[code] != "active":`, :664 `if v == "active"`, :718 `item_status.get(code) != "active"`. item_registry.xml has 3 `proposed` rows (K31/K44/K57, seq 8340, above cutoff, so never live); live statuses in every set are only `active` and `retired`, so the rule never fires on data | FIX on the solve.py side (deviation, see below): oracle treats only a live `retired` status as out of scope, exactly as the handbook says; prove shipped and H1-H4 outputs byte-identical | DS-20 DO "Fix the oracle"; NEVER "Changing the contract to match the oracle" | none/none/none/none/none (outputs byte-identical) | solution/solve.py, WORK/build/oracle.py |
| F2 DS-22 | REAL | 02_Data_Solution_QC.md:78 "TRUTH.md describes the bundle that actually shipped." | TRUTH.md:147-148 "the four optimality checks"; shipped optimality_certificate.json carries five check keys (handbook :296-299 "Each of the five check keys"); handbook :209 itself counts "four checks" (lot sizing check = two keys) | FIX: TRUTH names both counts so it matches the artifact and the handbook: "the four optimality checks in five check keys" (see Deviations); recount TRUTH counts, digest last | DS-22 DO: correct TRUTH to the shipped bundle | none x5 | solution/TRUTH.md |
| F3 JD-8 | REAL | 04_Judge_QC.md:77 "NO OVERLAP WITH TESTS. ... Same observable = overlap = fail" | judge.toml:147 R11 "The agent's solver.py applies every rejection reason before it decides that a row is out of scope."; a scope-first solver changes data_quality.json out_of_scope_rows/rejected_rows, graded by shipped_artifacts_match_contract (w1) and hidden_h1..h4_quality (w3 each) | FIX: delete R11; keep R12 (trajectory, agent checks one row) and renumber it R11, because the live kit judge_qc J2 fails on a gap ("R12: ids must be sequential R1, R2, ...; expected 'R11', got 'R12'"); reward.toml judge 0.5/16 = 0.03125 | JD-8 DO: delete the criterion the tests settle | none/none/none/none (tests channel unchanged; judge duplicate of LV-DPR-04 removed)/none | tests/judge.toml, tests/reward.toml, TRUTH.md, QC_DEFENCE.md, XREF.md, LEVERS.md |
| F4 AL-27 | REAL | 05_Alignment_Integrity_QC.md:27 "Trigger depth: a rule only counts as graded when the test's input actually constructs the situation where the rule matters." | handbook :36-38 "take the log entries at or below the cutoff"; :32-34 "its own `void` field is 0, and the row lifecycle log does not leave it voided"; :70-71 "Rounding is half up, away from zero"; QC mutants M10, M11, M16 each 101/101; local before scores here M10 101, M11 101, M16 101 | FIX: hidden fixtures in mkhidden.py: (a) log void above cutoff on a live demand row (H1, H3), (b) own void=1 demand row with later log restore (H2, H4), (c) energy index row whose total bps is negative and lands an uplift on an exact negative half (H2, H3, H4 spread); regenerate goldens | AL-27 DO: add hidden reseeded rows that construct the case inside stated bounds; NEVER shipped data | none/none/none/harder (void lifecycle)/none | WORK/build/mkhidden.py, tests/test_output.py |
| M1 JD-15/JD-16 | REAL | 04_Judge_QC.md:92-93 constraint criterion quotes its stated sentence and carries the matching type | judge.toml:79 R6 "computes every money amount with integer arithmetic on cents", :85 `type = "agent behavior"`; source is instruction.md:9 "All money is integer United States cents." | FIX: type -> `instruction following`, add `# instruction.md:9: "All money is integer United States cents."` | JD-15 DO relabel with quoted sentence | none x5 | tests/judge.toml |
| W1 X1 | FALSE_POSITIVE (kept) | structure_qc.py:71 "X1  no em/en dash in any text file; binary-skipped files warn." | five binary data files (docx, xlsx, sqlite, pdf, db) cannot be text scanned; they are deliberate input formats | KEEP, PL_NOTE.md | X1 warn on binaries is informational | none x5 | none |
| W2 IN-16 | REAL | 01_Instruction_QC.md:46 "No significant ambiguity in anything that is graded" | handbook :26-28 "never counted as rejected" vs :330-335 rejection reasons first, then out_of_scope counts rows "that survive rejection" | FIX: :27-28 "never counted as rejected because of the cutoff; the section 14 rejection reasons are applied first"; same non-empty line count so every output stays byte-identical | IN-16 DO: settling clause where the conflict sits | none/none/none/none (rule already at :330-335; R12 still reads the retired-above-cutoff check)/none | environment/data/handbook_ops_v9.md, tests/test_output.py (_SHIPPED_DATA only) |
| W3 TS-16 | REAL | 03_Tests_QC.md:47 "Anti-cheat negatives must fire on the cheat and ONLY on the cheat." | test_output.py:40 wrapper records `write_input`; :18221 `return any(e["kind"] == "write_outside" for e in events)` so a write into the input dir never fires; before: ts16_cheat_input 101/101, no trigger | FIX: count `e["kind"] in ("write_outside", "write_input")` in mktests.py and test_output.py:18371; judge R8 carved to "by any means other than running its solver.py" so one solver write into /app/data is penalised once (AL-28, see Side effects) | TS-16 DO: point the negative where the cheat lands | none x5 | WORK/build/mktests.py, tests/test_output.py, tests/judge.toml (R8), TRUTH.md |

QC_RULINGS rows used: DS-22 :94 (fix the bundle, not the reading), AL-27 :115-116 (add hidden triggering rows; hardens), JD-15 :96/:107 (relabel as instruction following), IN-16 :19/:26, TS-16 :12. QC_DEFENCE.md had no row for F1, F2, F4 (a,b,c), M1, W3; R11 row :70-71 is retired by F3.

## AL-27 mutants (local scorer, tests channel, of P = 101)

Mutants rebuilt in WORK/wrong/ by `mk_al27.py` from the oracle (one change each). Fixtures added as section C5 of WORK/build/mkhidden.py; goldens regenerated with the oracle (= solution/solve.py SOLVER).

| Mutant | Change | Before | After | Loss | Groups that now fail |
|---|---|---|---|---|---|
| M10 m10_logabove | applies log entries above the cutoff | 101 | 53 | 48 | h1, h3: coefficients, quality, plan, sourcing, totals, certificate |
| M11 m11_restorevoid | a log restore revives a row whose own `void` is 1 | 101 | 53 | 48 | h2, h4: same six groups |
| M16 m16_neghalf | negative halves rounded toward +inf | 101 | 79 | 22 | h2_coefficients, h3_coefficients, h4 coefficients/plan/totals/certificate |

Fixtures (inside stated bounds, hidden only, no shipped data touched): H1 K08 P04 and H3 K10 P14 live demand row with a log `void` at seq 8150 (> cutoff 8140); H2 K24 P18 and H4 K03 P01 demand row with own `void` 1 and a log `restore` at seq 8130; negative energy rows (rev 9, seq 8100) with total bps H2 P03 -40, H3 P22 -40, H4 P01 -45 so an uplift lands on an exact negative half (e.g. H2 K22 value 5375 x -40 / 10000 = -21.5 -> -22). Handbook section 7 places no sign bound on `index_bps`, and :70-71 states half up away from zero, so (c) arises from an allowed data shape; nothing kept for PL_NOTE. Lot ties still two per set (built after C5).

## Judge paper scores (after R11 deletion and renumber)

Positive judge weight 16 (R1 5, R2-R5 1 each, R6 1, R9 3, R11 [old R12] 3); negatives R7 -5, R8 -3, R10 -3. reward.toml judge = 0.5/16 = 0.03125; tests 0.5/101.

| Run | Tests | Rubric before (of 19) | Rubric new (of 16) | Overall before | Overall new |
|---|---|---|---|---|---|
| a2 (traj_a2) | 67.33 | 52.63 | 62.50 (passes R1-R6; fails R9, R11 [no step checks one retired row above cutoff]) | 59.98 | 64.92 (< 70) |
| reference | 100 | 84.21 | 81.25 (fails R9 only) | 92.11 | 90.63 |

## Side effects

- F1 (IN-15/DS-22/AL-18/AL-19): handbook not edited for F1; oracle change gives byte-identical shipped and H1-H4 outputs (scratch rebuild TESTS_SAME, DB_SAME, CASES_SAME before any other change), so tests, TRUTH counts and goldens stay aligned.
- F2/DS-22: TRUTH counts rechecked: 35 checks, P 101, negatives 20, 28 of 101 isolated, 55 data files, 22 artifacts, judge 11 criteria +16/-11; Provenance digests recomputed by script last (test_output.py a99279a00189..., solve.py 806aae3eb06a..., handbook fa0441297324...).
- F3 (JD-2/JD-7/JD-9/JD-15/IN-8): criteria 11 >= 8; weights only 1/3/5; reference still passes every outcome criterion (JD-7); outcome criteria R1-R5 still read instruction.md:13 figures (IN-8); live judge_qc J2 forced the renumber R12 -> R11 (TRUTH, XREF, QC_DEFENCE updated).
- F4 (TS-13, NEW-CHECK hygiene Always 12): C5 rows use existing file formats, rev 9 / seq 8100 like C3/C4 rows, manifests refreshed; no shipped file changed; no lever variant lost or gained a failing set; lot ties intact.
- W2 (AL-27): R11 [old R12] still has its trap (the retired row above the cutoff is still `retired_item`, not out of scope); non-empty handbook line count unchanged (307), so rows_seen and xref record_count unchanged.
- W3 (TS-14/TS-15, AL-28): honest-stdlib program does not fire (local 101, Docker below); the cheat that writes into its input dir fires (before 101 no fire, after -3). Judge R8 also penalised /app/data writes, so a solver writing there would have paid -3 twice; R8 carved to "by any means other than running its solver.py" (STACKING_CHECK.md hand correction: each act <= 5).
- Always 11: generator output diffed byte for byte against bundle before rebuilding (clean); every regeneration made in scratch and copied in.

## Trap survival (local scorer, tests channel, share of P = 101)

| Variant | Before loss of P | After loss of P | Ratio | Separating cases kept | Verdict |
|---|---|---|---|---|---|
| agent_v0 | 0.842 | 0.842 | 1.00 | y | PASS |
| m_fallback (LV-DPR-02) | 0.693 | 0.693 | 1.00 | y | PASS |
| m_tie (LV-DPR-01) | 0.693 | 0.693 | 1.00 | y | PASS |
| m_amend (LV-DPR-03) | 0.683 | 0.683 | 1.00 | y | PASS |
| m_rejnorm (LV-DPR-04) | 0.327 | 0.327 | 1.00 | y | PASS |
| m_voidlog (LV-DPR-04) | 0.129 | 0.129 | 1.00 | y | PASS |
| M10 m10_logabove | 0.000 | 0.475 | n/a (new) | y | PASS (harder) |
| M11 m11_restorevoid | 0.000 | 0.475 | n/a (new) | y | PASS (harder) |
| M16 m16_neghalf | 0.000 | 0.218 | n/a (new) | y | PASS (harder) |
| a2 solver.py | share 0.673 | share 0.673 | 1.00 | y | PASS (<= before + 0.02) |
| ts16_cheat_input | penalty 0 | penalty -3 | n/a | y | fires after only |
| ts16_cheat_tmp | penalty -3 | penalty -3 | 1.00 | y | PASS |
| ts16_honest | 101, no fire | 101, no fire | 1.00 | y | PASS |

Failed hidden groups are identical before and after for every lever variant and a2 (scores in WORK/trap/before_v3r2_scores.json and after_v3r2_scores.json). Overall: PASS.

## Deviations from master directions

- F1: fixed on the solve.py side, not the handbook. QC_FIX_PLAYBOOK_v2 DS-20 NEVER column: "Changing the contract to match the oracle"; the handbook (:80-82, :331-332) and glossary :18 already say only `retired` drops out. Outputs proven byte-identical, no lever easier.
- F2: TRUTH reads "the four optimality checks in their five check keys", not "five optimality checks", because handbook :209 counts four checks (lot sizing = two keys) and :296-299 five keys; plain "five checks" would contradict the handbook.
- F3: R12 renumbered to R11 (live judge_qc J2 requires sequential ids).
- W2: wording "never counted as rejected because of the cutoff; the section 14 rejection reasons are applied first, and a row that survives them is counted as out of scope." (merged the next sentence to keep the non-empty line count, so all outputs stay byte-identical).
- W3 side effect: judge R8 carved (not in directions) to stop a double penalty created by the TS-16 fix.

## Lessons for the master

- DS-20 preferred direction (edit contract to match oracle) is the playbook's NEVER column; directions should default to the oracle side when the contract is already clear | template_change: prompts/issued direction text for DS-20, no template file line (master direction, not template)
- Deleting a judge criterion needs the live J2 sequential-id rule in the direction | template_change: QC_FIX_PLAYBOOK_v2.md JD-8 row: add "renumber, J2 requires sequential ids"
- Widening a tests negative to a new channel (TS-16 input dir) can stack with a judge penalty on the same act (AL-28) | template_change: FIX_SIDE_EFFECTS.md TS-16 row: add AL-28
- Precheck notes no WORK/RULE_COVERAGE.md (LEVER_RULES G11); QC v6 did not flag it, left out of scope | no change: out of scope this round

## Gate results (Docker, tests only)

One nohup chain (`/tmp/opencode-logs/dpr-v3r2-20261024T140535-a0ec/chain.sh`, runs.log ends ALL_DONE), copies built by the live kit exe_copy.py (plain, `--owner-only`, `--stub`; ts16 = plain copy whose solve.sh runs WORK/wrong/ts16_honest.py as /app/out/solver.py). Verifier image warmed first (WARM rc=0).

| Run | Reward | Detail |
|---|---|---|
| oracle 1 / 2 / 3 | 1.000 / 1.000 / 1.000 | 101/101, no negative fired |
| owner-only | 1.000 | 101/101 |
| nop | 0.000 | 0/101, 29 positive checks fail |
| stub | 0.000 | share of P 0/101 |
| honest-stdlib TS-16 program | 1.000 | 101/101, all six negatives 0 |

Checks after fixes: xref_check 41 entries, 0 findings; precheck.sh last line `PRECHECK CLEAN`; live structure_qc.py exit 0 (17 pass, 1 warn X1, 0 fail); STACKING_CHECK.md PASS (hand corrected); no `__pycache__` in BUNDLE. Tree sha after: `1341a5ab938f`.
