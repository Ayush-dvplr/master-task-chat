# JUDGE_MAP - district-heat-flex-procurement (redesign r4, 25 Oct 2026)

| id | oracle shows it at (solve.sh / solve.py / solve.sh self-check stage) | test it must not overlap |
|---|---|---|
| R1 own extract, drawn allowance (w3) | solution/solve.sh self-check stage R10 recompute of remaining allowance on the oracle's own outputs (`check R10 ok`) | selection_match(_hard): tests grade reported selections, not the agent's own fixture |
| R2 start order on own extract (w3) | solve.py `ledger_order` + solve.sh self-check stage R10 walks events in ledger order | allowance_ticks_mutation grades rerun output only |
| R3 composed rate above cap on own extract (w3) | solve.sh self-check stage R11 recomputes effective rates (start + uplift + adder, capped) (`check R11 ok`) | credit_rows_match(_hard) grade values only |
| R4 half-cent interval amount on own extract (w3) | solve.sh self-check stage R11 per-interval half-even recompute | credit_rows_match(_hard) |
| R5 allowance ledger in one named function (w3) | solve.py `choose_all` + `holder` | none (code structure; no test reads source) |
| R6 exact arithmetic (w1, instruction following) | solve.py `half_up` / `half_even` integer helpers, no float | canonical_serialization_and_integer_units grades output types only |
| R7 final run after last edit exits 0 (w1) | solve.sh runs derive_report.py then solve.sh self-check stage after the last write | none (trajectory act) |
| R8 claims a check its output contradicts (-5) | oracle claims nothing; solve.sh self-check stage exits 1 on mismatch | none (judge-only act; test negatives grade hardcoding, grader reads, imports) |
| R9 recomputes grant cents outside the program (w3) | solve.sh self-check stage `check R9 ok (grant cents of 2000 event-regions recomputed)` via solve.sh | grants_match(_hard) grade program output, not an outside recompute |
| R10 recomputes remaining allowance via draws_from (w3) | solve.sh self-check stage `check R10 ok` | selection_match(_hard), ledger_quality_match(_hard) |
| R11 recomputes credit_cents outside the program (w3) | solve.sh self-check stage `check R11 ok (credit_cents of 2000 event-regions recomputed)` | credit_rows_match(_hard) |
| R12 | solve.py: named functions (load, choose_portfolio, credit_cents, share_pool, holder, choose_all, build, assemble), no bare except, every function under 150 lines | none (no test grades code shape) |
