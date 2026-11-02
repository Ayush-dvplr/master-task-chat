# migrakit repository contract

This file and `migration_semantics.md` state how the repaired `migrakit`
repository must behave. More rules live in the comment headers of
`null_semantics.ini` (N rules), `correction_log.txt` (C rules),
`partner_aliases.xml` (P rules) and the `rules` list of `report_taxonomy.json`
(T rules). Rules are numbered K1 to K19 here. Every rule applies whether or not
the shipped code already follows it.

## Package and public API

K1. The repository at `/app/repo` holds `pyproject.toml`, `README.md`,
`src/migrakit/` and `tests/test_visible.py`; the delivered archive holds the
same layout at its root. The package imports as `migrakit`
from `src/`, uses only the Python 3.12 standard library, and every name below is
importable from the top-level `migrakit` package.

K2. `load_contracts(path)` reads these seven files from one contract folder and
returns a registry object that the other functions take as their first
argument: `schema_versions.json`, `migration_edges.csv`, `field_policy.tsv`,
`null_semantics.ini`, `partner_aliases.xml`, `report_taxonomy.json`,
`partner_order.tsv`. Other files in the folder are ignored. `/app/ci` is such a
folder.

K3. `resolve_partner(registry, value)` returns the canonical partner id for a
partner id or alias string (P rules).

K4. `record_fingerprint(schema_id, payload)` returns the 64-character lowercase
hex sha256 of the UTF-8 bytes of
`json.dumps({"payload": payload, "schema": schema_id}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.

K5. `state_signature(registry, schema_id, payload)` returns a dict (M10).

K6. `plan_migration(registry, schema_id, payload)` returns the plan as a list of
edge id strings (M6 to M9). It plans on the payload exactly as given.

K7. `execute_plan(registry, schema_id, payload, plan, corrections)` runs a plan on
one record (M11, M12 and the C rules) and returns a dict. `plan` is a list of
edge ids forming a path from `schema_id`. `corrections` is a list, in log order,
of the corrections that belong to this record, each a dict
`{"id": str, "op": "SET" | "UNSET" | "NULL", "schema": str, "field": str, "value": any}`
(`value` is used by SET only). Neither function changes its arguments.

K8. `build_summary(registry, records, invalid_corrections)` returns the run
summary (K18) for a list of record dicts (K17) and a list of invalid correction
ids.

K9. `run_pipeline(contracts, feed, corrections, manifest)` takes four paths (the
contract folder, the feed, the correction log, the replay manifest) and returns
the tuple `(records, summary)`: the record dicts in feed line order and the
summary built from them.

K10. `python -m migrakit run --contracts DIR --feed FILE --corrections FILE
--manifest FILE --out DIR` runs `run_pipeline`, creates the output folder if
needed, and writes `records.jsonl` (one record per line, feed line order) and
`run_summary.json`. Relative paths are taken from the caller's working
directory. `python -m migrakit --help` exits with status 0.

K11. A rejection raises `migrakit.MigrationError`; its `code` attribute is one
of the K12 codes. `plan_migration` raises it for E_UNKNOWN_SCHEMA and
E_UNREACHABLE, `resolve_partner` for E_UNKNOWN_PARTNER and E_ALIAS_CYCLE,
`state_signature` for E_UNKNOWN_SCHEMA.

K12. Error catalogue (exact strings): `E_PARSE` (bad feed line, K15),
`E_UNKNOWN_PARTNER` (P1), `E_ALIAS_CYCLE` (P3), `E_UNKNOWN_SCHEMA` (schema id
not in schema_versions.json), `E_UNREACHABLE` (no plan exists, M7),
`E_PREREQ_FAILED` (a prerequisite fails during execution, M11),
`E_REPLAY_CONFLICT` (K16), `E_INVALID_CORRECTION` (C8; listed in the summary,
never a record code).

## Pipeline

K13. Stage order for each feed line: parse (K15); canonical partner (P rules);
fingerprint and replay identity (K16); null tokens (N6 to N8); plan (M rules);
execute with corrections (C rules, M11); classify (status and code from the
execution result) and summarise (K18, T rules). Lines are processed in
`received_seq` order of their batch in `replay_manifest.csv` (columns
`batch_id,received_seq`), then by feed line number.

K14. Limits. A contract folder holds at most 1,200 schemas and 6,000 edges; the
edges of one domain name at most 8 prerequisite fields and at most 10 fields in
total; a plan has at most 80 edges. Inside these limits every
`plan_migration` call must return within 10 seconds on a machine
with 2 CPUs, including graphs whose number of distinct paths is far too large
to list.

K15. A feed line is rejected with E_PARSE when it is not JSON, is not an object,
lacks a non-empty string `batch`, `partner`, `key` or `schema`, has a `payload`
that is not an object, or names a batch missing from the manifest. Such a record
has `batch`, `partner`, `key` and `schema` null. The run continues with the next
line.

K16. Replay identity. The identity of a record is (canonical partner id, key).
Its fingerprint is `record_fingerprint(schema, payload)` taken on the line as
received, before null tokens are replaced and before migration. In processing
order, the first record of an identity that passes the partner stage is its
holder. A later record with the same identity and the same fingerprint is
`replayed`. A later record with a different fingerprint is rejected with
E_REPLAY_CONFLICT, unless a REISSUE correction (C7) for that identity names a
prefix of its fingerprint: then the holder becomes `superseded` (code null,
payload null; its other keys stay) and the new record becomes the holder and is
migrated.

## Records, summary and reports

K17. Record keys (records.jsonl and `run_pipeline`): `line` (1-based feed line),
`batch`, `partner` (canonical id or null), `key`, `status` (`migrated`, `failed`,
`replayed`, `superseded`, `rejected`), `code` (a K12 code or null), `schema`
(canonical schema when migrated, the schema where execution stopped when failed,
else the schema as received), `plan` (edge ids or null), `completed_steps` (0
when execution never started), `failed_edge`, `payload` (the migrated payload when migrated, else null),
`attempted` (true when execution started), `fingerprint` (null before the
partner stage passes).

K18. Summary keys (`run_summary.json`, `build_summary`): `records` (count),
`attempted` (records with `attempted` true), `by_status` and `by_code` (counts
of the values present), `by_category` (T1, T2), `invalid_corrections` (sorted
ids, C8), `partners` (T3: list of `{"partner", "records", "migrated",
"failed"}`).

K19. Deliverables under `/app/out`:
- `patched-repo.zip`: the repaired repository with the K1 layout at the archive
  root, no directory entries, no absolute or `..` member names.
- `summary.json`: the run summary the repaired package produces for the shipped
  inputs (contracts `/app/ci`, feed `partner_batches.jsonl`, corrections
  `correction_log.txt`, manifest `replay_manifest.csv`).
- `module_core.json`, `module_parser.json`, `module_report.json`: each
  `{"module": "core" | "parser" | "report", "changed_functions": [...],
  "notes": [...]}`. `changed_functions` is the sorted, non-empty list of dotted
  names relative to `migrakit` (for example `core.records.FieldView.state`) of
  every function or method you changed or added in that area. Areas: core is
  `core/` and `pipeline.py`; parser is `parser/` and `cli.py`; report is
  `report/`. `notes` is a list of strings.
- `test_fixes.json`: `{"visible_tests": [{"name", "before", "after"}, ...]}`,
  one entry per test method of `tests/test_visible.py` sorted by name, `before`
  and `after` being `pass` or `fail` (an error counts as `fail`) for the shipped
  and the repaired repository.
- `repair-report.json`: `{"package": "migrakit", "fixes": [non-empty strings],
  "checks": [{"name": str, "passed": bool}, ...]}` with at least one passed
  check.
