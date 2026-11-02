# RECHECK_FIX sentinel-policy-recompute P12 r2 (board 47d0997)

QC report: `QC/reports/sentinel-policy-recompute/v2.md` (board 1d97a1e, kit 71a653b2). Live kit HEAD
71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e, same as the report kit: no rule ID or wording changed.
Start tree sha e478f82d9b72 (matches QC copy). Session rename 21:14: "codex: no match; opencode:
['ses_e96904e81ffe1Fz20DSQRqGV6y']".

Levers (WORK/LEVERS.md): L3 allowance, L2 rev 1 seconds, L7 per-term rounding, L1 ledger controls;
carried over: HO half-open window, VG version gate, BUN B9 vs B7, CV client version, ST seconds base
timeout, TI tier index, CO convergence. "others none" means every lever not named is none.

## Phase 1 rows

| ID | Label | Rule (live kit) | Evidence | Decision | Playbook row | Effect per lever | Files changed |
|---|---|---|---|---|---|---|---|
| F1 AL-27 | REAL | 05_Alignment_Integrity_QC.md:27 "AL-27 Trigger depth: a rule only counts as graded when the test's input actually constructs the situation where the rule matters." | override_precedence.conf:4 "match_version = the override row and the window containing effective_instant both carry the effective version"; test_body.py:346 `"version": spans[window_id][2]` (every hidden row inherits its window's version). Reference already checks the row: test_body.py:389 `... or row["version"] != EFFECTIVE_VERSION: continue` before the allowance decrement; solve.py:275-276 `elif override["version"] != version: reason = "row-version-" ...` before the allowance. Reference unchanged. | FIX as directed: explicit row version in every HIDDEN_HEADS tuple; new hidden-a row OV-K042-a8 (active, WIN-AUTH v100 window, row version v099) at second position, before the allowance runs out | AL-27 (DO add hidden reseeded rows constructing the case) | VG harder (new separating case for the row-version half); others none | WORK/test_body.py, tests/test_output.py, WORK/single_lever.py, LEVERS.md, QC_DEFENCE.md, TRUTH.md |
| F2 TS-26 | REAL | 03_Tests_QC.md:53 "TS-26 No intra-test double payment, in ANY pairing. ... Two tests reading the same observable with the same decisive logic pay (or punish) one behaviour twice." | test_body.py:609-618 `want = reference_documents("hidden-a") ... assert_document(got, want[doc], ...)`; hidden-a is in HIDDEN (:137) and already graded by the three hidden_* checks. QC_DEFENCE.md:64-67 described the reference-first ruling this replaces. | FIX as directed (Ayush approved): build hidden-a once, resolve twice, byte identity + canonical form, plus hidden-a policy_resolved.json differs from the shipped corpus's | TS-26 (DO narrow so the checks read different observables) | see Trap survival: the wrong readings that failed the rerun check only through the reference loop lose that 1 point (L3, L2, L7, first-only); separating cases all kept; others none | WORK/test_body.py, tests/test_output.py, TRUTH.md, QC_DEFENCE.md, STACKING_CHECK.md |
| M1 TS-13 | REAL (defended) | 03_Tests_QC.md:44 "TS-13 One property per test. A test asserting two unrelated properties hides which one failed and skews the weight; flag it." | test_body.py:624-671 one merged w1 shipped check. QC_DEFENCE.md:81-95 RULED Ayush 23 Oct 19:45 option a; QC_RULINGS TS-13 line 131 (splits created new findings). | KEEP, no edit; defence copied to PL_NOTE.md | TS-13 (DO split) not applied: split measured reflex 0.25-0.29 > 0.20 and broke the 5% shipped cap | all none | none |
| M2 TS-20 | REAL (defended) | 03_Tests_QC.md:51 "TS-20 Weights map to importance semantically. ... 5 = a core outcome ... 1 = a minor detail or existence check." | test_body.py:786-787 shipped check w1; the config outcome is graded w5 on three hidden corpora by hidden_config_document_rebuilt_by_cli_matches (:567-572). | KEEP, no edit; PL_NOTE.md | TS-20 (whole-document hidden checks stay core 5) | all none | none |
| M3 IN-L2 | REAL (minor clarity) | 01_Instruction_QC.md:68 "IN-L2 grammar and spelling clean"; :11 "Your job is everything the script cannot judge: naturalness, grammar, clarity, leaks" | instruction.md:7 first sentence about 70 words. | FIX as directed: split into three sentences, same facts, validation_report.json named once | row NEW (clarity split, no fact added or removed) | all none | instruction.md |
| M4 JD-5 | REAL | 04_Judge_QC.md:71 "JD-5 Each criterion names ONE observable behaviour ... If a judge would need to check two separate things, split it." | judge.toml:66 "The response summarizes the completed work and names where the produced artifacts were written." | FIX as directed: "The response names the path where each of the seven delivered artifacts was written." same id R5, weight 3, binary | JD-15/JD-16 (narrow wording) | all none | tests/judge.toml |
| W7 TS-26 | REAL (warn, defended) | 03_Tests_QC.md:53 (as F2) | test_body.py:530-542 rebuild_config feeds `set` from the delivered policy_resolved.json; :567-572. | KEEP: isolating init/set would hand 5 points to a solver with a wrong resolve (easier); this cascade is the defence in QC_DEFENCE.md TS-13/TS-26 for the merged shipped check | SUGGEST (KEEP) / LEVER_RULES G1 natural cascade | all none | none |
| W8 JD-2 | REAL | 04_Judge_QC.md:68 "JD-2 Positive grammar ONLY ... Describe the behaviour as happening. Banned tokens: not, without, fails to, cannot, instead of." | judge.toml:131 "The agent's repaired cli.py has no except clause that discards an error and continues." (+1, absence-shaped; QC_RULINGS line 100 district-heat AVOID). Oracle cli.py: `grep -n except solution/solve.py` returns nothing. | FIX as directed: negative "The agent's repaired cli.py contains an except clause that discards an error and continues.", -1, name r10_except_clause_discards_error | JD-15/JD-16 + JD-18 (keeps the one named-shape code-quality criterion) | all none | tests/judge.toml, tests/reward.toml, TRUTH.md, QC_DEFENCE.md |
| W9 JD-9 | REAL (warn) | 04_Judge_QC.md:86 "JD-9 Process focus is the judged channel's value-add ... Prefer trajectory/state_change criteria that watch HOW the agent worked." | judge.toml:91-94 R7 weight 5, implied by passing the hidden resolve tests. | FIX as directed: R7 5 -> 3, wording unchanged | JD-15/JD-16 | all none | tests/judge.toml, tests/reward.toml, TRUTH.md |
| W10 IN-2 | REAL (warn) | 01_Instruction_QC.md:32 "IN-2 The instruction must never name anything under `tests/` or `solution/` ... no \"the grader\" or \"the checker\""; :71 "(stating WHAT is judged is fine)" | instruction.md:5 "is extracted and its `resolve` subcommand is run ... each document it writes is graded whole" (procedure). README in tool.zip lists `resolve --data-dir <dir> --out <out-dir>`. | FIX as directed, QC's sentence verbatim (README options exist) | row NEW (state the requirement, not the procedure) | all none (the generality promise and whole-document match stay stated) | instruction.md, XREF.md |
| W11 Step 11 | REAL (warn) | Final_checklist.md:424-430 "Step 11: final coverage and overlap re-check ... Every explicit requirement in the instruction must be checked by at least one test or judged criterion" | instruction.md:7 asks for the resolution order; output_field_spec.txt:16 `resolution_order (files consumed in order)`; test_body.py:92 key presence only. | FIX as directed inside hidden_dependency_trace_document_matches (no new check, no weight change) | TS-19 (add the grader on hidden inputs) | BUN, chain order (dependency chain) harder; others none | WORK/test_body.py, tests/test_output.py, TRUTH.md |
| W12 DS-27 | REAL (warn) | 02_Data_Solution_QC.md:80 "DS-27 TRUTH.md describes the task, not how the task was made. ... What does not belong is any narrative of the production process" | TRUTH.md:17 "(the hardening levers; the shipped corpus does not separate them, the fresh corpora do)" | FIX as directed | DS-22 (TRUTH prose) | all none | solution/TRUTH.md |
| W13 X1 | REAL (warn, acknowledged) | structure_qc.py:71 "X1  no em/en dash in any text file; binary-skipped files warn." | 8 binary files skipped; Gate 02 DS-7 re-checked members by hand. | KEEP, no edit; PL_NOTE.md | SUGGEST (KEEP) | all none | none |

## Changes applied (Phase 2)

- F1: WORK/test_body.py HIDDEN_HEADS rows carry an explicit row version (10-tuple); build_variant writes that version instead of the window's. New hidden-a row `OV-K042-a8` (active, K042, WIN-AUTH v100, row version v099, rev 2, timeout 120, records 15, retry 1, risk 4), right after OV-K118-a1 so allowance 3 is still open. reference_documents (test_body.py:389) and solution/solve.py:275-276 both already reject a row whose version differs, before the allowance decrement; hidden-a reference is unchanged (applied OV-K042-a3, a5). Shipped data unchanged. New single_lever.py variant "window-version only" drops solve.py:275-276.
- F2: rerun check builds hidden-a once, runs resolve twice into two fresh dirs, requires byte identity and canonical form for every resolve document, then asserts the written policy differs from the shipped corpus's reference policy. Reference-equality loop removed; docstring, TRUTH.md, QC_DEFENCE.md, STACKING_CHECK row updated.
- W11: hidden_dependency_trace also requires boot_manifest.toml, bundle_ledger.jsonc, principal_role_index.yaml, override_deltas.json in that relative order in resolution_order (basenames; other entries allowed). Oracle passes shipped + hidden-a/b/c (31/31).
- M3/W10: instruction.md:5 and :7 reworded as directed (README option `resolve --data-dir <dir> --out <out-dir>` exists in tool.zip README.md).
- M4/W8/W9: judge.toml R5 wording, R10 negative -1 (name r10_except_clause_discards_error), R7 3. Judge: 15 criteria, positive 34, negative -17; reward.toml judge = 0.5/34 = 0.014705882352941176. solve.py has no `except`.
- W12: TRUTH.md:17 heading reworded as directed.
- Regenerated tests/test_output.py with build_tests.py (diff vs test_body.py clean). TRUTH.md: tests 12 checks, P 31, negatives -11; judge 0.5/34; test_output.py sha256 16db1933...; solve.py 674 lines, sha and tool.zip sha unchanged. XREF.md 25 entries (5 new, old values retired). LEVERS.md P12 r2 section.

## Deviations from master directions

None.

## Gate results

- xref_check: 25 entries, 0 findings.
- QC scripts (live kit 71a653b2): structure 17 pass / 1 warn (X1 binary skip, W13 KEEP) / 0 fail; instruction 5 pass; tests 37 pass; judge 19 pass. 0 FAIL.
- Manual checks: AL-27 window-version-only variant loses 20/31 (hidden policy, curve, trace, config); TS-26 rerun check reads no reference (stacking_check: no duplicate candidates); IN-L2 three sentences in line 7, IN-2 no grader/checker/tests/solution words, procedure sentence gone; JD-2 no banned token in R5/R7/R10, JD-5 R5 one observable, JD-9 R7 at 3; DS-27 "hardening levers" gone from TRUTH.md; Step 11 resolution_order asserted. No em/en dash in edited files.
- STACKING_CHECK.md: STACKING PASS (G3 whole-doc 64.5%, isolated+mutation 29.0%, shipped-only 3.2%; AL-28 eight acts, each <= 5).
- Docker (TS 20261023T213202-e350, exe_copy copies, warm image reused: tests/Dockerfile unchanged since 19:02 build): oracle 1.0 / 1.0 / 1.0, owner-only 1.0, nop 0.0, stub 0.0 (0/31 of P). Log `/tmp/opencode-logs/sentinel-policy-recompute-p12r2-20261023T213202-e350/runs.log`.
- Local (tests channel): oracle 31/31 shipped + hidden; nop 0/31 before and after; stub (seven empty artifacts) 0/31 before and after.

## Agent program before/after

harden_r1 agent program, build replay (reflex_score.py build): before 0.1290 (4/31: validate 3, shipped 1), after 0.1613 (5/31: validate 3, rerun 1, shipped 1). Swap mode 0.0968 -> 0.1290. The rerun point is now earned by any deterministic resolve whose policy is not the shipped one. 0.1613 <= 0.20 and within +0.05 of before.

## Trap survival

| variant | before loss of P | after loss of P | ratio | separating cases kept | verdict |
|---|---|---|---|---|---|
| first-only | 0.6774 | 0.6452 | 0.952 | y | PASS |
| no allowance | 0.7742 | 0.7419 | 0.958 | y | PASS |
| allowance per principal | 0.7742 | 0.7419 | 0.958 | y | PASS |
| raw timeout | 0.5161 | 0.4839 | 0.938 | y | PASS |
| abs(v) < 100 heuristic | 0.5161 | 0.4839 | 0.938 | y | PASS |
| sum rounding (L7) | 0.2903 | 0.2581 | 0.889 | y | FAIL |
| controls never recomputed | 0.1613 | 0.1613 | 1.000 | y | PASS |
| inclusive window end | 0.9032 | 0.8710 | 0.964 | y | PASS |
| window-version only (new) | 0.0000 | 0.6452 | new | y (new case) | PASS (> 0) |
| harden_r1 agent program (score) | 0.1290 | 0.1613 | - | - | PASS (<= 0.20) |

nop 0.000 and stub 0.000 of P, before and after.

Overall: FAIL on L7. Cause: F2 removed the hidden-a reference comparison from the rerun check (the TS-26 double payment), so every wrong reading that failed it now loses one point fewer; L7 is the smallest-loss lever (9 -> 8 of 31) so one point is over 10%. Compensation allowed by the prompt is only lowering a shipped weight (never below 1); the only shipped-only check is already weight 1, so none was applied. F2 stays in place; status PAUSED on F2 for the master's ruling.

## QC_RULINGS rows

- F1 AL-27: row-version half of match_version untriggered; QC fail; REAL; added hidden-a OV-K042-a8 (v099 row in v100 window), window-version-only reading now loses 20/31.
- F2 TS-26: rerun check re-paid hidden-a reference equality; QC fail; REAL; reference loop dropped, byte identity + canonical + differs-from-shipped kept (trap L7 0.889, paused).
- M1 TS-13: merged shipped check, two properties; QC minor; REAL (defended); KEEP per Ayush option a (split fails trap and shipped cap).
- M2 TS-20: shipped check at w1 holds config; QC minor; REAL (defended); KEEP, config graded w5 on hidden rebuild.
- M3 IN-L2: 70-word report sentence; QC minor; REAL; split into three sentences, no fact change.
- M4 JD-5: R5 two observables; QC minor; REAL; one observable (path of each of the seven artifacts).
- W7 TS-26: rebuild check feeds delivered policy; QC warn; REAL (defended); KEEP, natural cascade (G1), isolating is easier.
- W8 JD-2: R10 absence-shaped positive; QC warn; REAL; negative -1 "contains an except clause that discards an error and continues".
- W9 JD-9: R7 at 5 duplicates hidden resolve outcome; QC warn; REAL; R7 3.
- W10 IN-2: instruction described the grading procedure; QC warn; REAL; QC's requirement sentence.
- W11 Step 11: resolution_order order never checked; QC warn; REAL; relative order of four chain files asserted in hidden trace.
- W12 DS-27: TRUTH.md production word "hardening levers"; QC warn; REAL; reworded.
- W13 X1: binary files skipped by dash scan; QC warn; REAL (acknowledged); KEEP.

## Lessons for the master

- The trap "before" figure counted the very double payment F2 removed, so the smallest lever (L7, 9/31) cannot keep 90%; consider measuring before without the flagged pairing.
- To restore L7 margin: one hidden row where per-term rounding moves the converged risk_threshold (new fixture, out of this round's scope).
- R10 is now a negative for a code-quality act, not a cheating act (LEVER_RULES G4); QC r3 may flag it.
- TRUTH.md:183 says "for each lever" (describes R12-R15); not flagged, left as is.

Final tree sha 88d1009c6a4c. Final rename 21:37: "codex: no match; opencode: ['ses_e96904e81ffe1Fz20DSQRqGV6y']".
