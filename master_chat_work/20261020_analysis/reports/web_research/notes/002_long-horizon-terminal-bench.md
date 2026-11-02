# 002 Long-Horizon-Terminal-Bench (LHTB) (Li, Li, Shi et al., 2026; arXiv v3 9 Oct 2026)
URL: https://arxiv.org/abs/2607.08964 | Type: paper | File: sources/002_long-horizon-terminal-bench.pdf
## What it is
46 Harbor tasks, 9 categories, graded by weighted subtasks (dense reward) with hidden stress suites; 17 frontier models, Terminus-2, 90-min budget.
## Key findings (with cites)
- Best Grok 4.5: 28.3% (13/46) at R>=0.95, 19.6% (9/46) at R=1.0; mean over models 6.4% (R>=0.95) and 3.2% (R=1.0) [Abstract p.1; §3.1 p.5; Fig.3 p.6]
- Mean reward: Grok 4.5 0.51; Grok 4.20 0.10 (lowest); 10 of 17 models solve 0 tasks at R=1.0 [§3.1 p.6; §3.2 p.6]
- Of 782 runs (17x46): 50 pass (6.4%), 241 (30.8%) R<0.05, 491 (62.8%) partial; 223 runs (28.5%) R>=0.5 [Fig.4 p.7]
- Avg per run: 239 episodes, 9.8M tokens, 88.9 min, $10.8 [Table 1 p.8]
- Unresolved runs: 79% (518/660) timeouts, 19% early exits, 3% harness errors; timed-out runs have mean R only 0.10-0.35 per model, i.e. NOT close to done [Fig.6 + text p.9]
- False finish: 124 self-terminated runs; 14 with R>=0.75 stopped with ~20 min left (e.g. duckdb-optimizer-closure R=0.92; seven models stopped on apex-law433-matter at R 0.80-0.87) [§3.5 p.10]
- Near-misses (0.75<=R<0.95) 90 vs passes 50; Kimi K2.6 best near-miss 0.94 on grammar-fuzz-coverage-hunt [§3.2 p.6-7]
- Grading: public checks are low weight (CLI behaviour, formats, simple examples); most weight on hidden stress cases: nested manifests, gzip+base64 wrappers, renamed fields, missing values, injected noise, rotated/cropped frames, alt coordinate/time conventions [§2.3 p.5, Fig.1 p.3]
- Difficulty calibration: repeatedly ran DeepSeek-V4-Pro under 1.5 h budgets, adjusted until "challenging but solvable"; 120 candidates -> 46 kept [§2.3 p.5]
- Reward R = sum(w_k r_k)/sum(w_k); resolved if R>=0.95 [§2.2 p.3-4]
- Authors' claim: bottleneck is long-horizon completion/time budgeting and self-verification, not local correctness; contrasts with TB2 where trials finish <20 min [§3.4 p.9]
## What lowers scores
- Long dependent workflows with a deliberately broken project; hidden schema variants; running out of 90 min while still "busy"; stopping early with unverified residual defects.
## Relevance to our constraint (rules visible)
- partly. Time-budget exhaustion and false-finish (weak final verification) survive full visibility. BUT their main lever (hidden stress cases with undocumented schema variants) would fail our QC unless the variants are spec-legal and written in visible files. Dense subtask grading is the same shape as our weighted tests; only 6.4% pass at 0.95 yet 62.8% get partial credit.
