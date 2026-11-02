# L2: QC kit map: what every check demands, how to pass it honestly, which levers stay QC-clean
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_learning/L2_qc_kit_map/`

Ayush: "map each QC check: how we fix it; we can use levers as every other tasker does without raising a QC alert."
1. `KIT_MAP.csv`: every check id in `Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (gate files 01-05 + Final_checklist CL-1..CL-10 + scripts): id, file:line, what it demands in one line, automatable by script? (yes/partly/no), how often our tasks failed it (count tasks from `TB/QC/reports/*/v*.md` ❌ lines; say how).
2. For each check: how a builder satisfies it honestly at build time (concrete action), and what a later fix for it commonly breaks (cross-check with L1 if its files exist in `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_learning/L1_qc_fixes/`, else from reports).
3. Levers vs QC: for each hardness lever we or teammates use (LEVER_RULES_v3 P-1..P-5, N1/N2, LC1.., held-out exact, convention/induction, probe-band judge, hidden scale, timeout share; plus any lever S4/R3/R4 found in anubis-stage-2), list which QC checks it touches (e.g. IN-17 no pre-announcing, AL-1 graded-but-not-promised, AL-27 trigger depth, IN-8 satisfiable from prompt+container, CL-4 one wrong fact) and the exact way to keep it QC-clean (what must be stated, what may be withheld). Use real examples that PASSED our QC (QC/reports with PASS verdict) and teammate tasks. `LEVERS_VS_QC.md`.
4. Draft `BUILD_CHECKLIST_DRAFT.md` (<=60 lines): the checks to self-run before QC, ordered by how often they fail, each with the command or reading step. DRAFT, not installed.
5. Kit vs our templates: any place where `master_chat_tasks/prompts/templates/P2_build_v5.md`, `P12_recheck_fix_v4.md` or knowledge files contradict the live kit (path:line both sides).
Extra files: KIT_MAP.csv, LEVERS_VS_QC.md, BUILD_CHECKLIST_DRAFT.md.
