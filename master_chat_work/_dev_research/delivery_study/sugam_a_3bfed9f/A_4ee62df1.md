# A_4ee62df1 — artefact check

Task: `Perfect_for_Delivery/Sugam_Agrawal/4ee62df1-ecaf-5e15-a9f8-16682c3136e7` (offline security-policy compiler `sealb-ctl`: repair a CLI in tool.zip, replay a change journal, reduce 50 corpora in many formats).
Board: overall 48.99 / tests 20.62 (20 of 97 positive weight) / rubric 77.36 (41 of 53).

## Verdict: PARTLY
The agent misread one rule, and that misreading is genuine. It is amplified by two grader gates. One gate is designed and stated in the contract. The other is not stated, and it zeroes 15 points of checks whose own property the agent met.

## Artefact screen (all clean)
- `result.json`: `exception_info` null. Agent ran 16:49:51 to 17:16:25Z (about 27 min) with no timeout.
- `verifier/test-stdout.txt` prints only the reward, with no traceback. No negative fired.
- Every artifact exists: `artifacts_exist` (w1) PASS. `tool_round_trips` (w5) PASS, `report_transcript_real` (w5) PASS (it replays the agent's recorded CLI commands and rebuilds config.json byte-identical, tests/test_output.py:594-628), and `config_is_flat` PASS. So there was no crash, no path error and no permission error. The grader ran the agent's CLI as `nobody` (`run_tool` :664-687) with no failure.

## Root cause (one misreading)
- Correct rule: the spine (`config.json`) replays only `env == "base"` operations. Each zone profile replays only its own env's operations, against that zone's own state. Reference `_stateful_replay_for` tests/test_output.py:429-433: `if op.get("env") != env_name: ... continue`. TRUTH.md trap 9: "Zone operations are replayed on top of each zone's starting profile and judged against that zone's own state".
- Agent's reading: it applied one shared state to every env. Trajectory step 25 debug trace: the state is the correct base {467,180,3600,4,strict-seal} up to seq 9000, then "9002 core set retry_budget 9 VALID" and "9004 dmz set rekey_interval_s 43000 VALID" mutate the spine. Final spine {300,160,600,4,"audit-seal"} against expected {467,180,3600,4,"strict-seal"} (TRUTH.md:125-128). J was 8591 against an expected 8592.
- Why the reading was available: config_contract.md:14-19 (spine step 2) says to replay the journal, and that an op is valid when "its `env` is listed in `journal_envs`". `journal_envs` includes core/edge/dmz/mgmt (validation_rules.json:244-247). Nothing in the spine section restricts the spine to `base`. The restriction exists only by contrast: in the profile section ("replay the valid journal operations whose `env` is that zone", contract :37-38), in instruction.md:9 ("Generate the base spine") and in instruction.md:10 ("replaying only that zone's valid journal operations"). Sentence form: scope by omission.
- Consequence: R = 600 instead of 3600, so shift = 600%97 + 8591%31 + 19 = 41 instead of 35 (agent build log). TRUTH.md: "Forty corpora carry an otherwise eligible row at every value from hi + 1 to hi + 178, so a shift that is wrong by any amount changes those forty aggregates."

## Failed checks (77 points) by mechanism
| Group | Checks (weight) | Pts | Mechanism |
|---|---|---|---|
| Direct wrong VALUE | config_matches_policy 5, profiles_match 5, rejected_ops_match 5, validation_report_correct 5, manifest_correct 5, cli_reproduces_derived_outputs 5, aggregates_match 5, zone_totals_match 3, corpus_index_match 5 | 43 | wrong spine, so wrong J/R/shift, so wrong aggregates, eligible counts and hashes |
| Anchor gate (designed, stated) | aggregates_csv 3, _tsv 1, _xml 3, _ini 1, _env 3, _md 1, _txt 1, posture_match 3, summary_correct 3 | 19 | `_anchor` :530-546 requires agent aggregates to equal the grader reduction at the true shift on >=45/50 corpora. After that, mirrors and posture are compared with the agent's own aggregates. I re-derived them from the agent's files: all 7 mirrors and the posture totals ARE self-consistent with its aggregates.json. They fail only because the anchor fails. The contract states this cascade: "an error anywhere in the pipeline ... moves the effective upper bound of every corpus" (config_contract.md Z shift section). summary: INFERRED that its other fields are correct |
| `_real_work` gate (NOT stated) | json_artifacts_canonical 3, commands_through_cli_count_matches 3, zip_shift_present_and_coherent 3, profile_trailer_embeds_config_sha_prefix 3, config_sha_in_posture_matches_file 3 | 15 | each check calls `_real_work()` first (:1133, :1144, :1157, :1166, :1234). It requires >=1 of {config == wanted, rejected == wanted, aggregates anchored} (:553-562), and the agent missed all three. I checked the agent's files directly: every JSON is canonical, commands_through_cli 65 == len(commands) 65 (>=53), zip is sorted/STORED/single date/attr with zip_shift 19 == Z%53, posture zip_sha and config_sha are correct, and all 4 trailers end ":<zone>:<cfg sha8>". The own property held in all 5 |

Passed (20): artifacts_exist 1, config_is_flat 3, report_transcript_real 5, report_digest_truthful 3, tool_round_trips 5, touch_rejected_counter_nonzero 3 (1059 is correct: touch counting is right even with the wrong env scoping).

## Genuine test points lost
- 62 of 97 weight (direct 43 plus the stated anchor cascade 19), which is 63.9 points of the tests score.
- A further 15 of 97 (15.5 points of the tests score) come from the unstated `_real_work` gate on checks the agent satisfied.
- Without that gate the tests score would be 35/97 = 36.1 instead of 20.6 (computed).
- Gate named: `_real_work` (tests/test_output.py:553). Neither the instruction nor the contract mentions it. A grep for "real work|at least one|45 of" in instruction.md and config_contract.md has no hits.

## Why tests < 30
One scope misreading at the root of the pipeline (spine env filter) feeds R and J into the shift that every corpus bound uses. Two gates then turn it into a near-total loss: the anchor (>=45/50) and the `_real_work` (>=1 of 3) gate.
