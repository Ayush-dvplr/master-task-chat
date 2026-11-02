# 030 PlanBench-XL: Long-Horizon Planning of LLM Tool-Use Agents in Large-Scale Tool Ecosystems (Liu, Lin, ... Ji, Hakkani-Tur; UIUC, 2026)
URL: https://arxiv.org/abs/2606.22388 (v1, 21 Jun 2026) | Type: paper | File: sources/030_planbench-xl-2026.pdf
## What it is
Interactive benchmark: 327 retail tasks, 1,665 tools, retrieval-limited tool visibility; optional "blocking" (missing / failing / distracting tools) forces re-planning. 10 LLMs incl. GPT-5.4, Gemini-3.1-Pro, Gemini-3.5-Flash [Abstract, p.1; §4, p.6]. Overlaps agent B (agentic benchmarks); kept for 2026 failure-mode data on recovery.
## Key findings (with cites)
- Default setting accuracy: Gemini-3.1-Pro 77.06%, GPT-5.4 51.90%, Gemini-3.5-Flash 52.19%, GPT-5.4-Mini 3.07%, Llama-3.3-70B 18.96%, Qwen3-8B 0.00% [Table 3, p.7].
- GPT-5.4: 51.90% block-free -> 11.36% under the most severe blocking condition [Abstract, p.1]; ~30% with only one feasible path left and slightly above 10% when only the LONGEST valid path remains [§5, p.9, Fig. 3].
- Silent (implicit) failures are the most harmful: lowest accuracy for all models; untrusted-input reuse rate (UIRR) 11.99% implicit vs 9.67% explicit vs 9.89% misleading tools [§5, p.8].
- Exploration depth (Mean EDT) correlates with accuracy r=0.902, but not sufficient: Llama-3.3-70B has similar EDT to GPT-5.4 (19.20 vs 20.65) yet 18.96% vs 51.90% [§4, p.7].
- Takeaway 6: simply scaling test-time compute (more interaction) yields only limited gains [§5, p.9; details of the experiment not read - UNVERIFIED].
## What lowers scores
- Silent wrong output from a tool; recovery requiring a longer alternative path; fewer viable paths; agents reusing values from failed calls.
## Relevance to our constraint (rules visible)
- Partly yes. The rules are visible but the environment misbehaves silently (a spec-legal tool/input returns plausible garbage); models propagate it. This is a design lever for Terminal tasks: spec-legal edge-case inputs that make a helper produce quiet wrong output. Not an arithmetic/Python-bypassable failure. Evidence is for GPT/Gemini, not Claude (Claude models not seen in the result tables I read) - UNVERIFIED for Opus-class.
