# P1 ChatGPT idea prompt, template v3 (26 Oct 2026)

Replaces v2 (25 Oct). Why: from 24 to 26 Oct, 8 builds made under v2 were parked. Blind Opus sessions transliterated fully stated contracts into exact programs in about 3 minutes, and stated size and runtime limits handed over the exact method (cold-chain 85.0 final; cleanroom, crash-recovery, scheduler blind 100; registry/tasks.json:698-734). 19 delivered peer tasks stayed below a final of 70 by breadth, by a shipped instance that never fires the hard branch, by unique fit, and by a judge half of trajectory probes (delivery_study2 g1-g4; LEVER_RULES_v3 section 1A). So v3 asks ChatGPT for those hardness sources, not for an exact optimum or exact replay. Rules follow `knowledge/LEVER_RULES_v3.md`.

How the master chat uses this file: copy it to `prompts/issued/<batch>/P1_ideas.md`, fill every `[[...]]`, give Ayush the link. Ayush pastes ONLY the part below `=== PASTE BELOW ===` into ChatGPT (highest reasoning), and pastes the reply back. The master chat gates every idea (uniqueness, QC risk, LEVER_RULES_v3) and records each in `registry/ideas.jsonl`.

=== PASTE BELOW ===

You are designing original, very hard but fair tasks for a terminal-agent benchmark. A frontier coding agent (Claude Opus class) gets a Linux container with Python 3 (standard library only), a folder of input files and a written instruction. It has two hours. It must deliver a reusable program plus exact output files. Hidden tests then run its program on fresh inputs it never saw and compare each output document whole and exactly. A separate reviewer reads its work log and scores how it verified its work; the final score is the average of the test score and the reviewer score.

Target: a careful, competent agent earns 30 to 70 percent of the test points and 25 to 45 percent of the reviewer points, so its final stays below 60. Partial credit must stay possible (each output row graded by exactly one check).

Domain for this batch: [[DOMAIN]]
Number of ideas: [[N_IDEAS]] (each a genuinely different computational core, not a renamed scenario).

## What we measured (this is the most important section)
This agent reads specifications perfectly and fast. For every rule written in the instruction or a spec file, it writes the rule as code. When a task states a few rules, it finishes an exact program in about 3 minutes. It beat all of these (98 to 100 percent): habit traps (rounding mode, inclusive bounds), recursive allocations, stateful keys, rules inferred from data, an exact optimum when a stated size or runtime limit pointed at the method, and an exact replay when every semantic was spelled out.
What held, in 19 delivered tasks by other authors (final scores 34 to 69):
1. Breadth: 30 to 80 small, plainly stated rules spread over 10 to 100 files in 5 to 20 formats, each output document graded whole. The agent needed 10 to 46 minutes for its first full program and still missed 20 to 120 test points.
2. A shipped sample in which the hard case never happens: the rule and all its cases are stated, but the shipped files never trigger the hard case; the hidden test inputs always do. The agent's program is exact on the sample and wrong on the hidden inputs, because it only checks itself on the sample.
3. Unique fit: the output is the one candidate (out of a stated set) that fits all the evidence, and the program must fail clearly when none or several fit. The agent returns the first candidate that fits.
4. Partial-authority files: a file marked as superseded in its own header except for one named fact that still applies. The agent drops the whole file.
5. A long chain of stated authority rules deciding which of several near-identical deliveries governs.
6. The reviewer half: the agent rarely runs its program on an input it built where a stated case applies, rarely shows one concrete instance of a case, rarely recomputes a figure outside its program, and rarely reruns on a changed copy of the inputs. Reviewer scores of 25 to 33 percent kept finals below 70 even when tests were 90 to 96.
So the difficulty comes from many stated rules applied exactly, hard cases that only the hidden inputs trigger, and verification work the agent skips. Nothing may depend on reading a rule wrongly, and no rule may be missing from the files.

## The fixed frame (non-negotiable)
1. Every rule the tests grade is written in the instruction or a shipped spec file, with exactly one reading. No hidden rules, no secret constants, no unstated tie-breaks, no unstated output conventions (casing, file bundle, command flags), no network facts. The expected output is unique: either a stated total order breaks ties, or a stated rule says exactly one candidate must fit and the program must report an error when none or several fit.
2. The instruction states that each output document is graded whole on fresh inputs and only an exact match counts.
3. The instruction must not point at the difficulty. No sentences such as "beware", "note that greedy fails", "the hard part is", and no list of the traps.
4. The shipped sample never triggers the hard case of any rule (so self-checking on the sample reveals nothing). The instruction states that the program will be rerun on fresh inputs in the same layout, and mentions only what is necessary (no list of the axes that change). Do not state a size or runtime limit that tells the agent which method to use.
5. The answer must be checkable: the tests know the true optimum (computed offline by the task author with an exact method) and also verify feasibility of whatever the agent outputs, so a feasible but non-optimal plan earns the feasibility checks but not the optimum checks.
6. Do NOT use: textbook puzzles the agent recognises (sudoku, n-queens, plain knapsack, plain shortest path, plain max-flow); an exact optimum as the main difficulty; raw data volume with few rules; plain arithmetic; formatting trivia; lists of traps or warnings in any file; resource pressure; disabling the network; floating tolerance. Third-party solvers are not installed and must not be needed.
7. One archetype per idea from this list; its output files are fixed:
[[ARCHETYPE_LIST]]
8. Inputs: at least 10 and up to 50 flat files in at least 5 formats readable by the Python standard library, plus a rule register that names every governing file. Each rule sits in the file that governs its data. The files are chained (one is needed to interpret another) and every file matters to a graded result.
9. Exact deterministic outputs only (integers, or fixed decimal strings with a stated rounding rule).

## Already used (do not reuse a setting or core)
Settings: [[USED_SETTINGS]]
Cores and mixes: [[RECENT_MIXES]]

## Return format: for each idea, these fields in this order
1. Title and a one-sentence pitch.
2. Setting: who uses this professionally and why the exact answer matters.
3. Archetype and how its fixed output files map to the task.
4. The hardness sources used (at least two of: breadth, hard case only in hidden inputs, unique fit, partial-authority file, long authority chain), and for each: the rules involved, how many there are, and the files and formats they sit in.
5. Why a fast first program fails: what a careful agent writes in its first 10 minutes, the exact rule or case it gets wrong on a hidden input, and why its self-check on the shipped sample does not expose it.
6. Sample and hidden design: which stated cases the shipped sample triggers and which it never triggers, the hidden-input generator recipe that triggers every stated case, and why every hidden input still follows the stated rules.
7. Input files: name, format, approximate rows, contents, and the files it depends on.
8. Checks: 30 to 60 weighted checks, each output row graded by exactly one check, grouped (shipped outputs, hidden reruns per output document, rejection paths), with the heavy ones marked.
9. Rejection paths: which inputs must be refused, with the exact stated error.
10. Reviewer checks: 8 to 12 statements about the work log, each one verification act a careful engineer performs and a fast agent skips (runs the program on an input it built where a named stated case applies; shows one concrete instance of a named case and the program's decision; recomputes one figure outside the program; reruns on a changed copy of the inputs and shows what moved; runs the broken tool before editing it). Each holds for the author's own reference run and does not repeat a test.
11. Shortcuts and cheats (hardcoding samples, keying on file names, emitting a feasible plan only) and how the design blocks each.
12. Expected scores: lazy, careful and expert agent on the tests and on the reviewer checks, and the final (the average of the two), with a one-line reason each.
13. The nearest known benchmark task, contest problem or textbook problem, and exactly how this differs (it must not be solvable by recognising it).
14. A solvability argument: why an expert reaches 100 percent in two hours with the standard library.
15. The biggest risk (unfairness, a hidden tie, the naive method accidentally being exact, runtime).

Rules for your answer: no implementation code, no generated data, no test answers. Do not rank the ideas or pick a winner.
