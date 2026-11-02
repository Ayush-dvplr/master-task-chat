# 028 LLMs Still Can't Plan; Can LRMs? A Preliminary Evaluation of OpenAI's o1 on PlanBench (Valmeekam, Stechly, Kambhampati, 2024)
URL: https://arxiv.org/abs/2409.13373 (v1, 20 Sep 2024) | Type: paper | File: sources/028_planbench-o1-lrms.pdf
## What it is
PlanBench Blocksworld (3-5 blocks, 2-16 step plans, 600 instances), Mystery (syntactically obfuscated, same problem), Randomized Mystery (random strings, full PDDL), plus 110 larger instances (6-20 blocks, 20-40 step plans) [§2-3, p.2-4]. Full rules are given in the prompt. Fast Downward (classical planner) is the 100% reference.
## Key findings (with cites)
- Best pre-o1 LLM on plain Blocksworld: LLaMA 3.1 405B 62.6%; on Mystery Blocksworld no LLM reaches even 5% [§2, p.2, Table 1].
- o1-preview: Blocksworld 587/600 (97.8%); Mystery 317/600 (52.8%) zero-shot (41.6% one-shot); Randomized Mystery 224/600 (37.3%). o1-mini: 56.6% Blocksworld, 19.1% Mystery. Fast Downward 600/600 in 0.265 s average vs o1-preview 40.43 s (plain) / 83.37 s (Mystery) / 111.11 s (Randomized) [Table 2, p.3].
- Longer plans: o1-preview only 23.63% on 110 Blocksworld instances needing >=20 steps (6-20 blocks); most successes are below 28 steps [§3, p.4-5, Fig. 3].
- Unsolvable-instance detection: o1-preview true-negative rate only 27% on Blocksworld (0% false negatives); Randomized Mystery 16% TN / 11.5% FN. Earlier models ~0% [Table 3, p.5].
## What lowers scores
- Renaming/obfuscating familiar domains (same logic, unfamiliar tokens); plan length > ~20-28 steps; unsolvable instances (models invent a plan); format deviations needed parser rescue [fn.6, p.4].
## Relevance to our constraint (rules visible)
- Partly. All rules visible, yet the 2024 LRM falls from 97.8% to 23.6% by plan length and 37% under random renaming. But 2024 data: 2025-26 models UNVERIFIED (see 030 for a 2026 benchmark). A terminal agent with Python could write BFS/A* (or install a planner), which neutralises Blocksworld-scale search; difficulty survives only when the search space is large enough that naive search times out, or when "no solution exists" must be detected and reported honestly.
