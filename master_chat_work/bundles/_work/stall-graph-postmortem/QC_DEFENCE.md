# QC_DEFENCE stall-graph-postmortem (harden r1 Phase 2)

Phase 1 OPEN entries are now marked FIXED with the live position. New lever entries follow.

## Existing design

| item | rule ids | live position (quoted) | status / why it passes | safe fallback (playbook row + DO fix) |
|---|---|---|---|---|
| 12 decode rules, one sentence each | AL-1, AL-27 | each flag has its own sentence, `journal-and-wire.md:42-95`; checks `trap_*` w5 on hidden corpora forcing one flag | determinate, stated, graded on hidden reseeded corpora | AL-1 DO: keep the sentence and the hidden-only separating case |
| 13 window variations | AL-1, TS-19 | rules in `identity-and-registry.md`, `attribution-and-blame.md`, `epochs-and-clocks.md`, `invariants-and-closure.md` | FIXED: `calibration-and-controls.md:53-55` and `instruction.md:3` now say a later capture brings "its own copies of the side tables, laid out as the shipped ones are" | TS-19 DO: restate the bound so a later capture carries its own side tables laid out as the shipped ones |
| whole-document exact grading | CL-4 | no exactness sentence in `instruction.md` | FIXED `instruction.md:11`: G5 sentence "Each output document is graded whole on fresh windows, and only an exact match counts." | CL-4 DO: the G5 clause only (FC:491 exemption) |
| announcements | IN-17 | `instruction.md:1` "nothing tells you which of them bears on which figure, or in what order they bite", "for exactly one assignment of them to survive"; `instruction.md:33` "Five rules govern how you work"; `calibration-and-controls.md:29-31` "Exactly one assignment of the nine constants above reproduces all eleven at once." | FIXED: all four removed; rule sentences at `instruction.md:33` kept as plain statements | IN-17 DO: delete the announcement, keep each rule sentence |
| trap explanation | W1, IN-17 | `identity-and-registry.md:25-26` "A reading that takes the newest live row is a reading of the wrong window." | FIXED: sentence removed; bold rule `identity-and-registry.md:22` stays | IN-17 DO: delete the explanation only |
| sample answers | W11, Never 11 | `sample_summary_answer.json`, `sample_audit_answer.json` give summary and policy_audit for the sample population | kept: master rule "never contradict a shipped answer or sample answer file"; the sample population has all flags clear and does not separate any lever | flag to master only |
| negatives | G4 | hardcoded_sample_answers -5, filename_dependent_behaviour -5, reads_supplied_answer_data_at_runtime -5, nondeterministic_output -3 | kept per master note | none |
| test count 36 | A3 | 36 > 35 | WARN; master: no cap | none |
| grader permission fix | TS-30, H6 | `tests/test_output.py:1160-1178` skips `sys.executable` in `_grant_read` | keep | none |
| verifier format | TS-13, TS-26 | `tests/test.sh` chown root + chmod 755 /logs/verifier; `tests/Dockerfile` pip line exact | keep | none |
| bytecode | TS-25 | `tests/__pycache__/test_output.cpython-314.pyc` present | FIXED in Phase 3 | delete the folder |
| TRUTH stale | AL-2 | `solution/TRUTH.md:387` "positive total of 137" vs 142 at `:157` | FIXED: TRUTH provenance says 142, sha updated | update TRUTH after edits |

## New levers and cascade (harden round 1)

| item | rule ids | live position (quoted) | why it passes | safe fallback (playbook row + DO fix) |
|---|---|---|---|---|
| LV-1 closed partition set | AL-1, AL-27, CL-4, TS-19 | `invariants-and-closure.md:53` "A cell or a segment that no counted event reaches still reports, and reports zero."; `instruction.md:11` names the six partition files | stated single-reading rule; separating cases hidden only (12 corpora); bound restated so hidden side tables are in scope; whole-file exactness covered by the G5 clause | AL-27 DO: keep the sentence, move plants to fewer corpora; TS-19 DO: keep the restated bound |
| LV-2 padding writes the owner window | AL-1, AL-27, IN-16, W7 | `journal-and-wire.md:64-66` padding follows the events in written order; `journal-and-wire.md:83` "Every body line of the file, in logical order, writes its own owner into the window slot" | reference now follows the text; one reading (position and ring write both stated); every control reconciles under both readings, so the controls neither confirm nor contradict | IN-16 DO: tighten the padding position sentence; never add a separating example to environment/ |
| LV-3 owner alias rows | AL-1, AL-27, IN-17 | `identity-and-registry.md:59-65` (owner tag resolved at its event's epoch by governing rows; self-naming tag wins whatever its status; no live row, seventh row or revisit leaves it as written) | one sentence fixes which tags, which epoch, and the fallback; shipped/calibration/sample figures unchanged | AL-1 DO: keep the sentence, never name the hidden alias spellings |
| D3 0x010 byte order | IN-16 | `journal-and-wire.md:68-70` groups of two hex digits read in reverse order | one reading, matches `pair_reverse` | IN-16 DO: reword only |
| D4 stride and padding position | IN-16 | `journal-and-wire.md:53-58`, `:60-66` | stride walks event positions only; padding is the physical tail | IN-16 DO: reword only |
| judge rebuild | J2, J3, J4, J6, J8, J9, AL-28, IN-15 | `tests/judge.toml` R1-R11; oracle acts printed by the self-check stage in `solution/solve.sh` | conduct wording absent from instruction.md and data (grep clean); one negative per act; R10 uses no token 'not' | J3 DO: keep one honesty negative at -5 |
| CL-4 one fact wrong | CL-4 | `instruction.md:11` "Each output document is graded whole on fresh windows, and only an exact match counts." | G5 exemption (FC:491) | CL-4 DO: G5 clause only |
