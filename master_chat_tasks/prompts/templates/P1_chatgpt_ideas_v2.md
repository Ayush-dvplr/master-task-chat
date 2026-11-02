# P1 ChatGPT idea prompt, template v2 (25 Oct 2026)

Replaces v1 (21 Oct). Why: measured results 21-25 Oct. Every lever that is a stated rule (habit levers H1-H7, recursive shares, chains, stateful keys, evidence induction L11) was read and transliterated by Opus: tests 98-100 on sentinel, sensor, district, caldermoor, metered, config, cohort, schema, tariff. The only two tasks that held were dispatch-plan-reoptimization (tests 35.64: the exact optimum on 4 hidden instance sets was missed) and match-replay-desync-audit (tests 46.88: stateful replay with divergence). So v2 asks for difficulty that survives a perfect reading of every rule: computation, not interpretation. Rules follow `knowledge/LEVER_RULES_v2.md` (no silence, no announcing the traps, IN-17; exactness stated, G5).

How the master chat uses this file: copy it to `prompts/issued/<batch>/P1_ideas.md`, fill every `[[...]]`, give Ayush the link. Ayush pastes ONLY the part below `=== PASTE BELOW ===` into ChatGPT (highest reasoning), and pastes the reply back. The master chat gates every idea (uniqueness, QC risk, LEVER_RULES_v2) and records each in `registry/ideas.jsonl`.

=== PASTE BELOW ===

You are designing original, very hard but fair tasks for a terminal-agent benchmark. A frontier coding agent (Claude Opus class) gets a Linux container with Python 3 (standard library only), a folder of input files and a written instruction. It has two hours. It must deliver a reusable program plus exact output files. Hidden tests then run its program on fresh inputs it never saw and compare each output document whole and exactly. A separate reviewer reads its work log.

Target: a careful, competent agent earns 20 to 50 percent of the test points. Partial credit must stay possible (independent weighted checks).

Domain for this batch: [[DOMAIN]]
Number of ideas: [[N_IDEAS]] (each a genuinely different computational core, not a renamed scenario).

## What we measured (this is the most important section)
This agent reads specifications perfectly. For every rule written in the instruction or a spec file, it writes the rule as code, builds its own test fixture for it, and gets it right. We have tried, and it beat every one of these:
- habit traps (a rule that differs from the usual convention: rounding mode, calendar month vs 30 days, inclusive vs exclusive bounds, tier position per account vs per period);
- recursive or re-shared allocations, multi-stage dependent chains, stateful keys wider than the obvious key;
- rules to be inferred from data patterns (if the wrong guess crashes, the crash tells the agent the answer);
- many interacting documented rules in one record.
All of these scored 98 to 100 percent.

What held: two tasks where understanding the rules was not enough.
1. An optimisation task: the program had to reach the exact optimum of a stated objective on fresh hidden instances. The agent wrote a sound solver, but its search stopped at a good, non-optimal plan. It lost about 65 percent of the test points, and every hidden instance set failed.
2. A replay task: rebuild state by replaying a long event log under documented semantics, find where two replicas diverged, and report the first divergence. Errors carried through the state, so it lost about 53 percent.

So the difficulty must come from computation the agent cannot shortcut: an exact optimum or exact answer that needs a real algorithmic idea (decomposition, a dominance argument, a dynamic programme over the right state, an exact search with strong bounds, or careful incremental state). Greedy, local search, a time-limited solver or a plain LP relaxation must give a plausible answer that is wrong on the hidden instances. Nothing may depend on reading the rules wrongly.

## The fixed frame (non-negotiable)
1. Every rule the tests grade is written in the instruction or a shipped spec file, with exactly one reading. No hidden rules, no secret constants, no unstated tie-breaks, no network facts. Ties in an optimum are broken by a stated total order, so the expected output is unique.
2. The instruction states that each output document is graded whole on fresh inputs and only an exact match counts.
3. The instruction must not point at the difficulty. No sentences such as "beware", "note that greedy fails", "the hard part is", and no list of the traps.
4. The shipped sample instances must be solvable by the naive method (so self-checking on samples reveals nothing). The hidden instances are the same distribution at a larger size or with denser structure, still within a stated size limit, where the naive method is wrong (not merely slow). State the size limits and a runtime limit per instance (for example 60 s) that an exact method meets with margin.
5. The answer must be checkable: the tests know the true optimum (computed offline by the task author with an exact method) and also verify feasibility of whatever the agent outputs, so a feasible but non-optimal plan earns the feasibility checks but not the optimum checks.
6. Do NOT use: textbook puzzles the agent recognises and solves with a known library call (sudoku, n-queens, plain knapsack, plain shortest path, plain max-flow); data volume; plain arithmetic; formatting trivia; hundreds of corner cases; resource pressure; disabling the network; floating tolerance. Third-party solvers are not installed and must not be needed.
7. One archetype per idea from this list; its output files are fixed:
[[ARCHETYPE_LIST]]
8. Inputs: at least 6 to 10 flat files (as the archetype says) in at least 4 formats readable by the Python standard library. The files are chained (one is needed to interpret another) and every file matters to a graded result.
9. Exact deterministic outputs only (integers, or fixed decimal strings with a stated rounding rule).

## Already used (do not reuse a setting or core)
Settings: [[USED_SETTINGS]]
Cores and mixes: [[RECENT_MIXES]]

## Return format: for each idea, these fields in this order
1. Title and a one-sentence pitch.
2. Setting: who uses this professionally and why the exact answer matters.
3. Archetype and how its fixed output files map to the task.
4. The computational core: the exact problem in mathematical terms (decision variables, constraints, objective, total tie-break order), and the algorithmic idea an expert uses to solve the hidden sizes exactly in time.
5. Why the naive approaches fail: for greedy, local search, a time-limited search, and the most likely "smart" first attempt, say what plausible wrong answer each gives on a hidden instance and why the shipped samples do not expose it.
6. Instance design: sample sizes vs hidden sizes, the structure that makes naive methods miss (stated as a generator recipe), and why it is still the same stated distribution.
7. Input files: name, format, approximate rows, contents, and the files it depends on.
8. Checks: 30 to 60 independent weighted checks, grouped (feasibility, exact optimum per hidden instance, secondary reports, rejection paths), with the heavy ones marked.
9. Rejection paths: which inputs must be refused, with the exact stated error.
10. Reviewer checks: 10 to 15 statements about the work log that hold for any correct solution and do not repeat a test.
11. Shortcuts and cheats (hardcoding samples, keying on file names, emitting a feasible plan only) and how the design blocks each.
12. Expected scores: lazy, careful and expert agent on the tests, with a one-line reason each.
13. The nearest known benchmark task, contest problem or textbook problem, and exactly how this differs (it must not be solvable by recognising it).
14. A solvability argument: why an expert reaches 100 percent in two hours with the standard library.
15. The biggest risk (unfairness, a hidden tie, the naive method accidentally being exact, runtime).

Rules for your answer: no implementation code, no generated data, no test answers. Do not rank the ideas or pick a winner.
