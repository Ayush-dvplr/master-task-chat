# Pension Mechanism Card

Task: `9bb234eb-e964-5e0b-b8a9-37e9d58b887c`. Source references below are relative to that original task unless prefixed `QC/` or this report directory. `QC/` means `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`.

## Observed Outcome

Recorded and replay tests: **12/52 = 23.08%**; oracle **52/52 = 100%**. Recorded judge **12/56 = 21.43%**; combined **22.25%**. No negative fired. Eight scenario checks lost five raw points each. All eight calculations agree with the frozen oracle: six complete reports, including every atom, COLA transition, member benefit, plan total, manifest and audit hash, are byte-identical. Effective services also agree. Disagreements are only quality-report conventions and revision-decision representation. Evidence: `pension-instrument/*/diff.json`, `inventory.json $.pension.cases`, recorded `reward-details.json $.reward.components`.

## Hidden Extracts

Ten input files per extract: schema, policy, plans, seven JSONL families. The base has members 4, service revisions 8, salaries 7, leaves 5, COLAs 4, rebases 3, elections 4: **35 JSONL rows**. Hidden corpus is compressed literal data, not a random generator. The seed constants at `tests/test_output.py:8` do not drive generation. `_PACKED` at line 15 and `_write_variant` at line 58 reconstruct the files, then `_apply_scenario` at line 38 makes one mutation. Counts are independently retained in `pension-instrument/summary.json $.input_counts` and `inventory.json $.pension.shipped_counts`.

| Hidden extract | Mutation and resulting JSONL rows | Intended contract rule | Actual differing paths |
|---|---|---|---:|
| revision_tie | Clone SR-102B as SR-102Z with end 2024-11-01; service rows 9, total 36 | Equal revision/time peers conflict, record ID selects winner; schema:9 | 83 |
| overlapping_leave | Add LV-X, MEM-101, 2021-03-01..2021-06-01, 2500 bps; leaves 6, total 36 | Minimum covering leave and per-atom rounding; schema:15 | 78 |
| missing_salary | Remove SAL-102-21; salaries 6, total 34 | Missing salary issue and atom omission; schema:15 | 78 |
| same_day_order | COLA-A-22 factor becomes 15000; total 35 | ACCRUAL before COLA before REBASE; schema:19 | 78 |
| salary_cap | PLAN-A cap becomes 6,100,000 cents; total 35 | Cap salary before accrual arithmetic; schema:15 | 78 |
| election_day | EL-101 retirement becomes 2024-03-14; total 35 | Birth-day adjustment to age months; schema:21 | 78 |
| multiple_elections | Add EL-101-Z, retirement 2024-06-15, option 8400; elections 5, total 36 | Latest retirement then election ID; schema:11 | 78 |
| valuation_clip | Valuation becomes 2023-03-01; total 35 | Clip atoms and ignore later events; schema:15,19 | 107 |

Counts of differing paths are diagnostic traversal events, not independent facts. Missing list entries shift later indices. No count means the named business rule failed: the targeted business outputs match in every case.

## Contract Density

The seven-line instruction delegates to a 41-line, 616-word contract. This is accessible rather than deeply hidden: trajectory step 4 reads the complete contract and step 5 reads every input family. Eight interacting stages provide legitimate implementation load: revision/quarantine, interval cuts, salary precedence/cap, minimum leave and credited-day rounding, cent accrual rounding, chronological revaluation, election reduction/rounding, audit serialization. These are an analytical grouping, not a claimed count of every atomic rule. Load-bearing details occupy long paragraphs at schema:9,11,15,19,21; output definitions occupy schema:25-41.

The problem is missing specifications, not burial. Schema:27 names `record_counts` without its child keys; schema:29 specifies effective-service fields but not revision-decision fields. Schema:9 does not specify the issue ID scope or number of tie-conflict issues. No shipped output example resolves these choices.

## Exact Loss Mechanism

`CAUSES.csv` records these roots for every affected check:

| Root | Frozen expectation versus Opus | Scope |
|---|---|---|
| P-COUNTS | Seven semantic family keys versus nine input filename keys including policy/plans | All eight |
| P-DECISIONS | Three decision keys versus eleven; `winner_record_id`/`discarded_record_ids` versus `winning_record_id` plus other metadata | All eight |
| P-INVALID-ID | INVALID_SERVICE identifies SVC-BAD versus SR-BAD | All eight |
| P-TIE-ISSUE | One conflict identifying SVC-102 versus two identifying SR-102B/SR-102Z | revision_tie only |
| P-FUTURE-ISSUES | Oracle emits INVALID_COLA:COLA-A-24 and INVALID_REBASE:RB-102; Opus ignores valid future events | valuation_clip only |

The first four expectations are not determinate from the delivered contract; the last conflicts with its instruction to ignore events after valuation. Oracle lines 119/129 reject future events, whereas captured program lines 324/340 accept their validity and line 495 excludes them from calculation. Schema:11 does not define future dates as invalid. This is a quality-report disagreement, not a benefit disagreement. Root classification **UNFAIR** is an explicit contract-alignment assessment; the field values themselves are directly measured.

Each check executes `/app/out/calculate_pension.py DATA_DIR OUT_DIR` with Python `-I -S`, as nobody, a minimal environment, seeded stale outputs and 120-second timeout (`tests/test_output.py:79,86`). It hashes filename + NUL + raw bytes for **all nine reports** (lines 104-111). `_holds` catches every exception and returns false (100-103). Instrumentation bypasses only that swallowing wrapper: all eight original assertions raise empty-message `AssertionError`, in 0.022-0.030 seconds, not a crash or timeout. Recomputed oracle hashes match all eight frozen hashes.

Weights: artifact set 1, canonical serialization 3, safe local source 3, deterministic/no mutation 5 all pass; eight whole-bundle hashes at 5 each fail. Negative checks -5/-5/-3 are all false, not deductions. A single changed `manifest.engine_version` in otherwise exact oracle output fails all eight hashes: **one-fact-wrong scenario credit 0/40**, total would remain **12/52** with the four nonhash positives unchanged. This is CL-4 amplification, not eight independently demonstrated calculation bugs.

## Judge Loss

All ten lost criteria and exact recorded reasons are in `JUDGE_LOSS.csv`. R2-R8 cost 35 raw points: expected-value verification was missing, not necessarily the edge cases themselves. Pension step 13 actually constructs and runs a fresh extract, but prints results rather than asserting independent expectations. Steps 9/10 inspect outputs. R9-R11 cost nine raw points for incomplete shape/order validation, no independent digest/audit recomputation, and no immutability snapshot. Step 11 compares eight reports after reordering; excluding the raw-input digest portion of manifest is justified. The pension R11 demand for *every* output byte to stay equal under reordered raw inputs conflicts with manifest raw-file hashes (schema:25). Its missing immutability check remains a real omission; do not copy the impossible subclause.

## QC Fit

| Gate | Assessment | Evidence |
|---|---|---|
| IN-8 | **LIKELY FAIL** | Exact decision/count shapes and issue-ID conventions cannot be learned from schema:9,27,29 or any input. QC/01_Instruction_QC.md:38 requires discoverable outcome expectations. Conduct criteria are exempt; that exemption does not excuse output hashes. |
| IN-17 | **PASS, scoped to this gate** | Instruction:1,5 delegates discovery and gives generic fresh-input notice, not solutions to hidden cases. QC/01_Instruction_QC.md:47 forbids pre-announcing already discoverable facts; it does not authorize omitting indeterminate output requirements. Fixing IN-8 requires documenting output shapes, not exposing answers. |
| AL-1 | **LIKELY FAIL** | The five roots above lack determinate grounds, with P-FUTURE-ISSUES contradicting schema:19. QC/05_Alignment_Integrity_QC.md:21,27,34-35. Tests/solution are not agent-visible grounds. |
| AL-27 | **LIKELY FAIL** | Event-ID tie-break within equal date/kind (schema:19) lacks discriminating coverage in the eight extracts: removing `item[3]` from oracle sort at solve.py:203 changes no report in any case. `pension-instrument/trigger-probe.json` records all eight empty changed-report lists. Adjacent kind boundaries have examples, but the whole precedence chain is not proven. QC/05_Alignment_Integrity_QC.md:38. |
| CL-4 | **LIKELY FAIL** | One changed manifest field destroys all eight five-point hashes; the instruction never declares an intentionally all-or-nothing task. QC/Final_checklist.md:491 explicitly rejects whole-object equality across independent facts and repeated comparisons of the same wrong fact. |

Careful engineers could reasonably choose the observed count keys, decision metadata, and revision-record issue IDs. Those are schema traps, not demonstrated domain incompetence. Forgetting independent expected-value probes is a genuine verification-process weakness, but this run does not show that it produced wrong pensions. Potential defects on other inputs are not attributed to these lost points.

## Copy Into a New Domain

**Proposed recipe, not an empirically proven Opus failure:** use subscription entitlement proration. Publish a complete output JSON schema and an unambiguous contract of roughly eight interacting stages in 500-800 words. Supply one visible extract and eight hidden extracts: revision tie, overlap precedence, missing price, same-date event ordering, monetary cap, anniversary-day boundary, latest amendment, valuation clipping. Add one paired-fault witness for *every adjacent precedence pair*; ensure event-ID ordering is distinguishable by opposite input order and noncommutative rounded transitions.

Grade eight independent rule families, two raw points each, plus artifact/serialization/audit integrity at one point each; split repeated cross-extract observations rather than charging repeatedly for the same root. Give one schema deviation only its proportional schema credit loss. Use a small separate conduct channel, at most one three-point criterion for independent critical-boundary verification and one one-point criterion for honest input-preservation/determinism evidence; do not require arbitrary counts of checkpoints or a particular assertion syntax. Audit these conduct requirements under JD-15 before claiming QC pass. Independently prove oracle perfection and a one-fact-wrong proportional score. Avoid whole-report hashes as paid correctness units, undocumented issue IDs, contradictory future-event validation, and raw-manifest equality under reordered files.
