# ChatGPT Deep Research brief: practical task design that defeats frontier coding agents fairly

Paste everything below the line into ChatGPT (Deep Research mode). Save its report as `/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/chatgpt/REPORT.md`.

---

I build evaluation tasks for autonomous coding agents (Terminal-Bench / Harbor format). An agent such as Claude Opus or a GPT-5-class model works in an offline Docker container with a shell and a file editor. It gets a short instruction and some input files (specs, data, sometimes a broken codebase) and must deliver output files or a program. Grading: deterministic tests (many run the agent's program on hidden regenerated inputs) plus an LLM judge reading the agent's trajectory and final reply.

Target: a careful frontier agent should score about 10-20% on the tests, while the task stays strictly fair: every rule is written somewhere in the visible files, no hidden rules, no difficulty from data volume, arithmetic, puzzles or output-format nitpicks. An expert human with the files can reach 100%.

What we have seen: frontier agents read every file, write a program, re-derive any shipped sample output to confirm their interpretation, brute-force search when a sample pins the answer, and apply a rule literally when its whole meaning is in one sentence. They scored 85-100% on tasks we thought were hard. Tasks that held agents below 30% used: a rule split across two files; a plausible legacy default contradicted by the authoritative document on a rare edge case that appears in the shipped data; rules stated by omission ("for every other region"); no worked example confirming the full answer; and grading of whole downstream documents on hidden inputs.

I need a practitioner's playbook. Please research (industry write-ups, benchmark authors' design notes, red-teaming and eval-design guides, forum and engineering-blog evidence, open-source task repositories) and answer:

1. Concrete task patterns that legitimately trip frontier agents, with real examples: e.g. superseded or conflicting documentation with a clear precedence rule, units or conventions that change mid-pipeline, stateful processes where an early misreading compounds, edge cases present in data but absent from examples, precedence and override chains, temporal/versioned rules, implicit invariants stated once. For each: why agents miss it, how to keep it fair, how to grade it.
2. Domains where agents are weak in practice (e.g. accounting/settlement rules, scheduling with calendars and time zones, versioned schema migrations, binary/format recovery, concurrency, numerical stability), with evidence.
3. How to stop agents confirming their answer: what to ship and what not to ship (examples, sample outputs, tests); how to give enough evidence to decide each rule without letting the agent verify the full result.
4. Grader design: hidden-input regeneration, composing rules into end-to-end documents, partial-credit weighting, anti-hardcoding and anti-test-reading measures, negative checks, and how to avoid graders that reward format over substance.
5. Judge rubric design: criteria types that separate a correct full-chain solution from a plausible one (single computed figures, honesty checks on claimed validation), and criteria to avoid.
6. Process: how teams validate difficulty before running expensive agent trials (blind solves, ablations, "wrong-reading" variant programs), and when to drop a task as unfixable.
7. Pitfalls: difficulty that turns out to be ambiguity, environment flakiness (timeouts, permissions, network), or reviewer-rejected unfairness.

Output:
- A ranked list of at most 20 actionable design rules, each with: the rule, the agent behaviour it defeats, an example, evidence/source, fairness risk, and a pre-ship check.
- A list of anti-patterns to avoid, with evidence.
- Sources with links; label each as paper, official benchmark doc, engineering blog, or forum/opinion. Do not fabricate sources; mark weak evidence.
