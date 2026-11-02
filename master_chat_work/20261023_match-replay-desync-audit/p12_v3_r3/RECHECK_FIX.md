# RECHECK_FIX: match-replay-desync-audit (P12 v3 r3, board 878a0e4)

QC v3 (board fe8dec6, kit 976c166611e555e2ba20eb8d81bed279cee1ea30): 4 fail, 1 minor, 1 warn.
Session rename: `name_session.py 878a0e4` at 18:18 IST listed opencode `ses_e920b0237ffeMYXqDE0nownLxJ`.
Tree sha at start 666226360826 (matches the master's figure). xref_check before: 27 entries, 0 findings.

## Phase 1 recheck

Levers (WORK/LEVERS.md): L1 green control (amplifier), L3 running charter allowance, L4 renewal at live-window openings.

| ID | label | rule quote (live kit) | evidence quote (bundle) | decision | playbook row | effect per lever | files changed |
|---|---|---|---|---|---|---|---|
| F1 DS-20 | REAL | 02_Data_Solution_QC.md:68 "Any divergence between stated rule and oracle behaviour is a fail, even when no current test would catch it." | calibration.md:85-87 "A payload that holds the reserved byte once on its own, or that does not come out at twelve bytes, is written as twenty four zero digits." vs old solve.py:268-273 (wrote `none`); calibration.md:109-111 carry "0 and 0 ... for an entry after a `none`" vs old solve.py:321-323 (kept last settled carry); calibration.md:118-119 "a `none` entry counting as a stored 0" vs old solve.py:352-358 (every later tick none); calibration.md:122 index "taken against the length of the list" vs old solve.py:367 (dropped). Verifier reference already follows the notes (test_output.py:1025-1028, 1091-1095, 1103-1104, 1113). Candidate 200 CTRL-C figure: rule 1502353130b5, old oracle fa89167d0052 | FIX the oracle (contract unchanged); add four hidden damage corpora that trigger each rule | DS-20 DO: fix oracle, NEVER change contract | L1 none, L3 none, L4 none (decode-side only; shipped outputs byte-identical) | solution/solve.py, tests/test_output.py (4 new tests) |
| F2 DS-22 | REAL | 02_Data_Solution_QC.md:78 "Fail, and name the section and the contradiction." | TRUTH.md:25-27 "The chained mask reads the previous entry's settled tick and amount ... a single missed entry desynchronises every entry after it" vs calibration.md:109-111 and encoder test_output.py:594-604 (stored tick and amount, 0 and 0 after none) | FIX wording in TRUTH.md and the solve.py comment; TRUTH regenerated last by script | DS-22 DO: rewrite TRUTH by script | none on every lever | solution/TRUTH.md, solution/solve.py (comment) |
| F3 JD-7 R7/R8/R9 | REAL | 04_Judge_QC.md:76 "Every criterion must be satisfied (or, for negatives, avoided) by the shipped oracle in solution/." | judge.toml:92 R7 "The agent constructs its own input in which two settled entries of one charter together exceed that charter's allowance ..."; :105 R8; :118 R9; solve.sh:1-60 never builds or runs such an input | FIX the oracle: solve.sh self-check stage builds three small inputs, runs /app/out/optimize.py, prints `check R7 ok` / `check R8 ok` / `check R9 ok` | JD-7 DO: fix oracle to meet criterion | L1 none, L3 none, L4 none (conduct criteria kept; no test change) | solution/solve.sh |
| F4 CL-4 | REAL | 05_Alignment_Integrity_QC.md:77 "Count the independently discoverable facts the deliverable carries (per field, per setting, per row), then read how the tests compare them." | test_output.py:24 HELD_OUT_HEFT = 40; trap tests :2396-2453 compare whole scenario/perf/quality documents, so one settlement slip (cancelled draw) loses all 12 trap tests: 20/160 | FIX by partition (QC option 1): trap and damage corpora drawn without HELD_OUT_HEFT (heft 1), guarded by `_check_unbound` (every charter's live amounts, by owner and by opening charter, stay under its allowance; worst ratio 0.341), so no allowance reading can change a trap output; trap_flipped / trap_warded compare the quality report with the retired and off-window drop counts summed (`_dropped_view`), so the precedence rule no longer cascades into them; the tie-break mutant corpus is also drawn light so its separating case survives; allowance, renewal and reversal keep their own general_* / mutation tests | CL-4 (partition, no exact-match sentence) | L1 none, L3 easier (wrong reading no longer loses trap points), L4 easier (same); approved effect | tests/test_output.py |
| M1 JD-5 R11 | REAL | 04_Judge_QC.md:71 "If a judge would need to check two separate things, split it." | judge.toml:144 R11 names three observables | FIX: master wording, weight 3 | JD-5 DO: reword | none on every lever | tests/judge.toml |
| W1 TS-23 / A3 | REAL (warn), KEEP | 03_Tests_QC.md:62 "at most 35 (warn)" | 42 checks at QC time, 46 after F1 (test_output.py registration block) | KEEP: no cap (Ayush 24 Oct 12:50); recorded in PL_NOTE.md | TS-23 KEEP warn | none | none |

## Probe diagnosis (Phase 0, probe run 1, tests 75/160)

Full table: `WORK/PROBE_DIAGNOSIS.md`. The probe program (`WORK/probe/optimize.py`) lost 17 tests, 85 points:

| cause | tests | points |
|---|---|---|
| decode slip | 0 | 0 |
| settlement slip | 11 (trap woven, padded, shadowed seat a unit whose only entries were cancelled; trap drifted, flipped, spun and 5 general/mutation tests fail CTRL-J: its cadence over surviving units, optimize.py:620-634, 782-784) | 55 |
| both | 0 | 0 |
| runtime only (keeps every calibration branch in single-transform corpora, killed at LAUNCH_SECONDS 120; correct once given the true quantities) | 6 (trap sealed, chained, stepped, echoed, aliased, warded) | 30 |

The probe lost 0 points to the allowance cascade QC describes in F4. Its 4 negatives did not fire.

## Phase 2 changes

- F1: `solution/solve.py` follows calibration.md on all four rules: a lone reserved byte or a payload that is not twelve bytes reads as zeros (:268-274), the chain carry is 0 and 0 after a `none` (:322-324), a `none` counts as a stored 0 in the stepped series (:353), the unit index is taken modulo the table length (:365). Shipped outputs of old and new oracle: `diff -r` identical (9 files). New hidden tweak `("damage", rule)` in `tests/test_output.py` (DAMAGE_FLAGS :108, `_plant_damage` :496, `_check_damage` :520 G12 assert that every planted entry decodes as planned through the reference `_peel`, ghosts excluded from `walk_entries`, encoder plants the broken payload / lap index); four tests at weight 3 (:2571-2590): trap_zeroed_payload_inverse, trap_carry_reset_inverse, trap_stepped_gap_inverse, trap_index_lap_inverse. `WORK/RULE_COVERAGE.md`: each one-rule mutant fails exactly its own test (169/172); the old oracle fails all four; rules uncovered 0.
- F2: TRUTH.md chained-mask bullet and the solve.py comment now say "the stored tick and amount of the entry before it, 0 and 0 for the first entry and after a none"; the desynchronise claim is gone.
- F3: `solution/solve.sh` keeps lines 1-60 and appends a self-check stage (python heredoc from :67) that builds three one-capture inputs under `/app/out/selfcheck` (removed afterwards), runs `/app/out/optimize.py` on each, checks every calibration figure, then the settled amount: R7 two aurochs draws 70 + 50 in one window against allowance 100 -> `100/1`; R8 90 + 60 then 80 at the next window's first tick -> `180/1`; R9 a reversal cancels an 80 draw -> settled total `60/1`. Prints `check R7 ok`, `check R8 ok`, `check R9 ok`. Graded reports byte-identical to a run without the stage. var_perentry fails R7, var_norenew R8, var_cancelled_draw R9. R7-R9 wording unchanged. `WORK/JUDGE_MAP.md` written.
- F4: `_replay_draw` draws single-transform and damaged sets at heft 1 and asserts `_check_unbound` (:481); the tie-break mutant is drawn light too (`light`), since at heft 40 its binding cap absorbed the tie-break difference and no test separated the reading; `_dropped_view` sums the two drop counts for trap_flipped / trap_warded. Whole-document compares kept.
- M1: judge.toml R11 = "The agent leaves a /app/out/optimize.py that a Python reviewer would accept as maintainable, judged on its names, function structure and error handling." weight 3; J4 exactly 1 code-quality criterion.
- Totals: 46 checks, 42 positive P = 172, 4 negatives -20; `tests/reward.toml` test_output 0.0029069767441860465 (0.5/172). No test_weights.json in this bundle. TRUTH.md last, by script (counts, trap scale, damage tests, judge paragraph, one-fact-wrong section, four pitfalls, solve_py_sha256 b18c6baed8a9...). DESIGN.md, LEVERS.md, QC_DEFENCE.md, XREF.md kept in step.
- Generator byte-diff (Always 11): `test_output.py emit` reproduces environment/data identically; `notes` mode `all embedded notes match shipped: True`.

## Grammar check

`WORK/grammar_check.py` on shipped data and the new oracle reports: RESULT 11/11, one hit each (9, 23, 214, 11, 5, 13, 7, 3, 6, 4, 17). Shipped figures unchanged.

## Lever cost and one fact wrong (tests only, AFTER, P = 172)

Full table: `WORK/COST_TABLE.md`. Overall = 0.5 tests share + 0.5 rubric share.

| lever | wrong reading | tests lost / P | share |
|---|---|---|---|
| L3 | per-entry cap / draw on opening charter / cancelled entry draws | 75 / 172 each | 0.436 |
| L4 | never renewed | 75 / 172 | 0.436 |
| L4 | renewal strict `<` | 10 / 172 | 0.058 |
| L1 | "controls green so settlement right" (amplifier, no edit of its own) | 0 / 172 | 0.000 |
| CTRL-C/G/H family (one rule) | each of zero fill, carry reset, none as stored 0, index modulo | 3 / 172 each | 0.017 |
| CTRL-C/G/H family (all four) | old oracle | 12 / 172 | 0.070 |
| constants | carried shipped values (var_carry_eleven) | 160 / 172 | 0.930 |
| reversal order | LIFO | 171 / 172 | 0.994 |

One fact wrong (CL-4):

| case | tests earned / 172 | overall at rubric 90 | overall at rubric 17.65 |
|---|---|---|---|
| oracle | 172 | 95.00 | 58.82 |
| one allowance rule wrong (perentry / norenew / opening / cancelled draw) | 97 | 73.20 | 37.02 |
| renewal strict `<` | 162 | 92.09 | 55.92 |
| retired / off-window precedence swapped | 161 | 91.80 | 55.63 |
| walk tie-break swapped | 167 | 93.55 | 57.37 |
| reversal LIFO | 1 | 45.29 | 9.12 |
| one CTRL rule wrong | 169 | 94.13 | 57.95 |

Before F4 (P 160): one allowance rule wrong 20/160, precedence 139, strict 140, tie-break 155, LIFO 1. An allowance slip now costs the fifteen heavy general and mutation tests and no trap test.
G10: L1 FAIL (amplifier, unchanged); L3 and L4 single-wrong rows now 73.20 at rubric 90, above the 70 line; this is the approved F4 effect and no lever or data was added.

Probe program after (probe run 1 `optimize.py` on the AFTER tests, `WORK/trap/scores_after_v3r3/probe_agent.txt`): 75/172 = 43.60 % tests; overall 30.63 at rubric 17.65 and 66.80 at rubric 90. It loses the twelve trap and four damage tests (exit -9 at 120 s, its calibration keeps every surviving branch) and five general/mutation tests (calibration failed at CTRL-J). Gate tests < 100 and overall < 70: PASS. Kill rule (probe tests >= 95): not hit.

## Side effects

| fix | side-effect id | recheck | result |
|---|---|---|---|
| F1 | DS-22 (TRUTH matches oracle) | TRUTH stages 3 and 4, pitfalls and sha regenerated by script | PASS |
| F1 | TS-17 / AL-18 / AL-19 (shipped data and figures) | generator `emit` byte-identical; oracle shipped outputs identical old vs new; grammar 11/11 | PASS |
| F1 | NEW-CHECK hygiene (Always 12) | TS-13 one rule per damage test, own corpus; TS-25 whole-document compare, not an absence check; TS-14 positive names, weight 3; TS-16 negatives unchanged; TS-26 no two tests on one observable of one corpus; TS-17 exact string compare | PASS |
| F1 | G11 / G12 | RULE_COVERAGE 4 rows, each mutant drops its own test; `_check_damage` asserts every planted entry decodes as planned | PASS |
| F3 | JD-15 (FIX_SIDE_EFFECTS.md:18) | R7-R9 still trajectory conduct criteria, labels unchanged; the self-check writes only under /app/out and removes it, so R6 (-3, writes outside /app/out) stays 0 for the oracle | PASS |
| F3 | graded outputs | reports with and without the stage byte-identical; Docker oracle 1.0 | PASS |
| F4 | CL-4 / AL-27 | `_check_unbound` asserts every trap and damage corpus stays under each allowance (worst 0.341); each settlement reading still loses at least one test (Trap survival) | PASS |
| F4 | TS-13 (trap flipped / warded view) | `_dropped_view` folds only the retired / off-window split; every other quality field still compared | PASS |
| M1 | JD-2, JD-7, JD-9, JD-15, IN-8 (FIX_SIDE_EFFECTS.md:8) | one judgement in the master's wording; oracle solve.py meets it (named functions, ValueError when no candidate reproduces); weight 3; state_change target; instruction needs no code-quality line (deliverable at instruction.md:7) | PASS |
| all | reward.toml / TRUTH totals / xref | 0.5/172; TRUTH 172 and 46 checks; xref_check 28 entries, 0 findings | PASS |

## Trap survival

Before = P12 v3 r2 AFTER tests (P 160; QC v3.md:268 for precedence, strict, tie-break, LIFO). After = this round (P 172).

| variant | before loss of P | after loss of P | verdict |
|---|---|---|---|
| var_perentry (L3) | 140/160 = 0.875 | 75/172 = 0.436 | PASS (approved F4 effect; 15 tests still separate it) |
| var_opening (L3) | 0.875 | 0.436 | PASS (same) |
| var_cancelled_draw (L3) | 0.875 | 0.436 | PASS (same) |
| var_norenew (L4) | 0.875 | 0.436 | PASS (same) |
| var_renew_strict (L4) | 20/160 = 0.125 | 10/172 = 0.058 | PASS (general_scenario_latency, mutation_window_split) |
| var_precedence | 21/160 = 0.131 | 11/172 = 0.064 | PASS (instance_data_quality, general_charter_cap_surplus, general_dead_window) |
| var_tiebreak | 5/160 (trap_chained only) | 5/172 (general_reversal_tiebreak) | PASS; the separating case moved: without the light tie-break corpus no test would separate it |
| var_lifo | 159/160 | 171/172 | PASS |
| var_carry_eleven | 154/160 | 160/172 | PASS |
| one CTRL rule (x4) | 0 (ungraded) | 3/172 each | PASS (new) |

No separating hidden case disappeared.

## QC_RULINGS rows

| rule | bundle | finding | ruling |
|---|---|---|---|
| DS-20 | match-replay-desync-audit v3:F1 | oracle broke four calibration.md decode rules no shipped corpus reaches | FAIL; fix the oracle and add a hidden corpus per rule |
| DS-22 | match-replay-desync-audit v3:F2 | TRUTH described the chain mask from the old oracle, not the notes | FAIL |
| JD-7 | match-replay-desync-audit v3:F3 | "agent constructs its own input" criteria the oracle never shows | FAIL; an oracle self-check stage that builds and checks the inputs meets them |
| CL-4 | match-replay-desync-audit v3:F4 | one settlement rule wrong lost every whole-document trap test (20/160) | FAIL; partition trap corpora under the allowance |
| JD-5 | match-replay-desync-audit v3:M1 | code-quality criterion with three observables | MINOR; one reviewer judgement |
| TS-23 | match-replay-desync-audit v3:W1 | 42 checks over 35 | WARN; kept (no cap) |

## Docker block

Copies by live kit `exe_copy.py` (plain, `--owner-only`, `--stub`) in `/tmp/opencode-logs/match-replay-desync-audit-p12v3r3-20261024T193126-baa8`; one nohup chain, warm verifier image first, ends `ALL_DONE Sat Oct 24 19:35:10 IST 2026`. Chain and log: `docker_block/chain.sh`, `docker_block/runs.log`.

| run | reward |
|---|---|
| warm verifier image | rc 0 |
| oracle-1 | 1.000 (agent log prints `check R7 ok`, `check R8 ok`, `check R9 ok`) |
| oracle-2 | 1.000 |
| oracle-3 | 1.000 |
| owner-only-1 | 1.000 |
| nop-1 | 0.000 |
| stub-1 | 0.0058 (format_program_delivered only, 1/172 of the tests channel) |

## Checks after the last edit

Last bundle edit: TRUTH.md (P2.6, by script). After it: xref_check 28 entries, 0 findings; `precheck.sh` PRECHECK CLEAN (A3 warn 46 checks only, AL-27 note 4 rule rows); live kit `structure_qc.py` exit 0; `stacking_check.py` exit 0 (OUT/STACKING_CHECK.md); Docker block above; `find BUNDLE -name __pycache__` empty; tree sha `7b0bc6233c65`.

## Deviations from master directions

- F4: the direction offered "under every allowance" or "decode-only fields". I used the first for all twelve trap and four damage corpora (heft 1 plus the `_check_unbound` generator assert) and added two follow-ups not named in the direction: (a) trap_flipped and trap_warded compare the quality report with the retired and off-window counts summed (`_dropped_view`), because the precedence swap still cascaded into those two whole-document traps; (b) the tie-break mutant corpus is drawn light, because at heft 40 its binding cap absorbed the tie-break difference and after F4 no test separated that reading (before F4 only trap_chained did, by chance).
- Not done, flagged instead: an allowance slip still costs the fifteen heavy general and mutation tests, several of them not about allowances (empty_charter, dead_window, cadence_partition). QC's F4 text asked that such an error cost "only the cap/window/reversal tests"; the master direction scoped the change to trap_*, so I stopped there. Lightening those corpora too would remove most allowance separation and push the G10 rows further over 70.
- G10: the L3/L4 single-wrong rows are now 73.20 at rubric 90 (over 70). This is the approved F4 effect; no lever, data or test was added to pull it back.

## Lessons for the master

- JD-5 came from the playbook's own code-quality template listing three observables | template_change: master_chat_tasks/knowledge/QC_FIX_PLAYBOOK_v2.md:46 replace the J4 example with the single-judgement R11 wording used here
- CL-4 has no playbook row; the fix that worked is shipped-scale amounts for single-transform corpora plus a generator assert that no allowance binds under any reading | template_change: master_chat_tasks/knowledge/QC_FIX_PLAYBOOK_v2.md:50 add a CL-4 row after JD-5
- Lowering heft removed the only test separating the walk tie-break (a binding cap absorbed it); re-run every one-rule variant after any partition | template_change: master_chat_tasks/knowledge/LEVER_RULES_v1.md:50 add the re-run step to section 3
- An oracle self-check stage in solve.sh that builds its own inputs meets "agent constructs its own input" criteria without touching graded outputs | no change: LEVER_RULES J2 already says this
- The probe's biggest loss was runtime (calibration keeping every surviving branch, killed at 120 s), not decode or settlement | no change: contract allows several survivors and the time limit is stated
