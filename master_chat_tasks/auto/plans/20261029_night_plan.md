# PLAN: night 29 Oct 03:55-08:30 (Ayush 02:30-02:40; gate v3.7)

Until: 08:30 IST
Paid runs: no cap (Ayush 02:33: "no cap but try to improve and give me result"); each run only on frozen QC-passed bytes, never twice on the same bytes
Workers/harness/Docker: 5 / 2 / 2 Docker-heavy (metered 8 GiB may run beside one other Docker-heavy job; Docker has 16 GiB)
Budget: paid run only with no LIMIT and <= 2 busy workers; <= 3 busy while it runs; fresh window -> paid run first
Wind-down: running sessions and running paid runs finish their current step after 08:30; nothing new
Last spawn: 08:10
Model: anthropic/claude-opus-5-5 only (auto.py default; no Kiro)

Ayush's words (verbatim):
> so the idea is simple for today auto mode in this we are going to use anthropic claude ony not kiro ... so i wants 2 complete qc passed task with gate passed in harness whichever you sleect woek only on that , here's one pl feedback and task they fixed qc , fix harden , and score it under gate score too so total 4 tasks ... the session will be from 3:55 till 8:30 am
> (on a miss) do you best and you can give recomendation because out of this 4 i wants atleast 3 gate passed including QC

Answers 02:33-02:40: tasks cold-chain + metered; district = fix REAL fails + minor (JD-5), warns only if real and cheap, false positives -> reply; tariff = take QL edits, QC, harden, run < 40; 5 workers / 2 harness; up to 2 harden + rerun rounds per task, then Needs Ayush; priority metered > cold-chain > district > tariff; gate met on district/tariff -> pl_ready, Output_RFP untouched (Ayush repackages); QL reply drafts yes; start scheduled 03:55; nothing before 03:55.

Goal: >= 3 of the 4 tasks with QC PASS (P11 v3, 0 fail) and 1 valid run on those frozen bytes meeting the gate (tests < 85 AND rubric < 85 AND final < 40).

## Do, in this order (from 03:55)
1. 03:55 cold-chain-backbone-quote: paid run first (fresh window). Bytes = Tasks_INPUT tree 8ca9c267f59b = QC v4 copy 78b8d5b (MINOR G05-M1 PL note). `auto.py harness <Tasks_INPUT/cold-chain-backbone-quote>`. Predicted ~56, so expect a miss: on result -> gate_run copy + TRIP.md + intake --apply -> if missed, P9 v4 harden (gate v3.7 DESIGN READY bar, from the run's trajectory) -> master go only if DESIGN READY (a)-(e) met -> build -> P11 v3 recheck vs v4 copy 78b8d5b -> PASS -> freeze -> run.
2. 03:55 metered-usage-rating-pipeline: short worker finishes QC v1 report from kept Step 10 results (master_chat_work/20261028_metered-usage-rating-pipeline/qc_v1_step10_ac12c0b/; oracle 1.0x3, nop 0, stub 0, owner-only 1.0; no rerun) -> writes Step 10 section, verdict, result_ac12c0b.json in QC/reports/metered-usage-rating-pipeline/. FAIL -> P12 v4 fix -> recheck. PASS -> diff bundle == Tasks_INPUT == QC copy, freeze tree_sha -> run (as soon as the budget allows; predicted 39.8-45.7) -> missed -> harden round.
3. 03:55 district-heat-flex-procurement (pushed, frozen e9d91966ed25; Q2 a: QL asks for fixes + lower score): P16 triage of master_chat_work/_ql/district-heat-flex-procurement/20261029T0235_report/QL_REPORT.md (findings QL1-F1..F11) -> P12 v4 fix of REAL/PARTLY rows (fails + JD-5; warns only if REAL and cheap) -> P9 v4 harden to gate v3.7 (fixes add hidden coverage; harden from run a12 trajectory) -> P11 v3 recheck vs QC v9 copy 3f737e9 -> PASS -> freeze -> run -> gate met -> pl_ready + QL reply draft (QL_REPLY_TEMPLATE) at _ql/district-heat-flex-procurement/20261029T0235_report/REPLY_QL.md.
4. 03:55 tariff-engine-audit-repair (pushed, frozen 0de116d29fdb): P17 handback of _ql/tariff-engine-audit-repair/20261029T0235_zip/ (REQUEST = lower_score with QL edits; his edits: tests/test_output.py, solution/solve.py, solution/TRUTH.md) -> take his clean edits -> P9 v4 harden from his trajectory (81.35/27.27/54.31) -> P11 v3 full or recheck as ROUTE.md says -> PASS -> freeze -> run -> gate met -> pl_ready + QL reply draft.
5. Spawn order inside the budget: harness cold-chain first, then at most 3 busy workers while it runs (metered report, district P16, tariff P17). More workers (up to 5) only while no paid run is RUNNING.

## Rules per event
- Same as auto/plans/20261028_day_plan.md "Rules per event", with gate v3.7 (final < 40) and the v3.7 DESIGN READY bar in _COMMON_RULES_v5 rule 17.
- After a run: copy to master_chat_work/20261029_<slug>/gate_run_a<N>/, trajectory_readout TRIP.md, `intake.py --job SLUG --bundle PATH --event gate_run --apply` (district/tariff: `--event ql_rerun`). Gate met -> stage pl_ready. Missed -> harden from that trajectory -> QC recheck -> run; at most 2 harden + rerun rounds per task, then Needs Ayush with a recommendation.
- QC PASS -> freeze: diff bundle == Tasks_INPUT == QC copy, record tree_sha in the registry (status.py set SLUG tree_sha=...).
- district/tariff are pushed: never touch Output_RFP; Tasks_INPUT edits only through the fix/harden worker with backups; pushed copy stays at its frozen tree in master_chat_work/bundles backup.
- Priority when the budget or time is short: metered > cold-chain > district > tariff.
- At 08:10: no new spawns; recommend in REPORT.md the next step for every task not at the gate.

## Do not
Push or commit. Edit rule files, templates, GOALS or policy. Touch other pushed, parked, killed, dropped tasks or schema. Repackage Output_RFP. Docker prune. Re-run the same bytes. Use any model other than anthropic/claude-opus-5-5.

## Timed steps (the watcher delivers each at its time)
- at 08:10: last spawn time: no new spawns; write recommendations for each task in REPORT.md.
