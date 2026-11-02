# TODO 0dd7a8c tariff-engine-audit-repair (P9 harden r2)
Prompt: master_chat_tasks/prompts/issued/tariff-engine-audit-repair/20261025T0658_harden.md
(r1 TODO archived: TODO_r1_d62ffe6.md)

## Phase 0
- [x] rename session 0dd7a8c (opencode ses_e8f53eb83ffeUY2Klj90QGF61h; codex no match)
- [x] read COMMON_RULES_v3, round notes C/E/F/G, LEVER_RULES_v1, LEAK_LIBRARY, QC_RULINGS, QC_FIX_PLAYBOOK_v2
- [x] read WORK DESIGN, LEVERS, QC_DEFENCE (XREF pending for Phase 2) (no baselines.json); r1 DIAGNOSIS/HARDEN_REPORT
## Phase 1 (no edits to BUNDLE)
- [x] A: genuine? diff -rq copy vs BUNDLE, result.json, verifier stdout, judge read
- [x] lever table from reward-details.json
- [x] trajectory autopsy (steps per lever)
- [x] OUT/agent_program/ saved
- [x] fuzz >=300 corpora on probe2 agent program (OUT/fuzz_r2/), differing share per lever
- [x] per-lever: contract named amount/method or own reading? (all NAMED)
- [x] candidate new lever(s) prototype + mutant cost (OUT/proto/proto_b.py: B differs api 38/45, fuzz N2+N3 80/80, shipped/regression 0)
- [x] OUT/DIAGNOSIS.md -> STOP "DIAGNOSIS READY" (waiting for go)
## Phase 2/3: after go
