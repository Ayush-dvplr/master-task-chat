# 010 BenchEvolver: Frontier Task Synthesis via Solution-Centric Evolution (Wu, Li et al., UC Berkeley/Tsinghua, 2026; arXiv 2606.01286v1, 31 May 2026)
URL: https://arxiv.org/abs/2606.01286 | Type: paper | File: sources/010_benchevolver.pdf
## What it is
Method to turn saturated coding benchmarks (LiveCodeBench, SciCode) into harder verifiable variants by mutating the reference solution; measures difficulty by target-model pass rate.
## Key findings (with cites)
- Saturation numbers: on LiveCodeBench frontier models >99% Pass@1 on easy split, >90% average across difficulty levels [Abstract p.1; §1 p.2]
- Difficulty is defined behaviourally: attempt succeeds only if it passes ALL hidden tests; lower mean pass rate = harder [§3.1 p.3]
- Design principle: "dominant algorithmic lift" - a change to solution structure that makes the parent approach insufficient (stronger asymptotic strategy, richer data structure/state maintenance, new mathematical reformulation, or natural constraints that invalidate the parent's simple shortcut); accepted tasks judged by executable failure "rather than by surface complexity, longer statements, adversarial formats, or obscure edge cases" [§3.2 p.4]
- Effect: Hard split avg pass@1 87.0% -> 45.7% (-41.3 pts); Medium 96.5% -> 69.6% (-26.8); GPT-5.4 94.8% -> 49.7% and DeepSeek-V4-Pro 83.7% -> 23.2% on Hard [§4.2 p.9, Table 3]
- LiveCodeBench-Plus (91 problems): pass@1 from 27.5% (DeepSeek-V4-Pro) to 62.6% (GPT-5.5); kept only problems with mean pass@1 in 0.05-0.75 [§4.2 p.9]
- Statement-first synthesis is fragile: "ambiguous specifications, hidden assumptions, and superficial complexity can pass undetected" when the same model verifies; solution-first grounds tests in executable semantics [§3.2 p.3]
- Tests organised in small/medium/large/stress regimes; examples and expected outputs come from running the evolved reference [§3.2 p.4]
## What lowers scores
- Tasks where the memorised/standard algorithm is insufficient and a different data structure or reformulation is needed (single-shot coding tasks, not agentic).
## Relevance to our constraint (rules visible)
- yes for the principle (not agentic): difficulty from algorithmic lift while every rule stays in the statement; plus empirical filter 0.05-0.75. Evidence limited to competitive-programming/SciCode, not terminal tasks. Contamination/saturation point: public problems saturate (>90%).
