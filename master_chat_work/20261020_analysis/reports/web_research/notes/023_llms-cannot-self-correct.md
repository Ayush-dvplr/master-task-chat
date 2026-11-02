# 023 Large Language Models Cannot Self-Correct Reasoning Yet (Huang, Chen, ... Zhou, Google DeepMind, ICLR 2024)
URL: https://arxiv.org/abs/2310.01798 | Type: paper | File: sources/023_llms-cannot-self-correct.pdf
## What it is
Tests "intrinsic" self-correction (no external feedback / no oracle label) on GSM8K, CommonSenseQA, HotpotQA with GPT-3.5, GPT-4, GPT-4-Turbo, Llama-2 [§3, p.3-4].
## Key findings (with cites)
- With oracle labels deciding when to stop, GPT-4 GSM8K 95.5 -> 97.5; CSQA 82.0 -> 85.5; HotpotQA 49.0 -> 59.0 - this inflates "self-correction" [Table 2, p.4].
- Intrinsic (no oracle), GPT-4: GSM8K 95.5 -> 91.5 (round 1) -> 89.0 (round 2); HotpotQA 49.0 -> 49.0 -> 43.0; CSQA 82.0 -> 79.5 -> 80.0 [Table 3, p.4].
- GPT-3.5 CSQA collapses 75.8 -> 38.1 -> 41.8 after self-correction [Table 3, p.4]. All models' accuracy dropped across all benchmarks [§3.2, p.4].
- GPT-3.5 GSM8K: keeps initial answer 74.7% of the time; when it changes, correct->incorrect more likely than incorrect->correct. "LLMs cannot properly judge the correctness of their reasoning" [§3.3, p.4].
## What lowers scores
- Asking the model to re-check its own reasoning without a ground-truth signal (no test, no executable check).
## Relevance to our constraint (rules visible)
- Partly. Models are 2023-2024 (GPT-4, no reasoning models); whether 2025-26 reasoning models still degrade is UNVERIFIED here. Key lesson stands for design: self-review without an executable oracle is unreliable, so tasks where wrong answers LOOK right and no cheap test exists (but a terminal agent could write one) punish "looks done" behaviour. Python/tests = external feedback, which the paper says does help (oracle rows in Table 2).
