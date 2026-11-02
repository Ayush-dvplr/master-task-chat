# 040 On Randomness in Agentic Evals (Bjarnason, Silva, Monperrus; KTH; ICLR 2026 Workshop, 2026)
URL: https://arxiv.org/abs/2602.07150 (v3, 2026-03-25) | Type: paper | File: sources/040_randomness-agentic-evals.pdf
## What it is
60,000 SWE-Bench-Verified trajectories: 6 agent configs (3 models x 2 scaffolds) x 10 independent runs x 2 temperatures. Quantifies run-to-run variance, pass@k vs pass^k, and runs needed. Read §1-3 and App. A (pp.1-10).
## Key findings (with cites)
- Single-run pass@1 varies by 2.2 to 6.0 pp across 10 runs of identical config; SD > 1.5 pp even at temperature 0 [Abstract p.1; Table 1 p.5]. Examples: DeepSWE-preview/nano-agent T=1.0 31.4% +/- 1.0 (range 28.8-32.4); Qwen3-32B/R2E-Gym T=0.6 23.9% +/- 1.4 (21.4-26.4) [§2.4.1 p.4]. These SDs are of the AGGREGATE resolution rate over the ~500-task benchmark (SWE-Bench-Verified task count 500 is from memory, UNVERIFIED in my read), not per-task.
- Temperature 0 does not give determinism; variance did not fall (Qwen3-32B nano-agent SD 0.7% at T=0.6 vs 1.2% at T=0) [§2.4.1 p.5].
- DeepSWE-preview/r2e-gym: pass@1 34.4%, pass@5 52.9% (+18.5), pass^5 15.5% (<half of pass@1) [p.6]. Devstral-2/nano-agent pass@1 63.5%, pass@5 76.2% (+12.7), pass^5 49.1% (-14.4); max pass@1->pass@5 gain 24.9 pp (Devstral-2 on r2e-gym, T=0) [§2.4.2 p.6; Intro p.2]. pass^k cites Yao et al. 2025 (tau-bench; see source 014).
- Runs diverge early (first few percent of tokens) and the differences cascade; longer trajectories amplify variance [Abstract p.1; §2.2 p.8].
- Runs needed (80% power, normal assumption, comparing two agents): 1% gain needs 36 runs at SD 1.5 (8 at SD 0.7, 51 at SD 1.8) for p<0.05; 2% gain: 9 (SD 1.5), 13 (SD 1.8); 5%: 2-3; 10%: 1 [Table 2 p.9; §3.2 p.9-10]. Normality of pass@1 over runs held in 11/12 groups (Shapiro-Wilk, n=10) [fn.1 p.9].
## What lowers scores
- N/A (variance study). Lesson: with 10 runs the observed mean has SD ~ sigma/sqrt(10); long agentic trajectories amplify noise.
## Relevance to our constraint (rules visible)
- partly: the numbers are benchmark-aggregate variance (500 tasks), NOT per-task. For a single task the run-to-run variance is binomial/continuous per-run and much larger (see computation in D_findings). Use as evidence that 1 run is not reliable and that >=8-10 runs are the practical minimum to estimate a mean.
