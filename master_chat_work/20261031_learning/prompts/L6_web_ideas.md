# L6: Web research and brainstorm: new ways to make tasks hard (web search ON for this session only)
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_learning/L6_web_ideas/`

Web search is ON for you. Use it yourself in this chat (no sub-agents). Cite every outside claim with URL + date.
1. Research (aim 10-20 good sources): how hard agent benchmarks make tasks hard and fair (Terminal-Bench, SWE-bench variants, tau-bench, MLE-bench, OSWorld, ARC-style held-out generalisation, METR, frontier-model failure analyses 2025-2026), contamination/hidden-test practice, LLM-judge rubric robustness, which task traits frontier coding agents still fail on (long-horizon state, hidden-scale correctness, inferring conventions from data, numerical exactness, optimisation with hidden instances, spec ambiguity resolution). `SOURCES.md` (source, what it says, how it applies to us).
2. Check against us: read `master_chat_tasks/knowledge/LEVER_RULES_v3.md` (proven/promising levers), `knowledge/ANGLES.md`, the parked-task reasons in `master_chat_tasks/registry/tasks.json` (stage parked), and the gate (final < 40). Which outside ideas are new to us, which we already use, which failed for us and why.
3. Brainstorm 10 task ideas: domain, what the agent must do, the lever, why a strong agent's first program is WRONG on hidden inputs (not just slow), how it stays QC-clean (all rules stated, nothing pre-announced), how a design-blind test would kill it if it's easy. Rank by (chance final < 35) x (build cost). `IDEAS.md`.
4. Learning-method ideas: better ways for us to learn from each paid run (trajectory reading, failure taxonomies) with sources.
Extra: SOURCES.md, IDEAS.md.
