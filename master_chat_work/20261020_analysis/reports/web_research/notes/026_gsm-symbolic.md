# 026 GSM-Symbolic: Understanding the Limitations of Mathematical Reasoning in LLMs (Mirzadeh et al., Apple, ICLR 2025)
URL: https://arxiv.org/abs/2410.05229 (v2) | Type: paper | File: sources/026_gsm-symbolic.pdf
## What it is
Templates of GSM8K questions with variable names/values (50 sets x 100 templates), a clause-count difficulty ladder (GSM-P1/P2), and GSM-NoOp (add an irrelevant but plausible clause). 8-shot CoT [§3-4].
## Key findings (with cites)
- All models show non-trivial variance across instantiations of the SAME question: Gemma2-9B best-worst gap >12% [§4.1, p.5]; changing only numbers hurts more than changing only names [§4.3, p.7-8, Fig. 4].
- 21 of 25 models score on original GSM8K above 1 sd of their GSM-Symbolic distribution -> possible contamination [§4.1, p.7].
- Adding clauses (GSM-P1 -> P2) lowers accuracy and raises variance in all models; the drop rate itself accelerates [§4.2, p.8-9, Fig. 6].
- GSM-NoOp (one irrelevant clause) accuracy drop vs GSM8K: Phi-3-mini -65.7, GPT-4o-mini -40.0, GPT-4o -32.0, o1-mini -29.1, o1-preview -17.5 points [§4.4, p.10, Fig. 8a; values read from figure labels]. Models "blindly" convert distractor statements to operations (e.g. "discount" -> multiplication) [§4.4, p.9].
- Giving 8 shots drawn from NoOp questions does not remove the drop (Fig 8b/8c) [p.10].
## What lowers scores
- Plausible-but-irrelevant details, more clauses, changed numbers; distractor sentences placed in otherwise clear specs.
## Relevance to our constraint (rules visible)
- Partly. Models are 2024 (o1-preview best, still -17.5). 2025-26 frontier effect UNVERIFIED (a 2026 re-evaluation exists: arXiv 2605.28700 "Importance of Being Statistically Earnest" - title seen in search only, not read). A terminal agent could compute the arithmetic in Python, but distractor handling is about reading, not computing: relevant for specs with plausible-but-inapplicable clauses and for precedence/applicability rules.
