# DESIGN: data-product-config-compiler (board 13a9939)

Archetype cli-config, category software-engineering, seed 724163. Scoring levers LV-CC-1, LV-CC-2, LV-CC-4. LV-CC-3 is
graded load-bearing work, not a scoring lever (PREMORTEM kill-fallback).

## Deviations from IDEA.md (recorded)
1. LV-CC-3 removed from the scoring set (IDEA kill-fallback; PREMORTEM: first-write program gets it right).
2. COUPLING kept as the candidate quantity (quota share). No stronger quantity is needed: the denominator is taken over
   the active set (moved by LV-CC-1 and LV-CC-4) and over resolved weights (moved by LV-CC-2), so every lever reaches every
   quota row of three documents (config.json, profile_dev.json, profile_prod.json).
3. CL-4: both mechanisms. Tests own rows by family (one family = one field group), and instruction.md carries the G5
   whole-document sentence ("each output document must match the contract whole and exactly, on these files and on fresh
   data at other scales"), which is the CL-4 exemption. One-fact-wrong scores are reported below anyway.

## Job
Extract `/app/data/tool.zip` to `/app/tool`, repair it so it does what `/app/data/config_contract.md` says, run
`python3 cli.py compile --data /app/data --date <release_manifest compile_date> --out /app/out` and
`python3 cli.py export-report --out /app/out`, deliver `/app/out/tool.zip` (cli.py at archive root). Outputs:
/app/out/config.json, profile_dev.json, profile_prod.json, validation_report.json, summary.json, report.json, tool.zip.
Arbiter sentence (W8): where the tool's README or code comments disagree with config_contract.md, the contract wins.

## Spine stages
S1 load every input; canonicalise product ids (upper case, hyphens removed) at every comparison.
S2 catalog control: products.ini ids must equal release_manifest.json `catalog` (L1 green control, real, exit 3 on mismatch).
S3 status at D: retired (a `RETIRE product=` event dated on or before D), else active (owner active on D), else orphaned.
S4 team: owner's team on D for active products; null for orphaned and retired.
S5 settings: base_layer -> selectors.rules (file order) -> team_overrides.json (products whose team is that team) ->
   products.ini setting lines -> product_overrides.jsonl (ascending seq). Text layers read per schema type; JSON layers
   strict; rejected overrides are not applied and are reported. Retired products: settings null.
S6 profiles: same chain with env_<env>.toml `[defaults]` then `[tier.<tier>]` inserted right after base_layer.
S7 quota (COUPLING) per document: cluster quota x weight / sum of weights over active products, floor, largest remainder,
   ties by product id ascending; orphaned and retired get 0 (config.json) or are absent (profiles list active only).
S8 emit five compile documents (2-space indent, keys sorted, trailing newline); S9 export-report; S10 package tool.zip.

## Input files (flat, 13 data files + tool.zip; 10 formats; about 21,000 lines)
| file | format | rows | depends on | notes |
| config_contract.md | md | ~250 | all | every graded rule, output key, error string |
| base_layer.yaml | yaml (flat key: value) | ~25 | schema | a value for every required key; quoted and bare scalars |
| schema_registry.json | json | ~90 | - | 11 keys: weight int[1,100], retention_days int[1,3650], replicas int[1,7], partitions int[1,256], freshness_sla_min int[5,1440], pii_scan bool, alerts_enabled bool, encryption enum none/kms/hsm, notify list, tags list, cost_center string optional |
| products.ini | ini | ~4,300 (600 products) | owners, schema | `[product DP40217]` owner, tier bronze/silver/gold, labels, optional setting lines (text layer) |
| owners.csv | csv | ~3,400 | - | owner,team,active_from,active_to; non-overlapping rows per owner; empty active_to = open; team moves ship |
| deprecation.log | log | ~3,400 | products, owners | `<iso ts> RETIRE product=<id> ticket=..`, `<iso ts> RETIRE owner=<owner> ticket=..`, NOTICE/INFO noise; shipped: product events only, canonical ids, some dated after D |
| selectors.rules | rules DSL | ~70 | owners (team), ini (tier, labels) | `match team:<t>|tier:<t>|label:<l> set <key> <value>`; text layer; later line wins |
| team_overrides.json | json | ~300 | owners | team -> {key: JSON value}; strict; null, [] and quoted ints ship |
| product_overrides.jsonl | jsonl | ~9,000 | ini, log, schema | seq, product, key, value, ticket; strict; lines not in seq order; mixed-case ids ship; quoted ints/bools ship |
| env_dev.toml, env_prod.toml | toml | ~40 each | schema, ini tier | `[defaults]`, `[tier.gold]` ...; text layer; quoted and bare read alike (decoy) |
| cluster_quota.json | json | 5 | - | {"shared":N, "dev":N, "prod":N} |
| release_manifest.json | json | ~610 | ini | release, compile_date, catalog (600 ids) |
| tool.zip | zip | ~600 lines py+md | all | cli.py, loaders.py, resolve.py, quota.py, emit.py, README.md |

Chains (length >= 4):
C1 deprecation.log id -> canonical form -> catalog product -> status -> active set -> quota denominator -> every quota row.
C2 owners.csv interval + `RETIRE owner=` -> owner active on D -> product team -> team selectors / team overrides -> settings -> profile replicas -> quota.
C3 product_overrides value -> schema type -> accept or reject -> resolved weight -> denominator -> every quota; and -> validation_report -> summary.
C4 release_manifest compile_date -> --date -> owner interval and event dates -> status -> summary counts.

## Planted defects in the shipped tool (each breaks one contract sentence)
Load-bearing (shipped data shows them): P1 `compile` passes `args.date` to a parameter named `when` (crash); P2 TOML reader
`bool(text)` makes "false" true; P3 product overrides applied in file order, not ascending seq; P4 merge `if value:` drops
`[]` and turns null into "keep" (LV-CC-3 work); P5 quota uses `round()` (sum differs; `cli.py validate` reports it);
P6 emit without sort_keys/indent. Lever defects (shipped data does not show them): L1 `owner_active()` ignores owner
events, deprecation loader keeps product events only; L2 shared `coerce()` applied to both JSON layers; L4 deprecation
loader stores raw ids while canon() is applied in ini, manifest and override loaders.

## Levers
### LV-CC-1 (H3, denominator and selector scope): active owner
- Rule (glossary of config_contract.md, W3 form "definition with branch, no warning"): "Active owner on date D: an owner
  who has an owners.csv row with active_from on or before D and active_to empty or on or after D, and who has no
  `RETIRE owner=<owner>` event in deprecation.log dated on or before D. Their team on D is that row's team." Product status
  and team are defined next to it; selectors and team overrides use "products whose team is <name>". deprecation.log
  format block lists both event kinds.
- Reflex reading: CSV interval only (the tool's `owner_active()`), owner events ignored.
- Hidden cases: 8-12 owners retired in the log with open CSV rows, owning 15-30 products; at least 6 matched by team
  selectors on weight or replicas, at least 4 by team overrides; owner events dated after D (must not count) in M1.
- Why visible data cannot confirm (W5/W6): shipped log has no owner events; no control states an active count; no worked
  example. Every self-test in PREMORTEM agrees with the tool.
- Interactions: feeds status (with LV-CC-4, retired wins), team, settings, profiles membership, quota denominator.

### LV-CC-2 (H1/L5, strict JSON types beside lenient text layers)
- Rule, stated twice: product_overrides.jsonl field block ("value: a JSON value of the key's schema type: a JSON number
  without fraction or exponent for an integer key, true or false for a boolean key, a JSON string for a string or enum
  key, an array of strings for a list key; null only for an optional key") and the Malformed overrides list ("a JSON
  string for an integer or boolean key, whatever text it holds; a JSON boolean for an integer key; a number with a
  fraction or exponent; null for a key that is not optional" -> reason `type`). team_overrides.json block points to the
  same typing. Text layers section: quoted and bare values read alike per schema type (the allowed coercion, decoy).
- Reflex reading: keep `coerce()` for JSON layers (lenient parse), or fix product overrides only.
- Hidden cases: 15-25 quoted ints/bools across both JSON layers, at least 4 on weight of active products; bool-for-int and
  30.0 decoys (easy rejects); `" 30 "` never produced (IN-16 open case avoided by the generator).
- Shipped: separating rows ship (L5): ~25 quoted, at least 3 on weight, 2 on replicas, 2 on alerts_enabled / pii_scan.
- Interactions: weight -> denominator -> every quota; rejected list; summary rejected count.

### LV-CC-4 (H4/L10, general id rule in the rarely joined field)
- Rule (Identifiers section, W3 form "bare property, no example"): "Product ids are compared after converting them to
  upper case and removing every hyphen. Output documents write the canonical form." deprecation.log block: "product=
  names a product id".
- Reflex reading: canon() is applied wherever the tool already applies it; the log join is left raw.
- Hidden cases: 60 percent of retire ids mixed-case or hyphenated (`dp-40217`, `Dp4-0217`); 3-6 product overrides naming
  such products (must be rejected `unknown_product`).
- Why visible cannot confirm: every shipped log id is canonical; mixed ids ship only in overrides, where the tool is right.
- Interactions: status, team, settings null, rejected list, denominator.

### Graded non-lever work
Merge table (absent inherits, null deletes an optional key, [] replaces), precedence, ascending seq, TOML booleans,
largest remainder with tie order, formatting, errors, report.json, packaging.

## Rejection paths
Overrides: `type`, `bounds` (outside min/max or not in enum), `unknown_key`, `unknown_product` (not in catalog, or
retired). Rejected rows are listed in validation_report.json `rejected_overrides` (team rows first by team then key, then
product rows by ascending seq) with source, team or seq+product, key, reason. CLI: missing input file -> exit 2
`error: missing input <name>`; bad --date -> exit 2 `error: invalid date <value>`; catalog mismatch -> exit 3
`error: catalog mismatch <id>` (first differing id in sorted order).

## Test plan (tests/test_output.py; 30 checks; positive total P = 116; no negatives in tests)
Visible tier reads the agent's /app/out documents and compares with a reference computed from the embedded shipped data.
Hidden tier runs the delivered /app/out/tool.zip (extracted to a temp dir, uid nobody, cwd /tmp, data in a renamed temp
dir) on corpora built by an embedded seeded generator (seed in tests/ only; new release name and compile date per corpus;
G12 asserts every drawn value inside schema bounds; asserts at least one largest-remainder tie straddles the cut per doc).
| family (rows owned) | visible w3 | hidden `_hard` w5 |
| catalog_status: status per product | V1 | H1 |
| team: team per product | V2 | H2 |
| settings_int: weight, retention_days, replicas, partitions, freshness_sla_min | V3 | H3 |
| settings_other: pii_scan, alerts_enabled, encryption, notify, tags, cost_center | V4 | H4 |
| config_quota: quota per product in config.json | V5 | H5 |
| dev_deploy: alerts_enabled, pii_scan, replicas per product in profile_dev | V6 | H6 |
| dev_quota | V7 | H7 |
| prod_deploy | V8 | H8 |
| prod_quota | V9 | H9 |
| rejected_overrides | V10 | H10 |
| summary | V11 | H11 |
Plus V12 report_run w3 (report.json ok, argv, config_sha256 equals the delivered config.json), M1 date_shift_hard w5
(status+team at a second date), M2 quota_rescale_hard w5 (new cluster quotas; quota rows of three docs), M3
shuffled_relocated_hard w5 (override lines shuffled, data dir renamed; settings_int rows), R1 missing_input w3, R2
catalog_mismatch w3, R3 determinism w3 (two hidden runs byte-identical), Z1 tool_zip_layout w1.
Shares: visible 36/116 = 31.0%; hidden + mutated + robustness 79/116 = 68.1% (G3 >= 30%); existence 1/116.
Every assertion message gives the first differing path. Each hidden run is cached per corpus inside the test module; no
check uses the agent's earlier output as input (TS-26). G6: M2, M3 (stock recipes rescale and shuffle+relocate), plus M1.

## Predicted cost table (G10; all-but-one overall = 0.5 x tests + 0.5 x 0.90)
| lever | checks lost alone | points | alone % | all-but-this overall |
| LV-CC-1 | H1-H9, H11, M1-M3 | 65 | 56.0 | 67.0 |
| LV-CC-2 | V3-V11, H3-H11, M2, M3 | 82 | 70.7 | 59.7 |
| LV-CC-4 | H1-H11, M1-M3 | 70 | 60.3 | 64.8 |
One-fact-wrong (single wrong input fact, tests score): LV-CC-1 one retired owner missed 48-61%; LV-CC-2 one quoted
retention_days accepted 75%, one quoted weight accepted 50%; LV-CC-4 one mixed retire id missed 40-44%. The size comes
from COUPLING (G1 amplification through a stated single-reading rule) and the G5 whole-document sentence covers CL-4.

## Expected loss per lever (for the probe's loss.py)
LV-CC-1: hidden corpus H, log-retired owners -> H1, H2, H3, H5-H9, H11, M1, M2, M3. LV-CC-2: shipped quoted weight and
replicas rows -> V3-V11, and hidden quoted rows -> H3-H11, M2, M3. LV-CC-4: hidden mixed retire ids -> H1-H11, M1-M3.

## Judge plan (tests/judge.toml, batched, 12 criteria; positive 28, negative -8)
R1 recompute status and team for every product outside the tool and compare (w3, J2); R2 recompute quota for every
product in each of the three documents (w3, J2); R3 recompute the rejected override list (w3, J2); R4 recompute resolved
settings for every product (w3, J2); R5 recompute profile deploy keys for every product in both profiles (w3, J2); R6
recompute summary counts (w3, J2); R7 runs the tool on a copy of the data whose contents it altered and checks that the
dependent figures move (w3, J9); R8 code quality on /app/out/tool.zip functions (no bare or pass-only except, no function
over about 150 lines, no unreachable or unused function or branch) (w3, J4); R9 the response lists every tool file it
changed, each by its path (w1, J6); R10 runs the delivered /app/out/tool.zip from a directory other than /app/tool after
its last edit (w3); R11 honesty negative (w-3, J3); R12 grader-read negative (w-5). solve.sh self-check prints
`check R<n> ok` for R1-R7 and R10. No criterion restates an output figure (J1) or penalises writing in /app/data (JD-11).

## As built: hidden input and check where a careful solver loses (Phase 8)
The built test file supersedes the plan above: 34 checks, P = 125 (adds invalid_date, readonly_inputs, document_format
w3; negative_hardcoded_sample_answers -5). Hidden corpus = gen_corpus(318907, 420-520 products, hidden) at a 2027-2029
compile date, run by the delivered tool.zip as nobody from a foreign cwd on a renamed folder.
- LV-CC-1: a careful solver reads owners.csv intervals, sees no `RETIRE owner=` line in the shipped log and keeps the
  CSV-only owner check. Hidden input: 10 log-retired owners from teams with weight selectors (2-3 products each) plus 3
  retired between D and D+45. Loses catalog_status_hard, team_hard, settings_*_hard, *_quota_hard, *_deploy_hard,
  summary_hard, date_shift, quota_rescale, shuffled_relocated, readonly_inputs (68/125 measured).
- LV-CC-2: a careful solver keeps the shared coerce() for JSON layers because quoted values in env files are legal.
  Hidden and shipped input: quoted weight/retention/replicas/bools, booleans for integers, 30.0 and 1e2. Loses every
  settings, quota, deploy, rejected_overrides and summary family plus quota_rescale, shuffled_relocated, readonly_inputs
  (85/125 measured).
- LV-CC-4: a careful solver sees canonical ids everywhere in the shipped log and joins raw. Hidden input: about 60% of
  `RETIRE product=` ids in mixed case or hyphenated. Loses all 11 `_hard` families plus date_shift, quota_rescale,
  shuffled_relocated, readonly_inputs (73/125 measured).

## Harden round 1 (e317de1, 25 Oct 2026)
Probe 1 (Opus): tests 125/125, judge 25/28, overall 94.65; fuzz 0% differing on every build lever (REVEALING). The build
levers stay as background rules; three new counted levers replace them (OUT harden_r1/DIAGNOSIS.md):
- NL-1 (H3 defined term): "Assignment of an owner on date D" = the owner's row with the latest active_from on or before D
  (contract :38-42; owners.csv :63-65 rows may overlap, distinct active_from). Reflex: first or last covering row.
  Hidden: 14 planted owners, later row before/after the old row in file order, equal-weight teams (no quota cliff), some
  ended between D and D+45 (shifted tier). Alone 31.7%, one-fact (latest covering) 4.2%.
- NL-3 (H7 re-entry): optional `quota_cap`; capped units given back are handed out again by largest remainder among the
  products below their cap; holders keep units; untakeable units stay unassigned (:140-145). Reflex: restart water-fill.
  Shipped caps bind in round one only (restart = additive); hidden 10% caps, env tier cap, capped tier (3 rows w5),
  rescaled tier with an env_prod default cap. Alone 31.7%, one-fact (two rounds) 27.5%.
- NL-4 (H1 bare property): text integers only digits 0-9, booleans only true/false any case; other text is passed over
  and the key keeps the earlier value (:87-93). Reflex: int()/bool-word reading. Shipped ASCII `+N` and word plants;
  hidden fullwidth digits. Alone 59.2%, one-fact (isdigit) 20.8%.
- LV-ENUM: the reason-3 enumeration removed (:109).
- Tests: status_team merges catalog_status and team; 10 families x (w3 + w5), date_shift 5, quota_rescale 5,
  shuffled 5, three capped rows 5, readonly 3, six generic rows and layout w1: 35 checks, P = 120, negative -5.
- Judge: R1-R6 on shipped data and an altered copy (J2), R8 J4 text, new w3 R13-R15; 15 criteria, positive 37.
- Gates: oracle 120/120, nop 0, probe agent program 21/120 = 0.175 (reflex gate <= 0.20); fuzz r3 probe differs 96.6%.
- Forgery: Docker r1 scored 0.2667 (copied docs pass the visible rows). `_load` now requires each /app/out document to
  equal what the delivered tool writes for the shipped release; forgery then scores 2/120 locally.

## Lessons for the master
Row-owned families plus a COUPLING quota make one-fact-wrong large; the G5 sentence is what keeps CL-4 safe | no change: prompt already allows both
