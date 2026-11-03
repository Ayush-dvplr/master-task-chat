SELF CHECK (W1-030, 3 Nov 2026)

Method. The script scratchpad scripts/selfcheck.py (no AI tokens) reads FIX_MAP.md, picks 10 rows at random (Python random, seed 20261103), takes the first kit cite in the "what the kit asks" cell, reopens that line in the kit at origin/main 00d358c4 (git show origin/main:Input_Bundle_QC/<file>), and confirms the check id is written on that line.

| row check id | kit cite | result | kit line opens with |
|---|---|---|---|
| JD-16 | 04:93 | match | JD-16 What makes a valid constraint criterion |
| AL-1 | 05:21 | match | AL-1 Everything graded is promised |
| CL-5 | FC:492 | match | CL-5 No hidden conventions |
| CL-8 | FC:496 | match | CL-8 The reference solution does not survive by cheating |
| JD-18 | 04:99 | match | JD-18 At least one criterion judges the quality of the code the agent writes |
| TS-20 | 03:51 | match | TS-20 Weights map to importance semantically |
| AL-2 | 05:33 | match | AL-2 Everything promised is graded |
| DS-21 | 02:70 | match | DS-21 Solvable from what the agent actually receives |
| CL-10 | FC:498 | match | CL-10 Solvable from instruction.md and environment/ alone |
| JD-11 | 04:88 | match | JD-11 Negative-weight criteria should cover the real cheat surface |

Result: 10 of 10 match.

Extra pass over all 71 rows with the same script: 69 rows carry the id on the cited line. The other 2 are correct by content: IN-L2 cites 01:26 ("No grammar errors, no spelling errors") and IN-L3 cites 01:27 ("No AI-tell phrases"); those language rules carry no id on the rule line, and their ids appear in the gate 01 checklist at 01:69 and 01:70.
