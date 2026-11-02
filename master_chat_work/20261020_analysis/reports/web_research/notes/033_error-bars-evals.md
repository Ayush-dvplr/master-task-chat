# 033 Adding Error Bars to Evals: A Statistical Approach to LM Evaluations (Miller, Anthropic, 2024)
URL: https://arxiv.org/abs/2411.00640 | Type: paper | File: sources/033_error-bars-evals.pdf
## What it is
Statistical recipe for eval standard errors, clustered SEs, resampling (K answers/question), paired model comparison and power analysis. Read pp.1-10 (full text of §1-5).
## Key findings (with cites)
- SE of mean (CLT): SE = sqrt( (1/(n-1) * sum (s_i - s_bar)^2) / n ) [Eq.1, p.3]. For 0/1 scores: SE_Bernoulli = sqrt(s_bar(1-s_bar)/n) [Eq.2, p.3]. 95% CI = s_bar +/- 1.96*SE [Eq.3, p.3].
- Fractional (non-binary) scores: using SE_Bernoulli is conservative (too wide) vs the CLT SE [p.3]. => for our 0.5 tests + 0.5 judge score, use the sample-variance formula (Eq.1), not the Bernoulli one.
- Var(mu_hat) = Var(s)/n = (Var(x)+E[sigma_i^2])/n: question-difficulty variance Var(x) + within-question run noise E[sigma_i^2]; resampling K times divides only the second term: Var(s_i)=sigma_i^2/K [§3, §3.1, p.5].
- Worked example (binary scores, difficulty ~U[0,1]): Var(x)=1/12, E[sigma^2]=1/6; K=2 cuts total variance by 1/3, K=4 by 1/2, K=6 by 5/9; upper limit 2/3 [§3.1, p.5]. Resampling beyond K>>2 gives little gain.
- Clustered questions can inflate SE: clustered SE up to 3.05x naive on DROP (1.34 vs 0.44) [Table 4, p.4; Eq.4].
- Do not lower temperature to cut variance; it can raise Var of conditional means (1/12 -> 1/4) [§3.3, p.6].
- Power: n = (z_{a/2}+z_b)^2 (w^2 + sA^2/KA + sB^2/KB)/delta^2 [Eq.9, p.9]; example n~969 questions to detect delta=0.03 at 80% power, alpha=0.05; with n=198 and K 1->10 the minimum detectable effect falls 13.2% -> 7.5% [p.10].
## What lowers scores
- N/A (statistics paper). Lesson: with only a handful of runs per task, CIs are wide; need n (tasks) not only K (runs).
## Relevance to our constraint (rules visible)
- partly: not a difficulty source; it fixes how many trajectories are needed to claim "true mean < 0.30". The formula treats runs on ONE task as resamples (K), whose SE shrinks only until task-difficulty variance dominates; with one task, Var(x) is not estimable from the runs.
