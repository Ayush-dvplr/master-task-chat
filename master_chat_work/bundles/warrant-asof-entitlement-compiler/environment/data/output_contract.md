# Output contract

Every JSON document is written with two-space indentation, keys sorted at every level, UTF-8, and one trailing newline. Instants are UTC `YYYY-MM-DDTHH:MM:SSZ`. Documents carry no wall clock time, host name or absolute path of the machine that produced them.

## config.json

A flat object: `as_of`, `recorded_cutoff`, and every resolved key (`config_contract.md`). Values are strings, integers or booleans.

## profile_dev.json and profile_prod.json

A flat object mapping `principal|permission` (for example `emp:004211|orders.db.read`) to the key's value, an instant or `open`. Only keys listed under `access_contract.md` appear.

## validation_report.json

```json
{
  "rejects":     [{"source": "<file name>", "record": "<record id>", "reason": "<reject reason>"}],
  "unresolved":  [{"source": "<file name>", "record": "<record id>", "reason": "<unresolved reason>"}],
  "held_grants": [{"profile": "dev|prod", "ticket": "<ticket>", "reason": "pending|vetoed"}],
  "unattested":  [{"profile": "dev|prod", "principal": "<id>", "permission": "<name>"}],
  "sod":         [{"profile": "dev|prod", "principal": "<id>", "rule": "<rule>", "outcome": "standing_conflict|suspended", "permission": "<suspended permission or null>"}],
  "self_check":  {"<file name>": {"records": 0, "invisible": 0, "rejected": 0, "unresolved": 0, "collapsed": 0, "accepted": 0}}
}
```

`rejects` and `unresolved` list one entry per record, the source being the file the record came from and the record id as `corpus_index.md` defines it, sorted by source, record, then reason, with exact repeats listed once. `held_grants` lists every pending or vetoed request whose requested end is open or after `as_of`, sorted by profile then ticket. `unattested` lists every pair whose standing and elevated components were dropped for want of a current review, sorted by profile, principal, permission. `sod` lists one entry per principal and rule where both sides were held, `permission` being the suspended permission for `suspended` and null for `standing_conflict`, sorted by profile, principal, rule. `self_check` has one entry per record file (every `.csv`, `.tsv`, `.jsonl` and `.log` input), counting its rows by class (`provenance_rules.md`); `records` is the file's row count and equals the sum of the five classes.

## summary.json

```json
{
  "as_of": "...", "recorded_cutoff": "...",
  "profiles":     {"dev": {"keys": 0, "principals": 0, "open_keys": 0, "breakglass_keys": 0}, "prod": {}},
  "eligibility":  {"dev": {"eligible": 0, "inactive": 0, "disabled": 0, "mfa_blocked": 0}, "prod": {}},
  "grants":       {"dev": {"active": 0, "pending": 0, "vetoed": 0}, "prod": {}},
  "audit_counts": {"rejects": 0, "unresolved": 0, "held_grants": 0, "unattested": 0, "sod": 0},
  "inputs": ["<every file name in the data directory, sorted>"],
  "input_count": 0
}
```

`keys` is the number of keys in that profile, `principals` the number of distinct principals among them, `open_keys` those whose value is `open`, and `breakglass_keys` those that have an on-call component. `eligibility` counts every principal once by its state for that profile. `active` counts approved grants of that env that are in effect at `as_of` for an eligible beneficiary; `pending` and `vetoed` count that profile's entries in `held_grants`. `audit_counts` gives the length of each list in `validation_report.json`.

## report.json

```json
{
  "tool": "warrant-ctl",
  "commands": [{"argv": ["python3", "cli.py", "compile", "..."], "returncode": 0}],
  "config_sha256": "<hex sha256 of config.json bytes>",
  "profile_dev_sha256": "<hex>",
  "profile_prod_sha256": "<hex>",
  "repairs": [{"module": "<file inside tool.zip>", "defect": "<one sentence>"}]
}
```

`commands` lists, in the order they ran, the compiler invocations that produced the delivered artifacts.

## tool.zip

The repaired compiler: `cli.py` at the archive root beside every module it imports, runnable as `python3 cli.py <subcommand>` from any working directory after extraction.
