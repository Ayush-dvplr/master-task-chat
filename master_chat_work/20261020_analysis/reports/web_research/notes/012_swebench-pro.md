# 012 SWE-Bench Pro: Can AI Agents Solve Long-Horizon Software Engineering Tasks? (Deng, Da et al., Scale AI, 2025)
URL: https://arxiv.org/abs/2509.16941 | Type: paper | File: sources/012_swebench-pro.pdf
## What it is
1,865 human-verified, human-augmented multi-file tasks from 41 repos (public 731 / held-out 858 / commercial 276), with failure-mode clustering of trajectories. Later revisions exist (see last bullet).
## Key findings (with cites)
- Selection by size: trivial 1-10 line edits excluded; reference patch avg 107.4 lines across 4.1 files; every task >=10 changed lines, >100 tasks >100 lines [§1 p2]
- Public set: Sonnet 4.5 43.6%, Sonnet 4 42.7%, GPT-5(high) 41.8%, Haiku 4.5 39.5%, Kimi K2 27.7%, gpt-oss-120b 16.2% (50-turn cap, SWE-Agent) [Table 1 p6; §5 p6]
- Commercial (private startup repos) set: best Opus 4.1 17.8%, GPT-5 15.7%, GPT-4o 3.6%; gap vs public attributed to enterprise codebase difficulty [Table 2 p6]
- Success vs size: stable for 1-file problems, sharp declines as file count rises; >10% only for frontier models at 10+ files [§6.1 p7, Fig 3]; some repos <10% for all models, others >50% [§6.1 p7]
- Ablation: giving only the problem statement (no human-written requirements + interface) drops GPT-5 25.9% -> 8.40% and Opus 4.1 22.7% -> 8.20% (false negatives from tests expecting specific names/signatures) [Table 3, §6.2 p8]. Setting for Table 3 assumed 50-turn/$2 analysis cap: UNVERIFIED.
- Failure modes (GPT-5 judge, last 20 turns of unresolved runs; 87% judge-human agreement cited from SWE-agent paper): Opus 4.1 mostly wrong solution (text: 35.9%) and syntax errors (24.2%); Sonnet 4 mostly context overflow (35.6%) + endless file reading (17.0%); Gemini 2.5 tool errors 38.8%, syntax 30.5%; Qwen3-32B tool errors 42.0% [§6.3 p8]. Table 4 (p9) numbers differ from the text; cite the text only, treat Table 4 as UNVERIFIED (column alignment lost in extraction).
- Authors' ceiling statement: top models ~23% vs >70% on SWE-Bench Verified [§8 p9]
- Abstract-only (UNVERIFIED beyond abstract): SWE-Bench Pro V2 (arXiv 2610.24206) says 480 of 731 public tasks were repaired/retired, and frontier agents then resolve up to 99.4% of 642 tasks; "SWE-Bench Pro Verified" (2609.08149) reports reward hacking via leakage + misleading statements inflating scores. Not downloaded.
## What lowers scores
- More files/lines per change; enterprise/private code; context overflow and endless file reading; semantic wrong solutions; unspecified interfaces (test expects names the agent was not told).
## Relevance to our constraint (rules visible)
- partly. Adding visible requirements+interface raised scores ~3x, so visible rules help; the residual difficulty (multi-file semantic correctness, long exploration, context management) survives. The V2 abstract warns that much "difficulty" can be spec/test defects, not capability.
