# 014 tau-bench: Tool-Agent-User Interaction in Real-World Domains (Yao, Shinn, Razavi, Narasimhan; Sierra, 2024)
URL: https://arxiv.org/abs/2406.12045 | Type: paper | File: sources/014_tau-bench.pdf
## What it is
Agent talks to an LLM-simulated user, calls DB-writing tools, and must obey a written domain policy; reward = final database state (+ required info in messages) vs annotated goal. Introduces pass^k (all k trials succeed). Models are 2024-era.
## Key findings (with cites)
- Policy is fully visible (system prompt), yet gpt-4o pass^1 is 61.2 retail / 35.2 airline; claude-3-opus 44.2 / 34.7 [Table 2 p7]
- Reliability: gpt-4o retail pass^1 >60% but pass^8 <25% [§5.1 p7, Fig 4; abstract p1]
- Failure breakdown of 36 agent-caused failures (of 40 failures in 115 gpt-4o retail trajectories; 4 more were task typos): wrong argument/info ~55% (complex database reasoning, wrong totals, omitted info), wrong decision/rule not followed 25%, partial resolution of compound requests 19% [§5.2 p7-8, Fig 5]
- Concrete rule miss with visible rule: policy says exchange tool "can only be called once", all items must be collected first; agent exchanged one item, second never exchanged [§5.2 p8, App. C.2.1]
- Number of ground-truth DB writes per task predicts failure (more writes = harder) [Fig 6 p8]; agent "stops after checking only one order" when asked to fix addresses in all orders [§5.2 p8]
- Removing the policy from the prompt: gpt-4o retail 61.2 -> 56.8, airline 33.2 -> 10.8 (-22.4); retail rules are near common sense, airline rules ad-hoc (baggage by tier/cabin) [Table 3 p8]
- Hallucinated IDs: gpt-4o 0.46 non-existent-ID tool calls per retail task vs gpt-3.5 2.08 (FC) and 6.34 (Act) [§5.2 p8]
- Design: user instruction written so "only one possible outcome" exists under the policy; reward is rule-based DB comparison, no LLM judge [§3.2 p4]
## What lowers scores
- Many dependent write actions in one task; ad-hoc (non-commonsense) rules; numeric/inventory lookups over a large DB; skipping a rule that is written down; omitting implicit sub-actions; run-to-run inconsistency.
## Relevance to our constraint (rules visible)
- yes. The policy is visible and models still lose rule-following (single-call constraints, collect-before-act) and enumeration completeness. Ad-hoc rules (not commonsense) give a much larger gap than rules a model can guess. Dated models: absolute numbers UNVERIFIED for current models.
