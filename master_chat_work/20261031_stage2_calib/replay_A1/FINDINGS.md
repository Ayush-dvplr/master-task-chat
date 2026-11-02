VERDICT: The replays match all three recorded test scores, but most allocated normalized test loss comes from ungrounded contracts; the strongest proven QC-clean failure mechanism is shared-channel echo attribution defeating independent offset voting.

## Reproduction

| Task | Recorded Tests | Captured-File Replay | Oracle Tests | Lost Test Points | Recorded Judge |
|---|---:|---:|---:|---:|---:|
| billing | 7.22% | 7.22% | 100.00% | 92.783505 | 24.14% |
| pm25 | 9.09% | 9.09% | 100.00% | 90.909091 | 24.14% |
| royalty | 23.08% | 23.08% | 100.00% | 76.923077 | 10.71% |

All replay criterion values, including negative checks, match the recorded values, not just the aggregate score. Every oracle criterion earns full positive credit and no negative penalty. See [REPLAY_SUMMARY.json](REPLAY_SUMMARY.json), `evidence/<task>/replay_reward-details.json`, and `oracle_reward-details.json`. Recorded `score.json` and `pass_summary.json` agree on the user's final/tests/judge figures. Rounded composite `reward-details.json $.reward.score` is not substituted for the exported final score.

Replay `solve.sh` only copies the captured `artifacts/app/` payload into `/app`; it never reruns or repairs the captured program. Diagnostic counterfactuals are separate, never used to obtain the replay score. All 46 original hidden cases run successfully, with no diagnostic exception or timeout. Observed child-runtime ranges: billing 0.258-2.605 seconds, PM2.5 0.219-0.860 seconds. Royalty's 0.078-0.100 seconds measures the combined oracle-plus-agent diagnostic section, not one isolated agent invocation. Each case records wall time, exception details, and stderr in `evidence/<task>/case_NN.json` and associated stderr files.

## Lost Test Weight

Denominators differ: billing 97, PM2.5 110, royalty 52 positive raw weight. The principal share below sums each task's normalized percentage-point loss, giving each task equal scale. Raw-weight shares are also shown; they are not interchangeable with normalized shares.

| Cause | Allocated Raw Weight | Raw Share | Normalized Lost Points | Normalized Share |
|---|---:|---:|---:|---:|
| UNFAIR | 130 | 56.52% | 169.706582 | 65.12% |
| LATENT-WRONG | 100 | 43.48% | 90.909091 | 34.88% |
| RULE-MISREAD | 0 | 0% | 0 | 0% |
| RULE-MISSED | 0 | 0% | 0 | 0% |
| EDGE-INPUT | 0 | 0% | 0 | 0% |
| FORMAT | 0 | 0% | 0 | 0% |
| AMPLIFIED | 0 | 0% | 0 | 0% |
| CRASH | 0 | 0% | 0 | 0% |
| TIMEOUT | 0 | 0% | 0 | 0% |
| Total | 230 | 100% | 260.615673 | 100% |

**Allocation rule:** a failed +5 check is charged once. Where independently sufficient causes coexist, prefer a demonstrated in-contract inference failure, and record the ungrounded co-cause with zero additional weight. Thus all 20 PM2.5 checks have a LATENT-WRONG row worth +5 and an UNFAIR co-cause row worth zero. `CAUSES.csv` has 66 rows covering 46 failed checks and 230 raw lost weight. These shares are an explicit accounting policy, not uniquely identifiable causal fractions. Charging PM2.5's overlapping loss to its clock-contract defect instead would make UNFAIR 100%; it would hide the genuine echo failure, not establish that it does not exist.

AMPLIFIED is a structural modifier, not extra allocated weight: whole-extract/hash gates multiply the consequences of underlying errors. Positional JSON/JSONL leaf-difference counts are provided for every check, but ordering cascades and repeated totals are not additional independent mistakes. The CSV links every full expected/actual delta rather than treating a scenario name as a diagnosis.

### Billing: A Forbidden Temporal Model

The dictionary says a handset is set when issued and **never adjusted afterwards**, with one whole-minute offset (`59417607-2254-5165-b703-0d5a4aeb7367/environment/data/record_dictionary.md:19`). Captured `transform.py:217-299,344-346` implements one offset per handset. All 18 hidden profiles change offsets, and reference `tests/test_output.py:935-961` solves a different value per day. Those outputs are not a latent fact consistent with the stated model.

Injecting only the changed handsets' reference schedules, while leaving constant handsets' inference and every billing rule unchanged, makes **all 18 extracts and all 13 reports exact**. This stricter separation is in `evidence/billing/clock_separation.json`; the full field-level counterfactual is in `counterfactual_summary.json`. Therefore the 90 raw lost weight is assigned to the contract mismatch, not to unproven allowance, rate, rounding, or amendment errors. See [TASK_billing.md](TASK_billing.md) for the 18-seed inventory and rule citations.

### PM2.5: A Real Echo Failure Plus A Contract Defect

The dictionary's offset holds for every row of a card (`98ed74c1-19ac-5ec8-adaf-392a172d4600/environment/data/record_dictionary.md:40-44`), but every hidden profile uses clock steps. Separately, the agent's independent maximum-match vote (`derive_report.py:236-260`) misattributes shared-channel echoes even on units whose clocks are constant. The generator explicitly forces vote counting to fail and retains at least three single-candidate anchor receipts per segment (`tests/test_output.py:689-719,1142-1174`).

Profile 01 shows the distinction sharply: only three data-quality fields differ, and all eight other reports already match. Received-packet counts are 1749 versus 1256 for AQ525, 654 versus 1212 for AQ766, and 694 versus 1139 for AQ814 (`case_01.json $.reports.data_quality.json.differences`, expected versus actual). AQ525 changes clocks; AQ766 and AQ814 do not. Their true offsets are -4 and +14, but the agent selects -10 and +7.

Correcting only stepped units leaves **all 20 checks failing**; correcting every offset makes all 20 exact (`clock_separation.json`, `counterfactual_summary.json`). Three newly generated probes with **no clock steps anywhere** also fail the unmodified captured program, with two fooled echo pairs each (`conforming_echo_probes.json`). This is direct evidence for a copyable, conforming-clock inference trap, not just an interpretation of a low score. See [TASK_pm25.md](TASK_pm25.md).

### Royalty: One Unspecified ID, Not Eight Arithmetic Failures

Every one of eight scenarios differs at exactly two leaves: `data_quality.json $.issues[2].record_id` and `exception_register.json $.exceptions[2].record_id` contain `ST-BAD-A`, while the oracle expects `ST-BAD`. All seven other files, including financial ledgers, rollups, manifest and audit chain, are byte-identical. All eight oracle bundles were first validated against the verifier's fixed hashes (`evidence/royalty/case_NN.json $.oracle_hash_valid`).

Schema line 9 specifies statement ID for REVISION_TIE_CONFLICT, but does not specify the identifier for INVALID_STATEMENT; line 39 only sorts issues, and line 51 copies them into exceptions. Agent line 315 uses the offending winner's globally unique record ID; oracle line 51 uses statement ID. One expression changed to the oracle convention makes **all eight bundles exact**, without changing financial logic. The 40 raw loss is UNFAIR with severe amplification, not eight demonstrated finance bugs. See [TASK_royalty.md](TASK_royalty.md).

## Lost Judge Weight

Judge positive denominators are 58, 58, and 56. Missing positives and fired negative penalties are included once each. The 32 rows in `JUDGE_LOSS.csv` retain criterion text, verbatim recorded reasoning, and original trajectory step references. `RECORDED_CHECKS.csv` includes all passed, lost, and unfired criteria with JSON paths, not just losses.

| Class | Raw Lost Weight | Raw Share | Normalized Lost Points | Normalized Share |
|---|---:|---:|---:|---:|
| FIGURE-WRONG | 70 | 50.72% | 120.689655 | 50.08% |
| PROBE-SKIPPED | 35 | 25.36% | 62.500000 | 25.93% |
| PROCESS-SKIPPED | 24 | 17.39% | 41.933498 | 17.40% |
| NEGATIVE-FIRED | 6 | 4.35% | 10.529557 | 4.37% |
| OTHER | 3 | 2.17% | 5.357143 | 2.22% |
| Total | 138 | 100% | 241.009852 | 100% |

Billing loses 35 for seven wrong what-if figures and 9 for missing actual-open tracing, ambiguity error, and empty-fit handling. PM2.5 loses 35 for seven wrong figures, 6 for offset/journal consistency handling, and fires -3 for overstating distinct check counts. Royalty loses 35 because independent expected-value probes were not demonstrated, 9 for incomplete schema/digest/shuffle evidence, 3 for overstatement, and another -3 negative for unsupported validation claims. Correct royalty financial outputs do not establish that the requested independent verification occurred; conversely missing verification does not establish incorrect arithmetic.

**Inference boundary:** the expected/actual what-if integers and each judge's stated reason are directly recorded. Extending the experimentally proven hidden-test clock explanation to each individual what-if is **INFERRED**, not separately field-replayed here. Process conclusions are grounded in the captured source and executed trajectory. An absence of executed arithmetic assertions is not proof that no mental calculation happened.

## Three Copyable Mechanisms

1. **Anchored ambiguity that defeats a plausible heuristic.** Use two low-receipt/high-receipt shared-channel echo pairs with a long frame-lockstep interval, but preserve at least three uniquely attributable receipts for each constant-clock unit. The wrong independent vote gets more matches; a correct joint attribution respects all receipts and capacity. Start with 12-20 deterministic conforming extracts, grade recovered values/attribution separately, and keep a small end-to-end integration slice. The three no-step probes prove this mechanism survives the QC-relevant contract repair. Grounding and determinacy satisfy IN-8/AL-1; anchors satisfy IN-17 without announcing the answer; explicit trigger fixtures satisfy AL-27; sliced scoring avoids CL-4 cliffs.

2. **Grounded cross-rule composition with paired precedence defects.** Transfer billing's source precedence, amendment timing/reverts, gross-versus-net scopes, allowance ties, effective intervals and rounding, or royalty's revision/rounding/stateful-priority interactions. Use roughly 12-17 documented operational families and 8-18 independent fixtures, including both defects in every precedence pair. Define clock granularity, error identifiers, tie order and raw-versus-semantic determinism. Grade decisions, arithmetic and aggregate conservation separately so a common issue ID cannot zero unrelated scenarios. These are proposed QC-clean designs, not claims that this Opus run failed royalty arithmetic.

3. **Independent probes and auditable, truthful validation.** Require a small midpoint calculation, a multi-priority/cross-period transition, and an independent digest/audit recomputation; accept any competent testing method. Preserve an executed-fixture registry with deduplicated input hashes, actual-open evidence where it raises correctness odds, and input immutability checks. Royalty's missing probe evidence and PM2.5's inflated distinct counts are direct examples. Keep conduct weight proportionate and avoid duplicate negative charges. AL-1 permits unprompted correctness-raising conduct checks, not a preferred framework disguised as correctness (`05_Alignment_Integrity_QC.md:21`).

## Not Copyable

- Constant clocks in authoritative documents combined with changing hidden clocks: LIKELY FAIL IN-8/AL-1 (`01_Instruction_QC.md:38`; `05_Alignment_Integrity_QC.md:21`). Do not call violating the stated model a successful latent-value challenge.
- An unspecified INVALID_STATEMENT identity behind every financial bundle: LIKELY FAIL the same grounding gates and CL-4 (`Final_checklist.md:491`). Royalty's one-fact error takes tests from 100% to 23.08% with every financial target already correct.
- Missing trigger coverage: royalty's hidden variants do not exercise invalid-allocation/invalid-adjustment quarantine, despite those graded schema rules. LIKELY FAIL AL-27 (`05_Alignment_Integrity_QC.md:38`). The cards distinguish inspected triggers from an exhaustive mutation certificate.
- Requiring raw-input manifest bytes to survive JSONL row reordering conflicts with hashing every raw input byte (`royalty schema.md:3,37`). The agent's manifest exclusion is justified; claiming all-output byte identity anyway is not.
- Reading scenario names as error diagnoses, suppressing all exception/stderr detail, or reporting every repeated output delta as a distinct reasoning failure. Billing/PM2.5's explicit exact-match instructions qualify for the kit's CL-4 exception, but that exception does not fix unfair inputs. Royalty has no equivalent explicit all-or-nothing exception.

Full IN-8, IN-17, AL-1, AL-27 and CL-4 verdicts, source lines, density/burial analysis, input inventories, and domain-transfer recipes are in the three mechanism cards. IN-17 is not a reason to withhold an otherwise unspecified requirement (`01_Instruction_QC.md:47`). Positive loss plus one negative is not automatically forbidden multiple-negative stacking under AL-28.

## Replay Differences And Audit

Original tasks were never edited. Initial scratch Harbor attempts could not resolve the private ECR base (401). Only the registry name was changed to cached public ECR while preserving exact image digest `sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b`. Both original and replay copies use that same base.

The unchanged reward runner then aborted because oracle/replay runs have no paid-agent trajectory: `ValueError: Trajectory not found: /logs/agent/trajectory.json`, followed by missing reward files. The scratch-only recovery disables judge discovery and normalizes the unchanged test component to 100%. It changes neither `test_output.py`, test weights, inputs, expected values nor captured program. Six successful `a3-*` Harbor jobs produce the scores above; no paid judge was invoked. See `scripts/tests_only.py`, `REPLAY_SUMMARY.json`, and scratch `jobs/a2-royalty-oracle/royalty-oracle__sssgnmW/verifier/test-stdout.txt:55` for the failure.

Scratch root: `/Users/mac/Desktop/Terminal Bench/_runs/20261031/stage2-calib/replay-3d517b2/`. Failed attempts, resource-guard outputs, build logs, six successful job logs, and all rewards remain there. [INTEGRITY.json](INTEGRITY.json) records 96 matching original-versus-initial-copy or captured-payload hashes, including all three verifier programs and original oracle programs. This is snapshot equality, not a claim of an unavailable pre-session hash of the entire source tree.

No web, subagents, git operations, host package installation or paid agents were used. Session rename was attempted first but the naming tool found no matching session. Python language-server diagnostics were unavailable because basedpyright is absent and installation was previously declined; scripts are syntax-checked and exercised against real verifier images instead. All own containers exited and were removed automatically; the three diagnostic verifier image tags were removed; no scratch file exceeds 5 MB. The unrelated pre-existing stopped container was left untouched.

`result_3d517b2.json` is machine-readable and reports normalized test losses. `CAUSES.csv` and `JUDGE_LOSS.csv` reconcile every lost check/criterion without duplicate weight; `VALIDATION.json` records the passing schema/coverage/weight reconciliation. All Python scripts are under 150 nonblank/noncomment lines, separated by preparation, execution, diagnostics and reporting responsibilities; no production task code was refactored. Reproduce preparation, scoring, diagnostics and attribution with the retained scripts; counterfactual and no-step diagnostic corpora must never be mistaken for the scored captured-file replay.
