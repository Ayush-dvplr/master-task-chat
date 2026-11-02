# FIX_REPORT 8826f3a caldermoor-commitment-closure (P12 v3 r1)

SOURCE `Tasks_INPUT/caldermoor-commitment-closure` tree sha d36afaa2ebc6 (matches issue). Kit HEAD 976c166611e555e2ba20eb8d81bed279cee1ea30. BUNDLE `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/caldermoor-commitment-closure`, final tree sha cd89855ae882. Fix from the v0 real-run read (READ.md section 1); no QC report yet.

## Fix table

| row | kit rule (id, file:line, wording) | bundle evidence | change | playbook row | effect on A / B | files changed |
|---|---|---|---|---|---|---|
| F1 | AL-2, 05_Alignment_Integrity_QC.md:22 "Everything promised is graded. For each instruction requirement: point to the test (or criterion) that checks it."; AL-18 :64 "No stale references"; IN-8 01_Instruction_QC.md:38 | v0 instruction.md:86-138 asked for twelve what-if figures and seven units A-G in the final message; solve.py printed none of them; 81 of 95 judge points paid for them (J1) | deleted v0 lines 86-139; reworded v0 140-142 to "Every rule that decides the closure is inside the extract ... settles any part of it."; grep of instruction.md and environment/data/*.md: no pointer to the cut figures or units left ("figure" in data docs is the audit-figure sense, output-contract.md:62 etc.) | QC_FIX_PLAYBOOK_v2.md:29 (remove the request, not "states figure X") + LEVER_RULES J1 | none / none (levers sit in tests; instruction rule pointers kept) | instruction.md (144 -> 90 lines) |
| F2 | JD-5 04_Judge_QC.md:71 "Each criterion names ONE observable behaviour"; JD-8 :77 "NO OVERLAP WITH TESTS"; JD-18 :99 "At least one criterion judges the quality of the code the agent writes."; judge_qc G2 (batched), J6 (annotation keys), J7 (type = category), precheck J3/J4 | v0 judge.toml 28 criteria, +95/-9, mode individual, extra annotation keys on every criterion, no honesty negative, R26+R28 split code quality | rebuilt to 11 criteria, ids R1..R11 sequential, batched header, annotations only mode/type/evaluation_target/importance: R1 staging 3, R2 stdlib 3, R3 J4 code quality 3, R4 C1 3, R5 C2 3, R6 C3 3, R7 J6 lists files under /app/out 1, R8 (v0 R23) -5, R9 (v0 R24) -3, R10 (v0 R25) -1, R11 C4 honesty -3. WORK/JUDGE_MAP.md written | :45 JD-18 (one concrete J4), :49 JD-5, :50 JD-8 (delete, renumber), :41 JD-7 | none / none in tests; R4 and R5 reward the self check that would expose A and B, so a model that does that conduct tends to fix the lever (judge-side, harder to earn without the right reading) | tests/judge.toml |
| F3 | JD-7 04_Judge_QC.md:76 "Every criterion must be satisfied (or, for negatives, avoided) by the shipped oracle in solution/." | v0 solve.sh only copied and ran solve.py; no self check; v0 solve.py emit() was 317 lines, which breaks R3's 150-line bound | solve.sh gains a self-check heredoc run after the closure: check 1 (SETTLED dependent with one live edge to an OPEN blocker is blocked), check 2 (waiver on a discharged period is INERT, periods_waived 0), check 3 (extract without the eight documents in a temp path gives the same 28 outputs), then `wrote <path>` per file; temp dir only, removed after. solve.py emit split into emit + emit_intake / emit_views / emit_load / emit_figures (max function now 148 lines) | :41 JD-7 (fix the oracle to meet the criterion) | none / none | solution/solve.sh, solution/solve.py |
| F4 | JD-S13 04_Judge_QC.md:117 "weights.judge equals 0.5 divided by this file's positive criterion total at full float precision"; tests_qc R3 tests_qc.py:90 | reward.toml:4 judge = 0.005263157894736842 (0.5/95) | judge = 0.02631578947368421 (0.5/19); test_output 0.0037593984962406013 unchanged | JD-S13 | none / none | tests/reward.toml |
| F5 | AL-27 05_Alignment_Integrity_QC.md:27 "a rule only counts as graded when the test's input actually constructs the situation where the rule matters."; LEVER_RULES G11 | no RULE_COVERAGE.md (precheck NOTE AL-27) | WORK/RULE_COVERAGE.md: 25 rows (every TRUTH.md focal, drift, trap and pitfall rule plus levers A and B), each a solve.py mutant scored locally with the real tests (python3 -B); every row drops >= 1 test; rules uncovered 0 | :32 AL-27 | measured only | WORK only |
| F6 | DS-22 02_Data_Solution_QC.md:78 "A TRUTH.md that describes a different task, a superseded solution, or grading that does not exist is worse than none" | TRUTH.md judge paragraph described 28 criteria / 95 points, a twelve-figure table and units A-G | judge paragraph rewritten (11 criteria, +19/-12, 0.5/19, where the oracle shows each act), figures/units section deleted, ordered-plan step 13 rewritten to the self check; Provenance sha lines recomputed by script after the last edit (data digest b448b534 unchanged); test counts (38 checks, 133) unchanged | :42 DS-22, :31 AL-18 | none / none | solution/TRUTH.md |

## Output byte-identity proof

Oracle run on `/app/data` locally before any edit (WORK/oracle_before.sha, 29 files) and after the last edit through solve.sh (WORK/oracle_after.sha). `diff` shows one line only:

```
< 48b15840c975e7df06c2cc3529ff2f3e030eb66305ab3168fbd3b0d663e66f2d  ./reconcile.py
> cf6ca8ac5119b746da2f6b9a6c196e9dcffed217df17209400ea3a69e5ef17b4  ./reconcile.py
```

`reconcile.py` is the program itself (a byte copy of solve.py), changed by the emit split. All 28 deliverables are byte-identical. The self check writes nothing under `/app/out`.

## Judge before / after

| | criteria | positive points | negative points | judge weight |
|---|---|---|---|---|
| v0 | 28 | 95 | 9 | 0.5/95 |
| now | 11 | 19 | 12 | 0.5/19 |

Expected Opus on the new judge (READ.md): R1, R2, R3 and R7 about 10/19 = 52.6%, overall 63.5 at tests 74.44; one more conduct item gives 68.4% and 71.4.

## Cost table (WORK/COST_TABLE.md, G10)

| lever | wrong reading | tests lost / 133 | share |
|---|---|---|---|
| A | closure from class BLOCKED only | 28 | 21.1% |
| B | periods_waived counts waivers in discharged periods | 21 | 15.8% |
| A and B wrong | | 34 | 25.6% (tests 74.44, matches v0) |

Projected overall: both wrong 63.5 at rubric 52.6 / 71.4 at 68.4; A right only 68.4 / 76.3; B right only 65.8 / 73.7; both right 76.3 / 84.2. G10 verdict FAIL: each lever alone is under 25%; all-but-one-right stays under 70 at rubric 52.6 but not at 68.4. Weights alone cannot reach 25% (A max 30/135 = 22.2%, B max 25/137 = 18.2% with every lever test at 5).

## Rule coverage (WORK/RULE_COVERAGE.md)

25 rows, 0 uncovered. Thinnest rows: r21 cadence obligor at anchor_at (1 test, unseen_alpha_full_exact), lever B (5 tests), r13 waiver streak (5), r17 canonical tie (5). Two variant readings drop 0 tests and are listed as lessons there: the sweep class inverted where commitment rows compete (solve.py:380) and the cadence-owned-by-nobody fallback (solve.py:1224).

## Checks

- precheck.sh: before `PRECHECK: 4 finding(s)` (K8, H5, G2/J6/J7, J3); after last line `PRECHECK CLEAN` (tests 38, judge criteria 11).
- xref_check: 2 entries, 0 findings before and after.
- live kit structure_qc.py: 17 pass, 0 warn, 0 fail, exit 0.
- stacking_check.py: OUT/STACKING_CHECK.md, hand corrected (tool counted G3 at 6.0%, real 43.6%; AL-28 lumped six acts; J2 listed R4, R5 and missed R6). Corrected verdict PASS.
- `find BUNDLE -name __pycache__`: empty.

## Docker (tests only, kit exe_copy.py copies, one nohup chain, ALL_DONE)

Chain log `/tmp/opencode-logs/caldermoor-commitment-closure-p12-20261024T150419-4633/chain.log`; warm image `warm-caldermoor-commitment-closure` built first. exe_copy removes judge.toml and sets test_output 1/133, so these are tests-only rewards.

| run | copy | reward |
|---|---|---|
| oracle-1, oracle-2, oracle-3 | plain | 1.000, 1.000, 1.000 |
| owner-1 | --owner-only | 1.000 |
| nop-1 | plain, agent nop | 0.000 |
| stub-1 | --stub (29 empty artifacts) | 0.000 (0 of 133 positive points, share 0.0%) |

Oracle agent logs show the three self-check lines (`check 1 ok ...`, `check 2 ok ...`, `check 3 ok ...`) inside the task container.

## Side effects

Rechecked per FIX_SIDE_EFFECTS.md: JD-5 -> JD-2 (positive grammar, judge_qc J10 pass), JD-7 (every criterion shown by the oracle, JUDGE_MAP), JD-9 (all new criteria are conduct: derivation check, verification habit, honest reporting), JD-15 (R1/R2 instruction following with quoted sentences instruction.md:82-84 and :23-24; R3-R7 conduct at w3/w1), IN-8 (every self-check case is learnable from dependency-semantics.md:50 and cadence-register.md:51-64). JD-18 -> JD-7 (emit split so the oracle meets R3). AL-2 -> TS-25 (R3 is absence-shaped but is the mandated J4 named shape; tests unchanged). AL-27 -> TS-13 n/a (tests untouched). AL-18: no stale figure, unit or count reference in instruction.md, TRUTH.md or judge.toml.

## Deviations from master directions

1. tests/Dockerfile:12 adds `litellm==1.105.0` to the pip line (tests_qc K8 FAIL) and tests/test.sh:7 `chmod 700` -> `chmod 755` (tests_qc H5 WARN). Outside the F list; needed for `PRECHECK CLEAN`. Test code and weights untouched.
2. solution/solve.py emit() split into five functions so the oracle meets R3 (J4 150-line bound, JD-7). Outputs on /app/data byte-identical; reconcile.py (the program copy) changes bytes.
3. The self check lives in a heredoc inside solve.sh, not a helper file: structure_qc S3 allows only TRUTH.md, solve.py, solve.sh in solution/.
4. R3 says "one hundred and fifty lines", not "about 150": judge_qc J11 fails on "about" and precheck flags 3-digit numbers (J1 note).

## Lessons for the master

- G10 cannot be met by weights here: each lever's tests are shared by unseen_* tests, so A tops at 22.2% and B at 18.2% | template_change: LEVER_RULES_v1.md:61 add "lever needs >= 2 dedicated probe seeds with downstream artifacts reading the lever set" at authoring
- Two TRUTH-named readings drop 0 tests (sweep inversion on commitment competition solve.py:380; nobody-owned cadence fallback solve.py:1224) | no change: next test round, closest tests precedence_inversion_exact and cadence_streak_and_waiver_semantics_exact
- stacking_check.py misclassifies probe tests (G3 6.0% vs 43.6%) and lumps AL-28 acts | template_change: tools/stacking_check.py G3 and AL-28 classifiers
- J4 wording "about 150 lines" fails judge_qc J11 | template_change: LEVER_RULES_v1.md J4 line, use "one hundred and fifty lines"
- Self-check helpers must not be new solution/ files (S3) | template_change: P12 v3 F3 wording "or a helper it calls" -> "inside solve.sh"
