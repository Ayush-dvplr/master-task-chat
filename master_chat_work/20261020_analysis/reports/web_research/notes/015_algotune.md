# 015 AlgoTune: Can Language Models Speed Up General-Purpose Numerical Programs? (Press, Amos, ... Press, NeurIPS D&B 2025)
URL: https://arxiv.org/abs/2507.15887 | Type: paper | File: sources/015_algotune.pdf
## What it is
154 tasks (13 categories); each has reference solver, generator, and verifier; models write faster code; score = speedup vs reference. Open-ended, no ceiling.
## Key findings (with cites)
- Scoring: per task = ref runtime / LM runtime on held-out inputs if verifier accepts all outputs; invalid or <1x are clamped to 1x ("mercy score"); overall = harmonic mean across tasks [§2.3 p5-6; §3 p6]
- Calibration of instance size: n chosen so the reference takes ~100 ms on 1 CPU core; timing = warmup + 10 repeats, min kept [§2.3 p5-6]
- Results at $1/task budget: o4-mini 1.72x, R1 1.70x, Gemini 2.5 Pro 1.51x, Claude Opus 4 1.33x [Table 2 p6]; o4-mini sped up 59.7% of tasks (>=1.1x; 92 tasks) [§4.1 p7]
- No novel algorithms found: speedups are "surface-level" (better library call, better parameters, Numba/low-level rewrite); Numba use went 1 -> 25 packages [§4.2 p7; Table 3 p7]. Highest examples: graph_isomorphism 52x, communicability >142x, ode_hodgkinhuxley 112x, feedback_controller 81x [§4.2 p7-8]
- Failure cases: svm: three models reached same CVXPY implementation (no speedup), Gemini 2.5 Pro never produced valid output on all test instances; lasso: Opus 4 hand-wrote Lasso, ran at 0.33x reference speed and ran out of budget [§4.2 p8]
- Anti-gaming: unit verifier only checking validity let an LM output a fast trivial suboptimal quantization; fixed by adding an optimality check. Narrow input distributions allow hard-coded answers [§2.2 p5]
- Verifier QA: rerun with different seeds; caught verifiers accepting only one of several valid solutions [§2.2 p4]
- Real headroom exists: merged PRs in NumPy/SciPy/NetworkX show 2.7x to >600x speedups, so references are not optimal [§2.1 p3]
## What lowers scores
- Tasks where reference is already a tuned library call with no better known algorithm; needing a different algorithm (not just a different call); validity failures on any test instance (score clamps to 1x); budget exhaustion.
## Relevance to our constraint (rules visible)
- yes. Everything is visible (reference, verifier, dev inputs) and models still find only surface-level gains. Useful partial-credit design: continuous speedup score clamped at 1.0, correctness gate first. Caveat: models are 2025-era; the clamp means scores cluster near 1x so thresholds should be log-scaled (design inference, not from source).
