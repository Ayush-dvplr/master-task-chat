# FIRE_TABLE board ef7d851

318 findings from 42 reports (QC/reports/<slug>/v*.md). Parsed fail/minor/warn per report equal each report Verdict line. kit_head = 40-hex sha on the first kit line of the report header (source in fires.json kit_head_src). kit wording quoted from kit HEAD 71a653b2 checklist/definition lines (fires.json kit_wording_src); ids may have been renumbered in older kits (UNVERIFIED for bde868c4/f3765e67 rounds). next_round_status from the next report's "Compared with" section (evidence quote in fires.json next_round_evidence).

| task | v | qc_sha | kit | id | sev | bundle file:line | short finding | next |
|---|---|---|---|---|---|---|---|---|
| cohort | v1 | 982ad8c | 3fb1650b | DS-24 | fail | solution/solve.py:132-171 | ❌ Gate 02 DS-24: the oracle is a renamed restatement of the verifier's graded logic. | fixed |
| cohort | v1 | 982ad8c | 3fb1650b | DS-22 | fail | solution/TRUTH.md:109-110 | ❌ Gate 02 DS-22 (also AL-18): solution/TRUTH.md L109-110 says "R4 13 reason entries in the rejection register", but the oracle's register has 11 rows and 14 reason entries (e030, e | fixed |
| cohort | v1 | 982ad8c | 3fb1650b | DS-27 | fail | solution/TRUTH.md:202 | ❌ Gate 02 DS-27 (also sign-off "scores scoped to test channel"): solution/TRUTH.md L202 "The round 0 agent program scores 0.017." is process narration and an unscoped score claim. | fixed |
| cohort | v1 | 982ad8c | 3fb1650b | TS-25 | fail | tests/test_output.py:873-880 | ❌ Gate 03 TS-25 (also Gate 05 CL-2 F-05-1, Step 10 stub): two positives pay without earned output. | fixed |
| cohort | v1 | 982ad8c | 3fb1650b | JD-7 | fail | tests/judge.toml:52-53 | ❌ Gate 04 JD-7 (also AL-6): tests/judge.toml L52-53 R4 `r4_states_register_reason_entries_13` ("... | fixed |
| cohort | v1 | 982ad8c | 3fb1650b | JD-18 | fail | app/out/derive_report.py | ❌ Gate 04 JD-18: the deliverable is authored code (/app/out/derive_report.py), but no criterion judges its quality, and R7 (L91-92) prescribes one structure instead. | fixed |
| cohort | v1 | 982ad8c | 3fb1650b | JD-15 | minor | tests/judge.toml:91-92 | 🟡 Gate 04 JD-15 (also AL-1, Step 11): R7 (tests/judge.toml L91-92, "cleaning stage and ... | fixed |
| cohort | v1 | 982ad8c | 3fb1650b | IN-12 | minor | task.toml | 🟡 Gate 01 IN-12 (also AL-26): the task.toml description "Derive an exact cohort retention and survival study from flat event records, and provide a reusable deterministic derivatio | fixed |
| cohort | v1 | 982ad8c | 3fb1650b | AL-18 | minor | solution/TRUTH.md | 🟡 Gate 05 AL-18: the solution/TRUTH.md caveat mutation scores (0.700, 0.850, 0.417, ...) are each 1/60 below equivalent mutants measured on the current verifier (0.717, 0.867, 0.43 | fixed |
| cohort | v3 | 3583d79 | 71a653b2 | JD-7 | fail | tests/judge.toml:79 | ❌ Gate 04 JD-7 (root cause; | fixed |
| cohort | v3 | 3583d79 | 71a653b2 | DS-22 | fail | solution/TRUTH.md:189-190 | ❌ Gate 02 DS-22 TRUTH.md claims an except discipline the oracle does not follow. | recurred |
| cohort | v3 | 3583d79 | 71a653b2 | AL-2 | fail | instruction.md:7 | ❌ Gate 05 AL-2 / CL-1 (also Step 11) Nothing grades the final-reply request. | fixed |
| cohort | v3 | 3583d79 | 71a653b2 | AL-27 | fail | schema.md:77-80 | ❌ Gate 05 AL-27 No graded input triggers two of the stated cleaning-order rules. | recurred |
| cohort | v3 | 3583d79 | 71a653b2 | TS-13 | minor | test_output.py:1026 | 🟡 Gate 03 TS-13 Two format checks re-grade cohorts.json. | kept-rejected |
| cohort | v3 | 3583d79 | 71a653b2 | TS-29 | minor | test_output.py:971 | 🟡 Gate 03 TS-29 Checks return floats, not bools. | recurred |
| cohort | v4 | 4089e5c | 71a653b2 | DS-22 | fail | solution/TRUTH.md:231 | ❌ DS-22 (Bug/Error). | downgraded |
| cohort | v4 | 4089e5c | 71a653b2 | TS-29 | minor | 03_Tests_QC.md:135 | 🟡 TS-29 (Suggestion/Improvement; | kept-rejected |
| cohort | v4 | 4089e5c | 71a653b2 | AL-27 | fail | schema.md:88 | ❌ AL-27 (Bug/Error). | recurred |
| cohort | v4 | 4089e5c | 71a653b2 | IN-16 | minor | environment/data/schema.md:40-41 | 🟡 IN-16 (Suggestion/Improvement). | fixed |
| cohort | v4 | 4089e5c | 71a653b2 | TS-13 | minor | tests/test_output.py:1032-1036 | 🟡 TS-13 (Suggestion/Improvement). | kept-rejected |
| cohort | v5 | 07206f4 | 71a653b2 | AL-27 | fail | schema.md:20-23 | ❌ Gate 05 AL-27 (fail, Bug/Error) Five stated rules have no graded input that triggers them, so a solver breaking any one still scores 1.000 on the test channel: (a) plan_history.c | last-round |
| cohort | v5 | 07206f4 | 71a653b2 | TS-29 | minor | test_output.py:1032 | 🟡 Gate 03 TS-29 (minor, Bug/Error) Checks return floats, not bools: test_output.py:1032 `return hits / len(HIDDEN_SEEDS)` and :1372 `return 1.0 if result is None else float(result) | last-round |
| cohort | v5 | 07206f4 | 71a653b2 | TS-13 | minor | test_output.py:1089 | 🟡 Gate 03 TS-13 (minor, Suggestion/Improvement) test_output.py:1089 `assert _emitted(out, "cohorts.json") == expected["cohorts.json"], "cohorts.json differs from the reference"` in | last-round |
| cohort | v5 | 07206f4 | 71a653b2 | DS-22 | warn | TRUTH.md:79-80 | ⚠️ Gate 02 DS-22 (warn, Suggestion/Improvement) TRUTH.md:79-80 "an undrained same-day purchase and refund (the refund sorts first and is unhonored)" but the generator pairs the pur | last-round |
| dispatch | v1 | 4ee264e | 3fb1650b | IN-15 | fail | tests/test_output.py:16069-16070 | ❌ F1 Bug/Error (IN-15, TS-16): `negative_nondeterminism_source_in_solver` (w -3) fires on any `random`/`uuid`/`secrets` import or any call ending `time.time`, `time.time_ns`, `date | recurred |
| dispatch | v1 | 4ee264e | 3fb1650b | TS-17 | fail | tests/test_output.py:15998-16007 | ❌ F2 Bug/Error (TS-17): JSON/JSONL artifacts are compared with Python `==` on `json.loads` values (`_parse` tests/test_output.py:15998-16007, `_group_matches` :16010-16018), so `44 | fixed |
| dispatch | v1 | 4ee264e | 3fb1650b | JD-18 | fail | app/out/solver.py | ❌ F3 Bug/Error (JD-18): the deliverable is authored code (/app/out/solver.py) but no judged criterion grades its quality; | fixed |
| dispatch | v1 | 4ee264e | 3fb1650b | CL-5 | fail | environment/data/handbook_ops_v9.md:296-299 | ❌ F4 Bug/Error (CL-5, TS-19): the value type of the optimality_certificate checks and `budget_binding` is a silent requirement. | moved |
| dispatch | v1 | 4ee264e | 3fb1650b | DS-5 | minor | TRUTH.md:351 | 🟡 Suggestion/Improvement (DS-5): stray `environment/data/cache.txt` (1 byte `x`) is not in xref_manifest.db `sources` and named nowhere; | fixed |
| dispatch | v1 | 4ee264e | 3fb1650b | DS-22 | minor | TRUTH.md | 🟡 Suggestion/Improvement (DS-22): TRUTH.md cosmetic slips: `hidden_*_sourcing` listed twice (lines 310-311), `hidden_*_plan` twice (333-334), and line 354 `fix_patch_sha256` names  | fixed |
| dispatch | v1 | 4ee264e | 3fb1650b | JD-2 | minor | tests/judge.toml | 🟡 Suggestion/Improvement (JD-2): R6 uses negative grammar, "and never passes a cent amount through a float value or float division" (tests/judge.toml R6). | fixed |
| dispatch | v1 | 4ee264e | 3fb1650b | TS-24 | warn | tests/test_output.py:15987 | ⚠️ (TS-24): the agent solver inherits the verifier environment, including `OPENAI_API_KEY` from task.toml [verifier.env]: `_run_solver` env=None (tests/test_output.py:15987) and `e | fixed |
| dispatch | v1 | 4ee264e | 3fb1650b | X1 | warn | ledger_authority.sql | ⚠️ (structure_qc X1): 5 binary files skipped by the text scans (amendment_memo.docx, capital_program.xlsx, ledger_authority.sqlite, penalty_schedule.pdf, xref_manifest.db); | kept-accepted |
| dispatch | v2 | cc65d11 | 3fb1650b | IN-15 | fail | tests/test_output.py:16079 | ❌ IN-15 (gate 01; | moved |
| dispatch | v2 | cc65d11 | 3fb1650b | JD-7 | fail | judge.toml:116-126 | ❌ JD-7 (gate 04) the reference solver fails its own code-quality criterion R9 (judge.toml:116-126, w3: "functions are short enough for a reader to follow"): the embedded solver's ` | fixed |
| dispatch | v2 | cc65d11 | 3fb1650b | AL-28 | fail | test_output.py:16295-16318 | ❌ AL-28 (gate 05) one act costs 6 > 5 across layers: a solver writing inside its input directory trips negative_writes_outside_output_dir (w-3, test_output.py:16295-16318 compares  | fixed |
| dispatch | v2 | cc65d11 | 3fb1650b | TS-16 | minor | tests/test_output.py | 🟡 TS-16 (gate 03) hidden overlays (the same 19 files in H1..H4) never vary the parameter-bearing primary registers penalty_schedule.pdf (holding 132 bps, shortfall 418 c/unit), cap | escalated |
| dispatch | v2 | cc65d11 | 3fb1650b | TS-16 | warn | test_output.py:16081 | ⚠️ TS-16 (gate 03) negative evasion gaps: `_CLOCK_CALLS` (test_output.py:16081) misses `time.monotonic`, `time.perf_counter`, `time.localtime`, `date.today`, `datetime.today`; | escalated |
| dispatch | v2 | cc65d11 | 3fb1650b | TS-19 | warn | test_output.py:37 | ⚠️ TS-19 (gate 03) the 400 s per-run cap (test_output.py:37 `RUN_TIMEOUT = 400`) is stated nowhere the agent reads (oracle needs 0.17 s). | escalated |
| dispatch | v2 | cc65d11 | 3fb1650b | TS-19 | warn | instruction.md:3 | ⚠️ TS-19 (gate 03) the shipped-set artifacts instruction.md:3 asks to leave in /app/out are tested only for existence (`all_artifacts_exist`, w1, :16116-16118). | escalated |
| dispatch | v3 | 582b437 | 71a653b2 | DS-22 | fail | solution/TRUTH.md:188-190 | ❌ Gate 02 / DS-22a, Bug/Error: The author-side Verification claim that the grader removes the judge key is false: `solution/TRUTH.md:188-190` says “`OPENAI_API_KEY` removed from it | fixed |
| dispatch | v3 | 582b437 | 71a653b2 | DS-22 | fail | solution/TRUTH.md:191 | ❌ Gate 02 / DS-22b, Bug/Error: The author-side Verification claim that JSON comparison distinguishes boolean and number types is false: `solution/TRUTH.md:191` says “`1`, `1.0` and | fixed |
| dispatch | v3 | 582b437 | 71a653b2 | TS-16 | fail | tests/test_output.py:16971-16976 | ❌ Gate 03 / TS-16, Bug/Error: Anti-cheat negatives can punish honest comments and miss forbidden imports or calls: `tests/test_output.py:16971-16976,17148-17179` searches entire so | downgraded |
| dispatch | v3 | 582b437 | 71a653b2 | TS-17 | fail | handbook_ops_v9.md:296-299 | ❌ Gate 03 / TS-17, Bug/Error: Hidden JSON comparison pays for numeric stand-ins where booleans are required: `handbook_ops_v9.md:296-299` says the five check keys “hold a JSON bool | fixed |
| dispatch | v3 | 582b437 | 71a653b2 | TS-19 | fail | handbook_ops_v9.md:225-231 | ❌ Gate 03 / TS-19, Bug/Error: The test and judged channels omit promised serialization, shipped-set artifact values, continuous file-access scope and outside-hint constraints: `han | fixed |
| dispatch | v3 | 582b437 | 71a653b2 | TS-24 | fail | task.toml:27-28 | ❌ Gate 03 / TS-24, Bug/Error: Submitted solver code inherits the verifier credential despite a uid drop: `task.toml:27-28` supplies `OPENAI_API_KEY`, and `tests/test_output.py:1683 | fixed |
| dispatch | v3 | 582b437 | 71a653b2 | AL-2 | fail | instruction.md:3 | ❌ Gate 05 / AL-2, Bug/Error: The full instruction-to-grader crosswalk leaves serialization, shipped artifact content, complete read/write scope, standard-library/network/process en | fixed |
| dispatch | v3 | 582b437 | 71a653b2 | AL-18 | fail | solution/TRUTH.md:188-192 | ❌ Gate 05 / AL-18, Bug/Error: `solution/TRUTH.md:188-192` inaccurately claims both secret stripping and type-sensitive JSON comparison, while `tests/test_output.py:16826,16844,1688 | fixed |
| dispatch | v3 | 582b437 | 71a653b2 | AL-19 | fail | task.toml:27-28 | ❌ Gate 05 / AL-19, Bug/Error: The verifier's `OPENAI_API_KEY` reaches agent-authored code: `task.toml:27-28` injects it, and `tests/test_output.py:16826,16844,17198` inherits or co | fixed |
| dispatch | v3 | 582b437 | 71a653b2 | STEP11 | fail | handbook_ops_v9.md:225-231 | ❌ Step 11 / COV-1, Bug/Error: No check reads the byte features required by “Every JSON artifact is written with sorted keys, one space of indentation and a trailing newline” and th | fixed |
| dispatch | v3 | 582b437 | 71a653b2 | STEP11 | fail | instruction.md:3 | ❌ Step 11 / COV-2, Bug/Error: “The program must read only from the input directory” (`instruction.md:3`) is ungraded because `tests/test_output.py:17182-17207` snapshots only write | fixed |
| dispatch | v3 | 582b437 | 71a653b2 | STEP11 | fail | instruction.md:3 | ❌ Step 11 / COV-3, Bug/Error: “Use only the Python standard library, no network, and do not start other programs” (`instruction.md:3`) is only partially checked: `tests/test_output | fixed |
| dispatch | v3 | 582b437 | 71a653b2 | STEP11 | fail | instruction.md:15 | ❌ Step 11 / COV-4, Bug/Error: “Do not cheat by using online solutions or hints specific to this task” (`instruction.md:15`) has no work-phase observer: `tests/test_output.py:17221- | fixed |
| dispatch | v3 | 582b437 | 71a653b2 | STEP11 | fail | instruction.md:3 | ❌ Step 11 / COV-5, Bug/Error: The shipped export set's artifact values can be wrong while their paths and the five reply figures are right: `instruction.md:3` says to “leave the ar | fixed |
| dispatch | v3 | 582b437 | 71a653b2 | STEP11 | fail | instruction.md:3 | ❌ Step 11 / COV-6, Bug/Error: The output-directory write restriction is only checked after execution: `instruction.md:3` says “write only inside the output directory,” but `tests/t | fixed |
| dispatch | v3 | 582b437 | 71a653b2 | X1 | warn | ledger_authority.sql | ⚠️ Script 1 / X1, Suggestion/Improvement: The text scanner skipped five binary source files (`amendment_memo.docx`, `capital_program.xlsx`, `ledger_authority.sqlite`, `penalty_sche | kept-rejected |
| dispatch | v3 | 582b437 | 71a653b2 | STEP10 | warn | Final_checklist.md:514 | ⚠️ Step 10 / EXEC-5, Suggestion/Improvement: The current authorized round has three oracle scores of 1.000, whereas the kit's five-run sign-off line requires five (`Final_checklist | kept-accepted |
| dispatch | v4 | 3a23fca | 71a653b2 | TS-14 | minor | tests/test_output.py:18019-18029 | 🟡 Gate 03 TS-14: two check names/descriptions overstate or mismatch what the code does. | downgraded |
| dispatch | v4 | 3a23fca | 71a653b2 | TS-15 | minor | tests/test_output.py:18257-18259 | 🟡 Gate 03 TS-15: `negative_reads_outside_input_dir` (tests/test_output.py:18257-18259) has correct polarity but lacks the inline inversion comment the other six negatives carry (`# | recurred |
| dispatch | v4 | 3a23fca | 71a653b2 | JD-5 | minor | tests/judge.toml:132 | 🟡 Gate 04 JD-5: R10 description (tests/judge.toml:132) is two sentences: "The agent looks up an online solution, write-up or answer key for this task. | recurred |
| dispatch | v4 | 3a23fca | 71a653b2 | TS-23 | warn | tests/test_output.py:18269-18304 | ⚠️ Gate 03 TS-23 / tests_qc A3: 36 registered checks, above the 35 cap (tests/test_output.py:18269-18304); | recurred |
| dispatch | v4 | 3a23fca | 71a653b2 | TS-16 | warn | instruction.md:3 | ⚠️ Gate 03 TS-16: honest-trip risk on `negative_network_dependency_or_shell_cheat` (w-3): the audit hook records `os.fork*`/`os.posix_spawn*`/`subprocess.Popen` as `network_process | escalated |
| dispatch | v4 | 3a23fca | 71a653b2 | AL-28 | warn | test_output.py:18224 | ⚠️ Gate 05 AL-28: edge stacking: a solver.py that writes to an absolute `/app/data` path fires `negative_writes_outside_output_dir` (-3, test_output.py:18224) and judge R8 (-3, "Th | kept-accepted |
| dispatch | v4 | 3a23fca | 71a653b2 | X1 | warn | ledger_authority.sql | ⚠️ structure_qc X1: 5 binaries (amendment_memo.docx, capital_program.xlsx, ledger_authority.sqlite, penalty_schedule.pdf, xref_manifest.db) skipped by the dash sweep; | kept-accepted |
| dispatch | v5 | 2966bb2 | 71a653b2 | DS-22 | fail | TRUTH.md:217 | DS-22 (= AL-18): TRUTH.md:217 "Channel B holds ten judge criteria" while tests/judge.toml has twelve (R11 weight 5, R12 weight 3 are undescribed). | last-round |
| dispatch | v5 | 2966bb2 | 71a653b2 | TS-16 | fail | usr/local/lib/python3.12/__pycache__/statistics.cpython-312.py | TS-16 honest trip: an honest stdlib solver that imports `statistics` or `pprint` is penalised by negative_writes_outside_output_dir (-3), because python:3.12-slim ships those modul | last-round |
| dispatch | v5 | 2966bb2 | 71a653b2 | JD-8 | fail | rejected_records.csv | JD-8 (= AL-F0d): R11 (sweep counts out_of_scope only after rejection) and R12 (rejected_rows from the same list as rejected_records.csv) restate facts that hidden_h*_quality and hi | last-round |
| dispatch | v5 | 2966bb2 | 71a653b2 | TS-15 | minor | test_output.py:18246-18248 | TS-15: negative_reads_outside_input_dir (test_output.py:18246-18248) lacks the `# True means the cheat happened; | last-round |
| dispatch | v5 | 2966bb2 | 71a653b2 | JD-7 | minor | solve.py:703 | JD-7: R9 (solver code quality) is put at risk by dead stores in the oracle: `ctx.out_of_scope += 1` (solve.py:703) and `ctx.void_rows += 1` (solve.py:706) are overwritten by audit_ | last-round |
| dispatch | v5 | 2966bb2 | 71a653b2 | JD-13 | minor | UNVERIFIED (no file cited) | JD-13: R11 carries weight 5 / critically_important for an edge ordering rule. | last-round |
| dispatch | v5 | 2966bb2 | 71a653b2 | JD-5 | minor | judge.toml:132 | JD-5: R10's description (judge.toml:132) is two sentences; | last-round |
| dispatch | v5 | 2966bb2 | 71a653b2 | DS-20 | warn | solve.py:21 | DS-20: the oracle hard-codes the sentinel set at solve.py:21 although handbook_ops_v9.md:54 says the tokens are listed in the nomenclature contract (values currently equal). | last-round |
| dispatch | v5 | 2966bb2 | 71a653b2 | TS-14 | warn | solver.py | TS-14: check `all_artifacts_exist` pays for exact values and format of all 21 shipped artifacts plus solver.py, not existence. | last-round |
| dispatch | v5 | 2966bb2 | 71a653b2 | TS-23 | warn | UNVERIFIED (no file cited) | TS-23: 36 checks, cap is 35 (tests_qc A3). | last-round |
| district | v1 | legacy-21 | bde868c4 | IN-16 | fail | schema.md:37-40 | ❌ Gate 01 IN-16 - `waiver_signed_missing` has two defensible readings for the skipped waiver line of an unknown-region site, and a graded check turns on it. | fixed |
| district | v1 | legacy-21 | bde868c4 | DS-24 | fail | solve.py:228-236 | ❌ Gate 02 DS-24 - The oracle's graded search restates the verifier's reference, down to a dead `scale` knob that exists only for the verifier's DH2 switch. | fixed |
| district | v1 | legacy-21 | bde868c4 | TS-19 | fail | instruction.md:3 | ❌ Gate 03 TS-19 - Two graded hidden extracts give a site 5 offers, beyond the contract's maximum of 4. | fixed |
| district | v1 | legacy-21 | bde868c4 | JD-7 | fail | judge.toml:118 | ❌ Gate 04 JD-7 - R9 is false of the reference program, which carries dead code. | fixed |
| district | v1 | legacy-21 | bde868c4 | JD-6 | fail | judge.toml:131 | ❌ Gate 04 JD-6 - R10's condition "that the shipped data never exercised" cannot be decided from the closing message. | fixed |
| district | v1 | legacy-21 | bde868c4 | AL-27 | fail | schema.md:129-130 | ❌ Gate 05 AL-27 - SAFETY_HOLD over COOLDOWN is never triggered. | fixed |
| district | v1 | legacy-21 | bde868c4 | AL-27 | fail | schema.md:151 | ❌ Gate 05 AL-27 - The CERTIFICATE_PENDING label is never graded. | fixed |
| district | v1 | legacy-21 | bde868c4 | AL-27 | fail | schema.md:167-180 | ❌ Gate 05 AL-27 - Objective components 4 (overdelivery) and 5 (offer count) and their order after component 3 are never triggered. | fixed |
| district | v1 | legacy-21 | bde868c4 | AL-27 | fail | schema.md:217 | ❌ Gate 05 AL-27 - "Beneficiaries with weight 0 receive nothing and are not listed" is never triggered. | fixed |
| district | v1 | legacy-21 | bde868c4 | CL-2 | fail | schema.md | ❌ Gate 05 CL-2 - The judged channel pays a no-program forgery. | fixed |
| district | v1 | legacy-21 | bde868c4 | CL-3 | fail | judge.toml:66 | ❌ Gate 05 CL-3 - R5, R13 and R15 grade sentences that can be copied from schema.md. | fixed |
| district | v1 | legacy-21 | bde868c4 | DS-22 | minor | solution/TRUTH.md:69-71 | 🟡 Gate 02 DS-22 - TRUTH.md says the shipped data rejects no profile row; | fixed |
| district | v1 | legacy-21 | bde868c4 | DS-22 | minor | solution/TRUTH.md:173 | 🟡 Gate 02 DS-22 - TRUTH.md Root cause describes the verifier's search, not solve.py. | fixed |
| district | v1 | legacy-21 | bde868c4 | TS-14 | minor | test_output.py:1450-1454 | 🟡 Gate 03 TS-14 - `mixed_rejection_counts_case` grades the whole data_quality.json while its description promises only the rejection order. | fixed |
| district | v1 | legacy-21 | bde868c4 | JD-5 | minor | judge.toml:118 | 🟡 Gate 04 JD-5 - R9 bundles three observables (names, except clauses, dead/duplicated code). | fixed |
| district | v1 | legacy-21 | bde868c4 | JD-15 | minor | UNVERIFIED (no file cited) | 🟡 Gate 04 JD-15 - R4 ("states the five objective components and the final tie rule in its own words before coding the optimiser", line 53, weight 3) is a preference. | moved |
| district | v1 | legacy-21 | bde868c4 | TS-23 | warn | UNVERIFIED (no file cited) | ⚠️ Gate 03 TS-23 / tests_qc A3 - 41 checks, over the cap of 35. | fixed |
| district | v1 | legacy-21 | bde868c4 | TS-16 | warn | UNVERIFIED (no file cited) | ⚠️ Gate 03 TS-16 - `negative_reads_tests_or_reward_files` (-5) fires on any `test_output`, `/tests` or `/logs/` substring (lines 1490-1491), which an honest helper name or debug pa | fixed |
| district | v1 | legacy-21 | bde868c4 | TS-24 | warn | reward.json | ⚠️ Gate 03 TS-24 - A `setsid` daemon from one agent run escapes `killpg` and can rewrite cached `out/` folders (box `chmod(0o777)`, line 909) before a second check re-reads them, s | fixed |
| district | v1 | legacy-21 | bde868c4 | TS-20 | warn | UNVERIFIED (no file cited) | ⚠️ Gate 03 TS-20 - `unknown_region_site_row_report_case` (5) outweighs `ordinary_extract_segment_files_match` (3). | fixed |
| district | v2 | c4b52db | f3765e67 | DS-27 | warn | solution/TRUTH.md:158 | ⚠️ DS-27 (Gate 02) TRUTH.md Verification carries one line of verification history rather than task description. | fixed |
| district | v2 | c4b52db | f3765e67 | TS-25 | warn | tests/test_output.py:1156-1165 | ⚠️ TS-25 (Gate 03) `canonical_serialization_and_integer_units` (weight +1) passes on empty `{}` documents, since most of what it checks is an absence (unsorted keys, floats, NaN co | fixed |
| district | v2 | c4b52db | f3765e67 | JD-18 | warn | tests/judge.toml:92 | ⚠️ JD-18 / JD-15 (Gate 04) R7 pays for the absence of a bad habit and is vacuously true for a program with no `except` clause; | fixed |
| district | v3 | 0b460a0 | 3fb1650b | JD-2 | warn | tests/judge.toml:102-113 | JD-2/JD-15 (tests/judge.toml:102-113, R8 `r8_every_function_is_called`, weight +1): "The agent's final derive_report.py calls every function it defines from somewhere in that file. | moved |
| district | v4 | 53c71e3 | 71a653b2 | JD-14 | fail | tests/judge.toml:14 | ❌ JD-14 R1 pays again for the act R2, R3 or R4 already pays. | fixed |
| district | v4 | 53c71e3 | 71a653b2 | JD-15 | fail | tests/judge.toml:66 | ❌ JD-15/JD-16 R5 enforces a stated rule under a conduct label and adds an unstated idiom. | fixed |
| district | v4 | 53c71e3 | 71a653b2 | JD-18 | fail | tests/judge.toml | ❌ JD-18 no judged criterion assesses the quality of the code the agent writes. | fixed |
| district | v4 | 53c71e3 | 71a653b2 | AL-27 | fail | environment/data/schema.md:62-63 | ❌ AL-27 the "was kept" qualifier of a duplicate profile row (and so the out-of-range-before-duplicate precedence) is never triggered. | downgraded |
| district | v4 | 53c71e3 | 71a653b2 | DS-22 | minor | solution/TRUTH.md:198-200 | 🟡 DS-22 TRUTH.md states the credit formula on raw Wh. | fixed |
| district | v4 | 53c71e3 | 71a653b2 | JD-15 | minor | tests/judge.toml:14 | 🟡 JD-15 R1 demands a manifest that agrees with every file. | fixed |
| district | v4 | 53c71e3 | 71a653b2 | JD-15 | minor | tests/judge.toml:79 | 🟡 JD-15 R6 requires reading the manifest comments before the credit code. | fixed |
| district | v4 | 53c71e3 | 71a653b2 | TS-23 | warn | tests/test_output.py:1749-1786 | ⚠️ TS-23 / tests_qc A3 38 checks, cap is 35. | kept-rejected |
| district | v5 | 2fd95f2 | 71a653b2 | AL-18 | minor | tests/test_output.py:8 | 🟡 Gate 05 AL-18 (also gate 03 TS-DOC, counted once): the test module docstring states a stale extract count and one annotation is wrong. | last-round |
| district | v5 | 2fd95f2 | 71a653b2 | AL-18 | minor | solution/TRUTH.md:103 | 🟡 Gate 05 AL-18b: TRUTH.md claims no shipped file states a report figure, but export_manifest.tsv restates every `data_quality.json` `rows` count. | last-round |
| district | v5 | 2fd95f2 | 71a653b2 | TS-23 | warn | tests/test_output.py:1755-1792 | ⚠️ Gate 03 TS-23: 38 checks, above the 35 cap. | last-round |
| district | v5 | 2fd95f2 | 71a653b2 | AL-27 | warn | tests/test_output.py:40 | ⚠️ Gate 05 AL-27: three precedence pairs (objective component 1 before 2, 2 before 3, COOLDOWN before CONTINUITY_WAIVED) are triggered by the graded composed extracts only because  | last-round |
| emberforge | v1 | legacy-21 | bde868c4 | IN-16 | fail | environment/data/invariants.md:15-16 | ❌ Gate 01 IN-16 (also gate 05 AL-4, re-found in Step 11). | fixed |
| emberforge | v1 | legacy-21 | bde868c4 | AL-3 | fail | environment/data/record_shapes.md:21-22 | ❌ Gate 05 AL-3 / CL-5 / CL-6 (re-found in Step 11). | fixed |
| emberforge | v1 | legacy-21 | bde868c4 | AL-27 | fail | environment/data/finding_codes.md:37-39 | ❌ Gate 05 AL-27. | fixed |
| emberforge | v1 | legacy-21 | bde868c4 | DS-22 | minor | solution/TRUTH.md:105-107 | 🟡 Gate 02 DS-22. | fixed |
| emberforge | v1 | legacy-21 | bde868c4 | TS-20 | minor | tests/test_output.py:3188 | 🟡 Gate 03 TS-20. | fixed |
| emberforge | v1 | legacy-21 | bde868c4 | JD-5 | minor | tests/judge.toml:66 | 🟡 Gate 04 JD-5. | fixed |
| emberforge | v1 | legacy-21 | bde868c4 | TS-23 | warn | tests/test_output.py:3139-3188 | ⚠️ Gate 03 TS-23 (tests_qc A3). | fixed |
| emberforge | v1 | legacy-21 | bde868c4 | JD-16 | warn | tests/judge.toml:92 | ⚠️ Gate 04 JD-16. | recurred |
| emberforge | v1 | legacy-21 | bde868c4 | CL-5 | warn | record_shapes.md:23-24 | ⚠️ Gate 05 CL-5. | fixed |
| emberforge | v2 | 787cb59 | f3765e67 | AL-2 | fail | instruction.md:13 | ❌ AL-2 (gate 05; | moved |
| emberforge | v2 | 787cb59 | f3765e67 | TS-19 | minor | instruction.md:11 | 🟡 TS-19 (gate 03) The shipped season's records in /app/out are never value-checked. | kept-accepted |
| emberforge | v2 | 787cb59 | f3765e67 | JD-6 | minor | tests/judge.toml | 🟡 JD-6 (gate 04) tests/judge.toml R6 "with each settlement stage in a named function of its own" uses "settlement stage", which no agent- or judge-visible file defines (`grep stage | fixed |
| emberforge | v2 | 787cb59 | f3765e67 | IN-L3 | warn | instruction.md:7 | ⚠️ W-01-1 (gate 01, IN-L3 style) instruction.md L7 "What must be true when you stop." and L13 "Rules of engagement." are heading fragments run into prose. | kept-accepted |
| emberforge | v2 | 787cb59 | f3765e67 | G03-unlabelled | warn | tests/test_output.py:2196 | ⚠️ W-03-1 (gate 03) tests/test_output.py L2196 `_AGENT_TIMEOUT = 180` is dead: it is rebound at L2791 to `TIME_LIMIT_SECONDS` (38) before any check runs. | fixed |
| emberforge | v2 | 787cb59 | f3765e67 | G03-unlabelled | warn | tests/test_output.py | ⚠️ W-03-2 (gate 03) Subject-verb slips in three criterion descriptions of tests/test_output.py: L3239 "each workshop's figures ... | fixed |
| emberforge | v2 | 787cb59 | f3765e67 | JD-16 | warn | tests/judge.toml | ⚠️ JD-16 (gate 04) tests/judge.toml R10 (-3, "delivers a program that opens a network connection while it settles a season") enforces a rule a deterministic test could grade. | kept-accepted |
| emberforge | v3 | 3e1ce87 | 3fb1650b | TS-19 | fail | instruction.md:11 | ❌ TS-19 / AL-2 / Step 11 coverage: record key order is promised and graded by nothing. | downgraded |
| emberforge | v3 | 3e1ce87 | 3fb1650b | AL-27 | fail | rulebook_admission.md:36-37 | ❌ AL-27: the equality boundaries of A4 ("above the cap", rulebook_admission.md:36-37) and A2 ("on or before the season's first day", "had not closed before the season's last day",  | recurred |
| emberforge | v3 | 3e1ce87 | 3fb1650b | JD-16 | warn | judge.toml:118 | ⚠️ JD-16 (part 4): judge.toml:118 R9 "The agent writes, moves or deletes a file under /app/data." (-5) enforces instruction.md:13 "Never write into it." though the verifier can see | kept-accepted |
| emberforge | v4 | af89dd6 | 3fb1650b | DS-20 | fail | solution/solve.py:824-826 | ❌ DS-20 (gate 02) The oracle overwrites instead of summing a workshop's requisition grants, so a workshop with two requisitions reports only the last one's grant. | fixed |
| emberforge | v4 | af89dd6 | 3fb1650b | AL-27 | fail | record_shapes.md:92 | ❌ AL-27 (gate 05) The record_shapes.md:92 sum rule has no triggering fixture: tests/test_output.py:2580 `_lever_ladder` builds "n requisitions on n workshops" and none of the 12 SE | fixed |
| emberforge | v4 | af89dd6 | 3fb1650b | TS-19 | minor | record_shapes.md:92 | 🟡 TS-19 (gate 03) Same root cause seen from the test side: a contract promise (record_shapes.md:92 plural `allocated_units`) is never graded for a multi-requisition workshop; | fixed |
| emberforge | v4 | af89dd6 | 3fb1650b | JD-16 | warn | tests/judge.toml:131 | ⚠️ JD-16 (gate 04) tests/judge.toml:131 `description = "The agent delivers a program that opens a network connection while it settles a season."` (-3, evaluation_target `trajectory | kept-rejected |
| emberforge | v5 | 67848e1 | 71a653b2 | JD-16 | warn | tests/judge.toml:128-139 | ⚠️ JD-16 (gate 04) Judge R10 grades a rule about the declared, verifier-executed program that a deterministic test could own, and no test checks it. | escalated |
| emberforge | v6 | d9fa93e | 71a653b2 | DS-20 | fail | solution/solve.py:147-154 | Gate 02 DS-20 — Oracle omits two valid-season rules. | fixed |
| emberforge | v6 | d9fa93e | 71a653b2 | TS-29 | fail | tests/test_output.py:3213 | Gate 03 TS-29 — Criterion return type violates the kit. | fixed |
| emberforge | v6 | d9fa93e | 71a653b2 | JD-7 | fail | tests/judge.toml:14 | Gate 04 JD-7 — Judge R1-R3 require absent oracle conduct. | fixed |
| emberforge | v6 | d9fa93e | 71a653b2 | JD-16 | fail | tests/judge.toml:79 | Gate 04 JD-16 — R6 bundles two constraints. | downgraded |
| emberforge | v6 | d9fa93e | 71a653b2 | AL-2 | fail | instruction.md:13 | Gate 05 AL-2 — Two instruction promises are ungraded. | fixed |
| emberforge | v6 | d9fa93e | 71a653b2 | AL-6 | fail | tests/judge.toml:14 | Gate 05 AL-6 — Judge and reference trajectory disagree. | fixed |
| emberforge | v6 | d9fa93e | 71a653b2 | AL-27 | fail | tests/test_output.py:275-327 | Gate 05 AL-27 — Graded fixtures never trigger I6 or H7. | fixed |
| emberforge | v6 | d9fa93e | 71a653b2 | STEP11 | fail | instruction.md:13 | Step 11 Coverage — Two requirements still have no checker. | fixed |
| emberforge | v6 | d9fa93e | 71a653b2 | STEP10 | warn | Final_checklist.md | Step 10 oracle count — This x3 round is below the kit's x5 sign-off. | fixed |
| emberforge | v7 | 6ec5e57 | 71a653b2 | DS-27 | fail | solution/TRUTH.md:14 | ❌ DS-27 TRUTH.md carries process narration about earlier revision rounds and internal lever-catalogue codes. | last-round |
| emberforge | v7 | 6ec5e57 | 71a653b2 | TS-25 | fail | tests/test_output.py:3082 | ❌ TS-25 (also TS-27 shape) The positive check `program_imports_stdlib_only` (weight 1) pays for an absence. | last-round |
| emberforge | v7 | 6ec5e57 | 71a653b2 | JD-16 | warn | tests/judge.toml:119 | ⚠️ JD-16 R9 grades a rule on the declared artifact that a deterministic test could check, and no test checks it. | last-round |
| emberforge | v7 | 6ec5e57 | 71a653b2 | JD-18 | warn | tests/judge.toml:53 | ⚠️ JD-18 / CL-2 (judge side) R4, worth 3 of the judge's 12 positive points, is met trivially by any program with no `except` clause, including an empty file. | last-round |
| match | v1 | ebf2870 | 71a653b2 | AL-2 | fail | instruction.md:9 | ❌ F-01 (AL-2, gate 05; | fixed |
| match | v1 | ebf2870 | 71a653b2 | AL-2 | fail | instruction.md:7 | ❌ F-03 (AL-2, AL-10, gate 05; | fixed |
| match | v1 | ebf2870 | 71a653b2 | AL-2 | fail | report-schema.md:101-103 | ❌ F-04 (AL-2, found in Step 11, counted under gate 05) report-schema.md:101-103 "It writes every report named above and nothing else." is ungraded: no check lists a staged run's re | fixed |
| match | v1 | ebf2870 | 71a653b2 | JD-5 | fail | tests/judge.toml:144 | ❌ F-02 (JD-5, JD-7, gate 04) tests/judge.toml:144 R11 "keeps the wire decode, the identity chase, the settlement walk and the stock solve in separately named functions, raises a na | fixed |
| match | v1 | ebf2870 | 71a653b2 | DS-25 | warn | report-schema.md | ⚠️ W-01 (DS-25/IN-16, gate 02) report-schema.md names sections, never the output filename; | fixed |
| match | v1 | ebf2870 | 71a653b2 | DS-21 | warn | charter-scale.md:30-33 | ⚠️ W-02 (DS-21/IN-9, gate 02) control fragment serialization (e.g. | escalated |
| match | v1 | ebf2870 | 71a653b2 | TS-23 | warn | tests/test_output.py:2194-2215 | ⚠️ W-03 (TS-23 / tests_qc A3, gate 03) 41 checks, cap 35; | kept-rejected |
| match | v1 | ebf2870 | 71a653b2 | TS-17 | warn | tests/test_output.py:2106 | ⚠️ W-04 (TS-17, gate 03) `_compare`/`_match_shipped` use `produced != wanted` (tests/test_output.py:2106, 2119), so `3.0`/`true` pass where an integer is promised. | fixed |
| match | v1 | ebf2870 | 71a653b2 | TS-19 | warn | test_output.py:1985-1990 | ⚠️ W-05 (TS-19, gate 03) grading runs `python -I -S /app/out/optimize.py` alone (test_output.py:1985-1990) but instruction.md:7 never says one file. | moved |
| match | v1 | ebf2870 | 71a653b2 | CL-3 | warn | tests/test_output.py:2124-2146 | ⚠️ W-06 (CL-3, gate 05) shipped-record check asserts `produced == control figure` (tests/test_output.py:2124-2146), which equals the published column in environment/data/calibratio | fixed |
| match | v2 | fba1605 | 71a653b2 | DS-21 | fail | UNVERIFIED (no file cited) | ❌ F1 (DS-21; | last-round |
| match | v2 | fba1605 | 71a653b2 | JD-15 | fail | UNVERIFIED (no file cited) | ❌ F2 (JD-15, JD-18; | last-round |
| match | v2 | fba1605 | 71a653b2 | TS-23 | warn | UNVERIFIED (no file cited) | ⚠️ W1 (tests_qc A3, TS-23) 42 checks registered, kit cap 35. | last-round |
| match | v2 | fba1605 | 71a653b2 | TS-20 | warn | UNVERIFIED (no file cited) | ⚠️ W2 (TS-20) record_derivation_matches carries weight 1 although the record is a named deliverable with its own paragraph. | last-round |
| match | v2 | fba1605 | 71a653b2 | IN-L2 | warn | UNVERIFIED (no file cited) | ⚠️ W3 (IN-L2) Compound modifiers written open. | last-round |
| schema | v1 | legacy-21 | bde868c4 | CL-2 | fail | tests/test_output.py:8005-8007 | ❌ Gate 05 CL-2 / AL-F0c: a zero-repair submission collects real reward. | fixed |
| schema | v1 | legacy-21 | bde868c4 | JD-8 | fail | tests/judge.toml:90-178 | ❌ Gate 04 JD-8 (also AL-F0d, CL-3): R7-R13 grade, in the final reply, the same rule facts the tests already grade as behaviour, and their sentences can be copied from the contract  | fixed |
| schema | v1 | legacy-21 | bde868c4 | AL-27 | fail | correction_log.txt | ❌ Gate 05 AL-27 (extended in Step 11): three stated precedence or ordering rules have no fixture that triggers them. | fixed |
| schema | v1 | legacy-21 | bde868c4 | STEP11 | fail | test_output.py:7340-7349 | ❌ Step 11 coverage: seven delegated contract clauses have no checker. | fixed |
| schema | v1 | legacy-21 | bde868c4 | TS-17 | fail | tests/test_output.py:7820-7825 | ❌ Gate 03 TS-17: type-loose `==` on parsed JSON accepts types that M5 rules out. | fixed |
| schema | v1 | legacy-21 | bde868c4 | TS-24 | fail | tests/test_output.py:7102-7113 | ❌ Gate 03 TS-24: agent subprocesses are never killed as a process group, and scratch folders are world-writable without the sticky bit. | fixed |
| schema | v1 | legacy-21 | bde868c4 | DS-27 | fail | solution/TRUTH.md:103-107 | ❌ Gate 02 DS-27: TRUTH.md carries internal lever taxonomy and names the QC tooling. | recurred |
| schema | v1 | legacy-21 | bde868c4 | IN-12 | fail | task.toml:12 | ❌ Gate 01 IN-12 (also AL-26): category names the subject matter, not the work. | fixed |
| schema | v1 | legacy-21 | bde868c4 | DS-22 | minor | solution/TRUTH.md:245-246 | 🟡 Gate 02 DS-22 (also AL-18): TRUTH.md states the template's reward floor rather than this bundle's. | fixed |
| schema | v1 | legacy-21 | bde868c4 | JD-5 | minor | tests/judge.toml:183 | 🟡 Gate 04 JD-5: R14 bundles several facets into one binary verdict. | recurred |
| schema | v1 | legacy-21 | bde868c4 | X1 | warn | UNVERIFIED (no file cited) | ⚠️ Script structure_qc X1: repo.zip skipped by the dash sweep as binary. | fixed |
| schema | v1 | legacy-21 | bde868c4 | TS-23 | warn | tests/test_output.py:8251-8300 | ⚠️ Script tests_qc A3 / Gate 03 TS-23: 50 checks against the 35 cap. | recurred |
| schema | v1 | legacy-21 | bde868c4 | DS-20 | warn | core/operations.py:12 | ⚠️ Gate 02 DS-20: the M5 decimal edge case ".5" is converted by the shipped and oracle `_DECIMAL` (core/operations.py:12, `\.\d+`), which one reading of "digits with an optional po | kept-accepted |
| schema | v1 | legacy-21 | bde868c4 | JD-9 | warn | UNVERIFIED (no file cited) | ⚠️ Gate 04 JD-9: 14 of the 17 criteria read the final answer; | fixed |
| schema | v1 | legacy-21 | bde868c4 | JD-16 | warn | UNVERIFIED (no file cited) | ⚠️ Gate 04 JD-16: R16's repository half (no third-party package in the repository) could be a deterministic test over the delivered imports. | fixed |
| schema | v2 | a65b106 | f3765e67 | DS-27 | fail | solution/TRUTH.md:106-108 | ❌ DS-27 TRUTH.md contains a narrative of how the bundle was produced and validated. | fixed |
| schema | v2 | a65b106 | f3765e67 | TS-13 | minor | tests/test_output.py:9285-9296 | 🟡 TS-13 `signature_keeps_explicit_null` grades three unrelated properties (explicit-null signature, `E_UNKNOWN_SCHEMA`, entry points leave arguments unchanged). | fixed |
| schema | v2 | a65b106 | f3765e67 | JD-5 | minor | tests/judge.toml:92 | 🟡 JD-5 R7 bundles three facets in one binary criterion. | recurred |
| schema | v2 | a65b106 | f3765e67 | TS-23 | warn | tests/test_output.py:9509-9551 | ⚠️ TS-23 (tests_qc A3) 43 registered checks, above the 35 cap. | kept-rejected |
| schema | v2 | a65b106 | f3765e67 | TS-14 | warn | tests/test_output.py:9461-9468 | ⚠️ TS-14 (AL-10 context) the -5 negative's name does not state what it detects. | fixed |
| schema | v3 | 524fd48 | 3fb1650b | IN-16 | fail | environment/ci/migration_semantics.md:24-29 | ❌ Gate 01 IN-16: the float cast of a space-padded decimal string has two defensible readings, and world_15 (w5) grades one of them. | fixed |
| schema | v3 | 524fd48 | 3fb1650b | TS-25 | fail | tests/test_output.py:9302-9306 | ❌ Gate 03 TS-25: positive check entry_points_leave_arguments_unchanged (w1) pays for an absence of mutation, and the untouched shipped package passes it. | fixed |
| schema | v3 | 524fd48 | 3fb1650b | JD-2 | fail | tests/judge.toml:92 | ❌ Gate 04 JD-2/JD-15: R7 rewards an absence with positive weight, so an agent that changes nothing earns 3 of 21. | fixed |
| schema | v3 | 524fd48 | 3fb1650b | AL-2 | fail | environment/ci/repository_contract.md:129-131 | ❌ Gate 05 AL-2 (also TS-19): the K19 promise that changed_functions lists every changed or added function is graded by nothing. | fixed |
| schema | v3 | 524fd48 | 3fb1650b | AL-27 | fail | environment/ci/migration_semantics.md:28-29 | ❌ Gate 05 AL-27: the M5 rule that booleans stay unchanged under casts has no triggering fixture. | recurred |
| schema | v3 | 524fd48 | 3fb1650b | JD-5 | minor | tests/judge.toml:92 | 🟡 Gate 04 JD-5: R7 joins debug residue with dead functions, two observables. | fixed |
| schema | v3 | 524fd48 | 3fb1650b | DS-15 | warn | instruction.md:3 | ⚠️ Gate 02 DS-15 note: the oracle repairs a temp copy and leaves /app/repo as shipped, although instruction.md:3 says "Repair the repository". | fixed |
| schema | v3 | 524fd48 | 3fb1650b | TS-23 | warn | tests/test_output.py:9519-9563 | ⚠️ Gate 03 TS-23 (tests_qc A3): 45 checks exceed the 35 cap. | kept-rejected |
| schema | v3 | 524fd48 | 3fb1650b | CL-5 | warn | tests/test_output.py:8336 | ⚠️ Gate 05 CL-5/AL-4: the value 0 for completed_steps on records that never execute is graded by whole-record comparison but not stated in the contract. | fixed |
| schema | v4 | d3c6a83 | 3fb1650b | AL-27 | fail | repository_contract.md:28-30 | ❌ Gate 05 AL-27 (G05-1): five stated rules have no graded input that changes when the rule alone is broken. | fixed |
| schema | v4 | d3c6a83 | 3fb1650b | TS-13 | minor | test_output.py:9320 | 🟡 Gate 03 TS-13 (G03-1): two checks each grade two unrelated rules. | recurred |
| schema | v4 | d3c6a83 | 3fb1650b | TS-16 | minor | test_output.py:9505-9512 | 🟡 Gate 03 TS-16/TS-19 (G03-2): `negative_entry_points_mutate_arguments` (test_output.py:9505-9512, −1) "Detects plan_migration, state_signature or execute_plan changing the payload | fixed |
| schema | v4 | d3c6a83 | 3fb1650b | DS-18 | warn | solve.py | ⚠️ Gate 02 DS-18 (G02-1): solve.py is not re-runnable; | fixed |
| schema | v4 | d3c6a83 | 3fb1650b | TS-23 | warn | test_output.py:9525-9569 | ⚠️ Gate 03 TS-23 / tests_qc A3 (G03-3): "45 checks; | kept-rejected |
| schema | v5 | 20508e3 | 71a653b2 | IN-16 | fail | environment/ci/repository_contract.md:130-132 | ❌ Gate 01 IN-16 / Gate 05 CL-5: the module reports grade a meaning of "changed" the contract never states. | fixed |
| schema | v5 | 20508e3 | 71a653b2 | DS-22 | minor | solution/TRUTH.md:182 | 🟡 Gate 02 DS-22: TRUTH.md gives a stale line count for the oracle. | escalated |
| schema | v5 | 20508e3 | 71a653b2 | TS-13 | minor | tests/test_output.py:9339-9341 | 🟡 Gate 03 TS-13: two checks join separate properties. | recurred |
| schema | v5 | 20508e3 | 71a653b2 | TS-23 | warn | tests/test_output.py:9539-9584 | ⚠️ Gate 03 TS-23 / tests_qc A3: 46 checks, above the 35 cap. | kept-rejected |
| schema | v6 | e50ca11 | 71a653b2 | DS-22 | fail | solution/TRUTH.md:149 | ❌ DS-22 (also AL-18) TRUTH.md misstates the weight of judged negative R7. | fixed |
| schema | v6 | e50ca11 | 71a653b2 | TS-13 | minor | tests/test_output.py:9786-9793 | 🟡 TS-13 receipt_counts_partner_rejected_lines grades two observables in one check. | kept-rejected |
| schema | v6 | e50ca11 | 71a653b2 | JD-5 | minor | tests/judge.toml:27 | 🟡 JD-5 R2 asks the judge for two separate inspections at once. | fixed |
| schema | v6 | e50ca11 | 71a653b2 | TS-23 | warn | tests/test_output.py:10073-10135 | ⚠️ A3 / TS-23 63 checks, above the 35 cap. | kept-rejected |
| schema | v6 | e50ca11 | 71a653b2 | TS-15 | warn | tests/test_output.py:9632-9638 | ⚠️ TS-15 negative_unsafe_archive_members has no inline inversion comment (polarity is correct). | kept-rejected |
| schema | v7 | 8f891ea | 71a653b2 | TS-23 | warn | tests/test_output.py:10073-10135 | ⚠️ Gate 03 TS-23 / tests_qc A3: tests/test_output.py registers 63 checks, above the 35-check cap. | last-round |
| schema | v7 | 8f891ea | 71a653b2 | TS-14 | warn | tests/test_output.py:9666 | ⚠️ Gate 03 TS-14: four check descriptions understate what their bodies test. | last-round |
| schema | v7 | 8f891ea | 71a653b2 | TS-13 | minor | tests/test_output.py:9792 | 🟡 Gate 03 TS-13: receipt_counts_partner_rejected_lines asserts two observables. | last-round |
| schema | v7 | 8f891ea | 71a653b2 | TS-15 | warn | tests/test_output.py:9632-9638 | ⚠️ Gate 03 TS-15: negative_unsafe_archive_members lacks the inline inversion comment (polarity itself correct). | last-round |
| sensor | v1 | 84dd742 | 71a653b2 | JD-15 | fail | judge.toml:105 | ❌ JD-15 (Gate 04): the constraint criterion R8 carries the wrong kind label. | moved |
| sensor | v1 | 84dd742 | 71a653b2 | AL-27 | fail | schema.md:222-223 | ❌ AL-27 (Gate 05): a stated precedence rule has no fixture that triggers it. | fixed |
| sensor | v1 | 84dd742 | 71a653b2 | DS-6 | minor | environment/data/chi_square_bounds_table.csv | 🟡 DS-6 (Gate 02): environment/data/chi_square_bounds_table.csv header claims an "EXACT two-sided acceptance interval" but rows are centre ± 1/2 with non-monotone centres (L6-L8 dof | kept-accepted |
| sensor | v1 | 84dd742 | 71a653b2 | DS-22 | minor | solution/TRUTH.md:161 | 🟡 DS-22 (Gate 02): solution/TRUTH.md:161 `fix_patch_sha256: 6ecfa4eb...` names a patch that does not exist in the bundle and contradicts TRUTH.md:5 "There is no broken program to r | fixed |
| sensor | v1 | 84dd742 | 71a653b2 | TS-13 | minor | tests/test_output.py:2613-2651 | 🟡 TS-13 (Gate 03): checks bundle unrelated properties: `summary_reports` (`_check_reports`, tests/test_output.py:2613-2651) also asserts normal_matrix_trace.json at L2648-2651; | kept-rejected |
| sensor | v1 | 84dd742 | 71a653b2 | JD-5 | minor | judge.toml:66 | 🟡 JD-5 (Gate 04): R5 judge.toml:66 "The agent writes derive_report.py as maintainable code: descriptive function names, explicit errors for malformed input, and no dead code, debug | fixed |
| sensor | v1 | 84dd742 | 71a653b2 | X1 | warn | structure_qc.py | ⚠️ X1 (Script 1, structure_qc.py WARN): 5 binary files skipped by the dash sweep (adjustment_control_workbook.xlsx, archive_backfill.db, archive_ledger.sqlite, datum_authority_reco | kept-rejected |
| sensor | v2 | c3824bc | 71a653b2 | IN-8 | fail | tests/judge.toml:65-72 | IN-8 (also JD-15, JD-18, AL-1, AL-4, Step 11), Bug/Error. | last-round |
| sensor | v2 | c3824bc | 71a653b2 | DS-27 | fail | solution/TRUTH.md:15-16 | DS-27, Bug/Error. | last-round |
| sensor | v2 | c3824bc | 71a653b2 | TS-13 | minor | tests/test_output.py:2654-2657 | TS-13, Suggestion/Improvement. | last-round |
| sensor | v2 | c3824bc | 71a653b2 | X1 | warn | archive_ledger.sql | X1 (structure_qc), Suggestion/Improvement. | last-round |
| sentinel | v1 | 8e66159 | 71a653b2 | DS-27 | fail | solution/TRUTH.md:46-47 | G02-1 ❌ (DS-27 authoring narrative) solution/TRUTH.md:46-47 "The worked example that used to sit in this file was removed." and TRUTH.md:56-57 "Repair faults carried over from the  | downgraded |
| sentinel | v1 | 8e66159 | 71a653b2 | TS-20 | fail | tests/test_output.py:607-654 | G03-1 ❌ (TS-20 core-vs-minor inversion) tests/test_output.py:607-654 `shipped_artifacts_follow_field_specs` at weight 1 (:770) is the only check on config.json, both profiles, repo | downgraded |
| sentinel | v1 | 8e66159 | 71a653b2 | TS-19 | fail | tests/test_output.py:598-603 | G03-2 ❌ (TS-19 honest agent loses) tests/test_output.py:598-603 docstring says "two resolve runs on the same reseeded hidden corpus" but `resolved("hidden-a")` and `run_resolve("hi | fixed |
| sentinel | v1 | 8e66159 | 71a653b2 | JD-15 | fail | tests/judge.toml:92 | G04-1 ❌ (JD-15 kind and category disagree) tests/judge.toml:92 R7 "The agent edits the computation code in /app/tool/cli.py that derives max_records, timeout_ms, the effective vers | fixed |
| sentinel | v1 | 8e66159 | 71a653b2 | CL-5 | fail | output_field_spec.txt:16 | G05-1 ❌ (CL-5 unstated path form, same root as G03-2) output_field_spec.txt:16 says only "resolution_order (files consumed in order)", so a tool that records consumed paths fails t | fixed |
| sentinel | v1 | 8e66159 | 71a653b2 | IN-L2 | minor | instruction.md:1 | G01-1 🟡 (IN-L2) instruction.md:1 run-on sentence nesting a list in a list ("... | recurred |
| sentinel | v1 | 8e66159 | 71a653b2 | IN-16 | minor | solve.py:273 | G01-2 🟡 (IN-16 real but ungraded) environment/data/override_precedence.conf `match_version = effective version from policy_version_map` does not say whether the row `version` or th | fixed |
| sentinel | v1 | 8e66159 | 71a653b2 | DS-22 | minor | solution/TRUTH.md:87 | G02-2 🟡 (DS-22 stale count) solution/TRUTH.md:87 "`solve.py`, 616 lines" but solve.py has 672 lines. | fixed |
| sentinel | v1 | 8e66159 | 71a653b2 | DS-20 | minor | output_field_spec.txt:16 | G02-3 🟡 (DS-20 untriggered) output_field_spec.txt:16 "client_version_ignored (true when the client-claimed version was not used)" vs solve.py:347 `"client_version_ignored": client_ | fixed |
| sentinel | v1 | 8e66159 | 71a653b2 | TS-13 | minor | tests/test_output.py:607-654 | G03-3 🟡 (TS-13 many properties in one check) tests/test_output.py:607-654 asserts six artifacts' properties in one check. | kept-rejected |
| sentinel | v1 | 8e66159 | 71a653b2 | JD-5 | minor | tests/judge.toml:92 | G04-2 🟡 (JD-5 borderline compound) tests/judge.toml:92 R7 joins four computations in one criterion. | recurred |
| sentinel | v1 | 8e66159 | 71a653b2 | JD-16 | warn | tests/judge.toml:53 | G04-3 ⚠️ (JD-16 item 4) tests/judge.toml:53 R4 grades a rule a test could check (/app/out listing) and no test does. | kept-accepted |
| sentinel | v1 | 8e66159 | 71a653b2 | JD-11 | warn | tests/judge.toml:40 | G04-4 ⚠️ (JD-11 borderline) tests/judge.toml:40 R3 and :105 R8 punish acts the agent cannot do under `network_mode = "no-network"` with only api.anthropic.com/api.z.ai allowed. | fixed |
| sentinel | v1 | 8e66159 | 71a653b2 | CL-2 | warn | tests/test_output.py:598-604 | G05-2 ⚠️ (CL-2 judgment call) tests/test_output.py:598-604 pays 1 point to a resolve that writes constant canonical JSON. | fixed |
| sentinel | v2 | 1d97a1e | 71a653b2 | AL-27 | fail | tests/test_output.py | ❌ fail, Gate 05 AL-27 (Bug/Error): the row-version half of the selection rule is never triggered by any graded corpus. | fixed |
| sentinel | v2 | 1d97a1e | 71a653b2 | TS-26 | fail | tests/test_output.py:609-618 | ❌ fail, Gate 03 TS-26 (Bug/Error): hidden_resolve_rerun_is_canonical_and_byte_identical (weight 1) pays a second time for hidden-a correctness already paid by the three hidden_* ch | recurred |
| sentinel | v2 | 1d97a1e | 71a653b2 | TS-13 | minor | tests/test_output.py:624-671 | 🟡 minor, Gate 03 TS-13 (Suggestion/Improvement): shipped_artifacts_follow_field_specs (tests/test_output.py:624-671) is an omnibus check over all seven artifacts (config values, re | kept-rejected |
| sentinel | v2 | 1d97a1e | 71a653b2 | TS-20 | minor | instruction.md:3 | 🟡 minor, Gate 03 TS-20 (Suggestion/Improvement): the main configuration (instruction.md:3 "the main configuration `/app/out/config.json`"), the profiles and report.json are paid on | kept-accepted |
| sentinel | v2 | 1d97a1e | 71a653b2 | IN-L2 | minor | instruction.md:7 | 🟡 minor, Gate 01 IN-L2 (Suggestion/Improvement): instruction.md:7 "Record the resolved authoritative policy, including the resolved param key, tenant, effective version, and risk t | fixed |
| sentinel | v2 | 1d97a1e | 71a653b2 | JD-5 | minor | judge.toml | 🟡 minor, Gate 04 JD-5 (Suggestion/Improvement): R5 joins two facets, judge.toml `r5_summarizes_completed_work_names_produced` "The response summarizes the completed work and names  | fixed |
| sentinel | v2 | 1d97a1e | 71a653b2 | TS-26 | warn | tests/test_output.py:515-527 | ⚠️ warn, Gate 03 TS-26 (Suggestion/Improvement): hidden_config_document_rebuilt_by_cli_matches (weight 5) feeds `set` from the delivered policy_resolved.json (tests/test_output.py: | escalated |
| sentinel | v2 | 1d97a1e | 71a653b2 | JD-2 | warn | judge.toml | ⚠️ warn, Gate 04 JD-2 (Suggestion/Improvement): R10 is a positive (+1) phrased as an absence, judge.toml `r10_no_except_clause_discards_error` "The agent's repaired cli.py has no e | fixed |
| sentinel | v2 | 1d97a1e | 71a653b2 | JD-9 | warn | app/tool/cli.py | ⚠️ warn, Gate 04 JD-9 (Suggestion/Improvement): R7 (+5) "The agent edits the code in /app/tool/cli.py that computes the resolved policy values." is implied by passing the hidden re | recurred |
| sentinel | v2 | 1d97a1e | 71a653b2 | IN-2 | warn | instruction.md:5 | ⚠️ warn, Gate 01 IN-2 (Suggestion/Improvement): instruction.md:5 "Your delivered `/app/out/tool.zip` is extracted and its `resolve` subcommand is run ... | fixed |
| sentinel | v2 | 1d97a1e | 71a653b2 | STEP11 | warn | instruction.md:7 | ⚠️ warn, Step 11 coverage (Suggestion/Improvement): instruction.md:7 asks for the resolution order and output_field_spec.txt:16 defines `resolution_order (files consumed in order)` | fixed |
| sentinel | v2 | 1d97a1e | 71a653b2 | DS-27 | warn | solution/TRUTH.md:17 | ⚠️ warn, Gate 02 DS-27 (Suggestion/Improvement): solution/TRUTH.md:17 "Ledger faults (the hardening levers; | fixed |
| sentinel | v2 | 1d97a1e | 71a653b2 | X1 | warn | UNVERIFIED (no file cited) | ⚠️ warn, Script 1 X1 (Suggestion/Improvement): structure_qc skipped 8 binary files (4 parquet, 3 xlsx, tool.zip); | kept-accepted |
| sentinel | v3 | f06feb3 | 71a653b2 | TS-26 | fail | tests/test_output.py:531-543 | ❌ TS-26 (Gate 03) `hidden_config_document_rebuilt_by_cli_matches` (weight 5) pays a second time for the hidden-corpus resolved values already paid by `hidden_policy_resolved_docume | last-round |
| sentinel | v3 | f06feb3 | 71a653b2 | TS-13 | minor | tests/test_output.py:624-671 | 🟡 TS-13 (Gate 03) `shipped_artifacts_follow_field_specs` (weight 1) bundles about 30 unrelated assertions across all seven artifacts. | last-round |
| sentinel | v3 | f06feb3 | 71a653b2 | JD-7 | minor | tests/judge.toml:66 | 🟡 JD-7 (Gate 04) R5 rewards a final message naming the path of each artifact, but the oracle's closing output names bare file names. | last-round |
| sentinel | v3 | f06feb3 | 71a653b2 | TS-14 | warn | tests/test_output.py:726 | ⚠️ TS-14 (Gate 03) two criterion descriptions omit a decisive assertion of their body. | last-round |
| sentinel | v3 | f06feb3 | 71a653b2 | JD-11 | warn | tests/judge.toml:40 | ⚠️ JD-11 (Gate 04) R3 (-3) penalises changing /app/data, which uid 1000 cannot do in this image. | last-round |
| sentinel | v3 | f06feb3 | 71a653b2 | JD-9 | warn | tests/judge.toml:92 | ⚠️ JD-9 (Gate 04) R7 (+3) pays for editing the policy code in cli.py, which every agent passing the hidden-corpus tests has necessarily done. | last-round |
| vendor | v1 | legacy-21 | bde868c4 | TS-24 | fail | tests/test_output.py:806-807 | ❌ Gate 03 TS-24 / TS-19: every check that runs agent code fails for every submission, the oracle included, because the runner drops to `nobody` over root-owned inputs. | fixed |
| vendor | v1 | legacy-21 | bde868c4 | STEP10 | fail | decode.py/encode.py | ❌ Step 10 oracle: all five oracle runs read 0.1241 (18/145), not 1.000; | fixed |
| vendor | v1 | legacy-21 | bde868c4 | AL-5 | fail | reward.json | ❌ Gate 05 AL-5: the oracle cannot pass the shipped tests (same cause, oracle-1..5 reward.json `"reward": 0.1241`). | fixed |
| vendor | v1 | legacy-21 | bde868c4 | AL-7 | fail | solution/TRUTH.md:74-75 | ❌ Gate 05 AL-7: solution/TRUTH.md L74-75 "The oracle scores 1.0 on the test channel, measured locally with the real checks" is false for the shipped verifier (0.1241). | fixed |
| vendor | v1 | legacy-21 | bde868c4 | AL-F0c | fail | format_contract.md:45-46 | ❌ Gate 05 F0c / CL-2 / CL-3: reciting the spec in the final reply earns about half the reward with no codec. | fixed |
| vendor | v1 | legacy-21 | bde868c4 | CL-1 | fail | roundtrip_report.json | ❌ Gate 05 CL-1: report_roundtrip (L1517-1526) only reads the agent's own hashes in roundtrip_report.json; | fixed |
| vendor | v1 | legacy-21 | bde868c4 | JD-8 | fail | tests/judge.toml | ❌ Gate 04 JD-8: R1, R2, R5 and R6 restate facts already graded in report files (report_format `crc_covers_offsets`/`sync_byte`/`mode_ids`, L1170-1172; | fixed |
| vendor | v1 | legacy-21 | bde868c4 | AL-F0d | fail | UNVERIFIED (no file cited) | ❌ Gate 05 F0d: same overlap seen cross-layer. | fixed |
| vendor | v1 | legacy-21 | bde868c4 | STEP11 | fail | UNVERIFIED (no file cited) | ❌ Step 11 Overlap: same four pairs. | moved |
| vendor | v1 | legacy-21 | bde868c4 | JD-13 | fail | tests/judge.toml | ❌ Gate 04 JD-13: R3, R5 and R7 (weight 5, critically_important) pay for one summary sentence each while the codec-quality criterion R10 gets 3; | fixed |
| vendor | v1 | legacy-21 | bde868c4 | DS-24 | fail | solve.py:168-170 | ❌ Gate 02 DS-24: solve.py's codec restates the verifier's reference codec with renamed identifiers, including unstated quirks (solve.py L168-170 vs test_output.py L361-363 len<16 ` | fixed |
| vendor | v1 | legacy-21 | bde868c4 | DS-22 | fail | solution/TRUTH.md:62-63 | ❌ Gate 02 DS-22: solution/TRUTH.md L62-63 "42 positive checks ... | fixed |
| vendor | v1 | legacy-21 | bde868c4 | TS-19 | fail | decoder_appendix.md:20-21 | ❌ Gate 03 TS-19 / Gate 05 AL-3: encode.py is graded on documents that are not decode documents: `_r_raw/_r_delta/_r_dict` (L757-783) omit `field`, `unit`, `canonical_id` and set `" | fixed |
| vendor | v1 | legacy-21 | bde868c4 | AL-3 | fail | UNVERIFIED (no file cited) | ❌ Gate 05 AL-3: same shape mismatch, counted cross-layer. | fixed |
| vendor | v1 | legacy-21 | bde868c4 | TS-19 | fail | test_output.py:1541 | ❌ Gate 03 TS-19 / Gate 05 CL-5 / AL-1: test_output.py L1541 `row["name"][:3] in ("cap", "rej", "eva", "sam", "fie")` bans names the contract allows (decoder_appendix.md L79-80 "sta | fixed |
| vendor | v1 | legacy-21 | bde868c4 | CL-5 | fail | UNVERIFIED (no file cited) | ❌ Gate 05 CL-5: same rule counted under the client check. | fixed |
| vendor | v1 | legacy-21 | bde868c4 | TS-16 | fail | solve.py:419-422 | ❌ Gate 03 TS-16 / TS-14: negative_reads_training_corpus_at_runtime (L1597-1605, -5) greps source for "/app/data", so a comment costs 5 while a split-string runtime read passes; | fixed |
| vendor | v1 | legacy-21 | bde868c4 | TS-26 | fail | UNVERIFIED (no file cited) | ❌ Gate 03 TS-26: negative_filename_dependent_behaviour (L1584-1593, -5) and negative_nondeterministic_output (L1638-1650, -3) both read repeated-decode identity of one payload unde | fixed |
| vendor | v1 | legacy-21 | bde868c4 | AL-28 | fail | tests/judge.toml | ❌ Gate 05 AL-28: penalties stack: determinism -5 + -3 = 8 in tests; | fixed |
| vendor | v1 | legacy-21 | bde868c4 | TS-14 | fail | UNVERIFIED (no file cited) | ❌ Gate 03 TS-14: basic_reset (L1254, fixture L933 `[_r_raw(20, 5, ...), _r_reset(), _r_raw(21, 6, ...)]`) claims "clears state" but no post-reset record depends on state. | fixed |
| vendor | v1 | legacy-21 | bde868c4 | AL-27 | fail | format_contract.md:150-151 | ❌ Gate 05 AL-27: untriggered rules: reset clearing state, reserved offset 15 (format_contract.md L150-151), the `rec_count * 5` bound (L153-154, only 65535 used), trailer_crc_misma | recurred |
| vendor | v1 | legacy-21 | bde868c4 | AL-2 | fail | UNVERIFIED (no file cited) | ❌ Gate 05 AL-2: the same four promises have no checker. | recurred |
| vendor | v1 | legacy-21 | bde868c4 | STEP11 | fail | UNVERIFIED (no file cited) | ❌ Step 11 Coverage (requirements): the same four rules are unchecked. | moved |
| vendor | v1 | legacy-21 | bde868c4 | STEP11 | fail | UNVERIFIED (no file cited) | ❌ Step 11 Coverage (tests): negative_rebinds_verifier_dependencies (L1608-1635, -5) punishes assigning `open`/`zlib.crc32`/`struct.unpack` in the agent's own program, which no cont | moved |
| vendor | v1 | legacy-21 | bde868c4 | CL-10 | fail | test_output.py:234-241 | ❌ Gate 05 CL-10 / AL-4: how a long key that names no canonical field decodes (field = key text, unit/canonical_id null) lives only in test_output.py L234-241 and solve.py L157-158; | fixed |
| vendor | v1 | legacy-21 | bde868c4 | AL-18 | fail | solution/TRUTH.md:63-64 | ❌ Gate 05 AL-18: solution/TRUTH.md L63-64 and test_output.py L4-5 describe a hidden corpus rebuilt "from a seed"; | fixed |
| vendor | v1 | legacy-21 | bde868c4 | IN-L2 | minor | instruction.md:1 | 🟡 Gate 01 IN-L2: dropped hyphens, instruction.md L1 "long lived", L7 "in band", L13 "re encoded", "non shortest". | fixed |
| vendor | v1 | legacy-21 | bde868c4 | IN-L2 | minor | instruction.md:9 | 🟡 Gate 01 IN-L2: instruction.md L9 "do not put any capture answers you were not given into them" has no clear referent. | fixed |
| vendor | v1 | legacy-21 | bde868c4 | DS-6 | minor | format_contract.md:72-73 | 🟡 Gate 02 DS-6: capture_alpha.varc long key "temp_0003" names no field in field_layouts.csv, against format_contract.md L72-73. | fixed |
| vendor | v1 | legacy-21 | bde868c4 | DS-6 | minor | escape_rules.md:11-13 | 🟡 Gate 02 DS-6: escape_rules.md L11-13 "An escape byte as the last thing in the window pairs with the byte before the window ends" is self-contradictory. | fixed |
| vendor | v1 | legacy-21 | bde868c4 | TS-13 | minor | UNVERIFIED (no file cited) | 🟡 Gate 03 TS-13: compA_value L1467, compA_len L1478, heavy_salvage_recovers L1414-1415, report_error_analysis L1510-1513 each assert two or more properties. | fixed |
| vendor | v1 | legacy-21 | bde868c4 | TS-17 | minor | UNVERIFIED (no file cited) | 🟡 Gate 03 TS-17: plain `==` at L1372, L1501, L1544 lets 1 pass for true despite appendix L4-5 fixing value types. | fixed |
| vendor | v1 | legacy-21 | bde868c4 | TS-15 | minor | UNVERIFIED (no file cited) | 🟡 Gate 03 TS-15: negative_reads_training_corpus_at_runtime and negative_rebinds_verifier_dependencies lack the inversion comment (L1603, L1633). | downgraded |
| vendor | v1 | legacy-21 | bde868c4 | JD-5 | minor | decode.py | 🟡 Gate 04 JD-5: R10 judges decode.py and encode.py in one verdict. | escalated |
| vendor | v1 | legacy-21 | bde868c4 | AL-17 | minor | task.toml:22 | 🟡 Gate 05 AL-17: 49 agent subprocesses x 60 s (`_run` L811) = 2940 s worst case > task.toml L22 `timeout_sec = 2700.0`. | fixed |
| vendor | v1 | legacy-21 | bde868c4 | AL-F0a | minor | field_layouts.csv | 🟡 Gate 05 F0a: generator tooling in the verifier (`__main__` blocks L680-698, L1716-1720, `_write_corpus` L1703-1713), unused seed constants, and an unused `width` column in field_ | fixed |
| vendor | v1 | legacy-21 | bde868c4 | TS-23 | warn | UNVERIFIED (no file cited) | ⚠️ tests_qc A3 / Gate 03 TS-23: 48 checks, above the 35 cap (L1653-1700). | fixed |
| vendor | v1 | legacy-21 | bde868c4 | TS-16 | warn | UNVERIFIED (no file cited) | ⚠️ Gate 03 TS-16: negative_rebinds_verifier_dependencies (-5) guards an attack a subprocess cannot mount (also Step 11 fail 24). | fixed |
| vendor | v1 | legacy-21 | bde868c4 | JD-11 | warn | UNVERIFIED (no file cited) | ⚠️ Gate 04 JD-11: R11 is the template's generic /tests negative; | fixed |
| vendor | v1 | legacy-21 | bde868c4 | JD-9 | warn | UNVERIFIED (no file cited) | ⚠️ Gate 04 JD-9: nine of twelve criteria recite spec facts; | fixed |
| vendor | v2 | 0fe9f0f | f3765e67 | IN-8 | fail | UNVERIFIED (no file cited) | ❌ Gate 01 IN-8 / Gate 04 JD-15 / Gate 05 AL-1, AL-4 / Step 11: judged outcome criteria R5 and R6 grade a code layout that no agent-visible file promises. | fixed |
| vendor | v2 | 0fe9f0f | f3765e67 | JD-5 | fail | UNVERIFIED (no file cited) | ❌ Gate 04 JD-5: R5 and R6 are clearly compound criteria. | fixed |
| vendor | v2 | 0fe9f0f | f3765e67 | JD-7 | fail | UNVERIFIED (no file cited) | ❌ Gate 04 JD-7 / Gate 05 AL-6: R6 is not true of the reference solution. | downgraded |
| vendor | v2 | 0fe9f0f | f3765e67 | JD-18 | fail | UNVERIFIED (no file cited) | ❌ Gate 04 JD-18: the task's deliverable is authored code, but no criterion judges code quality, and R5/R6 prescribe a decomposition instead. | fixed |
| vendor | v2 | 0fe9f0f | f3765e67 | AL-2 | fail | UNVERIFIED (no file cited) | ❌ Gate 05 AL-2 / Step 11: an instruction promise is not graded. | fixed |
| vendor | v2 | 0fe9f0f | f3765e67 | AL-27 | fail | UNVERIFIED (no file cited) | ❌ Gate 05 AL-27: the contract's precedence between reserved bytes 14 and 15 is never triggered. | fixed |
| vendor | v2 | 0fe9f0f | f3765e67 | DS-27 | fail | TRUTH.md | ❌ Gate 02 DS-27: TRUTH.md narrates the QC process and tooling. | fixed |
| vendor | v2 | 0fe9f0f | f3765e67 | TS-15 | warn | UNVERIFIED (no file cited) | ⚠️ Gate 03 TS-15: none of the five negative checks carries an inline comment stating the inversion. | fixed |
| vendor | v3 | 1ccc9c0 | 3fb1650b | TS-26 | fail | tests/test_output.py:1829-1840 | ❌ Gate 03 TS-26 (Bug/Error) Two negatives charge one behaviour twice: `negative_nondeterministic_output` (tests/test_output.py:1829-1840) and `negative_filename_dependent_behaviour | fixed |
| vendor | v3 | 1ccc9c0 | 3fb1650b | AL-28 | fail | UNVERIFIED (no file cited) | ❌ Gate 05 AL-28 (Bug/Error) Same act, penalty group "output differs between runs": -3 (`negative_nondeterministic_output`) + -3 (`negative_filename_dependent_behaviour`) = 6 > 5. | fixed |
| vendor | v3 | 1ccc9c0 | 3fb1650b | TS-16 | warn | tests/test_output.py:1906-1921 | ⚠️ Gate 03 TS-16 (Suggestion/Improvement) `negative_rebinds_verifier_dependencies` (tests/test_output.py:1906-1921) looks for `.pth` files and shadow modules under /app and /app/ou | kept-rejected |
| vendor | v3 | 1ccc9c0 | 3fb1650b | JD-7 | warn | tests/judge.toml:65-74 | ⚠️ Gate 04 JD-7 (Suggestion/Improvement) R5 (tests/judge.toml:65-74) asks for "no dead or debug code", but the oracle writes one byte-identical 568-line source to both /app/decode. | fixed |
| vendor | v4 | 26b3948 | 3fb1650b | DS-4 | warn | decoder_appendix.md:115-116 | ⚠️ DS-4: the catalog's capture ids label exactly which captures are rejected, so two format_report figures can be read off the names and an agent gets a free self-check. | recurred |
| vendor | v4 | 26b3948 | 3fb1650b | TS-16 | warn | tests/test_output.py:1904-1926 | ⚠️ TS-16: negative_rebinds_verifier_dependencies can never fire in separate mode. | recurred |
| vendor | v5 | bddf20b | 71a653b2 | DS-20 | minor | instruction.md:7 | 🟡 DS-20-1 Plain decode of a segment with a good header and damaged frames crashes the oracle, and no test grades this case. | kept-rejected |
| vendor | v5 | bddf20b | 71a653b2 | JD-15 | minor | judge.toml:72 | 🟡 JD-15-1 R5 is a code-quality conduct criterion but carries an outcome label. | fixed |
| vendor | v5 | bddf20b | 71a653b2 | DS-6 | minor | field_layouts.csv:3 | 🟡 DS-6-1 Field units contradict field names, so the telemetry data reads as filler. | kept-rejected |
| vendor | v5 | bddf20b | 71a653b2 | TS-16 | warn | test_output.py:2286-2303 | ⚠️ TS-16-1 negative_rebinds_verifier_dependencies can never fire. | fixed |
| vendor | v5 | bddf20b | 71a653b2 | DS-4 | warn | decoder_appendix.md:147-148 | ⚠️ DS-4-1 Catalog capture ids mark exactly which captures are rejected (`cap-` 15200 decode, `rej-` 2500 reject; | fixed |
| vendor | v5 | bddf20b | 71a653b2 | X1 | warn | UNVERIFIED (no file cited) | ⚠️ X1 (structure_qc) The three .varc captures were skipped by the dash sweep as binary. | kept-accepted |
| vendor | v6 | 9bc33e6 | 71a653b2 | DS-20 | minor | instruction.md:7 | 🟡 Gate 02 DS-20-1 Plain decode of a good-header segment with damaged frames crashes the oracle (traceback, exit 1), and no test grades this case. | last-round |
| vendor | v6 | 9bc33e6 | 71a653b2 | DS-6 | minor | environment/data/field_layouts.csv:3 | 🟡 Gate 02 DS-6-1 Field units contradict field names, so the telemetry data reads as filler. | last-round |
| vendor | v6 | 9bc33e6 | 71a653b2 | DS-24 | warn | solution/solve.py:193-229 | ⚠️ Gate 02 DS-24-1 The oracle is a renamed line-by-line paraphrase of the verifier's reference codec, not an independent reading of the contract. | last-round |
| vendor | v6 | 9bc33e6 | 71a653b2 | TS-17 | warn | test_output.py:1986 | ⚠️ Gate 03 TS-17-1 Six positive checks compare decoded values with plain `==`, so float or bool values pass where the appendix promises integers. | last-round |
| vendor | v6 | 9bc33e6 | 71a653b2 | JD-6 | warn | judge.toml:13 | ⚠️ Gate 04 JD-6-1 R1's machine key says count unit while its description asks for a non-count unit. | last-round |

## Kit wording per id (HEAD 71a653b2)

| id | kit file:line | wording |
|---|---|---|
| AL-17 | Input_Bundle_QC/05_Alignment_Integrity_QC.md:102 | AL-17 timeout story coherent |
| AL-18 | Input_Bundle_QC/05_Alignment_Integrity_QC.md:103 | AL-18 no stale references or wrong counts anywhere |
| AL-19 | Input_Bundle_QC/05_Alignment_Integrity_QC.md:104 | AL-19 no credential/secret exfiltration |
| AL-2 | Input_Bundle_QC/05_Alignment_Integrity_QC.md:85 | AL-2 every instruction promise graded |
| AL-27 | Input_Bundle_QC/05_Alignment_Integrity_QC.md:90 | AL-27 every stated rule has a fixture that actually triggers it (precedence pairs traced) |
| AL-28 | Input_Bundle_QC/05_Alignment_Integrity_QC.md:91 | AL-28 no penalty stacking: one action never fires more than one max-severity penalty across tests and judged criteria |
| AL-3 | Input_Bundle_QC/05_Alignment_Integrity_QC.md:86 | AL-3 exact shapes agree across the contract, tests, solution (read the shipped spec, not just the prompt) |
| AL-5 | Input_Bundle_QC/05_Alignment_Integrity_QC.md:88 | AL-5 oracle would pass every test |
| AL-6 | Input_Bundle_QC/05_Alignment_Integrity_QC.md:89 | AL-6 judged criteria consistent with solution and instruction |
| AL-7 | Input_Bundle_QC/05_Alignment_Integrity_QC.md:92 | AL-7 no unearned measured claims |
| AL-F0a | Input_Bundle_QC/05_Alignment_Integrity_QC.md:68 | AL-F0a no template residue |
| AL-F0c | Input_Bundle_QC/05_Alignment_Integrity_QC.md:70 | AL-F0c work dependency holds, no shortcut found |
| AL-F0d | Input_Bundle_QC/05_Alignment_Integrity_QC.md:71 | AL-F0d no double scoring across tests and judged criteria |
| CL-1 | Input_Bundle_QC/05_Alignment_Integrity_QC.md:74 | CL-1 every demanded action has a checker that looks at the action itself, not the agent's report of it (test or judged criterion named for each action) |
| CL-10 | Input_Bundle_QC/05_Alignment_Integrity_QC.md:83 | CL-10 every asserted fact traced to an agent-visible file or a derivation from one; nothing load-bearing lives only in solution/ or tests/ |
| CL-2 | Input_Bundle_QC/05_Alignment_Integrity_QC.md:75 | CL-2 forgery price computed as a share of the positive weight, every paying test named, the total judged defensible with reasons |
| CL-3 | Input_Bundle_QC/05_Alignment_Integrity_QC.md:76 | CL-3 no asserted value liftable verbatim from a shipped file, an instruction constant or a worked example (derivation is fine and expected) |
| CL-5 | Input_Bundle_QC/05_Alignment_Integrity_QC.md:78 | CL-5 every exact comparison's silent requirements (order, keys, path form, casing) either stated in the contract or compared insensitively, judged criteria read the same way |
| DS-15 | Input_Bundle_QC/02_Data_Solution_QC.md:101 | DS-15 oracle would plausibly score 1.0 against the tests |
| DS-18 | Input_Bundle_QC/02_Data_Solution_QC.md:104 | DS-18 solve.sh idempotent (warn only) |
| DS-20 | Input_Bundle_QC/02_Data_Solution_QC.md:106 | DS-20 oracle obeys every contract rule, wherever stated, including rules no test triggers |
| DS-21 | Input_Bundle_QC/02_Data_Solution_QC.md:107 | DS-21 solvable from instruction.md + environment/ input alone (hard is fine; only genuinely unreachable information fails) |
| DS-22 | Input_Bundle_QC/02_Data_Solution_QC.md:108 | DS-22 TRUTH.md describes the shipped solution, the real grading and a defect list the bundle honours (read only after DS-21 was decided) |
| DS-24 | Input_Bundle_QC/02_Data_Solution_QC.md:110 | DS-24 oracle is an independent implementation, not the verifier's own code |
| DS-25 | Input_Bundle_QC/02_Data_Solution_QC.md:111 | DS-25 every literal the grading side requires of the output is findable in an agent-visible file (named file per literal) |
| DS-27 | Input_Bundle_QC/02_Data_Solution_QC.md:113 | DS-27 TRUTH.md describes the task, with no narrative of how it was produced |
| DS-4 | Input_Bundle_QC/02_Data_Solution_QC.md:87 | DS-4 no answers or answer-derivable content in any environment/ input directory |
| DS-5 | Input_Bundle_QC/02_Data_Solution_QC.md:88 | DS-5 no template residue, no redacted-spec pattern |
| DS-6 | Input_Bundle_QC/02_Data_Solution_QC.md:89 | DS-6 data internally consistent with the task story |
| G03-unlabelled | UNVERIFIED | not in kit HEAD |
| IN-12 | Input_Bundle_QC/01_Instruction_QC.md:81 | IN-12 category names the dominant work; description honest; keywords/tags related |
| IN-15 | Input_Bundle_QC/01_Instruction_QC.md:84 | IN-15 every graded rule of engagement is stated plainly enough to act on |
| IN-16 | Input_Bundle_QC/01_Instruction_QC.md:85 | IN-16 nothing graded has two defensible readings the contract fails to settle (both readings written out, or no finding) |
| IN-2 | Input_Bundle_QC/01_Instruction_QC.md:71 | IN-2 no mention of tests/, solution/, grader, logs, reward (stating WHAT is judged is fine) |
| IN-8 | Input_Bundle_QC/01_Instruction_QC.md:77 | IN-8 everything the tests assert AND everything an outcome judged criterion demands is knowable from prompt, shipped spec or data (conduct criteria are exempt, see JD-15) |
| IN-L2 | Input_Bundle_QC/01_Instruction_QC.md:68 | IN-L2 grammar and spelling clean |
| IN-L3 | Input_Bundle_QC/01_Instruction_QC.md:69 | IN-L3 no AI-tell phrases; reads like a human colleague wrote it |
| JD-11 | Input_Bundle_QC/04_Judge_QC.md:135 | JD-11 negatives target this task's real cheat surface |
| JD-13 | Input_Bundle_QC/04_Judge_QC.md:137 | JD-13 importance/weight pairing holds by /weight/ and magnitudes match semantic importance |
| JD-14 | Input_Bundle_QC/04_Judge_QC.md:138 | JD-14 no criterion pair (negative or positive) pays twice for one act |
| JD-15 | Input_Bundle_QC/04_Judge_QC.md:139 | JD-15 every criterion classified as outcome, constraint or conduct; outcome criteria trace to the contract (instruction plus any spec file it points to); conduct criteria hold for every competent rout |
| JD-16 | Input_Bundle_QC/04_Judge_QC.md:140 | JD-16 each constraint criterion quotes its stated sentence and names the file it lives in, fits one of the six kinds, carries annotations type "instruction following", covers exactly one rule, and is  |
| JD-18 | Input_Bundle_QC/04_Judge_QC.md:142 | JD-18 at least one criterion judges the quality of the code the agent writes (name it), or the task authors no code and the line says so |
| JD-2 | Input_Bundle_QC/04_Judge_QC.md:126 | JD-2 positive grammar everywhere, no banned tokens |
| JD-5 | Input_Bundle_QC/04_Judge_QC.md:129 | JD-5 one observable per criterion |
| JD-6 | Input_Bundle_QC/04_Judge_QC.md:130 | JD-6 every criterion decidable from evidence |
| JD-7 | Input_Bundle_QC/04_Judge_QC.md:131 | JD-7 every criterion true of / avoided by the reference solution |
| JD-8 | Input_Bundle_QC/04_Judge_QC.md:132 | JD-8 zero overlap with deterministic tests (observable-level) |
| JD-9 | Input_Bundle_QC/04_Judge_QC.md:133 | JD-9 the judged criteria add process value beyond the tests |
| STEP10 | Input_Bundle_QC/Final_checklist.md:317 | ## Step 10: the execution gate (mandatory before ship) |
| STEP11 | Input_Bundle_QC/Final_checklist.md:424 | ## Step 11: final coverage and overlap re-check (mandatory, after everything else) |
| TS-13 | Input_Bundle_QC/03_Tests_QC.md:114 | TS-13 one property per test |
| TS-14 | Input_Bundle_QC/03_Tests_QC.md:115 | TS-14 names state properties (<property> / negative_<cheat>), prefix iff negative weight |
| TS-15 | Input_Bundle_QC/03_Tests_QC.md:116 | TS-15 negative checks return True when the cheat happened, with inline comment |
| TS-16 | Input_Bundle_QC/03_Tests_QC.md:117 | TS-16 negatives fire on the cheat and only the cheat |
| TS-17 | Input_Bundle_QC/03_Tests_QC.md:118 | TS-17 exact comparisons where exactness promised (bool/int trap checked) |
| TS-19 | Input_Bundle_QC/03_Tests_QC.md:120 | TS-19 no obvious contract/test contradiction, checking the shipped spec as well as the prompt; a promise a judged criterion grades is covered (deep pass in Gate 05) |
| TS-20 | Input_Bundle_QC/03_Tests_QC.md:121 | TS-20 weights map to importance semantically, ordering matches the instruction |
| TS-23 | Input_Bundle_QC/03_Tests_QC.md:126 | TS-23 counts and balance: >=10 checks, <=35 (warn), >=1 positive, >=1 negative, weights not all identical, sum/neg/ <= sum pos |
| TS-24 | Input_Bundle_QC/03_Tests_QC.md:127 | TS-24 verifier execution isolation (reward not forgeable by executed agent code) |
| TS-25 | Input_Bundle_QC/03_Tests_QC.md:122 | TS-25 no positive test grades an absence |
| TS-26 | Input_Bundle_QC/03_Tests_QC.md:123 | TS-26 no test pair (any signs) pays twice for one observable |
| TS-29 | Input_Bundle_QC/03_Tests_QC.md:130 | TS-29 no check can raise on bad, missing or hostile agent output; every check returns a bool |
| X1 | Input_Bundle_QC/structure_qc.py:71 | X1  no em/en dash in any text file; binary-skipped files warn. |
