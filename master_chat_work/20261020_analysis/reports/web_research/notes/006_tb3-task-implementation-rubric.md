# 006 Terminal-Bench Task Implementation Rubric (task-implementation.toml) (harbor-framework, read 2026-10-20)
URL: https://github.com/harbor-framework/terminal-bench/blob/main/docs/prompts/task-implementation.toml | Type: docs | File: sources/006_tb3-task-implementation-rubric.toml
(companion read via gh api, not saved: docs/REVIEWING.md "Reviewing Tasks for Terminal Bench 3"; see Key findings)
## What it is
The 36-entry ([[criteria]] count; REVIEWING.md says 30) LLM/human review rubric run on every task PR (verifiable, solvable, difficult, essential_difficulty, test_instruction_alignment, binary_reward, ...).
## Key findings (with cites; criterion names)
- essential_difficulty: difficulty must come from reasoning/domain expertise/multi-step problem solving, "not from getting output formatting exactly right, matching arbitrary precision requirements, or satisfying clerical details"; FAIL if most failures would be formatting/precision/clerical [criterion essential_difficulty]
- difficult: FAIL if an average undergraduate could solve it in a few days, or difficulty "comes solely from tedium, obscure facts, or LLM-specific tricks" [criterion difficult]
- test_instruction_alignment: every assertion must trace to an instruction requirement and vice versa; tests ideally "under ~100 lines"; longer suites "may indicate over-specification" [criterion test_instruction_alignment]
- binary_reward: verifier must write exactly 0 or 1; weighted composites like 0.25*a+0.60*b+0.15*c and passed/total ratios FAIL; internal continuous scores allowed only if thresholded [criterion binary_reward]  -> CONFLICTS with our 0.5 tests + 0.5 judge partial-credit scheme; applies to TB, not necessarily to Harbor 0.24 task QC (UNVERIFIED which rubric Ayush's QC uses)
- difficulty_explanation_quality: must describe intrinsic difficulty, must NOT cite pass rates or model results [criterion]
- resource_configuration: "Tasks should be hard for the agent, not for the computer"; difficulty from computational intensity -> FAIL [criterion]
- agentic: FAIL if solvable by zero-shot generation; must need observe/adapt/iterate [criterion agentic]
- novel: FAIL for textbook exercises / widely available solutions [criterion novel]
- reviewable: expected values must be derived from solution scripts, hardcoded values without derivation are a red flag [criterion reviewable]
- deterministic: oracle failing 28 of 1,000 runs is unacceptable [criterion deterministic_reproducible]
- instruction_concision: do not list tools/libraries the agent can discover; length is only a non-blocking advisory (effective_instruction_length) [criteria]
- REVIEWING.md: reviewers run /run (agent trials; "if agents solve it easily, the task may be too easy"), /cheat (adversarial trials), /regrade; focus questions: "Is this actually hard, or just tedious?", "Would the instruction alone let you write the same tests?" [REVIEWING.md §Suggested Review Order, steps 4,6,7]
## What lowers scores
- n/a (review rubric).
## Relevance to our constraint (rules visible)
- yes. Defines the reviewer fairness/hardness checks our task will face; "essential_difficulty" and "test_instruction_alignment" are the two most likely to flag precision/format/exactness-based hardness.
