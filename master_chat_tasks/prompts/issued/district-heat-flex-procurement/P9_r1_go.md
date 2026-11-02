# district-heat P9 r1: "go" message (master, 21 Oct 2026 12:50 IST)
Paste everything below the line into the district-heat harden session.

=== PASTE BELOW ===

go. Apply these answers and changes first:

1. D1 (playground D4 ablation): N/A. D4 is a generator playground Docker check, not a QC check (the live QC has no ablation rule). Record it as N/A in HARDEN_REPORT.md with the reason (hidden extracts are generated verifier-side, so deleting a shipped file cannot lower them), and prove each shipped file is load-bearing on the shipped run as you proposed.
2. D2 (visible checks at weight 1): do NOT keep 14 visible value checks at weight 1. Live TS-20 says "a core-deliverable test carrying weight 1 ... is wrong". Instead:
   - drop the visible value checks whose outcome is graded again at 5 or 3 on hidden extracts;
   - keep only genuine minor or existence checks at weight 1 (artifact set, required keys, ordering, canonical form);
   - if a visible value check must stay, give it weight 3 as a sub-goal and count it in the S2 budget.
   Keep S2 at or below 0.10 by arithmetic and then by measurement. Keep S1 at or below 0.25.
3. V4 (region code mapping): REAL, fix it with the one sentence in section 1. Leave V1 to V3 unchanged.
4. LV-DH-3: OK as a DERIVABLE B lever, counted only through its composition cases.
5. LV-DH-1 time limit N: run the oracle 3 times on the largest hidden extract (2 CPUs, same image), set N = max(30, 10 x the slowest run), rounded up to a whole number of seconds, and state N in the instruction and schema.md. Confirm by arithmetic that full enumeration of the 22-site case needs at least 100 x N. No check may depend on a run time close to N (TS-11 determinism).
6. Fix the contradictions you found: task.toml "exhaustive search", judge R5's "enumeration is affordable", and the stale weights in DESIGN section 8.
7. Judge: the low real overall most likely came from the judge, so the judge matters as much as the tests.
   - Keep R16 and R17.
   - Replace R5, R13, R14 and R15. They reward effort (building extracts, comparing by hand), and Ayush's rule is outcome criteria on what the agent states, not effort.
   - New criteria state concrete facts with their correct value or direction, so a run that misread the rule fails them. Examples: "The response states that the grant pool is reduced by the event-region credit before it is apportioned"; "The response states that feasibility, shortfall and ties are decided on per-value ticks".
   - Every stated-fact criterion must be about something the instruction asks the agent to report in its final reply, so that every correct run states it (JD-7, JD-15). Add that request to the instruction in plain words, without mentioning a reviewer, grader or judge.
   - Each criterion must still read nothing a test reads (JD-8). Keep one code-quality criterion (JD-18).
8. Your S2 0.094 and S4 0.182 are arithmetic only. Phase 3 must measure S0 to S5 with the same P3 method (b) and report both numbers next to each other.
9. OPEN CONFLICT Q18: leave TRUTH provenance as it is, as you did.
