You are mining every QC report we have received, to find out why our QC rounds do not converge: which fix caused which new finding, where the reviewer judged the same text differently, and which defences held. Board id: `ef7d851`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261024T1004_qc_reports_mining_B.md`.

Why (Ayush, 24 Oct): every task loops through QC rounds (schema 7, emberforge 7, dispatch 6, vendor 6). Findings do not shrink: sentinel went 5/6/3, then 2/4/7, then 1/2/3; dispatch went 0/3/4 at v4 and 3/4/3 at v6 after a judge rework. A twin session (`5087cd2`, prompt `20261024T1004_qc_kit_reverse_A.md`) is reverse-engineering the kit source in parallel. Do NOT read or wait for its output; the master merges both on the check `id`.

## Rules that survive compaction
- First thing: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" ef7d851`. If it fails, note it and carry on. Run it again at the very end.
- Tools are always available; never claim otherwise without a real call and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `OUT/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Keep `OUT/TODO.md` and `OUT/LOG.md` current after every step. Read files in pieces of at most 50 KB.
- READ-ONLY study. Never edit the QC kit, the harness clone, any bundle, `QC/`, `QC assigned/` or `master_chat_tasks/`. Read-only git only. No Docker, no network. Write only to OUT and scratch (`/tmp/qc_reverse_B-<YYYYMMDDTHHMM>/`).
- Do the work yourself. No subagents.
- Every claim cites `file:line` and quotes the words. Something you did not confirm is labelled UNVERIFIED.

## Inputs
- QC reports: `/Users/mac/Desktop/Terminal Bench/QC/reports/<slug>/v*.md`, `result_<sha>.json`, `_progress*.md`, for all 9 tasks (cohort-retention-reconciliation, dispatch-plan-reoptimization, district-heat-flex-procurement, emberforge-vault-settlement, match-replay-desync-audit, schema-migration-plan-repair, sensor-network-lsq-correlated-adjustment, sentinel-policy-recompute, vendor-archive-roundtrip-recovery). `QC/PATH_MAP.md` explains the layout.
- The bundle QC actually reviewed, per round: `/Users/mac/Desktop/Terminal Bench/QC/copies/<qc sha>/` (the sha matches `result_<sha>.json`). Diff consecutive copies of the same task to see what changed between rounds.
- What we told the fixer and what it did: `/Users/mac/Desktop/Terminal Bench/master_chat_work/<date>_<slug>/` (p12_r*/RECHECK_FIX.md and its "Deviations" and "Trap survival" sections, harden_r*/, PL_NOTE.md) and the matching prompts under `master_chat_tasks/prompts/issued/<slug>/`.
- Timeline: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/board.json` (each session's step, sha, issued time) and `decisions.jsonl`.
- Our fix rules and defences: `master_chat_tasks/knowledge/QC_FIX_PLAYBOOK.md`, `QC_RULINGS.md`, and `master_chat_work/bundles/_work/<slug>/QC_DEFENCE.md`.
- Kit, only to quote a check's wording: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (HEAD 71a653b2). Match checks on id AND wording; ids may have been renumbered between rounds.
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261024_process/qc_reverse/B/`

## Phase 1: fire table
One row per finding in every report: `task, qc_version, qc_sha, kit_head (as the report states), id, severity (fail/minor/warn/suggest), kit_wording_quoted, bundle_file:line, short_finding, next_round_status`. `next_round_status` is one of: fixed, recurred (same id, same place), moved (same id, new place), escalated, downgraded, kept-accepted (our KEEP/REBUT held), kept-rejected, last-round. Write `OUT/FIRE_TABLE.md`, `OUT/fires.json`, and a per-id rollup `OUT/by_check.json`: `{id: {fires, tasks, fail, minor, warn, recur_rate, escalations}}`.

## Phase 2: cause of every new finding
For every finding in round N+1 that was not in round N, find its cause with evidence (the copy diff plus the fix direction or RECHECK_FIX line):
- `fix-induced`: our fix for finding X created it. Record `X -> Y`, the edit that did it, and whether the playbook row used for X predicted it.
- `harden-induced`: a harden or lever change (not a QC fix) created it.
- `reviewer-variance`: the text it cites did not change between the two copies (prove it with the diff), yet it was not flagged before, or a sibling task with the same pattern passed.
- `escalation`: a warn or kept item we left alone was raised.
- `kit-change`: the kit head changed between the rounds and the rule moved.
- `new-scope`: the reviewer looked at something it had not looked at before (say what).
Write `OUT/CASCADES.md` and `OUT/cascades.json` (`{task, from_version, to_version, cause, from_id, to_id, edit_file_line, evidence}`). Then a matrix `OUT/FIX_SIDE_EFFECTS.md`: for each fixed id, which new ids its fixes produced and how often (this is the "which new fails a fix can cause" column).

## Phase 3: variance and defences
- `OUT/VARIANCE.md`: the same or near-identical bundle text judged differently across rounds or across tasks; quote both verdicts.
- `OUT/DEFENCES.md`: every KEEP/REBUT we sent (QC_DEFENCE, PL_NOTE, fix directions): did the next QC accept it? Which wording held and which did not.
- `OUT/PLAYBOOK_AUDIT.md`: for each QC_FIX_PLAYBOOK row, how often it was applied, whether the finding came back, and whether the trap survival table showed lever loss. Mark each row WORKS / LEAKS / BACKFIRES with evidence.
- Loop accounting: for each task, rounds, findings per round, which rounds were caused by our own fixes, and the first round where stopping would have been right under the 3-round drop rule.

## Deliverables
`OUT/SUMMARY.md` (at most 60 lines): the 10 checks that cost the most rounds, the top fix -> new-finding chains, the share of new findings by cause, playbook rows that backfire, and "Lessons for the master". Also `OUT/result.json`: `{board:"ef7d851", reports_read, findings_total, new_findings_by_cause:{...}, top_checks:[...], top_chains:[...], playbook_backfires:[...], status:"done"}`.
End your final reply with: `Next session: board ef7d851 done. Paste back: done : ef7d851`.
