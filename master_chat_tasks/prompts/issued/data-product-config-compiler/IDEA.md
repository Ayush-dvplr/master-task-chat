# IDEA: data-product-config-compiler (cli-config)

- SOURCE: master_chat_tasks/registry/ideas.jsonl idea 3 "Data Product Configuration Compiler" (batch 20261021_data-processing, HOLD backup, never built). Pilot card /Users/Shared/md_pilot/workspace/master_chat_tasks/pilot/IDEA_1_config_compiler.md adapted to the cli-config scaffold.
- ARCHETYPE: cli-config. Fixed artifacts: /app/out/config.json, report.json, tool.zip, profile_dev.json, profile_prod.json, validation_report.json, summary.json.
- CATEGORY: software-engineering.

## Premise
A data platform team ships a small stdlib-only CLI (`/app/data/tool/`, zipped as tool.zip on delivery) that compiles layered configuration for about 40 data products: a base layer, environment overlays (dev, prod), team overrides, per-product settings, and a selector rule file. The tool has planted defects; each defect breaks one stated sentence of the one contract file `/app/data/config_contract.md` (W10, the scaffold's contract name). The agent repairs the tool, runs it, and delivers the compiled config, the two environment profiles, the validation report of rejected overrides, a command report and a summary. Hidden tests run the delivered tool.zip on fresh corpora (relocated, renamed, shuffled, run as nobody from a foreign cwd).

## Inputs (>= 10 files, >= 5 formats)
base layer (YAML-like flat text or JSON), env overlays (TOML-like ini), team overrides (JSON), per-product INI, selector rules (line DSL), product owners CSV (owner, team, active_from, active_to), deprecation log (log lines retiring owners and products), schema registry JSON (field types), cluster quota JSON, honest control file of expected product ids (no figures), the contract.

## Levers (each a stated single-reading rule; G10 each alone >= 25% of test points)
- LV-CC-1 (H3 scope): a selector such as `team:ingest` applies only to products whose owner row is active on the compile date given on the command line; the deprecation log retires owners. Opus habit: apply the selector to every product listed under the team.
- LV-CC-2 (H1 strict type): an override keeps its source JSON type; a quoted "30" for an integer field is a rejected override written to validation_report.json, never coerced. Easy decoys: fields where the contract explicitly allows string-to-boolean coercion in env overlays. Shipped data carries separating rows.
- LV-CC-3 (H6 / merge semantics): absent key inherits, explicit null deletes the inherited key, empty list replaces the inherited list; one contract table. Risk: well-known idiom, may leak (ideas verdict). This is the kill-fallback candidate: if the pre-mortem says Opus gets it right, swap to H4 below as the third scoring lever and keep this as noise.
- LV-CC-4 (H4 normalisation in a rarely joined field): product ids compare upper-cased with hyphens removed only when joining the deprecation log; shipped log canonical, hidden logs mixed-case and hyphenated.

## COUPLING (candidate; the build may pick a better one and say why)
Each product's quota share = cluster quota x its resolved `weight` / sum of resolved weights over all active, compiled products, integer largest-remainder (ties by product id). One wrong merge, scope or rejected-override decision moves the sum, so every product's quota moves. Stated in one contract sentence.

## Tests and judge
Owned-row tests per lever family, visible w3 then hidden `_hard` w5, 30-50 tests, no whole-document per tier; mutation tests from G6 stock; missing-input, determinism, run-as-nobody probes. Judge: recompute conduct per output family (solve.sh self-check prints `check <id> ok`), J9 altered-copy rerun, one concrete code-quality criterion on the edited functions, J6 path listing, J3 honesty negative, grader-read negative.
