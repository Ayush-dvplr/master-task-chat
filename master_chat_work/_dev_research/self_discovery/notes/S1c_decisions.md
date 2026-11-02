# S1c decisions.jsonl (87 lines) — path master_chat_tasks/decisions.jsonl

Gate churn (conflict material):
- d3 target overall<30 (superseded) -> d15 tests<0.20 -> d23 E1 per-run gate test<90 rubric<90 overall<30 -> d63 TEST-PHASE GATE tests<100 rubric<100 overall<70, design aim 0.10-0.20 -> d83 gate wording conflict resolved to tests<100 rubric<100 overall<70.
- d48 Q36 option A chmod 700 -> d51 Q39 755 supersedes (upstream 2690e960). Churn 755->700->755.
- d49 Q29 option C TEMPORARY skip build-time hardness solvers.
- d57/59/60 session caps 6->5; Docker heavy max 2; d70 Docker max-2 waived.
- d35 TRIAL FREEZE then d36 TRIAL USE.

Design doctrine:
- d16 D1 conflicts reported, not picked (VB 15.5 vs DS-27).
- d18 D3 hardness = A hidden composition + B chain + 1-2 of C/D/E/F; grade later stages on oracle-fed inputs.
- d19 D4 judge outcomes, no test overlap (JD-8); JD-7/JD-15.
- d21 D6 caps 70 tests / 70 judge criteria (QC WARN above 35) -> conflict with QC.
- d27-29 lever novelty: several new per task.
- d73 "levers alone are not enough, frontier models solve any direct task".
- d74 accept JD-7 conduct criteria; TS-26/AL-28 keep cascade/stacking built to pass QC.
- d77 reflex program = fresh blind-solve session; every P12 re-runs reflex; compensate if >0.20. d79 blind-solve skipped today (process gap).
- d80 vendor/district round count reset (earlier rounds judged on permission-bug scores).
- d84 MINOR/WARN suggestion test; d85 P12 per-finding FIX/KEEP/REBUT; d86 QC_FIX_PLAYBOOK + trap-survival check; d87 stacking_check isolated+mutation vs LEVER_RULES G3 isolated-only, no change (latent conflict).
- d55 fix every QC issue before trajectory; d64 DROP RULE after 3 rounds; d68/69 extra rounds for emberforge/schema (DROP RULE bent).
- d25 E3 Ayush runs trajectory.
