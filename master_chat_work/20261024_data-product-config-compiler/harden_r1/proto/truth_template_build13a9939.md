# TRUTH.md - data-product-config-compiler

## Defect

`/app/data/tool.zip` holds `dpcc`, a standard-library Python tool (`cli.py`, `loaders.py`,
`resolve.py`, `quota.py`, `emit.py`, `README.md`) that compiles the layered settings of a
catalog of data products into five documents. `/app/data/config_contract.md` holds every
rule. The tool has nine defects; each breaks exactly one contract sentence, quoted below
with its line in `config_contract.md`. The deliverable is the repaired tool as
`/app/out/tool.zip` plus the six documents it writes for the shipped release; the
delivered archive is rerun on fresh releases.

1. (focal) Owner retirement. Lines 38-40: "Active owner on date D: an owner who has an
   owners.csv row with active_from on or before D and active_to empty or on or after D,
   and who has no `RETIRE owner=<owner>` event in deprecation.log dated on or before D."
   `loaders.load_deprecations` keeps only product events and `resolve.classify` checks
   the owners.csv interval alone, so a log-retired owner's products stay `active`, keep
   their team, receive team selectors and team overrides, and enter the quota
   denominator of all three documents.
2. (focal) JSON override typing. Lines 92-93: "A JSON-layer value keeps its JSON type and
   is never converted", restated at lines 104-106: "a JSON string for an integer or
   boolean key, whatever text it holds; a JSON boolean for an integer key; a number with
   a fraction or exponent". `resolve.check_override` runs JSON values through the text
   reader `loaders.coerce`, so `"30"` and `"true"` are accepted and applied instead of
   rejected as `type`. A quoted `weight` moves every quota of the document.
3. (focal) Identifier canonical form. Line 28: "Product ids are compared after converting
   them to upper case and removing every hyphen." `products.ini`, the manifest and the
   override loaders call `canon()`, but `loaders.load_deprecations` stores the raw
   `product=` text, so `dp-40217` or `Dp-402-17` never retires `DP40217`.
4. (drift) Line 8: the `compile` command. `cli.main` calls
   `compile_release(args.data, when=args.date, ...)` against a parameter named `date`, so
   every compile ends in a TypeError and no document is written.
5. (drift) Line 86: text-layer booleans are "`true` or `false` in any letter case".
   `loaders.load_env` turns a bare `false` into `bool("false")`, which is True, so profile
   `alerts_enabled` and `pii_scan` flip.
6. (drift) Line 119: "5. the accepted product_overrides.jsonl entries for the product, in
   ascending seq." `resolve.screen_overrides` applies entries in file order; the file is
   not in seq order.
7. (trap) Lines 126-127: "a null value removes the key from the settings and any other
   value, the empty list included, replaces the current value". `resolve.merge` skips the
   empty list, so `notify: []` and `tags: []` keep the inherited list.
8. (drift) Lines 132-135: the largest remainder quota. `quota.split_quota` uses `round()`,
   so a document's quotas need not sum to the cluster quota and remainder ties are not
   broken by product id.
9. (drift) Lines 139-140: "Python's `json.dumps(document, indent=2, sort_keys=True) +
   "\n"`." `emit.write_document` omits `sort_keys`.

The shipped release separates defects 2 and 4 to 9 (quoted integers and booleans ship in
both JSON layers). It has no `RETIRE owner=` event and writes every deprecation.log
product id in canonical form, so defects 1 and 3 change nothing on it; the fresh releases
carry both.

## Load-bearing work

- Extract the archive to `/app/tool` and repair all nine defects so the tool follows the
  contract on any release.
- Read the twelve inputs in the Inputs order; stop with exit 2 and
  `error: missing input <name>` for the first missing one, exit 2 and
  `error: invalid date <value>` for a non-calendar date, exit 3 and
  `error: catalog mismatch <smallest canonical id>` when products.ini and the manifest
  catalog differ.
- Classify every catalog product on D as retired, active or orphaned from the canonical
  log ids, the owners.csv intervals and the owner retirement events.
- Screen both JSON layers strictly (reason order `unknown_product`, `unknown_key`,
  `type`, `bounds`) and list the rejected entries in validation_report.json.
- Resolve settings layer by layer (base, selectors in file order, team overrides,
  products.ini lines, product overrides in ascending seq; profiles add the env
  `[defaults]` and `[tier.<tier>]` sections after base) with the null/empty-list merge.
- Hand out each document's quota by largest remainder over the active products.
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
and scale; log-retired owners whose products carry team weight selectors and team
overrides; mixed-case hyphenated log ids; quoted integers and booleans; largest
remainder ties at the cut), copies it into a renamed folder and runs the delivered
`/app/out/tool.zip` there as another user from a foreign working directory. Each check
owns its rows and reports the first differing path:

- `catalog_status`: status, owner and tier of every catalog product in config.json.
- `team`: the team of every catalog product.
- `settings_int`: weight, retention_days, replicas, partitions, freshness_sla_min.
- `settings_other`: pii_scan, alerts_enabled, encryption, notify, tags, cost_center.
- `config_quota`, `dev_quota`, `prod_quota`: document header and every quota.
- `dev_deploy`, `prod_deploy`: alerts_enabled, pii_scan, replicas of every active product.
- `rejected_overrides`, `summary`: the whole validation_report.json and summary.json.
- `report_run` (3): report.json names the delivered documents by their sha256.
- `date_shift` (5): status and team of the fresh release compiled 45 days later.
- `quota_rescale` (5): every quota after the cluster quotas are rescaled.
- `shuffled_relocated` (5): integer settings after the override and owner rows are
  shuffled.
- `missing_input`, `invalid_date`, `catalog_mismatch` (3 each): exit code, the exact
  error line, and no document written.
- `determinism` (3), `readonly_inputs` (3: config.json from a read-only data folder),
  `document_format` (3), `tool_zip_layout` (1).
- `negative_hardcoded_sample_answers` (%(neg)s): fires only when the fresh-release
  config.json names the shipped release.

The judged channel has %(n_judge)s criteria, positive total %(jpos)s: R1 to R6 credit
independent recomputation of status and team, quota in all three documents, the
rejected override list, resolved settings, profile deployment keys and the summary
figures; R7 a rerun on an altered copy; R8 code quality of the edited tool functions; R9
the list of files written under `/app/out`; R10 a run of the delivered archive from a
foreign directory after the last edit. Negatives: R11 claiming a check passed with no
run after the last edit (-3), R12 opening `/tests/` or `/logs/verifier` (-5). The
self-check stage of `solution/solve.sh` performs R1 to R7 and R10 and prints
`check <id> ok` for each.

Current file hashes (sha256):

%(hashes)s

## Root cause

Every defect sits where the tool handles one layer with a habit instead of the
contract: a shared text coercer reused for JSON values, an owner check that reads only
the CSV interval, a canonical-id helper called in every loader but the log loader. The
shipped release cannot separate the right reading from the habitual one for defects 1
and 3, and the quoted override rows of defect 2 produce plausible documents with nothing
to compare them to. The quota is the quantity that carries any slip into many rows: a
product wrongly active, a weight wrongly accepted or a retirement wrongly missed changes
the denominator W, which moves the quota of every active product in all three documents
and the quota totals of the summary.

## Solution shape

1. Fix the `compile` call in `cli.main`.
2. In `loaders.load_deprecations`, canonicalise `product=` ids and also collect
   `RETIRE owner=` events with their earliest date; pass them to `resolve.classify`,
   which treats an owner retired on or before D as inactive.
3. Read env values with the text-layer reader, so bare and quoted booleans read alike.
4. Replace `coerce` in `resolve.check_override` with a strict JSON type test
   (`type(v) is int` for integers, `type(v) is bool` for booleans, `str` for strings
   and enums, list of strings for lists, null only for optional keys), then bounds.
5. Apply product overrides in ascending seq; merge `[]` as a replacement.
6. Split quotas by floor plus largest remainder, ties by product id.
7. Dump documents with `indent=2, sort_keys=True` and a trailing newline.

## Ordered plan

1. Read `config_contract.md` end to end, then the tool and the head of every data file.
2. Run the shipped tool, fix the crash, and compare each document with the contract.
3. Fix the loaders, then the override screen, then the merge and the quota split.
4. Compile with the manifest `compile_date`, export report.json, and zip the tool.
5. Recompute status and team, settings, rejected overrides, quotas and summary figures
   outside the tool and compare them with the documents.
6. Build a copy of the data with altered contents (a log-retired owner, a mixed-case
   hyphenated log id, a quoted weight, changed quotas) and check that the dependent
   figures move as the contract says.
7. Unpack the delivered archive elsewhere and run it from another directory on a
   renamed data folder.

## Pitfalls

- Keeping `coerce` for JSON values because the contract allows quoted values in text
  layers.
- Judging owner activity from owners.csv only.
- Canonicalising product ids everywhere except deprecation.log.
- Computing the quota denominator over compiled rather than active products, or
  rounding each share with `round()`.
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
