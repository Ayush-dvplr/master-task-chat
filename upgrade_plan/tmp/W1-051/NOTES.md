W1-051 NOTES (helper, 4 Nov 2026)

Sources read: README.md, PLAN_FINAL.md (A to K), RESUME.md, PROBLEMS.md, AYUSH_SUGGESTIONS.md, ANSWERS.md ENTRY 80 to 97, drafts/P1 RULES_IN_FORCE.md, BUILD_RULES.md, settings.json, delivery/README.md, opencode_handoff AGENTS.md, SETUP_STEPS.md, NEXT.md, knowledge/PATTERNS.md, reports/KIT_CHANGE_487b4697.md, tmp W1-030 FIX_MAP.md (head), W1-031 DESIGN.md and dockslot.py docstring, W1-032 S7_KIT_WATCH.md, W1-034 DESIGN_FLOW.md, W1-035 P13_INTAKE.md and S9_RUNNER.md, W1-046, W1-048, W1-049 reports, mc2 worktree (master_chat_tasks/README.md, tool docstrings, settings.json, .gitignore, CURRENT.json, opencode.jsonc, both dcp.jsonc, git tags read only).

Checked in the worktree (read only git): mc2-v2.0 is a tag object 719a09c8 (annotated), mc2-v2.1 and mc2-v2.5.2 are commits (lightweight), mc2-v2.5.2 = fe8e377a, mc2-stable = 8d1c963e (mc2-v2.0 commit). SYSTEM_VERSION version = v2.5.2.

Differences found between files (reported, not fixed):
1. PLAN_FINAL C4 says BACKUP/YYYYMMDD/records/; upgrade.py at mc2-v2.5.2 writes one folder per run <backup dir>/<YYYYMMDDTHHMMSS>/ with records/ and MANIFEST.json, plus one shared work_mirror/. TECHNICAL.md uses the code.
2. knowledge/REGRESSION_CHECK.md step 3 still says 3 oracle runs (5 final); settings.json oracle_runs is 2, 2, 2 (ENTRY 88). BUILD_RULES PL ANSWERS also says 2 everywhere. TECHNICAL.md uses settings.
3. BUILD_RULES LIMITS still says 4x and at most 6 what if criteria in the T43 and T42 lines; the PL ANSWERS line at the end replaces them (2x, 3).
4. intake.py docstring still names constants tests<85 etc.; P13_INTAKE says the gate must come from settings (STAGE B step 6 change).
5. triage folder upgrade_plan/triage/ and tmp/W1-050 were empty when this was written; triage_tasks.py is described from ENTRY 97 only.
6. master_chat_tasks/README.md (U13) and BUILD_RULES QC FIX STEPS still call a finding on unchanged lines noise; PL5 (ENTRY 88) dropped that rule. Flagged in TECHNICAL.md section 6.
7. dockslot state_dir: settings docker.state_dir ~/.local/state/dockslot versus PLAN_FINAL E1 ~/.local/state/mc2/. Flagged TO BE CONFIRMED.
8. Names: the files use "the owner"; only exact ids keep a name (the path /Volumes/ayush_prsnl and the intake.py flag --ayush-ok).
