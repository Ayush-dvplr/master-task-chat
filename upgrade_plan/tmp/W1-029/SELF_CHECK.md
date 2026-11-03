SELF CHECK (W1-029, 3 Nov 2026)

Method: 8 rows drawn at random (Python random, seed 29) from the 123 rows taken into TRIAGE.md. For each, the cited file:line was opened in the real file under /home/user/master-task-chat/master_chat_tasks/ or master_chat_work/ and compared with the FOLD_TABLE rule text.

1. F226 _COMMON_RULES_v5.md:64 (prompts/templates/_COMMON_RULES_v5.md): line reads "QC target ... Zero fails; every minor or warn left must be genuine, and as few as possible. Fix a REAL minor or warn when the fix keeps every lever". MATCH.
2. F21 LEVER_RULES_v3.md:91 (knowledge/LEVER_RULES_v3.md): line holds "(c) measured scale ... TIMEOUT/CRASH counts with no cap". MATCH.
3. F108 20261101_route1_notes.md:10 (prompts/issued/_adhoc/): line holds "instruction.md states the exact bar ... tests compare whole documents per hidden run ... Every task carries the sentence." MATCH.
4. F234 _COMMON_RULES_v5.md:68: line reads "a score from a run with a grader error ... is never a baseline. Only valid: true lines of ... scores.jsonl count." MATCH.
5. F353 state.json:96: line reads "PEER SAMPLES (Ayush 11:26 24 Oct): only Anubis_Tasks_Samples/Pass@1_New/ holds current passing peer tasks; older samples are QC failed." MATCH.
6. F238 pipeline_v4/PLAN.md:8 (master_chat_work/_dev_research/pipeline_v4/PLAN.md): row "1 | Order: design, build, blind, QC, freeze, 1 run." MATCH.
7. F93 LEVER_RULES_v3.md:242: line reads "Design, build (with precheck self checks), 3 fresh blind reads, one full QC with fix all, QC recheck rounds, freeze, 1 harness run." MATCH.
8. F23 LEVER_RULES_v3.md:91: line holds "(4) every lever names oracle branch, program branch and a saved input that differs". MATCH.

Result: 8 of 8 match. Line 91 of LEVER_RULES_v3.md is one long line that carries several rows (F18 to F23); both sampled phrases were found in it.

Other checks done by the build script: every one of the 123 taken rows sits in exactly one item (assert passed); item references inside TRIAGE.md (T24, T30, T34, T46) point to the right items; no dash used as punctuation.
