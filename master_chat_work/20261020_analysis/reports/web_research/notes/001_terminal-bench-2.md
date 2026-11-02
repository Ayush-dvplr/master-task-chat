# 001 Terminal-Bench: Benchmarking Agents on Hard, Realistic Tasks in CLIs (Merrill, Shaw et al., 2026)
URL: https://arxiv.org/abs/2601.11868 (only v1 exists, submitted 17 Jan 2026; checked abs page) | Type: paper | File: sources/001_terminal-bench-2.pdf
## What it is
The TB2 paper: 89 crowd-sourced, 3x-reviewed terminal tasks (Harbor format), 32,155 trials across 6 agents x 16 models, plus difficulty calibration and failure taxonomy.
## Key findings (with cites)
- 229 tasks from 93 contributors; 89 kept by author difficulty + 3 reviewers; ~3 reviewer-hours per task [§2.2 p.3; Fig.3 caption/§2.3 p.4]
- Verification criteria: Specificity (tests pass iff acceptable end state; instruction describes ALL correct end states), Solvability (oracle), Integrity (no shortcuts) [§2.3 p.4]
- Best: GPT-5.2 Codex CLI 62.9%+-3.0; Opus 4.5 Terminus 2 57.8%+-2.5; Gemini 3 Pro 56.9%+-2.5; Sonnet 4.5 42.8%+-2.8 [Table 2 p.81]
- Empirical difficulty = Terminus 2 pass rate across frontier models: Easy >=66.7%, Medium 33.3-66.7%, Hard <33.3% [§4.3 p.8]
- Human-predicted vs empirical: r=0.436 (p<0.001); of human-"hard" tasks 93.3% empirically hard; of human-"medium" 54.5% empirically hard, 29.1% medium, 16.4% easy [§4.3, Fig.7 p.8]
- Human-medium-but-model-hard tasks "require creative or adversarial reasoning rather than pattern-following" (XSS filter bypass, Redcode corewars strategy); human-medium-but-model-easy are "procedural subtasks (e.g., documentation adherence)" [§4.3 p.8]
- Failure taxonomy (Terminus 2, Execution/Coherence/Verification): Execution errors (disobey spec, step repetition, unaware of termination) dominate for Opus 4.5 and GPT-5.2; coherence+verification lower [§4.4 p.9, Fig.8]; no per-class percentages in text (UNVERIFIED numbers)
- Command-level: error rate 9.2% (Grok 4) to 26.7% (GPT-OSS-120B); command-not-found 24.1% of 3,800 sampled failures [§4.5 p.9-10]
- Most trials <20 min, <25 model calls, <10M tokens; max ~2h / ~100M tokens; essentially no correlation between turns and success [§4.1 p.7; App A.2 p.21; Fig.35]
- Some tasks unsolved by any model: complex system configuration, kernel driver compilation, database migration [Fig.11 caption p.22]
- Expert-time estimates: <1h 48.6%, 1h-1d 47.3%, 1d-1wk 4.1%; junior: <1h 8.1%, 1h-1d 71.6%, 1d-1wk 16.2%, >1wk 4.1% [Table 1 p.5]
- Predicts saturation: SOTA nearly doubled between Gemini 2.5 Pro and GPT-5.2 (8 months) [§4.2 p.7]
- No private test set; only canary string; "largely symbolic" (ABC item III.3 = 0) [§5 p.10; App B.5 p.28]
- Debug-tool rule: if ALL trials fail the same tests -> likely insufficient instructions; if trials fail DIFFERENTLY -> fair difficulty [App B.3 p.26-27]
- Example fabrication failure: mteb-leaderboard, fetch errors then agent wrote a guessed model id and finished [App C.3 p.34]
## What lowers scores
- Tasks needing creative/adversarial reasoning (exploit crafting, game strategy), long system builds/configs, kernel/db work; verification gaps (premature termination, weak verification: "fabricating data that should have been recovered") [§4.3, App C.1 p.29]
## Relevance to our constraint (rules visible)
- partly. TB2 requires instructions to describe ALL correct end states, so difficulty has to come from reasoning/search/long chains, not hidden rules. Opus 4.5 at ~58% means a typical TB2 task is too easy for the <20% goal; only the empirically "Hard" bucket (<33.3%) is comparable. Paper gives no per-category pass rates in text (Fig.11 is an image).
