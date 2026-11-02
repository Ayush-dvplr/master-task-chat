# QC_DEFENCE (design stage)

One entry per lever (S-1, S-2, S-3) and per cascade (C-A coupling of the replanned season into every output; C-B whole-document grading per hidden corpus).

## S-1 minimum total risk-days (lexicographic level 1)
- Rule ids: IN-15, IN-16, AL-1, AL-27, DS-20, TS-19.
- Live rule (docs/replan_contract.md, Objective): "Among all feasible replanned seasons, the published one has the smallest total risk-days, where a scheduled outage contributes its weight times the sum of the load-band factors of its days out and a deferred request contributes its weight times its duration times the defer factor."
- Why it passes: the rule, the weight (customers.csv x class weights in risk_policy.toml), the load factor bands (load_forecast.tsv daily peak vs thresholds) and the deferral factor are each written in one governing file (IN-15). One reading: an optimum is defined over all feasible seasons, not over a construction order (IN-16). Hidden corpora plant contention clusters where greedy plans are feasible but costlier (AL-27). check_exact.py proves optimality independently by brute force on small lanes (DS-20).
- Fallback: playbook row IN-16 DO: add one settling clause to replan_contract.md ("feasible" already defined by the constraints section of the same file; add a cross-reference), never name a method. Row AL-27 DO: add a hidden fixture that fires the branch on every graded seed.

## S-2 fewest moved requests (level 2)
- Rule ids: IN-15, IN-16, AL-27, DS-25, TS-19.
- Live rule: "Among seasons equal on level 1, the published one moves the fewest outages; an outage is moved when it appeared in the published plan and its replanned start differs from its published start, a published outage that becomes deferred is moved, a request that was deferred in the published plan and stays deferred is not moved, and a request added by the control-room log is never moved."
- Why it passes: every case of "moved" is defined in the sentence (published->deferred, log-added); deferred-in-published staying deferred is settled by the same definition (start equal). `moved` key and its boolean form are named in docs/output_schema.json (DS-25).
- Fallback: playbook IN-16 DO: add the missing case to the same sentence in replan_contract.md.

## S-3 start-list tie-break (level 3)
- Rule ids: IN-15, IN-16, AL-27, AL-1.
- Live rule: "Among seasons equal on levels 1 and 2, the published one has the smaller start-day list, read in ascending asset_id order, at the first asset where two seasons differ; a deferred request counts as later than every season day."
- Why it passes: ascending asset_id is a string order; asset ids are fixed-width (no numeric/lexical split), so one reading (IN-16). Hidden tie pairs fire it on every corpus (AL-27).
- Fallback: playbook AL-27 DO: plant tie pairs in every region of every hidden seed (already planned).

## C-A coupling (every figure from the one replanned season)
- Rule ids: AL-1, DS-20, TS-13, CL-4.
- Live rule: "Every published figure is computed from the one replanned season that the objective order selects." (docs/replan_contract.md)
- Why it passes: each test opens one output file (TS-13); a wrong season costs every file it touches, but each row is owned by one test (G1a OWNED map), so one slip costs its rows once per corpus.
- Fallback: TS-13 DO: split any test that opens two files.

## C-B whole-document exact grading on hidden corpora
- Rule ids: CL-4, TS-19, TS-20, TS-26, AL-17, AL-28, JD-7, JD-15.
- Live rule (instruction.md): "each output document is graded whole on fresh inputs in the same layout, and only an exact match counts."
- Why it passes: CL-4 exemption FC:491 ("An instruction that states out loud that only an exact match counts has set that bar deliberately"); the report gives the one-fact-wrong score. AL-17: "You have N seconds" equals timeout_sec; per-run limit 300 s stated plainly; verifier worst case <= 90% of its limit. AL-28: only cheating acts are negative (grader-read anchored "/tests/ at the filesystem root or /logs/verifier"). TS-26: no two checks read the same observable with the same logic (per-region files vs policy_audit vs segments vs summary). JD-7: every probe is shown by a solve.sh self-check stage. JD-15: criteria constrain only stated things.
- Fallback: CL-4 DO: quote FC:491 and the one-fact-wrong score; never add partial credit. AL-17 DO: raise verifier timeout, never shrink hidden corpora below the lever.
