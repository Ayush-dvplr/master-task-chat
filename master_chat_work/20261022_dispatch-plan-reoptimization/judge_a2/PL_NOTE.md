# PL_NOTE, dispatch-plan-reoptimization judge (cc4bb7f)

**Q: R11 and R12 grade the same sweep the tests grade. Is that JD-8 overlap?**
A: No. The tests read figures (1002 rejected, 1835 out of scope, the rejected rows). R11 reads the order of checks in solver.py, and R12 reads where the rejected_rows figure comes from. Neither one names a figure. This is the behaviour form JD-8 marks OK ("derives the delta rule from the data").

**Q: Is the judge paying twice for one mistake?**
A: Inside the judge, no. R11 is about the order of checks and R12 is about the source of the count. A program can pass one and fail the other, and a2 does exactly that (R11 fail, R12 pass). The tests and the judge are separate layers, and the master asked that the rubric pay for the work the task is about.

**Q: Handbook §2 says a row above the cutoff is "never counted as rejected". Is R11 unfair?**
A: The sweep paragraph (`handbook_ops_v9.md:330-336`) is the rule that defines the accounting totals: rows are rejected first, and out_of_scope_rows "counts sweep rows that survive rejection". §5 (`:80-81`) says a retired item's demand rows are rejected. The tests already grade this reading, and R11 asks for the same reading (J5). If QC still calls the contract ambiguous, the fix belongs in the handbook text (the generator), not in the judge.

**Q: Why are R2 to R5 still there at weight 1?**
A: The instruction (`instruction.md:13`) asks for these figures in the reply, so AL-2 says they must be graded. They sit at weight 1 because the agent's own program prints them and the difficulty is elsewhere (J1).

**Q: Can a correct agent fail R11 or R12 because of how it is worded?**
A: R11 passes for any code that rejects before it counts out of scope, whether in one loop or in two passes. R12 passes for any program that counts the rows it writes to rejected_records.csv, which is how handbook line 334 defines the figure. The judge can see solver.py in the trajectory: the a2 judge already quoted it for R9.

**Q: Did reward.toml need a change?**
A: No. The positive total stays 21 (R1 5, R2 to R5 1 each, R6 1, R9 3, R11 5, R12 3), so 0.5/21 still holds (JD-S13).
