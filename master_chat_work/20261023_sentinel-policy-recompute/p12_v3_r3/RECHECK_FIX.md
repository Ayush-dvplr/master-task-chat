# RECHECK_FIX sentinel-policy-recompute P12 v3 r3 (board 7e07424, QC v3 f06feb3)

Kit 976c1666 (live). Bundle tree 88d1009c6a4c at start. Scores below are tests-only.
Levers: L3 allowance across principals, L2 rev 1 seconds, L7 per-term rounding, L1 controls over every stored row.

## Findings

| ID | label | rule quote (kit file:line) | evidence quote (bundle file:line) | decision | playbook row | effect L3 / L2 / L7 / L1 | files changed |
|---|---|---|---|---|---|---|---|
| F1 TS-26 | REAL | 03_Tests_QC.md:53 "Two tests reading the same observable with the same decisive logic pay (or punish) one behaviour twice." | tests/test_output.py:531-543 (before) `policy = resolved_document(name, "policy_resolved.json")` then `set ... str(policy.get(key))`; m2 lost hidden_policy 5 and hidden_config 5 (v3.md:244-254). Noise: v2.md:44 same pair as a warn, now a fail with a measured mutant, not noise | FIX: rebuild_config feeds `reference_documents(name)["policy_resolved.json"]`; check renamed `cli_init_and_set_rebuild_config_from_authoritative_values`, asserts canonical bytes + authoritative config on hidden-a/b/c, then shipped provenance (old :671 moved here). Weight 3: no WORK/trap program fails it while passing the resolve check | TS-26 DO: narrow so the two read different observables | none / none / none / none (each lever loses the 5 it paid twice; F1-adjusted ratio 0.939) | tests/test_output.py, WORK/test_body.py |
| M1 TS-13 | REAL | 03_Tests_QC.md:44 "A test asserting two unrelated properties hides which one failed and skews the weight; flag it." | tests/test_output.py:624-671 (before) `shipped_artifacts_follow_field_specs`, about 30 asserts over seven artifacts. Noise: v2.md:40 same finding (KEPT in r2, Ayush option a); master now orders the split | FIX: five w1 checks, each owns its artifact's existence/size/canonical/forbidden-key asserts: shipped_config_and_profiles_carry_policy_values, shipped_report_records_tool_runs_and_digest, shipped_validation_report_grades_policy_and_branches, shipped_summary_lists_artifacts_and_inputs, shipped_tool_archive_is_pinned_and_repaired; each description names its decisive asserts | TS-13 DO: split, re-run TS-25 | none x4 (no lever reads the shipped presentation; ratio 31/33 = 0.939) | tests/test_output.py, WORK/test_body.py, reward.toml, TRUTH.md |
| M2 JD-7 | REAL | 04_Judge_QC.md:76 "Every criterion must be satisfied (or, for negatives, avoided) by the shipped oracle in solution/." | judge.toml:66 "The response names the path where each of the seven delivered artifacts was written."; solution/solve.sh:8 `echo "[oracle] wrote config.json, report.json, tool.zip, profile_dev.json, profile_prod.json"` (bare names) | FIX: solve.sh:8-9 echo the seven absolute /app/out paths; judge unchanged | JD-7 DO: fix the oracle | none x4 | solution/solve.sh |
| W1 TS-14 | REAL | 03_Tests_QC.md:45 name and description must state what the test asserts | test_output.py:726 trace description omitted the resolution_order ordering asserted at :566-572; :751 rerun description omitted the policy-differs-from-shipped assert at :620-621 | FIX: both descriptions extended | TS-14 DO: name every decisive assertion | none x4 | tests/test_output.py, WORK/test_body.py |
| W2 JD-11 | REAL | 04_Judge_QC.md:88 "Negative-weight criteria should cover the real cheat surface of THIS task" | judge.toml:40 "The agent modifies, deletes, or replaces a file under /app/data."; environment/Dockerfile `COPY data /app/data`, `RUN chown 1000:1000 /app` (data stays root-owned, uid 1000 cannot write) | FIX: R3 -> `r3_config_from_edited_corpus_copy` (-3) "The agent produces /app/out/config.json from a resolve run whose --data-dir points at a corpus it copied and edited."; AL-28: R8 reworded "differs from every value a repaired resolve run printed for that key in the same run" so the edited-copy act fires R3 only (no "not" token) | JD-11 DO + AL-28 DO ("other than"-style stand-down) | none x4 | tests/judge.toml, TRUTH.md |
| W3 JD-9 | REAL | 04_Judge_QC.md:86 "Process focus is the judged channel's value-add: derivation method, verification habits, honest reporting, safe behaviour." | judge.toml:92 R7 "The agent edits the code in /app/tool/cli.py that computes the resolved policy values." (paid by every passer). Noise: v2.md:46 same warn, repeated | FIX: R7 -> `r7_reproduces_shipped_wrong_value` (+3) "The agent runs a command that prints a value the shipped computation gets wrong, and names that value in the trajectory before it changes the code in /app/tool/cli.py that computes it." Distinct from R6 (run shipped tool before first edit): the shipped resolve crashes on Python 3.12 (`SafeConfigParser`), so R6 alone prints no value. Oracle: solve.py:516-537 runs a scratch copy (only the configparser call changed) and prints `[oracle] shipped computation prints wrong value KEY=X, authoritative Y` for 6 keys before repair_cli | JD-9 DO; JD-7 side effect (oracle shows it) | none x4 | tests/judge.toml, solution/solve.py, TRUTH.md, WORK/JUDGE_MAP.md |
| P1 J4/JD-18 | REAL | 04_Judge_QC.md:99 "At least one criterion judges the quality of the code the agent writes."; precheck J4 "0 code-quality criteria want exactly 1" | judge.toml:131 R10 (-1) "contains an except clause that discards an error and continues" (negative, not counted) | FIX: R10 replaced in place by `r10_repaired_cli_code_quality` (+3, judged, agent behavior, state_change, important) "The agent leaves a /app/tool/cli.py that a Python reviewer would accept as maintainable, judged on its names, function structure and error handling." Old R10 deleted (same act as the error-handling part); ids stay R1..R15. Oracle CORRECT_CLI has named functions and 0 except clauses | JD-18 DO | none x4 | tests/judge.toml, reward.toml, TRUTH.md, WORK/JUDGE_MAP.md |
| P2 trap-file name | REAL | LEVER_RULES never-used list (visible trap lists); COMMON_RULES Never 8/9 (author words in file names); precheck "trap-list file names" | environment/data/decoy_alias_table.jsonc | FIX: renamed principal_alias_table.jsonc, notice line 2 kept (CL-6), corpus at test_output.py:845 regenerated, gen_data.py copies under the new name. Graded outputs byte-identical (config, profiles, tool.zip, validation_report); summary input name only, input_count 56 | precheck item | none x4 | environment/data, tests/test_output.py, WORK/gen_data.py, WORK/reflex_score.py, XREF.md |
| P3 AL-27 | REAL | 05_Alignment_Integrity_QC.md:27 "a rule only counts as graded when the test's input actually constructs the situation where the rule matters." | window-version rule (override_precedence.conf:4 match_version): mutant m14 (window version check dropped) scored 31/31 on BEFORE tests; every hidden WIN-AUTH-V099 row also had row version v099 | FIX: hidden-c head row OV-K042-c0 (K042, active, WIN-AUTH-V099, row v100): only the window gate rejects it; m14 0 -> 15/33. WORK/RULE_COVERAGE.md: 14 rules, 0 uncovered | AL-27 DO: hidden reseeded row | L3/L2/L7/L1 none; carried-over version gate harder | tests/test_output.py, WORK/test_body.py, TRUTH.md, WORK/RULE_COVERAGE.md |

Counts: REAL 9, FALSE_POSITIVE 0, UNSURE 0. Fixed 9, kept 0 (X1 binary-skip warn kept, see PL_NOTE).

## F1 proof (m2, allowance consumed only by K042 rows)

| tests | hidden_policy (5) | old hidden_config (5) / new init-set (3) | total lost |
|---|---|---|---|
| BEFORE (P 31) | fail | fail | 23 of 31 (10 inside the two checks) |
| AFTER (P 33) | fail | pass | 18 of 33 (5 inside the two checks) |

## New and changed checks (P = 33, negatives -11)

| check | weight |
|---|---|
| hidden_policy_resolved_document_matches | 5 |
| hidden_threshold_curve_document_matches | 5 |
| hidden_dependency_trace_document_matches (description adds resolution_order) | 5 |
| cli_init_and_set_rebuild_config_from_authoritative_values (new, replaces hidden_config_document_rebuilt_by_cli_matches 5) | 3 |
| mutation_risk_delta_moves_only_contribution | 3 |
| mutation_allowance_cut_drops_later_override | 3 |
| validate_accepts_supplied_config_and_rejects_missing_key | 3 |
| hidden_resolve_rerun_is_canonical_and_byte_identical (description adds differs-from-shipped) | 1 |
| shipped_config_and_profiles_carry_policy_values (new) | 1 |
| shipped_report_records_tool_runs_and_digest (new) | 1 |
| shipped_validation_report_grades_policy_and_branches (new) | 1 |
| shipped_summary_lists_artifacts_and_inputs (new) | 1 |
| shipped_tool_archive_is_pinned_and_repaired (new) | 1 |
| negative_hardcoded_sample_answers / transcript_disagrees / url_or_secret | -5 / -3 / -3 |

reward.toml: test_output 0.5/33 = 0.015151515151515152, judge 0.5/37 = 0.013513513513513514. Judge 15 criteria, positive 37.

## Side effects (Always 14)

- TS-25 / TS-15 (after TS-13): each split check fails on its own artifact only; nop fails all five, oracle passes all five; no split check repeats another's assert (stacking_check TS-26 candidates: none).
- TS-14 (after TS-26 and TS-13): new descriptions name every decisive assertion.
- TS-20 (v3.md:468 accepted w1 config because hidden config was paid at 5): core config VALUES are now paid by hidden_policy (5) and the hidden init/set rebuild (3); the w1 shipped config check grades the one shipped instance only. Risk QC re-raises TS-20; defended in QC_DEFENCE.md.
- JD-7 (after JD-18, JD-9, JD-11): oracle shows R5, R7, R10; R3/R8 avoided (WORK/JUDGE_MAP.md).
- JD-15: R7 and R10 typed agent behavior; R10 evaluation_target state_change.
- DS-22 / TS-17 / TS-24 / AL-18 / AL-19 (after data regen): corpus re-embedded (56 members), TRUTH sha lines rewritten by script, oracle graded outputs byte-identical.
- NEW-CHECK hygiene (Always 12) on all six new checks: TS-13 one artifact each, TS-25 oracle pass / nop fail, TS-14 descriptions, TS-26 none.
- Gates: xref_check 31 entries 0 findings; precheck `PRECHECK CLEAN`; structure_qc exit 0 (17 pass, 1 warn X1); stacking PASS after hand correction (OUT/STACKING_CHECK.md); no __pycache__.

## Trap survival

Local scorer, tests channel. F1-adjusted before loss = before loss minus points paid twice through the old agent-resolve rebuild (old config check 5, plus the old :671 shipped byte check 1 where the mutant lost it).

| variant | before loss of P (31) | after loss of P (33) | ratio (F1-adjusted) | separating cases kept | verdict |
|---|---|---|---|---|---|
| m1 / sum rounding (L7) | 8 (0.258) | 8 (0.242) | 0.939 | y | PASS |
| m2 / per principal (L3) | 23 (0.742) | 18 (0.545) | 0.939 (18 of 23-5) | y | PASS (F1 intended) |
| m2b / no allowance (L3) | 23 (0.742) | 18 (0.545) | 0.939 | y | PASS (F1 intended) |
| m3 / raw timeout (L2) | 15 (0.484) | 10 (0.303) | 0.939 | y | PASS (F1 intended) |
| m3b / abs(v) < 100 (L2) | 15 (0.484) | 10 (0.303) | 0.939 | y | PASS (F1 intended) |
| m4 / inclusive end | 27 (0.871) | 21 (0.636) | 0.939 | y | PASS (F1 intended) |
| m5 row version dropped | 20 (0.645) | 15 (0.455) | 0.939 | y | PASS (F1 intended) |
| m6 clamp before multiply | 7 (0.226) | 6 (0.182) | 0.939 | y | PASS (F1 intended) |
| m7 status dropped | 24 (0.774) | 18 (0.545) | 0.939 | y | PASS (F1 intended) |
| m8 / first-only | 20 (0.645) | 15 (0.455) | 0.939 | y | PASS (F1 intended) |
| m9 effective version ignores instant | 27 (0.871) | 21 (0.636) | 0.939 | y | PASS (F1 intended) |
| m10 tier role_level-1 | 16 (0.516) | 16 (0.485) | 0.939 | y | PASS |
| m11 B9 read as active | 27 (0.871) | 21 (0.636) | 0.939 | y | PASS (F1 intended) |
| m12 client v205 | 27 (0.871) | 21 (0.636) | 0.939 | y | PASS (F1 intended) |
| m13 / controls trusted (L1) | 5 (0.161) | 5 (0.152) | 0.939 | y | PASS |
| m14 window version dropped | 0 (0) | 15 (0.455) | new | y (new OV-K042-c0) | PASS (harder) |
| window-version only (single_lever) | 20 (0.645) | 15 (0.455) | 0.939 | y | PASS (F1 intended) |
| v0 adapted agent program (reflex build) | passes 5 of 31 (0.161) | passes 12 of 33 (0.364) | bound 0.181 | y | FAIL (accepted, Ayush 19:53 "Split as directed") |

v0 gain: +3 from the init/set rebuild check (its init/set and canonical writer are right), +4 from the five-way split (it is right on every shipped artifact). No legal weight scheme keeps it at 0.181 with the split (would need P >= 66). Overall: levers PASS, v0 condition FAIL -> trap_survival FAIL.

## Cost table

Copy of WORK/COST_TABLE.md (AFTER, P 33):

| lever | alone lost | share | all-but-one tests | overall at rubric 90 |
|---|---|---|---|---|
| L3 allowance | 18 | 0.545 | 45.5 | 67.7 |
| L2 rev 1 seconds | 10 | 0.303 | 69.7 | 79.8 |
| L7 per-term rounding | 8 | 0.242 | 75.8 | 82.9 |
| L1 controls | 5 | 0.152 | 84.8 | 87.4 |

g10 FAIL (L7, L1 under 0.25 alone; L2, L7, L1 rows at or above 70). Before also FAIL (L7 0.258, L1 0.161, same rows above 70). Report only; no levers added.

## Docker (tests-only)

One nohup chain, TS 20261024T200412-04ba, warm image reused (tests/Dockerfile unchanged), copies from live kit exe_copy.py (plain, --owner-only, --stub), log `/tmp/opencode-logs/sentinel-policy-recompute-p12v3r3-20261024T200412-04ba/runs.log` (ALL_DONE 20:09:12, every rc=0), jobs `/tmp/harbor-jobs-p12v3r3/sentinel-policy-recompute-20261024T200412-04ba`.

| run | reward (tests-only) |
| --- | --- |
| oracle-1 | 1.0 |
| oracle-2 | 1.0 |
| oracle-3 | 1.0 |
| owner-1 (owner-only) | 1.0 |
| nop-1 | 0.0 |
| stub-1 (7 empty artifacts) | 0.0 (0 of P 33) |

Final tree sha (master method): b0332e7aa626 (issue 88d1009c6a4c). No `__pycache__` in BUNDLE.

## QC_RULINGS rows

- TS-26 | rebuild check fed the agent's own resolve output into init/set | fix: feed the authoritative reference values, check grades init/set coercion, canonical writing and provenance; weight 3 unless a real wrong program fails it and passes the resolve check.
- TS-13 | merged shipped check | split per artifact when the master orders it; measure the v0 agent program first: here 5/31 -> 12/33, accepted by Ayush.
- JD-9 | process criterion paid by every passer | "reproduces a shipped wrong value with a command and names it before changing the code"; oracle prints the wrong values from a scratch copy when the shipped tool crashes.
- J4/JD-18 | only a negative except-clause criterion | one positive w3 maintainability criterion (emberforge v9 wording); delete the overlapping negative.
- AL-27 | rule with no failing mutant | add one hidden reseeded row where only that rule decides (OV-K042-c0).

## Deviations from master directions

none (F1 weight set to 3 as directed when no real program separates; trap v0 FAIL reported, not hidden, after Ayush chose "Split as directed").

## Lessons for the master

- Splitting a merged shipped check always pays a correct-on-shipped agent program; quote the v0 delta in the direction (here +4 of 33) | template_change: prompts/templates P12 fix step "trap survival" add "M-splits: predicted v0 gain = split weight sum" or no change: covered by playbook s3 measurement.
- F1-style de-duplication also moves the v0 program (+3 here) because init/set are usually right | no change: master already flagged m2 as intended; extend that note to v0.
- instruction.md still says "decoys" twice (agent-visible author word, outside P2 scope; precheck does not grep instruction prose) | template_change: master_chat_tasks/tools/precheck.sh leak grep add instruction.md words.
- Shipped tool that crashes on the image Python makes "run shipped tool" criteria print no value; check R6/R7 pairs against the real shipped run | no change: task-specific.
- stacking_check misclasses hidden init/set rebuild as shipped_only and lumps unmatched negatives into one AL-28 FAIL | template_change: master_chat_tasks/tools/stacking_check.py act classifier.
