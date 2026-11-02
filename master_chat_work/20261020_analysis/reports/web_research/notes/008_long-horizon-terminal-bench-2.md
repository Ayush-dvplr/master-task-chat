# 008 Long-Horizon-Terminal-Bench 2.0 (Li, Li, Shi et al., 2026; arXiv 2610.14146v1, 9 Oct 2026)
URL: https://arxiv.org/abs/2610.14146 | Type: paper | File: sources/008_long-horizon-terminal-bench-2.pdf
## What it is
LHTB extended to 77 Harbor tasks (46 original + 31), 3-hour budget with verifier checkpoints every 30 min, 15 frontier models; adds "reconstruction" tasks (infer an artifact's behaviour from N public scenarios, graded on K hidden ones).
## Key findings (with cites)
- Best GPT-6-astra 48.1% (37/77) at R>=0.95, 42.9% at R=1.0, mean R 0.69; GPT-5.6-sol 41.6%, mean 0.67; Kimi K3 22.1%; others <=19.5% [§4.1 p.6-7, Fig.3]
- On 30 reconstruction tasks binary verifier avg 0.221 vs dense ladder avg 0.653 [Abstract p.1]
- Example reconstruction tasks, binary pass: lidar_icp 5/15 pass (10 models reached the oracle but scored 0 binary); chem_reaction_smarts 1/14 (binary 0.071); acoustic_beamforming 1/15 (0.067) [Fig.2 p.5]
- Category means (all models): Systems/perf/security 0.73 (highest); Scientific computing & simulation 0.30 and Multimodal & imaging 0.31 (two lowest); Audit-and-repair type mean 0.32, 11/23 solved by any model; Reconstruction 0.65, 26/30 solved by any [Fig.4 + §4.2 p.8]
- 24 tasks solved by no model; 20 are from released split, 12 are audit-and-repair; 9 tasks where no model exceeds R=0.2 (8 are audit-and-repair) -> "sustained debugging and repair, not a single missing final step" [§4.2 p.8]
- Time: median successful run solves after 57 min; 42% of all solves after the 1-hour checkpoint, 21% after 2 h; 189 solves over 1,143 runs [§4.3 p.8]
- Fast models "often claim completion long before they finish" [Intro p.2]
- QC: oracle R=1.0 on all hidden cases; starter materials "incomplete enough that solving requires genuine work"; an LLM reviews instruction-verifier alignment so instructions suffice "without revealing hidden answers" [§3.3 p.6]
- Harness hardening: stale verifier artifacts and hidden grader data leaking across phases found via checkpoints; successful trajectories audited for grader access [§2.3 p.3]
## What lowers scores
- Audit-and-repair of broken multi-stage pipelines; scientific simulation / multimodal workflows; inferring latent behaviour then generalising to unseen parameter scenarios (public feedback "is a hint, not the score") [§4.2 p.8; Fig.2 p.5]
## Relevance to our constraint (rules visible)
- partly. Reconstruction/hidden-scenario grading is the opposite of fully visible rules (the behaviour is only observable via examples) and would likely be flagged by TB-style QC as underspecified unless the generator contract is documented. Survives visible rules: long dependent debugging chains, premature completion claims, time budgets, near-miss on final checks.
