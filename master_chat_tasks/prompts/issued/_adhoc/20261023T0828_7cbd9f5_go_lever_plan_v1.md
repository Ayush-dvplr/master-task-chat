# GO note for session 7cbd9f5 (cohort-retention harden r2, Phase 2), 23 Oct 2026 08:28 IST

Paste below into session `7cbd9f5`. Save it as the first item of `WORK/TODO.md` so it survives compaction.

=== PASTE BELOW ===

go. Phase 2 now follows the approved lever plan. It REPLACES the lever, judge and weighting parts of this prompt's Phase 2. Every other rule in this prompt still applies: format, gates, clash rules, deliverables.

1. Read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/LEVER_PLAN_v1.md`, plus your own `OUT/DIAGNOSIS.md`. For the evidence behind each lever, read only the GROUP_SUMMARY section it cites: `/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/peer_levers/G1..G5/GROUP_SUMMARY.md`. Copy the patterns, never peer text, data or code.

2. Levers: use L1 (green control, wrong answer), L2 (make-it-match repair) and L3 (stateful stream), plus one of L4/L5. Write them per W1-W7:
   - no trap explanations, no rule counts in the instruction;
   - each rule in the file that governs its data;
   - overrides name the field exactly;
   - no worked example that separates the two readings.
   Every rule must be fully stated with one reading (IN-15, IN-16). For each lever, in `WORK/LEVERS.md`: rule text with file:line, reflex reading, constructed hidden cases, and the checks the wrong reading fails. Remove or rewrite the existing CR-1..CR-5 and V0 giveaways, for example audit_policy.md L20-25 "not only the one for the cleaning step...".

3. Grading, per G1-G7:
   - one test per downstream document, on hidden reseeded inputs, each asserting only its own document;
   - isolated rule checks run on supplied correct inputs, with no whole-set asserts;
   - weight shares: isolated <= 30%, whole-document on hidden inputs >= 50%, shipped-only <= 5%;
   - negatives grade only cheating, at most 5 per act across both layers;
   - the instruction states that "each output document is graded whole on fresh inputs";
   - at least 2 mutation tests on governed constants;
   - assertion messages recorded in ctrf;
   - caps 70/70; core weights never 1.

4. Judge, per J1-J5:
   - delete every "states figure X" criterion;
   - one w3 conduct criterion per lever ("constructs its own input in which <case the shipped data lacks> and checks <observable>"; Ayush accepts these under JD-7);
   - one honesty negative ("claims a check passed while its own output shows otherwise");
   - one named-shape code-quality criterion;
   - no criterion may endorse a reading the tests penalise;
   - `[judge] mode = "batched"`.

5. New: write `OUT/STACKING_CHECK.md` before the Docker gates:
   - (a) a table, one row per test: test id, weight, the observable it reads, its decisive logic, and the levers whose misreading fails it. No two rows may share both observable and logic (TS-26), and each test asserts one property (TS-13);
   - (b) penalty groups by triggering act across tests and judge, with the sum of |weight| per group, each <= 5 (AL-28);
   - (c) the cascade, measured: run the agent's a2 program (from `.../traj_a2/trajectory_job_cohort-retention-reconciliation_bb8ec0/`, the agent's `/app/out` program or its reconstruction from the trajectory) against the NEW tests locally. Report the tests-channel score and which tests each misread fails. **It must score <= 0.20.** If it does not, strengthen the levers before any Docker gate, max 2 tries, then stop and report "PILOT WEAK: <score>".

6. Then run Phase 3 as written: QC scripts + QL diff list, warm image, oracle x3 (per Ayush; kit asks x5), owner-only, nop, stub, forgery, S4 0.10-0.20. Write HARDEN_REPORT.md and result_7cbd9f5.json, adding a field `"a2_program_score": x`.

Final reply (10 lines max): new lever ids and where each rule is written, test/criterion counts, weight shares, the a2 program score, stacking check result, gates, report path.
