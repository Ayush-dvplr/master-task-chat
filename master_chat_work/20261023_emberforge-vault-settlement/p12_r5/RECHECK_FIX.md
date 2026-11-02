# P12 r5 RECHECK_FIX - emberforge-vault-settlement (board 51efd20)

Kit: `Terminal_2.0_Harbor_Harness/Input_Bundle_QC` HEAD `71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e`. QC report v7 (2 fail, 0 minor, 2 warn). Levers in WORK/LEVERS.md: L7 per-unit charge, L3 cap ledger, L6 scope by definition (plus the draw drift and the digest decoy, which no fix touches). None of the four findings is script-owned: the four QC scripts on the BUNDLE before any change print instruction_qc 5/0/0, structure_qc 17/0/0, tests_qc 37/0/0, judge_qc 19/0/0 (pass/warn/fail), all VERDICT PASS (OUT/qc_before/).

## Phase 1 recheck

| ID | Label | Rule (live kit) | Evidence (bundle before) | Decision | Playbook row | L7 / L3 / L6 | Files changed |
|---|---|---|---|---|---|---|---|
| DS-27 (fail) | REAL | `02_Data_Solution_QC.md:80` "TRUTH.md describes the task, not how the task was made. ... What does not belong is any narrative of the production process: ... a changelog of what the author tried first, ... review and approval history, internal taxonomy."; fail list :117 "DS-27 authoring or process narrative in TRUTH.md" | `solution/TRUTH.md:14` "Three rules carry this round's levers."; :17/:24/:32 "(focal) L7 / L3 / L6"; :38 "cover the older same-day trap"; :42 "(drift)", :45 "(trap)"; :48 "Rules carried from earlier rounds"; :92 "decide nothing about the L7 lever"; :108-110 "L7: / L3: / L6:"; :121/:126/:145 "lever"; :136 "hardened". Bundle grep also hits `tests/test_output.py:2598` `_lever_ladder` and :2599 docstring "LV-EF-4:" (internal taxonomy). Every other grep hit is a rule id (V1-V9) or the plain words "round"/"earlier" in task sense. | FIX per direction: rule names as task facts, process and taxonomy words removed in TRUTH.md and WORK/TRUTH.src.md; `_lever_ladder` renamed `_requisition_ladder`, docstring tag dropped (name only, no behaviour change) | DS-27 DO: rewrite as task facts | none / none / none | solution/TRUTH.md, WORK/TRUTH.src.md, tests/test_output.py |
| TS-25 (fail) | REAL | `03_Tests_QC.md:52` "Positive tests grade earned work, never an absence. ... (an empty violations list, a banned import that is absent, ...) ... A positive-weight check whose pass condition is an absence is a fail; keep the detection logic, move it to a negative check." | `tests/test_output.py:3082` `assert all(name.split(".", 1)[0] in sys.stdlib_module_names for name in names)` inside positive `test_program_imports_stdlib_only`; registered :3467 `criteria.program_imports_stdlib_only(weight=1)`; QC stub (12 empty artifacts) earned 1/55 = 0.0182 from it | FIX per direction: same detection moved to `negative_imports_third_party_module` (-1); positive total 55 -> 54; reward.toml test_output 0.5/54 | TS-25 DO: keep detection, invert to negative | none / none / none | tests/test_output.py, tests/reward.toml, solution/TRUTH.md |
| JD-16 (warn) | REAL | `04_Judge_QC.md:97` "It is graded once, and by the layer that should own it. ... where both layers could grade a rule the test should own it ... When a constraint criterion enforces a rule a test could have checked and no test checks it, say so and name the assertion that would have worked. Warn rather than fail"; balance rules `03_Tests_QC.md:62` TS-23 "the sum of absolute negative weights is at most the sum of positive weights (fail)" and `04_Judge_QC.md:89` JD-12 "negatives never outweigh" positives | `tests/judge.toml:111-123` R9 "The agent delivers a program that opens a network connection while it settles a season, contrary to instruction.md: 'no network calls while it runs'." weight -1, evaluation_target state_change; no test checks network use | FIX per direction: test `negative_program_opens_network` (-1) runs the program once on the visible season under an audit hook wrapper; R9 deleted. Totals after: tests 54 positive / 10 negative (10 <= 54), judge 12 positive / 10 negative (10 <= 12) | JD-16 DO: move the rule to the layer that owns it | none / none / none | tests/test_output.py, tests/judge.toml, solution/TRUTH.md |
| JD-18 / CL-2 (warn) | REAL | `04_Judge_QC.md:99` "At least one criterion judges the quality of the code the agent writes. ... no bare `except`, errors handled rather than swallowed ..."; `Final_checklist.md:489` CL-2 "Price the forgery ... any test that paid while believing it was grading content" | `tests/judge.toml:53` R4 "every except clause names an exception type and either raises again or reports the error with a message", weight 3; `solution/solve.py` has no except clause (grep `except` 0 hits), so R4 pays any program with none. No missing-input rule is stated: grep of instruction.md and environment/data/*.md for missing/exit/non-zero finds only data semantics (finding_codes MISSING_FORGE_REF, invariants.md:26, rulebook_editions.md:31, rulebook_salvage.md:10) | FIX per direction with the fallback sentence: one plain sentence added to instruction.md paragraph 3 beside the other program rules; R4 rephrased to that error path; oracle checks its inputs and exits 1 naming the file; shipped outputs byte-compared old vs new | JD-18 DO: named code-quality criterion the oracle meets (JD-7) | none / none / none | instruction.md, tests/judge.toml, solution/solve.py, solution/TRUTH.md |

No deviations from master directions so far.

## Phase 2 changes

- DS-27: `solution/TRUTH.md` rewritten as task facts (17 line edits; rule names "per-unit charge (H1, H5)", "cap release (S5)", "live window (S2)"); `tests/test_output.py` `_lever_ladder` renamed `_requisition_ladder` (2 sites), "LV-EF-4:" tag dropped. WORK/TRUTH.src.md synced. Whole-bundle grep (solution, tests, environment, instruction.md, task.toml) for `round|lever|harden|earlier version|\bL[0-9]\b|\bv[0-9]+\b` now hits only "rounded" (rulebook_admission.md, test_output.py) and test_output.py:1429 "each round adds the candidate case" (a greedy loop step, not process).
- TS-25: positive `program_imports_stdlib_only` removed; `test_negative_weight_imports_third_party_module` keeps the same AST detection and asserts the set of top-level non-stdlib names is non-empty; missing program -> assertion fails -> False. Criterion `negative_imports_third_party_module` weight -1. `tests/reward.toml` test_output = 0.009259259259259259 (0.5/54).
- JD-16: `_run_delivered` takes an optional `launch` prefix; `test_negative_weight_program_opens_network` runs the program once on `_visible_corpus()` through a grader-written wrapper that installs `sys.addaudithook` for `socket.connect`, `socket.getaddrinfo`, `socket.gethostbyname`, then `runpy.run_path` the program; a recorded event counts even when the run fails. Criterion `negative_program_opens_network` weight -1. R9 deleted from `tests/judge.toml`. Follow-on (same fix, not a deviation): the first tests_qc run after the change failed H6 because the wrapper ran under the dropped uid without a chmod; `_run_delivered` now does `os.chmod(launch[0], 0o644)` before the uid drop, and H6 passes.
- JD-18: instruction.md:7 gains, right after "Two runs over the same corpus must write byte-identical files.": "When a file it needs is missing from its data directory, it must exit with a non-zero status and name the missing file." R4 is now `r4_program_names_missing_input`: "The agent leaves a /app/out/settle_vault.py that, when a file it needs is missing from its data directory, exits with a non-zero status and names the missing file." (weight 3, annotations unchanged). `solution/solve.py` main checks `REQUIRED_INPUTS` (12 files) first and prints `settle_vault: missing input file <path>` to stderr, return 1. IN-15 (`01_Instruction_QC.md:45`) now holds: the graded rule is stated. IN-16 (:46): stderr vs stdout, name vs path both satisfy R4 as written, so no reading flips a grade. IN-14 (:44): end-state rule, not a fix path. Hidden seasons always write all 12 files (`write_corpus` test_output.py:1338-1352, `_build_corpus_dir` :2185-2201), so no test trips the check.
- TRUTH.md counts and prose updated (22 checks, 16 positive 54, six negatives -10, shares of 54, eight criteria 12 / -10, R4 text, solution step 7), then `solve_py_sha256` = 07d36336fb3a..., `test_output_sha256` = 276613231cda... recomputed LAST (TRUTH has no line counts).
- WORK: LEVERS.md (P12 r5 effects table, all none), QC_DEFENCE.md (P12 r5 disposition), XREF.md (retired `program_imports_stdlib_only`, `r9_program_opens_network_connection`, `r4_program_reports_every_caught_error`, `0.00909090909090909`, `**55**`, `_lever_ladder`, "every except clause", "nine criteria"; new names added).

## Gate results

| Gate | Result |
|---|---|
| xref_check | 61 entries, 0 findings |
| instruction_qc / structure_qc / tests_qc / judge_qc (OUT/qc_after/) | 5/0/0, 17/0/0, 37/0/0, 19/0/0 (pass/warn/fail), all VERDICT PASS |
| DS-27 grep | clean (only "rounded" and a greedy-loop "round") |
| TS-25 stub | local: empty settle_vault.py fails every real check; the local scorer's NOT_RUN credit for `structure_program_takes_directories` is its only point (scorer artifact, the test needs `/app/data`). Docker stub below |
| JD-16 negative totals | tests TS-23 `03_Tests_QC.md:62`: 10 <= 54; judge JD-12 `04_Judge_QC.md:89`: 10 <= 12 (script rules tests_qc W7, judge_qc G6 pass) |
| JD-18 oracle meets R4 | old and new solve.py on environment/data: rc 0 both, `diff -r` identical over 11 files, stdout identical; with vault_opening.csv removed: stderr `settle_vault: missing input file miss/vault_opening.csv`, rc 1, no output written |
| TS-29 real bool | both new wrappers return `_passes(...)`, which returns a bool and catches Exception; a 2000-byte random program raises in no check |
| Negative proofs | WORK/wrong/neg_third_party.py 53/54, only `negative_imports_third_party_module` fires; WORK/wrong/neg_network.py (`socket.getaddrinfo("example.com", 80)` in try) 53/54, only `negative_program_opens_network` fires; every other row equals the oracle's |
| Stacking (OUT/STACKING_CHECK.md) | PASS: AL-28, whole-doc 64.8%, shipped-only 0%, caps. The tool's G3 hint (isolated + mutation 31.5%) counts the two structure checks as isolated rule checks; it read 32.7% on the QC copy before the change. Rule checks proper: 15/54 = 27.8% <= 30% (LEVER_RULES_v1.md:38) |

## Reflex before/after

Codex reflex program (blind_r2_codex/app/settle_vault.py), local tests channel: before 17/55 = 0.3091 normalized = 0.1545 reward contribution; after 16/54 = 0.2963 normalized = 0.1481 contribution. Gate on the contribution scale (as in r4): 0.1481 <= 0.20 and <= 0.1545 + 0.02. The only row it lost is the removed positive `program_imports_stdlib_only`; its FAIL set is otherwise unchanged (seven whole documents, live_window_refusals).

## Trap survival

| Reading | Before loss of P (55) | After loss of P (54) | Ratio | Verdict |
|---|---|---|---|---|
| L7_rebased | 32 | 32 | 1.00 | PASS |
| L3_rebased | 38 | 38 | 1.00 | PASS |
| L6_rebased | 38 | 38 | 1.00 | PASS |
| no_reinstate | 35 | 35 | 1.00 | PASS |
| no_apprentice_relief | 20 | 20 | 1.00 | PASS |
| codex reflex (contribution) | 0.1545 | 0.1481 | n/a | PASS |

Overall: PASS. Each variant lost exactly the 1 point the removed positive used to pay it, on both sides.

## QC_RULINGS rows

| Rule | Our design | QC verdict | Our label | Reason |
|---|---|---|---|---|
| DS-27 | TRUTH.md named rules by internal lever ids and round history | fail | REAL | Production narrative and internal taxonomy; rewritten as task facts |
| TS-25 | Positive 1-point check paid for an absent third-party import | fail | REAL | Absence on the positive side pays a stub; inverted to a -1 negative |
| JD-16 | Judge R9 graded network use a test can detect | warn | REAL | Deterministic layer owns it; audit-hook negative test added, R9 removed |
| JD-18 / CL-2 | R4 graded except-clause hygiene; oracle had no except clause | warn | REAL | Vacuous pass; R4 now names a stated error path the oracle meets |

## Docker (tests channel, live kit exe_copy.py copies)

Root `/tmp/emberforge-p12r5-20261023T172056-2073`, warm image `warm-emberforge-vault-settlement`, one nohup chain (OUT/docker_chain.log, ALL_DONE 17:26:59). oracle x3 = 1.0, 1.0, 1.0; owner-only x1 = 1.0; nop x1 = 0.0; 12-empty-artifact stub x1 = 0.0 (was 0.0182 in QC v7). No trial exceptions.

## Lessons for the master

- A launcher placed between `sys.executable` and the agent program is read by tests_qc H6 as the executed program; chmod it 0644 before the uid drop or H6 fails.
- stacking_check's G3 hint counts structure checks as isolated rule checks; read the rule share by hand before calling G3 failed.
- Moving an absence check to the negative side costs every non-cheating program one point evenly, so trap losses stay at ratio 1.00.
