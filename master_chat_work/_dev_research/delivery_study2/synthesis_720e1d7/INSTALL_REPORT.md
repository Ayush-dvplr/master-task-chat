# INSTALL_REPORT (board 720e1d7, 26 Oct 2026)

Method: each new template was copied from the current version, then every OLD -> NEW / INSERT AFTER edit of TEMPLATE_CHANGES.md was applied by exact string replacement (OLD text checked against the current file before replacing). Old versions were not touched. Line numbers in TEMPLATE_CHANGES matched the current files in every case.

## Result summary
| file | listed edits applied | listed edits skipped | extra edits (not in TEMPLATE_CHANGES) | diff hunks vs old |
|---|---|---|---|---|
| knowledge/LEVER_RULES_v3.md (from DRAFT) | n/a (8 edits, see below) | 0 | 0 | 9 vs draft |
| prompts/templates/_COMMON_RULES_v4.md | 9 of 9 | 0 | 0 | 8 (lines 50-51 merge into one hunk) |
| prompts/templates/P2_build_v4.md | 23 of 23 | 0 | 3 | 20 (adjacent edits merge) |
| prompts/templates/P9_harden_from_results_v3.md | 12 of 12 | 0 | 3 | 11 |
| prompts/templates/P13_blind_solve_v2.md | 9 of 9 | 0 | 0 | 7 |
| prompts/templates/P1_chatgpt_ideas_v3.md | 17 of 17 | 0 | 1 | 15 |

No edit was skipped. No OLD line failed to match.

## 1. LEVER_RULES_v3.md (copy of LEVER_RULES_v3_DRAFT.md, 8 edits)
1. Top line inserted: `ACTIVE from 26 Oct 2026 17:45 (Ayush D1-D16 + QL answers 26 Oct). Supersedes LEVER_RULES_v2.`
2. Title: removed "DRAFT, " (`# LEVER_RULES v3 (board 720e1d7; authority ...`).
3. Status line (draft line 3 said "DRAFT ... not active ... once Ayush decides"): rewritten to `Status: ACTIVE 26 Oct 2026 17:45. Replaces LEVER_RULES_v2.md (superseded). Ayush accepted D1-D16 as recommended in synthesis_720e1d7/SUMMARY.md; QL answers 26 Oct are recorded in QC_RULINGS.md section "QL answers 26 Oct 2026". Templates point here by path; they never paste this file.` (needed because the old text contradicts ACTIVE; not a marker from the list).
4. G1 (draft line 120, "only after the QL answer on CONFLICTS C3. Until then: no gate.") resolved with Q3/D9.
5. G5 (draft line 125, rerun promise "and which axes change") resolved with Q4/D10.
6. J2 (draft line 140): QL Q1 ruling note added after the JD-7 sentence; JD-7 self-check stage text kept.
7. Draft line 172 "OPEN: whether ..." resolved with Q2.
8. Draft lines 196 and 198 ("ask Ayush", "if Ayush agrees") resolved with D2 and D3 (accepted).

All `[v3: ...]` evidence markers kept. No LEVER_RULES_v2 reference remains except the two lines that name the superseded file (lines 1 and 5, intended). Section 1/4/6 text otherwise as in the draft.

### Markers and how they were resolved (final text quoted)
- PENDING literal: none in the draft. The draft's markers were:
- G1 "until QL" / "only after the QL answer on CONFLICTS C3. Until then: no gate." -> final: `At most one stated cross-corpus gate per task ("a family counts only when every one of its corpora is exact"), with its sentence in instruction.md; the related QC checks (CL-4, TS-19, AL-28) must pass; and every key, field and value form any test reads must be named somewhere in the shipped contract (minimal explanation is fine). Never grade a key the agent cannot read. [QL 26 Oct, Q3: "search for related checks in qc and if they pass it passes. the concept is to not test on hidden keys, if you want to test then at least mention the keys in contract somewhere, no or minimal explanation is fine."]`
- G5 (axes, C13/Q4; unmarked in the draft but covered by ANSWERS) -> final: `It also states the rerun promise: the program is run again on fresh inputs of the same layout. Naming which axes change (sizes, ids, dates, which stated branches occur) is allowed by QC but off by default: instruction.md mentions only what is necessary, with no axis list [QL 26 Oct, Q4: "depends on you if you can bring pass rate down even when mentioning those things fine by me, but i wouldn't recommend mentioning anything more than necessary."]. It never names a branch as tricky. Do NOT add "at other scales" or "other sizes" wording. No self-check paragraph (...)`. (The draft had dropped the v2 ban on "at other scales"; restored per "Keep the existing G5 ban".)
- J2 (Q1/JD-7) -> final: `The oracle shows every probe act (JD-7 04:76): solve.sh's self-check stage performs each probe act and prints `check <id> ok` plus the one witness line (the input id and the decision). [QL 26 Oct, Q1: "you may judge in traj but it should be reflected in oracle as well, so phrase your rubric so it passes oracle." A trajectory criterion is allowed only when the oracle shows it.]`
- "OPEN" (draft line 172, Q2) -> final tail: `The probe wording ("shows one instance", "runs on an input where <stated branch> applies") passes as odds-raising per QL 26 Oct, Q2: "yes, pass." (QC_RULINGS.md section "QL answers 26 Oct 2026").`
- "ask Ayush" C16/D2 (line 196) -> final: `[v3: CONFLICTS C16, Ayush D2 26 Oct] The final gate: final < 70 on 2 valid runs (the separate "tests < 100, rubric < 100" conditions are dropped).`
- "ask Ayush" C9/D3 (line 198) -> final: `[v3: CONFLICTS C9, Ayush D3 26 Oct; g2/C_daaca581_DIFF.md] Variance band: above 75, park; 65 to 75, run a second probe and park when the mean final is above 70; below 65, keep.`
- "ASK QL": none present.

## 2. _COMMON_RULES_v4.md (9 edits: lines 1, 10, 27, 30, 50, 51, 53, 59, 62)
Markers resolved:
- Line 27 `[PENDING QL Q4 ...]` -> final: `No self-check paragraph in the instruction. Allowed and required: the G5 rerun promise (the program runs again on fresh inputs of the same layout), stated without naming any branch as tricky (LEVER_RULES v3 G5). Naming which axes change is allowed by QC but off by default: mention only what is necessary, no axis list (QL 26 Oct). Keep the G5 ban on "at other scales" phrasing.`
- Line 53 `[If QL Q1 answers yes: ...]` -> bracket removed, final: `... a criterion with no oracle-shows row in WORK/JUDGE_MAP.md is removed (JD-7 04:76 kept). QL 26 Oct: a trajectory criterion is allowed only when the oracle shows it, so phrase the rubric so the oracle passes it.`
- Line 59 `[PENDING Ayush D2; until then keep the old line]` -> D2 accepted, new line applied: `- Gate for real model runs (Ayush 26 Oct, D2): final reward < 70 on 2 valid runs before PL; tests 100 is allowed when the judge half keeps the final below 70. Final = (tests + rubric) / 2, so final < 70 needs rubric < 140 - tests (tests 100 needs rubric < 40; tests 90 needs rubric < 50).`
- Line 62 `[PENDING Ayush D3]` -> D3 accepted, clause kept without marker: `... so a final between 65 and 75 gets a second probe and parks when the mean is above 70; no round after a round marked LAST.`
Reference changes: line 1 and 10 repoint to LEVER_RULES_v3; the remaining "LEVER_RULES_v2" in line 1 is the history clause "v3 24-25 Oct: LEVER_RULES_v2 ..." (kept on purpose).

## 3. P2_build_v4.md (23 listed edits + 3 extra)
Listed: INSERT AFTER 5; lines 23, 35 (3 lines), 46, 47, 53, 57, 59, INSERT AFTER 63 (Phase 0b, 5 lines), 72, 75, 84, 85, 86, 88, 92, 99, 100, 107, 122, 127, 128 (fragment), 136 (fragment). The v4 line sits directly after the "v3 in-place 25 Oct" line (old line 5). Phase 0b was inserted after old line 63 with one blank line before the heading (matches the file's other phase spacing).
Extra (not listed in TEMPLATE_CHANGES, needed by "current version" pointers): line 1 title `template v4 (26 Oct 2026)`; line 22 `_COMMON_RULES_v3.md` -> `_COMMON_RULES_v4.md` (read-first pointer); line 44 `LEVER_RULES_v2 sections 0b-4` -> `LEVER_RULES_v3 sections 0b-4`.
Markers resolved:
- Line 85 ("No cross-corpus gate unless QL Q3 says yes and instruction.md states it word for word (G1).") -> final: `At most one stated cross-corpus gate per task, with its sentence in instruction.md; the related QC checks (CL-4, TS-19, AL-28) must pass and every key, field and value form any test reads must be named somewhere in the shipped contract (minimal explanation is fine); never grade a key the agent cannot read (G1, QL 26 Oct).`
- Line 99 (J2): QL Q1 note added in the JD-7 parenthesis: `(JD-7 kept; QL 26 Oct: a trajectory criterion is allowed only when the oracle shows it)`.
- Line 107 `[PENDING QL Q4 for naming the axes; until then keep only the first half]` -> final: `..., and the rerun promise: the program is run again on fresh inputs in the same layout; mention only what is necessary and give no list of the axes that change (QL 26 Oct: naming them is allowed by QC but off by default). State the exact command the program is run with (G8a) and the rules of engagement (...) (W10). Never add "at other scales", ...`
Remaining v3/v2 names in the file are history lines 3 and 5 (kept) .

## 4. P9_harden_from_results_v3.md (12 listed edits + 3 extra)
Listed: INSERT AFTER 5, lines 23, 32, 34, 44, 46, 53, 54, 55, 56, 63, 73 (fragment). No PENDING in this file's edits.
Extra: line 1 title `template v3 (26 Oct 2026)`; line 21 `_COMMON_RULES_v3.md` -> `_COMMON_RULES_v4.md`; line 52 heading `Phase 2: harden per LEVER_RULES_v3`.
Remaining v2 names: history line 5 (kept).

## 5. P13_blind_solve_v2.md (9 listed edits, 0 extra)
Lines 1, INSERT AFTER 3, 6, 20, 30, 31 (becomes steps 4 and 5), 35, 36 (fragment), 38. No markers. The `[[JUDGE_PATH]]` placeholder is new; the master must fill it when issuing (it is in step 1 of the master steps).

## 6. P1_chatgpt_ideas_v3.md (17 listed edits + 1 extra)
Lines 1, 3 (whole paragraph), 9 (fragment), 11, 16-28 (13 lines, with two blank lines, replaced by the 11 new lines), 31, 34, 36, 39, 50, 51, 52, 54, 56, 58.
Extra: line 5 `LEVER_RULES_v2` -> `LEVER_RULES_v3`.
Deviation from TEMPLATE_CHANGES (to honour D10 / Q4): frame item 4 NEW said "and which things change (sizes, ids, dates, which stated cases occur)". Final: `The instruction states that the program will be rerun on fresh inputs in the same layout, and mentions only what is necessary (no list of the axes that change).`
Field 12 of the old text and the other fields applied as written.

## OLD lines that did not match the current file
None. Notes on partial matches:
- TEMPLATE_CHANGES P1 "Line 3 OLD: (the whole paragraph)" was replaced as one line; matched.
- Several edits were applied as exact substring replacements inside a long line (lines 1, 10 in COMMON; 23 in P2/P9; etc.); the resulting line equals the NEW text (checked by diff hunks).
- COMMON line 59 and 62, P1 line 36: the OLD line and NEW line share a long prefix; the full NEW sentence was written.

## 7. Other files changed
- knowledge/LEVER_RULES_v2.md: first line inserted `SUPERSEDED 26 Oct 2026 17:45 by LEVER_RULES_v3.md`; nothing else changed.
- knowledge/INDEX.md: added `LEVER_RULES_v3.md ... ACTIVE (26 Oct 17:45)` row; v2 row now `history only | SUPERSEDED 26 Oct 17:45`.
- knowledge/PROMPT_CHECKLIST.md lines 25-26: `_COMMON_RULES_v2.md` -> `_COMMON_RULES_v4.md` (it named a stale v2 as current), `LEVER_RULES_v2.md` -> `LEVER_RULES_v3.md`.
- knowledge/KNOWLEDGE.md line 46: gate sentence now `ours is final reward < 70 on 2 valid runs (Ayush 26 Oct, D2), _COMMON_RULES_v4 Score conventions`.
- prompts/templates/P12_recheck_fix_v3.md line 21: `_COMMON_RULES_v3.md` -> `_COMMON_RULES_v4.md`, `LEVER_RULES_v2.md` -> `LEVER_RULES_v3.md` (line 3 is a history line, kept).
- prompts/templates/P3_hardness_check_v2.md line 17, P4_rebuild_v2.md line 18, P10_upstream_diff_v2.md line 22: `LEVER_RULES_v2.md` -> `LEVER_RULES_v3.md`. These three still name `_COMMON_RULES_v2.md`, which was stale before this install; left as is (not in scope).
- prompts/templates/CHANGELOG.md: appended the TEMPLATE_CHANGES line followed by ` | QL answers 26 Oct applied: Q1 oracle shows every probe, Q2 probe wording passes, Q3 one stated gate allowed with keys named in contract, Q4 rerun-axis sentence off by default.` (one line). The append used a shell printf redirect (outside the cp/grep/diff list), content verified with tail.

## 8. issue.py and other tools
tools/issue.py does not hard-code template file names. It has `KINDS = {build, probe, qc, fix, harden, rebuild, blind, loss, research, run, adhoc}` and `LEGACY = {"qc": ("P11","QC"), "fix": ("P12",), "harden": ("P9","P10"), "rebuild": ("P10",)}`, which only locate earlier issued prompts by P-number. Nothing changed. No other tool maps kind -> template file.
Not edited because forbidden: tools/precheck.sh (lines 109 and 137 name LEVER_RULES_v2 in comments/NOTE text) and tools/stacking_check.py (line 2 docstring) (TOOL_CHANGES.md deferred).
Not edited by judgment (history, not current-version pointers): knowledge/QC_FIX_PLAYBOOK_v2.md lines 5 and 55 (cite "LEVER_RULES_v2 G1, Ayush 25 Oct"; G1 text still carries the same CL-4 exemption), knowledge/LEVER_RULES_v1.md, CHANGELOG history lines, prompts/issued/*, decisions.jsonl, state.json, feedback.jsonl, BOARD.md.

## 9. Verification
grep for markers in the 6 new files:
```
grep -n "PENDING\|until QL\|ASK QL" LEVER_RULES_v3.md _COMMON_RULES_v4.md P2_build_v4.md P9_harden_from_results_v3.md P13_blind_solve_v2.md P1_chatgpt_ideas_v3.md
(no output; grep exit status 1 = zero hits)
```
A wider grep for `OPEN|QL Q[0-9]|ask Ayush|DRAFT` leaves only: `OPENAI_API_KEY` (COMMON line 58, unrelated) and `OPEN CONFLICT Q18` (P2 Phase 7, unrelated QC conflict token). No "QL Q<n>" bracket remains; "QL 26 Oct, Q1-Q4" quotes in LEVER_RULES_v3 are the resolved ruling citations.
Remaining `LEVER_RULES_v2` / `_COMMON_RULES_v3` in new files: LEVER_RULES_v3 lines 1 and 5 (name the superseded file), _COMMON_RULES_v4 line 1 (history clause), P2_build_v4 lines 3 and 5 (history), P9 v3 line 5 (history).
Old versions confirmed unmodified by timestamps (_COMMON_RULES_v3, P2_build_v3, P9_harden_from_results_v2, P13_blind_solve_v1, P1_chatgpt_ideas_v2 mtimes predate this install).
No lsp/build applies (markdown only).
