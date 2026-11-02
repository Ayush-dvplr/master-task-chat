# RECHECK_FIX deb4e4a: tariff-engine-audit-repair, QL round 2

Report: `master_chat_work/_ql/tariff-engine-audit-repair/20261029T1940_report/QL_REPORT.md` (FAIL 4/4/3). Triage: `ql2_triage_d262a8b/TRIAGE.md`.
Kit: live `Terminal_2.0_Harbor_Harness` HEAD `5574d77eb9f22c207ba05fd8f9ac31d42ba45271` (same HEAD as the triage). Rule IDs and wording match the report; one line number moved: AL-2 is at `05_Alignment_Integrity_QC.md:33` in the live kit (triage cited :22), same wording.
Bundle before: tree `b0cd2c1813ba` = previous QC copy `QC/copies/e91a9d2` (`diff -rq` empty), backed up to `WORK/pushed_b0cd2c1813ba/`. So every line the findings cite is byte-identical to the copy QC v4 passed (noise check, Always 13).
Abbreviations: B = bundle, T = `B/tests/test_output.py` (fixed tree line numbers unless "old T"), KIT = `Input_Bundle_QC/`, FC = `KIT/Final_checklist.md`, DEF = `WORK/QC_DEFENCE.md`, KEPT = `QC/reports/tariff-engine-audit-repair/KEPT.md`, v4 = `QC/reports/tariff-engine-audit-repair/v4.md`.
Levers (LEVERS.md): L1 statement redeem at scale (bitset, gcd_split, mitm_only, mitm_dedupe, branch_bound, blind_r3), L2 tie rule (tie_naive, greedy), L3 first write / ledger (first_write). "none" below means every lever.

## Findings

| ID | label | rule quote (live kit file:line) | evidence quote (file:line) | decision | playbook row | effect per lever | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| TQ2-F1 hidden statement scale, 55% weight | FALSE_POSITIVE (carry-over, NOISE) | DS-21 02_Data_Solution_QC.md:70 "Default to pass. To fail this check you must ... name the exact piece of information the solver cannot obtain"; CL-10 FC:498 "Derivation counts fully"; CL-5 FC:492; CL-4 FC:491; IN-8 01_Instruction_QC.md:38 "The fail here is narrow"; TS-19 03_Tests_QC.md:50 "stated in the instruction OR determinate in the input"; AL-4 05:35 | Rule stated `environment/ci/api_contract.md:211-231`; limit stated :25-28 (10 s, later output counts as no output); `instruction.md:13` "graded whole on fresh inputs, and only an exact match counts". Lines unchanged vs `QC/copies/e91a9d2` (diff empty). | REBUT, no edit | NOISE; TS-19 NEVER ("describing the hidden distribution") not applied | none | none | none |
| TQ2-F2 statement weight and three seeds | FALSE_POSITIVE (carry-over, NOISE) | TS-20 03_Tests_QC.md:51 "Mild imbalance within the right ordering is a minor."; TS-26 03:53 "What is NOT a duplicate: two tests reading genuinely different aspects" | T:7568 `_SCALE_RNG = {"statement": (53, 29), "batch": (61, 37), "cycle": (67, 41)}`; T:7672-7690 `_scale_texts(kind, corpus)` builds a separate input per kind; KEPT rows TS-20, TS-26 | REBUT, no edit | NOISE; TS-20 / TS-26 rows (NEVER drop or merge a lever check) | none | none | none |
| TQ2-F3 delivered test_visible.py never run | REAL (PARTLY: "never checked" overstated) | AL-2 05_Alignment_Integrity_QC.md:33 "Everything promised is graded. ... point to the test or the judged criterion that checks it"; CL-1 FC:488; CL-9 FC:497 "Grading does not supply what it measures" | Promise `api_contract.md:237` "The repaired `/app/repo/tests/test_visible.py` passes against the repaired package." Old T:7803-7808 ran only the verifier copy (`_contract_visible_suite`, old T:7790-7800). Host/Docker probe (R/probe.json): old tests, attempt-5 zip with its test edited to assert 9.31 -> check True. v4:233 CL-1 PASS misread which file runs, so not carry-over. | FIX: T:7823-7831 now also runs `python -B -m unittest discover -s tests -p test_visible.py` in the delivered archive tree (`_repo()`), same `_run` (nobody via setpriv, own session, group kill); passes only if both runs exit 0 (verifier copy still needs `Ran {count} tests`). Weight 3 (T:8822) unchanged; `_check_corrected_tests` (T:7848-7855) untouched. Description T:8038 now names both suites. | AL-2/CL-1 (QC_FIX_PLAYBOOK_v3:33) DO "grade it through an observable the program writes"; NEW-CHECK hygiene (:57) | L1 none, L2 none, L3 none (check outside every lever family; all lever losses equal, see Trap survival) | none needed | tests/test_output.py, solution/TRUTH.md (bullet), WORK/QC_DEFENCE.md:277 |
| TQ2-F4 no process group / no kill on timeout | REAL | TS-24 03_Tests_QC.md:68 "verify all of the following; any miss is a fail:" and :71 "Every agent subprocess has exited before its check returns (killing the process group), so nothing outlives rewardkit's final write." | Old T:5637-5639 `_run` = `subprocess.run(..., timeout=120)`; old T:7221-7225 statement run and old T:7500-7504 ledger run `subprocess.run(..., timeout=STATEMENT_SECONDS)`; no start_new_session/killpg. Probe (Docker, uid 1000) on old tests: grandchild left alive after return (1) and after timeout (1). v4:195 TS-24 PASS reason does not cover :71. | FIX: new `_kill_group` T:5638-5642 and `_group_run` T:5645-5657 (`Popen(..., start_new_session=True)`, `communicate(timeout)`, on timeout SIGKILL the group, wait, re-raise; `finally` SIGKILL the group). `_run` T:5660-5661 (timeout 120), statement run T:7244 and ledger run T:7522 (timeout `STATEMENT_SECONDS` = 10, T:7181) use it; user (setpriv nobody), arguments and the "no statements within 10 seconds" assertion unchanged. Probe on new tests: grandchildren left 0 after return and 0 after timeout (timeout raised at 3.51 s for a 3 s cap). | NEW-CHECK hygiene (:57, lists TS-24); no TS-24 row | none (timeouts unchanged; slowest oracle statement child 1.36 s under 8 threads, --cpus 2 --memory 4g, was 1.25 s, limit 10 s) | none needed | tests/test_output.py, solution/TRUTH.md, WORK/QC_DEFENCE.md |
| TQ2-M1 "graded whole" vs per-part scoring | FALSE_POSITIVE (carry-over, NOISE) | AL-18 05:75 "nothing mentions files, paths, counts, or numbers that do not match the actual bundle"; CL-4 FC:491 | `instruction.md:13` "Each invoice, each exception list and each statement list is graded whole"; per-part checks T:7709-7765 are each an exact match of a whole part (`_same`, T:7697); whole statement document T:7289. v4:236 CL-4 PASS, v4:261 AL-18 PASS. | REBUT, no edit | NOISE | none | none | none |
| TQ2-M2 R7 two facets / target | FALSE_POSITIVE (carry-over, NOISE) | JD-5 04_Judge_QC.md:71 "a borderline case (two facets of one act) is a minor"; JD-6 04:72; JD-18 04:99 "At least one criterion judges the quality of the code" | `tests/judge.toml:89-100` R7 "free of dead code ..." (one observable), target state_change; `instruction.md:3` repair is in /app/repo. v4:210, v4:211 PASS; DEF:272-274. | REBUT (if QC still reads two facets: KEEP as minor by 04:71) | NOISE; SUGGEST (KEEP with kit line) | none | none | none |
| TQ2-M3 two balance ranges in TRUTH | FALSE_POSITIVE | DS-22 02:78 "confirm the stated counts, weight totals and named negatives are the real ones"; AL-18 05:75 | `solution/TRUTH.md:145`, :153 "4e10 to 8e10" = generator aim T:7420 `rng.randrange(40_000_000_000, 80_000_000_000)`; TRUTH.md:251, :259 "between 3e10 and 1e11" = guard T:7352 `LEDGER_LOW, LEDGER_HIGH = 30_000_000_000, 100_000_000_000` (asserted T:7436, :7484, :7662). Two true statements about aim and guard. | REBUT, no edit | none needed | none | none | none |
| TQ2-M4 TRUTH overstates what every check does | REAL (minor) | DS-22 02_Data_Solution_QC.md:78 "confirm the stated counts, weight totals and named negatives are the real ones"; fail 02:117 "TRUTH.md contradicting the shipped solution, the real grading" | Old TRUTH.md:188-191 "Every check extracts `/app/out/patched-repo.zip` and runs the package inside it" vs JSON-only `_check_module_notes` T:7895, summary T:7907, repair report T:7925, previously failing T:7934. | FIX: `solution/TRUTH.md:190-199` names the checks that run the package (metadata, visible tests, every corpus check incl. statements and ledger, missing input, two runs, `negative_hardcoded_sample_answers`), the four that read delivered JSON only, and the text-only/verifier-computed ones; states the session/group kill. TRUTH sha lines rewritten by `WORK/truth_sha.py` last (values unchanged: solution/ untouched). | DS-22 (QC_FIX_PLAYBOOK_v3:47) | none | none | solution/TRUTH.md |
| TQ2-W1 158 checks > 35 | FALSE_POSITIVE (carry-over, warn KEEP) | TS-23 03_Tests_QC.md:62 "at least 10 checks (fail), at most 35 (warn)" | 158 registrations T:8820-8977; KEPT row F09 | KEEP warn with the count (158); no merge | TS-23 (never merge to reach 35) | none | none | none |
| TQ2-W2 wall-clock under threads | FALSE_POSITIVE (carry-over) | TS-11 03_Tests_QC.md:41 | per-key memo lock T:5590-5608; re-measured after F4: slowest statement child 1.36 s, 8 threads, --cpus 2 --memory 4g, 0 timeouts (oracle 670/670), limit 10 s (T:7181) | KEEP, no edit | NOISE | none | none | none |
| TQ2-W3 R1 rewards verifying own work | FALSE_POSITIVE (carry-over) | JD-15 04_Judge_QC.md:92 "Verifying your own work ... all pass here"; JD-9 04:86, at most a warn per 04:146 | `tests/judge.toml:11-22` R1; v4:214, v4:220 PASS | KEEP, no edit | NOISE | none | none | none |

QL coverage table: no FAIL rows beyond F1-F4 (QL_REPORT.md:79-82).

### Rebuttals (FALSE_POSITIVE fails)
- TQ2-F1: The rule the statements grade is stated (`api_contract.md:211-231`), so is the 10 second limit (:25-28) and the whole-document exact bar (`instruction.md:13`). DS-21 (02:70) fails only when a needed fact appears in no agent-visible file; QL names input size, which is not information the solver needs to apply the stated rule, and CL-10 (FC:498) says long or hard derivation is not a defect. CL-5 (FC:492) and IN-8 (01:38) cover order, spelling, key names, strings, error shapes and tolerances, not input scale. Same lines passed QC v4 (KEPT F08, v4:157/188/242/246). Stating or shrinking the hidden scale is a TS-19 NEVER fix.
- TQ2-F2: The three statement kinds read three different generated inputs (T:7568 three seed pairs; T:7672-7690 separate input per kind and corpus), which 03:53 names as not a duplicate; the weight balance is a minor at most (03:51) and was kept at QC v3/v4 with Ayush's approval (KEPT TS-20, TS-26). Dropping or merging batch/cycle is a playbook section 0 NEVER (each lost points in TRIP.md).

## Deviations from master directions
None. Guard G2 ("Never move an assert into an existing check", QC_FIX_PLAYBOOK_v3:65) was weighed for TQ2-F3: the added run grades the same contract sentence (`api_contract.md:237`) with the same command on the same delivered package, so the check still states one property (TS-13 03:44): "the visible suite passes against the delivered package", on the delivered file and on the contract-corrected reference. A separate check would change the positive total 670, which the master's score bar forbids. Residual stated honestly: a delivered file whose assertion bodies are gutted still passes the delivered run, but the verifier copy run in the same check still grades the contract values against the delivered src, and `negative_visible_test_removed` (-3) still catches deleted tests.

## Gate results
- xref_check: `xref_check: 78 entries, 0 findings` (before and after edits).
- precheck.sh BUNDLE: last line `PRECHECK CLEAN` (158 tests, 16 criteria).
- stacking_check.py: output identical to the pre-fix tree except the folder name; OUT/STACKING_CHECK.md ends `STACKING PASS`.
- Probes (Docker, R/probe.json): new tests: attempt-5 zip visible check True; same zip with its test asserting 9.31 False; grandchild left after return 0, after timeout 0. Old tests: True, True (F3 real), 1, 1 (F4 real).
- Score bar: attempt-5 delivered package 306/670 and agent program 306/670, as before; oracle 670/670 in the measuring harness.
- Harbor (copies from the live kit `exe_copy.py`, warm image first, R=/tmp/opencode-logs/tariff-deb4e4a-20261029T214412-5a32): oracle x3 = 1.0, 1.0, 1.0; owner-only x1 = 1.0; nop x1 = 0.0; 0 errors; chain ALL_DONE 22:02:27 IST.
- Tree sha: BUNDLE 754f14eb4e5e = Tasks_INPUT 754f14eb4e5e (was b0cd2c1813ba; only `tests/test_output.py` and `solution/TRUTH.md` changed). Backup `WORK/pushed_b0cd2c1813ba/`.
- Session rename: `name_session.py deb4e4a` printed `codex: no match` / `opencode: ['ses_e779dae83ffemu9fiol2H4U2jQ']`; the list did not show deb4e4a by name; not retried.

## Touched rules

| id | touched how | rules re-checked | verdict with file:line |
|---|---|---|---|
| delivered_visible_tests_pass | body extended (second run of the delivered `tests/test_visible.py`), description re-worded; weight 3 unchanged | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4; judge rules n/a (no criterion touched) | TS-13 PASS: one property, the visible suite passes against the delivered package (T:7823-7831; api_contract.md:237). TS-14 PASS: name and description T:8038 state both suites, body runs both. TS-20 PASS: weight 3 unchanged (T:8822), total 670 unchanged. TS-25 PASS: delivered run must exit 0; no `tests/` dir -> unittest rc 1, empty or absent `test_visible.py` -> rc 5 (host check, Python 3.14; same since 3.12), so absence fails. TS-26 PASS: `corrected_tests_name_the_changed_tests` (T:7848-7855) reads names/AST, this check reads run outcomes; different observables. CL-2 PASS: forged deliverables without a repair fail the verifier copy run (vacuity probe below). CL-4 PASS: no partial-credit change. |

Runner change (TQ2-F4) touches no check's property, name, weight or assertion; it changes how every agent child is started and stopped. TS-24 re-checked: PASS (probe, grandchildren left 0 after return and after timeout); TS-11 re-checked: PASS (slowest child 1.36 s, limit 10 s).

## Vacuity probe
`WORK/vacuity_p12.py` in Docker (python:3.12-slim, uid 1000, --cpus 2 --memory 4g, THREADS=8) on the fixed tests (R/vacuity.json):
- nothing built: 0/670.
- unedited shipped tool and data packed as the deliverable: 7/670, from `archive_follows_build_config`, `summary_lists_inputs_and_artifacts`, `repair_report_has_stated_shape`, `previously_failing_matches_log`, `two_runs_are_identical` (same five as round 0d8cf26; none is a lever check). `delivered_visible_tests_pass` fails for the unedited tool (the verifier copy run fails on the contract-wrong source), and no statement or ledger check passes.
- Judge: no criterion touched in this round; the judge criteria were probed at 0d8cf26 and are unchanged (judge.toml byte-identical to e91a9d2).
Verdict: PASS.

## Side effects
| FIX id | ids re-checked (FIX_SIDE_EFFECTS + NEW-CHECK) | result |
|---|---|---|
| TQ2-F3 (AL-2/CL-1) | TS-25, TS-13, TS-14, TS-26, CL-2, CL-9 | PASS: absence fails (rc 1/5); one property; name matches body; different observable from corrected_tests; vacuity 7/670 unchanged; the verifier supplies only the reference copy, the delivered file is graded as delivered (CL-9 FC:497). Probe: attempt-5 zip passes, its copy asserting 9.31 fails (`Ran 13 tests ... FAILED (failures=1)`). |
| TQ2-F4 (TS-24) | TS-24, TS-11, TS-17 | PASS: grandchildren left 0 after return and after timeout (old tests: 1 and 1); slowest statement child 1.36 s under 8 threads with --cpus 2 --memory 4g (limit 10 s, was 1.25 s, measured with 3 other sessions' jobs running); assertion messages unchanged (timeout still "no statements within 10 seconds"). |
| TQ2-M4 (DS-22) | DS-22, AL-18 | PASS: TRUTH Verification paragraph matches the code by read (T:7895-7934 JSON only; T:5660 runner); sha lines rewritten by `WORK/truth_sha.py` last, precheck recomputes them clean. |
Side-effect findings: 0.

## Noise keeps
Before any edit `diff -rq` BUNDLE vs `QC/copies/e91a9d2/tariff-engine-audit-repair` printed nothing (tree b0cd2c1813ba both), and QC v4 passed the same checks:
- TQ2-F1 (DS-21/CL-10/CL-5/IN-8/TS-19/AL-4): lines unchanged; v4:157, v4:188, v4:242, v4:246 PASS; KEPT F08.
- TQ2-F2 (TS-20/TS-26): unchanged; v4:189, v4:191; KEPT TS-20, TS-26.
- TQ2-M1 (AL-18): unchanged; v4:236, v4:261 PASS.
- TQ2-M2 (JD-5/JD-6/JD-18): judge.toml unchanged; v4:210, v4:211 PASS.
- TQ2-W1 (TS-23): unchanged; KEPT F09.
- TQ2-W2 (TS-11): memo lock unchanged; v4 PASS; re-measured 1.36 s.
- TQ2-W3 (JD-15/JD-9): judge.toml unchanged; v4:214, v4:220.

## Trap survival
Single-lever wrong-reading variants on the fixed tests, Docker, THREADS=8 (R/trap_*.json). Before = 0d8cf26 "after" column on tree b0cd2c1813ba.

| lever / variant | before loss | after loss | ratio | separating cases kept | verdict |
|---|---|---|---|---|---|
| agent program (harden_r_ql1) | 364 | 364 | 100% | y | PASS |
| bitset | 364 | 364 | 100% | y | PASS |
| tie_naive | 145 | 145 | 100% | y | PASS |
| first_write | 482 | 482 | 100% | y | PASS |
Attempt-5 delivered package: 306/670 (as before). Oracle (same harness): 670/670. No check, weight, hidden input or contract line removed. Two Docker runs (agent, bitset) died with SIGKILL of the measuring process on the first try (same flake as round 0d8cf26, INFERRED memory pressure from other sessions' jobs); one retry each completed with the numbers above.

## QC_RULINGS rows
- TS-19 | hidden statement scale, rule and 10 s limit stated (api_contract.md:25-28, :211-231) | QL2 ❌ F1 | FALSE_POSITIVE | the needed facts are stated; scale is not a needed fact (DS-21 02:70, CL-10 FC:498); stating it is a TS-19 NEVER fix.
- TS-20 | statements 369/670 of test weight | QL2 ❌ F2 | FALSE_POSITIVE | 03:51 "Mild imbalance within the right ordering is a minor."; approved Ayush 29 Oct 09:12.
- TS-26 | batch and cycle statements on separate generated inputs | QL2 ❌ F2 | FALSE_POSITIVE | 03:53 different inputs are not duplicates; T:7568 three seed pairs.
- JD-15 | R1 judges own-work verification as conduct | QL2 ⚠️ W3 | KEEP | 04:92 allows verifying own work; JD-9 warn only (04:146).

## Lessons for the master
- A runner that is not group-killed passes TS-24 review until a QL reads the subprocess call | template_change: P2 template runner section: start agent children with start_new_session and killpg on return/timeout (TRIAGE lesson already filed)
- Measuring tools that monkeypatch subprocess.run go blind after a runner change | no change: WORK/p12v3/checks_threads.py now wraps `_group_run`; note in the bundle's WORK only
- A "visible tests pass" check must run the delivered test file, not only a verifier copy | template_change: P2 template contract checks: visible-suite check runs both the delivered file and the reference copy
