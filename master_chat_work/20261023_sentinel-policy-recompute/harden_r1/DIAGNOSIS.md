# DIAGNOSIS: sentinel-policy-recompute (P9 v2 r1, board 55d3b87)

Run: claude-opus-5, trial `sentinel-policy-recompute__pdsnniy`, 2026-10-20 00:36, openhands-sdk 1.55.1. Copy: `baseline_v0/trajectory_job_sentinel-policy-recompute_1b1795/`. BUNDLE tree sha `505104cc7e41` (identical to SOURCE, `diff -rq` clean). Kit HEAD 71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e.

## 1. Phase A: is the score genuine? GENUINE (tests channel 1.000; the 0.7778 is NOT tests-only)

- The master's note says 0.7778 is tests-only. It is not. `result.json` verifier env carries `REWARDKIT_JUDGE=gpt-5.6-sol` with an API key, and `verifier/reward-details.json` has two components:
  - `test_output` weight 0.009259259259 x score 54.0 = 0.5000 (all 22 checks: 18 positives earned 54/54, 4 negatives did not fire);
  - `judge` weight 0.018518518519 x score 15.0 = 0.2778 (positives 27, earned R1 5 + R2 5 + R5 3 + R7 5 + R10 1 + R13 1 = 20, R9 fired -5).
  - 0.5000 + 0.2778 = 0.7778. **Tests-only score = 1.000.**
- No failed test exists, so there is no permission artefact to name: ctrf 22/22 passed; `grep -i "permission|errno|denied|not_run|skipped" test-stdout.txt` returns nothing. The run-as-nobody checks (`config_round_trips_through_cli_validator`, `repaired_resolve_reproduces_authoritative_policy`) passed, so the batch-notes permission trap did not trigger here (it remains UNVERIFIED for oracle chmod 600; tested in Phase 3).
- The run used this bundle: `agent/instruction.txt` equals `instruction.md` byte for byte (CR stripped); the 22 check names and weights in reward-details equal `tests/test_output.py` (22 `def test_`, P=54); the 13 judge criteria equal `tests/judge.toml`. `judge.toml` and `test.sh` have mtime 21 Oct (after the run) but the criteria and weights are identical.
- Judge points lost (process, not answer): R6 shipped tool never run before the first edit; R11 profiles built by a custom driver, not init/set; R12 error messages; R9 fired (claimed two-run determinism, step 34 diff printed nothing).

## 2. Root cause

| cause | verdict | evidence |
|---|---|---|
| 1 run error / wrong copy | NO | instruction, tests and judge of the run equal the bundle; no errors, no NOT_RUN, no permission lines. |
| 2 harness / rescoring change | NO | run 20 Oct after the last content fix (fixplan_v2, 19 Oct); reward.toml 0.5/54 + 0.5/27 is the formula the run used; kit changes since 2690e960 (K8 pip, H6 `_grant_read`, judge batched) are format checks that do not move the tests score. |
| 3 conversion / QC fixes made it easier | PARTLY | see table below; QC v1 rewrote the tier rule into a direct instruction sentence, QC v2 defined `iterations` in output_field_spec. The traps were already spelled out in the original instruction, so the fixes added a little on top of an already open task. |
| 4 levers weak by design | **YES, PRIMARY** | every one of the 14 traps is stated as a direct sentence, most of them twice (instruction line 5 plus a data file that names the wrong reading). The solver derived every graded number by hand at step 23 before writing any code. |

**PRIMARY CAUSE: 4.** Contributing: 3 (partly). Also contributing: the only whole-document grading runs on the shipped corpus (one principal, one window, one override), so a correct reading of the shipped case is the whole test.

### Cause 3 file list (conversion + QC v1 + QC v2 fix plans)
| file | change | put a rule, figure or separating example in front of the solver? |
|---|---|---|
| instruction.md:1 | v2 #16 deleted "finding the faults is the task rather than something this brief lists" | no (neutral) |
| instruction.md:5 | v1: "comparisons must use the documented boundary operators without shifting the index" became "The threshold tier lookup must use the role level as the tier index without shifting it" | YES, names the trap and its answer |
| instruction.md:7 | v1 added tool.zip member layout, "flat and scalar", "Write nothing under /app/out except the seven artifacts" | partly, format only |
| data/output_field_spec.txt:14 | v2 #8 defined `iterations` as seed plus every computed value ending at the first within epsilon | YES, rule beside its use |
| data/override_precedence.conf | v1 added `match_version = effective version from policy_version_map` | YES, one-line rule naming the v099 gate |
| data/effective_windows.xml, data/override_deltas.json | v2 #7 added WIN-AUTH-V099 + OV-K042-v099 | no (data only, rule already stated) |
| data/report_field_spec.txt, data/tool.zip | v1 field and tool fixes | no |
| environment/Dockerfile | chown 1000 /app, agent user, openhands pre-bake | no |
| solution/*, task.toml, tests/* | oracle, TRUTH, expert 300, judge R10 split, 22 checks, embedded corpus | no (hidden) |

### Cause 4: existing traps, rule location, where the solver got it right, what gave it away
| # | trap | rule text and location | solver got it right | give-away |
|---|---|---|---|---|
| 1 | B9 latest vs B7 active | instruction "retired bundle"; stale_version_rules.txt `retired_bundle = B9`, `prefer = active_bundle_id`, `ignore = latest_bundle_id`; bundle_ledger.jsonc "// decoy latest"; boot_manifest "do not compile" | step 7 read, step 23 "B7" | data names the decoy |
| 2 | half-open window | instruction:5 "treated as half-open, so a candidate effective at exactly a window end instant is excluded"; glossary; override_precedence.conf; reconciliation_rules.conf `window_boundary = half_open` | steps 13, 20 (checked effective_instant_examples.xml), 23 | trap and answer in one sentence, 4 copies |
| 3 | client version v205 | instruction "never from a client-claimed or higher-numbered version"; reconciliation_rules `trust_client_version = false` | steps 12/15, 23 "v100" | named exception |
| 4 | clamp before multiply | instruction "multiply-then-cap"; clamp_rules.txt "multiply THEN cap / do NOT clamp before multiplying"; reconciliation_rules `multiplier_then_cap = true` | step 23 "297 min 285" | trap spelled out |
| 5 | timeout seconds | instruction "milliseconds, with no value left in seconds"; units_reference; glossary; reconciliation_rules `timeout_unit_factor = 1000` + note | step 23 "2*1000+250=2250" | factor given as a key |
| 6 | convergence single step | instruction convergence sentence; convergence_spec.txt formula, epsilon 0, seed; output_field_spec:14 | step 23 "40,50,51,51" | formula + iterations definition |
| 7 | tier shift | instruction:5 "use the role level as the tier index without shifting it" | step 23 "tier 4 base 40" | trap and answer named |
| 8-10 | SafeConfigParser, validate split, canonical write_json | tool bugs visible in cli.py; determinism_rules.txt | step 8 bug list, step 25 rewrite | ordinary code reading |
| 11 | superseded OV-K042-prev | override_precedence.conf `select = active status only` | steps 14/19, 23 | one-line rule |
| 12 | resolve --out /app/out | instruction seven artifacts only | step 27 used /app/build | named |
| 13 | B9 drift decoy | memo pdf, legacy_override_table.ini, superseded_windows.xml labelled legacy | step 17 | labelled decoy |
| 14 | v099 version gate | override_precedence.conf `match_version = ...` | step 23 "v099 version mismatch" | one-line rule |

## 3. Lever table (ctrf + trajectory)
| check | pts | earned | levers / traps | status |
|---|---|---|---|---|
| artifacts_exist | 1 | 1 | none | n/a |
| config_is_flat_json_object | 3 | 3 | format | n/a |
| config_matches_hidden_seed_policy | 5 | 5 | 1,2,3,4,5,7,11,14 | LEAKED |
| report_records_cli_command_transcript | 1 | 1 | process | n/a |
| report_digest_and_trailer_match_config | 3 | 3 | 1 (trailer) | LEAKED |
| artifacts_parse_and_stay_under_size_limit | 1 | 1 | format | n/a |
| config_round_trips_through_cli_validator | 5 | 5 | 8, 9 | LEAKED |
| profile_dev_matches_resolved_policy_plus_deltas | 3 | 3 | 4,5 + sidecar | LEAKED |
| profile_prod_matches_resolved_policy_plus_deltas | 3 | 3 | 4,5 + sidecar | LEAKED |
| validation_report_covers_all_artifacts_and_profiles | 1 | 1 | format | n/a |
| summary_lists_inputs_profiles_and_artifacts | 1 | 1 | format | n/a |
| policy_resolved_matches_authoritative | 5 | 5 | 1,3,7,14 | LEAKED |
| threshold_curve_converged | 5 | 5 | 6,7 | LEAKED |
| dependency_trace_order_and_decoy_rejected | 5 | 5 | 1,2,11,13,14 | LEAKED |
| tool_archive_is_deterministic | 3 | 3 | 10 | LEAKED |
| json_artifacts_are_canonical | 1 | 1 | 10 | LEAKED |
| config_bytes_match_repaired_cli_rebuild | 3 | 3 | 8,10 | LEAKED |
| repaired_resolve_reproduces_authoritative_policy | 5 | 5 | all, shipped corpus only | LEAKED |
| 4 negatives (-5,-5,-3,-3) | -16 | 0 | cheating acts | did not fire (correct) |
Total 54/54. Every graded trap LEAKED; none HELD.

## 4. Solve autopsy (36 steps)
- Read order: 3 `ls`; 4 unzip tool; 5 `cat` every spec .txt (output/report field spec, convergence, clamp, determinism, rounding, units, stale_version, glossary, precedence); 6 zip infolist; 7 every .ini/.cfg/.conf/.env/.jsonc; 8 `cat -n` README, schema, cli.py; 9-11 parquet; 12/15 version map; 13 windows, superseded, examples; 14/19 overrides; 16 xlsx; 17 ladder, migrations, memo; 18 aliases; 20 checked the half-open examples xml; 21 windows; 22 threshold_overrides judged a decoy.
- Step 23 (think): the full chain and every graded number derived by hand before any code (B7, K042, v100, WIN-DECOY excluded, prev rejected, v099 mismatch, auth selected, 297 min 285 = 285, 3, 2250, contribution 66, tier 4 base 40, 40-50-51-51, both profiles) plus the full cli.py bug list.
- Step 24 deleted cli.py, step 25 wrote a new one (24,750 chars), 26 one str_replace, 27 `resolve --out /app/build`, 28 custom build.py, 29-31 run and inspect, 32-34 two-run sha compare, 35 Decimal recompute, 36 finish.
- Graded logic changed after a self-check: NO. The self-checks (examples xml for half-open, two-run determinism, forbidden keys, Decimal arithmetic) only confirmed the step 23 numbers.
- Self-checks covered traps 2, 4, 5, 6, 10. Nothing in the data could make a self-check green while a value was wrong.

## 5. Reflex program
`OUT/agent_program/`: `tool/cli.py` (rebuilt from steps 25+26; equal to cli.py inside the agent's `out/tool.zip`), `tool/README.md`, `tool/schema.json`, `build/build.py` (step 28 driver), `out/` (the 7 delivered artifacts).

## 6. LEAK_LIBRARY rows
| lever | how it was written | where it leaked | planned fix |
|---|---|---|---|
| half-open window | instruction sentence naming the end-instant exclusion, plus glossary, precedence and reconciliation copies | step 13/20/23 | keep one definition in the windows file's conventions; delete the instruction sentence and the copies (W1/W2); grading moves to hidden reseeded windows |
| retired latest bundle | stale_version_rules keys `ignore = latest_bundle_id`, ledger comment "decoy latest" | step 7/23 | keep the active-bundle rule once in the ledger; drop "decoy" labels |
| multiply then cap | "multiply THEN cap / do NOT clamp before multiplying" in clamp_rules and instruction | step 5/23 | formula line only, no warning (W1) |
| seconds to ms | `timeout_unit_factor = 1000` key + notes + instruction "no value left in seconds" | step 5/23 | unit stated once in units_reference; superseded by per-row unit (L2) |
| tier index | QC v1 instruction sentence "role level as the tier index without shifting it" | step 23 | state the tier key once in the tier file |
| convergence | formula + output_field_spec `iterations` definition beside its use | step 5/23 | keep formula in convergence_spec only |
| reconciliation_rules.conf | one key per trap, a numbered rule list | step 7 | delete the file's trap keys; each rule lives in its governing file |
| shipped-corpus-only grading | whole-doc test reran resolve on the one shipped case | all | hidden reseeded corpora (many principals, tenants, windows, ledger rows) |

## 7. Chosen levers: L1 + L2 + L3 + L7 (interacting)
Not a repeat: cohort is L1+L2+L3+(L4 or L5), district-heat L1+L2+L4+L7, emberforge L3+L6+L7, vendor L2+L3+L5+L6, schema L1+L2+L5+L6; none is contained in this set. The sentinel-style peer (G3 P2) is used as a pattern only.

- **L3 stateful stream (override ledger with a tenant allowance).** `override_deltas.json` becomes an ordered ledger (`seq`) where several overrides can apply to one principal. Each tenant has an override allowance per effective version (bare property in `quota_limits.cfg`, the tenant-quota file). Every override that passes selection consumes one unit in `seq` order across all of the tenant's principals; after the allowance is spent, later overrides do not apply. Reflex reading: apply the principal's own matching overrides on their own (or only the single latest one), ignoring what earlier rows for other principals consumed. Hidden ledgers put other principals' rows earlier so the allowance runs out before, between, or after the target's rows.
- **L7 rounding per item (risk terms).** `risk_weight_rounding.txt` (the stage file) states that the base risk weight and each applied override's `risk_delta` are scaled by the tenant multiplier and rounded half_up one by one, then summed. The worked example is removed (W6). Reflex: sum the deltas first, then scale and round once. Interacts with L3, since the allowance decides how many terms there are. Hidden multipliers and deltas make the two readings differ, which in turn shifts the convergence chain.
- **L1 green control.** A per-tenant control block at the end of the ledger (`rows`, `max_records_delta_sum`, `timeout_delta_ms_sum` over every stored row, whatever its status, window, version or allowance), described honestly in the ledger header as a parse/count control (W7). The repaired `validate` path reports it green for any complete parse. The graded values depend on the selection, allowance and rounding rules above that layer.
- **L2 make-it-match repair (per-row timeout unit).** The ledger's conventions block (top of file, far from the control) defines `timeout_delta` as milliseconds, with a branch: rows with `rev` 1 carry seconds. The control's ms sum only matches when rev-1 rows are converted. The shipped loader reads raw values, so the control fails. The correct repair converts by `rev`. A plausible coerce or rescale repair, such as scaling small values or scaling by window age, also matches the shipped control, because every shipped rev-1 row is small and every rev-2 row is at least 100 ms. That repair breaks the stated rule on hidden ledgers, which include rev-2 rows under 100 ms and rev-1 rows at awkward values.
- **Retire the leaks.** Remove instruction:5 trap sentences (point to files only) and the reconciliation_rules.conf trap keys. Remove "decoy" labels and the clamp warning. Each rule stays stated once, in plain form, in the file that governs its data (never hidden, IN-15).
- **Grading plan.** Whole-document tests rerun the delivered `resolve` on several hidden reseeded corpora (within the stated bounds, AL-27/TS-19) and compare one observable per test. Targets: whole-doc at least 50%, isolated checks at most 30%, shipped-only at most 5%. Other gates: at least 2 mutation tests, negatives only for cheating acts, judge batched with J2 conduct criteria per lever, and the K8 pip line plus `_grant_read`.
