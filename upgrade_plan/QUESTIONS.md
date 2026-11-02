QUESTIONS FOR AYUSH

Answer in chat with the id (for example "Q9: 64 GB"). Claude records answers in ANSWERS.md and changes the status here.

PROCESS
Q0. You wrote "Do not edit when you are 100% sure". I read it as "do not edit UNTIL we are both 100% sure". Is that right? [ANSWERED: yes]
Q1. Is this repo a full copy of your Mac folders master_chat_tasks and master_chat_work, or a snapshot that may be older than the Mac? [OPEN]
Q2. After PROCEED, where do changes go: committed in this repo on the branch for you to copy to the Mac, or written as files for you to place by hand? [OPEN]
Q3. Which of the six problems hurts most right now, so the plan starts there? [ANSWERED, FOLLOW UP Q34]
Q4. Should the UNVERIFIED_RULES.md batches come one batch at a time in chat, or will you read the file and answer by rule id? [OPEN]

P1 COMPACTION
Q5. Does the master chat run in the opencode TUI (auto.py mentions "oc master")? Which model and provider? [OPEN]
Q6. Is opencode auto compaction on? Do you also compact by hand? About how many compactions per day? (RQ4 may answer this.) [OPEN]
Q7. After a compaction, what exactly did the master get wrong? Old lever rules, your feedback (links, tables), running sessions, something else? One or two real examples. [OPEN]
Q8. May superseded files (LEVER_RULES v1 and v2, snapshots, old template versions) move to a history folder the master never reads? [OPEN]
Q9. Would you accept the master reading one small generated state card (under about 4 KB) after compaction, instead of the 7 step read order? [OPEN]

P2 QC FIXES
Q10. Are the careful program and the blind programs saved for every task in a fixed place? Where? [OPEN]
Q11. When a fix lost a lever, how did you find out: next blind read, paid run, or reading the diff? [OPEN]
Q12. The new errors after fixes: mostly new QC findings at recheck, or broken oracle or nop runs, or both? [OPEN]
Q13. Is the QC kit owned by someone else (you can only change your bundle), or can its rules change? [OPEN]

P3 DOCKER
Q14. How much RAM does your M1 Max have, 32 GB or 64 GB? (RQ3 may answer this.) [OPEN]
Q15. Docker Desktop, OrbStack or Colima? Memory and CPUs given to its VM now? [OPEN]
Q16. When sessions wait, what do they print: dockfree START=no, the harness queue, or the auto.py busy worker limit? [OPEN]
Q17. Which Docker rule is in force: one at a time, max 2 heavy, or dockfree only? (CONTRADICTIONS C1, C6) [OPEN]
Q18. The 27 Oct Mac hang: do you know the cause (memory, disk, too many containers)? [OPEN]
Q19. How many Docker jobs at the same time do you believe the Mac can run, and of what kind (kill tests, oracle or nop, paid harness runs)? [OPEN]

P4 HARDENING
Q20. "Hardening as per the proven": do you mean (a) a repeatable recipe applying the R0 lever kinds to a task, (b) a library of proven levers with implementation patterns, or (c) something else? [OPEN]
Q21. Which tasks should be hardened first? [OPEN]
Q22. What goes wrong today when you harden: the lever does not bite, QC flags it, or too many rounds? [OPEN]

P5 TOKENS
Q23. Which plans do you pay for (Claude Max, Anthropic API, ChatGPT Pro or Plus, OpenAI API, others)? Is the pain usage limits or money? [OPEN]
Q24. Which step feels most expensive: build, QC, fix, blind reads, or the master chat itself? [OPEN]
Q25. Are cheaper models fine for mechanical steps (tallies, diffs, intake), or must every session use the strongest model? [OPEN]

P6 TOOLS
Q26. Every tool and model you use now, including the others (Gemini CLI, Kiro, Cursor, anything). [OPEN]
Q27. Which tool for which step, and why (cost, quality, limits)? [OPEN]
Q28. Should auto mode start and watch Codex and the others by itself, or is it enough that they report back in one shared format when you start them by hand? [OPEN]
Q29. Known limits per tool in practice (for example Codex cannot reach Docker, GPT skips parts of long prompts)? [OPEN]

RECORD CONTRADICTIONS (see CONTRADICTIONS.md)
Q30. Count cap: is there any cap on tests and judge criteria, a warn above 35, or no cap at all? (C2) [OPEN]
Q31. Which P12 fix template is active, v4 or v5? (C3) [OPEN]
Q32. Is the gate tests under 85, rubric under 85, final under 40, and the older 100, 100, 70 dead? (C4) [OPEN]
Q33. Push needs 1 harness run, or 8 runs on final approval? (C5) [OPEN]

NEW PROBLEMS P7 TO P10 (from the Q3 answer, 3 Nov)
Q34. Is your Q3 list in priority order, so compaction (P1) comes first, then the others in the order you wrote them? [OPEN]
Q35. P7: when you "upgrade the master chat session", what kind of upgrade do you mean (new template versions, new rules, new tools, a new plan like v3.7 or v3.8)? What became worse afterwards? One real example. [OPEN]
Q36. P8: do your teammates use the same QC kit and the same generator as you? Do they build by hand, with their own chat, or with a system like yours? [OPEN]
Q37. P8: can you share one or two teammate tasks that passed QC and scored well, with their scores? I saw master_chat_work/20261102_test_design_study (10 teammate tasks). Are those the right examples, or are there better ones? [OPEN]
Q38. P9: "very bad at creating new tasks with respect to the fixing tasks". Which do you mean: (a) new tasks built from scratch come out worse than tasks that get fixed, (b) the system is good at fixing but bad at designing new tasks, or (c) something else? [OPEN]
Q39. P10: which templates were still old after an upgrade? Name one case (which upgrade, which template, which session used the old one). I already found one: state.json and README line 31 still say P12 v4 while INDEX says v5 is active (CONTRADICTIONS C3). [OPEN]

Note: these ids replace the unnumbered list Claude gave in chat on 2 Nov. Same questions, new numbers.
