# A_8764bfdd — artefact check (Data Processing, estatectl repair, Aditya Patel)

Run: `Final_Delivery/8764bfdd-.../trajectories/claude-opus-5/run_1/`. Recorded 67.39 / tests 51.46 / rubric 83.33.

## Verdict: GENUINE (tests and judge), with one caveat on attribution

## 1. ctrf vs task tests
- ctrf.json lists 50 tests; tests/test_output.py registers 50 criteria (:8279-8328). Names identical, weights identical (6 x 1, 40 x 5, negatives -5,-5,-5,-3). No diff. stacking_check: "50 checks, positive total 206, negatives -18; judge: 11 criteria, positive 18, mode batched".
- Run is on the shipped test file version (same names incl. decoy_* ids that appear in TRUTH.md decoy table :163-181).

## 2. Errors / timeouts / path
- result.json `exception_info` None; agent 04:12:58-05:46:26Z (93.5 min of 240), verifier finished 05:47:25Z.
- verifier dir has no reward-details.json / reward_raw.json (only ctrf, reward.json `{"reward":67.39}`, score.json, test-stdout `reward: 0.6739`). Not an error: score.json carries rubric + final_reward.
- ctrf failed tests carry empty message (checks print no expected values by design, TRUTH.md:185 "failure messages carry no expected values"). No traceback, no "errored" lines in test-stdout.
- Tool did run on the eval tier: every HARD check is `_visible_ok AND _eval_ok` (test_output.py:534-539); 20 HARD checks passed (incl. concept_c1, concept_c9, decoy_site_policy_v2_yaml), which is impossible if the eval run crashed, timed out (1500 s; agent measured ~82 s on 5100-row scale, eval scale is 200) or wrote to a wrong path. Permission: agent tested `env -i` from a read-only extraction (step 222, step 245) - consistent.
- All 7 deliverables present (artifacts_present_and_parse PASS, tool_archive_layout PASS).

## 3. Failed checks: value vs gate vs crash
20 HARD checks failed (100 of 206 pts): families t1, t3, t8, t10, t11, t12, t13, t14, t15; decoys inv_fin01_q3_r2_csv, ecs_annex_hosts_rev7_pdf, journal_mkt01_q3_b_log; concepts c2, c3, c4, c5, c6, c7, c8, c10.
- All are wrong VALUES (digest mismatch of a record set or of a concept population), not crash/path.
- Gate inside each concept check: `KEEP_PERMILLE = 990` (:71) and `_concept_ok` (:215-231) returns False on the FIRST kept record whose field hash differs, and requires the concept's whole exception set digest and extra digest to match. So a concept check is whole-population exact, and concept_c10 (ledger, control, chain, every entry id; :193-198) fails on any upstream error. This is amplification, not a hidden gate: the instruction states exact five-file output per ECS section 11 and the ledger reconciliation (instruction.md:5). Concept checks that passed (c1, c9) show the keep gate itself was met.
- Which rule(s) were read wrong cannot be pinned statically: messages are empty and the eval-tier truth exists only inside the inlined generator (running it is forbidden here). Recorded as UNDETERMINED. INFERRED partial map: TRUTH.md:183-185 says the eval tier plants one fixture each for five stated rules the visible inputs never reach (ECS 5.3 UNC/.. above root -> c2,t1; ECS 4.3 spring-forward gap -> c4,t3; ECS 6.4 equal captured_utc -> c3,t11; ECS 8 RESTORE after double delete -> c5,t13; ECS 8 OBJ01 hex sequencer with leading zero -> c5,t3). Every one of those eight checks failed. The rules are stated plainly in ECS-standard.md (4.3 at :102-111 "A time that maps to none (spring-forward gap) is read with the zone's standard offset"; 5.3 at :137 "a .. above the root makes the path unresolved"; 6.4 at :194 "ties go to the greater record id"; 8 at :255-262). So hidden separating cases for stated rules = GENUINE (W5 / TD1).
- c6, c7, c8, t8, t10, t12, t14, t15 and the three decoy checks are not covered by the five fixtures; INFERRED visible-or-eval value errors on stated rules (decoy facts each documented in their status header + an ECS section, TRUTH.md:163-181).

## 4. Negatives
None fired (ctrf "failed" for negative_* = cheat not detected; polarity comment :8214 "True means the cheat happened").

## 5. Judge
Rubric 15/18. Single loss r10 (+3, important, trajectory): "every except clause acts on the caught error, for example by reporting it on stderr, recording an ECS reason code, re-raising it or falling back to another documented reading of the same input." Judge: "at least one except clause with a bare pass in the TSV declared-encoding path". Confirmed in the delivered archive (artifacts/app/out/tool.zip, estatectl/estatectl.py:338-341):
```
try:
    fields = line.decode(want).split("\t")
except (UnicodeDecodeError, LookupError):
    pass
```
Real defect in the delivered code (silently keeps the earlier decoding). Borderline only in that the criterion's own list includes "falling back to another documented reading"; the clause falls through to the prior reading implicitly. Judged GENUINE (the criterion asks the clause to act; it does not).
All 5 negatives not fired; all other 5 positives (process criteria: ledger/control check, run_mode headers, precedence section, raw bytes inspection, rerun compare) passed.

## Points
- Genuine test points lost: 100/206 (= 48.54 tests pts). Attribution to specific rules UNDETERMINED (see 3).
- Genuine judge points lost: 3/18 (= 16.67 rubric pts).
