# DIAGNOSIS: schema-migration-plan-repair, P9 v2 harden r1 (board f681ef6, 23 Oct 2026 IST)

Scores below are tests-only.

## 1. Phase A: GENUINE

- `blind_r1/SCORE.md`: "Bundle tree c14ac49d14e5 (unchanged since P12 r3 a2407ba). Solver: opencode Opus 5.5. Scored offline in tests/Dockerfile image, judge removed ... tests: 137 / 137 (100), 46 checks, no negative fired, no check notes."
- `blind_r1/score_run.log` holds only `reward: 0.5`, which is the full tests half (137 x 0.5/137). It has no traceback, denied or skipped line.
- `score_reward_details.json` has one component (`test_output`). All 46 criteria are present, every positive is 1.0 and every negative 0.
- P12 r4 re-scored the same blind output on the 49-check tree (8c0eca82c1d9) and got 137/137 again (WORK/LOG.md 2026-10-23 rows), so the score does not depend on the tree change.
- The run was blind: work/BLIND_REPORT.md lists only instruction, environment and ci reads, with no tests/ or solution/ read.

The 1.00 is a real solve of the task as written, so this report continues.

## 2. Four causes

| Cause | Verdict | Evidence |
|---|---|---|
| C1 run error or wrong copy | NO | Stated tree was scored in the tests image, no verifier errors, 46/46 criteria scored, and the result reproduced on the current tree. Side finding (not a cause): the bundle `tests/test_output.py` embeds an older `ci/repository_contract.md` (7819 bytes, before the P12 r4 K19 precision clause; the live file is 8082 bytes). That is an Always 6 slip from P12 r4 and is fixed in this round by re-embedding. No graded figure reads that clause from the embed. |
| C2 harness or rescoring change, or baseline artefact | PARTLY | The harness only moved 3fb1650b to 71a653b2 (structure_qc.py and FORMAT_SPEC only; no scoring change). The artefact is the baseline. No hard baseline was ever measured. hardness_r1 `baselines.json` already said REBUILD (S4 0.6268, S4b 0.7746, every lever DERIVABLE), and the v0 trajectory scored 99.3. Nothing "got easier": it never was hard. |
| C3 our QC and fix rounds made it easier | PARTLY (small) | Files changed since hardness_r1, and whether each change put a rule, figure or separating example in front of the solver: rebuild r1 (every file; added the decoy and N7 text, which made it harder); P12 r1 (tests TS-13 split; DS-27 sentence deleted from TRUTH; judge R7 narrowed; no solver-facing rule); P12 r2 (M5 gained "booleans included" (IN-16) and K17 got a precision edit, both solver-facing rules that close a bool and fingerprint ambiguity; tests case_fill bools); P12 r3 (K7 "no argument mutation" sentence, solver-facing; test gadgets); P12 r4 (K19 "changed" definition, solver-facing. It decides the module claims, which v0 lost (`module_core_claims_match_archive`) and blind won, worth 1 point). These are worth at most 1 to 4 of 137 points. |
| C4 levers weak by design | YES | See the per-lever table in section 3. Every lever is a shipped code defect that contradicts one explicit sentence in the file that governs it, and the task tells the solver to "repair the repository so that every stage behaves as the contract states". A line-by-line read of code against contract finds every defect. The data never tempts a wrong reading, because the shipped code is the only wrong reading and the solver reads code critically. No control, no bait, no definition-carried scope. |

PRIMARY CAUSE: 4 (levers weak by design). Contributing: 2 (no hard baseline ever existed) and 3 (P12 r2 to r4 precision sentences, at most 4 points).

### C4 per lever: rule, where the solver got it right, what gave it away

| Lever | Rule text and home | Blind fix (repo_repaired) | Give-away |
|---|---|---|---|
| STATE | M6 "on the record at that point of the plan", M7 "may revisit a schema" (migration_semantics.md:31-39) | planner `_search` state = (schema, signature), prereqs on the transitioned view | one-sentence rule; shipped `_applies(received)` visibly ignores the step |
| TIE | M8 "smallest edge-id list, compared as Python lists" (:41-44) | heap on (cost, ids) | explicit comparison rule |
| SCALE | K14 limits + 10 s (repository_contract.md:81-86) | Dijkstra over states | limits stated; DFS obviously exponential |
| NULL | N1 "every stage keeps null distinct" (null_semantics.ini:3-6) | FieldView.from_payload keeps NULL | code drops null in one line |
| POLICY | N2/N3 empty column falls back to [presence] (ini:7-14) | null_counts_as/fill_mode fall back to ini | the OPTIONAL_NULL decoy contradicts N3 verbatim |
| TOKENS | N7 "exactly that line" (ini:22-23) | tokens_for without `or` | the word "exactly" names the trap |
| CORR | C4 first arrival, log order, re-check (correction_log.txt header) | executor arrive() + re-check | numbered rule list |
| REPLAY | K16 canonical identity, holder once partner stage passes (contract:94-103) | `_admit` order fixed | the blind report says it "needed reading K16 literally" and did so |
| FEED | P2/P3 every link, loop; K15 run continues | identity loop + feed continue | direct sentences |
| REPORT | T1/T3 (report_taxonomy.json rules) | summary code-first, rank order | rules in the same JSON |
| CLI | K10 caller cwd, `python -m` | `__main__.py`, cwd paths | visible tests fail on shipped code |

## 3. Lever table (blind r1, 46-check tree, from score_reward_details.json)

| Check | Points | Earned | Levers | Verdict |
|---|---|---|---|---|
| artifacts_exist, archive_members_safe_src_layout, api_entry_points_importable, visible_repo_tests_pass_from_archive, summary_json_matches_delivered_run, module_core/parser/report_claims_match_archive, test_fixes_matches_visible_test_runs, repair_report_well_formed | 10 x 1 | 10 | STRUCT, CLI, K19 | LEAKED |
| signature_keeps_explicit_null | 3 | 3 | NULL | LEAKED |
| signature_rejects_unknown_schema | 1 | 1 | STRUCT | LEAKED |
| plan_revisits_schema_with_new_state | 3 | 3 | STATE | LEAKED |
| plan_tie_first_edge_decides | 3 | 3 | TIE | LEAKED |
| ladder_large_state | 3 | 3 | SCALE | LEAKED |
| exec_add_fill_absent_vs_null | 3 | 3 | NULL, POLICY | LEAKED |
| exec_correction_first_arrival_only | 3 | 3 | CORR | LEAKED |
| identity_merge_links_followed | 3 | 3 | FEED | LEAKED |
| pipe_rejection_codes | 3 | 3 | REPLAY, FEED | LEAKED |
| pipe_bad_lines_run_continues | 3 | 3 | FEED | LEAKED |
| summary_categories_code_first | 3 | 3 | REPORT | LEAKED |
| summary_partner_order_by_rank | 1 | 1 | REPORT | LEAKED |
| world_01 .. world_19 (19 x w5) | 95 | 95 | lever mixes in names | LEAKED |
| 5 negatives | -13 | 0 | HONESTY | not fired |

Every lever LEAKED. Total 137/137.

## 4. Solve autopsy

- Read order: instruction, environment Dockerfile, repo README, pyproject, every src file, test_visible.py, then the six ci rule documents in full and heads of the six data files. Context was compacted once and re-read.
- Repair was done in a single pass of about 20 minutes (14:55 to 15:20). The solver changed every file that holds a defect, plus `_rename`.
- It did not change graded logic after its self-check, and BLIND_REPORT says there was no rework.
- Self-checks: visible tests 9/9; a shipped CLI run (exit 0, 8000 records, by_category sum 8000, attempted 5648 = migrated 5604 + superseded 44); output existence; zip layout. None of these self-checks covers a lever with constructed input. The solver got the levers right by reading alone. Its own note: "zero E_PREREQ_FAILED on shipped data surprising given C5, did not investigate".
- Takeaway for hardening: the solver trusts green shipped runs and a balanced count identity ("attempted = migrated + superseded"). That is the reflex a green control (L1) exploits.

## 5. Agent program

`OUT/agent_program/` holds `repo/` (the blind repaired migrakit, including `__main__.py`), `out_blind/` (the blind deliverables), BLIND_REPORT.md and TODO.md. The reflex replay against the new tests is `agent_program/replay.py` (Phase 3). It applies the blind fixes plus the reflex reading of each new lever to the new shipped repo.

## LEAK_LIBRARY rows

- STATE: one-sentence rule M6 beside visibly wrong code; leaked by the code-against-contract read. Fix: retire as a separator and keep it as a cascade member; the new receipt (L1/L2) and definition scope (L6) carry the separation.
- TIE: explicit comparison sentence M8; leaked by the same read. Fix: retire as a separator and keep it.
- SCALE: stated limits plus obviously exponential DFS; leaked. Fix: retire and keep the ladder.
- NULL: N1 one sentence; leaked. Fix: keep. The L5 token row separates instead.
- POLICY: the decoy refuted verbatim by N3 (LEAK "decoy refuted beside use"); leaked. Fix: keep.
- TOKENS: "exactly that line" spells the trap out; leaked. Fix: the new L5 strict-vs-normalising token match (N6 vs N8/M5) on the same stage.
- CORR, REPLAY, FEED, REPORT, CLI: numbered one-sentence rules; leaked. Fix: keep as cascade members only.
- New levers (written this round): L1 receipt per batch in replay_manifest.csv, green for every downstream misreading; L2 shipped receipt check fails on partner-rejected lines, and the make-it-match repair writes fingerprints into those records against K17; L6 the receipt line count is scoped by the K17/K15 definition of a record's `batch`; L5 N6 exact token match beside N8 trimming and M5 space-ignoring casts, with separating rows shipped.

## Lessons for the master

- A repo-repair task whose defects each contradict one contract sentence is solved by a careful diff read. It needs controls and definition-scoped terms to be hard.
- The P12 r4 contract edit was not re-embedded in tests; re-run embed after every ci edit.
- Hardness r1 never measured a hard baseline, so "leaked since baseline" has no anchor for this task.
