# P12 recheck + fix: district-heat-flex-procurement (QL round 1, board 8556721)

Kit HEAD `5574d77eb9f22c207ba05fd8f9ac31d42ba45271` (live = report kit; no rule ID or wording changed). Frozen tree before fixes `e9d91966ed25` (BUNDLE = backup `WORK/pushed_e9d91966ed25` = PREV_QC_COPY 3f737e9; `POST_QC_DIFF.diff` empty). "TO" = `tests/test_output.py` before edits. Kit files under `Input_Bundle_QC/`.

Noise check (Always 13): every cited line is byte-identical to PREV_QC_COPY (empty diff), and v9 passed those rows. The carry-over ruling (QC_RULINGS carry-over, Ayush decision 2, 27 Oct) lets a finding on unchanged bytes stand only where it names a live kit line v9's PASS reason missed; the "noise" column records that test per row (detail in triage `ql_triage_17a1c2f/TRIAGE.md`).

## Phase 1 rows

| ID | label | rule quote (kit file:line) | evidence quote (bundle file:line, before) | noise check | decision | playbook row | effect per lever (REENTRY / CHAIN1 / RELIEF / WIDE / greedy) | compensation | files changed |
|---|---|---|---|---|---|---|---|---|---|
| QL1-F1 | REAL | TS-25 "Positive tests grade earned work, never an absence ... if it passes because something bad is missing (an empty violations list ...)" 03_Tests_QC.md:52; sev fail :135 | TO:1922-1924 `tie_decisions_match` "Run on the shipped extract"; reference on shipped data gives `tie_decisions []`; a program writing a constant `[]` passes (w3, TO:2370) | v9.md:162 "positives all require produced values" missed that the produced value is the empty list: stands | FIX: same check id and w3, pointed at a generated extract whose expected tie_decisions is non-empty | TS-25 (DO: assertion on earned output in a separating case) | none / none / none / none / none (removes 3 a no-tie program earns) | none needed | TO |
| QL1-F2 | REAL (part) | AL-2 "Everything promised is graded. Enumerate from `instruction.md` alone ... An ungraded promise invites solutions that skip it" 05_Alignment_Integrity_QC.md:33; CL-1 Final_checklist.md:488 | instruction.md:9 "When you finish, reply with a short report of what the program does and how you checked it."; only judge.toml:90-99 R7 (-5, false pass claim) reads the reply | v9.md:219 cited R7, which cannot grade a missing reply or the program description: stands | FIX: remove the sentence; R7 stays and still reads any reply (G3: R7 grades the remaining "false check claim" act) | AL-2/CL-1 (DO: not a lever -> remove the request) | none on all | none needed | instruction.md |
| QL1-F3 | REAL | AL-27 "a rule only counts as graded when the test's input actually constructs the situation where the rule matters" 05_Alignment_Integrity_QC.md:38 | schema.md:19-22 ([units], [region_codes] "Several codes can name the same region.", [segment_codes]); TO:789 `wh_per_tick = {spec.get('wh_per_tick', 10)}` and literal `millicents_per_cent = 1000`; TO:790-791 write the shipped code tables; no spec sets them | v9.md:224 fixture list covers none: stands | FIX: hidden generator draws units and fresh code strings per hidden extract; generator arithmetic follows the drawn wh_per_tick | AL-27 (DO: hidden reseeded rows inside stated bounds) | none / none / none / none / none; new hidden-coverage row UNITS-CODES = harder | n/a (harder) | TO |
| QL1-F4 | REAL | AL-27 05_Alignment_Integrity_QC.md:38 | schema.md:23-25 "A segment name with no option has an adder of 0."; TO:794 default writes both names, TO:981/1147/1421 always both | v9.md:224: stands | FIX: one hidden extract omits a segment's adder option while that segment has chosen offers | AL-27 | none on old levers; new row ADDER-MISSING = harder | n/a | TO |
| QL1-F5 | REAL | AL-27 05_Alignment_Integrity_QC.md:38 | schema.md:57-59 "An interval with no kept row means 0 Wh of both."; TO:833 writes every interval of every offer | v9.md:224: stands | FIX: drop a kept profile row of a chosen, site-linked offer in hidden extracts | AL-27 | none on old levers; new row PROFILE-GAP = harder | n/a | TO |
| QL1-F6 | REAL | AL-27 05_Alignment_Integrity_QC.md:38 | site_allowances.tsv comment "events reached before it"; reference TO:554 filter, deduction after all regions TO:566-569; triage sweep "within-event" 0 of 13 extracts change | v9.md:224 lists allowance fixtures, none with one site in two regions of one event: stands | FIX: hidden site with offers in two regions of one event, allowance binding only under the within-event reading | AL-27 | none on old levers; new row ALLOW-WITHIN = harder | n/a | TO |
| QL1-F7 | REAL (both halves) | AL-27 05_Alignment_Integrity_QC.md:38 | schema.md:230-236 "add up to F or less" vs TO:648 `<= funded`; "more than what remains" vs TO:554 `<= left`; sweep F7a 0 of 13, F7b 1 of 13 (H2, ungraded families only) | v9.md:224: stands | FIX: hidden cases with claims == F and need == left, on graded families | AL-27 | none on old levers; new rows CLAIM-EQ, ALLOW-EQ = harder | n/a | TO |
| QL1-F8 | REAL (minor) | JD-5 "Each criterion names ONE observable behaviour ... If a judge would need to check two separate things, split it" 04_Judge_QC.md:71 | judge.toml:38-47 R3 "... checks the credit_cents and cap_binding_count it reports against figures it worked out by hand" (w3); solve.sh:432/:433 show each figure | v9.md:185 itself calls them "two facets of one act", the kit's minor wording: stands | FIX: two trajectory criteria, one per figure, w3 each; positive judge 24 -> 27; reward.toml judge 0.5/27; solve.sh one `check <id> ok` line per criterion | JD-5 (DO: split + JD-2/7/9/15, IN-8 re-checks) | judge R3: easier (one-figure checker 3/27 instead of 0/24); tests levers none | none: master ruling 04:15 (each half w3 per judge rules); recorded in Lessons | judge.toml, reward.toml, solve.sh |
| QL1-F9 | FALSE_POSITIVE (carry-over) | TS-23 "at least 10 checks (fail), at most 35 (warn)" 03_Tests_QC.md:62 | `WARN [A3] 66 checks; cap is 35 (warn)`, registrations TO:2362-2427 | KEPT.md p12_fix_v6_9a85fdc TS-23 KEEP; QC_RULINGS:137 option A | KEEP warn with count (no edit, master ruling) | TS-23 | none | n/a | none |
| QL1-F10 | REAL (fail) | TS-16 "Anti-cheat negatives must fire on the cheat and ONLY on the cheat ... could an honest solution trip this?" 03_Tests_QC.md:47; sev fail :135 | TO:2356 `network = {"socket", "urllib", "http", "ftplib", "smtplib", "ssl", "xmlrpc"}` fires on stdlib modules; instruction.md:3 allows the Python 3.12 standard library | v9.md:157 equated the network set with the stdlib rule: stands | FIX: trigger only on modules outside `sys.stdlib_module_names`; description "imports a module outside the Python 3.12 standard library" | TS-16 (DO: narrow to the cheat) | none on all | none needed | TO |
| QL1-F11 | OUT OF SCOPE (SUGGEST) | no kit line: TS-28 03_Tests_QC.md:73 four defences all present (v9.md:169) | TO:1643-1645 Popen without `env=` | n/a | no edit (master ruling) | SUGGEST | none | n/a | none |

## Deviations from master directions

None. Note on F8: playbook v3 row JD-5 says "keep the total weight in the same family"; the master ruling (29 Oct 04:15) follows the judge weight rule instead (JD-13 04_Judge_QC.md:90, an important criterion weighs 3), so each half keeps w3 and the positive judge total is 27. Recorded in Lessons.

## What changed (files)

- `tests/test_output.py` (generated from `WORK/test_output.src.py` by `WORK/embed.py`): F1 `tie_case_passes` + new description of `tie_decisions_match` (w3 kept); F3-F7 hidden generator (drawn `wh_per_tick` 4/5/20/25 and `millicents_per_cent` 400/500/2000, 2-3 fresh region codes per region and 1-2 fresh segment codes per segment, `public` adder option omitted on the settlement extract, two dropped profile rows of chosen offers, a cross-region `draws_from` pair whose holder allowance is one tick short of both draws, an allowance equal to the need left, a pool whose claims add up to F exactly) and 7 new reference wrong-reading flags (UNIT10, CODESHIP, ADDmiss, GAPdrop, LEDwithin, ALWge, CLAIMlt) added to `HIDDEN_GUARDS`, so a hidden seed is kept only when each changes a graded family; F10 negative trigger `sys.stdlib_module_names`.
- `instruction.md`: F2 line 9 removed.
- `tests/judge.toml`: F8 R3 credit_cents only, new R12 cap_binding_count (w3); `tests/reward.toml` judge 0.5/27; `solution/solve.sh` prints `check R3 ok` and `check R12 ok`.
- `solution/TRUTH.md`: drift list, negatives, judge 12 (+27/-5), measured figures, ordered plan step 5; sha lines rewritten by script last.
- WORK docs: QC_DEFENCE (P12 section), XREF (R12 entry), JUDGE_MAP, LEVERS (P12 section), RULE_COVERAGE (7 rows), COST_TABLE (P12 section).
- G7 byte diff: `OUT/G7_tests_diff.txt` (Dockerfile, test.sh SAME; judge.toml, reward.toml, test_output.py CHANGED; every hunk belongs to F1, F3-F8 or F10).

## Touched rules

| id | touched how | rules re-checked | verdict with file:line |
|---|---|---|---|
| tie_decisions_match (w3) | re-pointed from the shipped extract to the generated tie extract `case_root("tie")` | TS-13 one property (tie_decisions of policy_audit.json), TS-14 name states the property, TS-20 w3 core unchanged, TS-25 expected non-empty `[{T2-0001, North, 2, [T2-0001-S1-Z, T2-0001-S2-M]}]` so a constant `[]` fails, TS-26 different extract from `tie_decisions_match_hard` (hidden H1) and `wide_k_tie_decisions_match` (wide k), CL-2 forging needs the tie, CL-4 one wrong tie costs 3/237 | PASS tests/test_output.py:2086-2105 |
| negative_external_dependency_or_network (-3) | trigger narrowed to roots outside `sys.stdlib_module_names`; description re-worded | TS-16 honest stdlib program (socket, http.client, json) does not fire, numpy/requests fire; TS-14 description names the act; AL-28 group sum 3 <= 5 (STACKING_CHECK) | PASS tests/test_output.py:2525-2535 |
| hidden generator H1/H2 (feeds 18+ *_hard checks) | new drawn inputs and planted cases; check ids and weights unchanged | TS-25 each plant changes a graded family under its wrong reading (guards); TS-26 no new check; CL-2 unchanged; CL-4 one wrong reading costs 5 (CLAIMlt) to 100 (CODESHIP) of 237, every misreading still keeps all 61 shipped points (no almost-right scored as entirely wrong, 05_Alignment_Integrity_QC.md:88) | PASS tests/test_output.py (`_hidden_spec`, `_plant_ledger`, `_plant_exact_claims`, `HIDDEN_GUARDS`) |
| R3 (w3) | split: now grades credit_cents only | JD-2 positive grammar (no banned token), JD-5 one figure, JD-6 decidable from the trajectory (agent's own extract, hand figure), JD-7 oracle prints `check R3 ok` (solve.sh:434), JD-9 trajectory, JD-13 important w3, JD-15 own label `r3_checks_composed_rate_credit_on_own_extract`, AL-28 not a penalty, IN-8 knowable from schema.md rate rules | PASS tests/judge.toml:37-48 |
| R12 (w3) | new, split from R3: cap_binding_count | JD-2, JD-5, JD-6, JD-7 oracle prints `check R12 ok` (solve.sh:436), JD-9, JD-13 w3, JD-15 label `r12_checks_composed_rate_cap_binding_on_own_extract`, JD-S4 ids R1..R12 sequential, AL-28, IN-8 | PASS tests/judge.toml:154-165 |
| reward.toml | judge weight 0.5/24 -> 0.5/27 | TS-S10 0.5 / positive total (tests 0.5/237 unchanged) | PASS tests/reward.toml |

## Vacuity probe

- Shipped tool and data, no agent edit: the shipped `environment/` has no `/app/out/derive_report.py`, so every positive test check fails at `artifact_set_exists_and_parses` / `run_agent` (nop run in Docker below: reward 0.000).
- New `tie_decisions_match` (local projection, /tmp probe): constant `[]` passes False; the H2 wrong reading passes False; LEDtie passes True (single event, irrelevant to tie detection).
- Negative probe: socket + http.client fires False, json False, numpy True, requests True.
- Judge: R3 and R12 need the agent to build its own extract and a hand figure; an agent who changed nothing has no trajectory act, earns 0 of 6. Other criteria unchanged from v9.
- Verdict: PASS.

## Side effects

| FIX id | ids re-checked | result |
|---|---|---|
| F1 | NEW-CHECK: TS-13, TS-14, TS-16, TS-25, TS-26, TS-17/TS-24 wording | clean (Touched rules row 1) |
| F2 | AL-2 re-enumerated from instruction.md (no reply promise left), JD-6/JD-15 R7 still reads any reply, IN-15 no rule moved | clean |
| F3-F7 | TS-25 guards, CL-4 one-wrong-reading table, verifier time (worst grader 46 s per program in the sweep), oracle 237/237, solve.py = reference on all families of 12 hidden extracts, 20 visible cases byte-identical | clean |
| F8 | JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, JD-S4, IN-8, TS-S10, AL-28; precheck J3 (name > 64 chars) found once and fixed by shortening R3/R12 names | clean after fix |
| F10 | TS-16, AL-28 | clean |

side_effect_findings: 1 (judge_qc J3 name length, fixed before PRECHECK CLEAN).

## Noise keeps

- QL1-F9 TS-23 66 checks (warn): registrations byte-identical to PREV_QC_COPY 3f737e9 (empty `POST_QC_DIFF.diff`); KEEP with count per QC_RULINGS:137 option A and KEPT.md p12_fix_v6_9a85fdc.

## Trap survival

| lever | before loss (/237, TRAP_g36) | after loss (TRAP_p12new) | kept | verdict |
|---|---|---|---|---|
| REENTRY | 45 | 45 | 100% | PASS |
| CHAIN1 | 55 | 55 | 100% | PASS |
| RELIEF | 58 | 53 | 91.4% | PASS |
| WIDE (exact generic search, a12/a11 agent programs) | 64 | 64 | 100% | PASS |
| greedy | 165 | 183 | 111% | PASS |

No separating hidden case was removed (only added); no loss table exists for this round (`none`). New rows, wrong reading alone on the new tests vs the old tests: UNIT10 147 (old 237), CODESHIP 137, ADDmiss 202, GAPdrop 222, LEDwithin 202, ALWge 197, CLAIMlt 232 (old-test column in Gate results). Each loses >= 1 graded check by WRONG output (graded in ~45 s, no timeout).

Predicted tests for the a12 agent program (`20261028_district-heat-flex-procurement/gate_run_a12/run/artifacts/app/out/derive_report.py`) on the new tests: 173/237 = 73.0 (fails only the 16 wide checks at the 120 s limit; passes every hidden check including F3-F7). a11 agent program: 173/237. The F3-F7 rows therefore do not lower these two programs; they bite programs with those misreadings.

## Gate results

| gate | result | evidence |
|---|---|---|
| precheck | `PRECHECK CLEAN` (warn A3 66 checks = F9 keep) | `tools/precheck.sh BUNDLE`, run after the TRUTH sha rewrite |
| xref_check | 50 entries, 0 findings | `WORK/XREF.md` (R12 entry added) |
| stacking | PASS | `OUT/STACKING_CHECK.md` (hidden/mutated 73.0%, AL-28 groups <= 5) |
| trap survival | PASS | table above (RELIEF 91.4% lowest) |
| G7 byte diff | every hunk belongs to F1, F3-F8 or F10 | `OUT/G7_tests_diff.txt` (Dockerfile, test.sh SAME) |
| Docker block (exe_copy plain / --owner-only, --memory 4g --cpus 2) | oracle 1.000 / 1.000 / 1.000; owner-only 1.000; nop 0.000 | `/tmp/opencode-logs/dh-8556721/dchain-20261029T051636-923a/runs.log` (ALL_DONE 05:37:47); oracle log prints `check R3 ok`, `check R12 ok` |
| Tasks_INPUT sync | 6 files copied, `diff -rq` empty; tree_sha 2b289f9f9561 (intake.py tree_sha) | Tasks_INPUT/district-heat-flex-procurement |
| verifier time | oracle 46 s; worst measured a12/a11-like program 485 s = 18% of 2700 s (<= 90%) | runs.log; `WORK/p12/dout/TRAP_p12new.txt` |

New wrong readings, old tests vs new tests (/237, `WORK/p12/dout/TRAP_p12old.txt` vs `TRAP_p12new.txt`):

| wrong reading | old tests | new tests | failed checks (new) |
|---|---|---|---|
| UNIT10 (fixed 10 Wh / 1000 mill-cents) | 237 | 147 | 18 |
| CODESHIP (shipped code tables) | 237 | 137 | 20 |
| ADDmiss (missing adder read as 750) | 237 | 202 | 7 |
| GAPdrop (offer with a missing row dropped) | 237 | 222 | 3 |
| LEDwithin (allowance drawn inside the event) | 237 | 202 | 7 |
| ALWge (equal need excluded) | 237 | 197 | 8 |
| CLAIMlt (claims equal to F apportioned) | 237 | 232 | 1 |
| a12 agent program | 173 | 173 | 16 (wide, 120 s limit) |
| a11 agent program | 173 | 173 | 16 (wide) |

## QC_RULINGS rows

No finding of this round sits on IN-15, IN-16, TS-13, TS-19, TS-20, TS-26, AL-28, JD-7 or JD-15, so no new ruling row. Re-checks done for the touched items (for the master's record only):
- TS-26 | tie_decisions_match now on the generated tie extract, its _hard twin on hidden H1, wide_k twins on wide extracts | QC: n/a | PASS | three different extracts, no double payment (STACKING_CHECK by-hand verdict).
- JD-7 | R3 and R12 split from one criterion | QC: n/a | PASS | the oracle prints `check R3 ok` and `check R12 ok` (solve.sh:434, :436).
- JD-15 | R3 and R12 each with an own label | QC: n/a | PASS | names `r3_checks_composed_rate_credit_on_own_extract`, `r12_checks_composed_rate_cap_binding_on_own_extract` (judge.toml:39, :156).
- AL-28 | negative_external_dependency_or_network narrowed | QC: n/a | PASS | negatives group sum unchanged (STACKING_CHECK).

## Lessons for the master

- A tie or empty-list check on the shipped data passes a constant: point list checks at an extract where the list is non-empty (TS-25).
- An AL-27 fix is proven only by a wrong-reading flag in the reference plus a hidden-seed guard that keeps a seed only when that flag changes a graded family; the old tests scored all 7 new wrong readings 237/237.
- Drawn codes must fit the fixed-width fields (pools/feeder code column is 4 chars).
- Playbook JD-5 ("keep the total weight") and JD-13 (important = 3) clash on a split; the master ruling chose JD-13 (24 -> 27).
- Judge names are capped at 64 chars (precheck J3); shorten split names before precheck.
