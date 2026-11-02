# 035 Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (Zheng et al., 2023)
URL: https://arxiv.org/abs/2306.05685 | Type: paper | File: sources/035_mt-bench-llm-judge.pdf
## What it is
Foundational study of LLM judges: biases (position, verbosity, self-enhancement), weak math/reasoning grading, mitigations, and agreement with humans. Read §3-4 (p.4-7).
## Key findings (with cites)
- Position bias: swapping answer order, consistency GPT-4 65.0%, GPT-3.5 46.2%, Claude-v1 23.8% (default prompt); Claude-v1 prefers first position 75.0% [Table 2, p.5].
- Verbosity bias "repetitive list" attack on 23 answers: failure rate Claude-v1 91.3%, GPT-3.5 91.3%, GPT-4 8.7% [Table 3, p.5].
- Self-enhancement: GPT-4 favours itself with +10% win rate, Claude-v1 +25%, GPT-3.5 not; authors say data too limited to conclude [§3.3, p.5].
- Math/reasoning grading: judge can be misled by the answers shown even when it can solve the problem alone [§3.3 p.6]. GPT-4 judge failure rate on 10 math questions (20 judgments): default 14/20, CoT 6/20, reference-guided 3/20 [Table 4, p.5]; text: 70% -> 15% with reference-guided [§3.4 p.6]. Even CoT judge often repeats the answer's mistake [§3.4 p.6].
- Mitigations: swap order and require agreement in both orders, else tie [§3.4 p.6]; few-shot judge raises GPT-4 consistency 65.0% -> 77.5% but makes calls ~4x more expensive [§3.4 p.6].
- Agreement: GPT-4 vs humans 85% (non-tie, setup S2) vs human-human 81%; overall ">80% agreement" [§4.2 p.7; Abstract].
## What lowers scores
- N/A (judge study). Lesson: a judge can be fooled by long/confident traces and by wrong-but-plausible answers; scores drift with order and verbosity.
## Relevance to our constraint (rules visible)
- partly: relevant to the 0.5 LLM-judge half. A judge given a reference solution / explicit checklist (reference-guided) fails far less; a judge with no reference is unreliable on exact-computation tasks. Run the judge >1 time or with shuffled order if score is borderline. Models here are 2023-era (UNVERIFIED for Opus-class judges).
