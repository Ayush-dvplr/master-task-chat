# 009 Life After Benchmark Saturation: A Case Study of CORE-Bench (Nadgir, Kapoor, ... Narayanan, 2026; arXiv 2606.26158v1, 23 Jun 2026)
URL: https://arxiv.org/abs/2606.26158 | Type: paper | File: sources/009_life-after-saturation-core-bench.pdf
## What it is
Case study of an agentic benchmark (CORE-Bench Hard, computational reproducibility) that saturated; audits construct validity, OOD transfer, reliability, scaffold effects, human uplift.
## Key findings (with cites)
- Saturation: top agent 100% and next four 97.4% on the 39-task CORE-Bench v1.1; Carlini's Claude Code scaffold reached near-ceiling on CORE-Bench Hard [§2.1 p.4, Table 2]
- Log analysis found 15 task-level errors and 20 tasks with exploitable shortcuts in CORE-Bench Hard that "would have been difficult to surface before accuracy saturation" (weaker agents never progressed far enough to hit shortcuts/grading bugs) [§1 p.2; Table 10 p.19]
- Shortcut example: agent guesses a plot label from matplotlib's default colour order; grading error example: 95% prediction interval missed float rounding / alternate valid answers; unsolvable: dead download URL [Table 10 p.19; A.3]
- OOD suite (19 tasks, new disciplines) is also saturated: GPT-5.2 (medium) 100%, GPT-5.4 (xhigh) 100%, others 84.2-94.7% [Table 4 p.4]
- Scaffold effect: same model GPT-5.4 (medium), Codex CLI beats CORE-Agent by ~44 pp; Opus 4.5 82.1% on both CORE-Agent and OpenCode but outcomes disagree on 12/39 (31%) tasks; oracle router per task gets 100% [§2.1 p.4; §3.3 p.7]
- Reliability: agents with same mean accuracy differ in consistency; mean empirical pass rate 93% but mean stated confidence only 32.1%; confidence not better than random at separating correct from incorrect [§3.1 p.5]
- "retire-and-replace" pattern: ARC-AGI 1->2/3, MMLU->MMLU-Pro, HumanEval->HumanEval+, SWE-bench->SWE-bench Pro [§1 p.1]
## What lowers scores
- Mostly earlier: version/dependency conflicts were the dominant failure pre-saturation [Table 10 caption p.19]. Today no accuracy failures to analyse (ceiling).
## Relevance to our constraint (rules visible)
- partly. Evidence that tasks solvable by "README + code + data" with documented procedure saturate; surviving signal is in efficiency/consistency, not accuracy. Also a warning: tasks with exploitable shortcuts or ambiguous grading look hard to weaker models and then collapse once models progress further (hardness that is really a validity bug disappears).
