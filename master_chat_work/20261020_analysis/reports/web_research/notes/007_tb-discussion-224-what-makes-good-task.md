# 007 What Makes a Good Terminal Bench Task (Bercovich, GitHub discussion #224, 2026-03-22, updated 2026-08-07)
URL: https://github.com/harbor-framework/terminal-bench/discussions/224 | Type: blog | File: sources/007_tb-discussion-224-what-makes-good-task.md
## What it is
Senior TB reviewer's opinionated guide: benchmark tasks are adversarial, taxonomy of bad tasks, what difficulty means, how to build and debug tasks.
## Key findings (with cites; section names)
- "A prompt is designed to help the agent succeed. A benchmark is designed to find out if it can." Ideal task describable in two paragraphs; hard to think about, solution need not be long [§Adversarial, Difficult, Legible]
- Clerical difficulty: failures from "a dollar sign in the amount field when you expected a float" measure format compliance, "hard in an uninteresting way" [§Clerical Difficulty]
- Over-prescriptive instructions: tell the end state, not steps; "every token is an opportunity to mistakenly add ambiguity" [§Over-Prescriptive Instructions]
- Oracle must explore like an agent; jumping straight to hard-coded answer "might be making unfair assumptions" (author knows ground truth, e.g. chosen typos vs other typos) [§Solutions That Assume Hidden Knowledge]
- "difficulty should come from the problem, not from the environment. Not from resource pressure, not from verbose instructions, not from trick formatting" [§What Difficulty Actually Means]
- LLM capabilities are jagged: reading a million log lines is easy for LLMs; navigating an interactive TUI "can completely stall an agent" (e.g. GPT-5 using nano and getting stuck) [§What Difficulty Actually Means; §Building Tasks That Work]
- Testing against models "isn't the definition of difficulty, but it's the best diagnostic"; asks for how many SOTA agents tried and failure examples with harbor task debug [§What Difficulty Actually Means]
- Making it bigger ("extracting more images, adding more of the same but longer") "does not make it better. Real difficulty is conceptual" [§What Difficulty Actually Means]
- Telling agents the time left ("10 minutes left") made agents "freak out ... start doing irrational stuff" [§What Difficulty Actually Means]
- Constraining resources without telling the agent is unfair; results flip between near-identical infrastructures [§What Difficulty Actually Means]
- Run failures in batches of 5 then debug; distinguish "hard" from "unfair" failures [§Building Tasks That Work]
- Word2vec task run 25 times: "king" within top 75 100% of the time but rank varied from 1 to 40 -> inherent variance makes tests hard [§Tests That Validate the Wrong Things]
- LLM-as-judge allowed only in "rare and extraordinary circumstances" [§Tests That Validate the Wrong Things]
## What lowers scores
- Interactive TUIs, long installs needing polling (install-windows-xp: 2-hour timeout, 30-60 min install, agent must watch disk growth), hidden-state unattended-config gaps [§intro example; §Difficulty]
## Relevance to our constraint (rules visible)
- partly. Strongly endorses visible, short, outcome-only specs and rejects clerical/size/resource difficulty; endorses conceptual difficulty + iterative trial-and-error + monitoring long jobs. Note: opinion piece, no pass-rate statistics.
