# REWRITE_REPORT: template rewrite to SETUP_PLAN_v1 + IMPROVEMENT_PLAN_v1 (board 3f73e3d)

23 Oct 2026, 09:11 to 09:30 IST. The new templates are v2 DRAFT-ACTIVE (Q8 b). No existing template was overwritten. No pilot file, bundle, harness clone, QC kit, `QC assigned/`, `my tasks/` or Anubis repo file was edited, and no git writes were made. The session was renamed to `3f73e3d`.

Base path: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/`.

## Files created
- `knowledge/LEVER_RULES_v1.md`: the authority file. It holds L1-L7, the not-allowed list, W1-W7, G1-G7 with caps, J1-J5, the STACKING_CHECK gate (a-d), the reflex gate (<= 0.20, 2 tries, P12 re-run, Phase A baseline rule) and the LP1 pilot lessons.
- `knowledge/LEAK_LIBRARY.md`: the common leak causes, plus rows for CR-1..5 and V0-1..8 (from cohort DIAGNOSIS s0) and the vendor r1 levers (from vendor DIAGNOSIS s3).
- `knowledge/QC_RULINGS.md`: rulings on IN-15, IN-16, TS-13, TS-19, TS-20, TS-26, AL-28, JD-7 and JD-15 from 24 QC reports, each tagged reuse or avoid, plus 10 patterns. The subagent crashed, so this file was written in the main session.
- `knowledge/PROMPT_CHECKLIST.md`: A1 checklist covering identity and survival, scope, reads, must-not, evidence and gates.
- `prompts/templates/_COMMON_RULES_v2.md`: W1 is now hard rule Never 8. Adds paths for LEVER_RULES, LEAK_LIBRARY and QC_RULINGS, the baseline-validity and reflex-gate lines, and the "Lessons for the master" ending.
- `prompts/templates/P2_build_v2.md`: designs from LEVER_RULES. Adds the reflex pre-mortem (PREMORTEM.md), QC_DEFENCE written before QC, STACKING_CHECK and the reflex gate. Drops the v1 "N rules" sentence, which breaks W1.
- `prompts/templates/P4_rebuild_v2.md`: adds the pre-mortem, a per-lever effect for each fix, STACKING_CHECK and the reflex gate.
- `prompts/templates/P9_harden_from_results_v2.md`: Phase A first, then the 4-cause root-cause section, the trajectory autopsy, the `agent_program/` save and LEAK_LIBRARY rows. Pauses for "go". Phase 2 follows LEVER_RULES, Phase 3 runs stacking plus the reflex gate.
- `prompts/templates/P12_recheck_fix_v2.md`: no fix may undo a lever or add a giveaway. Each fix's effect is labelled for every lever. The reflex program is re-run after fixes, with compensation if it goes above 0.20. Adds a QC_RULINGS rows section.
- `prompts/templates/P3_hardness_check_v2.md`: replay gate (R <= 0.20; PASS-PENDING-REPLAY when no reflex program exists), L5-SHIPPED, a W1/W6 grep, and stacking_check measures.
- `prompts/templates/P13_blind_solve_v1.md` (new): read-only, sees only a copy of instruction.md + environment/, writes its program once, self-checks on shipped data and stops.
- `prompts/templates/P14_task_analysis_v1.md` (new): the G1-G5 Phase A/B/C analysis structure.
- `prompts/templates/P15_research_angle_v1.md` (new): angle slots (Gemini academic, ChatGPT practical, own evidence) and a mergeable claim-line output.
- `prompts/templates/P5_quick_qc_v2.md`, `P6_oracle_nop_stub_v2.md`, `P10_upstream_diff_v2.md`: v1 plus the _COMMON_RULES_v2 path and the Lessons line (E3).
- `tools/peer_manifest.py`: commands `check <dir>`, `add <task_dir>`, `add --from-result <json> <dir>` and `show [slug]`. `root_sha` = sha256 over the sorted relative paths, sizes and contents of every file.
- `tools/stacking_check.py`: static AST reader of `tests/test_output.py` and `tests/judge.toml`. Reports the test-to-observable map with TS-26 candidates, TS-13 hints, AL-28 groups, G3 shares, caps, TS-20 and J1/J2 hints. Supports `--classes` and `--json`.
- `tools/lever_dose.md`: the D2 dose-test procedure.
- `registry/peer_tasks.json`: 20 Pass@1_New tasks, each with verdict, patterns, board, report and root_sha.

## Files changed (append-only)
- `prompts/templates/CHANGELOG.md`: 11 lines dated 2026-10-23 09:40.
- `registry/levers.json`: added L1-L7 (peer evidence, rule file, reflex score per task, trajectory result per task as pending, status candidate) and CR-1..CR-5 and V0-1..V0-8 with status leaked. The existing 48 entries were verified unchanged. Total is now 68.
- `registry/scores.jsonl`: 4 lines appended. One is a schema line (`valid` / `artefact_reason`; correction lines name what they correct). Three are `valid:false` corrections: cohort 58.67 (permission bug), vendor 52.41 (0600 permission bug) and the district-heat 7200 s timeout. Old lines were not rewritten, and all 51 lines parse.

Unchanged: P11 v2 (QC stays blind) and P1 v1. P7/P8 were already retired. The rename command, compaction rules, result json (sha = board id), oracle x3 (the kit asks for x5) and the clash rules are carried word for word into every new template.

## Self-tests
- `peer_manifest.py check Anubis_Tasks_Samples/Pass@1_New`: before the fill it reported `new: 20`. After the fill it reports `scanned 20 task folders ... new: 0  changed: 0  unchanged: 20`. A /tmp copy with an edited instruction.md was reported CHANGED (0d76119446b8 -> f59d9b6c27c2), and the copy was then removed.
- `stacking_check.py` run read-only on the 3 pilot bundles:
  - cohort: 24 checks, positive 71 / negative -23. TS-26: none. AL-28: 6 groups, all <= 5. Shares: whole-document 60.6%, isolated+mutation 29.6%, shipped-only 1.4%. All pass, and this matches the pilot's own STACKING_CHECK.
  - district-heat: 38 checks, positive 113 / negative -13. TS-26: none. AL-28: 4 groups pass. Shares: whole-document 69.9%, isolated+mutation 26.5%, shipped-only 3.5%. Test count is WARN (>35). This matches the pilot.
  - vendor (snapshot taken while the pilot was still editing): 32 checks, positive 107 / negative -19. AL-28: 7 groups pass. Isolated+mutation is 33.6%, a FAIL hint, because the 4 report_* checks are counted as isolated; the session must confirm. Whole-document 63.6%.
- Two tool bugs were fixed during the self-test: the act-regex order, and the mutation-class trigger.
- The tool also runs on peer tasks, but its class heuristics are tuned to our naming, so peer tasks need `--classes`.
- Both python tools parse. LSP was not available (basedpyright not installed), and pyflakes is absent.

## Not done / open
- Vendor STACKING_CHECK and the HARDEN_REPORTs for all pilots did not exist at 09:15, so the vendor pilot lessons in LEVER_RULES section 7 are partial.
- _COMMON_RULES_v2 still carries the v1 per-run gate (test < 90, rubric < 90, overall < 30). SETUP Part 4 uses tests < 100, rubric < 100, overall < 70. I left it unchanged for the master to decide.
- No QC ruling yet exists on J2 conduct criteria (PL Q46).

## Lessons for the master
- Background subagents for file-writing deliverables can crash silently. Keep critical deliverables in the main session, or check them as soon as the subagent finishes.
- stacking_check.py gives hints only. Each P2/P4/P9/P12 report must quote its output and correct its class column by hand.
- Decide the score-gate wording conflict between `_COMMON_RULES_v2` and SETUP Part 4 before issuing v2 prompts.
- Re-run `peer_manifest.py check` before every P14 batch. Wire-format-recovery has 0 recorded patterns.
