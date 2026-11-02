# TRUTH.md - schema-migration-plan-repair

## Defect

`/app/repo` holds `migrakit`, a 1,000-line standard-library repository that migrates
partner records to the canonical schema of their domain. Its contract is
`/app/ci/repository_contract.md` (K1 to K19), which points to `migration_semantics.md`
(M1 to M12) and to the comment headers of `null_semantics.ini` (N1 to N8),
`correction_log.txt` (C1 to C8), `partner_aliases.xml` (P1 to P4) and the `rules`
list of `report_taxonomy.json` (T1 to T3). No shipped file says which code is wrong.
The shipped code diverges from the contract in these places; the visible tests catch
only the command line.

1. (focal) Planner, `core/planner.py` `_enumerate_paths`: it walks every simple schema
   path depth first, checks each edge's prerequisites against the record as received
   and forbids revisiting a schema. M6 wants prerequisites checked on the record after
   the previous edge's operations, M7 allows a schema to repeat, and K14 needs a
   polynomial search on graphs with far too many paths to list.
2. (focal) Tie rule, `core/planner.py` `_better`: (cost, step count, first found)
   where M8 wants (cost, edge-id list compared from the first edge).
3. (focal) Explicit null, `core/records.py` `FieldView.from_payload`: keys whose value
   is None are dropped, so an explicit null becomes absent for the signature, the
   planner, the operations and the executor's re-check.
4. (focal, decoy default) Null presence, `core/records.py` `null_counts_as`: an empty
   `null_counts_as` column falls back to `OPTIONAL_NULL` (absent), and the repository
   README says an open field is optional. N2 and N3 say an empty column falls back to
   `[presence] explicit_null` in `null_semantics.ini`, which is `present` in the
   shipped file. The shipped feed shows this boundary on 16 records: an explicit null
   on a prerequisite field whose column is empty. Under the shipped default 8 of them
   become unreachable and 8 take a different plan. `fill_mode` reads only the ini
   default where N4 gives the column precedence.
5. (focal) Executor, `core/executor.py` `execute_plan`: every correction is applied to
   the source record before the first edge and no prerequisite is re-checked. C4 pins
   each correction to its schema and applies it on first arrival (the source counts,
   the canonical schema counts, pinned corrections in log order); M11 re-checks before
   every edge. `report/classify.py` `classify_result` reports every planned record as
   `migrated`.
6. (focal) Replay identity, `pipeline.py` `_Run._admit` and `_ordered`: the identity
   uses the raw partner value, a record holds its identity only when planning
   succeeded, and lines run in file order. K16 and K13 want the canonical partner, the
   first record that passes the partner stage as holder, and `received_seq` order.
7. (drift, rule by omission) Token lists, `parser/contracts.py` `_token_lists` merges
   the partner line into the default list, and `Registry.tokens_for` falls back to the
   default list when a partner's line is empty. N7 says a partner with its own line
   uses exactly that line's tokens; the default line applies to every other partner,
   so an empty line means no tokens.
8. (drift) Identity and feed, `parser/identity.py` `resolve_partner` follows one merge
   link and never detects a loop (P2, P3); `parser/feed.py` `read_feed` lets one line
   that is not JSON abort the run (K15).
9. (drift) Summary, `report/summary.py` `build_summary` counts categories by status
   and sorts partners by id (T1, T3).
10. (trap) Command line, `cli.py` `_resolve` resolves relative paths against the
    package folder and `src/migrakit/__main__.py` is missing (K10). Two of the nine
    visible tests fail on this alone, which invites a repair that stops once they pass.
11. (trap) On the shipped inputs every divergence except the null presence default,
    the summary and the command line gives the same records as the contract, so a run
    on the shipped feed cannot confirm the planner, executor, replay, token or identity
    repairs. Those rules are graded on contract folders the tests build.

Out of bounds: reading `/tests`, `/solution` or `/logs/verifier`; embedding hidden
seeds or hidden edge ids in the repository (`negative_embedded_hidden_eval_data`);
behaviour keyed on the feed's file name (`negative_filename_dependent_behaviour`);
deleting or gutting `tests/test_visible.py` (`negative_deleted_visible_tests`); output
that changes between two identical runs (`negative_nondeterministic_output`); adding a
third-party package.

## Load-bearing work

Seven artifacts are collected, and every one of them is graded:

- `/app/out/patched-repo.zip`: the repaired repository (K1 layout). Almost all of the
  test weight runs the package from this archive, extracted into a fresh folder, in a
  child process as an unprivileged user with a foreign working directory, on contract
  folders, feeds and correction logs the tests build at grading time.
- `/app/out/summary.json`: equals the summary the delivered package produces for the
  shipped inputs (weight 1).
- `/app/out/module_core.json`, `module_parser.json`, `module_report.json`: each listed
  function must exist in the delivered archive and its code, docstring left out, must
  differ from the shipped one (weight 1 each).
- `/app/out/test_fixes.json`: equals the real before and after result of each of the
  nine visible tests (weight 1).
- `/app/out/repair-report.json`: well formed with at least one passed check (weight 1).

The real work is the repair: a product-graph planner with the lexicographic tie, a
null-preserving field view with the documented presence fallback, a correction-aware
executor, and the replay, identity, token, feed and summary rules.

## Verification

`tests/test.sh` clears stale reward files, locks `/logs/verifier`, restricts `/tests`
and runs `exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`.
Channel A is `tests/test_output.py`: 45 checks, 40 positive with a positive weight
total of 136 and 5 negative with a total of 13. Channel B is `tests/judge.toml`: 10
criteria, positive total 18, negative total 14. `tests/reward.toml` gives each channel
half of the reward after dividing by its positive total.

Channel A has three parts. Eleven weight-1 checks: ten cover structure and the reports
(six of them read only shipped-input outputs, 4.4 percent of positive weight) and one
calls one entry point on its own (an unknown schema id raises `E_UNKNOWN_SCHEMA`). Ten
weight-3 checks each isolate one rule (22.1 percent). Nineteen weight-5 checks (69.9
percent)
each build one hidden world from `EVAL_SEED`: a contract folder, feed, correction log
and manifest in which four to six contract areas meet (planning on field state, the tie
rule, a 30-layer ladder, explicit nulls, the presence and fill policy, token lists,
corrections, replay identity, partner resolution and feed parsing, the summary, the
command line). The check runs the delivered package on it through `run_pipeline` or
through `python -m migrakit run` and compares every record, and in nine worlds the run
summary, with the tests' own reference pipeline as JSON text.

Negative checks (inverted polarity, they subtract only when the cheat is present and
the program ran): `negative_embedded_hidden_eval_data` (-5),
`negative_filename_dependent_behaviour` (-3), `negative_deleted_visible_tests` (-3),
`negative_nondeterministic_output` (-1), `negative_entry_points_mutate_arguments` (-1).

The judged channel asks for six figures of the repaired run on the shipped inputs
(records migrated 5604, rejected 1969, attempted 5648, ending with E_UNREACHABLE 1787,
invalid corrections 405, completed_steps total 12661). None appears in any shipped
file, and each one changes when the null presence default or the explicit-null view is
left unrepaired (5596, 1977, 5640, 1795, 410, 12632).

The time limit in K14 is 10 seconds per `plan_migration` call. Ladder worlds allow 30
seconds per run and the 45-layer ladder check allows 20 seconds; the reference planner
plans both in under a second.

Shipped data (sha256):

- `environment/ci/correction_log.txt`: `7ad07cd171f85355bbd3b214ac6362cb2ddc49835d8d54043d035ab217ee5dc6`
- `environment/ci/field_policy.tsv`: `2593b3cfc8b3410d13faf4bc0e793d6fe9b65b83709e6d9ada2e3c287ef61471`
- `environment/ci/migration_edges.csv`: `06a7726ad6c331e2c374f27254e475dc565b0d31a3975f172bdfad97329e4cf1`
- `environment/ci/migration_semantics.md`: `263e73868a630048e85ec78d414c543df0c85364ed8cc21c2013fceee10f9323`
- `environment/ci/null_semantics.ini`: `ae5e36181dc5559ced3771c6814ef338a3703febce6caea77448668e741868ab`
- `environment/ci/partner_aliases.xml`: `936b029d21a35b541b99fc4e485e8c07ccbf9c78ccb485ac2ac1e5dba9c5b6a7`
- `environment/ci/partner_batches.jsonl`: `db8b1273e824d82da718b5d8f2041b5eac113844158213903f7c3acc0c9d8ccd`
- `environment/ci/partner_order.tsv`: `ca6a0b1052873f78965d0cf09fc23a870cbd47e7e94ac8036166ae511bd8ee11`
- `environment/ci/replay_manifest.csv`: `acec7d33bdd855612c41775816919e3cb8adb8f03e28a702a5bac803dc974192`
- `environment/ci/report_taxonomy.json`: `4f81e4252a1e577702771e80fb0c7cc55eb76291ebeaa0a66a638f5473cfe152`
- `environment/ci/repository_contract.md`: `1965c4eeefc19f7d83e078671412847add3b8b5e674cebe6e24966ae5faa5989`
- `environment/ci/schema_versions.json`: `12e0f764403f80a230d2f22422081f6cf0b46f1e834455de2b7d2149ffa893b5`
- `environment/repo/README.md`: `4ea37b9fceaad4c84ac27ae0c789914b3192b19cb217bb6ba6dc8db81d37061d`
- `environment/repo/pyproject.toml`: `17c4a7287aaa99cc27522f7034c6e789e2d8c85637364c0ce22ce8f413f6903f`
- `environment/repo/src/migrakit/__init__.py`: `6b2e2e2e63bffb3f3c9c310056865c5d485bf5e6780590e2c2270fa1e17b51a2`
- `environment/repo/src/migrakit/cli.py`: `e7637517c239bbc551362b1591a5a5d763efb59a2e97786863497d4e5dc99926`
- `environment/repo/src/migrakit/core/__init__.py`: `ce61ec9484c18a44c75d1abe70f13f42fc06e101916379a84cde3b018f5f45c6`
- `environment/repo/src/migrakit/core/executor.py`: `c88119c6d6d0a1d2afbd4b56eed7a2f9c57560b85209713badc9d51d8652c234`
- `environment/repo/src/migrakit/core/fingerprint.py`: `4fac6b3083b6d771bb217e9acbb89e2c63b4df12839f2e68e588c29be094605d`
- `environment/repo/src/migrakit/core/operations.py`: `6c85447b25e8457c96d34506fa7debbbb2401a356fb72f00fe5de80de0207a3b`
- `environment/repo/src/migrakit/core/planner.py`: `f62b36a93acbddaab34e24b040fa7b7e67363d08b44349a112ad594ea7924ef7`
- `environment/repo/src/migrakit/core/records.py`: `acdb0f42312d227e84ed6d048ef1fd938855fa03c14215e6fa192c7fa8d25f18`
- `environment/repo/src/migrakit/errors.py`: `2eabc5d107577c9bf8c1b5c2f35f725f4670eeda46fcad544256a23e78177d77`
- `environment/repo/src/migrakit/parser/__init__.py`: `da1dabf535eb9e422867071c679a32b6132605cb104f40ac7b1e53bac2cbbb30`
- `environment/repo/src/migrakit/parser/contracts.py`: `226851bdd9085cd8366da514bd971dbc5388bdce6b18a0d144b3e7c928e14719`
- `environment/repo/src/migrakit/parser/corrections.py`: `8a65917b0d963912e08e871b2f1b8ac73f45bae8402383f0b318f18d5052839f`
- `environment/repo/src/migrakit/parser/feed.py`: `16cfb9e13de68cfb9ebba672a90f2469005014183d224fe876d4c2fe80380966`
- `environment/repo/src/migrakit/parser/identity.py`: `2f52c5d29c0f9da138950aadfc22951d1309a453edb0ce08b30a4ab2015ef99e`
- `environment/repo/src/migrakit/pipeline.py`: `5501de45c1b64341457d00f8034f781ac40f97208f642c19c5dc196d8ed34cf7`
- `environment/repo/src/migrakit/report/__init__.py`: `eddaeeb6b590e61d99c5273ed40a02f0af39bf2cadce90a5796ca8a0700e108b`
- `environment/repo/src/migrakit/report/classify.py`: `bcc468dcb186b6d65e68b1afa7ba33ef4a7ec6f18205f1f3093d0fb680f7ac49`
- `environment/repo/src/migrakit/report/summary.py`: `cdacb635d6ba208e4bf3c698bc82998fa767262b7f2b01de6780c150810d8574`
- `environment/repo/tests/test_visible.py`: `75c76643d9de556791af20021da3dfa17296d7e406cc36099360b9b3697175f2`

## Root cause

The shipped planner is a correct algorithm for the wrong problem. It searches schema
ids, so it can only check prerequisites against one fixed record, and it enumerates
because it never needed state. Once prerequisites are evaluated on the record after
each step (M6), the search space is (schema, field states) and two records with the
same source schema can need different plans (M9). M8's tie compares whole edge-id
lists from the first edge, so a longer plan can win. Ordering the heap by (cost,
edge-id tuple) over product nodes satisfies M6 to M8 and stays fast because the
product graph is small even when the path count is astronomical.

The field view is the one representation every stage reads, and the presence of an
explicit null has two homes: the per-field column and the ini fallback. The shipped
code and its README offer a plausible default for the open column that the contract
contradicts. Corrections are invisible to planning (C5), so the executor, not the
planner, has to discover that a correction broke a later edge, and the classifier has
to report what the executor found.

## Solution shape

`solution/solve.py` (604 lines) copies `/app/repo`, applies twenty text repairs, each
asserted to match exactly once, and adds `__main__.py`:

1. `FieldView.from_payload` keeps explicit null as a state; `null_counts_as` falls back
   to the ini `[presence]` value and `fill_mode` reads the column first; the README
   line on optional fields is removed.
2. `plan_migration` runs a heap search over (schema, field states) ordered by (cost,
   edge-id tuple), with prerequisites checked on the state reached and repeated
   schemas allowed.
3. `execute_plan` applies corrections on first arrival at their pinned schema (the
   source counts) and re-checks prerequisites before every edge; `classify_result`
   takes status and code from the execution result.
4. `_Run._admit` keys identity on the canonical partner and registers the holder once
   the partner stage passes; `_ordered` sorts by `received_seq` then line.
5. `resolve_partner` follows every merge link and raises E_ALIAS_CYCLE on a loop;
   `read_feed` turns a bad line into an E_PARSE record; `_token_lists` and
   `tokens_for` use a partner's own line exactly; `build_summary` uses the taxonomy
   and partner order; `cli._resolve` resolves against the working directory.

It then runs the visible tests on the shipped and the repaired tree, builds the
archive, extracts it again, runs `python -m migrakit run` on the shipped inputs from a
foreign folder, and writes the reports from what it observed, including the changed
functions from an AST comparison of the two trees with docstrings left out. Last, it
copies the repaired tree back over `/app/repo`.

## Ordered plan

1. Read the contract and every file it names before the code; list every rule.
2. Copy the repository, run the visible tests (seven pass, two fail), and read every
   module against the rules rather than against the failing tests or the README.
3. Repair the field view and the presence and fill fallbacks first, because planning,
   signature, operations and execution all read them.
4. Replace the planner with a product-graph search and its tie rule; test it on a
   generated layered graph of at least 30 layers, on a case where a cheap edge drops a
   field a later edge needs, and on a case whose best plan revisits a schema.
5. Repair the executor and the classifier together, then test corrections that break
   a later edge, one pinned at the canonical schema, and two pinned to one schema.
6. Repair replay identity, ordering, identity resolution, feed parsing, tokens and the
   summary, each against its rule, on small contract folders written for the purpose.
7. Repair the command line, add `__main__.py`, rerun the visible tests from an
   extracted archive in another folder, then produce the reports and the figures.

## Pitfalls

- Trusting the README or the shipped default for an open `null_counts_as` column:
  the 16 boundary records and every world with the presence gadget come out wrong.
- Fixing the null symptom in `operations.py` only: the planner and the signature still
  see explicit null as absent.
- Dijkstra on schema ids: fast, and wrong whenever a cheap edge drops a needed field or
  the best plan revisits a schema.
- Exhaustive search over (schema, state): right on small graphs, over the time limit on
  the ladders.
- Preferring fewer steps or the last edge among equal-cost plans.
- Applying corrections at the start, on every arrival, never at the canonical schema,
  or in id order; skipping the re-check.
- Fingerprinting after token replacement or after migration; keying replay identity on
  the alias; registering the holder only when planning succeeds; file order.
- Falling back to the default token list for a partner whose own line is empty.
- Stopping when the visible tests pass: they cover only the command line.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: schema-migration-plan-repair
task_name: terminal-bench/schema-migration-plan-repair
fix_patch_sha256: 25c71b6c701c5cdc752f2284c1d929d0ca149547952669c1fb7c8b4ac00dc680  # sha256 of solution/solve.sh
solve_py_sha256: 444006095fdd45fa24bcca39ad006525b3bb63085adaafd60c779bfe05719a18  # informational; solve.py is 604 lines
language: python
golden_score_measured: null  # not measured
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: >
  Not yet measured.
caveat: >
  The test channel carries 40 positive checks worth 136 weight and 5 negative
  checks worth -13 weight, so on its own it ranges -13/136 = -0.096 to
  +1.000. The judged channel carries 10 criteria, 6 positive worth 18 points
  and 4 negative worth -14, so on its own it ranges -14/18 = -0.778 to
  +1.000. tests/reward.toml divides each channel's weighted sum by its
  positive total and gives each half of the reward, so the combined reward
  runs from -0.437 to +1.000 with no clamp.
```
