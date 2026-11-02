# TOOL_CHANGE_SPECS v1 DRAFT (no code; anchors are current file:line)

T1 `master_chat_tasks/tools/issue.py`
- :34 KINDS: add `ql`. It joins TASK_KINDS (:37) and is used for P16 and P17.
- :71 `passed`: add `pushed`, so that `qc`, `fix` and `harden` on a pushed task are refused unless the board row has a QL round open (registry `ql_round` set and `next` starting "QL round"). Today a pushed task slips through.
- :89 time box: skip it for kind `ql`, and for `qc`/`fix`/`harden` on a pushed task with a QL round open. Print "QL round <n>, cap skipped".
- :14-19 docstring: list the new rules.

T2 `master_chat_tasks/tools/intake.py`
- :104 and :11, :106: change the gate to `o < 40`. Read it from one constant, `FINAL_GATE = 40` (Ayush 28 Oct "Target <40 now").
- :124 `--event`: add `ql_rerun` and `regrade`. A `regrade` row must carry `valid: false` unless the flag `--ayush-ok "<verbatim>"` is given (FINDINGS Q1).
- :108 row: add `tree_sha`, computed from `--bundle` with the REGRADE_REPORT.md:7 command. Refuse `gate_run` and `ql_rerun` when it differs from the registry `tree_sha`.

T3 `master_chat_tasks/tools/status.py`
- :22 FIELDS: add `tree_sha`, `ql_round` and `ql_last` (path to the newest `_ql/<slug>/<TS>_*` folder).
- :24 / :72 STAGES: no new stage. A QL round shows as `pushed` with `next = "QL round n: <step>"`. This keeps the order logic unchanged.

T4 one-slug repackage (harness side, needs Ayush, FINDINGS Q5)
- New wrapper next to `Terminal_2.0_Harbor_Harness/scripts/package_rfp_bundles.py`. It takes `--slug`, `--run-dir`, and `--task-dir` set to the frozen Tasks_INPUT, not `config.json task.path` (:15, :152), because after a regrade that path is under /tmp (REGRADE_REPORT.md:123).
- It calls `_package_run()` (:117) only. It backs up `Output_RFP/<slug>/trajectories` first and writes sha listings before and after. It refuses when Tasks_INPUT and the frozen tree differ.
- It never calls `main` (:273), which walks every job (:189).

T5 rules text (applied only after "proceed")
- `_COMMON_RULES_v5.md:49,61` and `LEVER_RULES_v3.md:89,210`: final < 40.
- `_COMMON_RULES_v5.md:65-66`, `KNOWLEDGE.md:119` and `LEVER_RULES_v3.md:215`: a named exception, "a regrade Ayush orders for a judge-only edit on a pushed task may be packaged (sentinel 28 Oct, decisions.jsonl:391,396,400)", or keep the ban and mark sentinel as a one-off (Q1).
- `knowledge/INDEX.md`: add the `_ql/` inbound folder, P16 and P17. Mark P7 v2 and P8 v2 retired for QL reports (both read `_COMMON_RULES.md` v1 at line 9).
- `knowledge/FP_DOSSIER.md`: create it with the header `| date | slug | finding | kit rule file:line | why false | source (QC round / QL round) |`.
