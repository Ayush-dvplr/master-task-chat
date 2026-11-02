# G3 check (board 653bf5d, 29 Oct 2026 02:10-02:15 IST)

Checklist = `MT/knowledge/PROMPT_CHECKLIST.md` (CL). Templates in `MT/prompts/templates/`. Read only; nothing edited.
Section 0 (CL:5-9, handoff message) is about the master's message, not template text: N/A for all four except where noted.
Note on CL:25: it still says `_COMMON_RULES_v4.md`; upgrade plan A5 (`UPGRADE_PLAN_v2.md:84`) makes `_v5` the target, so `_v5` is scored PASS. The checklist line itself is stale (see Fixes).

Totals: P16 4 fails, P17 2, P14 v2 3, P15 v2 7; extra checks 8 fails.

## P16_ql_report_triage_v1.md

| checklist item (file:line) | result | template line | note |
|---|---|---|---|
| CL:12 board id + name_session first and last | PASS | P16:7 "Board id: `[[SHA]]`"; P16:10 "First thing and last thing" | |
| CL:13 own saved path, re-read after compaction | PASS | P16:7, P16:11 | |
| CL:14 survival section | PASS | P16:9-14 | ALL_DONE part N/A: "No Docker" (P16:13) |
| CL:17 one bundle, scope in first paragraph | PASS | P16:7 "one Harbor 0.24 bundle" | |
| CL:18 absolute, quoted input paths | FAIL | P16:12 "`master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md`, `knowledge/QC_FIX_PLAYBOOK_v3.md` ..."; P16:25 "`Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`", "`master_chat_work/20261024_process/qc_reverse/A/checks.json`" | relative; `knowledge/` is relative to MT, the others to T. Inputs P16:21-23 are absolute |
| CL:19 OUT + deliverables named | PASS | P16:26, P16:42-43 | |
| CL:20 stops | PASS | P16:45-48 | |
| CL:21 result json, "sha", fields, "It must parse" | PASS | P16:43 | |
| CL:22 final reply cap | PASS | P16:50 "at most 8 lines" | |
| CL:25 common rules | PASS | P16:12 `_COMMON_RULES_v5.md` | |
| CL:26 LEVER_RULES_v3 by path | PASS | P16:12 | section names: see extra E4 |
| CL:27 LEAK_LIBRARY + QC_RULINGS + QC_FIX_PLAYBOOK where QC fixes are designed | FAIL | P16:12 reads playbook and QC_RULINGS only; P16:38 designs fix lines ("`<id> \| FIX / KEEP / REBUT \| row <id> ...`") | `LEAK_LIBRARY.md` missing |
| CL:28 plans / lessons folded in | PASS | P16:16 (Q2 a), P16:42 (Q5 a) | |
| CL:29 blind prompt | N/A | | |
| CL:32 no git writes | PASS | P16:13 | |
| CL:33 never edit kit/harness/bundles/records | PASS | P16:13 "READ ONLY everywhere" | |
| CL:34 never explain a trap (W1) | FAIL | P16:17 "`grep -niE \"lever\|trap\|probe\|harden\|session\|board\" OUT/TRIAGE.md` inside `## Reply notes` must find nothing"; P16:42 "no lever, trap or tool names" | (a) the grep runs on the whole file and cannot be limited to one section; P16:38 makes every direction line contain "levers:", so it always hits. (b) word lists differ: P16:17 lacks `tool`, P16:42 lacks probe/harden/session; QL_REPLY_TEMPLATE:3 forbids "lever, trap, probe, harden, tool or session names" |
| CL:35 Docker clash rules | N/A | P16:13 "No Docker" | |
| CL:36 oracle x3 | N/A | no runs | |
| CL:39 evidence file:line | PASS | P16:15 | |
| CL:40 INFERRED / did not run / UNVERIFIED | PASS | P16:15 | "did not run" wording absent; nothing is run except script checks (minor, not counted) |
| CL:41 tests-only / artefact baselines | N/A | no scores produced | |
| CL:44-45 stacking, QC_DEFENCE | N/A | triage, not build | |
| CL:46 fix-directions block: FIX/KEEP/REBUT, playbook row, no NEVER-column fix, difficulty kept | FAIL | P16:38 "`<id> \| FIX / KEEP / REBUT \| row <id> \| ... \| levers: <L>=none/harder/easier`" | format, row and lever effect present; the "no line uses a NEVER-column fix" rule is missing |
| CL:47 trap survival | N/A | not a fix prompt (P12 v4 does it) | |
| CL:48 `## Lessons for the master` | PASS | P16:42 | |

## P17_ql_handback_v1.md

| checklist item (file:line) | result | template line | note |
|---|---|---|---|
| CL:12 board id + name_session first and last | PASS | P17:13, P17:16 | |
| CL:13 saved path, re-read | PASS | P17:13, P17:17 | |
| CL:14 survival section | PASS | P17:15-21 | ALL_DONE N/A (P17:19 "No Docker") |
| CL:17 scope | PASS | P17:13 | |
| CL:18 absolute, quoted input paths | FAIL | P17:18 "`master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md`, plus `knowledge/LEVER_RULES_v3.md`"; P17:25 "TASKS_INPUT: `Terminal_2.0_Harbor_Harness/Tasks_INPUT/[[SLUG]]/`" (and OUTPUT_RFP, BUNDLE); P17:37 "`python3 master_chat_tasks/tools/trajectory_readout.py`"; P17:47 "`jobs/[[SLUG]]/trajectory/<model>/Run N`" | all relative, with mixed roots; P17:47 does not say which `jobs/` (INFERRED: `Terminal_2.0_Harbor_Harness/jobs`, which exists) |
| CL:19 OUT + deliverables | PASS | P17:27, P17:53 | |
| CL:20 stops | PASS | P17:56 | |
| CL:21 result json | PASS | P17:53 | |
| CL:22 final reply cap | PASS | P17:58 | |
| CL:25 common rules | PASS | P17:18 `_v5` | |
| CL:26 LEVER_RULES_v3 by path | PASS | P17:18 | section names: E4 |
| CL:27 QC_RULINGS / QC_FIX_PLAYBOOK where QC fixes are designed | FAIL | P17:50 "which of his hunks to take, and which to drop with a reason"; P17:40 judges W1 / IN-15 / Law-1 conflicts; P17:18 reads only _COMMON_RULES_v5 + LEVER_RULES_v3 | INFERRED applicability: taking or dropping QL hunks is a QC-fix decision, so it needs `QC_RULINGS.md` (QL rulings) and `QC_FIX_PLAYBOOK_v3.md` |
| CL:29 blind | N/A | | |
| CL:32-33 git, no edits | PASS | P17:9, P17:19 | |
| CL:34 W1 | PASS | P17:40 checks W1 / IN-17 in his edit | |
| CL:35-36 Docker, oracle | N/A | P17:19 | |
| CL:39-40 evidence, INFERRED, UNVERIFIED | PASS | P17:21 | |
| CL:41 artefact baselines | PASS | P17:37 "Say which bytes the run was made on" | |
| CL:44-47 gates | N/A | routing only | |
| CL:48 Lessons | PASS | P17:53 | |

## P14_task_analysis_v2.md

| checklist item (file:line) | result | template line | note |
|---|---|---|---|
| CL:12 board id + name_session first AND last | FAIL | P14v2:9 "Board id: `[[SHA]]`" OK; P14v2:14 "First thing: rename this session" | no last-step rename anywhere (P14v2:73-77) |
| CL:13 saved path, re-read | PASS | P14v2:9, P14v2:19 | |
| CL:14 survival section | PASS | P14v2:13-24 | ALL_DONE N/A (P14v2:18 "No Docker") |
| CL:17 one group | PASS | P14v2:5 "groups of up to 4 tasks", P14v2:9 | |
| CL:18 absolute paths | FAIL | P14v2:58 "Compare with `knowledge/QC_RULINGS.md`"; P14v2:54 "compare with `LEAK_LIBRARY.md`" | P14v2:54 is absolute at :11; :58 relative and given nowhere else |
| CL:19 OUT + deliverables | PASS | P14v2:32, :35, :50, :65, :75 | |
| CL:20 stops | PASS | P14v2:47 ARTEFACT handling | no other stop needed |
| CL:21 result json | PASS | P14v2:75 | status only "DONE" (no BLOCKED value); not counted |
| CL:22 final reply cap | PASS | P14v2:77 | |
| CL:25 common rules | FAIL | P14v2:11 reads LEVER_RULES_v3 + LEAK_LIBRARY only | no `_COMMON_RULES_v5.md`; P14 is not one of the exempt P11/P13 |
| CL:26 LEVER_RULES_v3 by path | PASS | P14v2:11 | |
| CL:27 leak library / rulings | PASS | P14v2:11, :54, :58 | playbook N/A (no fixes designed) |
| CL:29 blind | N/A | | |
| CL:32-33 | PASS | P14v2:18 | |
| CL:34 W1 | PASS | P14v2:23 patterns not content | |
| CL:35-36 | N/A | | |
| CL:39-40 | PASS | P14v2:22, :42 | |
| CL:41 artefact baselines | PASS | P14v2:34-47 Phase A | |
| CL:44-47 | N/A | analysis | |
| CL:48 Lessons | PASS | P14v2:73 | |

Draft fidelity (`U/R4_teammate_repo/drafts/P14_task_analysis_v2.md`, `diff P14_task_analysis_v1.md P14_task_analysis_v2.md`):

| draft item | landed at | status |
|---|---|---|
| A-new-1 score conventions (draft:6) | P14v2:41 | landed, PLUS a new clause "tests negatives on `passed=True`" (not in draft:6; source is P15 draft:64 and `R4/scripts/losses.py:4-5`, checked on one task, FINDINGS.md:9 "No test negative fired anywhere") |
| A-new-2 no failure messages (draft:7-11) | P14v2:42 | landed |
| A-new-3 identifiability (draft:12-16) | P14v2:43 | landed (task ids dropped, fine for a template) |
| A-new-4 instructed caps (draft:17) | P14v2:44 | landed |
| A-new-5 channel split, 50/P (draft:18) | P14v2:45 | landed, adds "P = judge positive weight" (clarification) |
| A-new-6 band source (draft:19) | P14v2:46 | landed |
| B-new-1 weight geometry (draft:22) | P14v2:60 | landed |
| B-new-2 judge composition (draft:23) | P14v2:61 | landed |
| B-new-3 time use (draft:24) | P14v2:62 | landed |
| result json fields (draft:27) | P14v2:75 | all 6 landed |
| CHANGELOG line (draft:29; plan D2 `UPGRADE_PLAN_v2.md:208`) | CHANGELOG.md:52 | landed |
| outside draft | P14v2:1, :3 (header, changes note); P14v2:11 `LEVER_RULES_v1.md (sections 0-4)` -> `LEVER_RULES_v3.md (sections 1C, 1D, Law-1, gate v3.7)` | path change is planned (CL:26, CHANGELOG:52); the `passed=True` clause above is the only unplanned change in substance |

## P15_research_angle_v2.md

| checklist item (file:line) | result | template line | note |
|---|---|---|---|
| CL:7 paste-only file, nothing to cut | FAIL | P15v2:62-67 "## Proposed prompt changes (for v3, from this R4 run) ... CHANGELOG line (proposed): ..." | left over from the R4 draft and placed below `=== PASTE BELOW ===` (P15v2:20), so it goes to every session and to Gemini/ChatGPT. Items 2-3 are already in P14 v2 (:41, :45) |
| CL:12 board id line + name_session | FAIL | P15v2:51 "Board id `[[SHA]]`. First and last thing: ..." | no colon. `tools/name_session.py:148` matches `needle = f"Board id: \`{sha}\`"`, so the rename finds no session |
| CL:13 own saved path | FAIL | P15v2:52 "re-read this prompt" | no `[[PROMPT_PATH]]`/saved-path line anywhere |
| CL:14 survival section | FAIL | P15v2:52-53; P15v2:55 "Copy its ranked UNTRIED list into OUT/TODO.md" | no `OUT/LOG.md` |
| CL:17 scope | PASS | P15v2:22 | |
| CL:18 absolute paths | PASS | P15v2:12 absolute default; `[[CORPUS]]` filled by master | |
| CL:19 OUT + deliverables | PASS | P15v2:53, :58-59 | |
| CL:20 stops | N/A | | no stop needed by this step |
| CL:21 result json | PASS | P15v2:59 | |
| CL:22 final reply cap | PASS | P15v2:59 "5 lines max" | |
| CL:25 common rules | FAIL | P15v2:50-60 own-session rules | no `_COMMON_RULES_v5.md` for own / own-repo sessions |
| CL:26 LEVER_RULES_v3 for hardness/analysis prompts | FAIL | P15v2:24-44 context on levers; no LEVER_RULES reference | INFERRED applicability (research on hardness levers) |
| CL:27 | N/A | no levers designed | |
| CL:32-33 | PASS | P15v2:53 | |
| CL:34 W1 | PASS | P15v2:27-28 | |
| CL:39 evidence | PASS | P15v2:18, :48 | |
| CL:40 INFERRED / did not run / UNVERIFIED | FAIL | P15v2:48 "`C<n>.<k> \| claim \| evidence \| confidence \| type`" | own-session rules never ask for INFERRED or UNVERIFIED marks |
| CL:41, 44-47 | N/A | | |
| CL:48 Lessons | PASS | P15v2:59 | |

## Extra checks

Gate text (`grep -n "final < 40\|final<40"`): P16:16, P16:47; P17:46, P17:48 (2 each) -> PASS.
`grep -n "final < 50\|under 50\|\[\[FINAL_GATE\]\]"` on all 4 -> no hit (rc=1) -> PASS.
`grep -n "_COMMON_RULES\.md"` on all 4 -> no hit (rc=1); only `_COMMON_RULES_v5` (P16:12, :48; P17:18) -> PASS.
`grep -n "LEVER_RULES_v[12]"` on all 4 -> no hit (rc=1); v3 only (P16:12, P17:18, P14v2:3, :11) -> PASS.

Paths named by the templates: all exist (`ls` each): tools/issue.py, name_session.py, trajectory_readout.py, stacking_check.py, peer_manifest.py, registry/peer_tasks.json, knowledge/PROMPT_CHECKLIST.md, QC_FIX_PLAYBOOK_v3.md, QC_RULINGS.md, FP_DOSSIER.md, LEVER_RULES_v3.md, LEAK_LIBRARY.md, ANGLES.md, prompts/templates/_COMMON_RULES_v5.md, prompts/issued/_adhoc, master_chat_work/_ql, master_chat_work/bundles, harness Tasks_INPUT, Output_RFP, Input_Bundle_QC (+ 01/03/04/05 files), harness jobs, `master_chat_work/20261024_process/qc_reverse/A/checks.json`, `U/R4_teammate_repo`. Templates named by version exist: P9 v4, P11 v3, P12 v4, P13 v2. PASS.

Placeholders and the "Master:" header:

| template | placeholders | header says how to fill |
|---|---|---|
| P16 | SHA, PROMPT_PATH, OUT, SLUG, TS, TREE_SHA, N, QL_REPORT_PATH, LAST_QC_REPORT, KEPT_PATH_OR_NONE, LAST_QC_COPY, QC_DEFENCE_PATH_OR_NONE | SLUG/TS/N/QL_REPORT_PATH yes (P16:3 save path, numbering); TREE_SHA no source named (registry); rest "Fill every `[[...]]`" only. SHA/PROMPT_PATH/OUT conflict with issue.py (E3) |
| P17 | SHA, PROMPT_PATH, OUT, SLUG, TS, ZIP_PATH, ZIP_SHA, REQUEST, REQUEST_PATH, TREE_SHA, LAST_QC_COPY, PENDING_DIFF_OR_NONE | ZIP_PATH/ZIP_SHA/REQUEST_PATH/REQUEST yes (P17:4-6); rest generic. Same issue.py conflict (E3) |
| P14 v2 | SHA, PROMPT_PATH, OUT, N_TASKS, GROUP, TASK_ROWS | generic only ("Master fills `[[...]]`", P14v2:5); TASK_ROWS format given by the table header P14v2:27 |
| P15 v2 | ANGLE, ANGLE_BRIEF, QUESTIONS, ANGLES_FILE, CORPUS, SHA, OUT | P15v2:10 lists 5; SHA and OUT not listed (E5) |

E1 tree-sha method and spaces (P16:29, P17:32), FAIL x2. Same pipeline as the `intake.py:46-71` docstring, but BSD xargs `-I` mangles names. Test in `/tmp/653bf5d-t` (removed):
```
single-space names, -not -path './trajectories/*':  shell 44f329f8d5a5 == intake.tree_sha 44f329f8d5a5   (OK)
"sub dir/c  d.md":  shasum: ./sub dir/c d.md: No such file or directory   (double space collapsed)
"x/  lead.txt":     shasum: ./x/ lead.txt: No such file or directory       (leading spaces)
"it's.txt":         xargs: unterminated quote, exit=1
print0 variant with all three names: e7c645f8d18d == intake.tree_sha e7c645f8d18d
```
The trajectories exclusion (`-not -path './trajectories/*'`) removes only the top-level trajectories/ and keeps `sub dir/trajectories/keep.txt` (correct). CHANGELOG.md:50 says "tree-sha method with spaces", but only single spaces work.

E2 P17 trajectories exclusion, FAIL. P17:32 needs the zip bundle sha "excluding trajectories/", but its method note says "(for Output_RFP add `-not -path './trajectories/*'` to find)", so it does not say to add it for the zip bundle. P17:35 "Run `diff -rq` and `diff -U0 -r` of the zip bundle (excluding trajectories/)" gives no `-x trajectories`. P16:29 is fine: the exclusion is stated for Output_RFP.

E3 issue.py placeholders (P16:3, P17:7), FAIL x2. Both say to issue with `tools/issue.py`. `issue.py:143-144` exits with "REFUSED: draft has no <SHA> placeholder", and only `<SHA>`, `<PROMPT_PATH>`, `<OUT>` are replaced (`issue.py:174`). The templates use `[[SHA]]`, `[[PROMPT_PATH]]`, `[[OUT]]` and tell the master to "Fill every `[[...]]`". If he puts in a real sha, issue.py refuses the draft. Nothing says to write `<SHA>` instead.

E4 LEVER_RULES section names (P16:12, P17:18), FAIL. Both say "`knowledge/LEVER_RULES_v3.md` sections Law-1 and freeze". The headings in LEVER_RULES_v3 (`grep -n "^#"`) are 0, 0b, 1, 1A, 1C, 1D, 1b, 2-8. Law-1 is a bullet in 1C (:87-88). Freeze text sits in section 6 (:241). No section is named either. INFERRED impact: a worker may read the whole 50 KB+ file or the wrong part.

E5 P15 header (P15v2:10), FAIL. It lists the placeholders to fill but leaves out `[[SHA]]` (P15v2:51, :59) and `[[OUT]]` (P15v2:53).

E6 P14 v2 fidelity (P14v2:41), FAIL (low). It adds "tests negatives on `passed=True`", which is not in draft:6. It is supported only by `losses.py:4-5` on one task, and `FINDINGS.md:9` reports that no test negative fired anywhere.

P15 `[[ANGLES_FILE]]` default, PASS. P15v2:12 sets "`/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/ANGLES.md`" and the file exists (5457 B). The version rule is at P15v2:13 (">= 1 angle rated S or M ... Two runs in a row with only W/N angles -> the master stops the loop"), PASS. Observations, not counted: `knowledge/ANGLES.md:3` still says each run "appends its own rows to the log below", which conflicts with P15v2:12 "Sessions never write it". ANGLES.md has no "Prompt versions" table yet (headings: `## Log (angles tried)` :5, `## Untried angles, ranked` :21). Plan D3 has the master add it after the first run.

`_COMMON_RULES_v5.md` rule 18 (:50), PASS. It reads: "Polls on long jobs: `sleep 120; echo poll <n>` with a rising n (or a changing command); never repeat an identical tool call 3 times in a row. opencode's doom_loop guard denies the 3rd identical call and stops your step (metered QC 28 Oct 16:53; R5-06)." The wording is clear, and it fits Always 3 (waits under 4 min). Numbering: Never 1-11 (:20-30), Always 1-18 (:33-50), with no gap and no duplicate.

QL_REPLY_TEMPLATE W1, PASS. `grep -niE "lever|trap|probe|harden|tool|session|board"` hits only line 3, which is the rule itself. The reply body (:7-27) has none of those names.

CHANGELOG, PASS. CHANGELOG.md:50 (P16/P17/QL_REPLY), :51 (P15 v2), :52 (P14 v2) are present.

## Fixes for the master

- P16:12. Old: "`master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md`, `knowledge/QC_FIX_PLAYBOOK_v3.md`, `knowledge/QC_RULINGS.md`, `knowledge/FP_DOSSIER.md` (if present), and `knowledge/LEVER_RULES_v3.md` sections Law-1 and freeze". New: the same files as absolute quoted paths under `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/`, adding `knowledge/LEAK_LIBRARY.md`, and ending "`knowledge/LEVER_RULES_v3.md` section 1C (Law-1 bullets) and section 6 (freeze / push order)". Covers CL:18, CL:27, E4.
- P16:25. Old: "`Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`", "`master_chat_work/20261024_process/qc_reverse/A/checks.json`". New: "`/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`", "`/Users/mac/Desktop/Terminal Bench/master_chat_work/20261024_process/qc_reverse/A/checks.json`" (CL:18).
- P16:17. Old: "`grep -niE \"lever|trap|probe|harden|session|board\" OUT/TRIAGE.md` inside `## Reply notes` must find nothing". New: "`awk '/^## Reply notes/{f=1;next} /^## /{f=0} f' OUT/TRIAGE.md | grep -niE \"lever|trap|probe|harden|tool|session|board\"` must find nothing" (CL:34).
- P16:42. Old: "(one plain sentence per finding, no lever, trap or tool names)". New: "(one plain sentence per finding, no lever, trap, probe, harden, tool or session names)" (CL:34).
- P16:38. Append: "No line uses a fix from the playbook NEVER column." (CL:46)
- P16:29 and P17:32 (tree sha). Old: "`cd <DIR>; find . -type f | LC_ALL=C sort | xargs -I{} shasum -a 256 \"{}\" | shasum -a 256 | cut -c1-12`". New: "`cd <DIR>; find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -c1-12`", with `-not -path './trajectories/*'` before `-print0`. Matches `intake.tree_sha` (E1). Also fix the `intake.py:48` docstring and CHANGELOG.md:50 "with spaces" to match.
- P17:32. Old: "(for Output_RFP add `-not -path './trajectories/*'` to find)". New: "(for Output_RFP and the zip bundle add `-not -path './trajectories/*'` before `-print0`)" (E2).
- P17:35. Old: "Run `diff -rq` and `diff -U0 -r` of the zip bundle (excluding trajectories/)". New: "Run `diff -rq -x trajectories` and `diff -U0 -r -x trajectories` of the zip bundle" (E2).
- P16:3 and P17:6. Append: "Write `[[SHA]]` as `<SHA>`, `[[PROMPT_PATH]]` as `<PROMPT_PATH>` and `[[OUT]]` as `<OUT>`: issue.py fills them and refuses a draft without `<SHA>`. `[[TREE_SHA]]` = registry `pipeline.tree_sha`." (E3)
- P17:18. Old: "`master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md`, plus `knowledge/LEVER_RULES_v3.md` sections Law-1 and freeze". New: absolute paths for both, plus `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/QC_RULINGS.md` and `.../knowledge/QC_FIX_PLAYBOOK_v3.md`, and the LEVER_RULES section names as for P16:12 (CL:18, CL:27, E4).
- P17:25. Old: "`Terminal_2.0_Harbor_Harness/Tasks_INPUT/[[SLUG]]/`", "`Terminal_2.0_Harbor_Harness/Output_RFP/[[SLUG]]/`", "`master_chat_work/bundles/[[SLUG]]/`". New: each prefixed with `/Users/mac/Desktop/Terminal Bench/` (CL:18).
- P17:37. Old: "`python3 master_chat_tasks/tools/trajectory_readout.py`". New: "`python3 \"/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/trajectory_readout.py\"`" (CL:18).
- P17:47. Old: "`jobs/[[SLUG]]/trajectory/<model>/Run N`". New: "`/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/jobs/[[SLUG]]/trajectory/<model>/Run N`" (CL:18; INFERRED root).
- P14v2:76 (before "Final reply"). Add: "Last step: run `python3 \"/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py\" [[SHA]]` again." Optionally edit :14 "First thing:" to "First thing and last thing:" (CL:12).
- P14v2:11. Append: "Also read `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md` (Never and Always; the bundle-edit rules do not apply, you edit nothing)." (CL:25)
- P14v2:58. Old: "`knowledge/QC_RULINGS.md`". New: "`/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/QC_RULINGS.md`" (CL:18).
- P14v2:41. Old: "rubric negatives apply on `passed=False`; tests negatives on `passed=True`; this reconciles on 90/90". New: either drop "tests negatives on `passed=True`;", or keep it as "tests negatives on `passed=True` (seen on one task, 725e575c, R4 losses.py:4-5; none fired in the 90)". Master decides (E6).
- P15v2:62-67. Delete the "## Proposed prompt changes (for v3, from this R4 run)" block and the proposed CHANGELOG line. Move them to `knowledge/ANGLES.md` "Prompt versions", or drop them (CL:7).
- P15v2:51. Old: "Board id `[[SHA]]`. First and last thing:". New: "Board id: `[[SHA]]`. This prompt is saved at `[[PROMPT_PATH]]`. First and last thing:" (CL:12, CL:13).
- P15v2:52. Append: "Keep `OUT/TODO.md` and `OUT/LOG.md` (IST time, command, result) current." (CL:14)
- P15v2:53. Append: "Read `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md` and `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v3.md` (sections 1A, 1C, 1D, 8) before step 1." (CL:25, CL:26)
- P15v2:57. Append: "Mark inferred claims INFERRED, unchecked ones UNVERIFIED, unmeasured ones \"did not run\"." (CL:40)
- P15v2:10. Old: "Fill `[[ANGLE]]`, `[[ANGLE_BRIEF]]`, `[[QUESTIONS]]`, `[[ANGLES_FILE]]`, `[[CORPUS]]`". New: the same list plus "`[[SHA]]`, `[[PROMPT_PATH]]`, `[[OUT]]`" (E5).
- knowledge/ANGLES.md:3 (not a template, so not counted). Old: "appends its own rows to the log below". New: "writes its rows to its own OUT/ANGLES.md; the master merges them here".
- knowledge/PROMPT_CHECKLIST.md:25 (not a template, so not counted). Old: "`_COMMON_RULES_v4.md`". New: "`_COMMON_RULES_v5.md`".
