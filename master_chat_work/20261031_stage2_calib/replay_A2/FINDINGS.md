VERDICT: Both Opus replays reproduce 23.08% tests, but every lost scenario point comes from underdefined or contradictory report details amplified by whole-bundle hashes, not demonstrated pension or spectrum calculation errors.

## Reproduction

| Task | Recorded tests | Replay tests | Oracle tests | Recorded judge | Recorded final |
|---|---:|---:|---:|---:|---:|
| pension | 12/52 = 23.08% | 12/52 = 23.08% | 52/52 = 100% | 12/56 = 21.43% | 22.25% |
| spectrum | 12/52 = 23.08% | 12/52 = 23.08% | 52/52 = 100% | 12/56 = 21.43% | 22.25% |

No replay-score difference, missing captured artifact, crash, timeout, or fired negative. The combined original score is `round(0.5*12/52 + 0.5*12/56,4) = 0.2225`; a tests-only replay's 0.2308 must not be compared to that mixed-channel 0.2225. Recorded score.json and pass_summary agree. CTRF marks eleven checks failed, but three are false **negative triggers**, not extra deductions; only eight positive checks lost points. Complete preserved evidence is in `pension-recorded/`, `spectrum-recorded/`, and `replay-results/`.

Replay solve.sh **only restores captured `/app` files**, preserving paths; it does not recompute shipped reports. The verifier subsequently invokes the captured reusable program on its own extracts. `scripts/prepare.py:24-26` documents restoration.

### Runtime Qualification

The first four attempts could not pull the original pinned private ECR Python image: HTTP 401 before agent execution. These infrastructure failures are retained under scratch `jobs/a2-{task}-{oracle,replay}` and `harbor.log`. Successful runs use locally available `python:3.12-slim`, image ID and recorded digest `sha256:cb33f7f771ecec2ef1225cf39b159591a040391bd73e4c01f00fdfc4c47611d2`. Thus this is not an exact reproduction of the inaccessible private base image.

Scratch copies also use the QC toolkit's tests-only execution copy: remove the judge, normalize test weight to 1/52, use public network plumbing for Docker Desktop, and omit the prebaked OpenHands install. No paid judge or agent was run; `OPENAI_API_KEY=unused`. See `scripts/prepare.py`, `scripts/local_base.py`, `scripts/run_harbor.sh`, `harbor-local.log`; QC `Final_checklist.md:335-352,375-386` explains this supported execution plumbing. The **grading module and frozen expected hashes were unchanged**. Four successful runs are `a2-local-pension-oracle`, `a2-local-pension-replay`, `a2-local-spectrum-oracle`, `a2-local-spectrum-replay`. Instrumentation used verifier images built from those copies. Resource gate START=yes preceded every launch.

## Lost Test Points

The denominator here is **80 lost raw positive test points** across two tasks, not 80 percentage points. Each task loses 40/52 = 76.9231 normalized test percentage points. Each failed scenario has weight five.

| Primary cause | Pension raw loss | Spectrum raw loss | Combined raw loss | Share of lost test points |
|---|---:|---:|---:|---:|
| UNFAIR: indeterminate/contradictory output expectation | 40 | 40 | 80 | 100% |
| RULE-MISREAD / RULE-MISSED | 0 | 0 | 0 | 0% |
| LATENT-WRONG / EDGE-INPUT | 0 | 0 | 0 | 0% |
| FORMAT as an independently specified requirement | 0 | 0 | 0 | 0% |
| CRASH / TIMEOUT | 0 | 0 | 0 | 0% |

**AMPLIFIED is an overlapping mechanism, not another allocation:** 40 + 40 raw points, affecting 100% of the same lost checks. CAUSES.csv contains 35 root-fact UNFAIR rows and 16 secondary AMPLIFIED rows. A row's `weight` is the full check weight, not a fractional attribution. Several roots are independently sufficient to fail the same check. Deduplicate `(task,check)` when summing lost points; never sum the 51 row weights. Primary assignment to UNFAIR is a documented contract-alignment assessment; measured expected/actual values and hashes are not inference.

### What Actually Differs

| Task/root | Exact discrepancy | Cases affected | Agent-visible specification |
|---|---|---:|---|
| pension P-COUNTS | Seven semantic count keys versus nine filename keys including policy/plans | 8 | schema.md:27 does not define child keys |
| pension P-DECISIONS | Three revision-decision keys versus eleven; different winner key, absent discarded-record key | 8 | schema.md:29 defines only effective-service row fields |
| pension P-INVALID-ID | INVALID_SERVICE record_id SVC-BAD versus SR-BAD | 8 | schema.md:9,27 does not choose service or revision-record scope |
| pension P-TIE-ISSUE | One group-level conflict versus two conflicting-peer issues | 1 | schema.md:9 does not specify ID scope or multiplicity |
| pension P-FUTURE-ISSUES | Oracle labels two valid future COLA/rebase events invalid; agent ignores them in valuation | 1 | schema.md:11,19 says ignore future events, not invalidate them |
| spectrum S-GRANT-ROW | Raw effective grant includes revision/recorded_at/status; agent projects usable grant without these three | 8 | schema.md:13 defines input; :53 does not define effective-row field set |
| spectrum S-CELL-ORDER | Preserved winning `[C2,C1]` versus normalized `[C1,C2]` | 1 | schema.md:13 says set-valued comparison; :53 does not define output cell order |

All cited schemas are in the respective original task's `environment/data/`; CAUSES.csv gives absolute references plus captured-program lines and full expected/actual structures. Originals contain inputs and a schema, not example outputs resolving these omissions. Calling the discrepancies merely FORMAT would obscure that the expected format was not determinable.

Pension: **six of nine entire reports match on all eight extracts**, including every accrual atom, COLA transition, member benefit, plan rollup, audit hash and manifest. The effective-service section of the seventh also matches. Spectrum: **eight of nine entire reports match on all eight extracts**, including every slice, winner, preemption, cent allocation, correction, settlement and audit hash; revision decisions inside the ninth match too. These are byte comparisons, not approximate numerical comparisons. This does not certify correctness on all possible conforming inputs; latent concerns outside these fixtures are deliberately not counted as causes.

### Why Eight Failures Do Not Mean Eight Broken Rules

Pension `tests/test_output.py:100-111` and spectrum `:275-299` swallow every exception and compare a single digest of all nine report filenames and bytes. Scenario names suggest domain checks, but the assertion is whole-bundle equality. Instrumentation invokes the original comparison without `_holds`, runs the original oracle on **the same exact inputs**, and verifies every regenerated oracle digest equals the frozen constant.

All sixteen original failures are empty-message `AssertionError`; wall times span 0.0222-0.0324 seconds, far below the 120-second subprocess timeout. Evidence: `{task}-instrument/summary.json` and `*/diff.json` contain exception type/message, wall time, input counts, both hashes, field paths and values. `scripts/instrument.py:45-87` implements the driver; no grading logic is changed.

One-fact-wrong experiment: change only `manifest.engine_version` in otherwise exact oracle output, retaining valid canonical JSON. **Every one of the sixteen bundle hashes fails.** Scenario credit drops from 40/40 to 0/40 per task; with the unrelated four positives unchanged, total becomes 12/52, exactly the observed low tests score. This last total is the calculated counterfactual composition, not a separate Harbor run of a mutated submission. The actual per-case altered reports are retained under `one-fact-wrong/`, with `one_fact_wrong_fails:true` in every summary. QC `Final_checklist.md:491` specifically rejects this collapse of independent facts and repeated loss for the same root.

Trigger-depth counterexamples are separate from lost-point causes: dropping pension event-ID ordering at oracle line 203 or spectrum party-ID winner ordering at line 258 leaves every hidden expected report unchanged. `{task}-instrument/trigger-probe.json` and `scripts/trigger_probe.py` show that these final tie-breaks lack discriminating coverage. A test name is not AL-27 evidence.

## Lost Judge Points

Across two tasks, **88/112 raw positive judge points** were lost. Per task the loss is 44/56 = 78.5714 normalized judge percentage points. JUDGE_LOSS.csv has exactly twenty rows: R2-R8 at five and R9-R11 at three for each task. Passed R1/R12/R13/R14 are three each; negative R15/R16/R17 do not fire.

| Class | Pension raw loss | Spectrum raw loss | Combined | Share of lost judge points |
|---|---:|---:|---:|---:|
| PROBE-SKIPPED | 35 | 35 | 70 | 79.5455% |
| PROCESS-SKIPPED | 9 | 9 | 18 | 20.4545% |
| FIGURE-WRONG / NEGATIVE-FIRED / OTHER | 0 | 0 | 0 | 0% |

PROBE-SKIPPED means **independent expected-value evidence missing**, not necessarily no scenario run. Both agents built and ran purpose-built fresh extracts. Pension mostly printed outputs. Spectrum actually asserted Decimal gross arithmetic and winner-plus-owner conservation; its lost bundled criteria additionally demanded auction-boundary proofs and a deliberately chosen share-rounding case. `JUDGE_LOSS.csv` preserves each original reason and step; readable full trajectories are in `{task}-recorded/trajectory-steps.txt`.

Process losses concern complete field/order checks, independent input digest/audit recomputation and input preservation snapshots. Both reordered inputs and compared eight reports. Excluding raw manifest input hashes was correct: those hashes must change when JSONL bytes reorder. Pension R11's literal all-output-byte stability demand is impossible alongside its raw-input manifest; missing preservation evidence remains a valid omission. The table classifies the **recorded decisions**, not a claim that every phrasing or weight was fair.

Conduct criteria do not require announcement under IN-8/AL-1. Their mere absence from instruction is not the unfairness finding. However, many five-point, all-or-nothing verification-habit criteria exceed the kit's minor weighting for odds-raising conduct; copying their scale and arbitrary checkpoint counts is not justified. Consult QC `01_Instruction_QC.md:38`, `05_Alignment_Integrity_QC.md:21,35`. These failures demonstrate sparse independent verification evidence, **not** a causal link to wrong business results on these extracts.

## Three QC-Compatible Mechanisms to Reuse

These are **design recommendations, not an empirical guarantee that a redesigned task will fail Opus**. No new domain bundle was authored or certified here.

1. **Fresh extracts with real interaction witnesses.** Reuse eight fixed variants around an explicit 8-12-stage domain contract, but make each precedence pair decisive. Include equal-ranked conflicts, abutting endpoints, true rounding midpoints and signed residual ties. Grade independent rule-family facts rather than entire report bundles. This retains legitimate generalization pressure while satisfying IN-8/AL-1/AL-27; complete missing output schemas first.
2. **Independent boundary arithmetic as low-weight conduct.** The observed omission is printing plausible outputs without independent expected results, even on a fresh probe. A small, method-neutral criterion for independently validating a genuinely critical boundary or conservation law is defensible. Weight odds-raising conduct as minor (e.g. three), accept equivalent approaches, and avoid seven near-duplicate maximum-weight criteria or mandatory arbitrary probe counts. These changes follow AL-1's conduct split, rather than assuming unannounced habits can carry unlimited weight.
3. **Canonical integrity and preservation checks with proportional credit.** Reuse independent digest/hash-chain recomputation, repeat-run stability and input snapshots. Distinguish invariant semantic outputs from intentionally changed raw input digests. Give these facts their own small budgets, not a repeated dependency in all correctness checks. This retains the observed audit/preservation verification weakness without CL-4 cliffs or impossible manifest comparisons.

Concrete domain recipes, extract counts, rule density, scoring budgets and avoid lists are in TASK_pension.md (subscription proration) and TASK_spectrum.md (warehouse allocation). Their five-gate tables mark IN-8, AL-1, AL-27 and CL-4 **LIKELY FAIL** for the originals; IN-17 **PASS scoped to unnecessary pre-announcement**, not an overall certification.

### Not Copyable Under the Kit

Undocumented output key sets, issue-ID scope and list ordering; oracle behavior contradicting the contract; hashing nine reports into each five-point scenario; repeatedly pricing one metadata fact; assuming seed constants imply a generator; calling named scenario failures proof of failed domain arithmetic; treating missing conduct assertions as measured wrong results; impossible raw-manifest stability; and final tie-breaks with no discriminatory fixture. Also avoid same-action negative penalties in both layers (QC `05_Alignment_Integrity_QC.md:39`), although none fired in these runs.

## Evidence and Verification

`CAUSES.csv`: 16 failed checks, 35 primary root rows plus 16 nonadditive amplification rows. `JUDGE_LOSS.csv`: 20 lost positive criteria. `inventory.json`: input counts and exact-report sets. `replay-results/`: successful verifier outputs and result metadata. Scripts reproduce copying, runtime substitution, Harbor runs, field diffs, trigger probes and accounting. `validation.json` records all consistency assertions.

Originals remained read-only; no agents, git, web, host dependency installation or paid calls. Session rename was attempted first but the supplied tool returned NOT RENAMED because no session matched the board ID; TODO records this. Python LSP diagnostics were unavailable because basedpyright was not installed and installation had previously been declined; scripts were instead syntax-compiled and exercised directly, with CSV/JSON accounting assertions. No full new-bundle QC certification is claimed. Owned containers were auto-removed and owned verifier image tags removed; no large files needed deletion from the 2.2 MB scratch copies, and logs/results remain.
