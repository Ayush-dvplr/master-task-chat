# DIAGNOSIS: sentinel-policy-recompute, test half (b7e15f9)

Input: probe 4, claude-opus-5 run_1, tests-only 52/52 = 100, rubric 40 (old judge), final 70.0.

## P1.1 staged tests vs BUNDLE

`diff -rq` run staged `tests/` vs BUNDLE `tests/`: only `tests/judge.toml` differs (d0f1870 judge rebuild landed after the run); `environment/` and `instruction.md` identical.

## P1.2 positive tests: what the agent read and why it was easy

Agent pattern (trajectory, 57 steps): steps 3-30 read every data file (rule files at 10-11, version map 12-13, windows 14, override_deltas conventions + rows 15-17, catalog 18-19, parquet 20-21, xlsx 22, the rest 23-26), step 27 computed the cutover unit sums by hand, step 33 wrote the whole cli.py in one pass, steps 48-52 self-tested with corpora it edited (instant moved, admit/pool edited, r-north = 1). It transliterated each sentence into one line of code (`OUT/agent_program/cli.py`).

| test (weight) | rule the agent needed, where read | step right | what made it easy |
|---|---|---|---|
| hidden_region_allowance_hard (5) | quota_limits.cfg:7 + tenant_catalog.xml region, override_precedence.conf:6 | 10, 18-19, 33 | rule next to its values; one sentence; draw_order sentence spells the algorithm |
| hidden_unit_cutover_hard (5) | units_reference.txt:6-7 + policy_version_map effective_from | 12-13, 27 | stated cutover value; shipped control mismatch is a loud pointer (agent checked controls by hand at step 27) |
| hidden_window_admit_hard (5) | override_precedence.conf:5-6, effective_windows.xml `admit` | 14, 33 | rule sits in the conf line next to draw_order; attribute visible on every window |
| hidden_timeout_pool_hard (5) | override_precedence.conf:7 | 14, 33 | the sentence is the algorithm (sum<=pool, floor share, drop <100, reshare); agent copied it line for line |
| hidden_policy_resolved_document_matches (5) | all of the above + clamp_rules.txt, tenant_multiplier_table.xlsx cap | 10, 22, 33 | each step is one stated line; nothing in hidden-a..d needs a rule the shipped data does not show |
| hidden_threshold_curve_document_matches (5) | convergence_spec.txt, risk_weight_rounding.txt, reconciliation_rules.conf | 10, 20-22 | stated limit (64 iterations, epsilon 0) and per-term rounding sentence hand over the method |
| hidden_dependency_trace_document_matches (5) | output_field_spec.txt:16, override_deltas controls convention [8] | 6, 15-17 | field list named in the spec; controls rule one sentence |
| cli_init_and_set_rebuild_config... (3) | README + schema + output_field_spec profiles | 8-9 | reference values, independent of resolve |
| mutation_risk_delta_moves_only_contribution (3) | risk_weight_rounding.txt | 10 | same code path as hidden-c; no new rule |
| mutation_allowance_cut_drops_later_override (3) | quota_limits.cfg | 10, 52 | the agent self-tested exactly this edit (r-north = 1, step 52) |
| mutation_pool_cut_reshares_timeout (3) | override_precedence.conf:7 | 50-51 | agent self-tested pool edits |
| validate_accepts_supplied_config... (3) | validation_rules.json, config_schema.json | 11 | stated key list |
| hidden_resolve_rerun_is_canonical... (1) | determinism_rules.txt | 11 | byte identity by construction |
| shipped_artifacts_carry_policy_runs_and_archive (1) | output_field_spec.txt, report_field_spec.txt | 6, 53-56 | stated artifact list |

Summary: every rule a test reads is a stated sentence whose shipped data shows the feature (allowance values, admit attributes, pool attributes, cutover line). A reader who transliterates every sentence and self-tests with edited copies earns 100. The levers are not quiet: each sits on a value the agent sees on shipped data, so its self-tests cover them.

## P1.3 arithmetic

- P = 52 today. To land 70-90 the careful solver must miss 5-16 points.
- Rules that carry no hidden-only behaviour today: every one. N1-N4 fire (or are visibly exercised) on shipped data, the carried levers (half-open window, version gate, B9 vs B7, client version, seconds base, tier index, convergence) all fire on shipped data. Nothing is met only on hidden data.
- Plan: 5 new quiet rules, each owned by one new hidden test (2 seeded corpora, whole policy/curve/trace documents exact) of weight 4, plus one combo test (rare pairs of two quiet rules on one record, own RNG) of weight 3. New P = 52 + 20 + 3 = 75.
  - one rule wrong alone: 4 + 3 = 7 / 75 = 9.3% (inside 5-12%).
  - all but one rule right: 68 / 75 = 90.7 (<= 95).
  - first-write (skips all five, everything else right): 52 / 75 = 69.3.
  - careful strong solver holding 2-3 of 5: 75-85.
- Old corpora (hidden-a..d, n1-*, n2-*, n3-*, pool-*, mutation-*) are rebuilt so that none of the new rules fires in them (per-row ownership, G1a): their tests keep their meaning and a quiet-rule miss is charged only to its owner and the combo.

## Planned new rules (shortlist; each one plain sentence + toy example, in the file that owns the family)

| id | where written | sentence (draft) | reflex reading targeted | wrong document it yields |
|---|---|---|---|---|
| Q1 timeout floor, running | units_reference.txt (new lines after line 7) + value line `timeout floor: <n>` with stated range | timeout_ms starts at the base in ms and takes the added delta of each applied row in ascending seq; whenever it falls below the timeout floor it is set to the floor before the next row | `base + sum(deltas)` (probe-4 cli.py:406) | timeout_ms too low or too high by the clipped amount in policy_resolved.json |
| Q2 reissued override id | override_deltas.json conventions (new item) | when several stored rows carry one override_id, only the row with the highest seq is considered for selection and draw; the earlier rows draw nothing (controls still count every stored row) | every row stands alone (cli.py:306 status filter only) | extra applied row: wrong applied_overrides, allowance/admit used, wrong max_records/timeout/contribution |
| Q3 principal alias for part of a window | override_deltas.json new top key `param_key_aliases` (entries alias, principal, start, end, half-open) + convention item | a row whose param_key is an alias counts as an override of the alias's principal while effective_instant lies in the alias span, and of no principal outside it; it draws allowance and admit as any row | `param_key == resolved principal` | missing applied row in trace and its deltas in policy/curve |
| Q4 retry cap | clamp_rules.txt (new lines) + value with stated range | retry_limit = min(retry_cap, retry_limit_base + the retry_limit_delta of every applied row) | no cap (cli.py:405) | retry_limit above the cap in policy_resolved.json |
| Q5 carried clause of a superseded row | override_deltas.json conventions + optional `carry` field on superseded rows | a superseded row with a `carry` field still adds that one named delta to its principal when its window contains effective_instant and row and window carry the effective version; it draws no allowance or admit and is not an applied row | skip superseded rows | max_records / contribution / threshold off by the carried delta; applied_overrides unchanged |

Native mapping to the master's candidate list: Q5 = "superseded file whose one carried-forward clause still binds"; Q3 = "alias that maps two names to one principal for part of a window"; Q2 = "rev withdrawn and later reinstated" (reissue under the same id); Q1 = "dependency chain whose order changes the result"; Q4 = clamp family (max_records already has a stated clamp; retry has none).

Shipped data fires none: Q1 floor set below every running value of the shipped and old hidden corpora; Q2 shipped override ids unique; Q3 one shipped alias entry whose span ends before effective_instant and no row carries that alias as param_key; Q4 cap above every shipped and old-hidden retry; Q5 shipped `carry` appears only on a superseded row whose window does not contain the instant. BRANCH_FIRE target: shipped 0, each owned hidden corpus >= 2, combo corpora >= 2 per rule.

None crashes when ignored: new keys/fields are optional additions to JSON objects already read; every miss is a plausible number.

Judge: kept exactly (d0f1870). A w3 probe per new rule only if solve.sh self-check can print `check <id> ok` with a witness; on shipped data the rules do not fire, so the self-check can only show the code path on a toy corpus. Decision in Phase 2 after reading solve.sh.

## Lessons for the master
- every lever placed on a value the shipped data shows is self-tested away by a reader who edits copies | no change: covered by LEVER_RULES v3.2 T1
