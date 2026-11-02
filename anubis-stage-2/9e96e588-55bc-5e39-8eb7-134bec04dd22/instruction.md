You are the policy convergence engineer for the offline security policy compiler installed as sealb-ctl. The source archive `/app/data/tool.zip` ships a broken stdlib-only CLI. The written derivation contract lives in `/app/data/config_contract.md`, and `/app/data/config_schema.json`, `/app/data/defaults.json`, `/app/data/env_overrides.json`, `/app/data/validation_rules.json`, and `/app/data/change_journal.jsonl` complete the spine. The fifty evidence corpora `/app/data/c01_cve_severity.csv` through `/app/data/c50_oauth_scopes.bang` carry the rows. Every bit of every delivered artifact must be derived from these files; nothing may be invented, networked, or hand-written. Use only the Python standard library.

Satisfy every one of these requirements:

1. Extract `/app/data/tool.zip` safely to `/app/tool` and repair the broken CLI so every subcommand runs offline.
2. Replay `/app/data/change_journal.jsonl` strictly in ascending `seq` order; the file is intentionally out of order.
3. Classify each journal operation against `/app/data/validation_rules.json`; a `set` on an integer spine key must carry a JSON integer value inside its `bounds`, not a JSON string of digits.
4. Treat a valid `unset` as a restore to the `defaults.json` value for that key; last-set-wins while ignoring `unset` is wrong.
5. Generate the base spine as `/app/out/config.json` by driving the repaired CLI (init / set / validate), not by hand-writing JSON.
6. Produce the four zone profiles at `/app/out/profile_core.json`, `/app/out/profile_edge.json`, `/app/out/profile_dmz.json`, `/app/out/profile_mgmt.json` by starting from the finished spine, applying `/app/data/env_overrides.json` deltas, and replaying only that zone's valid journal operations.
7. Reduce the fifty corpora into `/app/out/aggregates.json`; the effective upper bound of every corpus is `hi + (R mod 97) + (J mod 31)`, where R is the finished-spine `rekey_interval_s` and J is the rejected-ops count. The two shifts are co-prime (97, 31), so a misclassified journal op can shift the aggregate of any corpus whose eligible rows sit near the shifted bound.
8. Count a row only when its `zone` is byte-exactly one of `core`, `edge`, `dmz`, `mgmt`, its `flag` is byte-exactly `active`, and `str(int(value)) == value` on the raw field bytes. Reject `-0`, `-00`, `-000`, leading zeros, leading `+`, surrounding spaces, underscores, hex, floats, units, words, scientific notation, and every non-ASCII decimal digit (Devanagari U+0966..U+096F, Arabic-Indic U+0660..U+0669, Gujarati U+0AE6..U+0AEF, full-width U+FF10..U+FF19).
9. Mirror aggregates into `/app/out/aggregates.csv`, `/app/out/aggregates.tsv`, `/app/out/aggregates.xml`, `/app/out/aggregates.ini`, `/app/out/aggregates.env`, `/app/out/aggregates.md`, and `/app/out/aggregates.txt`, corpora in sorted name order; `.env` keys upper-cased.
10. Emit `/app/out/zone_totals.json` with the counted-row total per active zone across every corpus.
11. Emit `/app/out/corpus_index.json` with `count` and a `corpora` list carrying `name`, `format`, `op`, `lo`, `hi`, `eligible_rows`, and `value`.
12. Emit `/app/out/posture.json` with `aggregate_total`, `corpus_count`, `max_corpus`, `max_value` (ties broken by the earlier name), and `nonzero_corpora`.
13. Emit `/app/out/rejected_ops.json` with `rejected` (the ascending `seq` list of every invalid journal operation) and `count`.
14. Emit `/app/out/validation_report.json` with `ok` and `checks` covering `all_artifacts_present`, `config_matches_policy`, `config_scalar_flat`, `command_failures`, `rejected_ops`, per-zone `profiles` (`scalar_flat`, `trailer`), `corpus_count`, and `aggregate_total`.
15. Emit `/app/out/summary.json` with `tool`, `profile_tag`, `trailer`, `profiles`, `artifacts`, `artifact_count`, `inputs` (sorted names of every file under `/app/data`), `input_count`, `corpus_count`, and `aggregate_total`.
16. Emit `/app/out/report.json` through the repaired tool's `export-report` subcommand with `ok`, `tool`, `config_path`, `config_sha256` (sha256 hex of `/app/out/config.json` bytes), `trailer`, and `commands` (one object per CLI call, each with `argv`, `returncode`, `stdout`). No timestamps or run-dependent fields.
17. Rebuild the repaired tool deterministically as `/app/out/tool.zip` (ZIP_STORED, fixed epoch, fixed external_attr, sorted member order) so its sha256 is reproducible across runs.
18. Emit `/app/out/manifest.sha256`: one `<sha256>  <name>` line per delivered JSON artifact except `report.json`, names in sorted order, two spaces between.
19. Every JSON artifact is written with these exact parameters: UTF-8, `json.dumps(obj, sort_keys=True, indent=2, separators=(",", ": "), ensure_ascii=False)`, plus a single trailing `\n`. Default `json.dumps(obj)` breaks the manifest.
20. The configuration must stay flat scalars only; no nested dicts or lists in `/app/out/config.json` or in any profile.
21. Keep the workflow deterministic and offline: no network, no wall-clock timestamps, no random seeds, no reliance on dict insertion order. Running the pipeline twice must produce byte-identical artifacts.

You have 7200 seconds to complete this task. Do not consult online solutions or hints specific to this task.
