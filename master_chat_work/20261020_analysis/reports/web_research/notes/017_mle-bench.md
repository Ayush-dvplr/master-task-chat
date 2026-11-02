# 017 MLE-bench: Evaluating Machine Learning Agents on ML Engineering (Chan, Chowdhury, Jaffe et al., OpenAI, ICLR 2025)
URL: https://arxiv.org/abs/2410.07095 | Type: paper | File: sources/017_mle-bench.pdf
## What it is
75 offline Kaggle competitions with grading code and a leaderboard snapshot; success = medal-level result vs humans. Agents get 24 h on 36 vCPU/440 GB/1 A10. Models are 2024-era.
## Key findings (with cites)
- Headline: o1-preview + AIDE reaches any medal in 16.9% +- 1.1 (bronze 3.4, silver 4.1, gold 9.4), above-median 29.4%; gpt-4o AIDE 8.7%; claude-3.5-sonnet AIDE 7.6%; gpt-4o MLAB 0.8%; gpt-4o OpenHands 4.4% [Table 2 p6]
- Partial-credit ladder in the grader: made submission -> valid submission -> above median -> bronze/silver/gold (o1-preview: 98.4 / 82.8 / 29.4 / 3.4 / 4.1 / 9.4%) [Table 2 p6]
- Valid-submission gap: gpt-4o AIDE made a submission 70.7% but valid only 54.9%; "all agents often failed to create valid submissions despite access to a validation server ... did not always use it" [Table 2; §3.1 p6]
- Premature stopping: MLAB and OpenHands "tend to end their runs early, sometimes within the first few minutes" despite being told to use the full 24 h; AIDE keeps re-prompting up to 500 nodes [§3.1 p6]
- Resource blindness: all three agents failed to factor in compute/time limits (overloaded disk/RAM, process killed, run ended); "rarely verbalized any consideration of how long their produced code would run" [§3.1 p6]
- Debugging: agents do well when "well-known approaches" apply but "struggle to debug issues and recover from missteps" [§1 p2]
- Complexity tiers by expert-hours (Low <2 h, Medium 2-10 h, High >10 h): o1-preview any-medal 34.3% Low, 8.8% Medium, 10.0% High [App. A.9 Table 9 p28; definition §2.1 p3]. Non-monotonic at High: UNVERIFIED reason
- Newer competitions are harder: medals on 2013-2022 contests but struggle after 2022 [Fig 9 p28]
- More attempts: pass@6 roughly doubles pass@1 (o1-preview and gpt-4o) [Fig 3 p7]; time 24 h -> 100 h only 8.7% -> 11.8% for gpt-4o AIDE; most medals arrive in first few hours [§1 p2; §3.4 p8]; doubling GPUs / CPU-only made no difference (9.1 / 8.7 / 10.2%); agent never used the 2nd GPU [Table 3 p7]
## What lowers scores
- Invalid output format, stopping early, ignoring time/memory limits, failure to recover from errors, tasks with no standard recipe.
## Relevance to our constraint (rules visible)
- partly. Visible-rule failures that survive: not running the provided validator, ignoring stated resource/time limits, quitting early. The graded ladder (valid -> above median -> medal) is a template for partial credit. Scores are mainly bounded by method novelty rather than rule discovery.
