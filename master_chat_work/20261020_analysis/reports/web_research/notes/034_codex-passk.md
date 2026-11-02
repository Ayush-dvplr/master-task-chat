# 034 Evaluating Large Language Models Trained on Code (Chen et al., OpenAI, 2021)
URL: https://arxiv.org/abs/2107.03374 | Type: paper | File: sources/034_codex-passk.pdf
## What it is
Codex/HumanEval paper; introduces the unbiased pass@k estimator (n samples, c correct). Read §2.1 (p.2-3) and App. A (p.19).
## Key findings (with cites)
- Unbiased estimator: pass@k = E_problems[ 1 - C(n-c,k)/C(n,k) ], generated with n >= k samples/task (paper uses n=200, k<=100) [Eq.1, §2.1, p.3].
- Numerically stable code: `if n-c<k: return 1.0; return 1.0 - np.prod(1.0 - k/np.arange(n-c+1,n+1))` [Fig.3, p.3].
- The plug-in estimate 1-(1-p_hat)^k (p_hat = empirical pass@1) is biased: a consistent UNDER-estimate; gap does not fully close even for n>5k [App. A, p.19, Fig.13].
- Naive "any of k samples" per-problem estimate has high variance, hence the estimator [§2.1, p.3].
- Per-problem single-sample pass probabilities vary hugely: three example HumanEval problems for Codex-12B have p = 0.9, 0.17, 0.005 [Fig.2, p.3] -> task difficulty is a distribution, so mean over runs on ONE task is a single-task quantity.
- Headline: Codex-12B solves 28.8% (pass@1) and 77.5% when the best of 100 samples is chosen by unit tests [Abstract/§1 p.1-2; Table pass@1/10/100 = 28.81/46.81/72.31%, ~p.8].
## What lowers scores
- N/A. Lesson: pass@1 (mean over runs) is the right target for "average score < X"; pass@k with k>1 hides low per-run reliability.
## Relevance to our constraint (rules visible)
- partly: measurement tool only. For a task whose per-run success p is small, pass@8 can be high even if mean score is low; our criterion (mean score < 0.30) is a pass@1-style expectation, estimated unbiasedly by the sample mean of run scores.
