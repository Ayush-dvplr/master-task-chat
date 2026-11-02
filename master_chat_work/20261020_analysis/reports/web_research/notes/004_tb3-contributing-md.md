# 004 Contributing to Terminal-Bench (TB3 task guidelines) (harbor-framework, read 2026-10-20)
URL: https://github.com/harbor-framework/terminal-bench/blob/main/CONTRIBUTING.md | Type: docs | File: sources/004_tb3-contributing-md.md
## What it is
Official contributor guide for the current Terminal-Bench release (repo pushed 2026-10-20): difficulty bar, strategies for harder tasks, task format, checks.
## Key findings (with cites; section names, no page numbers)
- Bar: tasks "well beyond the current frontier of model ability: tasks which agents cannot solve (reliably or at all) due to meaningful failures" [§Task Guidelines > Task Difficulty]
- Difficulty "should not be arbitrary (e.g. by adding unnecessary complexity)"; do NOT mass-generate candidates and filter for current-model failures (finds "trivial corners of capability gaps ... quickly remedied") [§Task Difficulty]
- Disabling network is "not a valid way to make a task difficult"; solutions must not be easily findable online [§Task Difficulty]
- Strategies: long-horizon (hours-days for expert); richer environments (microservices, filesystems, DBs); dynamic environments (live traffic sim); new domains; cross-domain expertise; "Iterative tasks solved through trial and error, not read-and-solve" [§Strategies for creating more challenging tasks]
- Quality: clear instruction + robust verifier such that solution passes "if and only if it successfully completes the instruction" [§Task Quality]
- Instruction rules: human-written, absolute paths, "Include all information the agent needs to complete the task and nothing more", must end with fixed timeout + no-cheating sentence [§instruction.md]
- task.toml: agent timeout comment "expect hard tasks with agents running for multiple hours"; verifier runs in separate container (environment_mode="separate"); expert_time_estimate_hours = best-case focused expert [§task.toml]
- README must have human-written "Difficulty explanation", "Solution explanation", "Verification explanation", "Relevant experience" [§README.md sections]
- PR must include failure analysis (harbor analyze) "to confirm the task is fundamentally hard, not just misspecified" [§Submit your Task]
- Tests: test all behaviours in instruction; ground truth lives in tests/ (verifier image), never in environment/ [§Writing good tests]
## What lowers scores
- Not specified here (guide is about authoring). Hard = long-horizon, richer environments, iterative trial-and-error.
## Relevance to our constraint (rules visible)
- yes for the principle: official TB3 guidance already demands that everything the verifier checks is described in the instruction, so hard-by-hidden-rule is explicitly out. Hardness is expected from long horizon/iteration/exploration, not from tricks.
