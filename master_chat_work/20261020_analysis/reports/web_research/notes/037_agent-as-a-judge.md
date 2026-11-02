# 037 Agent-as-a-Judge: Evaluate Agents with Agents (Zhuge et al., Meta/KAUST, 2024)
URL: https://arxiv.org/abs/2410.10934 | Type: paper | File: sources/037_agent-as-a-judge.pdf
## What it is
DevAI benchmark (55 AI-dev tasks, 365 hierarchical requirements) graded per requirement; compares Human-as-a-Judge, LLM-as-a-Judge and an agentic judge that can read files/trajectories. Read abstract, §1, §3, §4.1 (pp.1-9).
## Key findings (with cites)
- Requirement-level (dense) grading: 365 hierarchical requirements over 55 tasks [Abstract p.1]. Humans: GPT-Pilot and OpenHands each satisfy ~29% of requirements (dependency-aware), ~44% ignoring prerequisites, but each fully solves only 1 task (task solve rate 1.81%, MetaGPT 0.00%) [§1 p.2; Table 2 p.6: Req met (I) 22.13/44.80/42.89%, (D) 6.55/28.96/28.68%]. => dense per-requirement scores sit far above all-or-nothing solve rates (e.g. 28.7% vs 1.81%).
- Single human judges are unreliable: pairwise disagreement 10-30% [§3.2 p.7]; one evaluator's error vs consensus up to 23.77% (GPT-Pilot); majority vote of 3 reduces overall error to 6.01%, still ~5% vs consensus with small groups [§3.2 p.8].
- Agent judge aligns with human consensus 90% vs LLM-as-a-Judge 70% [§1 p.2]; saves 97.72% time, 97.64% cost vs 3 human experts [p.3].
- Argues final-outcome-only grading (e.g. SWE-bench resolve rate) hides intermediate process info [§1 p.2].
## What lowers scores
- Task dependency chains: requirements met drop from 44.80% (independent) to 28.96% (dependency-aware) for GPT-Pilot, 22.13% -> 6.55% for MetaGPT [Table 2 p.6]. Upstream failure invalidates downstream requirements.
## Relevance to our constraint (rules visible)
- partly: (1) supports a dependency-ordered, per-requirement weighted checklist; (2) a judge that can inspect files/trajectory is closer to humans than a plain LLM judge (90% vs 70% agreement), so judge rubric should be concrete per-item; (3) dependency chains cut scores even when each requirement is stated. Judge reliability numbers are for 2024 judges (UNVERIFIED for current Opus).
