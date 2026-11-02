# Gemini Deep Research brief r2 (academic angle): how many interacting mechanisms make a fair task defeat a frontier agent? Issued 23 Oct 2026 09:12 IST

Paste everything below the line into Gemini Deep Research. Save its whole report as `/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/gemini_r2/REPORT.md` (an empty file is already there).

---

I design evaluation tasks for autonomous coding agents in the style of Terminal-Bench (Harbor 0.24 task format). The agent (frontier model, e.g. Claude Opus class, shell + file editor, no internet) gets a plain-language instruction plus files in a Docker container and must produce output files or a program. Grading: (1) deterministic pytest checks on outputs, including hidden regenerated inputs, (2) an LLM judge scoring the trajectory and final reply against a rubric. Fairness constraints: every graded rule is fully stated in visible files with exactly one reading; no hidden rules; no difficulty from volume, arithmetic, puzzles or formatting; a human expert with the same files can score 100%.

What we measured (23 Oct 2026): our tasks scored 100/100/100 on real runs. In every run (ours and 20 peer tasks) the agent read all files, wrote its program once 6-10 minutes in, never changed the logic, and self-tested only on shipped data, invariants (totals, determinism) or tiny examples it made up. Peer tasks that genuinely beat it used: (a) a shipped control (counts/sums) that stays green while graded values are wrong, (b) a tempting repair that makes a control pass but breaks a stated reading rule, (c) an ordered stream where an early decision consumes a cap or budget later records read, (d) one value composed from 3-5 files, (e) a strict type rule beside a global normalise rule. The biggest losses (100-200 test points) came where these mechanisms INTERACT. Our current plan uses 4 such mechanisms per task.

Research questions (academic and benchmark literature; cite every claim, with venue and year):
1. In published hard agent or reasoning benchmarks (for example SWE-bench Verified/Pro, Terminal-Bench, tau-bench, MLE-bench, long-horizon or compositional reasoning suites), how many independent rules, constraints or reasoning steps does a typical task that frontier models fail contain? Is there evidence for a threshold, i.e. accuracy falling sharply after k interacting steps?
2. What does research on compositional generalisation and multi-step error compounding say about INTERACTING mechanisms versus the same number of independent ones? Give any quantitative results.
3. What is known about model self-verification failures: when do models check their own work, which checks do they choose (invariants versus independent oracles), and which task designs make self-checks pass while the answer is wrong?
4. What does research say about "satisficing" or premature commitment (writing a solution once, then not revising it), and which task features trigger or break it?
5. How do benchmark authors keep tasks fair (fully specified) yet hard? List published design principles and their failure modes (contamination, ambiguity, under-specification).
6. Any evidence on how robust these difficulty mechanisms stay across model generations (difficulty decay)?

Output format (needed for merging with two other reports):
- Section per question 1-6, each starting with a 3-line answer, then the evidence.
- Then a table: mechanism | evidence of effect size | source | applies to our setting (yes/partly/no, why).
- Then "Design recommendations": numbered, each with the source ids it rests on.
- Then a reference list.
Mark anything not directly supported by a source as SPECULATION.
