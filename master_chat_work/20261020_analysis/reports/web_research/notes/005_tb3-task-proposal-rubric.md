# 005 Terminal-Bench Task Proposal Rubric (LLM-judge prompt) (harbor-framework, read 2026-10-20)
URL: https://github.com/harbor-framework/terminal-bench/blob/main/docs/prompts/task-proposal.md | Type: docs | File: sources/005_tb3-task-proposal-rubric.md
## What it is
The prompt used by the TB LLM reviewer for task ideas: six criteria (Verifiable, Well-specified, Solvable, Difficult, Interesting, Outcome-verified) with accept/reject examples.
## Key findings (with cites; section names)
- "Well specified: problem description completely describes what the verification algorithm will look for. Nothing is left up to guessing." [§Rubric item 2]
- Two-reviewer test: two reasonable people reading the description should write verifiers that accept the same solutions [§Well-specified]
- "Reject tasks that are primarily hard because of how many corner cases must be handled appropriately"; longer description + more corner cases -> more errors [§Well-specified]
- Difficulty: needs PhD-level or several years of domain expertise; "any task that could be solved by an average undergraduate student in under a few days is too easy" (course-project compilers/OS/simple protocols unlikely accepted) [§Difficult]
- "Obscure factual knowledge generally does not make tasks hard"; LLM-trick difficulty (strawberry tokenization) is not interesting [§Difficult]
- Tasks humans find easy but LLMs find hard are good contenders "if generalizable and not adversarially selected for" [§Difficult]
- "Tedious tasks can be very difficult, especially if it is easy to make mistakes. We don't want contrived instruction following problems that have tons of 'work' ... just a large volume" [§Difficult]
- Solution must be implementable "in a few hours at most" by an expert who knows the idea; difficulty must not be measured by amount of work [§Solvable, §Difficult]
- Rejection examples: 100,000-LoC file summarisation ("time-consuming but not hard"); unsolved research problems (factor 2^1024-bit numbers in 30 s); non-programmatic "mimic gmail" [§Examples > Reject]
- Acceptance examples: GPT-2 forward pass in C in <4000 bytes; Verilog CPU under 10,000 gates [§Examples > Accept]
- Outcome-verified: process constraints only if mechanistic anti-cheat; "dozens of attributes" JSON output = overspecification concern [§Outcome-verified]
- No gimmicks: description must not be "technically correct but suggest the wrong answer" [§Misc]
## What lowers scores
- n/a (review rubric).
## Relevance to our constraint (rules visible)
- yes, and it constrains us: hardness-by-many-written-corner-cases and volume are explicitly rejected; allowed routes are search/algorithmic insight, tight constraints (bytes/gates), error-prone-but-fundamental tedium. Good template for what survives QC.
