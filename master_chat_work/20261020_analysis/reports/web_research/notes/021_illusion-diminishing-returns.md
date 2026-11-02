# 021 The Illusion of Diminishing Returns: Measuring Long Horizon Execution in LLMs (Sinha, Arun, Goel et al., ICLR 2026)
URL: https://arxiv.org/abs/2509.09677 (v3, 13 Mar 2026) | Type: paper | File: sources/021_illusion-diminishing-returns.pdf
## What it is
Isolates "execution" from planning/knowledge: plan (keys) and knowledge (in-context dict of 5-letter words -> ints in [-99,99]) are given; model keeps a running sum over T turns, K keys/turn [§3, p.5].
## Key findings (with cites)
- Horizon length H_s = ln(s)/ln(p) under constant independent step accuracy p; growth is hyperbolic, sharp beyond ~80% single-step accuracy [§2.1, p.4, Prop. 1].
- Per-step accuracy is NOT constant: it falls as turns increase; "self-conditioning": the more errors in the context history, the worse the next step (induced error-rate sweep, turn-100 accuracy falls monotonically) [§3.2, p.7, Fig. 5].
- Scaling model size fixes long-context degradation (Kimi-K2, DeepSeek-V3, Qwen3-235B near-perfect at turn 100 with a healed history) but NOT self-conditioning [§3.2 Result 4, p.7].
- Thinking models (Qwen3 thinking) do not self-condition: turn-100 accuracy stable regardless of error rate in history [§3.2 Result 5, p.7-8, Fig. 6]. Prompting to self-verify does not fully fix it for non-thinking models [p.8, §C.1 - appendix not read].
- Without CoT, even frontier non-thinking models (DeepSeek-V3, Kimi K2, Qwen3-32B) cannot do more than ~6 chained steps in one turn [§3.3 Result 6, p.8, Fig. 7a].
- Max steps in a single turn at >=80% accuracy (binary search on K): GPT-5 2176, Claude-4 Sonnet 432, Grok 4 384, Gemini 2.5 Pro 120 [§3.3 Result 7, p.8]. DeepSeek-R1 ">100" [p.2].
- Majority voting (parallel compute) helps only marginally for execution length [p.8, §D - appendix not read].
## What lowers scores
- Many dependent steps with state carried across turns; earlier mistakes left in context; no CoT/thinking; models only 2025 vintage (Claude-4 Sonnet, GPT-5) tested - newer models UNVERIFIED.
## Relevance to our constraint (rules visible)
- YES for execution by hand: a long chain of simple dependent lookups/accumulations fails even with plan and data given. BUT the task is trivially bypassed by a terminal agent running Python (a running sum is one line). Only helps if the chain cannot be scripted (e.g. needs reading/judgement per step) or the agent must keep state in-head over many turns.
