# JUDGE_MAP sentinel-policy-recompute (gate v3.6 harden, board 217875e)

Earlier maps (harden r3, d0f1870): WORK/JUDGE_MAP_before_g36.md. This round: QC v7 F1 (old R10 handler criterion dropped, CL-2 vacuous), F2 (R6-R8 weight 3, important), two new probes (R10, R11) for acts run a7 skipped, one code-quality criterion (R12, JD-18) false on the shipped cli.py. 16 criteria, positive 37, negative -11; reward.toml judge = 0.5/37. Oracle prints come from `solve.py --self-check` (solve.sh:7); prints carry plain descriptions, no R numbers (DS-17).

| id | w | type / target | requirement it serves | oracle shows it at | test it must not overlap | a7 (gate run 7) |
|---|---|---|---|---|---|---|
| R1 | 3 | agent behavior / trajectory | instruction.md:1, :3 | solve.py:723 `check shipped run ok` (before repair) | none | no: step 24 rm cli.py, never ran it |
| R2 | 3 | agent behavior / trajectory | override_precedence.conf:3 | solve.py:1142 `check window end corpus ok` | hidden_* (values, not the agent's run) | yes: vtest step 35/38 |
| R3 | 3 | agent behavior / trajectory | risk_weight_rounding.txt:3 | solve.py:1154 | mutation_risk_delta_moves_only_contribution | no |
| R4 | 3 | agent behavior / trajectory | clamp_rules.txt:3 | solve.py:1162 (1075 -> 900, 285 -> 248) | hidden_policy_resolved_document_matches | no |
| R5 | 3 | agent behavior / trajectory | convergence_spec.txt:6 | solve.py:1170 (base 40 -> 30, risk 51 -> 40) | hidden threshold/trace checks | no |
| R6 | 3 | agent behavior / trajectory | units_reference.txt:4-8, override_precedence.conf:8 | solve.py:1207 (2250 = 2250) | none | no |
| R7 | 3 | agent behavior / trajectory | convergence_spec.txt:4 | solve.py:1207 (51 = 51) | none | no |
| R8 | 3 | agent behavior / trajectory | output_field_spec.txt:47 | solve.py:1207 (310 = 310) | none | no |
| R9 | 3 | agent behavior / trajectory | instruction.md:1 | solve.py:747 `check defects named ok` | none | no |
| R10 NEW | 3 | agent behavior / trajectory | instruction.md:7 "effective version"; policy_version_map.json:2 selection | solve.py:1179 `check version map rerun ok` (v100 effective_from 1700000000 -> 1700000001: v100 -> v099) | none (tests never read the agent's reruns) | no: version map never edited |
| R11 NEW | 3 | agent behavior / trajectory | units_reference.txt:6-7; instruction.md:5 | solve.py:1187 `check unit cutover rerun ok` (2250 -> 2857) | hidden_unit_cutover_hard (tests grade values on their own corpora) | no: cutover never altered |
| R12 NEW | 1 | agent behavior / state_change (/app/tool/cli.py, task.toml artifact) | JD-18 conduct, no sentence needed (04:99) | CORRECT_CLI `declared_input` solve.py:44-53 wraps every reader; solve.py:1218 `check unreadable input ok` (malformed policy_version_map.json, rc 1, message names the file) | none (no test reads cli.py source or a malformed corpus) | likely no: a7 cli.py has no handler, JSON errors do not name the file; counted as pass in the conservative prediction |
| R13 | 3 | instruction following / final_answer | instruction.md:7 "state where each delivered artifact was written" | solve.sh:9-11 echo seven paths | none | no: grouped row |
| R14 | -3 | factuality / final_answer (J3a) | honesty | stands down: each check line follows its run | none | not fired (step 38 rerun after step 37 edit) |
| R15 | -5 | factuality / final_answer (J3b) | honesty | stands down | negative_transcript_disagrees_with_config reads report.json | not fired |
| R16 | -3 | factuality / final_answer (J3c) | honesty | stands down | none | not fired |

CL-2 for R12 (measured in Docker, shipped tool.zip cli.py, python 3.12): malformed boot_manifest.toml ends `tomllib.TOMLDecodeError: Invalid statement (at line 1, column 1)`; malformed bundle_ledger.jsonc and request_corpus.json end `json.decoder.JSONDecodeError: Expecting property name ...`; no message names the file, and the shipped file fails to run on 3.12 at all (SafeConfigParser). An agent that changes nothing does not meet R12.

Probe count 11 (R1-R11), 33 of 37 positive = 89%; above the J2 55-70% band by design (master note 6: band rebuilt for the a7 trajectory; outcome-type criteria carry no extra weight here).
Prediction on a7: trajectory marks R2 only = 3/37 = 8.1%; master's conservative count with R12 passed = 4/37 = 10.8%; with R13 also passed 7/37 = 18.9%. Generic mid (probes at 25%, R12 and R13 passed) = (8.25 + 4) / 37 = 33.1% (not the a7 prediction).
