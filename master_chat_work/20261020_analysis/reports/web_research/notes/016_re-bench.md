# 016 RE-Bench: Evaluating frontier AI R&D capabilities of LM agents against human experts (Wijk, Lin, Becker et al., METR, 2024)
URL: https://arxiv.org/abs/2411.15114 | Type: paper | File: sources/016_re-bench.pdf
## What it is
7 open-ended ML research-engineering environments, each with a starting solution, a scoring function and a reference solution; 71 8-hour attempts by 61 human experts compared with agents under equal budgets.
## Key findings (with cites)
- Normalised score yn = (y - ys)/(yr - ys): starting solution = 0, reference solution = 1; worse-than-start clipped to 0; no score above 2 observed; avg human 8 h score is 0.5-1.5 per environment [§3.2.2 p8]
- Calibration with humans: with 8 h, 82% of expert attempts got non-zero score, 24% matched/exceeded the reference [abstract p1]; >70% of experts made progress in every environment [§3.5 p11]
- Hardness is relative to time budget: agents beat humans ~4x at a 2 h total budget but humans win at 8 h and keep improving with more time/samples [abstract p1; §1 p2; Fig 5 p14]. Agents (o1-preview, Claude 3.5 Sonnet) plateau after ~2 h while human scores keep rising [Fig 5 caption p14]
- Agents mostly score near 0 (do not improve on the starting solution) but have a long right tail; best-of-k raises the score: Claude 3.5 Sonnet keeps improving up to 128 30-min samples yet stays below humans given 32 h [§1 p2; §4 p13]
- Agents iterate faster: 36.8 (AIDE) and 25.3 (Modular) score attempts/hour vs 3.4 for humans [§5.1 p17]
- Failure analysis: (a) low variety, e.g. Restricted Architecture MLM: agents try lightly modified transformers 84% of the time though transformers work poorly there (37 high-scoring runs analysed) [§5.2 p17]; (b) consistent misreading of instructions, leading to loopholes that break rules [§5.2 p17]; (c) "perhaps the biggest" limit: long-horizon agency — not learning from new info, stubborn incorrect assumptions, ignoring contradictory information, not recovering from zombie processes holding VRAM [§5.2 p17, Figs 13,15]
- Evidence for context rot: Modular agent does better when context is wiped every 30 min, i.e. it accumulates more false assumptions than useful insights over time [§5.2 p17]
- Gap predictor: greater engineering complexity (lines of code edited by reference solution) favours humans (R^2=0.602); little need for exploration/discovery favours agents; the two exploration-heavy environments (Optimize LLM Foundry, Fix Embedding) had large gaps [§5.3 p18, Fig 10]
- Noise: a lucky agent score of 0.88 re-ran to 0.69 (Finetune GPT-2 for QA) [§5.1 p17]
## What lowers scores
- Long dependent engineering with many lines changed; needing exploration/discovery/diagnosis; stale beliefs carried through long context; time budgets beyond ~2 h; noisy scorers (overfitting luck).
## Relevance to our constraint (rules visible)
- yes. All instructions and scoring are visible and the gap persists via long-horizon belief maintenance and engineering volume. The normalised start=0 / reference=1 scheme is a ready partial-credit template. Models are 2024-era: UNVERIFIED for current Claude.
