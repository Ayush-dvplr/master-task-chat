# 029 NPHardEval: Dynamic Benchmark on Reasoning Ability of LLMs via Complexity Classes (Fan, Hua et al., 2023-24)
URL: https://arxiv.org/abs/2312.14890 (v4) | Type: paper | File: sources/029_nphardeval.pdf
## What it is
900 algorithmic questions: 3 P tasks (Sorted Array Search, Edit Distance, Shortest Path), 3 NP-complete (Graph Coloring decision (GCP-D), TSP decision (TSP-D), Knapsack (KSP)), 3 NP-hard (TSP optimisation, Graph Coloring optimisation (GCP-O), Meeting Scheduling (MSP)), difficulty levels per task (count of 10 per abstract/§4 summary; exact generator parameters not read); monthly refresh; 12 models (GPT-4 Turbo, Claude 2, GPT-3.5, Claude Instant, PaLM 2, open models) [§3-4, p.4-8].
## Key findings (with cites)
- Averaged over 12 models, weighted accuracy: P 0.24, NP-complete 0.25, NP-hard 0.02 [§5.1, p.10]. Significant gap P vs NP-hard and NP-complete vs NP-hard (p<0.05) [§5.1.1, p.11].
- Failure rate (wrong output format / no valid answer) rises with complexity; open-source models fail more often than closed ones [§5.1, p.11].
- GPT-4 Turbo is the frontrunner on most tasks; Claude 2 best at mid-level NP-complete zero-shot; on Knapsack only GPT-4 Turbo showed promising performance [§5.1, p.10; §5.1.1, p.12].
- Per-level accuracy curves (10 levels) are in Fig. 4-6 only; not extracted - UNVERIFIED.
## What lowers scores
- Optimisation (not decision) versions of NP-hard problems where the answer must be optimal and exactly formatted; larger instances.
## Relevance to our constraint (rules visible)
- Partly. Models are Dec-2023 era (GPT-4 Turbo, Claude 2); 2025-26 reasoning models UNVERIFIED and likely much better on small instances. A terminal agent with Python bypasses small NP-hard instances with brute force / ILP / OR-tools (if installable). Difficulty survives only when instance sizes defeat brute force and no solver is on the machine and heuristic quality is scored (partial credit by tour length).
