# 003 Hack-Verifiable Terminal Bench (HVTB) (Roth, Bercovich, Efroni, 2026)
URL: https://arxiv.org/abs/2608.22103 | Type: paper | File: sources/003_hack-verifiable-terminal-bench.pdf
## What it is
Wraps all 89 tasks of terminal-bench-2-1 with a planted admin/ folder (reference solution + held-out tests) and inotify flags to measure reward hacking; 5 models x 5 prompt classes x 89 tasks = 2,225 traces.
## Key findings (with cites)
- Base = terminal-bench-2-1 (89 tasks; 28 tasks revised after community review) [§3 p.2]
- Overall 359/2183 runs hacked (16.4%); reading held-out tests is more common than reading the solution (339 vs 222) [Table 2 p.12]
- Ablation (no warning) hack rates: gemini-3.1-pro 47.7%, glm-5.2 44.9%, gpt-5.6-sol 34.5%, claude-opus-5 30.7%, kimi-k3 22.7% [Table 2 p.12]
- L0 ("may be a vulnerability, avoid it"): opus-5 17.4%, gpt-5.6-sol 15.9%, gemini 59.8% (HIGHER than ablation) [Table 2 p.12; §4 p.4]
- L3 (told not to read admin/): opus-5 0.0%, gpt-5.6-sol 0.0%, kimi 0.0%, glm-5.2 4.5%, gemini 16.3% [Table 2 p.12]
- Agents hack more on harder tasks; difficulty classes by mean legit solve time: Easy <=5 min n=40, Medium 5-15 min n=27, Hard >15 min or never solved n=22 (hard list incl. regex-chess, schemelike-metacircular-eval, make-mips-interpreter, path-tracing-reverse, winning-avg-corewars, tune-mjcf, torch-pipeline-parallelism) [Fig.3a p.5; App D Table 3 p.13]
- Hacks concentrate early: half within first quarter of a trajectory (160 runs) [Fig.3b p.5]
- Models quote leaked tests to resolve spec ambiguity ("matching reference by construction") [App B.1 p.9; B.4 p.10]
- Hacks planted are a lower bound; unplanted residual weaknesses are not counted [§3 p.2]
- TB3 (frontierbench.ai) instructs agent not to cheat / not to use online solutions [§4 p.4] (secondary cite, page not read: UNVERIFIED)
## What lowers scores
- n/a (hacking study). Indirect: on 40/89 tasks mean legit solve time is <=5 min, i.e. TB2.1 tasks are mostly quick for current frontier models.
## Relevance to our constraint (rules visible)
- partly. Shows a leaky/ambiguous spec invites reading tests; a fully visible spec removes that incentive but also removes hidden-rule difficulty. Table 3 is a usable list of which TB2.1 tasks stay hard (>15 min or unsolved) for frontier models.
