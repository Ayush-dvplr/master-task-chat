# P12 v3 r6 recheck and fix: match-replay-desync-audit (board c45716e)

QC report: `QC/reports/match-replay-desync-audit/v6.md` (board a9d62f3, kit 976c1666). Live kit now `5574d77eb9f22c207ba05fd8f9ac31d42ba45271` (IN-17 new at `01_Instruction_QC.md:47`; IN-16, TS-16, TS-23, CL-4 wording read live, unchanged in substance). Tree sha at issue 765e3d04ab89 (verified); after **9c687037cd93**.
Always 13: `diff -rq` BUNDLE vs `QC/copies/a9d62f3/match-replay-desync-audit` printed nothing; every cited line read as quoted. No NOISE row.
Session rename: `name_session.py c45716e` printed `codex: no match` / `opencode: ['ses_e8d48bb6dffeAqIOiQgfJLC0bQ']`; the title itself was not echoed back. Not retried.

## Findings

| ID | label | rule quote (live kit) | evidence quote (bundle, before) | decision | playbook row | effect per lever (L1 / L3 / L4) | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| F1 IN-16 (v6.md:35, 95-100) | REAL | `01_Instruction_QC.md:46` "must show all three parts ... something graded depends on the answer ... the contract admits two readings ... nothing in any file the agent can read picks between them" | `engine-rules.md:97` "A cancelled entry contributes nothing to any total."; `engine-rules.md:79` "Every amount a capture decodes is either settled, dropped or held as surplus"; tests `_fit_plan` L873 `decoded_amount = sum(row["amount"] for row in rows)`, L972 `plan["entry_total"] = len(rows)` count cancelled pairs (feeds entry_total, decoded_total, decoded_amount_total, conservation_residual) | FIX: oracle reading kept. New general clause `report-schema.md:13-15` "The decoded fields, `entry_total`, `decoded_total` and `decoded_amount_total`, count every entry the captures decode, before unit identity, live windows and cancellation are applied."; `engine-rules.md:97` narrowed to "contribute nothing to any settled total"; `engine-rules.md:79` lists the cancelled pair (see Deviations). Same bytes in tests STATIC_NOTE_TEXT (notes match True; emit byte-identical to environment/data) | IN-16 DO "one settling clause in the governing file, written for the general case" | none / none / none (all variants identical before and after) | none needed | environment/data/report-schema.md, environment/data/engine-rules.md, tests/test_output.py (STATIC_NOTE_TEXT) |
| F2 TS-16 (v6.md:37, 110-114) | REAL | `03_Tests_QC.md:47` "Anti-cheat negatives must fire on the cheat and ONLY on the cheat. Ask for each: could an honest solution trip this?" | tests L2778-2785 (before) `root = "/" + "app" + "/out/"` ... `if root + leaf in source: return` for the very paths instruction.md:7 names | FIX: behavioural trigger. `tests/test_output.py:2781` `_decoy` + `:2794` negative: plants decoy reports with sentinel rationals `%d/9973` at /app/out (originals moved aside and restored in `finally`), runs the delivered program on a fresh staged set, fires only when a sentinel appears in the fresh report directory. Docstring and criterion `:3104` "fires when a fresh run copies figures planted in the reports under /app/out." Weight -5 unchanged | TS-16 DO "narrow the trigger to the cheat only" (live form built, so no deletion) | none on all (negatives 0 on every variant) | none | tests/test_output.py |
| F3 CL-4 (v6.md:39, 128-129) | REAL, REBUT after fix | `Final_checklist.md:491` "One wrong fact should cost about one fact's worth of reward ... An instruction that states out loud that only an exact match counts has set that bar deliberately." | reading-B variant (decoded totals skip cancelled pairs) 37/172 = 0.215; instruction.md:13 (before) "each output document is graded whole on fresh inputs" (no exact-match words) | FIX + REBUT: after F1 reading B is a genuine wrong reading; `instruction.md:13` now "Each report is graded whole on fresh capture sets, and only an exact match counts". `_compare` and `_settled_view` untouched. REBUT in WORK/QC_DEFENCE.md D11 with the one-fact-wrong rows below | CL-4 DO "confirm the instruction states exact whole-document match and REBUT quoting FC:491 with the one-fact-wrong score" | none / none / none | none | instruction.md |
| N1 IN-17 M-2 | REAL | `01_Instruction_QC.md:47` "the sentence announces something the agent was meant to find ... the shipped input ALREADY establishes that thing" | instruction.md:3 "Two captures carry a flag word of zero and can be read straight off the wire"; input `replay-format.md:128` "Two captures in the shipped set carry a flag word of zero ... they can be read directly." | DELETE | IN-17 DO delete | none | none | instruction.md |
| N2 IN-17 M-3 | REAL | same | instruction.md:3 "Eleven numeric quantities ... appear in no shipped file ... ordered so that each figure is fixed by the quantities pinned by the figures ahead of it together with one further quantity"; input `calibration.md:3-8` states count and order | DELETE count and order; neutral requirement kept: "Some numeric quantities that the serializer and the engine both depend on are withheld. For each one the notes publish the set of values it may take, and the calibration notes publish control figures."; L7 "recover the withheld quantities" (L7/L9 deliverables need the noun) | IN-17 DO delete, keep requirement part (AL-1) | none | none | instruction.md |
| N3 IN-17 M-4 | REAL | same | instruction.md:5 "Unit identity is not what a capture recorded: the roster carries openings, closings, successions and merges"; input `roster-register.csv` + `engine-rules.md:9-30` | DELETE announcement; kept "The word an entry names is chased to the identity in force at that entry's tick before anything is counted." | IN-17 DO | none | none | instruction.md |
| N4 IN-17 M-5 | REAL | same | instruction.md:5 "Charter stocks stand in a coupled relation ... solved for rather than approached by repeated substitution"; input `engine-rules.md:49-55` "a unique stable assignment of stocks exists" | DELETE | IN-17 DO | none (var_* unchanged) | none | instruction.md |
| N5 IN-17 M-1 | REAL | same | instruction.md:3 "in no particular order of application"; input: application order fixed operationally by `calibration.md:81-133` control recipes and `replay-format.md:15` "in bit order" | DELETE phrase | IN-17 DO | none | none | instruction.md |
| N6 IN-17 M-7 | REAL | same | instruction.md:5 "exactly one set drawn from the bench candidates meets the upkeep target exactly"; input `engine-rules.md:74` "Exactly one set drawn from the bench candidates carries a settled upkeep that meets the target exactly." | DELETE | IN-17 DO | none | none | instruction.md |
| N7 IN-17 M-6 | REAL | same | instruction.md:5 "a binary floating-point pipeline will not reproduce the settled charter stocks"; requirement already at instruction.md:11 "rather than binary floating point" | DELETE clause; kept "Work the whole settlement in exact rational arithmetic." | IN-17 DO | none | none | instruction.md |
| W1 TS-23 / A3 (v6.md:41, 116) | REAL (warn) | `03_Tests_QC.md:62` "at least 10 checks (fail), at most 35 (warn)" | 46 checks (`tests/test_output.py` registrations L3116-3161); tests_qc `WARN [A3] 46 checks; cap is 35 (warn)` | KEEP (Ayush 24 Oct 12:50, no cap) | TS-23 KEEP with count and kit line | none | none | none (OUT/PL_NOTE.md) |

Totals: REAL 11, FALSE_POSITIVE 0, UNSURE 0; fixed 10 (F1, F2, F3, N1-N7), kept 1 (W1).

## One-fact-wrong rows (tests channel, earned of P = 172; WORK/single_lever.py, logs WORK/trap/run_before_v3r6.log, run_after_v3r6.log)

| case (variant) | lever | before | after | one-fact-wrong score |
|---|---|---|---|---|
| oracle | - | 172 | 172 | 1.000 |
| one ctrl note rule (mut_zero / carry / stepped / index) | L1 | 169 each | 169 each | 0.983 |
| all four ctrl rules (var_ctrl_all_old) | L1 | 160 | 160 | 0.930 |
| allowance per entry (var_perentry) | L3 | 97 | 97 | 0.564 |
| allowance from opening charter (var_opening) | L3 | 102 | 102 | 0.593 |
| cancelled entry draws (var_cancelled_draw) | L3 | 97 | 97 | 0.564 |
| allowance never renewed (var_norenew) | L4 | 97 | 97 | 0.564 |
| renewal strictly before (var_renew_strict) | L4 | 162 | 162 | 0.942 |
| precedence (var_precedence) | - | 161 | 161 | 0.936 |
| tie-break (var_tiebreak) | - | 162 | 162 | 0.942 |
| reversal latest entry (var_lifo) | - | 157 | 157 | 0.913 |
| constants carried (var_carry_eleven) | - | 12 | 12 | 0.070 |
| decoded totals skip cancelled pairs (var_decoded_live, CL-4 reading B) | - | 37 | 37 | 0.215 |

Reading B touches entry_total, decoded_total, decoded_amount_total and conservation_residual, which sit in three reports (scenario_visible, perf_report, data_quality) of every graded set, so whole-report exact grading fails those reports everywhere. After F1 that reading contradicts `report-schema.md:13-15`, and instruction.md:13 now says out loud that only an exact match counts: FC:491 "An instruction that states out loud that only an exact match counts has set that bar deliberately."

## Trap survival (loss = points lost by the lever's variants)

| lever | before loss | after loss | ratio | verdict |
|---|---|---|---|---|
| L1 green control (mut_* / var_ctrl_all_old) | 3 / 12 | 3 / 12 | 100% | PASS |
| L3 running charter allowance (var_perentry / var_opening / var_cancelled_draw) | 75 / 70 / 75 | 75 / 70 / 75 | 100% | PASS |
| L4 renewal at window openings (var_norenew / var_renew_strict) | 75 / 10 | 75 / 10 | 100% | PASS |

Negatives fired on no variant before or after. Oracle 172/172 locally on the AFTER tests.

## F2 local evidence (WORK/trap/f2, driver neg_only.py with the /app/out root redirected to scratch)

| program | new negative | hardcoded / rebinds | /app/out restored byte for byte |
|---|---|---|---|
| oracle solve.py | no fire | no fire | yes |
| oracle + unused constants naming `/app/out/scenario_visible.json` etc. (old source-match form would fire) | no fire | no fire | yes |
| program that copies reports from its own folder (/app/out) into the report directory | FIRES | no fire | yes |

## Side effects

| id (FIX_SIDE_EFFECTS row) | check | result |
|---|---|---|
| TS-14 (TS-16 fix, rate 0.40) | negative name, docstring, criterion description, sign and polarity match the body | PASS: name `reads_supplied_answer_data_at_runtime`, body reads the planted /app/out reports; description states the trigger; weight -5; returns True only on copying |
| TS-15 (TS-16 fix) | negative cannot fire when the program is absent or crashes | PASS: `_stage` raises without a program; non-zero exit raises before the sentinel scan |
| AL-27 (IN-16 fix, rate 0.17) | new clause has fixture coverage | PASS: var_decoded_live loses 135 of 172 on every set that carries cancelled pairs |
| AL-28 | one act at most -5 | PASS: copying planted reports is a different act from source literals (hardcoded), filename dependence, naming /tests or /logs/verifier (rebinds), judge R6 writes outside /app/out, judge R10 false claim |
| TS-26 / TS-13 / TS-23 | no duplicate, one property, count | PASS: stacking_check groups unchanged (7 hand-checked groups, different hidden inputs); 46 checks unchanged |
| DS-22 | TRUTH and WORK docs match measured rows | PASS: TRUTH sha line re-written by script (solve.py unchanged); QC_DEFENCE D11 and LEVERS table carry the measured rows above |
| IN-16 after IN-17 deletions (AL-1) | deletions open no gap | PASS: each deleted fact is stated in the shipped input cited in its row; requirement nouns kept in L3/L5/L7 |
| W9 | literal reading of every new sentence | PASS (WORK/W9_SELFTEST.md r6 rows): no literal reading loses oracle points |

Gates: xref_check before `33 entries, 0 findings`, after `38 entries, 0 findings`; precheck last line `PRECHECK CLEAN` (0 IN17-PHRASE warns; A3 46 checks warn kept); kit structure_qc / instruction_qc / tests_qc / judge_qc exit 0,0,0,0 (tests_qc VERDICT WARN for A3 only; OUT/kit_*.txt); stacking_check PASS after hand correction (OUT/STACKING_CHECK.md); no `__pycache__`; reward.toml 0.5/172 and 0.5/17 unchanged.

## Docker block

Copies by live kit `exe_copy.py` (plain and `--owner-only`) in `/tmp/opencode-logs/match-replay-desync-audit-p12v3r6-20261025T164537-9df7`; warm verifier image first (warm rc=0), one nohup chain ending `ALL_DONE Sun Oct 25 16:48:23 IST 2026`. Chain, copy notes and log: `docker_block/chain.sh`, `docker_block/copy_*.txt`, `docker_block/runs.log`.

| run | reward |
|---|---|
| oracle-1 / -2 / -3 | 1.0 / 1.0 / 1.0 |
| owner-only-1 | 1.0 |
| nop-1 | 0.0 |

oracle-1 reward-details: `negative_reads_supplied_answer_data_at_runtime` value 0.0 (the new decoy negative did not fire on the oracle inside the verifier).

## Noise keeps

None: the QC copy a9d62f3 is byte-identical to the pre-fix bundle.

## QC_RULINGS rows

- IN-16 | rule 01:46 three parts | our design: decoded fields count every decoded entry (cancelled pairs included), settled totals exclude them | QC verdict FAIL (v6.md:35) | our label REAL | reason: engine-rules "any total" vs tests counting cancelled pairs in decoded totals; settled by one general clause in report-schema.md (emberforge v2 form).
- AL-28 | one act at most -5 | our design: decoy-copy negative -5, distinct from hardcode/filename/rebinds/judge R6/R10 | QC verdict PASS in v6 (acts table) | our label n/a (re-checked after F2) | reason: behavioural trigger names a different act.
- IN-15, TS-13, TS-19, TS-20, TS-26, JD-7, JD-15: no finding in v6.md; nothing to add.

## Deviations from master directions

- F1: `engine-rules.md:79-81` also edited ("is settled, dropped, held as surplus beyond an allowance, or carried by a cancelled entry or the reversal that cancels it"). Reason: the old "either settled, dropped or held as surplus" partition contradicts the new schema clause and the oracle (the residual includes cancelled pairs), so narrowing L97 alone would leave a second reading.
- F1: L97 narrowing also names the reversal ("A cancelled entry, and the reversal that cancels it, contribute nothing to any settled total") instead of keeping the second sentence, so both halves of the old pair say "settled".
- N-scan side note: instruction.md:7 "has to finish within two minutes" became "has to finish within 120 seconds": precheck's IN17-PHRASE count regex flagged "two minutes"; the requirement (120 s launch limit) is unchanged.

## Lessons for the master

- IN-16 settlement of a "total" word needs every sentence that partitions the same amount checked, not only the one QC quoted (engine-rules L79 partition also contradicted) | no change: playbook IN-16 DO already says governing file; add "grep the partition sentence" only if it recurs.
- IN-17 precheck regex flags numeric requirement words like "two minutes" | template_change: master_chat_tasks/tools/precheck.sh IN17-PHRASE regex (exempt time units).
- Behavioural decoy negative (plant sentinel rationals, restore in finally) is a reusable TS-16 form for "reads graded reports" negatives | no change: record in QC_FIX_PLAYBOOK_v2 TS-16 row examples when next edited.
