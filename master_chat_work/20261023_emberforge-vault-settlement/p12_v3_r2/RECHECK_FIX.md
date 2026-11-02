# RECHECK_FIX: emberforge-vault-settlement, P12 v3 r2 (board 5f0812e, QC v8 board 391ff22)

Date 24 Oct 2026 13:45-14:09 IST. Kit: harness HEAD `71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e` (live kit = authority).
Session rename `5f0812e` at 13:45:50: `opencode: ['ses_e9305157dffev2BIYQqeR8DoBI']` (listed; codex: no match).
Tree sha at start `e9bd62b2225d` (matches issue). Lock `/tmp/opencode-logs/locks/emberforge-vault-settlement.lock` taken 13:47.
Noise check (Always 13): the QC copy 391ff22 `tests/test_output.py` is byte-identical to the bundle at start; the 6ec5e57 -> 391ff22 diff is rulebook_identity.md, rulebook_salvage.md, instruction.md, TRUTH.md, solve.py, judge.toml, reward.toml, test_output.py and the stray `tests/__pycache__`. None of the five findings is noise.

Levers (WORK/LEVERS.md): L7 per-unit forge charge, L3 cap ledger after credited salvage, L6 live window scope by definition.

## Findings

| ID | label | rule quote (live kit) | evidence quote (bundle at start) | decision | playbook row | L7 | L3 | L6 | files changed |
|---|---|---|---|---|---|---|---|---|---|
| F1 S5 | REAL (master error 12:29) | structure_qc.py:336-342 `fail("S5", f"forbidden directory: {rel}")` for `__pycache__`; Final_checklist.md:287 FC-S4 "...or the directories __pycache__, .git, .pytest_cache." | v8.md:35 "`tests/__pycache__/test_output.cpython-314.pyc` (214220 B)". Already deleted by master 13:05. `find BUNDLE -name __pycache__` at start: (printed nothing); before Docker 14:02: (printed nothing); at end: see Final state. | FIX (confirm absent); every import this round ran with `PYTHONDONTWRITEBYTECODE=1 python3 -B` | S5: delete, never import without the flag | none | none | none | none (master did the delete) |
| F2 DS-22 | REAL (master error 12:29) | 02_Data_Solution_QC.md:78 "TRUTH.md describes the bundle that actually shipped... confirm the stated counts, weight totals and named negatives are the real ones." | solution/TRUTH.md:241 `test_output_sha256: 276613231c...` while shasum was `a8b43242a2ab...` (v8.md:36/150) | FIX LAST: Provenance digests recomputed after every tests/ edit (`test_output_sha256: e5dbc5f005bca3c9...`, `solve_py_sha256: 07d36336fb3a...` unchanged, both re-verified by shasum 14:03); Verification counts rewritten: 24 checks, 18 positive = **58**, six negatives = -10; judge 8 criteria +12 / -10; R4 paragraph; weight-share paragraph. WORK/TRUTH.src.md synced (identical) | DS-22: rewrite TRUTH by script, last | none | none | none | solution/TRUTH.md, WORK/TRUTH.src.md |
| F3 JD-18 | REAL (ping-pong: v7 JD-18 warn suggested turning the old code-quality R4 into the missing-input outcome; P12 r5 did so, v8 then failed JD-18) | 04_Judge_QC.md:99 "At least one criterion judges the quality of the code the agent writes... It is a CONDUCT criterion under JD-15, it needs no quoted sentence... the criterion must judge quality, not prescribe a style guide"; fail at :146 | v8.md:37/211 "no judged criterion assesses the quality of the authored program... R4 at tests/judge.toml:53 judges a behaviour" | FIX: R4 slot reused: `id = "R4"`, `name = "r4_program_code_quality"`, weight 3, description "The agent leaves a /app/out/settle_vault.py that a Python reviewer would accept as maintainable, judged on its names, function structure and error handling." (QC's wording), annotations mode judged / type "agent behavior" / evaluation_target "state_change" / importance "important" (tests/judge.toml:51-62). Oracle passes on paper (see Judge paper scores) | JD-18: add exactly one concrete code-quality criterion, conduct, w1-3, confirm oracle meets it (JD-7) | none | none | none | tests/judge.toml |
| W1 JD-9 | REAL | 04_Judge_QC.md:86 "Process focus is the judged channel's value-add... Prefer trajectory/state_change criteria that watch HOW the agent worked."; warn at :146 "JD-9 criteria that add no process value beyond the tests" | v8.md:44/212 "R4 `r4_program_names_missing_input` (tests/judge.toml:50-61) grades a deterministic artifact outcome... under the label `type = \"agent behavior\"`" | FIX (with F3a): R4 removed from the judge; new test `test_program_names_missing_input` (test_output.py:3163-3181), registered `criteria.program_names_missing_input(weight=1)` (:3576). It copies forge_a's hidden data, unlinks `crafting_ledger.csv`, runs the delivered program the same way as every other check (`_run_delivered`), and passes only on a non-zero exit whose stderr+stdout contains `crafting_ledger.csv`. `_run_delivered` now raises `ProgramFailed(AssertionError)` carrying the printed text (:2316, :2356) | JD-9 / LEVER_RULES J7: deterministic artifact behaviour is a test | none | none | none | tests/test_output.py, tests/reward.toml |
| F4 AL-27 | REAL (new scope; v7 examined precedence pairs only) | 05_Alignment_Integrity_QC.md:27 "a rule only counts as graded when the test's input actually constructs the situation where the rule matters... no such input means the rule is ungraded regardless of what the test is called. Fail; name the rule and the missing fixture." | v8.md:38/243 "four stated rules have no graded fixture, so a solver breaking any one of them still scores 54/54... `_trigger_quiet_rules` (tests/test_output.py:2427-2481) is reachable only through `MUTATIONS[\"nonapplying\"]` (:2490), which no season or check uses". Local proof before: all four mutants 54/54 | FIX: SEASONS entry `"quiet_rules": (EVAL_SEED + 4, Params("RS-C", "half-up", "FSG", "opening"), _mut_nonapplying)` (:2957); `test_quiet_rules_findings_and_funding` (:3410-3412) asserts `_same` on data_quality.json and allocation.json, registered weight 3 (:3587). The old V2 and STOCK_FLOOR edits did not bite on the seed-27 corpus (L0246 is a salvage there; no STOCK_FLOOR finding), so `_trigger_quiet_rules` was extended: a heavy copy L0902 of L0196 (units 999) plus a same-day acquisition AQ9001 of 2 x 999 units of R01, so that the STOCK_FLOOR detail is R05 only when V2 counts same-day units and the detail names the first short reagent. Docstring (:2437-2443) now claims only A2 both edges, Q1, V2 and the STOCK_FLOOR detail order. WORK/RULE_COVERAGE.md written (LEVER_RULES G11) | AL-27 + NEW-CHECK: hidden reseeded rows inside stated bounds (TS-19); not a new lever | none | harder (salvage_day_window and L3 variants also fail the new check) | none | tests/test_output.py, tests/reward.toml, WORK/RULE_COVERAGE.md |

reward.toml: `weights = { test_output = 0.008620689655172414, judge = 0.041666666666666664 }` (0.5/58, 0.5/12; judge positive stays 12 because R4 keeps weight 3).

New check weight choice: `program_names_missing_input` weight 1, because it is a contract-shape behaviour any competent program meets (like the four weight-1 `structure_*` checks, TS-20: not a core check) and weight 3 would dilute the lever shares toward the 0.90 trap floor.

## AL-27 mutant table (WORK/wrong/, built by make_al27_mutants.py from solution/solve.py; local scorer, tests channel)

| mutant | single rule broken | before (earned/54, loss) | after (earned/58, loss) | failing check after |
|---|---|---|---|---|
| al27_stock_floor_last | STOCK_FLOOR detail names `short[-1]` | 54/54, 0 | 55/58, 3 | quiet_rules_findings_and_funding (data_quality.json) |
| al27_a2_edges | A2 opening edge `>=`, closing edge `<=` | 54/54, 0 | 55/58, 3 | quiet_rules_findings_and_funding (both documents) |
| al27_q1_all | Q1 funds every requisition | 54/54, 0 | 55/58, 3 | quiet_rules_findings_and_funding (allocation.json) |
| al27_v2_strict | V2 same-day units `<` | 54/54, 0 | 55/58, 3 | quiet_rules_findings_and_funding (data_quality.json) |

Missing-input proof (WORK/wrong/make_missing_input_variants.py): oracle 58/58 passes `program_names_missing_input`; `mi_generic` (exits 1 with a message without the file name) 57/58 and `mi_traceback` (raises a bare `RuntimeError("input missing")` traceback without the name) 57/58, both failing only `program_names_missing_input`. Note: a real `FileNotFoundError` traceback prints the path, so it meets instruction.md:7 and passes; that is intended.

## Judge paper scores (new R4 r4_program_code_quality)

- Oracle solution/solve.py: PASS. 1183 lines, 46 functions, 45 with return annotations, 13 docstrings, no `except` clause anywhere, no debug residue (grep TODO/XXX/pdb/breakpoint: none); missing inputs are handled explicitly: solve.py:1163-1166 `for name in REQUIRED_INPUTS: if not (data_dir / name).is_file(): print("settle_vault: missing input file %s" % (data_dir / name), file=sys.stderr); return 1`. Longest function compile_records (228 lines) is a flat record builder a reader can follow.
- a7 agent program (traj_a7 .../app/out/settle_vault.py): likely PASS. 1352 lines, 43 named functions (`reduce_fraction`, `read_csv`, `load_season`, `derive_conventions`, `scarcity_index`...), 10 docstrings, no annotations (none expected: the file uses none), no debug prints; error handling explicit at :122-127 (`sys.stderr.write("error: missing required input file: %s\n" ...); sys.exit(2)`); the one handler `except Done: pass` (:1102) catches a named control-flow exception of its own search, not a swallowed error. Weak points a strict reviewer might cite: `class Season(object): pass` attribute bag (:118), three functions of 184-191 lines.
- Other criteria unchanged; a7 before: R1-R3 FAIL (-9), old R4 PASS, no negative fired -> 3/12.
- a7 projected: tests 17/58 = 0.2931 (local scorer, OUT/after/a7.json); rubric 3/12 = 0.250 (R4 PASS) or 0/12 if a judge fails R4; overall = mean = **0.2716** (0.1466 if R4 fails). Before: run reward 0.2731 (16/54, 3/12).

## Side effects (Always 14; FIX_SIDE_EFFECTS.md rows)

| fix | side-effect id | re-check | result |
|---|---|---|---|
| JD-18 | JD-7 every criterion satisfied by the oracle | oracle solve.py meets R4 (above); oracle trajectory has no R5-R8 act | PASS |
| JD-5 (judge edit) | JD-2 positive grammar | R4 description is a positive statement starting "The agent leaves" | PASS |
| JD-5 | JD-5 one observable | R4 judges one artifact on one property (maintainability) | PASS |
| JD-5 | JD-9 | R4 judges how the code is written, not what it outputs; no criterion now grades a deterministic outcome | PASS |
| JD-5 | JD-15 | R4 is conduct (type agent behavior, state_change), weight 3; judge_qc exit 0, warns 0 | PASS |
| JD-5 | IN-8 | missing-input contract stays stated at instruction.md:7 ("must exit with a non-zero status and name the missing file"); the check accepts the name on either stream because the instruction names none | PASS |
| JD-S4 / judge_qc J2 | sequential ids | R1..R8 contiguous, R4 slot reused | PASS |
| AL-27 | TS-13 one property per test | quiet_rules check grades the two documents of one hidden season, the only two the four rules touch; program_names_missing_input asserts one behaviour (exit + name) | PASS (stacking hint lists only structure_canonical_serialisation, unchanged) |
| TS-19 | TS-23 count/negatives | 24 checks (>= 10), sum of negatives 10 <= 58 | PASS |
| TS-19 | TS-26 no pair pays twice | stacking TS-26 duplicates: none; quiet_rules season is a separate seed (EVAL_SEED+4) and no other check reads it | PASS |
| NEW-CHECK | TS-25 no positive grades an absence | nop 0.000 and stub (Docker, below); with no program `_run_delivered` raises AssertionError, which `test_program_names_missing_input` does not catch | PASS |
| NEW-CHECK | TS-14 / TS-16 naming | new positives have no `negative_` prefix; descriptions say what passes | PASS |
| STEP11 | TS-13/TS-14/TS-25 | as above | PASS |

Kit runs (PYTHONDONTWRITEBYTECODE=1): precheck.sh `structure_qc exit=0 warns=0`, `instruction_qc exit=0 warns=0`, `tests_qc exit=0 warns=0`, `judge_qc exit=0 warns=0`, `NOTE AL-27 RULE_COVERAGE.md 11 rule rows`, `tests 24 (tests_qc A3 count), judge criteria 8`, last line `PRECHECK CLEAN`. structure_qc.py: `SUMMARY: 17 pass, 0 warn, 0 fail` `VERDICT: PASS`, exit 0. xref_check: `xref_check: 63 entries, 0 findings`. embed_rulebooks.py on a temp copy: `embedded 12 documents`, cmp equal (RULEBOOK_TEXTS in sync). Stacking: OUT/STACKING_CHECK.md; tool says "judge J2 conduct criteria: none" and counts 3 structure/contract checks as isolated (known tool bug), corrected by hand there: R1-R4 are conduct; verdict PASS.

## Trap survival (local scorer, tests channel; before = WORK/trap/before_v3r2, P 54; after = bundle, P 58)

| variant | before loss of P | after loss of P | ratio | verdict |
|---|---|---|---|---|
| oracle | 0/54 | 0/58 | - | PASS (full) |
| L7_rebased (lever) | 32/54 = 0.593 | 32/58 = 0.552 | 0.931 | PASS |
| L3_rebased (lever) | 38/54 = 0.704 | 41/58 = 0.707 | 1.005 | PASS |
| L6_rebased (lever) | 38/54 = 0.704 | 38/58 = 0.655 | 0.931 | PASS |
| no_reinstate (wrong) | 35/54 = 0.648 | 35/58 = 0.603 | 0.931 | PASS |
| no_apprentice_relief (wrong) | 20/54 = 0.370 | 20/58 = 0.345 | 0.931 | PASS |
| salvage_day_window (wrong) | 38/54 = 0.704 | 41/58 = 0.707 | 1.005 | PASS |
| neg_network (negative probe) | negative fires (-1) | negative fires (-1) | 1.000 | PASS |
| neg_third_party (negative probe) | negative fires (-1) | negative fires (-1) | 1.000 | PASS |
| a7 agent program | 38/54 = 0.7037 (score share 0.296) | 41/58 = 0.7069 (score share 0.293) | - | PASS (score share 0.293 <= 0.296 + 0.02) |
| al27_* x4 | 0 | 3/58 each | new | separated |
| mi_generic, mi_traceback | not scored (new) | 1/58 each | new | separated |

No check that failed for any variant before passes after (no separating hidden case gone). a7's lost checks (whole_* x7 -5, live_window_refusals -3) are all kept. WORK/wrong/r0 and r1 are superseded solver sets of earlier rounds, not scored. Overall: **PASS**.

## Docker (tests only, copies from the live kit's exe_copy.py)

Root `/tmp/emberforge-p12v3r2-20261024T140254-c93f` (plain, owner = `--owner-only`, stub = `--stub`; logs exe_copy_plain/owner/stub.log). Chain `docker_chain.sh`, log `docker_chain.log` (ALL_DONE 14:07:06), warm image `warm-emberforge-vault-settlement` (WARM EXIT:0, warm.log). At most 2 Docker jobs at once (0 other containers at start).

| job | copy | agent | reward | test_output earned |
|---|---|---|---|---|
| oracle-1 | plain | oracle | 1.000 | 58/58 |
| oracle-2 | plain | oracle | 1.000 | 58/58 |
| oracle-3 | plain | oracle | 1.000 | 58/58 |
| owner-1 | owner (--owner-only) | oracle | 1.000 | 58/58 |
| nop-1 | plain | nop | 0.000 | 0/58 |
| stub-1 | stub (--stub) | oracle | 0.000 | 0/58 (share of P 0.0) |

## QC_RULINGS rows

| rule | bundle | ruling | evidence |
|---|---|---|---|
| JD-18 / JD-9 | emberforge v8 | Turning the only code-quality criterion into an artifact-outcome criterion (as v7's JD-18 warn suggested) gives JD-18 FAIL + JD-9 WARN; keep a code-quality conduct criterion and put deterministic exit/stderr behaviour in a test | v7.md:45, v8.md:37,44 |
| AL-27 | emberforge v8 | A fixture builder reachable only through an unused MUTATIONS entry is not coverage; mutants of each rule must lose points | v8.md:38; this report AL-27 table |
| DS-22 | emberforge v8 | Any tests/ edit after TRUTH is written (incl. master regeneration of embedded texts) stales the digest; rewrite TRUTH last | v8.md:36 |

## Deviations from master directions

1. Code-quality criterion takes id R4 / name `r4_program_code_quality` instead of QC's suggested R9: the kit requires contiguous ids (judge_qc.py J2, 04_Judge_QC.md:108 JD-S4) and R4 was moved out, so reusing the slot keeps R1-R8 stable; judge stays 8 criteria, +12 / -10, reward judge weight 0.5/12 unchanged (QC's 0.5/15 assumed R4 stayed).
2. `program_names_missing_input` accepts the file name in stderr or stdout (master said stderr): instruction.md:7 names no stream, so requiring stderr would grade an unstated rule (IN-8).
3. `_trigger_quiet_rules` V2 and STOCK_FLOOR edits were rebuilt on L0196 (the old L0246/L0117 edits did nothing on the seed-27 corpus); this is the "extend until each mutant loses" branch of the direction.

## Lessons for the master

- A QC warn suggestion that rewrites the only code-quality criterion into an outcome criterion triggers JD-18 fail + JD-9 warn next round | template_change: master_chat_tasks/knowledge/QC_FIX_PLAYBOOK_v2.md JD-18 row: add "never repurpose the code-quality criterion; add the new check beside it"
- Fixture builders written per rule must be proved with single-rule mutants at write time; seed-dependent edits (entry ids) silently stop biting when a season's seed changes | template_change: master_chat_tasks/knowledge/LEVER_RULES_v1.md G11: require mutant rows for every fixture edit, not only the flagged rules
- Any master-side edit of tests/ (here RULEBOOK_TEXTS at 12:29) must end with `find -name __pycache__ -delete` and a TRUTH digest rewrite | template_change: master_chat_tasks/prompts/templates/_COMMON_RULES_v3.md Always 6/15: state that it binds master edits too
- WORK/RULE_COVERAGE.md lists 11 rules (the flagged four plus lever/wrong-variant rules), not every stated rule | no change: a full per-rule mutant table is a design-round job, out of scope here
- LEVER_RULES J4's concrete wording ("no function longer than about 150 lines") would fail the oracle (compile_records 228 lines); QC's maintainability wording was used | template_change: master_chat_tasks/knowledge/LEVER_RULES_v1.md J4: check oracle function lengths before using the 150-line clause

## Final state

- `find BUNDLE -name __pycache__` at end: printed nothing.
- xref_check at end: `xref_check: 63 entries, 0 findings`.
- Tree sha (master method) at end: `2e6b88b4a05f` (start `e9bd62b2225d`). Files changed in BUNDLE: tests/test_output.py, tests/judge.toml, tests/reward.toml, solution/TRUTH.md.
- WORK changed: TODO.md, LOG.md, LEVERS.md, QC_DEFENCE.md, DESIGN.md, XREF.md, TRUTH.src.md, RULE_COVERAGE.md (new), score_local.py, trap_run.sh, trap/before_v3r2/, wrong/make_al27_mutants.py + al27_*.py (4), wrong/make_missing_input_variants.py + mi_generic.py, mi_traceback.py.
- Lock removed at end; session renamed again at end.
