# P14 Task analysis, v2 delta (DRAFT, R4 1d26a6e, 28 Oct 2026)

This is a delta on `prompts/templates/P14_task_analysis_v1.md`. Insert these items; nothing else changes. Each item cites the R4 evidence that motivates it.

## Phase A additions
- A-new-1 Score conventions. Before counting points, check on 3 tasks that `final = (tests + rubric) / 2`, and confirm which `passed` value applies a negative. In the stage-1 repo, rubric negatives apply on `passed=False`; this reconciles on 90/90 (R4 losses.py).
- A-new-2 No failure messages. When `verifier/test-stdout.txt` holds only the reward, judge wrong value vs crash from:
  1. the artifacts manifest (every deliverable `ok`);
  2. the judge's exact-figure justifications, which quote the agent's own shipped-data figures;
  3. the agent's final message.
  If none of these settles it, mark the check UNVERIFIED (R4 genuineness.md method line).
- A-new-3 Identifiability of withheld facts. When TRUTH.md says a fact is withheld or undocumented, record:
  - (a) whether its candidate space is stated in an agent-visible file (file:line);
  - (b) whether uniqueness is shown globally or only by a one-step sweep;
  - (c) whether the evidence is confirm-only (digests) or gives partial signal.
  If (a) fails, the verdict is RISKY for our rules (Never 6), even when the loss is genuine. Seen in 8defd7be TRUTH.md:121-127, d49e259f, and 5b2b0901 TRUTH.md:51.
- A-new-4 Instructed caps. If the instruction tells the agent to stop or limit effort (5b2b0901 instruction.md:36), report the share of loss that follows the cap. That share is not a lever.
- A-new-5 Channel split. Report `loss_tests = (100 - tests) / 2` and `loss_judge = (100 - rubric) / 2` in final points, plus `50 / P` (final points per judge weight). A task whose band comes from the judge while tests >= 85 is flagged "judge-only band" (725e575c).
- A-new-6 Band source. Use the stored run's report.json, not a README score; note any README mismatch above 5 points (d22ff871: 51 vs 32.36).

## Phase B additions
- B-new-1 Weight geometry. Report the weight share on hidden instances and the mean weight of hidden vs shipped checks (G3a "cheap shipped, dear hidden").
- B-new-2 Judge composition. Report the share of exact-figure criteria, split into headline figures and counterfactual what-ifs (J11), plus the share of trajectory probes and the negatives that name a specific wrong reading.
- B-new-3 Time use. Report agent minutes / budget and the first-write minute. Note an early stop with budget left (8defd7be at 63%, b5c7b14c at 4%).

## Result json additions
`"loss_tests_pts", "loss_judge_pts", "pts_per_judge_weight", "hidden_wshare", "identifiability": "stated|unbounded|n/a", "instructed_cap": true|false`.

CHANGELOG line (proposed): `P14 v2 (28 Oct 2026): score-convention check, no-message genuineness path, identifiability of withheld facts, instructed caps, channel split and 50/P, weight geometry, judge composition, time use; evidence master_chat_work/20261028_upgrade/R4_teammate_repo/`
