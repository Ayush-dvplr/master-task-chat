TASK: ceadc676-2dc1-5575-80d7-b145aba9b5f1, scientific data pipeline (EA-IRMS isotope batch recompute from raw peak exports, 21 reports plus manifest), Opus tests 8.45, rubric 75.58, final 42.02.

1. VERDICT: DESIGN, 100 percent of lost test weight (65 of 71 positive weight), confidence low. All losses sit behind the full-core gate. The files do not show which core report or corpus failed, and no defect was found in what was read.

2. LOSSES:
1. 21 checks, weight 65 (6 shipped leaf reports at 3, 7 shipped leaf reports at 1, 6 held-out and 2 metamorphic reruns at 5). Cause: WRONG output in at least one of the eight core reports (injection ledger, linearity slopes, drift fits, normalization fits, corrected injections, session acceptance, sample results, replicate screening), on the shipped batch or on a held-out batch. No crash and no timeout on the fresh-path rerun.
2. Passed: deliverables, fresh-path run, headers, JSON keys, manifest, serialization (6 of 71).

3. DIFFICULTY KIND: (b) and (a), probably both. The held-out batches add PDF octal escapes, Td moves and uncompressed streams, xlsx rich-text runs and cells without an r reference, YAML flow mappings, a skipped spring hour with a pause typed inside it, a negative base offset, and tie-breaks the shipped data never shows (two rulings on one date, two ACTIVE requests, two leak checks in one minute, LIMIT_STOP and MAX_REJECT together). The shipped data already carries hard cases (repeated fall-back hour in SQ-2611-07, double SKIP, a REVERSE of a REVERSE). The judge says the agent never inspected the SKIP lines before writing the tray mapping, the journal chain, the repeated-hour records or the full ruling history (R9, R10, R12, R13, R16). A shipped-level miss is therefore also possible (d).

4. EVIDENCE:
1. Gate: tests/test_output.py:3700 _full_core needs every CORE report exact in /app/out and on every corpus in HELD (test_output.py:3446), and _leaf and _held_out_exact both require it.
2. Shipped spot check: session_acceptance.csv for SQ-2611-16 N gives computed REJECT, ruling RL-0484, decision ACCEPT, which fits method_handbook.md:195 to 197 (the latest IN FORCE ruling replaces the computed decision). No divergence was located.

5. TEST DESIGN: a seeded generator in test_output.py rebuilds the shipped batch, six reconfigured held-out batches and two metamorphic copies (extra tray journal chains, extra rulings and a smaller scope). Reports are compared exactly after normalization (row multisets with numbers by decimal value, canonical JSON). One core miss on any batch zeroes 65 of 71. Negatives: replayed answers, filename dependence, nondeterminism, third-party import, echoing published values, and two flipped methods (withdrawn reference set, SKIP events ignored).

6. INSTRUCTION: "every other report rests on the eight core reports ... which have to be exact on the shipped batch and on every fresh batch"; "with memo, workbook and YAML files written by other tools" (the only hint at encoding variation); "Each run has to finish within two minutes"; "Arithmetic and rounding follow the handbook exactly". The final message must list the defects with the rule or table that overrides each, plus the sets aside. Not said: which tie-breaks or clock edge cases the held-out batches exercise.

7. RUBRIC: lost R9, R10, R12, R13, R14 and R16 (the agent did not view specific shipped evidence rows, such as SKIP lines, a journal chain, repeated-hour records, PAUSE rows, the linearity session list and a ruling history, before coding the matching logic) and R24 (sqlite3.Error swallowed with pass). No judged negative fired.

8. REUSABLE IDEA: grade with rubric items that check the agent looked at the exact source rows behind each tricky rule before implementing it (inspect before code). Pair this with held-out corpora that move the same rules to edge cases (ties broken by id, two stop conditions at once, a time typed inside a clock gap) and with documents written by other tools (other PDF text operators, other xlsx cell forms, YAML flow style), all behind a full-core exact gate.
