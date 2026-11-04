STEPS 3, 4 AND 5 REPORT (rollout steps 3 to 5, tags mc2-v2.3, mc2-v2.4, mc2-v2.5). Helper W1-045, 4 Nov 2026 15:15 IST.

Worktree W = /tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad/mc2 (branch mc2-v2).
Test folder T = /tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad/mc2_test (simulated ROOT with the step 0 data copy).
Nothing was pushed, no branch was checked out, nothing in /home/user/master-task-chat changed except this folder. kit_watch.py save was never run on a real snapshot (only inside the temp folders of its unit test). Full outputs: upgrade_plan/tmp/W1-045/logs/.

1. COMMITS AND TAGS (in W only, author Claude <noreply@anthropic.com>, both attribution lines at the end of each message)

mc2-v2.3  7634e0e2876b7316ba49282aaaa4deb81a355397  "mc2-v2.3: rollout step 3 (templates manifest, fill tokens, issue.py checks and runner, mc2 names)"  36 files
mc2-v2.4  6d5ee6b491ef50f36d653ceb512d04326240fcef  "mc2-v2.4: rollout step 4 (regression check script, minor decisions, P12 and P16)"  12 files
mc2-v2.5  c7b0592a7b87449819a9e07066f14c651bf36af7  "mc2-v2.5: rollout step 5 (kit watch, classify prompt, card kit line)"  10 files
All on top of mc2-v2.2 (37f2a6d7). git diff --stat mc2-v2.2 mc2-v2.5: 45 files, 2808 insertions, 321 deletions. git status is clean.

2. SMALL FIXES (inside the mc2-v2.3 commit)

1. master_chat_tasks/knowledge/PATTERNS.md and CONFIRM.md: byte copies of upgrade_plan/knowledge/ (no secret found by grep). INDEX.md rows added. MASTER_RECOVERY part A point 3c (knowledge/PATTERNS.md) now resolves.
2. knowledge/BUILD_RULES.md holds only the final values: LEVERS primary lever at least 40 and at most slip_cap_pct (50) percent; GRADING ONE SLIP CAP (per row or per field, never one whole document per run as the only check; "tests compare whole documents per hidden run" removed); RUBRIC at most what_if_max (3) what if criteria per judge; LIMITS time limit at least time_limit_factor (2) times the reference time on a busy machine, oracle runs 2 by day, in auto mode and in the final QC; OLD CLASHES C39 without "4x"; the PL ANSWERS paragraph keeps only the lines not folded in above. grep finds no "4x", "at most 6", "3, 2 in auto" or "5 once" left.
3. tools/board.py rebuilds the card through card_hook.py after new, set and md (same pattern as the other four tools; stdout of new stays the sha only). card_hook.py docstring names board.py. test_state_card.py has a board.py test (11 tests).
4. README.md: issue.py row now says warnings, refusal only for dropped, killed or parked, runner and hash8, --render; scratch line points at ROOT/_runs/<YYYYMMDD>/<slug>/mc2-<step>-<ts>-<hash8>/{scratch,logs}/ and /tmp/mc2/locks/; long job logs in the run folder; template_check, regression_check, minor_decisions and kit_watch rows; layout rows for CURRENT.json, prompts/rendered/ and minor_decisions.jsonl.

3. STEP 3 (mc2-v2.3)

1. prompts/templates/CURRENT.json: families _COMMON_RULES, P1, P2, P4, P9 to P17, QL_REPLY active with their current file and history; P3, P5, P6, P7, P8 retired (current null). P4 is active ("kept for rebuild", issue.py kind rebuild).
2. Templates edited in place (14 current files; history and retired files untouched), each with one "vN in-place mc2-v2.3" note line and, for issued templates, a "Template: <file>" line at the top of the paste part. Changes per P10_TEMPLATES.md section 2, no further rewriting:
   a. dropped: SHAPE, HARDNESS SOURCES, BREADTH TARGET and S codes (P2 inputs are now PRIMARY LEVER and EXTRAS); old gates and aims; count cap 35 and "no count cap"; round caps, ROUND LIMIT and "refuses a third fix round"; blinds before QC and blind programs as lever judges (P2 Phase 0b and P13 now optional diagnostics); "QC-safe" edits; misread levers as extras; "never state a size"; holes list; parking and the kill rule; J1 "no figure criterion" and J4 behavioural wording; reflex gate; whole document only grading ("graded whole", "whole-document exact"); the COUPLING "sentence that states it" demand (now optional, the output field or definition, BR-SL2).
   b. added from the rules in force: fix map rows (FIX_MAP.md) and BUILD_RULES QC FIX STEPS instead of the playbook and G1 to G7; lever check against the paid run program (CR2) with NO CORE; QC pass per RULES_IN_FORCE (ENTRY 88) in _COMMON_RULES and P12; no softening without Ayush's word; one deciding sentence per value (BR-SL1, BR-SL2) in P2.
   c. fill tokens: [[ROOT]] for all 119 old root paths, <GATE>, <GATE_TESTS>, <GATE_FINAL>, <DESIGN_BAR>, <NO_CORE_KEEP_PCT>, <SOFT_CAP>, <HARD_CAP>, <SLIP_CAP>, <WHAT_IF_MAX>, <LEVER_KEEP_PCT>, <TIME_FACTOR>, <ORACLE_RUNS>, <ORACLE_RUNS_AUTO>, <ORACLE_RUNS_FINAL>, <RUNS>, <PAID_MODEL>, <DOCKER>, <DOCKER_CHECK>, <SYSTEM_ID>, <HASH8>.
   d. rules pointers: RULES_IN_FORCE.md, knowledge/BUILD_RULES.md and knowledge/PATTERNS.md instead of LEVER_RULES_v3; P4 reads _COMMON_RULES_v5 instead of _COMMON_RULES_v2; P16 and P17 name families without versions.
3. tools/fill_tokens.py (new, shared): token values from settings.json and ROOT. Values today: gate tests < 85, rubric < 85, final < 40; design bar 35; oracle runs 2 / 2 / 2; time factor 2; slip cap 50; what if 3; soft 70, hard 100; lever keep 90; runs 1; paid model claude-opus-5; Docker "--memory 4096m --cpus 2"; system id mc2.
4. tools/issue.py:
   a. fills [[ROOT]] and every token in the draft and in OUT, then lints; a known token settings cannot fill is a hard refusal; LIVE_GATE now comes from settings (85/85/40 only as fallback).
   b. every current template the draft names by path (prompts/templates/<file>) is rendered, filled, to prompts/rendered/<sha>/<file> and the prompt points at that copy. This is needed because sessions read _COMMON_RULES_v5.md straight from disk; rendered/ is DATA (.gitignore, backup list).
   c. template check from CURRENT.json: a retired family is refused; an older version or an unknown file is a WARNING, issued and logged to decisions.jsonl.
   d. caps (2 fix rounds per QC, 2 QC rounds, QC or harden after pass, 3 edit rounds, 8 session time box) are warnings, issued and logged (Q120, T23); only a dropped, killed or parked task is refused unless --override.
   e. --runner from settings runners.options; default runners.default_by_step (blind oc-opus-5, else oc-opus-5.5); "runner" and "hash8" written into the board row (S9); a GPT runner needs "strictly do not run subagents" (R32).
   f. LEGACY fixed: rebuild maps to P4, P10 is no longer counted as harden.
   g. issue.py --render FILE prints a template filled from settings (P1 and the QL reply are not issued through issue.py); --lint fills before linting and skips template history lines for the oracle count.
5. System id in names (SYSTEM_ID.md): run folders <SYSTEM_ID>-<step>-<TS>-<HASH8> (qc, fixgate, gate, scratch, blind), locks /tmp/<SYSTEM_ID>/locks/, kill containers --name <SYSTEM_ID>-kill-<slug>-<HASH8> --label <SYSTEM_ID>.system=<SYSTEM_ID>, QL scratch under /tmp/<SYSTEM_ID>/ (all in templates); repackage_one.py /tmp/mc2/repack-<slug>-<ts>-<hash8>; lever_dose.md /tmp/mc2/dose-...-<HASH8>; auto.py run folders runs/<ts>_mc2-<label> (default label mc2-auto); precheck.sh reads the kit from settings paths.kit (PRECHECK_KIT overrides).
6. tools/template_check.py from W1-032 adapted: defaults to W's master_chat_tasks, final settings keys, extra RETIRED classes (WHOLEDOC, COUPLING, WHATIF6), any LEVER_RULES or playbook pointer, SYSID class (old root, /tmp path, cd /tmp, docker --name, _runs folder without the system id or [[ROOT]]), TOKEN class, retired family pointers, manifest coherence. Exit 0 on the current templates.
7. tests/test_issue_mc2.py (new, 9 tests): tokens, ROOT and rendered _COMMON_RULES; retired refused; older warned and issued; caps warn; parked refused unless override; runner defaults and choice, GPT line; unfillable token; --render; template_check clean then flags 7 planted conflicts. test_upgrade_tools.py A1Issue expectations moved from refusals to warnings.
8. upgrade.py release text v2.3, test_issue_mc2.py in the self tests, prompts/rendered in DATA. SYSTEM_VERSION v2.3.

4. STEP 4 (mc2-v2.4)

1. tools/regression_check.py: REGRESSION_CHECK.md steps 1 (byte diff of tests/, or --scope all, every hunk named by a plan line file:N, file:N-M or file:*), 2 (lever keep share from loss.py outputs, per lever before and after, optionally only the checks LEVERS.md maps to the lever, against settings lever_keep_pct 90), 3 (oracle, nop, owner, stub rewards read from result.json or verifier/reward.json in a run folder, at least settings oracle_runs.day oracle runs) and 7 (changed graded literals listed; with --deciding-map each needs a cited AFTER line that holds it). Writes REGRESSION.md and regression.json with --out. Exit 0, 1 FAIL, 2 usage.
2. tests/test_regression_check.py (5 tests): a synthetic copy of a past fix pattern that lost a lever (a TS-19 "hidden input outside a stated bound" fix clamped the hidden generator, removing the case that fires the lever, and moved the expected value). The plan names both hunks (step 1 PASS) but the L1 variant loses 8.0 points before and 0.0 after, keep 0 percent: step 2 FAIL, verdict FAIL (logs/s4_regression_sample.txt). Also: an unnamed hunk fails step 1; a fix that keeps the lever passes; DECIDING_MAP catches a value its cited line does not hold; run folder oracle and nop pass, a nop of 0.1 and too few oracle runs fail. loss.py itself produces the loss outputs from synthetic reward-details.json.
3. tools/minor_decisions.py (ENTRY 88): record (refused without Ayush's verbatim words), propose (per check id, reuse of the closest earlier decision when the finding text is at least 60 percent alike, else "none: the master proposes"), list. tests/test_minor_decisions.py (2 tests).
4. loss.py also reads any Harbor job folder (rglob verifier/reward-details.json) so variant runs made with harbor run -o can be scored.
5. P12: master duty proposes minors with minor_decisions.py and records Ayush's words before issuing; new input [[QC_COPY]]; Phase 2 step 5 writes OUT/DIRECTIONS.md and per lever loss outputs and runs regression_check.py (rerun after the fixgate runs); deliverables and result json carry the regression verdict. P16: Phase 0 step 2 runs regression_check.py from LAST_QC_COPY to BUNDLE against the post QC directions ([[POST_QC_DIRECTIONS_OR_NONE]]), Phase 1 step 8 minor proposals, directions name FIX_MAP rows.
6. upgrade.py release v2.4, two new self tests and --help checks. SYSTEM_VERSION v2.4.

5. STEP 5 (mc2-v2.5)

1. tools/kit_watch.py from W1-032 adapted: kit default ROOT/<settings paths.kit>; snapshot, FIX_MAP.md, BUILD_RULES.md and RULES_IN_FORCE.md default from master_chat_tasks; save needs --by (empty refused), defaults its folder to knowledge/fingerprints/qc_<head8>/ (never overwritten), moves the old fingerprints/qc.json into archive_<old head8>/qc.json (archive_<old head8>_<time>/ if taken), writes the new qc.json pointing at its qc_text/, logs Ayush's words to decisions.jsonl and prints the rollback copy command; --no-install keeps the W1-032 behaviour. card_line() for the state card.
2. knowledge/KIT_CLASSIFY_PROMPT.md (from W1-032): [[ROOT]] paths, the new check command, a "Prompt file:" line instead of "Template:" (it is not a template family), the save step on Ayush's word.
3. state_card.py kit_line uses kit_watch card_line (plain hash test only if kit_watch fails) and now prefers ROOT's own kit (settings paths.kit) over the snapshot's source path.
4. P10: the QC half uses the kit watch output ([[KIT_WATCH_DIR]]) and the classes; the session only proposes the save command; fingerprint_qc.json dropped.
5. tests/test_kit_watch.py (4 tests): card defaults from settings; save refusals, archive move, new qc.json, decisions row, no overwrite; changed kit gives TS-23 with fix map row 2 and the card line; rollback restores the old snapshot.
6. upgrade.py release v2.5, test_kit_watch.py in the self tests. SYSTEM_VERSION v2.5.

6. CHECKS (TMPDIR in T; T/ROOT refreshed from W before each step with logs/refresh_root.sh <previous tag>)

1. template_check.py on W and on T/ROOT after each step: exit 0, "TOTAL templates 14 conflicting lines 0 SETTING 0 RETIRED 0 POINTER 0 SYSID 0 TOKEN 0 stale pointers outside templates 0 manifest problems 0" (logs/s3_, s4_, s5_template_check.txt). Before step 3 the W1-032 script found 87 conflicting lines in the 13 active templates. With --all (retired families scanned too) 30 lines remain, all in retired files.
2. Self tests in W after step 5: test_issue_mc2 9 OK, test_state_card 11 OK, test_regression_check 5 OK, test_minor_decisions 2 OK, test_kit_watch 4 OK, test_carry_over 6 OK, test_dockfree 5 OK, auto/tests/test_auto.py 75 OK.
3. Data tests on T/ROOT (copies with dir="/tmp" pointed at T/tmp, deleted afterwards), after each step: test_issue_lint 7 OK; test_upgrade_tools A1Issue and A3Status 13 OK (logs/s3_, s4_, s5_tests_data.txt).
4. upgrade.py backup then preflight on T/ROOT, each step: with --old T/old_sim (stand in for the Mac's old folder): exit 0 READY, git commands for the next tag printed; template_check PASS, card PASS, opencode PASS, tool self tests PASS (25 Python files compile, 7 test files OK at v2.5), backup PASS (775 record files). WARN only: known_bundle empty, kit_watch (from v2.5, see 6), the two old system sessions. Plain preflight: exit 1 BLOCKED on the same single FAIL as steps 1 and 2 (the old root /Users/mac/Desktop/Terminal Bench is not reachable here).
5. Card size on T/ROOT data: 7570 B after step 3 and 4, 7741 B after step 5 (7.6 KB, longer QC KIT line), under the 8 KB hard limit, over the 6 KB target (logs/s5_STATE_CARD_mc2_test.md).
6. kit_watch on T/ROOT with a copy of the origin/main kit (57c22748, from W1-032's test data) placed at T/ROOT/Terminal_2.0_Harbor_Harness/Input_Bundle_QC: check exit 1 and card "QC KIT: CHANGED 2 files (05_Alignment_Integrity_QC.md, Final_checklist.md); 0 check ids, 0 in the fix map, 0 in BUILD_RULES; ids unknown for 2 files (snapshot has no text copy)." Same as W1-032 T1. The fingerprints folder was hashed before and after: unchanged.
7. Sample issued prompts for Ayush to read (issued in a scratch copy of T/ROOT, ROOT shown as <ROOT>): logs/s3_sample_issued_P11.md, logs/s3_sample_issued_P12.md and the rendered copy logs/s3_sample_rendered_COMMON_RULES_v5.md (gate, bar, Docker check, mc2 run folder with the hash8 all filled; no token, no [[ROOT]], no old path left).

7. PROBLEMS AND OPEN POINTS

1. Sessions read _COMMON_RULES_v5.md from disk, so issue.py renders a filled copy per issue (prompts/rendered/<sha>/). A session that opens the raw template sees tokens; its first lines say how to resolve them. Prompts issued before mc2-v2.3 are not affected.
2. The templates keep LEVER_RULES labels as tags (W2, W6, G1a, G8a, J2b, H1 to H9, L11) but no longer point at LEVER_RULES_v3.md (now "background only" in INDEX). Most labels carry their meaning inline; a short label glossary (in BUILD_RULES or FIX_MAP) would close the gap. Decision for Ayush.
3. How to text that no rule decides was left as is (probe band, 30 to 60 checks in P1, STACKING_CHECK metrics such as whole_doc_share in result json). It does not conflict with the rules in force.
4. A missing "Template:" line is not refused (P10 open point 2 was never decided); version warnings are issued and logged, not refused, unlike lint warnings which still need --force-lint.
5. Not done (STAGE B or not asked): name_session.py titles mc2-<sha> and the "System: mc2" line (SYSTEM_ID C4, C5); dockslot state dir and labels; auto.py --system marker and MASTER_SESSION in settings; AUTO_POLICY A1 to A13. issue.py --runner uses runners.default_by_step (blind and other), so research defaults to oc-opus-5.5 unless --runner codex-sol-6.1 is given, although settings steps.research names Codex.
6. New master placeholders: P2 [[PRIMARY_LEVER]] and [[EXTRAS]], P9 [[LEVER_CHANGE]], P10 [[KIT_WATCH_DIR]], P11 [[KIT_CHANGED_IDS]], P12 [[QC_COPY]], P16 [[POST_QC_DIRECTIONS_OR_NONE]]. issue.py refuses a draft that leaves one unfilled.
7. Regression check step 2 needs per lever variant scores before and after the fix (Docker runs by the fix session, then loss.py); steps 4, 5, 6, 8 and the judgement halves stay with the session.
8. The ROOT snapshot is still the 25 Oct hash only qc.json, so kit_watch reports CHANGED with ids unknown until Ayush's word; the plan's step 5 check "kit_watch says unchanged" is reached only after the save.
9. state_card now prefers ROOT's own harness kit; if ROOT has no harness clone on the Mac, it falls back to the snapshot's source path, which is the old folder's kit.
10. The card is 7.6 KB, under 8 KB but over the 6 KB target.
11. README read order part A (word for word from step 2) still names knowledge/QC_FIX_PLAYBOOK_v3.md next to FIX_MAP.md; the templates point at FIX_MAP.md only and INDEX marks the playbook REFERENCE.
12. BUILD_RULES OLD CLASHES keeps "a final between 35 and 40" (C13) as typed numbers; it is a rules file, not a template, so template_check does not scan it.
13. Not possible here: harness tests (test_upgrade_tools A2Intake and A4Repackage, test_e3_e6_tools), precheck.sh on a real bundle, Docker, opencode.

8. WHAT AYUSH MUST DO ON THE MAC (nothing here was run; upgrade.py never runs git)

A. Read the diff (git diff mc2-v2.2 mc2-v2.5 in W) and the three sample files in logs/ (step 3 check "Ayush reads one issued prompt").
B. Publish from W: git push origin mc2-v2 mc2-v2.3 mc2-v2.4 mc2-v2.5
C. On the Mac, one tag at a time from mc2-v2.2: python3 master_chat_tasks/tools/upgrade.py backup, then preflight, then the git commands it prints, then upgrade.py recheck --from <old tag> --to <new tag>. Expect template_check PASS at v2.3 and later.
D. After mc2-v2.3: issue one real prompt with the new templates and read it; check python3 master_chat_tasks/tools/template_check.py prints exit 0 in ROOT.
E. Step 5: the master shows the kit_watch report and the classification (KIT_CLASSIFY_PROMPT.md); only on Ayush's word the master runs python3 tools/kit_watch.py save --by "<his exact words>". Then kit_watch card must say unchanged. Rollback: copy knowledge/fingerprints/archive_5574d77e/qc.json back over knowledge/fingerprints/qc.json.
F. Decide: a label glossary for the LEVER_RULES tags (problem 2); whether a missing Template line should be refused (problem 4); whether research should default to Codex in issue.py (problem 5).

LESSONS FOR THE MASTER
1. Templates that sessions read from disk cannot carry fill tokens unless the issuer renders them: issue.py now renders every named template per issue | no change: done in tools/issue.py.
2. A check script tuned on the current text passes by construction; the planted conflict test in test_issue_mc2.py keeps template_check honest | no change: test added.
