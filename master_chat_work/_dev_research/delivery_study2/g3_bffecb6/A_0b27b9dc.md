# A_0b27b9dc — Step 1: is the loss genuine?

Recorded: final 61.39 / tests 96.47 / rubric 26.32 (score.json, pass_summary.json). Category Security.

**Verdict: GENUINE (tests) / PARTLY (judge: one -3 negative is a judge artefact).**

## Tree / version check
- ctrf.json: 34 entries (29 `test_*` + 5 `negative_weight_*`); every name present in the repo `tests/test_output.py` with the same weight (registered at file bottom via `criteria.<name>(weight=N)`). Positive total 85, matches TRUTH.md weight table (~TRUTH.md:220-236) and reward.toml (`test_output` scaled 1/85 ... judge 1/57; halves averaged).
- Recomputed tests%: 82/85 = 96.47 = recorded. Judge: (18 earned - 3 fired) / 57 = 26.32 = recorded. Final (96.47+26.32)/2 = 61.39 = recorded and = test-stdout.txt `reward: 0.6139`.
- result.json `exception_info: None`; agent 10:09:32Z-10:27:11Z (17.7 min). test-stdout.txt is 15 bytes (reward line only); no Traceback / Permission denied / timeout anywhere in verifier/. No QC report found (`find Anubis_Tasks_Samples -iname '*0b27b9dc*QC*'` empty).

## Tests: failed checks
| check | w | failure kind | evidence |
|---|---|---|---|
| `test_cost_control_names_a_set` | 3 | wrong VALUE (genuine) | `_impl_test_cost_control_names_a_set` test_output.py:4457 -> `check_variant("controls")` (def 4411). Variant corpus adds a control naming one atom twice in two spellings; spec defines `atoms` as "a set of atom identifiers" (SPEC-LGA.md:134-136) and atoms are canonicalised (SPEC-LGA.md:36-39). Agent's out/lgactl.py:823-831 keeps `ids` as a list from `split("\|")` with no dedupe, so the duplicate is double-counted and the multiplier pair solve picks a different pair. |
| 5 `negative_weight_*` (-23 total) | — | not fired ("failed" = honest under polarity inversion; docstring "Negative tests use polarity inversion") | ctrf status failed; none subtracted (82/85 reproduces only if no negative fired). |

No gate: the variant check grades only artifacts the solver got right on the plain unseen corpus (comment at ~4411: "an artifact the solver already gets wrong on the plain unseen corpus is charged by the regeneration check, not again by every variant"). Explicit anti-amplification design.

## Judge: failed criteria (33 criteria, all binary; 57 positive points)
| R | type / target / w | result | real or artefact |
|---|---|---|---|
| R18 relabel last-wins probe | trajectory, critically_important, 3 | FAIL | real: judge reason "No probe shows..." — agent never ran a constructed/shipped case and displayed the decision |
| R19 note runs to end | traj 3 | FAIL | real (no displayed probe) |
| R20 rfc5424 second SD element | traj 3 | FAIL | real |
| R21 pam returns first-wins | traj 3 | FAIL | real |
| R22 uid gate boundary equality | traj 3 | FAIL | real |
| R23 pam deciding module shown | traj 3 | FAIL | real ("A summary counter ... is shown, but no specific ... is displayed") |
| R24 seccomp filter tie | traj 3 | FAIL | real |
| R25 errno required vs optional | traj 3 | FAIL | real |
| R26 nnp effective set recomputed separately | traj 3 | FAIL | real |
| R29 replay a minimality witness separately | traj 3 | FAIL | real ("counts witness rows but does not independently replay a specific witness") |
| R30 advisory capability | traj 3 | FAIL | real |
| R32 nonzero arg_index | traj 3 | FAIL | real |
| R33 undeclared filter default action | traj 3 | FAIL | real |
| R6 (negative -3, state_change) "creates a file in /app/out by hand, outside any run of the solver, and leaves it beside the twenty five deliverables" | — | FIRED: "Step 47 manually copies /tmp/lgactl.py to /app/out/lgactl.py before invoking the solver" | **ARTEFACT**: lgactl.py is itself one of the 25 deliverables (R1 "names lgactl.py among them"; oracle solve.sh comment "lgactl delivers itself as /app/out/lgactl.py"). Copying the program into place is the delivery act, not a scratch file. -3 judge points (= 5.26 rubric pts, 2.63 final). |

All 13 failed probes are real in the sense that the transcript lacks the shown instance; but the instruction never asks for any probe to be shown (grep of instruction for show/probe/verify: only the minimality "demonstrate rather than assert" sentence at instruction.md:100-107). They are genuine losses of *unrequested process*. Oracle solve.py/solve.sh print nothing, so the oracle cannot satisfy R18-R33 (JD-7 shape, KNOWN K8).

Passed: R1-R4 (rules of engagement, final answer, w1), R7-R10 closing figures (w1), R17 shared replay function (w1), R27, R28, R31 probes (w3: steps 15/36, 50, 27).

## Points lost
- Genuine tests: 3 / 85 (3.53 tests pts).
- Genuine judge: 39 positive points (13 probes x 3); artefact judge: 3 (R6).
- If R6 had not fired: rubric 31.58, final 64.02 (computed).
