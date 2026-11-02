# Security policy compilation contract

Every value the compiler emits is derived from the files in `/app/data`.
Nothing is fixed by the tool. The compiler is offline and uses only the
Python standard library.

## Spine policy (config.json)

1. Start from `defaults.json`: the four `base_config` integer keys
   (`max_sessions`, `retry_budget`, `handshake_timeout_ms`,
   `rekey_interval_s`) plus its `trailer`, `checksum` and `mode`. `profile`,
   `producer` and `container` come from `config_schema.json`. Those ten keys
   are the schema `required_keys`; the configuration is flat scalars only.
2. Replay `change_journal.jsonl`. Each line is one recorded operation with
   `seq`, `env`, `key`, an `op` that is either `set` or `unset`, and (for a
   `set`) a `value`. Lines are not in `seq` order: apply in ascending `seq`.
   An operation is valid only when all hold:
   - its `env` is listed in `journal_envs` of `validation_rules.json`;
   - its `key` is one of the four integer spine keys or `mode` (exact case);
   - a `set` on an integer key carries a JSON integer `value` inside the
     inclusive `[min, max]` pair of `bounds`; a `set` on `mode` carries a
     `value` in `allowed_modes`; an `unset` needs no value.
   Apply valid operations as events in `seq` order, last valid wins per key: a
   valid `set` assigns the key, and a valid `unset` restores the key to its
   `defaults.json` value (the `base_config` value for an integer key, the
   `defaults.json` `mode` for `mode`). An `unset` after a `set` therefore
   clears that `set`; keeping only the last `set` and ignoring `unset` is wrong.

## Profiles (profile_core.json, profile_edge.json, profile_dmz.json, profile_mgmt.json)

For each zone, start from the finished spine configuration and then: add
`retry_budget_delta`, `handshake_timeout_ms_delta` and `rekey_interval_s_delta`
of that zone in `env_overrides.json`, take its `mode`, set `profile` to
`<spine profile>-<zone>` and `trailer` to `<spine trailer>:<zone>`, then replay
the valid journal operations whose `env` is that zone, in ascending `seq`.

## Evidence corpora and the eligibility rule

There are fifty evidence corpora. Each logical row carries a `zone`, an
integer `value`, and a `flag`. A row is counted only when every one holds:

- `zone` is exactly one of the active zones `core`, `edge`, `dmz`, `mgmt`;
- `flag` is exactly the token `active` (no case or whitespace variants);
- `value` is a canonical base-10 integer, meaning `str(int(value)) == value`
  evaluated on the exact field bytes (not on the result of any numeric
  parse). This rejects: leading zeros, a leading `+`, surrounding spaces,
  underscore grouping, hex, floats, units, words, scientific notation,
  the strings `-0`, `-00`, `-000` (which parse as integer 0 but are not
  canonical), and any non-ASCII decimal digit (Devanagari U+0966..U+096F,
  Arabic-Indic U+0660..U+0669, Gujarati U+0AE6..U+0AEF, full-width
  U+FF10..U+FF19) because `int()` accepts them silently;
- the integer is within the corpus's effective bound. The lower bound is the
  published `lo` in `corpus_bounds` of `validation_rules.json`. The effective
  upper bound is the published `hi` plus two shifts that both depend on the
  journal replay: `(R mod 97) + (J mod 31)`, where
  `R` is the finished-spine `rekey_interval_s` from `config.json`, and
  `J` is the number of rejected journal operations (the `count` field of
  `rejected_ops.json`). Every corpus therefore depends on BOTH a correct
  spine replay AND byte-exact validity classification: a wrong `R` or a
  single misclassified journal operation shifts every corpus's upper bound
  and corrupts all fifty aggregates. The two shifts are co-prime (97 and 31)
  so an off-by-one in `J` is observable, and each corpus plants rows just
  above its published `hi` so these shifts change which rows count.

Comparisons are exact and byte-literal: there is no case-folding, no Unicode
normalization, and no numeric parse through floating point. A value written
with full-width digits, a zone with a zero-width or look-alike (for example
Cyrillic) character, and a bound at or beyond 2**53 are all judged by the exact
rules above, so `int(value)` (never `float`) and byte equality are required.

Blank lines and lines whose first non-space character is `#` are skipped in
the line-oriented formats; a record whose field count is not three is skipped.

Each corpus declares one aggregation operator over the counted integers, in
the file row order:

- `max`, `min`, `sum`: the maximum, minimum or sum of the counted values;
- `count`: how many rows were counted;
- `first`, `last`: the first or last counted value in file order.

When no row is counted, `max`, `min`, `sum`, `first` and `last` are `0`.

The formats, operators and bounds of the fifty corpora:

| corpus | format | operator | lo | hi |
| --- | --- | --- | --- | --- |
| c01_cve_severity.csv | csv | max | 1 | 500 |
| c02_cipher_grade.tsv | tsv | min | 2 | 517 |
| c03_port_exposure.psv | psv | sum | 3 | 534 |
| c04_tls_versions.scsv | scsv | count | 4 | 551 |
| c05_key_age_days.colon | colon | last | 5 | 568 |
| c06_iam_priv_level.ssv | ssv | first | 1 | 585 |
| c07_mfa_factor_count.caret | caret | max | 2 | 602 |
| c08_patch_lag_hours.at | at | min | 3 | 619 |
| c09_firewall_hits.dcolon | dcolon | sum | 4 | 636 |
| c10_cert_days_left.bang | bang | count | 5 | 653 |
| c11_session_ttl.tilde | tilde | last | 1 | 670 |
| c12_rate_budget.json | jsonarr | first | 2 | 687 |
| c13_scope_bits.jsonl | jsonl | max | 3 | 704 |
| c14_audit_gap_min.xml | xmlflat | min | 4 | 721 |
| c15_sudo_grants.nxml | xmlnest | sum | 5 | 738 |
| c16_ssh_keybits.ini | ini | count | 1 | 755 |
| c17_kms_rotations.fixed | fixed | last | 2 | 772 |
| c18_acl_depth.md | mdtable | first | 3 | 789 |
| c19_quota_caps.kv | kvline | max | 4 | 806 |
| c20_login_fails.properties | props | min | 5 | 823 |
| c21_privilege_escal.csv | csv | sum | 1 | 840 |
| c22_dns_ttl_sec.tsv | tsv | count | 2 | 857 |
| c23_backup_age_hrs.psv | psv | last | 3 | 874 |
| c24_vuln_count.scsv | scsv | first | 4 | 891 |
| c25_handshake_ms.colon | colon | max | 5 | 908 |
| c26_nonce_reuse.ssv | ssv | min | 1 | 925 |
| c27_hsts_max_age.caret | caret | sum | 2 | 942 |
| c28_cookie_ttl.at | at | count | 3 | 959 |
| c29_jwt_exp_min.dcolon | dcolon | last | 4 | 976 |
| c30_replay_window.bang | bang | first | 5 | 993 |
| c31_entropy_bits.tilde | tilde | max | 1 | 1010 |
| c32_salt_rounds.json | jsonarr | min | 2 | 1027 |
| c33_cidr_size.jsonl | jsonl | sum | 3 | 1044 |
| c34_egress_ports.xml | xmlflat | count | 4 | 1061 |
| c35_ingress_ports.nxml | xmlnest | last | 5 | 1078 |
| c36_trust_score.ini | ini | first | 1 | 1095 |
| c37_risk_weight.fixed | fixed | max | 2 | 1112 |
| c38_drift_count.md | mdtable | min | 3 | 1129 |
| c39_seal_depth.kv | kvline | sum | 4 | 1146 |
| c40_vault_leases.properties | props | count | 5 | 1163 |
| c41_rotation_days.csv | csv | last | 1 | 1180 |
| c42_throttle_rps.tsv | tsv | first | 2 | 1197 |
| c43_ban_minutes.psv | psv | max | 3 | 1214 |
| c44_cap_drops.scsv | scsv | min | 4 | 1231 |
| c45_syscall_allow.colon | colon | sum | 5 | 1248 |
| c46_namespace_ct.ssv | ssv | count | 1 | 1265 |
| c47_cgroup_limit.caret | caret | last | 2 | 1282 |
| c48_seccomp_rules.at | at | first | 3 | 1299 |
| c49_apparmor_hits.dcolon | dcolon | max | 4 | 9007199254740993 |
| c50_oauth_scopes.bang | bang | min | 5 | 1333 |

### Wire formats

- `csv`, `tsv`: `zone`, `value`, `flag` separated by comma or tab, with a header.
- `psv`, `scsv`, `colon`, `caret`, `at`, `bang`, `tilde`: the three fields
  separated by `|`, `;`, `:`, `^`, `@`, `!` or `~`, no header.
- `dcolon`: the three fields separated by `::`.
- `ssv`: the three fields separated by runs of spaces, with a header.
- `jsonarr`: a JSON array of objects with `zone`, `value`, `flag`.
- `jsonl`: one JSON object per line; `//` lines are comments.
- `xmlflat`: `<rows>` of `<row zone=.. value=.. flag=../>`.
- `xmlnest`: `<rows>` of `<row><zone/><value/><flag/></row>`.
- `ini`: one `[rNNNN]` section per row with `zone`, `value`, `flag` keys.
- `fixed`: fixed columns, `zone` in 0-10, `value` in 10-30, `flag` from 30.
- `mdtable`: a Markdown table with a `zone value flag` header and a rule row.
- `kvline`: one line per row with `zone=.. value=.. flag=..` tokens.
- `props`: `rNNNN.zone`, `rNNNN.value`, `rNNNN.flag` property lines.

In `jsonarr` and `jsonl` a JSON integer is already canonical; a value given
as a JSON string, float or boolean is judged by the canonical-integer rule
and is rejected when it is not a canonical base-10 integer string.

## Derived artifacts

- All JSON artifacts are written with these exact parameters: UTF-8,
  `json.dumps(obj, sort_keys=True, indent=2, separators=(",", ": "),
  ensure_ascii=False)` followed by a single trailing `\n` newline. No
  timestamps or run-dependent fields anywhere. The `manifest.sha256` is
  computed over these exact bytes; any serialization drift breaks it.
- `aggregates.json`: an object mapping each corpus name to its derived integer.
- `aggregates.csv`, `.tsv`, `.xml`, `.ini`, `.env`, `.md`, `.txt`: the same map
  in each format, corpora in sorted name order; the `.env` keys are the corpus
  names upper-cased.
- `zone_totals.json`: for each active zone, the number of counted rows across
  every corpus whose row zone is that zone.
- `corpus_index.json`: `count` and a `corpora` list, one object per corpus with
  `name`, `format`, `op`, `lo`, `hi`, `eligible_rows` and `value`.
- `posture.json`: `aggregate_total` (sum of every derived value), `corpus_count`,
  `max_corpus` and `max_value` (the corpus with the greatest derived value, ties
  broken by the earlier name), and `nonzero_corpora`.
- `rejected_ops.json`: `rejected`, the ascending `seq` of every invalid journal
  operation, and its `count`.
- `validation_report.json`: `ok` and `checks` with `all_artifacts_present`,
  `config_matches_policy`, `config_scalar_flat`, `command_failures`,
  `rejected_ops`, `profiles` (per zone `scalar_flat` and `trailer`),
  `corpus_count` and `aggregate_total`.
- `summary.json`: `tool`, `profile_tag` (the spine `profile`), `trailer`,
  `profiles`, `artifacts`, `artifact_count`, `inputs` (sorted names of every
  file in `/app/data`), `input_count`, `corpus_count` and `aggregate_total`.
- `report.json`: written by `export-report`, with `ok`, `tool`, `config_path`,
  `config_sha256` (the sha256 hex of the delivered `config.json` bytes),
  `trailer` and `commands` (one object per command run, each with `argv`,
  `returncode` and `stdout`). No timestamps or other volatile keys anywhere.
- `manifest.sha256`: for each delivered JSON artifact except `report.json`, one
  line `<sha256>  <name>`, names in sorted order, two spaces between.
- `tool.zip`: the repaired tool itself, rebuilt deterministically.

