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
   `seq`, `env`, `key`, an `op` that is `set`, `unset` or `touch`, and (for a
   `set` or a `touch`) a `value`. Lines are not in `seq` order: apply in
   ascending `seq`.
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
`<spine profile>-<zone>` and set `trailer` per the HARDENING_V2 "Fixed-point
profile trailer" section below (the authoritative statement of the trailer
format), then replay the valid journal operations whose `env` is that zone,
in ascending `seq`, each judged by the rules above against that zone's own
state at that `seq`.

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
  upper bound is the published `hi` plus three shifts that all depend on the
  pipeline: `(R mod 97) + (J mod 31) + (Z mod 53)`, where
  `R` is the finished-spine `rekey_interval_s` from `config.json`,
  `J` is the number of rejected journal operations (the `count` field of
  `rejected_ops.json`), and `Z` is the first 16 hex characters of
  `sha256(/app/out/tool.zip)` parsed as a hex integer. Every corpus therefore
  depends on BOTH a correct spine replay AND byte-exact validity
  classification AND a reproducible `tool.zip`: a wrong `R`, a single
  misclassified journal operation, or a non-reproducible archive shifts every
  corpus's upper bound. The three moduli
  (97, 31, 53) are pairwise coprime so an off-by-one in any of `R`, `J`, or
  `Z` is observable, and each corpus plants rows just above its published
  `hi` so these shifts change which rows count. The HARDENING_V2 section
  below is the authoritative statement of this rule; it is restated here so
  the eligibility rule is complete at its first appearance.

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
  names upper-cased. Each mirror uses a fixed shape, so every byte is derived
  rather than invented. Every mirror sorts by corpus name ascending and ends
  with one trailing `\n`.
  - `aggregates.csv`: header line `corpus,value`, then one `name,value`
    line per corpus.
  - `aggregates.tsv`: header line `corpus<TAB>value`, then one
    `name<TAB>value` line per corpus.
  - `aggregates.ini`: single section `[aggregates]`, then one `name = value`
    line per corpus (one ASCII space on each side of `=`).
  - `aggregates.env`: one `NAME=value` line per corpus, name upper-cased,
    no surrounding quotes.
  - `aggregates.md`: header row `| corpus | value |`, rule row
    `| --- | --- |`, then one `| name | value |` row per corpus.
  - `aggregates.txt`: one `name value` line per corpus, single ASCII space
    separator.
  - `aggregates.xml`: root element `<aggregates>` with child
    `<corpus name="NAME" value="N" />` per corpus, written through
    `xml.etree.ElementTree` (`ET.tostring(root, encoding="unicode") + "\n"`).
- `zone_totals.json`: for each active zone, the number of counted rows across
  every corpus whose row zone is that zone.
- `corpus_index.json`: `count` and a `corpora` list, one object per corpus with
  `name`, `format`, `op`, `lo`, `hi`, `eligible_rows` and `value`.
- `posture.json`: `aggregate_total` (sum of every derived value), `corpus_count`,
  `max_corpus` and `max_value` (the corpus with the greatest derived value, ties
  broken by the earlier name), `nonzero_corpora`, `zip_sha256` (the sha256 hex
  of the `/app/out/tool.zip` bytes), `config_sha256` (the sha256 hex of the
  `/app/out/config.json` bytes) and `touch_rejected` (the number of rejected
  `touch` journal operations).
- `rejected_ops.json`: `rejected`, the ascending `seq` of every invalid journal
  operation, and its `count`.
- `validation_report.json`: `ok` and `checks` with `all_artifacts_present`,
  `config_matches_policy`, `config_scalar_flat`, `command_failures`,
  `rejected_ops` (the same ascending `seq` list as `rejected_ops.json`'s
  `rejected`), `profiles` (per zone `scalar_flat` and `trailer`),
  `corpus_count`, `aggregate_total`, `commands_through_cli` (the number of
  entries in `report.json`'s `commands` list, at least 53) and `zip_shift`
  (`Z mod 53`).
- `summary.json`: `tool`, `profile_tag` (the spine `profile`), `trailer`,
  `profiles`, `artifacts`, `artifact_count`, `inputs` (sorted names of every
  file in `/app/data`), `input_count`, `corpus_count` and `aggregate_total`.
  `artifacts` lists the 22 delivered artifacts in this order: `config.json`,
  `report.json`, `tool.zip`, `aggregates.json`, `aggregates.csv`,
  `aggregates.tsv`, `aggregates.xml`, `aggregates.ini`, `aggregates.env`,
  `aggregates.md`, `aggregates.txt`, `validation_report.json`, `summary.json`,
  `profile_core.json`, `profile_edge.json`, `profile_dmz.json`,
  `profile_mgmt.json`, `rejected_ops.json`, `zone_totals.json`,
  `corpus_index.json`, `posture.json`, `manifest.sha256`.
- `report.json`: written by `export-report`, with `ok`, `tool`, `config_path`,
  `config_sha256` (the sha256 hex of the delivered `config.json` bytes),
  `trailer` and `commands` (one object per command run, each with `argv`,
  `returncode` and `stdout`). No timestamps or other volatile keys anywhere.
- `manifest.sha256`: for each delivered artifact except `tool.zip`,
  `report.json` and `manifest.sha256` itself, one line `<sha256>  <name>`,
  names in sorted order, two spaces between.
- `tool.zip`: the repaired tool itself, rebuilt deterministically.

## Hardening addendum (HARDENING_V2)

### Stateful replay

Replay `change_journal.jsonl` in ascending `seq` order. The spine state after
each op is the state used to validate the next op. The validity of a `set`
on `max_sessions` depends on the state of `rekey_interval_s` and
`handshake_timeout_ms` at that moment: a `set` on `max_sessions` is valid only
when its value does not exceed `floor(current(rekey_interval_s) /
current(handshake_timeout_ms))`.

### Touch op

In addition to `set` and `unset`, the journal carries `touch`. A `touch` is
valid iff its `value` is byte-equal to the current post-replay value for the
same key at that `seq`; otherwise it is rejected and counts toward J. A `touch`
never mutates the spine. For integer-typed keys, a `touch` whose `value` is a
JSON string of digits is rejected on type grounds (same rule as `set`). A
`touch` must also meet the `env` and `key` conditions above.

### Z shift

The effective upper bound used in corpus aggregation is
`hi + (R mod 97) + (J mod 31) + (Z mod 53)`, with Z = first 16 hex characters
of sha256(/app/out/tool.zip) parsed as a hex integer. The three moduli are
pairwise coprime so that an error anywhere in the pipeline (ZIP non-determinism,
op misclassification, miscounted rejection) moves the effective upper bound of
every corpus.

### Fixed-point profile trailer

Every zone profile written to `/app/out/profile_<zone>.json` carries
`trailer = <spine trailer>:<zone>:<first 8 hex of sha256(/app/out/config.json)>`.
This requires `/app/out/config.json` to be byte-frozen (serialized per
instruction 19) BEFORE any profile is written.

### CLI-driven derivation

`--data` defaults to `/app/data` and `--out` to `/app/out`. Inputs are read
from `<data>`; `R` and the trailer digest come from `<out>/config.json` and
`Z` from `<out>/tool.zip`.

- `sealb-ctl plan --data <dir> --out <dir> --env <env>` prints the resolved
  policy for `<env>` (`base` or a zone) in the JSON form above, byte-equal to
  the delivered `config.json` or `profile_<zone>.json`.
- `sealb-ctl compile --data <dir> --out <dir>` writes `aggregates.json`, the
  seven `aggregates.*` mirrors, `zone_totals.json` and `corpus_index.json`
  into `<out>`; the delivered copies are the files it writes.
- `sealb-ctl aggregate --corpus <name> --data <dir> --out <dir>` prints that
  corpus's derived integer and one newline.

Each of the fifty corpora is aggregated by invoking
`sealb-ctl aggregate --corpus <name>`. Its argv, returncode, and stdout are
captured into `/app/out/report.json`'s `commands` list alongside `init`, every
`set`, `validate`, and `export-report`.

### Byte-exact zone matching

Only the five ASCII byte-strings `core`, `edge`, `dmz`, `mgmt`, `svc` match a
zone slot. Rows carrying homoglyphs (U+0441, U+200B, U+00A0, U+FEFF) do not
match any zone, even when `str.strip()` or Unicode normalization make them
appear equal to an ASCII zone name. The `svc` zone is reserved and never
contributes to counted-row totals.
