# G4 peer lever mining: group summary (board 6c051f3)

Anubis HEAD `19cdf6989906385943b9ca00acaadcae204b29e8`. One recorded claude-opus-5 run per task. Every number below was reproduced locally by importing each task's `tests/test_output.py` (with a no-op rewardkit stub) and running the agent's delivered program against the reference. The evidence is in the per-task A_/B_ files. Session rename: the db shows title `6c051f3`, but the session did not appear in the top 5 rows of `opencode session list`.

## 1. Scoreboard

"Stated-rule pts lost" counts only test points lost on a rule that is fully written somewhere the agent can read. "Wrong-value pts" counts every test point lost to a wrong value, whatever the reason.

| task | verdict A | overall / tests / rubric | wrong-value test pts lost | stated-rule test pts lost (genuine) | judge pts lost (genuine / unstated conduct) |
|---|---|---|---|---|---|
| clinical-assay-qc-recalibration-forge | PARTLY | 56.72 / 42.00 / 71.43 | 58 of 100 | 0 (all 58 come from one ambiguous definition) | 3 genuine (R8 code quality) / 3 unstated (R4 run twice) |
| 6090aa67 (seismic bulletin) | PARTLY | 68.22 / 65.00 / 71.43 | 28 of 80 | 0 (two output keys are never defined) | 0 / 8 (R4 hand recompute, R7 name policy values) |
| collateral-gated-settlement-ladder | GENUINE | 62.73 / 30.38 / 95.08 | 55 of 79 | **55** (one rule, stated twice) | 0 / 3 (R15 reordered-copy test) |
| iterative-solver-reconciliation | ARTEFACT | 53.60 / 23.88 / 83.33 | 51 of 67 | 0 (oracle applies a rule the spec never states) | 0 / 3 (R5 controlled variant) |

Each task lost its test points to exactly one root cause, or two in T2. Patching only those lines in the agent's program gave 0 differing artifacts on every case: shipped, hidden, and mutated. All 8 TRUTH levers in T1, all TRUTH levers in T2, and every "Trap (...)" rule in T4 were passed on the first write. These are the same leaked levers as in our cohort DIAGNOSIS.

## 2. Lever patterns that cost points (SAFE or RISKY only), ranked by genuine points

### P1. Type-strict rejection next to a normalising neighbour rule. SAFE. Family F (error path/rejection). Cost 55 test pts (T3).
- **Mechanism:** one field must have a strict native type, and any other type rejects the record. Elsewhere, the spec has broad "trim every value" and "corrections replace a field with text before parsing" rules. Those rules make coercing a digit string look like the helpful reading. The agent counted the 40 string-typed values (step 10) and chose to parse them (transform.py L371-384).
- **How it is written:** a bare type property with no example and no warning (schema.md L34: "must be a JSON integer and carries its own sign"). It is repeated once as one clause inside a long enumerated malformed-record list (L148-149).
- **Why self-tests miss it:** all of the agent's checks were interlocks and conservation identities (steps 27, 36-37, 41/44, 46, 49). These hold whether or not the 40 records are admitted. Nothing in the agent's checks says which rows should be rejected.
- **Evidence:** A_/B_collateral-gated-settlement-ladder.md. The separating case ships in the data (40 str, 34 float, 18 bool values).
- **Our tasks:** in vendor-archive or district-heat, make one numeric field type-strict ("is a JSON integer") while a global whitespace/normalise rule sits in another section, and ship a few string-typed rows. The rejection then ripples into totals and downstream state.

### P2. Code-quality judge criterion that names the forbidden shapes. SAFE. NEW family "named-shape code quality". Cost 3 judge pts (T1 R8).
- **Mechanism:** the criterion names concrete bad shapes, for example an except clause that discards an error. The agent's defensive fallback (`except zlib.error` → treat as raw) matched one of them.
- **Why self-tests miss it:** fallbacks are added by reflex and never exercised.
- **Evidence:** B_clinical-assay-qc-recalibration-forge.md §7. It satisfies JD-18.
- **Our tasks:** in cohort-retention, add a criterion against silent catch-and-continue in any loader that parses a binary or office file.

### P3. Whole-output exactness gates. RISKY. Amplifier, not a lever. Multiplied P1 and the T1/T2 ambiguities.
- **Mechanism:** a 5-point check passes only if the whole document, campaign or event set is exact. One root cause therefore fails many checks.
  - T1 `_full_core_matches` L1517-1525: one root cost 58 pts.
  - T2 `_campaign_matches` L2000-2008: one undefined key cost 25 pts.
  - T3 per-rule checks also assert the whole event-id set (test_output.py L812, L823, L832), so 3 "isolated" checks failed on an unrelated rule.
- **How it is written:** T3 instruction L37-41 states it in the open: "one cent or one unit out of place costs the whole file". That makes it legal, but T3's whole-set asserts inside per-rule checks hit TS-13 (one property per test) and TS-26 (double payment).
- **Use for us:** keep whole-artifact exactness checks (stated in the instruction) separate from isolated rule checks. Never put a whole-set assert inside a rule check.

### P4. Mutation and hidden-variant tests on governed constants. SAFE test design. Cost 0 genuine here, but it is the right way to hold a stated rule.
- **Mechanism:** the test changes one governed input and requires every dependent figure to move. Examples: T4 omega 1300 (L1208-1223), Newton cap 12 (L1226-1239), epoch 15000 (L1242-1255). T2 adds new history edges, retracted revisions and a whole new policy (make_case L1587-1756). T1 perturbs superseded files and requires the output to stay unchanged (L1928-1938).
- **Why self-tests miss it:** the agents only varied row order or relabels, or ran on trivially small synthetic extracts. None changed a governed constant and checked which outputs moved. T2's variant with 0 accepted events was not even investigated.
- **Our tasks:** in district-heat or cohort-retention, add hidden cases where the precedence-deciding row changes (for example, a later amendment for the reporting period). Only that one figure family should move.

## 3. Writing patterns: rule fully stated, not reflexively solvable
1. **Bare type property, no example** (T3 schema.md L34). This states a constraint, not a procedure. Nothing tells the agent that strings will occur.
2. **One clause inside a long enumeration** (T3 L148-150). The rule is present, but it is one item among many routine malformed cases.
3. **A global normalisation rule in another section** (T3 L14 trim, L92-94 corrections become text). This invites the wrong generalisation without contradicting the strict rule.
4. **Definition with a branch and no warning** (T1 stage_note_convergence.md L5: target is "the batch mass when that mass sits at or below the batch cap, and the batch cap otherwise"). Boundary `>=` folded into a definition (L7). Edge rules as trailing clauses (L9). In T1 the *timing* of the definition (once versus per round) was left open. That made it ambiguous, which we must NOT copy, but the branch-in-definition style itself is safe.
5. **Count defined by a balancing identity with another file** (T2 bulletin_spec.md L719-722: a count includes trimmed items "so that these counts sum to magnitude_stations.reported"). The rule is exact and checkable, but only by reading across files. It is family D.
6. **Global default with a counted exception** (T3 schema.md L10-11).

## 4. Anti-patterns (looked hard, cost nothing, or are not allowed)
- **Did not cost points:**
  - The rule is stated with its wrong route named. Examples: "Round-half-to-even is not this rule" (T2 L46-47), "...is a different procedure" (T2 L605-606), T4's "Trap (...)" paragraph after every rule, T1's footguns_and_gotchas.md that lists every trap. Every one of these passed. This is the same as our leaked CR/V0 levers.
  - Decoy and superseded files: T1 has 56 files including retired archives, T4 has a decoy plain-text omega and ~90 padding lines in known_pitfalls. All were handled.
  - Volume: a 34 KB spec (T2), a 4 MB output (T3), binary xlsx/pdf/docx sources (T1, T4). All were read correctly.
  - Judge "response states figure X" criteria: T3 R1-R9 pay 31 of 61 rubric points without checking correctness.
- **Only work because the rule is hidden (NOT ALLOWED):**
  - Undefined output keys (T2 `mag_station_count` L649, `relocation_drops` L752).
  - An oracle override the spec never states and other files contradict (T4 omega_history over Relaxation!B5).
  - A definition whose evaluation time is ambiguous (T1 fair share).
  - Every trajectory-conduct judge criterion with no instruction sentence: T1 R4 run twice and compare, T2 R4 hand-recompute a graded figure, T2 R7 enumerate policy keys and values, T3 R15 reordered-copy test, T4 R5 controlled variant. These fail IN-15/JD-15 unless the instruction asks for the conduct.

## 5. Score artefacts (never copy)
- **T4 is an ARTEFACT.** The reference (test_output.py L278-284) and solve.py (L270-272) override xlsx B5=1150 with omega_history row `20260,1205,active`. The schema never states this (L75-77 and L214 only call it "informational only unless..." and "the base"). It is contradicted by schema L208-209, known_pitfalls L3, the xlsx NodeAudit sheet, TRUTH.md L21-24 and judge R2. The patched agent matches on all 6 cases. Also, T4's "visible" checks regenerate a 60-node corpus, so 0 of 67 test points look at the delivered files. Lesson for QC: check that the TRUTH constants actually appear in the oracle outputs.
- **T2's 28 test points come from undefined keys.** **T1's 58 test points come from one ambiguous sentence.** Neither is a lever.
- **No permission artefacts.** All 4 graders copy or chmod the agent program to readable modes, open the output dir with 0777 and run under `setpriv nobody`, each with a comment about 0600 editor saves (T1 L1398-1402, T2 L1793-1795, T3 L626-668, T4 L871-897). This is the fix for our cohort Errno 13 bug.

## 6. Agent behaviour common to all 4 runs
- 34-55 steps, 9-20 min wall.
- The program is created in one shot 6-10 min in. Afterwards only encoding and I/O edits; the logic never changes (T1 step 25+, T2 step 11, T3 step 22, T4 step 24).
- Self-tests are determinism, reordering, primitives and identities, or tiny synthetic extracts. None used an independent oracle or a constant mutation. Each run's final claim was "done" or "verified".
- T1 step 25 even saw negative masses in its own hand trace and accepted them.

## 7. Open questions for the master chat
1. Should PARTLY ambiguity costs (T1, T2) feed any lever design? I recommend no, because they would fail IN-8/TS-19.
2. Should whole-artifact gating be adopted (P3)? It is legal only if stated in the instruction and kept out of per-rule checks. Do we accept the TS-13/TS-26 risk?
3. Should the T1/T2 grader permission block (copy to 0644, out 0777, setpriv nobody) become our standard test helper?
4. JD-7 on T4 R2: the criterion names B5 as the source, but the reference uses a different value. Should our QC add "judge source and value criteria match the reference constants"?
5. P1 is the only lever in this group that cost genuine points. Do we want 2-3 independent P1-style type and rejection rules per task, so one is not the whole score?
