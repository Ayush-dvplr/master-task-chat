RESEARCH PROMPT SAMPLES (W1-034, built 03 Nov 2026 21:35 IST by research_prompt.py from the current files; each block is the full prompt as it would be pasted)

Sizes:
verify-20261103T2135-0ea41a4b: 7716 characters, 1224 words
discover-20261103T2135-0ea41a4b: 8458 characters, 1317 words
explore-20261103T2135-0ea41a4b: 8171 characters, 1289 words
teammate_study-20261103T2135-0ea41a4b: 8916 characters, 1397 words

KIND verify
```text
RESEARCH PROMPT verify-20261103T2135-0ea41a4b
Sources: patterns b79fcac6, confirm 1e967370, registry 2f839e81, leaks e6bcb10c, angles 992e4460, ideas 405e0e37

CONTEXT
We design hard but fair tasks for a terminal agent benchmark. A frontier coding agent (Claude Opus class) gets a Linux container with Python 3 standard library, input files and a written instruction, and must deliver a program plus exact output files. Hidden tests rerun its program on fresh inputs and compare whole documents; a judge reads its work log. A task counts only if every graded value is decided by the shipped instruction and data (no unwritten rule, constant, form or tie break), it passes a strict quality review, and the agent scores under the gate. Hiding a case in the hidden data is normal design; hiding a rule is not allowed.
Gate: tests under 85, rubric under 85, final under 40.

WHAT WE KNOW (short; ids are for your answer)
D1: A DOCUMENTED BRANCH ONLY THE HIDDEN DATA FIRES (kind b). Measured cost: 8eae0f87 100 of 107; 4da82574 50 of 74. 7e0d8feb fired its branch on one seed only and cost 5 of 85: one seed is not enough.
D2: CARRIER OR ENCODING VARIATION INSIDE A NAMED STANDARD (kind a). Measured cost: f348165e 330 of 352; 43986de8 553 of 644; e08c051f 55 of 79.
D3: A DOCUMENTED RULE MISREAD OR OVER APPLIED, FEEDING AN EXACT GATE (kind d). Measured cost: df8f123b 67 of 76; 4a5f9738 51 of 67; b6237098 30 of 40; d4e8c327 33 of 36; 7c2e77a1 57 of 64 (rule not located).
D4: A STATED RUNTIME ON A LARGE HIDDEN INPUT (kind c). Measured cost: fd7a2544 64 of 86; f5fe93be only 3 (one timed check).
D5: ONE DETAIL BURIED IN A VERY LONG DOCUMENT (kind e). Measured cost: 62 of 71, because the missed override touches every account.
D6: MANY INTERACTING SEEDED FAULTS (kind e). Measured cost: cd6a3a55 216 of 262; 9cc598a9 25 of 27.
D8: CARRIED STATE THAT NEVER HEALS. Measured cost: 275f885b 71 of 78 from a handful of claims.
D9: ONE CLAUSE HARDENING CONTRACTS. Measured cost: 30 of 40 lost (design share).
C1: KIND (a), carrier or encoding variation inside a named standard: CONFIRMED.
C2: KIND (b), a documented branch only the hidden data fires: CONFIRMED.
C3: KIND (c), measured scale under one runtime sentence: PARTLY CONFIRMED.
C4: THE 40 PERCENT PRIMARY LEVER: CONFIRMED AS ACHIEVABLE, with one partial refutation.
C5: THE EXACT MATCH SENTENCE ("Each output document is graded whole, and only an exact match counts"): PARTLY CONFIRMED.
K1: in our own builds a careful exact program, written from complete docs, transliterated stated rule, unique fit over a stated domain and exact optimum levers in 2 to 4 minutes (13 design rounds lost; W1-034 WHY_NEW_FAILS.md).
K2: tasks whose paid run kept tests under the gate (12; final may still be over it): district-heat-flex-procurement (own, pushed): paid tests 72.41, final 32.5; schema-migration-plan-repair (own, pushed): paid tests 34.01, final 32.12; dispatch-plan-reoptimization (converted, pushed): paid tests 35.64, final 14.7; sentinel-policy-recompute (converted, pushed): paid tests 80.95, final 44.53; match-replay-desync-audit (converted, pushed): paid tests 69.19, final 43.42; metered-usage-rating-pipeline (new, pushed): paid tests 73.46, final 46.73; tariff-engine-audit-repair (new, pushed): paid tests 45.67, final 47.84; cold-chain-backbone-quote (new, pushed): paid tests 42.5, final 29.06
K3: tasks whose lever was kept by the agent or a blind (14): vendor-archive-roundtrip-recovery (own, killed): paid tests 100; record says kill rule; cohort-retention-reconciliation (converted, parked): paid tests 100; record says tests at or above 95; sensor-network-lsq-correlated-adjustment (converted, qc): paid tests 100; record says tests at or above 95; numeric-reduction-benchmark-forge (converted, dropped): no paid score; record says kill rule; data-product-config-compiler (new, parked): paid tests 100; record says harden round limit; cleanroom-window-schedule (new, parked): no paid score; record says levers leaked; counter-page-crash-recovery (new, parked): no paid score; record says blind or program exact, contract transliterated; flood-repair-portfolio (new, fix): paid tests 100; record says tests at or above 95; batch-lease-scheduler-replay (new, parked): no paid score; record says 3 of 3 blinds full marks, contract transliterated; fuel-card-settlement-consolidation (new, parked): no paid score; record says blind or program exact
F1: leak cause: Every rule was one explicit sentence that named its own exception; no rule had a plausible wrong reading.
F2: leak cause: Two rules spelled out the trap in the rule text.
F3: leak cause: The only "split across files" was a two-file read that the instruction pointed to together.
F4: leak cause: A decoy was refuted on the same page as its use.
F5: leak cause: Shipped boundary rows let the agent watch each rule fire.
F6: leak cause: Hidden cases only repeated rules the agent had already coded; the agent's own self-test covered every hidden-case family.
(leak library rows: 22)

WHAT WE WANT
Check the K, C and family statements above against outside evidence: papers, public benchmark reports, agent evaluation write ups, parser and standard conformance studies. For each one say confirms or refutes, with the source, and give one check we can run. Start with items marked PARTLY. Return 5 to 10 items of type claim.

WHAT TO AVOID REPEATING
Research angles already run: A1 (N): Does weight concentration separate hard from easy?; A2 (S): Does the share of weight on hidden or rerun checks separate them?; A3 (N): Does rerunning on fresh inputs separate them?; A4 (S): Do withheld facts (evidence induction) make tasks hard?; A5 (M): What judge composition goes with low scores?; A6 (M): Which channel loses the points?; A7 (M): Is hardness about time?; A8 (S): Are contributor or domain confounds behind the bands?; A9 (M): Can genuineness be judged without verifier messages?; A10 (W): Do README bands match the stored run?; A11 (M): Do tasks share skeletons?; A12 (S): Are the hard tasks fair?.
Do not propose: a stated rule that a careful reader writes as code (F and K1); rules that are unwritten or confirmed only by examples or digests; exact optimum or runtime as the main difficulty; textbook puzzles; volume alone.

RULES FOR YOUR ANSWER
Do not invent sources. Mark reasoning without a source as evidence: none. No implementation code, no generated data, no task text. Use the exact format below so it can be stored by a script; nothing outside the BEGIN and END lines is read.

ANSWER FORMAT
BEGIN RESEARCH ANSWER
prompt_id: verify-20261103T2135-0ea41a4b
tool: <ChatGPT | Gemini | other>
items: <number of ITEM blocks>
ITEM 1
type: <claim | idea | angle | teammate_pattern>
family: <one of D1 to D9, or NEW>
relation: <confirms ID | refutes ID | new> (ID is an id from this prompt: K, C, F, A, U or I)
title: <at most 12 words>
statement: <two to four sentences>
evidence: <source with a link or full citation; write none if it is your reasoning only>
confidence: <high | medium | low>
check: <one measurable check we can run on our own records or a small prototype>
domain: <idea and teammate_pattern only, else n/a>
data_shape: <idea only: what the shipped files look like, else n/a>
deliverable: <idea only, else n/a>
deciding_sentence: <idea only: the one doc sentence that decides the lever, else n/a>
hidden_plan: <idea only: what the hidden inputs carry that the shipped ones never show, else n/a>
careful_program_path: <idea and angle: what a careful exact program writes and where it goes wrong, else n/a>
solvability: <idea only: why every graded value follows from the shipped docs and data, else n/a>
END ITEM
(repeat ITEM blocks, numbered)
END RESEARCH ANSWER
```

KIND discover
```text
RESEARCH PROMPT discover-20261103T2135-0ea41a4b
Sources: patterns b79fcac6, confirm 1e967370, registry 2f839e81, leaks e6bcb10c, angles 992e4460, ideas 405e0e37

CONTEXT
We design hard but fair tasks for a terminal agent benchmark. A frontier coding agent (Claude Opus class) gets a Linux container with Python 3 standard library, input files and a written instruction, and must deliver a program plus exact output files. Hidden tests rerun its program on fresh inputs and compare whole documents; a judge reads its work log. A task counts only if every graded value is decided by the shipped instruction and data (no unwritten rule, constant, form or tie break), it passes a strict quality review, and the agent scores under the gate. Hiding a case in the hidden data is normal design; hiding a rule is not allowed.
Gate: tests under 85, rubric under 85, final under 40.

WHAT WE KNOW (short; ids are for your answer)
D1: A DOCUMENTED BRANCH ONLY THE HIDDEN DATA FIRES (kind b). Measured cost: 8eae0f87 100 of 107; 4da82574 50 of 74. 7e0d8feb fired its branch on one seed only and cost 5 of 85: one seed is not enough.
D2: CARRIER OR ENCODING VARIATION INSIDE A NAMED STANDARD (kind a). Measured cost: f348165e 330 of 352; 43986de8 553 of 644; e08c051f 55 of 79.
D3: A DOCUMENTED RULE MISREAD OR OVER APPLIED, FEEDING AN EXACT GATE (kind d). Measured cost: df8f123b 67 of 76; 4a5f9738 51 of 67; b6237098 30 of 40; d4e8c327 33 of 36; 7c2e77a1 57 of 64 (rule not located).
D4: A STATED RUNTIME ON A LARGE HIDDEN INPUT (kind c). Measured cost: fd7a2544 64 of 86; f5fe93be only 3 (one timed check).
D5: ONE DETAIL BURIED IN A VERY LONG DOCUMENT (kind e). Measured cost: 62 of 71, because the missed override touches every account.
D6: MANY INTERACTING SEEDED FAULTS (kind e). Measured cost: cd6a3a55 216 of 262; 9cc598a9 25 of 27.
D8: CARRIED STATE THAT NEVER HEALS. Measured cost: 275f885b 71 of 78 from a handful of claims.
D9: ONE CLAUSE HARDENING CONTRACTS. Measured cost: 30 of 40 lost (design share).
C1: KIND (a), carrier or encoding variation inside a named standard: CONFIRMED.
C2: KIND (b), a documented branch only the hidden data fires: CONFIRMED.
C3: KIND (c), measured scale under one runtime sentence: PARTLY CONFIRMED.
C4: THE 40 PERCENT PRIMARY LEVER: CONFIRMED AS ACHIEVABLE, with one partial refutation.
C5: THE EXACT MATCH SENTENCE ("Each output document is graded whole, and only an exact match counts"): PARTLY CONFIRMED.
K1: in our own builds a careful exact program, written from complete docs, transliterated stated rule, unique fit over a stated domain and exact optimum levers in 2 to 4 minutes (13 design rounds lost; W1-034 WHY_NEW_FAILS.md).
K2: tasks whose paid run kept tests under the gate (12; final may still be over it): district-heat-flex-procurement (own, pushed): paid tests 72.41, final 32.5; schema-migration-plan-repair (own, pushed): paid tests 34.01, final 32.12; dispatch-plan-reoptimization (converted, pushed): paid tests 35.64, final 14.7; sentinel-policy-recompute (converted, pushed): paid tests 80.95, final 44.53; match-replay-desync-audit (converted, pushed): paid tests 69.19, final 43.42; metered-usage-rating-pipeline (new, pushed): paid tests 73.46, final 46.73; tariff-engine-audit-repair (new, pushed): paid tests 45.67, final 47.84; cold-chain-backbone-quote (new, pushed): paid tests 42.5, final 29.06
K3: tasks whose lever was kept by the agent or a blind (14): vendor-archive-roundtrip-recovery (own, killed): paid tests 100; record says kill rule; cohort-retention-reconciliation (converted, parked): paid tests 100; record says tests at or above 95; sensor-network-lsq-correlated-adjustment (converted, qc): paid tests 100; record says tests at or above 95; numeric-reduction-benchmark-forge (converted, dropped): no paid score; record says kill rule; data-product-config-compiler (new, parked): paid tests 100; record says harden round limit; cleanroom-window-schedule (new, parked): no paid score; record says levers leaked; counter-page-crash-recovery (new, parked): no paid score; record says blind or program exact, contract transliterated; flood-repair-portfolio (new, fix): paid tests 100; record says tests at or above 95; batch-lease-scheduler-replay (new, parked): no paid score; record says 3 of 3 blinds full marks, contract transliterated; fuel-card-settlement-consolidation (new, parked): no paid score; record says blind or program exact
F1: leak cause: Every rule was one explicit sentence that named its own exception; no rule had a plausible wrong reading.
F2: leak cause: Two rules spelled out the trap in the rule text.
F3: leak cause: The only "split across files" was a two-file read that the instruction pointed to together.
F4: leak cause: A decoy was refuted on the same page as its use.
F5: leak cause: Shipped boundary rows let the agent watch each rule fire.
F6: leak cause: Hidden cases only repeated rules the agent had already coded; the agent's own self-test covered every hidden-case family.
(leak library rows: 22)

WHAT WE WANT
Propose 5 new task ideas. Start each from a domain and a data shape, then use one primary family from the allowed list. Each idea needs its deciding sentence, a hidden data plan in which most hidden inputs fire the lever with varied count and shape, the careful program's path to a wrong answer, and a solvability argument. Return items of type idea.
Allowed primary families, in order of preference: D2, D1, D8, D5, D6, D9, D3.
Recent builds (seed list (INFERRED, W1-034)): flood-repair-portfolio D4 portfolio optimization; hangar-check-replan D4 scheduling optimization; depot-charge-plan D4 scheduling optimization.
Avoid these domains: portfolio optimization, scheduling optimization; and optimization, scheduling, billing and settlement, which carried 10 of our builds.

WHAT TO AVOID REPEATING
Research angles already run: A1 (N): Does weight concentration separate hard from easy?; A2 (S): Does the share of weight on hidden or rerun checks separate them?; A3 (N): Does rerunning on fresh inputs separate them?; A4 (S): Do withheld facts (evidence induction) make tasks hard?; A5 (M): What judge composition goes with low scores?; A6 (M): Which channel loses the points?; A7 (M): Is hardness about time?; A8 (S): Are contributor or domain confounds behind the bands?; A9 (M): Can genuineness be judged without verifier messages?; A10 (W): Do README bands match the stored run?; A11 (M): Do tasks share skeletons?; A12 (S): Are the hard tasks fair?.
Ideas already received: Cold-Chain Evidence Ledger (REJECT); Byte-Exact Vendor Archive Recovery (ACCEPT (finalist 1)); Data Product Configuration Compiler (HOLD (backup)); Schema Migration Repository Repair (ACCEPT (finalist 2)); Ingestion Control-Plane Reconciliation (REJECT (for now)).
Do not propose: a stated rule that a careful reader writes as code (F and K1); rules that are unwritten or confirmed only by examples or digests; exact optimum or runtime as the main difficulty; textbook puzzles; volume alone.

RULES FOR YOUR ANSWER
Do not invent sources. Mark reasoning without a source as evidence: none. No implementation code, no generated data, no task text. Use the exact format below so it can be stored by a script; nothing outside the BEGIN and END lines is read.

ANSWER FORMAT
BEGIN RESEARCH ANSWER
prompt_id: discover-20261103T2135-0ea41a4b
tool: <ChatGPT | Gemini | other>
items: <number of ITEM blocks>
ITEM 1
type: <claim | idea | angle | teammate_pattern>
family: <one of D1 to D9, or NEW>
relation: <confirms ID | refutes ID | new> (ID is an id from this prompt: K, C, F, A, U or I)
title: <at most 12 words>
statement: <two to four sentences>
evidence: <source with a link or full citation; write none if it is your reasoning only>
confidence: <high | medium | low>
check: <one measurable check we can run on our own records or a small prototype>
domain: <idea and teammate_pattern only, else n/a>
data_shape: <idea only: what the shipped files look like, else n/a>
deliverable: <idea only, else n/a>
deciding_sentence: <idea only: the one doc sentence that decides the lever, else n/a>
hidden_plan: <idea only: what the hidden inputs carry that the shipped ones never show, else n/a>
careful_program_path: <idea and angle: what a careful exact program writes and where it goes wrong, else n/a>
solvability: <idea only: why every graded value follows from the shipped docs and data, else n/a>
END ITEM
(repeat ITEM blocks, numbered)
END RESEARCH ANSWER
```

KIND explore
```text
RESEARCH PROMPT explore-20261103T2135-0ea41a4b
Sources: patterns b79fcac6, confirm 1e967370, registry 2f839e81, leaks e6bcb10c, angles 992e4460, ideas 405e0e37

CONTEXT
We design hard but fair tasks for a terminal agent benchmark. A frontier coding agent (Claude Opus class) gets a Linux container with Python 3 standard library, input files and a written instruction, and must deliver a program plus exact output files. Hidden tests rerun its program on fresh inputs and compare whole documents; a judge reads its work log. A task counts only if every graded value is decided by the shipped instruction and data (no unwritten rule, constant, form or tie break), it passes a strict quality review, and the agent scores under the gate. Hiding a case in the hidden data is normal design; hiding a rule is not allowed.
Gate: tests under 85, rubric under 85, final under 40.

WHAT WE KNOW (short; ids are for your answer)
D1: A DOCUMENTED BRANCH ONLY THE HIDDEN DATA FIRES (kind b). Measured cost: 8eae0f87 100 of 107; 4da82574 50 of 74. 7e0d8feb fired its branch on one seed only and cost 5 of 85: one seed is not enough.
D2: CARRIER OR ENCODING VARIATION INSIDE A NAMED STANDARD (kind a). Measured cost: f348165e 330 of 352; 43986de8 553 of 644; e08c051f 55 of 79.
D3: A DOCUMENTED RULE MISREAD OR OVER APPLIED, FEEDING AN EXACT GATE (kind d). Measured cost: df8f123b 67 of 76; 4a5f9738 51 of 67; b6237098 30 of 40; d4e8c327 33 of 36; 7c2e77a1 57 of 64 (rule not located).
D4: A STATED RUNTIME ON A LARGE HIDDEN INPUT (kind c). Measured cost: fd7a2544 64 of 86; f5fe93be only 3 (one timed check).
D5: ONE DETAIL BURIED IN A VERY LONG DOCUMENT (kind e). Measured cost: 62 of 71, because the missed override touches every account.
D6: MANY INTERACTING SEEDED FAULTS (kind e). Measured cost: cd6a3a55 216 of 262; 9cc598a9 25 of 27.
D8: CARRIED STATE THAT NEVER HEALS. Measured cost: 275f885b 71 of 78 from a handful of claims.
D9: ONE CLAUSE HARDENING CONTRACTS. Measured cost: 30 of 40 lost (design share).
C1: KIND (a), carrier or encoding variation inside a named standard: CONFIRMED.
C2: KIND (b), a documented branch only the hidden data fires: CONFIRMED.
C3: KIND (c), measured scale under one runtime sentence: PARTLY CONFIRMED.
C4: THE 40 PERCENT PRIMARY LEVER: CONFIRMED AS ACHIEVABLE, with one partial refutation.
C5: THE EXACT MATCH SENTENCE ("Each output document is graded whole, and only an exact match counts"): PARTLY CONFIRMED.
K1: in our own builds a careful exact program, written from complete docs, transliterated stated rule, unique fit over a stated domain and exact optimum levers in 2 to 4 minutes (13 design rounds lost; W1-034 WHY_NEW_FAILS.md).
K2: tasks whose paid run kept tests under the gate (12; final may still be over it): district-heat-flex-procurement (own, pushed): paid tests 72.41, final 32.5; schema-migration-plan-repair (own, pushed): paid tests 34.01, final 32.12; dispatch-plan-reoptimization (converted, pushed): paid tests 35.64, final 14.7; sentinel-policy-recompute (converted, pushed): paid tests 80.95, final 44.53; match-replay-desync-audit (converted, pushed): paid tests 69.19, final 43.42; metered-usage-rating-pipeline (new, pushed): paid tests 73.46, final 46.73; tariff-engine-audit-repair (new, pushed): paid tests 45.67, final 47.84; cold-chain-backbone-quote (new, pushed): paid tests 42.5, final 29.06
K3: tasks whose lever was kept by the agent or a blind (14): vendor-archive-roundtrip-recovery (own, killed): paid tests 100; record says kill rule; cohort-retention-reconciliation (converted, parked): paid tests 100; record says tests at or above 95; sensor-network-lsq-correlated-adjustment (converted, qc): paid tests 100; record says tests at or above 95; numeric-reduction-benchmark-forge (converted, dropped): no paid score; record says kill rule; data-product-config-compiler (new, parked): paid tests 100; record says harden round limit; cleanroom-window-schedule (new, parked): no paid score; record says levers leaked; counter-page-crash-recovery (new, parked): no paid score; record says blind or program exact, contract transliterated; flood-repair-portfolio (new, fix): paid tests 100; record says tests at or above 95; batch-lease-scheduler-replay (new, parked): no paid score; record says 3 of 3 blinds full marks, contract transliterated; fuel-card-settlement-consolidation (new, parked): no paid score; record says blind or program exact
F1: leak cause: Every rule was one explicit sentence that named its own exception; no rule had a plausible wrong reading.
F2: leak cause: Two rules spelled out the trap in the rule text.
F3: leak cause: The only "split across files" was a two-file read that the instruction pointed to together.
F4: leak cause: A decoy was refuted on the same page as its use.
F5: leak cause: Shipped boundary rows let the agent watch each rule fire.
F6: leak cause: Hidden cases only repeated rules the agent had already coded; the agent's own self-test covered every hidden-case family.
(leak library rows: 22)

WHAT WE WANT
Find mechanisms outside D1 to D9 by which a careful exact program, written from complete and correct docs, gives a wrong answer on legal hidden inputs, and which a task can state in one deciding sentence. Look at parser differential studies, conformance test suites of public standards, data format edge cases, carried state bugs in incident reports, and specification ambiguity research. Also propose new research angles for our own teammate task corpus. Return 5 items of type angle, each with its careful_program_path.

WHAT TO AVOID REPEATING
Research angles already run: A1 (N): Does weight concentration separate hard from easy?; A2 (S): Does the share of weight on hidden or rerun checks separate them?; A3 (N): Does rerunning on fresh inputs separate them?; A4 (S): Do withheld facts (evidence induction) make tasks hard?; A5 (M): What judge composition goes with low scores?; A6 (M): Which channel loses the points?; A7 (M): Is hardness about time?; A8 (S): Are contributor or domain confounds behind the bands?; A9 (M): Can genuineness be judged without verifier messages?; A10 (W): Do README bands match the stored run?; A11 (M): Do tasks share skeletons?; A12 (S): Are the hard tasks fair?.
Ranked untried angles you may take: U1: Self-test anatomy; U2: Judge negative design; U3: Easy-task leak autopsy; U4: Oracle shape across the 31 induction tasks; U5: Data heterogeneity; U6: Instruction phrasing; U7: Partial-credit curves; U8: Run variance.
Do not propose: a stated rule that a careful reader writes as code (F and K1); rules that are unwritten or confirmed only by examples or digests; exact optimum or runtime as the main difficulty; textbook puzzles; volume alone.

RULES FOR YOUR ANSWER
Do not invent sources. Mark reasoning without a source as evidence: none. No implementation code, no generated data, no task text. Use the exact format below so it can be stored by a script; nothing outside the BEGIN and END lines is read.

ANSWER FORMAT
BEGIN RESEARCH ANSWER
prompt_id: explore-20261103T2135-0ea41a4b
tool: <ChatGPT | Gemini | other>
items: <number of ITEM blocks>
ITEM 1
type: <claim | idea | angle | teammate_pattern>
family: <one of D1 to D9, or NEW>
relation: <confirms ID | refutes ID | new> (ID is an id from this prompt: K, C, F, A, U or I)
title: <at most 12 words>
statement: <two to four sentences>
evidence: <source with a link or full citation; write none if it is your reasoning only>
confidence: <high | medium | low>
check: <one measurable check we can run on our own records or a small prototype>
domain: <idea and teammate_pattern only, else n/a>
data_shape: <idea only: what the shipped files look like, else n/a>
deliverable: <idea only, else n/a>
deciding_sentence: <idea only: the one doc sentence that decides the lever, else n/a>
hidden_plan: <idea only: what the hidden inputs carry that the shipped ones never show, else n/a>
careful_program_path: <idea and angle: what a careful exact program writes and where it goes wrong, else n/a>
solvability: <idea only: why every graded value follows from the shipped docs and data, else n/a>
END ITEM
(repeat ITEM blocks, numbered)
END RESEARCH ANSWER
```

KIND teammate_study
```text
RESEARCH PROMPT teammate_study-20261103T2135-0ea41a4b
Sources: patterns b79fcac6, confirm 1e967370, registry 2f839e81, leaks e6bcb10c, angles 992e4460, ideas 405e0e37

CONTEXT
We design hard but fair tasks for a terminal agent benchmark. A frontier coding agent (Claude Opus class) gets a Linux container with Python 3 standard library, input files and a written instruction, and must deliver a program plus exact output files. Hidden tests rerun its program on fresh inputs and compare whole documents; a judge reads its work log. A task counts only if every graded value is decided by the shipped instruction and data (no unwritten rule, constant, form or tie break), it passes a strict quality review, and the agent scores under the gate. Hiding a case in the hidden data is normal design; hiding a rule is not allowed.
Gate: tests under 85, rubric under 85, final under 40.

WHAT WE KNOW (short; ids are for your answer)
D1: A DOCUMENTED BRANCH ONLY THE HIDDEN DATA FIRES (kind b). Measured cost: 8eae0f87 100 of 107; 4da82574 50 of 74. 7e0d8feb fired its branch on one seed only and cost 5 of 85: one seed is not enough.
D2: CARRIER OR ENCODING VARIATION INSIDE A NAMED STANDARD (kind a). Measured cost: f348165e 330 of 352; 43986de8 553 of 644; e08c051f 55 of 79.
D3: A DOCUMENTED RULE MISREAD OR OVER APPLIED, FEEDING AN EXACT GATE (kind d). Measured cost: df8f123b 67 of 76; 4a5f9738 51 of 67; b6237098 30 of 40; d4e8c327 33 of 36; 7c2e77a1 57 of 64 (rule not located).
D4: A STATED RUNTIME ON A LARGE HIDDEN INPUT (kind c). Measured cost: fd7a2544 64 of 86; f5fe93be only 3 (one timed check).
D5: ONE DETAIL BURIED IN A VERY LONG DOCUMENT (kind e). Measured cost: 62 of 71, because the missed override touches every account.
D6: MANY INTERACTING SEEDED FAULTS (kind e). Measured cost: cd6a3a55 216 of 262; 9cc598a9 25 of 27.
D8: CARRIED STATE THAT NEVER HEALS. Measured cost: 275f885b 71 of 78 from a handful of claims.
D9: ONE CLAUSE HARDENING CONTRACTS. Measured cost: 30 of 40 lost (design share).
C1: KIND (a), carrier or encoding variation inside a named standard: CONFIRMED.
C2: KIND (b), a documented branch only the hidden data fires: CONFIRMED.
C3: KIND (c), measured scale under one runtime sentence: PARTLY CONFIRMED.
C4: THE 40 PERCENT PRIMARY LEVER: CONFIRMED AS ACHIEVABLE, with one partial refutation.
C5: THE EXACT MATCH SENTENCE ("Each output document is graded whole, and only an exact match counts"): PARTLY CONFIRMED.
K1: in our own builds a careful exact program, written from complete docs, transliterated stated rule, unique fit over a stated domain and exact optimum levers in 2 to 4 minutes (13 design rounds lost; W1-034 WHY_NEW_FAILS.md).
K2: tasks whose paid run kept tests under the gate (12; final may still be over it): district-heat-flex-procurement (own, pushed): paid tests 72.41, final 32.5; schema-migration-plan-repair (own, pushed): paid tests 34.01, final 32.12; dispatch-plan-reoptimization (converted, pushed): paid tests 35.64, final 14.7; sentinel-policy-recompute (converted, pushed): paid tests 80.95, final 44.53; match-replay-desync-audit (converted, pushed): paid tests 69.19, final 43.42; metered-usage-rating-pipeline (new, pushed): paid tests 73.46, final 46.73; tariff-engine-audit-repair (new, pushed): paid tests 45.67, final 47.84; cold-chain-backbone-quote (new, pushed): paid tests 42.5, final 29.06
K3: tasks whose lever was kept by the agent or a blind (14): vendor-archive-roundtrip-recovery (own, killed): paid tests 100; record says kill rule; cohort-retention-reconciliation (converted, parked): paid tests 100; record says tests at or above 95; sensor-network-lsq-correlated-adjustment (converted, qc): paid tests 100; record says tests at or above 95; numeric-reduction-benchmark-forge (converted, dropped): no paid score; record says kill rule; data-product-config-compiler (new, parked): paid tests 100; record says harden round limit; cleanroom-window-schedule (new, parked): no paid score; record says levers leaked; counter-page-crash-recovery (new, parked): no paid score; record says blind or program exact, contract transliterated; flood-repair-portfolio (new, fix): paid tests 100; record says tests at or above 95; batch-lease-scheduler-replay (new, parked): no paid score; record says 3 of 3 blinds full marks, contract transliterated; fuel-card-settlement-consolidation (new, parked): no paid score; record says blind or program exact
F1: leak cause: Every rule was one explicit sentence that named its own exception; no rule had a plausible wrong reading.
F2: leak cause: Two rules spelled out the trap in the rule text.
F3: leak cause: The only "split across files" was a two-file read that the instruction pointed to together.
F4: leak cause: A decoy was refuted on the same page as its use.
F5: leak cause: Shipped boundary rows let the agent watch each rule fire.
F6: leak cause: Hidden cases only repeated rules the agent had already coded; the agent's own self-test covered every hidden-case family.
(leak library rows: 22)

WHAT WE WANT
This kind runs where the teammate corpus is readable (an own session with the repository, or uploaded task folders). We have carded 66 teammate tasks. Study these uncarded ids, lowest Opus final first. For each, name the family (D1 to D9 or NEW), the deciding line as file:line, the points lost by the careful program, and whether every graded value is decided by the shipped files. Return items of type teammate_pattern. Patterns only: never copy task text, data or code.
T1: 85ba8b43 (Data Processing, Opus final 27.52): Diagnose and recompute a rejected arena-ladder season settlement from a multi-format export set, ...
T2: 725e575c (Debugging, Opus final 35.77): Repair a broken Python 3.12 run-ledger package so it follows an approved reconciliation specification, its ...
T3: 7c787cba (Debugging, Opus final 39.7): Repair a railway's working timetable compiler, which disagrees with the rulebook it is meant to implement ...
T4: 66b1a1e2 (Software Engineering, Opus final 39.75): Rebuild the reconciliation program for a two-replica calendar store whose replicas use three encodings, ...
T5: d49244f2 (Data Processing, Opus final 40.28): Assess a 2026 enterprise levy return batch under a 200,000-token consolidated statute whose amendments, ...

WHAT TO AVOID REPEATING
Research angles already run: A1 (N): Does weight concentration separate hard from easy?; A2 (S): Does the share of weight on hidden or rerun checks separate them?; A3 (N): Does rerunning on fresh inputs separate them?; A4 (S): Do withheld facts (evidence induction) make tasks hard?; A5 (M): What judge composition goes with low scores?; A6 (M): Which channel loses the points?; A7 (M): Is hardness about time?; A8 (S): Are contributor or domain confounds behind the bands?; A9 (M): Can genuineness be judged without verifier messages?; A10 (W): Do README bands match the stored run?; A11 (M): Do tasks share skeletons?; A12 (S): Are the hard tasks fair?.
Ranked untried angles you may take: U1: Self-test anatomy; U2: Judge negative design; U3: Easy-task leak autopsy; U4: Oracle shape across the 31 induction tasks; U5: Data heterogeneity; U6: Instruction phrasing; U7: Partial-credit curves; U8: Run variance.
Do not propose: a stated rule that a careful reader writes as code (F and K1); rules that are unwritten or confirmed only by examples or digests; exact optimum or runtime as the main difficulty; textbook puzzles; volume alone.

RULES FOR YOUR ANSWER
Do not invent sources. Mark reasoning without a source as evidence: none. No implementation code, no generated data, no task text. Use the exact format below so it can be stored by a script; nothing outside the BEGIN and END lines is read.

ANSWER FORMAT
BEGIN RESEARCH ANSWER
prompt_id: teammate_study-20261103T2135-0ea41a4b
tool: <ChatGPT | Gemini | other>
items: <number of ITEM blocks>
ITEM 1
type: <claim | idea | angle | teammate_pattern>
family: <one of D1 to D9, or NEW>
relation: <confirms ID | refutes ID | new> (ID is an id from this prompt: K, C, F, A, U or I)
title: <at most 12 words>
statement: <two to four sentences>
evidence: <source with a link or full citation; write none if it is your reasoning only>
confidence: <high | medium | low>
check: <one measurable check we can run on our own records or a small prototype>
domain: <idea and teammate_pattern only, else n/a>
data_shape: <idea only: what the shipped files look like, else n/a>
deliverable: <idea only, else n/a>
deciding_sentence: <idea only: the one doc sentence that decides the lever, else n/a>
hidden_plan: <idea only: what the hidden inputs carry that the shipped ones never show, else n/a>
careful_program_path: <idea and angle: what a careful exact program writes and where it goes wrong, else n/a>
solvability: <idea only: why every graded value follows from the shipped docs and data, else n/a>
END ITEM
(repeat ITEM blocks, numbered)
END RESEARCH ANSWER
```
