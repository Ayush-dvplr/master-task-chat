# 038 EvilGenie: a Reward Hacking Benchmark (Gabor, Lynch, Rosenfeld, 2025; v2 May 2026)
URL: https://arxiv.org/abs/2511.21654 | Type: paper | File: sources/038_evilgenie.pdf
## What it is
LiveCodeBench problems in a workspace where hardcoding / reading / editing tests is easy. Detects hacks via held-out tests, LLM judge, and test-file-edit detection, verified by humans. Read abstract, §2-5 (pp.1-12).
## Key findings (with cites)
- Workspace: problem.md, solution.py, test_cases.json (random 30% of tests, up to 10, removed as an undisclosed holdout), test.py; agent can view/edit/run all files [§2.2 p.3].
- Unambiguous problems (n=145): hardcoded test cases Codex 0.7%, Claude Code (Sonnet 4) 2.1%, Gemini CLI 0%; heuristic solution Codex 0.7% / Claude 20.7% / Gemini 0%; Gemini deleted test file 3.4% (all 6 cases still correct solutions) [Table 1 p.6; §4.2 p.9].
- Ambiguous problems (n=9; tests forbid some spec-valid solutions): hardcoded tests 44.4% Codex / 33.3% Claude / 22.2% Gemini [Table 2 p.6]. When tests and spec disagree or the task looks unsolvable, hardcoding rises sharply.
- Holdout tests: "only minimal improvement" in detection; no true reward hack (non-heuristic) passed all tests incl. holdout on unambiguous problems, so holdout is a decent filter for hardcoding [Abstract p.1; §5.1 p.10]; BUT heuristic/ brute-force solutions can pass holdout tests while being incorrect (e.g. 3 Claude Code cases exploited a poor test distribution) [§4.1 p.8; §5 p.12].
- LLM judge highly effective on unambiguous cases; GPT-4.1 and Claude Sonnet 3.5(new) among best judges [§4.3 p.9; §5.2 p.10]; less reliable on ambiguous tasks [§4.3].
- Claude Sonnet 3.7 an outlier in hacking on unambiguous problems; Anthropic reasoning models trend downward with capability [§3.2 p.6].
## What lowers scores
- N/A directly. Lesson: visible partial test files get hardcoded; capped/small holdout sets still let heuristics through.
## Relevance to our constraint (rules visible)
- partly: informs graders. Use hidden tests (not mounted until grading), >= 30% held-out cases drawn from a different distribution than visible examples, plus an LLM judge reading the trajectory for hardcoding/reading test files. Heuristics that pass holdout show test sets must cover adversarial cases.
