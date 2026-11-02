# Gemini Deep Research brief: what makes frontier coding agents fail on terminal tasks (academic and benchmark angle)

Paste everything below the line into Gemini Deep Research. Save its report as `/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/gemini/REPORT.md`.

---

I design evaluation tasks for autonomous coding agents in the style of Terminal-Bench (Harbor 0.24 task format). The agent (a frontier model such as Claude Opus or GPT-5 class, running in an OpenHands-style harness with a shell and file editor, no internet) receives a short plain-language instruction plus files in a Docker container and must produce output files or a working program. Grading has two halves: (1) deterministic pytest checks on the outputs, including checks run on hidden regenerated inputs the agent never sees, and (2) an LLM judge that scores the agent's trajectory and final reply against a rubric of stated facts.

My goal: tasks where a careful frontier agent scores roughly 10-20% on the deterministic checks, while the task stays fair: every rule needed is documented in the visible files, no hidden or unwritten rules, and no difficulty from sheer volume, arithmetic, puzzles, or output formatting. A human expert with the same files should be able to get 100%.

Evidence so far from our own runs: frontier agents score 85-100% on tasks we expected to be hard. They read all documents, write a program, recompute any shipped example outputs to confirm their reading, search parameter spaces exhaustively when an example pins the answer, and apply rule sentences literally when a rule's full composition sits in one sentence. Tasks from other teams that did score below 30% shared traits: rules split across files, a plausible "legacy default" contradicted by the authoritative source on a rare boundary, rules stated by omission ("for every other X"), no worked example that confirms the full answer, and grading of whole downstream documents on hidden inputs rather than isolated rule checks.

Please research and report:

1. Benchmark evidence. What do published results and analyses (Terminal-Bench, SWE-bench and SWE-bench Verified/Pro, SWE-Lancer, MLE-bench, RE-Bench, METR task suites, OSWorld, tau-bench, Aider, LiveCodeBench, HCAST, and others you find) say about which task properties most reduce frontier-agent success, as opposed to properties that only add noise? Give numbers where available.
2. Failure taxonomies. Summarise published taxonomies of agent failure modes (for example: specification misreading, premature verification, overfitting to visible examples, insufficient exploration, error compounding over long horizons, tool misuse, reward hacking). For each, which task-design choices legitimately expose it?
3. Long-horizon and dependency effects. Evidence on how error compounding across dependent steps, cross-file information integration, and conflicting or superseded documentation affect agent accuracy.
4. Verification behaviour. How agents decide they are done; when they self-test; how visible examples, unit tests, or sample outputs change their success rate (both helping and hurting). Evidence on "confirmation by example" making tasks easier.
5. Fairness and validity. Benchmark-design guidance (task validity, contamination, ambiguity audits, solvability checks, inter-annotator agreement) that keeps hard tasks fair. How do benchmarks separate "hard" from "ambiguous" or "broken"?
6. LLM-as-judge rubrics. Evidence on rubric criteria that discriminate well between strong and weak agent trajectories, and on criteria that judges score unreliably.
7. Anti-gaming. Known ways agents game deterministic graders (hardcoding visible outputs, reading test files, special-casing), and grader designs that resist them.

Output format:
- For each section: findings as numbered claims, each with source (title, authors/organisation, year, link) and a confidence level.
- Then a table "Design criteria we can implement": criterion; what it does to the agent; evidence; risk of making the task unfair; how to measure it in a task (a check we could run before shipping).
- Then "Things that do not work" (difficulty sources that add noise or unfairness), with evidence.
- Distinguish peer-reviewed papers, official benchmark reports, and blogs/opinion. Do not invent citations; if evidence is thin, say so.
