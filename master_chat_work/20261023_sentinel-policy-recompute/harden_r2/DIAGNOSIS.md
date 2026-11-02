# DIAGNOSIS: sentinel-policy-recompute, harden round 2 (0074a64)

Written 24 Oct 2026 21:20 IST. Probe 1 (harness attempt 2, bundle tree b0332e7aa626 = fix 7e07424 plus the master's 24 Oct instruction.md edit): tests 33/33 = 100, judge 16/37 = 43.24, overall 71.62. Run folder `Terminal_2.0_Harbor_Harness/jobs/sentinel-policy-recompute/trajectory/claude-opus-5/Run 1/`. QC kit HEAD 976c166611e555e2ba20eb8d81bed279cee1ea30 (matches expected).

## 1. Phase A: is the score genuine? GENUINE

- `result.json`: `exception_info: null`, trial `sentinel-policy-recompute__5Y67UUL`, openhands-sdk 1.55.1, claude-opus-5, agent run 14:48:41Z to 15:01:48Z (13 min, 59 steps, out tokens 67,005, $4.27), verifier 15:02:00 to 15:03:46, reward 0.7162.
- `diff -rq` of the staged copy `.kiro-staged-tasks/sentinel-policy-recompute` against BUNDLE: only the stage marker `.kiro-staged-from` and the harness-injected `"host.docker.internal"` in task.toml `allowed_hosts` (lines 25 and 32). Everything else identical.
- No Permission denied, Errno 13, Traceback, timeout or missing-file lines in trial.log, test-stdout or verifier output. The only grep hits are the harbor command line in job-config/wrapper.log (`--agent-setup-timeout-multiplier`). trial.log `docker inspect returned 1` is the benign image OS-validation skip.
- test-stdout: the three negatives end in `AssertionError: honest baseline ...` (not fired), then `reward: 0.7162`. Artifact manifest: all 7 `/app/out` files status ok.
- The judge read the trajectory: `judge_response.txt` cites agent acts per criterion, e.g. R13 "In the copied c3 corpus the agent reduced the t-atlas allowance to one ... K042 rejected because the allowance was exhausted"; R11 "produced through a newly added `profile` subcommand, not through repaired CLI init and set commands".

Verdict: GENUINE. The 100 on tests is a real solve.

## 2. Root cause

| cause | verdict | evidence |
|---|---|---|
| 1 run error / wrong copy | NO | Section 1: staged copy equals BUNDLE, no errors, every check ran. |
| 2 harness / rescoring change | NO | reward-details weights are 1/66 per test point and 1/74 per judge point, i.e. reward.toml 0.5/33 + 0.5/37 as built in 7e07424; judge gpt-5.6-sol as before. |
| 3 our QC/fix rounds made it easier | PARTLY (grading only, not for Opus) | See 2a. No change put a rule or answer in front of the agent. The 7e07424 split raised the share a partial program can earn (reflex v0 0.161 to 0.364), but Opus scored 100 on every lever, so this did not cost us this probe. |
| 4 levers weak by design | **YES, PRIMARY** | See 2b. Each of L3, L2, L7 and L1 is a literal sentence or formula in the file that holds its data. The agent read every rule file in one `cat` loop at step 9, wrote the resolver in one go at step 33 by transliterating each sentence, and never changed graded logic afterwards. |

**PRIMARY CAUSE: 4.** Contributing: 3 (partly). The test channel has been 100% for Opus since v0 (harden_r1 `baselines.json`: tests_only 1.0). The r1 levers did not change that.

### 2a. Cause 3: files changed since the last hard baseline

There is no hard test baseline. v0 (20 Oct) already scored tests 1.0. Changes since then, by whether the agent can see them:

| change | round | agent-visible? | effect |
|---|---|---|---|
| override_deltas.json conventions (rev-1 seconds, allowance sentence, controls sentence), quota_limits.cfg allowance block, risk_weight_rounding.txt per-term formula, override_precedence.conf `match_version`, gen_data.py data | P9 r1 / P12 r1-r2 | yes | These are the levers. Each is stated as a direct rule (2b). |
| instruction.md: trap list replaced by pointer + G5 sentence (23 Oct 17:18); master 24 Oct edit removed "decoys that disagree ... on purpose" | P12 r1, master | yes | Fewer hints, not more. The edit removed a warning, which can only make the task harder. Neither edit states a rule or a value. |
| 7e07424: `decoy_alias_table.jsonc` renamed `principal_alias_table.jsonc` (content and in-file notice kept) | P12 v3 r3 | yes (name) | Removes the word "decoy" from a file name. Harder if anything. Agent read it at step 9 and did not use it as a lever source. |
| 7e07424: TS-26 `cli_init_and_set_rebuild_config_from_authoritative_values` w3 rebuilt from reference values; M1 split into 5 w1 `shipped_*` checks; hidden-c row OV-K042-c0; solve.py `inspect_shipped_tool`; judge R3/R7/R8/R10 reworded | P12 v3 r3 | no (tests, solution, judge) | Grading only. Shipped-only checks are now 5/33 = 15.2% (target <= 5%), and the w3 init/set check is passable by any working build. This is why the reflex program rose from 0.161 to 0.364. It made the task more forgiving for a partial program. It does not explain Opus's 100. |

Answer to the master: neither 7e07424 nor the 24 Oct instruction edit put a rule or answer in front of the agent. The agent took every lever from the data files' own rule text (steps 9 and 14).

### 2b. Cause 4 per lever: what let Opus get each right (trajectory steps)

| lever | where the rule is written | what Opus did, with steps | what gave it away |
|---|---|---|---|
| L3 tenant override allowance (H6) | override_deltas.json `conventions` (allowance sentence: "in ascending seq order across all rows of the tenant whichever principal they name ... after its tenant's allowance is used up is not applied"); quota_limits.cfg `[override_allowance] t-atlas = 5` keyed by the same `tenant` field every row carries | Step 9 read quota_limits.cfg. Step 14 printed the conventions in full. Step 15 listed t-atlas rows by seq. Step 33 cli.py:309-320 transliterated the sentence: `row["tenant"] == tenant`, sorted by seq, `used >= allowance` reject. Steps 47-50 self-test c3 cut the allowance to 1 and saw OV-K042-auth rejected (judge R13 = 1). | The sentence names the separating case ("whichever principal they name"). The counter key is the per-line `tenant` field the agent already holds, so the habit key and the rule key are the same. LEVER_RULES 1b: a wider key is needed. |
| L2 make-it-match (rev 1 rows in seconds) | override_deltas.json conventions line 6: "timeout_ms_delta is a delta in milliseconds; a rev 1 row stores it in whole seconds."; units_reference.txt; reconciliation_rules.conf `timeout_unit_factor = 1000` | Step 14 read the sentence. Step 27 reconciled `controls` with `t*1000 if rev==1`, so the control confirmed the stated reading. Step 33 cli.py:269-272 `delta * unit_factor if rev == 1`. Final message: "rev-1 deltas are seconds (this also makes all 13 ledger_controls reconcile as ok)". | The rule is one explicit sentence keyed by a per-line field (`rev`). The control only reconciles under the right reading, so there was never a failing control to "repair". L2 needs the honest reading to fail a control; here it passes. |
| L7 per-term rounding | risk_weight_rounding.txt lines 2-3: `contribution = sum of round_half_up(term * mult_bps / 1000) over the terms` | Step 9 read it. Step 33 cli.py:349-352 copies the formula and even asserts the file still contains `"sum of round_half_up(term"`. Final message "half-up per term -> 61 + 2 = 63". | A formula at the point of use is code (LEVER_RULES 1b, H2 note). |
| L1 green control, wrong answer | override_deltas.json conventions controls sentence ("a parse and count control for this file only"); output_field_spec.txt line 16 `ledger_controls` | Step 27 used the control only as a parse check. cli.py:274-285 outputs ok/mismatch per tenant. The graded values never relied on it. | The control is truthfully described as parse-only, and Opus does not treat a green control as proof. On its own L1 is an amplifier at most (G10 measured 15.2%). |

Carried-over traps (half-open window WIN-PRE, version gate v099 rows/windows, B9 vs B7, client version v205, seconds base timeout, tier = role_level, convergence) were all read at step 9/26 and transliterated at step 33. Step 26 verified the half-open rule against all 200 `effective_instant_examples`.

### 2c. Scattered rule files: helped or hurt?

They helped Opus and hurt only QC. The agent read about 31 rule files in a single shell loop at step 9 (14:49:09, under 20 s). Each rule sits next to its data and reads as one formula, so the spread cost it nothing and made the mapping from rule to code direct. Opus does not lose rules because they are scattered. What made it slip in other tasks is a key or scope defined in a different file from the rule that uses it (H3/H6), and none of our levers has that shape. Spreading does count against W10 (one contract file), as already logged. The new rules below each go into the single file that owns their topic.

## 3. Lever table (reward-details.json + trajectory)

| check / criterion | points | earned | levers | status |
|---|---|---|---|---|
| hidden_policy_resolved_document_matches | 5 | 5 | L3 L2 L7 L1 + carried | LEAKED |
| hidden_threshold_curve_document_matches | 5 | 5 | L3 L7 (via contribution) | LEAKED |
| hidden_dependency_trace_document_matches | 5 | 5 | L3 (applied/rejected) | LEAKED |
| mutation_allowance_cut_drops_later_override | 3 | 3 | L3 | LEAKED |
| mutation_risk_delta_moves_only_contribution | 3 | 3 | L7 | LEAKED |
| cli_init_and_set_rebuild_config_from_authoritative_values | 3 | 3 | L2 (timeout in config) | LEAKED |
| validate_accepts_supplied_config_and_rejects_missing_key | 3 | 3 | none | n/a |
| hidden_resolve_rerun_is_canonical_and_byte_identical | 1 | 1 | none | n/a |
| shipped_config_and_profiles_carry_policy_values | 1 | 1 | shipped only | n/a |
| shipped_report_records_tool_runs_and_digest | 1 | 1 | none | n/a |
| shipped_validation_report_grades_policy_and_branches | 1 | 1 | shipped only | n/a |
| shipped_summary_lists_artifacts_and_inputs | 1 | 1 | none | n/a |
| shipped_tool_archive_is_pinned_and_repaired | 1 | 1 | none | n/a |
| negatives: hardcoded -5, transcript disagrees -3, url/secret -3 | -11 | 0 | cheating | not fired |
| R1 resolve / R2 init+set build / R5 summary paths | 5/5/3 | 13 | none | earned |
| R6 run shipped tool before first edit | 3 | 0 | conduct | HELD (inspected and imported, never ran the unrepaired sentinel-ctl) |
| R7 reproduce shipped wrong value | 3 | 0 | conduct | HELD |
| R10 code quality | 3 | 0 | J4 | HELD (resolve_policy monolithic, raw exceptions) |
| R11 profiles through repaired init/set | 3 | 0 | conduct | HELD on wording (agent added a `profile` subcommand; see section 6) |
| R12 own rev-1/rev-2 timeout ledger | 3 | 0 | L2 conduct | HELD |
| R13 own allowance ledger | 3 | 3 | L3 conduct | LEAKED (step 49-50 self-test c3) |
| R14 own per-term vs summed rounding | 3 | 0 | L7 conduct | HELD |
| R15 own multi-override ledger | 3 | 0 | L3/L7 conduct | HELD |
| R3/R4/R8/R9 negatives | -16 | 0 | cheating | not fired |

Test channel: every lever LEAKED. Judge channel: 6 conduct criteria held, the only reason the overall is below 72.

## 4. Trajectory autopsy

| phase | steps | time (UTC) | what |
|---|---|---|---|
| read rules | 3-9 | 14:48:51-14:49:09 (18 s) | ls, versions, unzip; step 6 field specs; step 8 README/schema/`cat -n cli.py` (saw the shipped `//1000`, seconds base + raw delta, single selected row, summed rounding); step 9 one loop over ~31 rule files |
| explore data | 10-28 | 14:49:29-14:51:31 (2 min) | version map, windows, step 14 conventions printed in full, step 15 t-atlas rows by seq, parquets/xlsx/corpus/catalog/pdf, step 26 half-open check on 200 examples, step 27 controls reconciled with rev-1 x1000, step 28 multiplier row |
| think | 28-29 | 3.5 min gap | no reasoning saved |
| write program | 31-33 | 14:58:04 | cli.py in one create (24,164 B; an earlier 24,491 B draft removed). Step 34 first run printed the final correct values. |
| graded-logic edits | none | | steps 35/36/45 edit README only |
| build | 37-46 | to 14:59:50 | /app/sentinel-ctl launcher, /app/build.py (init + 9 set + validate + profile/export + package), double-build sha compare |
| self-tests | 47-52 | 14:59:50-15:00:26 | three mutated corpora in /tmp: c1 instant moved, c2 active bundle B7 to B3, c3 t-atlas allowance 5 to 1. None for rev-1/rev-2 units, per-term rounding or multi-override. |
| finish | 53-59 | to 15:01:44 | rebuild, zip check, AGENTS.md, final message listing 10 defects with the correct reading of each |

The agent's method: read every rule file once, transliterate each rule sentence into code using the per-line field the sentence names (`row["tenant"]`, `row["rev"]`, the formula string), then verify on its own mutated copies only the levers it thought were stateful. Any rule written as an explicit sentence about a per-line field is free for this method. It would miss a rule whose key or scope comes from a different file than the field it reads (cli.py:254 `quota[...][tenant]`, :310 `row["tenant"] == tenant`, :272 `row["rev"] == 1`).

## 5. Agent program saved

`OUT/agent_program/`: `tool/` (cli.py 24,164 B equal to the step-33 text, README.md, schema.json, unzipped from the delivered tool.zip), `build/build.py` (step 38 plus edits 39 and 51 replayed, 2,501 B) and `build/sentinel-ctl`, `out/` (the 7 delivered artifacts). The reflex gate in Phase 3 runs this program, adapted only for file-name or key-format changes, against the new tests.

## 6. What trips Opus vs what does not

| does not trip Opus (this probe) | trips or held (this and peer probes) |
|---|---|
| A rule sentence that names its per-line key (`rev 1 row`, `rows of the tenant`) | A counter keyed wider than the field the agent filters on, with hidden-only separating cases (H6; caldermoor C, metered LV-MU-5 plan) |
| A formula at the point of use (`sum of round_half_up(term ...)`) | A scope or unit set by a defined term or cut in another file that differs from a convenient per-line field (H3; metered H3, pa M1) |
| A control that reconciles only under the right reading (it confirms the rule) | A control that reconciles under both the right and the habit reading on shipped data (L1 amplifier on a real lever) |
| Separating case named in the sentence ("whichever principal they name") | Conduct criteria asking for its own input per lever (R12, R14, R15 held: it self-tests only levers it sees as stateful) |
| Decoys, superseded files, half-open windows, version gates (all read at step 9/26) | Running the shipped tool before editing (R6) and reproducing a shipped wrong value (R7): it reads code instead |
| Rules spread over many files (read in one loop) | Code-quality judgement on one long function (R10) |

## 7. LEAK_LIBRARY rows

| lever | how it was written | leaked at | fix rule |
|---|---|---|---|
| SPR-L3 tenant override allowance | override_deltas.json conventions sentence naming the scope "across all rows of the tenant whichever principal they name"; quota_limits.cfg keyed by the per-line `tenant` field | step 14 read, step 33 cli.py:309-320, self-test step 49-50 | H6: key the counter wider than the per-line field (region from tenant_catalog.xml); never name the separating case in the sentence; separating rows hidden-only |
| SPR-L2 rev-1 seconds make-it-match | one explicit sentence keyed by per-line `rev` (conventions line 6); the control reconciles only under the right reading, so it confirms the rule | step 14 read, step 27 control reconcile, step 33 cli.py:269-272 | H3: unit set by a defined cut in units_reference.txt, not by the per-line field; the shipped control must reconcile under both readings |
| SPR-L7 per-term rounding | formula at the point of use in risk_weight_rounding.txt lines 2-3 | step 9 read, step 33 cli.py:349-352 (asserts the formula text) | H2 note: point-of-use rounding is a library call; demote to graded noise |
| SPR-L1 green control | control truthfully described as "parse and count control for this file only" | step 27 used as parse check only | amplifier only; pair it with a lever whose habit reading also reconciles on shipped data |

## 8. Phase 2 lever plan (proposal, not implemented)

Target: Opus tests about 75 or lower with the judge about 43, so overall below 70. Current one-lever cost (P=33): L3 54.5%, L2 30.3%, L7 24.2%, L1 15.2% (G10 failed on L7 and L1).

Grading change for all levers: per-lever hidden `_hard` families (w5 each, owned rows: each family's corpus separates only its own lever), plus the existing whole-document tests as the COUPLING family on a corpus where all three separate. Shipped-only checks folded back to at most 5% (merge the 5 w1 `shipped_*` into 1 w1 plus the existing w3 checks), so a partial program cannot earn 36%. Mutation tests >= 2 kept (allowance cut, risk delta).

| lever | decision | new rule text and file (bare, no why, no malformed list) | hidden cases (owned rows) | predicted alone / one-fact-wrong | why the probe-1 program misses it |
|---|---|---|---|---|---|
| N1 region override allowance (H6, replaces L3) | REPLACE L3 | quota_limits.cfg (owner of allowances), replacing the comment and keys: `# an override_allowance belongs to a region of tenant_catalog.xml and is shared by every tenant in that region` / `# the override rows that pass selection draw on their region's allowance one unit each in ascending seq order, and a row that passes selection after its region's allowance is used up is not applied` / `[override_allowance] r-north = 5 ...` (one key per region). The allowance sentence leaves override_deltas.json conventions (one file owns the topic). | hidden_region_allowance_hard: another tenant placed in r-north (tenant_catalog.xml + tenant_multiplier_table.xlsx region kept equal) with earlier-seq rows that pass selection and use up the allowance before OV-K042-auth; a second corpus where the other tenant's rows fail selection (so they draw nothing). Shipped: r-north holds only t-atlas, so no separation. | family 15 + coupling 15 + mutation 3 = about 33/80, >= 40%; one-fact-wrong = per-tenant counter with region lookup | cli.py:254/310: it keeps `row["tenant"] == tenant`. The minimal repair after the region key lookup fails is to map tenant to region for the lookup and keep the per-tenant filter. |
| N2 timeout unit by version cutover (H3 + L1 amplifier, replaces L2) | REWRITE L2 | units_reference.txt (owner of units): `override timeout_ms_delta stored: seconds for a row whose version has effective_from before <cutover> in policy_version_map, milliseconds otherwise`. Conventions line 6 becomes `timeout_ms_delta is a timeout delta.` (the rev sentence removed); `rev` stays a 1-or-2 field. gen_data.py regenerates `rev` so every shipped row has rev 1 exactly when its version is before the cutover (today 20+ rev-1 rows are after any cutover, e.g. OV-K042-prev v100), then common rule 6. | hidden_unit_cutover_hard: rev-2 rows before the cutover and rev-1 rows after it, on applied K042 rows and on other-tenant rows (moves `ledger_controls`). Shipped: rev and cutover agree, so the control is green under both readings (L1 amplifier). | family 15 + coupling 15 + init/set 3 = about 33/80, >= 35%; one-fact-wrong = unit by `rev` | cli.py:272 keys the unit on `row["rev"]`, the per-line field, and the shipped control (step 27) would confirm that reading. |
| N3 window admit count (H6 second key, replaces L7 as a counted lever) | REPLACE L7 (L7 kept as graded noise) | effective_windows.xml gets a bare `admit="N"` attribute per window; override_precedence.conf (owner of selection and application): `admit = a window admits at most its admit value of applied rows, drawn one each by the rows that pass selection in ascending seq order across all tenants; a row that passes selection after its window's admits are used up is not applied` and `draw_order = a row that passes selection draws its window admit and its region allowance together, and a row refused by either draws neither`. | hidden_window_admit_hard: WIN-AUTH admit 1 with an earlier-seq row of another tenant (other region) in WIN-AUTH; second corpus where the earlier row fails selection. Shipped: every admit >= the rows that pass selection in that window (WIN-AUTH 3), so no separation. | family 15 + coupling 15 = about 30/80, >= 35%; one-fact-wrong = per-tenant (or per-principal) admit count | cli.py iterates only `tenant_rows`, so it can never see another tenant's draw on the same window. |
| L1 green control | KEEP as amplifier (not counted) | none new | covered by N2 hidden ledgers | 0 alone (amplifier) | n/a |
| L7 per-term rounding | DEMOTE to noise | unchanged text | stays in coupling corpus | not counted | n/a |

COUPLING amplifier (stated in DESIGN.md and LEVERS.md): N1, N2 and N3 all decide which rows apply and with what timeout. They feed max_records, retry, timeout and risk contribution, then the threshold iteration, `threshold_curve.json`, `dependency_trace.json` (applied/rejected rows), config.json and both profiles, and N2 also feeds `ledger_controls`. One slip moves the policy, curve and trace families plus config/profiles at once. N1 and N3 use different keys (region vs window across all tenants), and N2 is a unit, so a slip on one never forces a slip on another.

Predicted Opus outcome. The three rules are still explicit sentences, because IN-15 requires that, so a trip is not certain. N1 and N3 are the bank's strongest shape: hidden-only counters wider than the field the agent filters on. N2 hands a per-line field to an agent that keys on per-line fields, and a shipped control confirms both readings. If one lever trips: tests about 55 to 62, overall about 50 to 53. If none trips: tests 100, overall about 72. Reflex gate: the probe-1 program, adapted only to look up the region key, keeps per-tenant filtering, `rev` units and no admit, so it fails all three families. Predicted reflex <= 0.15 once shipped-only is cut to 5%.

Judge plan (J1-J9, batched, P about 37):
- R11 rewrite: the contract (instruction.md "Produce the two environment profiles ... through the same tool"; README lists only init/set/resolve/validate) does not require init/set for profiles. New observable wording: "The agent produces /app/out/profile_dev.json and /app/out/profile_prod.json by running its repaired sentinel-ctl, not by writing them from a separate script or by hand." This is fairer. Opus probably earns it (+3 judge), which is why the test channel must carry the drop.
- R12 becomes the N2 conduct criterion: "builds its own ledger where a row's `rev` disagrees with its version's side of the unit cutover and checks the timeout_ms its resolve prints".
- R13 becomes the N1 conduct criterion: "builds its own corpus where another tenant of the same region uses up the allowance first".
- R14 becomes the N3 conduct criterion: "builds its own corpus where another tenant's earlier row uses up a window's admits".
- R15 multi-override kept. R6, R7 and R10 (J4 code quality, one judgement) kept.
- solve.sh prints `check <id> ok` for each new conduct criterion.

Risks for Ayush to weigh:
- N2 regenerates the `rev` column (data edit, not a corpus restructure). The shipped answer is unchanged, because OV-K042-auth is rev 2/v100, but TRUTH and the _SHIPPED_DATA digests must be regenerated.
- N1 changes the quota_limits.cfg key format, so the old reflex program crashes on the lookup. The reflex gate uses the minimal adaptation (region lookup only) to stay honest.
- tenant_multiplier_table.xlsx also has a `region` column. Every corpus keeps it equal to tenant_catalog.xml, and the rule names tenant_catalog.xml as the source, so the rule has one reading.

STOP: Phase 1 done. Waiting for Ayush "go" before Phase 2.
