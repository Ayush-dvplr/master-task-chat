# RECHECK_FIX, schema-migration-plan-repair, P12 r5 (3b74d43)

Author: Ayush Sah. QC report: `QC/reports/schema-migration-plan-repair/v6.md` (board e50ca11, kit 71a653b2). Live kit HEAD 71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e, same as the report kit, so no rule changed. Bundle tree sha before 07efcfdfbe69, after bb51b816dfad.

Session rename: `name_session.py 3b74d43` printed "codex: no match / opencode: no match / NOT RENAMED" at start and end; not retried on another ID.

## Findings

| ID | label | rule quote (live kit) | evidence quote (bundle) | decision | playbook row | effect per lever (L1 / L2 / L5 / L6) | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| DS-22 / AL-18 ❌ | REAL | 02_Data_Solution_QC.md:78 "DS-22 TRUTH.md describes the bundle that actually shipped"; :117 fail list "DS-22 TRUTH.md contradicting the shipped solution, the real grading"; 05_Alignment_Integrity_QC.md:64 "AL-18 No stale references: nothing mentions ... counts, or numbers that do not match the actual bundle" | solution/TRUTH.md:149 (before) "installing a package (-3)" vs tests/judge.toml:91-94 `r7_installs_third_party_package` `weight = -1`; listed negatives summed 14 against the stated "negative total 12" | FIX: TRUTH.md:151 now "installing a package (-1)"; listed negatives 3 + 5 + 1 + 3 = 12 = stated total. Every other count re-checked after the JD-5 split: 63 checks = 10 + 17 + 30 + 6; 201 = 10 + 41 + 150; 6/201 = 3.0%, 41/201 = 20.4%, 150/201 = 74.6%; test negatives 14; judge "9 criteria, positive total 13, negative total 12" (:115-116); judged range -12/13 = -0.923 to +1.000, combined -0.496 to +1.000; solve.py 715 lines, sha 779b00ae... unchanged (checked last) | DS-22 (QC_FIX_PLAYBOOK.md:40) "Rewrite TRUTH.md to the shipped code and data" | none / none / none / none | none needed | solution/TRUTH.md |
| TS-13 🟡 | REAL | 03_Tests_QC.md:44 "TS-13 One property per test. A test asserting two unrelated properties hides which one failed and skews the weight; flag it." | tests/test_output.py:9786-9793 `receipt_counts_partner_rejected_lines`: `return _same(result["summary"]["receipt_mismatches"], expected) and prints == [None] * len(rejected)` | FIX TRIED, REVERTED, KEPT minor. Dropping the second condition raised the reflex replay from 39/201 = 0.194 to 42/201 = 0.209, over the 0.20 gate (log `WORK/trap/r5_after_ts13_rejected.log`). The second condition is the L2 separating observable (make-it-match writes a fingerprint into partner-rejected records and still gets the receipt right). tests/test_output.py is byte-identical to the before copy | TS-13 (QC_FIX_PLAYBOOK.md:33) DO "Split into two checks ... sharing the original weight"; NEVER "Dropping the harder half" | applied form: none / easier (replay +3) / none / none; kept form: none on all | revert (master direction) | none in the bundle (WORK/test_output.src.py edited and restored) |
| JD-5 🟡 | REAL (borderline) | 04_Judge_QC.md:71 "Each criterion names ONE observable behaviour ... If a judge would need to check two separate things, split it. ... a borderline case (two facets of one act) is a minor." | tests/judge.toml:27 R2 "... and checks both that batch's receipt result and the fingerprint field of the rejected record." R2 is the J2 w3 conduct criterion for L2 (LEVERS.md:183-188, QC_DEFENCE.md:75) | SPLIT, not reworded: R2 keeps w3 and now checks "the fingerprint field of the rejected record" (the L2 observable); new R9 `r9_checks_partner_rejected_receipt` w1, important, checks "that batch's receipt result". Judge 8 -> 9 criteria, positive 12 -> 13, negative 12; reward.toml judge 0.5/12 -> 0.5/13 = 0.038461538461538464 | none for JD-5; closest SUGGEST (:46) and TS-13 split DO (:33) | none / none on tests, judge: a receipt-only probe now earns 1 of 13 where it earned 0 of 12 (slightly easier), a full probe earns 4 of 13 against 3 of 12 / none / none | split instead of drop | tests/judge.toml, tests/reward.toml, solution/TRUTH.md |
| A3 / TS-23 ⚠️ | REAL (warn) | 03_Tests_QC.md:62 "TS-23 Counts and balance: at least 10 checks (fail), at most 35 (warn)"; tests_qc.py:295 `warn("A3", f"{n} checks; cap is 35 (warn)")` | tests/test_output.py:10073-10135, 63 registered checks | KEEP: Ayush approved (23 Oct 18:20, decisions.jsonl: the check-count cap is not an issue for any task); 63 is under the 70 cap | TS-23 (:34) "KEEP as a warn with the count and the kit line 03:62" | none on all | none | none |
| TS-15 ⚠️ | REAL (comment only) | 03_Tests_QC.md:46 "TS-15 Negative checks use inverted polarity ... Each negative check should carry an inline comment stating the inversion." | tests/test_output.py:9632-9638 `negative_unsafe_archive_members` returns `any(n.startswith("/") or ".." in Path(n).parts or n.endswith("/") ...)`, True when an unsafe member is present: polarity correct, comment missing | KEEP: Ayush accepted as-is (23 Oct 18:20); not edited | none (SUGGEST :46 KEEP) | none on all | none | none |

Counts: REAL 5 (DS-22/AL-18 as one), FALSE_POSITIVE 0, UNSURE 0. Fixed 2 (DS-22, JD-5). Kept 3 (TS-13 minor after the revert, A3/TS-23 warn, TS-15 warn).

## Deviations from master directions

1. JD-5 "keep R2 total weight": impossible as two criteria. 04_Judge_QC.md:111 JD-S7 allows only weights {1, 3, 5, -1, -3, -5}, so 3 cannot be split into two allowed halves, and judge_qc.py:243-245 needs ids R1..Rn in order, so the new criterion is appended as R9 rather than inserted. R2 keeps w3 on the L2 observable (fingerprint field), R9 takes w1 (JD-13: important needs 1 or 3). Judge positive 13, negative 12 (JD-12 holds, 12 <= 13).
2. "same in WORK/TRUTH.src.md / make_truth.py" and "update make_judge.py": WORK/README_STALE.md marks both generators stale (make_judge.py writes the old 17-criterion individual judge; make_truth.py writes the old layout and TRUTH.src.md has no negatives sentence), and round notes E forbid running stale scripts. Neither was run or edited; the bundle files were edited directly and a P12 r5 note was added to README_STALE.md. Current generators kept in step: WORK/test_output.src.py + embed.py (embed output "embedded 33 files; test positive 201, negative 14, judge positive 13").
3. TS-13 conditional fix reverted by its own condition (reflex gate), as the direction allows.

## Gate results

- xref_check: 50 entries, 0 findings (new entry "judge R9 id"; "judge criteria" value updated, old value retired).
- QC scripts (live kit, outputs in `qc/`): structure 17 pass / 0 warn / 0 fail; instruction 5 / 0 / 0; tests 36 pass / 1 warn (A3, 63 checks) / 0 fail; judge 19 / 0 / 0. 0 FAIL.
- Manual: DS-22 listed judge negatives sum 12 = stated total; TS-13 test unchanged from before; JD-5 R2 and R9 each name one observable, R9 importance important at w1 (JD-13), JD-12 12 <= 13; JD-7 oracle meets R2 and R9 through solve.py self_checks probe 2 (records[1] code E_ALIAS_CYCLE, fingerprint None, B1 not in receipt_mismatches).
- stacking_check: exit 0; same two hints as Harden r1 resolved by hand (TS-26 shared `_holds` artefact; AL-28 UNMATCHED group of four different acts each <= 5). See `STACKING_CHECK.md`: STACKING PASS.
- Docker (`/tmp/smpr-p12r5b-20261023T183819-9ead73`, copies by live kit exe_copy.py, plain and --owner-only, ALL_DONE): oracle 1.0 / 1.0 / 1.0, owner-only 1.0, nop 0.0. One earlier chain (`/tmp/smpr-p12r5-20261023T183715-9d04a8`) was stopped during its first build because the copy step left stub lines; ABORTED.txt there.

## Reflex before / after

`harden_r1/agent_program/replay.py`, tests channel, local grade: before 39/201 = 0.194, after 39/201 = 0.194 (tests file identical). With the TS-13 drop applied it was 42/201 = 0.209 (rejected).

## Trap survival

Before = `WORK/trap/before_r5/tests` (copied before any edit), after = the fixed bundle tests; P = 201 positive test points; local grade, tests channel (`WORK/trap/score_r5.py`, logs `r5_before.log`, `r5_after.log`). Oracle loss before 0, after 0. The TS-13 drop failed this gate on the reflex (42/201 = 0.209) and was reverted before this run.

| variant | before loss of P | after loss of P | ratio | separating kept | verdict |
|---|---|---|---|---|---|
| replay (reflex) | 39/201 = 0.194 earned | 39/201 = 0.194 earned | n/a | n/a | PASS |
| shipped | 195 | 195 | 1.00 | y | PASS |
| F1-F4 planner | 125 | 125 | 1.00 | y | PASS |
| F5 from_payload | 83 | 83 | 1.00 | y | PASS |
| F6 decoy null | 47 | 47 | 1.00 | y | PASS |
| F6 fill | 49 | 49 | 1.00 | y | PASS |
| F7 parser merge | 54 | 54 | 1.00 | y | PASS |
| F7b tokens_for or | 51 | 51 | 1.00 | y | PASS |
| F8 executor | 59 | 59 | 1.00 | y | PASS |
| F9 classify | 56 | 56 | 1.00 | y | PASS |
| F10 admit | 96 | 96 | 1.00 | y | PASS |
| F11 order | 61 | 61 | 1.00 | y | PASS |
| F12 identity | 109 | 109 | 1.00 | y | PASS |
| F13 feed | 54 | 54 | 1.00 | y | PASS |
| F14 summary | 156 | 156 | 1.00 | y | PASS |
| F16 tokens trimmed | 87 | 87 | 1.00 | y | PASS |
| F17 receipt shipped | 138 | 138 | 1.00 | y | PASS |
| F15 cli | 38 | 38 | 1.00 | y | PASS |
| W_alias_before_id | 51 | 51 | 1.00 | y | PASS |
| W_corrections_sorted_by_id | 55 | 55 | 1.00 | y | PASS |
| W_tokens_after_planning | 55 | 55 | 1.00 | y | PASS |
| W_cast_int_drops_integral_float | 51 | 51 | 1.00 | y | PASS |
| W_cast_touches_null | 41 | 41 | 1.00 | y | PASS |
| W_cast_converts_booleans | 41 | 41 | 1.00 | y | PASS |
| W_fingerprint_ascii_escaped | 61 | 61 | 1.00 | y | PASS |
| W_schema_before_partner | 51 | 51 | 1.00 | y | PASS |
| W_partner_before_batch | 51 | 51 | 1.00 | y | PASS |
| W_holder_needs_known_schema | 50 | 50 | 1.00 | y | PASS |
| W_receipt_make_it_match | 103 | 103 | 1.00 | y | PASS |
| W_receipt_counts_parse_rejects | 98 | 98 | 1.00 | y | PASS |
| W_receipt_skips_rejected | 104 | 104 | 1.00 | y | PASS |
| W_receipt_always_empty | 87 | 87 | 1.00 | y | PASS |

Trap survival: PASS (every variant >= 90% of its before loss, no separating hidden case gone, reflex <= 0.20).

## QC_RULINGS rows

- DS-22/AL-18 | schema | v6:DS-22 | TRUTH negatives list said R7 -3 against judge -1 | FAIL | stale count | FIXED-IN P12 r5 (TRUTH to shipped weights)
- TS-13 | schema | v6:TS-13 | `receipt_counts_partner_rejected_lines` asserts receipt and null fingerprint of rejected records | MINOR | two properties | KEPT: dropping the fingerprint half raised reflex 0.194 -> 0.209; it is the L2 separating observable
- JD-5 | schema | v6:JD-5 | R2 checked receipt result and fingerprint field | MINOR | two facets of one probe | FIXED-IN P12 r5 by split (R2 w3 fingerprint, R9 w1 receipt); REUSE: one observable per J2 conduct criterion
- A3/TS-23 | schema | v6:A3 | 63 checks | WARN | above 35 | KEPT (Ayush 23 Oct 18:20, under 70)
- TS-15 | schema | v6:TS-15 | `negative_unsafe_archive_members` without the inversion comment | WARN | comment missing, polarity correct | KEPT (Ayush 23 Oct 18:20)

## Lessons for the master

- A TS-13 drop on a lever check can raise the reflex even when the worlds compare the same field whole; run the replay before accepting any "drop the second condition" suggestion.
- "Keep total weight" cannot hold when splitting a w3 judge criterion (JD-S7 {1,3,5}); give the lever observable the w3 and the other facet w1.
- The direction to edit make_judge.py / make_truth.py conflicted with README_STALE.md; directions should name only current generators.
