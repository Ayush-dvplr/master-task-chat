# EVIDENCE_MAP

Every graded rule in this task has a governing sentence (see RULE_TRACE.md, column 2). No graded rule rests on a shipped fact alone, so the determinate-fact table of LEVER_RULES 0b (`rule | test ids | shipped fact file:line | wrong readings it contradicts`) has no rows.

Shipped facts that support stated rules (none is the sole authority for a graded value):

- Network constraint pairs lie in one lane: stated in docs/replan_contract.md line 27; network_constraints.json pairs name two assets of one region and crew type in assets.jsonl.
- Load rows exist for every region and season day: stated in docs/replan_contract.md line 11; load_forecast.tsv has 4 x 91 x 6 rows.
- `published_at` timestamp form: docs/intake.md lines 22 and 34; published_plan.json `published_at` is an ISO Z string and log stamps use the same form.

UNIQUENESS.md: not applicable (no L11 lever and no S3 candidate space).
