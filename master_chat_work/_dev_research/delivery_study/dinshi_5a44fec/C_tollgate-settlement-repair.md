# C card: tollgate-settlement-repair

Base `T=.../Perfect_for_Delivery/Dinshi_Jain/tollgate-settlement-repair`. QC report `Aniket_Datta_tollgate-settlement-repair_QC_Report.md`.

## 1 Scores and verdict
- Recorded overall 72.89, tests 91.55, rubric 54.24. QC re-grade 66/72 = 91.67% (QC :149).
- Verdict **GENUINE** (A file). 6/71 lost on two w3 checks: one genuine wrong value (3) and one contested by a test-vs-runbook contradiction (3).

## 2 Inventory
- Domain: toll-road settlement software (Python stdlib package `tollnet` 2.4.0). Archetype: **repair a broken package** (find real defects, name them from a vocabulary with decoys) + report blocks + held-out fixture.
- Data: project.zip, runbook.md 11.4 KB (236 lines, binding contract), release_notes.md, config/ (canonical_form.toml, label_vocabulary.json 14 labels incl 4 decoys, module_contracts.json, report_blocks.json, settlement defaults/overrides), gates/ 18 profiles, incidents/ 8, patches/ 2 rolled back, gate_events.jsonl 1.27 MB, selftest_trace.log 214 KB, tariff_table.json, registries.
- Instruction 716 words, 9 rules. 5400 s.
- Tests (stacking_check, current): 30 checks, positive 72, negatives -6 (4). Judge 24 criteria, positive 55, batched. Reward = (tests + rubric)/2.
- Shares: isolated 63.9%, whole_doc 22.2%, shipped_only 13.9%. By hand the holdout drivers (`_drive` with fixture.json) are hidden inputs, so the real hidden share is higher than stacking reports.

## 3 Test architecture
- Expected values: **hand-frozen constants in the test** (MEMBER_ORDER, UNTOUCHED sha256 of 5 files, SHIPPED_IMPLICATED, DEFECT_LABELS 10, MODULES_CHANGED, LOAD_ORDER, BIND_ORDER, MANIFEST_ORDER :81, CORPUS figures, HOLDOUT / HOLDOUT_ROWS / HOLDOUT_REPORT / HOLDOUT_LEDGER). QC DS-24 (:96) and CL-3 (:103): corpus figures appear in no shipped file.
- Execution: `_tree` 351 extracts the delivered package.zip and chowns it; `_sandboxed` 361 runs under setpriv 65534 (100 s); `_drive` 394 runs drivers on a hidden fixture; `_selftest` 408.
- Behaviour probes: `package_repair_scope_exact` uses a BAND_DRIVER probe (QC CL-2 fix :33) instead of a diff; untouched modules checked by sha256.
- Partial credit: summary split into counts/money/ledger/evidence (`_summary_subset` 488); report blocks split by block; `shared_figures_agree_across_blocks` 649 added by QC.
- Negatives: hardcoded -3, filename -1, reads_training_corpus -1 (token grep; QC TS-16 warn :47), nondeterministic -1 (4 hash seeds). No wrong-reading negatives.

## 4 Lever table (failed checks)

| id | w | rule graded | locations (quotes) | form | agent reading | why self-test missed | fully stated? | nearest |
|---|---|---|---|---|---|---|---|---|
| build_report_chain_and_phase | 3 | root_cause_chain = ["_bootstrap.py","core.py"] (solution/solve.py:44 constant) | runbook.md:179-180 "the modules whose defects had to be repaired in order before the next one could be seen, listed in that order"; rationale only in solution/TRUTH.md:139-146 | **definition with a judgement** (which defect masks which) | ["_bootstrap.py","tariff.py","metrics.py"], written at step 33 without deliberation | no observable to self-check; the chain is a narrative judgement | Stated as a definition; applying it needs reconstructing masking order | NEW: judgement field graded exactly |
| dependency_block_orders | 3 | dependency block lists bare module names (solve.py:97-98, 443-445; MANIFEST_ORDER test:81 bare) | runbook.md:182-185 "Every module named in a delivered block carries the source file name as it appears in the archive, with its `.py` suffix, and every module list in a block is sorted and carries no repeats" (inside the 8.5 build_report paragraph) | **scope by placement** (global wording inside one block's section) | applied `.py` to every block; orders correct | its output obeys the literal sentence | **CONTRADICTED**: the literal global sentence says `.py`; the test wants bare names | never-used list "answer key contradicting contract" |

## 5 How tests handle QC
- TS-13 ✅ (QC :238). TS-16 ❌ warn (QC :241): token-grep negative fires on `/app/` and other tokens no file forbids.
- TS-19 ✅ (QC :244). Risky per our rulings: runbook.md:182-185 vs bare-name expectation; QC CL-5 (:105) cited the `.py` rule but did not see the contradiction.
- TS-20 ✅ (QC :245). TS-26 ✅ after narrowing module blocks (QC :247); stacking still lists 5 groups, by hand different observables.
- IN-15 ✅ / IN-16 ✅ (QC :186-187).
- AL-28 ✅ (QC :304); stacking flags judge R10/R22/R23/R24 as unmatched 12, by hand distinct acts.
- CL-4 ✅ (QC :290): one wrong fact 60/71 = 0.845.
- JD-7 ✅ (QC :267).

## 6 Leak avoidance
- W3: "The vocabulary is wider than this job needs" (instruction) – decoy labels signposted only by that line (QC CL-3 :103).
- W2/W8: "Where two sources disagree, the runbook settles it" – one sentence naming the winning document (QC CL-6 :106).
- "The shipped case set is narrow" – warns the agent without naming the holdout cases.
- Holdout fixture and corpus figures are only in tests; patches/ show two rolled-back fixes as evidence, not as answers.
- LEAK_LIBRARY: avoids "decoy refuted beside use" (decoy labels are not refuted anywhere; the agent must test each defect by reverting it).

## 7 Agent behaviour
- 49 steps, 12 minutes (20:24-20:36 UTC). Wrote root_cause_chain at step 33 without discussion.
- Self-test: final message (step 49) claims 10 defects each verified by reverting the fix – a strong behavioural self-test that explains the high pass rate.
- Final claim vs reality: defects and labels right; chain judgement and suffix scope wrong.

## 8 Passed checks
- Package form, repair scope, case set, holdout pricing/reports/reconciliation, fleet accounts, summaries, labels, module blocks, selftest block: each is behaviourally checkable by the agent (revert-and-run), so Opus got them right.

## 9 Take-aways
- SAFE adopt: behavioural probe drivers over the delivered package on a hidden fixture, plus sha256 for untouched modules.
- SAFE adopt: decoy vocabulary signposted by one neutral sentence.
- Avoid: a format sentence worded globally but placed in one block's section when another block's expected value disagrees (contradiction, not a lever).
- RISKY: exact-match judgement fields (root-cause chain) – low yield (3 pts) and arguable.
