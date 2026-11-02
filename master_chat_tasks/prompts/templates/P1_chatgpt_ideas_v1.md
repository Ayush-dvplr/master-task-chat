# P1 ChatGPT idea prompt, template v1 (21 Oct 2026)

How the master chat uses this file: copy it to `prompts/issued/<batch>/P1_ideas.md` and fill every `[[...]]` from `registry/levers.json`, `registry/tasks.json` and `registry/ideas.jsonl`. Ayush pastes ONLY the part below the line `=== PASTE BELOW ===` into ChatGPT (high reasoning), then gives the reply to the master chat. The master chat gates each idea (uniqueness against its own registry, QC risk, the lever rules) and records every idea, accepted or rejected, in `registry/ideas.jsonl`.

Fill rules:
- `[[LEVERS_HELD]]` and `[[LEVERS_LEAKED]]`: name, one-line mechanism, and the measured effect for each. While no real scores exist, write "none measured yet".
- `[[RECENT_MIXES]]`: for the last 10 tasks, archetype + setting + lever ids. The new ideas must differ from every one of them.
- `[[USED_SETTINGS]]`: every setting or domain story already in the registry.
- Novelty norm: several new levers per idea. Exactly one new lever is a rare exception, allowed only if the idea explains why.

=== PASTE BELOW ===

You are designing original, very hard but fair tasks for a terminal-agent benchmark. A frontier coding agent (Claude Opus class) gets a Linux container, a folder of input files and a written instruction, has two hours, and must produce exact output files. Hidden tests then run its delivered program again on fresh inputs it never saw and compare outputs field by field. A separate reviewer reads its work log.

Target: a careful, competent agent should earn only 10 to 20 percent of the test points, while partial credit stays possible (each check is independent and weighted).

Domain for this batch: [[DOMAIN]]
Number of ideas: [[N_IDEAS]] (give exactly this many, each a genuinely different mechanism, not a renamed scenario).

## The fixed frame (non-negotiable)
1. Every rule the tests grade must be written in the instruction or in a shipped specification file. No hidden rules, secret constants, undocumented tie-breaks or required network facts. A rule may be long, but it must be stated.
2. Difficulty must come from the structure of the work, not from secrecy. What reliably defeats careful agents, by evidence:
   - A. Hidden composition: each rule is documented, but the hidden inputs combine several rules in one record or case, so rules interact in ways no single visible example shows.
   - B. Dependent chain: four or more stages, each needing the exact output of the previous one (for example parse, then reconcile, then allocate, then report). Later stages are graded on correct inputs supplied by the tests, so one early slip does not zero everything.
   - C. Audit-and-repair: a provided component or pipeline is broken in several quiet ways against a written contract.
   - D. Size ladder: small instances are easy, the largest needs an algorithmic idea (brute force is too slow within the stated limits).
   - E. Stacked orthogonal constraints on the same output that pull against habit.
   - F. Rejection paths: some inputs must be refused with a stated error, and that is weighted heavily.
   Every idea must use A and B, plus one or two of C to F, plus NEW levers of your own (see below).
3. What does NOT work, so do not use it: sheer data volume, plain arithmetic or counting (the agent writes Python), small puzzles or textbook NP-hard instances (the agent writes a solver), formatting trivia, hundreds of corner cases, resource or time pressure, disabling the network, or any hidden or ambiguous rule.
4. The agent builds one reusable program plus a fixed set of output files. Choose ONE archetype per idea from this list; its output files are fixed and cannot change:
[[ARCHETYPE_LIST]]
5. Inputs: at least 10 flat files in at least 5 different formats readable by the Python standard library (csv, tsv, jsonl, json, xml, ini, fixed-width text, sqlite, gzip, zip, log). The files must be chained (a value in one file is needed to interpret another), and every file must matter to a graded result. Size: large enough to need a program, but size is not the difficulty.
6. Exact deterministic outputs only (integers or fixed decimal strings with stated rounding). No floating tolerance.

## What has been learned so far (use it)
Levers that held against real agents: [[LEVERS_HELD]]
Levers that leaked (agents solved them; do not reuse as the main difficulty): [[LEVERS_LEAKED]]
Settings already used (do not reuse): [[USED_SETTINGS]]
Recent archetype and lever mixes (your mix must differ from each): [[RECENT_MIXES]]

## New levers
Each idea must introduce several new levers that are not in the A to F list and not in the lists above. A lever is a documented rule or structure plus the specific way a careful agent gets it wrong. Only if an idea truly cannot carry more than one new lever, say why.

## Return format: for each idea, exactly these fields, in this order
1. Title and one-sentence pitch.
2. Setting: who uses this and why the output matters (a realistic professional context, not a game).
3. Archetype (from the list) and how the fixed output files map to the task.
4. Deliverable program: what it reads, what it writes, what it must handle on fresh inputs.
5. Input files: name, format, approximate rows, what each holds, and which other file it depends on. Show at least three dependency chains of length four or more.
6. Spine: the stages of the dependent chain (lever B), and which stage outputs the tests check on supplied correct inputs.
7. Levers. For each lever, including A, B, the chosen C to F, and every new lever:
   a. name (mark NEW or STANDARD),
   b. the rule as it will be written, and where (instruction or which spec file),
   c. what a careful but hurried agent will most likely do instead (the reflex reading),
   d. a constructed hidden case where the reflex reading changes the output, and which fields change,
   e. why the shipped sample data does NOT reveal the reflex error (the agent cannot confirm the rule by checking the samples),
   f. whether it is independent of the other levers (independent levers give finer partial credit).
8. Rejection paths: which inputs must be refused and the exact stated error.
9. Partial-credit plan: roughly 40 to 70 independent checks, grouped by lever, with which ones are heavy.
10. Reviewer checks on the work log: 10 to 20 statements about what the agent says or reports (for example "the agent reports which records it rejected and the stated reason"). Each must be true for any correct solution, must not repeat what a test already checks, and must not reward effort alone.
11. Shortcuts and cheats an agent might try (hardcoding sample answers, keying on file names, reading files it should not), and how the design blocks each.
12. Expected scores: what a lazy agent, a careful agent and a perfect agent would each earn on tests, with a one-line reason per lever.
13. Nearest known benchmark task or textbook problem, and exactly how this idea differs.
14. Solvability argument: why an expert with the instruction and files can reach 100 percent in two hours.
15. Biggest risk to the idea (fairness, ambiguity, or a lever that might leak).

Rules for your answer: no implementation code, no generated data, no test answers. Do not rank the ideas or pick a winner. Do not reuse a setting or a lever mix from the lists above.
