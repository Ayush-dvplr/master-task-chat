# C card: chainfold-resume-repair

Base `T=/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Perfect_for_Delivery/Dinshi_Jain/chainfold-resume-repair`. Line numbers point to the current (post-QC) files.

## 1 Scores and verdict
- Recorded overall 62.93, tests 78.49, rubric 47.37. Final = (tests + rubric) / 2 (score.json: (78.49+47.37)/2 = 62.93).
- QC re-grade: tests 67/87 = 77.01% after "two duplicated checks were removed" (QC report :34, re-grade table).
- Verdict **GENUINE** (A file). Genuine test points lost: 20 (re-graded 87 scale): beta 5, gamma 5, delta 5, rollups 5. No negative fired.

## 2 Inventory
- Domain: training-run ledger auditing (restart/rollback/accumulation/LR schedule/probe selection). Archetype: repair + reusable program (`/app/out/optimize.py --data --out`) + 9 canonical JSON reports, run again on unseen archives.
- Files seen: about 60 in `environment/data`: 20 `segment_*.jsonl` + 3 `tail_*.jsonl` (130 lines in total), shard manifests a-j csv, 6 policy/contract md (run_contract, policy_ordering, policy_precedence, policy_arithmetic, policy_validation, policy_serialization), worked_examples.md (an invented mini run), json configs (accumulation_policy, schedule_base, schedule_phases, metric_cadence, restart_log, restart_exceptions, probe_log), csv (shard_moves, checkpoint index ...).
- Instruction: 747 words, 45 lines. 5400 s.
- Tests (stacking_check, current): 29 checks, positive 87, negatives -12 (hardcoded -5, filename -3, nondeterministic -3, rebinds_verifier_dependencies -1). Hidden tier (alpha x4, beta, gamma, delta, seals, rollups, output_set) = 48/87 = 55%.
- Judge: 26 criteria, positive 69, batched (`tests/judge.toml`).

## 3 Test architecture
- Expected values come from an **independent mirror inside the test file**: `_mirror` (tests/test_output.py:988-1077) and `_ledger` (1080-1234), with helpers `_rounded` 894 (half-even, zero-denominator box), `_width_for` 945 (lane > waiver > phase > default, then clamp), `_carry_for` 959, `_pace` 967. QC DS-24 (:81): 14% of lines shared with solve.py; the reviewer read them as a "separate implementation".
- Hidden archives are **generated in the test** from `PLANS` (350-593) + `LANESETS` (595-633) via `_compose` 646 / `_archive` 761 / `_stage` 861. Each plan is built to exercise one regime: beta = vanishing spans (warmup 0, decay_span 0, log_every 0) + a restart that does not carry partials; gamma = too short to close a window, `"probes": []`, average_window 0; delta = scattered sequences, a plan-row clash, twin markers, an unused phase.
- Program run: `_invoke` 298 under setpriv as nobody (DROP_GUARD 237), after `_grant_read` 274 chmods the program (QC :79).
- Isolation: `_compare(tag, fields)` 1619 compares a field tuple across all 5 lanes. Alpha is split into 4 field families (core/faults/schedule/selection, 1632-1684); beta/gamma/delta each compare `ALL_FIELDS` whole lane (1687-1708). `h_hidden_rollups` 1730 loops all 4 tags and fails if any roll-up disagrees. So one wrong fact in gamma costs gamma 5 + rollups 5.
- Partial credit: per-family bool checks; no float scoring. QC CL-4 (:75) computed 59/87 = 0.678 for one wrong value.
- Negatives: 1785 hardcoded, 1803 filename, 1834 nondeterministic, 1854 rebinds verifier dependencies; each is a cheating act. No wrong-reading negatives.
- Mutation-style: the plans are regime variants of one generator; no explicit mutate-and-compare pairs.

## 4 Lever table (failed checks)
| id | w | rule graded | rule locations | form | agent reading | correct reading | why self-test missed | fully stated? | nearest |
|---|---|---|---|---|---|---|---|---|---|
| h_hidden_gamma_empty | 5 | value of `best_checkpoint` when no probe matches | run_contract.md:44 "best_checkpoint the settled best checkpoint identifier"; no other mention (grep of data md/json for best/checkpoint/empty/absent/null) ; test `pick = ""` (tests/test_output.py:1174) | other: **default left unstated** (no-value case of a string field) | `best_checkpoint = "none"` (artifacts optimize.py:562) | empty string | the shipped run has probes; agent's stress archives (steps 22-23) also had probes INFERRED | **NO, HIDDEN RULE** (nullable/empty with no stated empty value; it is on LEVER_RULES "never used" list line 24) | NEW / never-used list |
| h_hidden_beta_degenerate | 5 | whole lane under zero spans + no-carry restart | policy_arithmetic.md:13, :34-36, :64-67 (zero denominator -> 0 + one event); policy_validation.md:58-59 rollback window | plain sentence | static compare shows agent zero-denominator, carry and rollback paths equivalent (optimize.py:335-339, 462-475 vs test 959-965, 1084-1130) | not located | n/a | undetermined (static) | INFERRED: the same empty-value or field-default class; **not proven** |
| h_hidden_delta_order | 5 | scattered sequences, plan clash, twin markers | policy_ordering.md:16-43; policy_precedence.md:85 | multi-doc composition | static compare equivalent on ordering/dup/marker paths | not located | n/a | undetermined | not proven |
| h_hidden_rollups | 5 | roll-ups agree for all 4 tags | test 1730 loop | cascade | n/a | n/a | n/a | cascade of the above | G1-style cascade |

Note: the worked example contradicts itself (worked_examples.md:21-24 says 17 "survive[s]" yet lists accepted 11,12,13,14,18,19,20). The agent saw this (step 16 think: "The worked example's record list conflicts") and followed the prose rule (policy_validation.md:58-59). The test uses the same exclusive window (`low < seq < high`, test 1092), so the contradiction cost nothing.

## 5 How tests handle QC
- TS-13 ✅ (QC :223): one field family per check. But beta/gamma/delta compare ALL_FIELDS for each lane (whole-doc-per-regime); QC accepted this as "one property" per regime.
- TS-16 ✅ (:226): negatives are cheating acts only.
- TS-19 ✅ (:229). Promise "A zero denominator has a stated answer" (instruction.md:31) is graded by beta.
- TS-20 ✅ (:230): 1 hygiene, 3 visible, 5 hidden.
- TS-26 was FAIL (:34) "two duplicated tests are gone. `h_burst_carry` and `h_steady_schedule` were deleted"; the pass came from deletion, not from merging.
- IN-15 ✅ (:171), IN-16 ✅ (:172): QC did not flag the unstated empty `best_checkpoint`, which is risky under our rulings (IN-16/TS-19 "every promise graded" is satisfied, but a graded value with no stated rule is our "never used" item). It passed.
- AL-28 ✅ (:289) five distinct acts.
- CL-4 ✅ (:75, :275) "59 of 87 = 0.678 ... no cliff": QC accepts a natural cascade of 28 points for one wrong value.
- JD-7 ✅ (:252).
- Warns kept: TS-25 `e_integers_only` passes on absence (:49); TS-29 hang exceeds verifier timeout (:51); AL-2 the "only ten deliverables" promise is ungraded (:53).

## 6 Leak avoidance
- W3/W6: "The run you can see is a quiet one. Rules that sit idle in it are live in other runs" (instruction.md:37). The shipped run separates nothing. Every hard regime is hidden only (W5).
- W1 kept: "A zero denominator has a stated answer and a stated side effect, and both are the ones you must produce" (instruction.md:31) names the class, not the value.
- Worked example disowns the archive: "They do not describe the archive that ships with them" (worked_examples.md:3-5, QC CL-3 :88), so no figure can be lifted.
- Shipped data does not separate (no zero spans, no empty probes); visible tests compare only the shipped lanes.
- LEAK_LIBRARY: avoids CR-2 (no decoy refuted next to its use) and V0-1 (rules spread over 6 notes, not numbered steps).

## 7 Agent behaviour
- Read every note in order (steps 4-10, 12:06:55-12:07:13, first 30 s), then the configs and csv (11-13), and data probes (14-15).
- Step 16 (12:10:29, minute 4) think: noticed the rollback contradiction. First full program at step 17 (12:12:09, minute 5.5); rewritten at step 19 (12:13:45).
- Self-tests: shipped run (21), hand-made mini archive mirroring the worked example (22), stress archive with shared-sequence markers (23), a verify script (24-25), a determinism double run (28).
- Graded logic did not change after step 19 (INFERRED from the step list: later steps only run and tidy).
- Final claim (step 32): canonical, integers only, and a description of the reconstruction; it made no claim about empty-probe archives. The claim is accurate apart from the untested regimes.

## 8 Passed checks
- Hygiene (4x1 + program_runs 3), all visible-lane families, fingerprints, and alpha x4: the shipped and alpha regimes match the prose the agent transliterated.
- seals and output_set passed on all tags, so the program ran cleanly everywhere and lost only on values.

## 9 Take-aways
- SAFE adopt: build hidden regime archives from one in-test generator, each plan planting one idle-in-shipped branch, and say in the instruction only that idle rules are live elsewhere.
- SAFE adopt: a worked example that explicitly disowns the shipped data.
- RISKY (passed QC, conflicts with our never-used list): a graded empty/no-value default for a string field that no file states.
- Avoid: a roll-up check that loops all hidden tags (one regime fact is paid twice; QC accepted it as a natural cascade).
