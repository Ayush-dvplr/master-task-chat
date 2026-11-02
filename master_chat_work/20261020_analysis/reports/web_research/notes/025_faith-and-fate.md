# 025 Faith and Fate: Limits of Transformers on Compositionality (Dziri et al., NeurIPS 2023)
URL: https://arxiv.org/abs/2305.18654 (v3) | Type: paper | File: sources/025_faith-and-fate.pdf
## What it is
Three compositional tasks (long-form multiplication up to 5x5 digits, Einstein logic-grid puzzles, a DP problem) expressed as computation graphs to quantify depth/width of the required reasoning [§2, p.3-4].
## Key findings (with cites)
- Off-the-shelf ChatGPT / GPT-4 reach only 55% / 59% on 3-digit x 3-digit multiplication [§1, p.2].
- Zero/few-shot accuracy "deteriorates from near perfection to zero" as problem size (digits, houses/attributes, sequence length) and graph depth grow [§3.1, p.4, Fig. 2]. Exact per-size numbers are in the figure only; not extracted - UNVERIFIED.
- Fine-tuning on all multiplication pairs up to a size (~1.8M pairs) gives high in-distribution accuracy but fails on larger OOD splits; training far past the overfitting point (30K steps) does not help OOD [§3.1, p.5-6, Fig. 3-5].
- Models get single steps right but fail to plan/compose them; 82.3% of correct final answers for 4-digit x 2-digit multiplications still contained >=1 wrong node in the computation graph (memorisation / pattern matching, not algorithm) [§3.2, p.7].
- Theory: error probability grows exponentially with reasoning depth for autoregressive generation; repeated application of a function can give unbounded errors [§4, p.8-9, Prop. 4.1/4.2].
## What lowers scores
- Deep + wide computation graphs; large digit counts; novel (OOD) problem size; puzzles needing global constraint propagation.
## Relevance to our constraint (rules visible)
- Models tested are GPT-3/3.5/4 (2023). Frontier reasoning models (2025-26) with CoT do far better on mid-size multiplication (UNVERIFIED here, no 2025 data read in this note). For a terminal agent with Python, arithmetic/multiplication is TRIVIALLY BYPASSED (python -c). Only the logic-grid/DP "plan and compose" flavour matters, and a solver (CSP/brute-force) also bypasses small instances. Use as support for "do not rely on arithmetic or small puzzles" rather than as a difficulty source.
