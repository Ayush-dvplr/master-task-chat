# TODO stall-graph-postmortem harden r1 (board 109e662)
Prompt: master_chat_tasks/prompts/issued/stall-graph-postmortem/20261026T1322_harden.md

## Phase 1 (no BUNDLE edits)
- [x] session rename (opencode ses_e88cbb416ffeJnbgxhw12FF0TR matched)
- [x] read common rules, round notes C/E/F/G, LEVER_RULES_v2, LEAK_LIBRARY, QC_RULINGS, QC_FIX_PLAYBOOK_v2
- [x] fingerprints: qc 5574d77e 12 files match, gen 976c1666 160 files match; kit HEAD 5574d77e
- [x] read bundle TRUTH, instruction, tests, judge, all environment/data
- [x] Phase A: diff staged tests/ + ctrf ids vs BUNDLE; result.json errors; judge read response
- [x] Phase A Docker confirm (one oracle or agent-program run on fixed grader)
- [x] root causes 1-4 (C1 NO, C2 YES tests artefact, C3 NO, C4 YES primary)
- [x] lever table from reward-details + trajectory (DIAGNOSIS section 3)
- [x] trajectory autopsy
- [x] copy agent program to OUT/agent_program
- [x] WORK: DESIGN.md, LEVERS.md, QC_DEFENCE.md, XREF.md (reconstructed)
- [x] OUT/DIAGNOSIS.md + LEAK_LIBRARY rows; STOP "DIAGNOSIS READY"

## Phase 2/3: after Ayush "go"

## Phase 2 (GO 14:42)
- [x] backup pre-round bundle to WORK/pre_r1
- [x] grader LV-2 padding writes owner window (decode + encoder)
- [x] grader LV-3 resolve_owner at carrying event epoch
- [x] generator PLANTS (LV-1 12 corpora, LV-3 12 corpora), calibration half split for CTRL-E neutrality
- [x] shipped check: only stall_journal.psv + calibration_stall_journal.psv change; controls and sample answers SAME; recover unique under both readings
- [x] verify plants run on reference (all 25 corpora build, reference recovers)
- [x] solve.py mirror LV-2, LV-3, closed partitions; oracle == reference on all corpora
- [x] write regenerated data (_write_corpus), common rule 6
- [x] measure mutant costs (each lever alone, all-but-one, reflex all three, oracle)
- [x] docs D1 D3 D4 D6 G5, LV-2 padding sentence, LV-3 sentence, EVIDENCE_MAP
- [x] judge rebuild + solve.sh self-check + JUDGE_MAP
- [x] TRUTH, DESIGN, LEVERS, QC_DEFENCE, XREF; xref_check 0
- [ ] stacking, precheck CLEAN, QC scripts, rm __pycache__
- [ ] Docker gates
- [ ] reports, result json, BUILD READY
