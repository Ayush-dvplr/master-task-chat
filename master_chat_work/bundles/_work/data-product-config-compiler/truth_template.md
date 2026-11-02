# TRUTH.md - data-product-config-compiler

## Defect

`/app/data/tool.zip` holds `dpcc`, a standard-library Python tool (`cli.py`, `loaders.py`,
`resolve.py`, `quota.py`, `emit.py`, `README.md`) that compiles the layered settings of a
catalog of data products into five documents. `/app/data/config_contract.md` holds every
rule. The tool has twelve defects; each breaks one contract sentence, quoted below with
its line in `config_contract.md`. The deliverable is the repaired tool as
`/app/out/tool.zip` plus the six documents it writes for the shipped release; the
delivered archive is rerun on fresh releases.

1. (focal) Assignment on D. Lines 38-42: "Assignment of an owner on date D: of the
   owner's owners.csv rows with active_from on or before D, the one with the latest
   active_from." and "Their team on D is the team of their assignment on D."
   `resolve.owner_team` returns the team of the first row in file order whose interval
   covers D. An owner with a later-started row on another team keeps the older team, and
   an owner whose latest row ended before D stays active, so team, team selectors, team
   overrides and the profile deployment keys of their products are wrong.
2. (focal) Text-layer reading. Lines 89-92: "integer as one or more of the digits 0 to 9;
   boolean as `true` or `false` in any letter case; ... Text that does not read as its
   key's type is passed over, and the key keeps the value the earlier layers gave it."
   `loaders.coerce` reads integers with `int()` and every boolean word other than `true`
   as false, so a text value that is not a digit string or `true`/`false` is applied
   instead of passed over.
3. (focal) Quota caps. Lines 140-145: "A product whose settings in that document carry
   `quota_cap` and that holds more units than its cap gives the excess back and keeps its
   cap. Every product keeps the units it holds. The units given back are handed out again
   by largest remainder in proportion to weight among the products still holding less
   than their cap or carrying no cap, with Q the units given back and W the sum of their
   weights, and each cap applies again after the round." `quota.split_quota` ignores
   `quota_cap`.
4. Owner retirement. Lines 40-41: "and who has no `RETIRE owner=<owner>` event in
   deprecation.log dated on or before D." `loaders.load_deprecations` keeps only product
   events, so a log-retired owner's products stay `active`.
5. JSON override typing. Lines 97-98: "A JSON-layer value keeps its JSON type and is never
   converted". `resolve.check_override` runs JSON values through the text reader
   `loaders.coerce`, so `"30"` and `"true"` are accepted instead of rejected as `type`.
6. Identifier canonical form. Line 28: "Product ids are compared after converting them to
   upper case and removing every hyphen." `loaders.load_deprecations` stores the raw
   `product=` text.
7. (drift) Line 8: the `compile` command. `cli.main` calls
   `compile_release(args.data, when=args.date, ...)` against a parameter named `date`, so
   every compile ends in a TypeError and no document is written.
8. (drift) Lines 89-90: text-layer booleans are "`true` or `false` in any letter case".
   `loaders.load_env` turns a bare `false` into `bool("false")`, which is True.
9. (drift) Line 122: "5. the accepted product_overrides.jsonl entries for the product, in
   ascending seq." `resolve.screen_overrides` applies entries in file order.
10. (trap) Lines 129-130: "a null value removes the key from the settings and any other
    value, the empty list included, replaces the current value". `resolve.merge` skips the
    empty list.
11. (drift) Lines 134-138: the largest remainder quota. `quota.split_quota` uses `round()`.
12. (drift) Lines 149-150: "Python's `json.dumps(document, indent=2, sort_keys=True) +
    "\n"`." `emit.write_document` omits `sort_keys`.

The shipped release separates defects 2, 3, 5 and 7 to 12: some text values carry a sign
or a yes/no/on word, four products carry a `quota_cap` that binds in round one, and quoted
integers and booleans ship in both JSON layers. It has no later-started owner row, no
`RETIRE owner=` event and only canonical deprecation.log product ids, so defects 1, 4
and 6 change nothing on it; the fresh releases carry all twelve.

## Load-bearing work

- Extract the archive to `/app/tool` and repair all twelve defects so the tool follows the
  contract on any release.
- Read the twelve inputs in the Inputs order; stop with exit 2 and
  `error: missing input <name>` for the first missing one, exit 2 and
  `error: invalid date <value>` for a non-calendar date, exit 3 and
  `error: catalog mismatch <smallest canonical id>` when products.ini and the manifest
  catalog differ.
- Classify every catalog product on D as retired, active or orphaned from the canonical
  log ids, each owner's assignment on D (latest active_from on or before D) and the owner
  retirement events.
- Read text-layer values by the schema type and pass over text that does not read as the
  type.
- Screen both JSON layers strictly (reason order `unknown_product`, `unknown_key`,
  `type`, `bounds`) and list the rejected entries in validation_report.json.
- Resolve settings layer by layer (base, selectors in file order, team overrides,
  products.ini lines, product overrides in ascending seq; profiles add the env
  `[defaults]` and `[tier.<tier>]` sections after base) with the null/empty-list merge.
- Hand out each document's quota by largest remainder over the active products, then hand
  the units above each `quota_cap` out again round by round among the products still
  under their cap, keeping the units already held.
- Write config.json, profile_dev.json, profile_prod.json, validation_report.json and
  summary.json in the stated format, export report.json, and deliver
  `/app/out/tool.zip` with `cli.py` at the archive root.

## Verification

`tests/test.sh` prepares `/logs/verifier` and runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. rewardkit
scores the test channel from the checks in `tests/test_output.py` and the judged channel
from `tests/judge.toml` against the agent trajectory. `tests/reward.toml` divides each
channel's weighted sum by its positive total and gives each half of the reward.

The test channel has %(n_pos)s positive checks with positive weight total %(pos)s and
%(n_neg)s negative check worth %(neg)s. Each row family has a visible check (weight 3)
that compares the documents in `/app/out` for the shipped release with a reference
computed inside the tests from the embedded shipped data, and a `_hard` check (weight 5)
that builds a fresh release from an embedded seeded builder (another date, release name
and scale; owners with a later-started row on another team of equal weight; text values
with signs, non-ASCII digits and yes/no/on words; quota caps that bind in round one and
caps that bind only after a re-share; log-retired owners; mixed-case hyphenated log ids;
quoted integers and booleans; largest remainder ties at the cut), copies it into a
renamed folder and runs the delivered `/app/out/tool.zip` there as another user from a
foreign working directory. Each check owns its rows and reports the first differing
path:

- `status_team`: status, owner, tier and team of every catalog product in config.json.
- `settings_int`: weight, retention_days, replicas, partitions, freshness_sla_min.
- `settings_other`: pii_scan, alerts_enabled, encryption, notify, tags, cost_center.
- `config_quota`, `dev_quota`, `prod_quota`: document header and every quota.
- `dev_deploy`, `prod_deploy`: alerts_enabled, pii_scan, replicas of every active product.
- `rejected_overrides`, `summary`: the whole validation_report.json and summary.json.
- `date_shift` (5): status and team of the fresh release compiled 45 days later.
- `quota_rescale` (5): every quota after the cluster quotas are rescaled.
- `shuffled_relocated` (5): integer settings after the override and owner rows are
  shuffled.
- `config_quota_capped`, `dev_quota_capped`, `prod_quota_capped` (5 each): every quota of
  a fresh release where about a third of the active products carry a cap.
- `readonly_inputs` (3): config.json from a read-only data folder.
- `report_run`, `missing_input`, `invalid_date`, `catalog_mismatch`, `determinism`,
  `document_format`, `tool_zip_layout` (1 each): report.json digests, the exact error
  line, exit code and no document written, byte-identical reruns, the document format,
  `cli.py` at the archive root.
- `negative_hardcoded_sample_answers` (%(neg)s): fires only when the fresh-release
  config.json names the shipped release.

The judged channel has %(n_judge)s criteria, positive total %(jpos)s: R1 to R6 credit
independent recomputation of status and team, quota in all three documents, the
rejected override list, resolved settings, profile deployment keys and the summary
figures, each for the shipped data and for an altered copy; R7 a rerun on an altered
copy; R8 a maintainable delivered tool.zip; R9 the list of files written under
`/app/out`; R10 a run of the delivered archive from a foreign directory after the last
edit; R13 a later-started owner row that ended before D, checked to orphan the owner's
products; R14 a text value outside the digits 0 to 9, checked to leave the earlier value;
R15 a cap that binds only after a re-share, computed by hand or by separate code and
compared with the tool. Negatives: R11 claiming a check passed with no run after the
last edit (-3), R12 opening `/tests/` or `/logs/verifier` (-5). The self-check stage of
`solution/solve.sh` performs R1 to R7, R10 and R13 to R15 and prints `check <id> ok` for
each.

Current file hashes (sha256):

%(hashes)s

## Root cause

Every defect sits where the tool handles one layer with a habit instead of the
contract: the first covering owners.csv row instead of the owner's latest assignment, a
lenient `int()` text reader instead of the stated digits, one largest-remainder split
with no cap, a shared text coercer reused for JSON values, a canonical-id helper called
in every loader but the log loader. The shipped release cannot separate the right
reading from the habitual one for the assignment rule, and the caps it ships bind only in
round one, where a re-share from scratch and the stated additive re-share agree. Team
plants keep the old and the new team at the same weight, so a wrong team costs the team,
settings and deployment rows; the quota is the quantity that carries a wrong weight or
a wrong cap round into every quota row of a document and the summary totals.

## Solution shape

1. Fix the `compile` call in `cli.main`.
2. In `resolve.owner_team`, take the owner's row with the latest active_from on or before
   D; the owner is active only when that row's active_to is empty or on or after D.
3. In `loaders.load_deprecations`, canonicalise `product=` ids and also collect
   `RETIRE owner=` events with their earliest date; pass them to `resolve.classify`.
4. Make `loaders.coerce` read integers only from the digits 0 to 9 and booleans only from
   `true`/`false`; return a pass-over marker from `text_value` and skip it in every text
   layer, the env files included.
5. Replace `coerce` in `resolve.check_override` with a strict JSON type test, then bounds.
6. Apply product overrides in ascending seq; merge `[]` as a replacement.
7. Split quotas by floor plus largest remainder, ties by product id, then loop: give back
   the units above each cap, re-share them among the products under their cap, keep what
   each holds, until nothing is given back.
8. Dump documents with `indent=2, sort_keys=True` and a trailing newline.

## Ordered plan

1. Read `config_contract.md` end to end, then the tool and the head of every data file.
2. Run the shipped tool, fix the crash, and compare each document with the contract.
3. Fix the loaders, then the owner assignment, the override screen, the merge and the
   quota split.
4. Compile with the manifest `compile_date`, export report.json, and zip the tool.
5. Recompute status and team, settings, rejected overrides, quotas and summary figures
   outside the tool and compare them with the documents.
6. Build copies of the data with altered contents (a later owner row that ended before D,
   a text value with a non-ASCII digit, a cap that binds after a re-share, a log-retired
   owner, changed quotas) and check that the dependent figures move as the contract says.
7. Unpack the delivered archive elsewhere and run it from another directory on a
   renamed data folder.

## Pitfalls

- Taking the first owners.csv row whose interval covers D.
- Reading text integers with `int()`, which accepts signs and non-ASCII digits.
- Re-sharing the whole quota from scratch after fixing the capped products.
- Keeping `coerce` for JSON values because text layers accept quoted values.
- Canonicalising product ids everywhere except deprecation.log.
- Skipping `[]` in the merge, or applying overrides in file order.
- Delivering a tool that writes beside its data or depends on the working directory.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: data-product-config-compiler
task_name: terminal-bench/data-product-config-compiler
fix_patch_sha256: %(solve_sh)s  # sha256 of solution/solve.sh
solve_py_sha256: %(solve_py)s  # informational; solve.py is %(solve_lines)s lines
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: >
  Not yet measured. The expected figures are exactly 1.000 on each oracle run
  and exactly 0.000 on a no-op run, on the test channel in
  tests/test_output.py only; the judged channel has no oracle score.
caveat: >
  The test channel carries %(n_pos)s positive checks worth %(pos)s weight and %(n_neg)s
  negative check worth %(neg)s weight. The judged channel carries %(n_judge)s criteria
  worth %(jpos)s positive points. tests/reward.toml divides each channel's weighted
  sum by its positive total and gives each half of the reward.
```
