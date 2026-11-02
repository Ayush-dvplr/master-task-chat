# DESIGN_SUMMARY 13a9939 data-product-config-compiler (cli-config, software-engineering, seed 724163)
Job: repair /app/data/tool.zip (stdlib compiler, 5 modules) per /app/data/config_contract.md, run `compile --date <manifest compile_date>` and `export-report`, deliver /app/out/{config,profile_dev,profile_prod,validation_report,summary,report}.json + tool.zip. Contract wins over README/comments (W8).
Inputs (flat, 13 data files, 10 formats, ~21k lines): contract md, base_layer.yaml, schema_registry.json, products.ini (600), owners.csv (~3.4k), deprecation.log (~3.4k), selectors.rules, team_overrides.json, product_overrides.jsonl (~9k), env_dev/env_prod.toml, cluster_quota.json, release_manifest.json (catalog = real L1 control, exit 3 on mismatch).
Chains: C1 log id -> canon -> status -> active set -> quota denominator -> every quota; C2 owners.csv + owner retire -> team -> team selectors/overrides -> settings -> profiles; C3 override JSON value -> type -> accept/reject -> weight -> quotas + report; C4 compile_date -> --date -> owner/event dates -> status.
Planted defects: 6 load-bearing (date wiring crash, TOML bool("false"), file order not seq, merge `if value:`, round() quota, unsorted emit) + 3 lever defects (owner_active ignores owner events; shared coerce() on JSON layers; log join without canon()).
Deviation: LV-CC-3 killed (premortem: [] row visibly broken, Opus fixes it); stays graded work. COUPLING = candidate quota share (all 3 levers reach its denominator).

| lever | habit | rule written in | hidden case | shipped separates? |
|---|---|---|---|---|
| LV-CC-1 | H3 | contract glossary "Active owner on date D" (interval AND no RETIRE owner on/before D) | 8-12 log-retired owners, 15-30 products under team selectors/overrides | no (no owner events shipped) |
| LV-CC-2 | H1/L5 | product_overrides.jsonl field block + Malformed overrides list (twice) | 15-25 quoted ints/bools both JSON layers, >=4 on weight | yes (~25 quoted rows, 3 on weight) |
| LV-CC-4 | H4/L10 | Identifiers section bare property; log block "product= names a product id" | 60% retire ids mixed-case/hyphenated, overrides naming them | no (log ids canonical; mixed ids only in overrides, tool right there) |
Why no shipped self-test separates LV-CC-1/4: the shipped log holds only canonical product events; no file states an active count; no worked example. Noise: text-layer quoted values (allowed), bool/30.0 easy rejects, team moves in owners.csv, events after D, NOTICE lines.

Tests (30, P=116, no test negatives): 11 row-owned families (status, team, settings_int, settings_other, config_quota, dev_deploy, dev_quota, prod_deploy, prod_quota, rejected_overrides, summary) visible w3 on /app/out + hidden `_hard` w5 running delivered tool.zip as nobody from /tmp on embedded-generator corpora; report_run w3; M1 date_shift, M2 quota_rescale, M3 shuffled+relocated w5; missing_input, catalog_mismatch, determinism w3; zip layout w1. Visible 31.0%, hidden/mutated 68.1%. CL-4: row ownership + G5 whole-document sentence in instruction.

| lever | alone % | all-but-this overall | one-fact-wrong tests score |
|---|---|---|---|
| LV-CC-1 | 56.0 (65/116) | 67.0 | 48-61% (one retired owner missed) |
| LV-CC-2 | 70.7 (82/116) | 59.7 | 75% (quoted retention_days) / 50% (quoted weight) |
| LV-CC-4 | 60.3 (70/116) | 64.8 | 40-44% (one mixed retire id missed) |

Judge (12, batched): R1-R6 J2 recompute (status+team, quotas x3 docs, rejected list, settings, profile deploy keys, summary) w3; R7 J9 altered-copy rerun w3; R8 J4 code quality on delivered tool w3; R9 J6 lists every changed tool file by path w1; R10 runs delivered zip from foreign cwd after last edit w3; R11 J3 honesty w-3; R12 grader-read w-5. solve.sh self-check prints `check R<n> ok`.
Files: WORK/PREMORTEM.md, DESIGN.md, QC_DEFENCE.md, TODO.md, LOG.md.
Risk: LV-CC-1 alone is the thinnest (56%); if the probe shows Opus audits owner_active(), raise hidden log-retired owners matched on weight (COUPLING), never weight > 5.
