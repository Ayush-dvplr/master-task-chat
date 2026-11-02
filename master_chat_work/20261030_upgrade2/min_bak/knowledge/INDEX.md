# knowledge/ index (24 Oct 2026 11:30 IST; updated 27 Oct 18:45 pipeline v4). One line per doc. Read only what the step needs.

| Doc | Read when | Status |
|---|---|---|
| KNOWLEDGE.md | always first; pipeline, kit, harness runner, caps, peer samples; section T = trajectory read-out and decision after every run | ACTIVE, the single fact sheet (section T 27 Oct) |
| LEVER_RULES_v3.md | designing or changing a design shape, hardness source, lever, judge probe band, stacking gate, probe gate (determinate test 0b, EVIDENCE_MAP, holes list) | ACTIVE (26 Oct 17:45; v3.3 27 Oct: section 1C proven levers, stated-rule levers paused; v3.4 27 Oct 18:45: Law-1 filter, push = 1 run on frozen QC-passed bytes, order, no re-run on same bytes; v3.5 27 Oct 20:10: Law-1 amended, hidden-scale timeout/crash counts under 3 conditions) | v3.6 27 Oct 22:30: gate tests<85/rubric<85/final<50 (history), lever 25-40%, blind <=80, judge mid 15-20. v3.7 29 Oct (Ayush 28 Oct "Target <40 now"): gate final<40, aims tests<=60, blind<=65, judge mid<=20, DESIGN READY (a)-(e), section 1D lever table, regrade exception; old text LEVER_RULES_v3.6_snapshot.md.
| LEVER_RULES_v2.md | history only | SUPERSEDED 26 Oct 17:45 |
| LEVER_RULES_v3.6_snapshot.md | history only: LEVER_RULES_v3.md bytes before v3.7 (sha256 7f3f733a...) | SNAPSHOT 29 Oct (upgrade C0) |
| KNOWLEDGE_v3.6_snapshot.md | history only: KNOWLEDGE.md before v3.7 (sha256 50649d4b...) | SNAPSHOT 29 Oct (upgrade C0) |
| ../prompts/templates/_COMMON_RULES_v5_v3.6_snapshot.md | history only: _COMMON_RULES_v5.md before v3.7 (sha256 4c41f765...) | SNAPSHOT 29 Oct (upgrade C0) |
| ../../master_chat_work/_dev_research/pipeline_v4/PLAN_v3.6_snapshot.md | history only: pipeline v4 PLAN.md before v3.7 (sha256 1ca2cbcb...) | SNAPSHOT 29 Oct (upgrade C0) |
| LEVER_RULES_v1.md | history only | SUPERSEDED 25 Oct |
| LEAK_LIBRARY.md | before build/harden/fix; how levers leaked on real runs | ACTIVE |
| QC_FIX_PLAYBOOK_v3.md | fixing any QC finding without softening a lever; section 1b guard rules G1-G7, count cap option A (over 35 = warn) | ACTIVE v3 27 Oct 18:45 |
| QC_FIX_PLAYBOOK_v2.md | history only | SUPERSEDED 27 Oct 18:45 (line 57 contradicted line 41) |
| QC_RULINGS.md | precedent for a QC check id; carry-over between QC rounds | ACTIVE (carry-over section 27 Oct) |
| PROMPT_CHECKLIST.md | master, before handing any prompt link | ACTIVE |
| FP_DOSSIER.md | a QC or QL finding shown false; before triaging a QL report (P16) | ACTIVE, file created 29 Oct (upgrade A6), rows added as findings are proven false |
| QL_MASTER_STEPS_v1.md | the QL pastes a QC report or hands back a zip: master steps, then P16 / P17 / QL_REPLY_TEMPLATE | ACTIVE 29 Oct (upgrade A6, from R1 086e1b4) |
| ../prompts/templates/P16_ql_report_triage_v1.md | triaging a QL QC report (REAL / FALSE POSITIVE / PARTLY / OUT OF SCOPE) | ACTIVE 29 Oct; P7 v2 and P8 v2 are NOT used for QL work (they read the stale _COMMON_RULES.md) |
| ../prompts/templates/P17_ql_handback_v1.md | a QL zip handback (trajectory only / regrade only / lower score / QC + fix) | ACTIVE 29 Oct |
| ../prompts/templates/QL_REPLY_TEMPLATE.md | writing any reply to the QL (Ayush reads before sending) | ACTIVE 29 Oct |
| ../../master_chat_work/_ql/ | inbound QL material: one folder per slug, `<TS>_report/` and `<TS>_zip/` inside; `hardness_md/` for the hardness.md reply | ACTIVE 29 Oct |
| ANGLES.md | before any P15 run (default `[[ANGLES_FILE]]`) | ACTIVE 29 Oct, master merges each P15 OUT/ANGLES.md; sessions never write it |
| ../prompts/templates/P15_research_angle_v2.md, P14_task_analysis_v2.md | learning runs (P15) and task analysis (P14) | ACTIVE 29 Oct; v1 files kept as history |
| TEAMMATE_MODELS_v1.md | designing a new task: 9 genuine Hard/Expert teammate models + 4 flagged | ACTIVE 29 Oct (labels UNVERIFIED, from R4 1d26a6e) |
| archetypes.md | P1 archetype list | STALE (generator 9b8229f6) |
| qc_authoring_checklist_9b8229f6.md | never; superseded by master_chat_work/20261024_process/qc_reverse/A/checks.json | STALE |
| PLAN_v1.md | history only (21 Oct system plan) | HISTORY |
| archive_md/ | history only (old md stores) | HISTORY |
| fingerprints/ | checking whether kit/generator changed (qc.json, pl_generator.json) | ACTIVE |
| intake/ | PL/QL handover facts (oracle/nop procedure, ecosystem) | REFERENCE |

Live process plan: master_chat_work/_dev_research/pipeline_v4/PLAN.md (pipeline v4, Ayush 'proceed' 27 Oct; decisions 1-9, stages 1-7) on top of master_chat_work/20261024_process/MASTER_UPGRADE_PLAN_v1.md (approved 24 Oct 11:26; where they differ v4 wins).
QC check matrix: master_chat_work/20261024_process/qc_reverse/A/checks.json + B/by_check.json.
