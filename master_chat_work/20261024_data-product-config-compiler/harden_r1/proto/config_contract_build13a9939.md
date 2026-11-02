# Data product config compiler: contract

This file specifies the `dpcc` tool and every document it writes. All inputs live in one data folder (the shipped one
is /app/data). Where the tool's README, docstrings or comments disagree with this file, this file wins.

## Command line

- `python3 cli.py compile --data <folder> --date <YYYY-MM-DD> --out <folder>` compiles the release for the date D given
  by --date and writes config.json, profile_dev.json, profile_prod.json, validation_report.json and summary.json into the
  --out folder, creating the folder when it does not exist.
- `python3 cli.py export-report --out <folder>` writes report.json into that folder (see report.json below).
- For the shipped release, D is the `compile_date` of release_manifest.json.
- The tool uses only the Python standard library, reads its inputs without changing them and writes only inside the
  --out folder. It works from any working directory, from any folder it is unpacked into, on a data folder with any
  name, and on a data folder it may not write to.

Errors. On each of the following the tool prints exactly one line to standard error, writes no document and exits
with the stated code:

- a file of the Inputs list is missing from the data folder: `error: missing input <file name>`, exit code 2; when
  several are missing, the line names the first of them in the order of the Inputs list;
- --date is not a calendar date written YYYY-MM-DD: `error: invalid date <value as given>`, exit code 2;
- the set of product ids of products.ini differs from the `catalog` of release_manifest.json:
  `error: catalog mismatch <id>`, exit code 3, naming the smallest canonical id that is in one set and not in the other.

## Identifiers

Product ids are compared after converting them to upper case and removing every hyphen. This canonical form is the one
every output document writes. Owner names, team names, tiers, labels and setting keys are compared exactly as written.

## Dates

Dates are calendar dates written YYYY-MM-DD and compare in calendar order. A deprecation.log event is dated by the date
part (the first ten characters) of its timestamp.

## Glossary

- Active owner on date D: an owner who has an owners.csv row with active_from on or before D and active_to empty or on
  or after D, and who has no `RETIRE owner=<owner>` event in deprecation.log dated on or before D. Their team on D is
  the team of that row.
- Status of a catalog product on D: `retired` when deprecation.log has a `RETIRE product=<id>` event for it dated on or
  before D; otherwise `active` when its owner is an active owner on D; otherwise `orphaned`.
- Team of a product: for an active product, its owner's team on D; for an orphaned or a retired product, null.
- Compiled product: an active or an orphaned product. Retired products appear in config.json but are not compiled.

## Inputs

The data folder holds these twelve files, in this order.

1. `release_manifest.json`: an object with `release` (string), `compile_date` (date) and `catalog` (array of product
   ids).
2. `schema_registry.json`: an object with `keys`, mapping every setting key to its spec. `type` is one of `integer`
   (with inclusive `min` and `max`), `boolean`, `enum` (with `values`), `string` or `list` (a list of strings).
   `"optional": true` marks a key that a product may lack; every other key is required.
3. `base_layer.yaml`: one `key: value` line per setting, a value for every required key. Lines starting with `#` and
   blank lines are ignored. A text layer.
4. `products.ini`: one section `[product <id>]` per catalog product with the lines `owner = <owner>`,
   `tier = <tier>` and `labels = <label>, <label>, ...` (possibly empty), followed by zero or more
   `<setting key> = <value>` lines. Lines starting with `#` and blank lines are ignored. Its setting lines are a text
   layer.
5. `owners.csv`: header `owner,team,active_from,active_to`; one row per assignment of an owner to a team. An empty
   active_to means the assignment is open. The rows of one owner never overlap.
6. `deprecation.log`: one event per line, `<timestamp> <KIND> <field>=<value> ...`. Two kinds of event count:
   `RETIRE product=<product id>` retires a product and `RETIRE owner=<owner>` retires an owner. Every other line
   (NOTICE, INFO and so on) is ignored. The file is not in time order.
7. `selectors.rules`: one rule per line, `match <field>:<name> set <setting key> <value>`, where field is `team`,
   `tier` or `label` and value is the rest of the line. Lines starting with `#` and blank lines are ignored. A text
   layer.
8. `team_overrides.json`: an object mapping a team name to an object of `<setting key>: <JSON value>` entries. A JSON
   layer. A team that no product has on D simply matches no product.
9. `product_overrides.jsonl`: one JSON object per line with `seq` (integer, unique in the file), `product` (product id),
   `key` (setting key), `value` and `ticket` (string, informational). A JSON layer. The value is a JSON value of the
   key's schema type: a JSON number without fraction or exponent for an integer key, true or false for a boolean key, a
   JSON string for an enum or string key, an array of strings for a list key, and null only for an optional key.
10. `env_dev.toml`: sections `[defaults]` and `[tier.<tier>]` with `<setting key> = <value>` lines. Lines starting with
    `#` and blank lines are ignored. A text layer, used for profile_dev.json only.
11. `env_prod.toml`: as env_dev.toml, used for profile_prod.json only.
12. `cluster_quota.json`: an object with the integer quotas `shared`, `dev` and `prod`.

## Settings

### Text layers

base_layer.yaml, the setting lines of products.ini, selectors.rules and the env files are text layers. A value written
inside one pair of double quotes is read without the quotes, so a quoted value and a bare value read alike. The text is
then read by the schema type of its key: integer as decimal digits; boolean as `true` or `false` in any letter case;
enum and string as written; list as items separated by commas, each item trimmed of surrounding spaces, with empty text
giving the empty list. Every text-layer value names a schema key and is valid for it, so text layers never reject.

### JSON layers

team_overrides.json and product_overrides.jsonl are JSON layers. A JSON-layer value keeps its JSON type and is never
converted: it is accepted only when it has the type stated for the key in the product_overrides.jsonl block of the
Inputs list. An accepted value must also lie within the key's `min` and `max`, or be one of its enum `values`.

### Malformed overrides

A JSON-layer entry is rejected, not applied anywhere, and listed in validation_report.json with the first reason that
applies, in this order:

1. `unknown_product` (product_overrides.jsonl only): the canonical product id is not a compiled product, that is, it is
   not in the catalog or the product is retired on D;
2. `unknown_key`: the key is not in schema_registry.json;
3. `type`: the value does not have the key's type, which includes a JSON string for an integer or boolean key, whatever
   text it holds; a JSON boolean for an integer key; a number with a fraction or exponent; and null for a key that is
   not optional;
4. `bounds`: an integer outside `min` and `max`, or an enum value outside `values`.

### Precedence

The settings of a compiled product in config.json are built by applying these layers in order, later layers winning:

1. base_layer.yaml;
2. selectors.rules, rule by rule in file order, each rule applying to every compiled product it matches: `team:<name>`
   matches the products whose team is that name, `tier:<name>` those of that tier, `label:<name>` those whose labels
   include that name;
3. the accepted entries of team_overrides.json for the product's team;
4. the setting lines of the product's products.ini section;
5. the accepted product_overrides.jsonl entries for the product, in ascending seq.

The settings of a product in a profile document are built the same way, with the env file's `[defaults]` section and
then its `[tier.<tier of the product>]` section applied right after base_layer.yaml.

### Merging

When a layer gives a value for a key, a null value removes the key from the settings and any other value, the empty
list included, replaces the current value; a key the layer does not mention keeps its current value.

## Quota

config.json hands out the `shared` quota of cluster_quota.json, profile_dev.json the `dev` quota and profile_prod.json
the `prod` quota. In each document, with Q the quota and W the sum of the resolved `weight` over all active products in
that document, an active product with weight w first gets the integer part of Q x w / W; the units left over then go
one each to the active products in descending order of the remainder of Q x w divided by W, products with equal
remainders in ascending product id order. Orphaned and retired products get quota 0 in config.json.

## Output documents

Every output document is JSON with keys sorted, two-space indentation, ASCII escapes for any other character and one
trailing newline, which is Python's `json.dumps(document, indent=2, sort_keys=True) + "\n"`.

### config.json

`release` and `compile_date` (D) as strings, `cluster_quota` (the shared quota) and `products`, an object with one entry
per catalog product keyed by canonical id: `status`; `owner` and `tier` as written in products.ini; `team`; `settings`,
the object of resolved settings (a key removed by a null is absent), or null for a retired product; and `quota`.

### profile_dev.json and profile_prod.json

`env` (`dev` or `prod`), `release`, `compile_date`, `cluster_quota` (the env quota) and `products`, an object with one
entry per active product keyed by canonical id: `alerts_enabled`, `pii_scan` and `replicas` from the profile settings,
and `quota`.

### validation_report.json

`release` and `rejected_overrides`, an array with one entry per rejected JSON-layer entry. A team_overrides.json entry
is `{"source": "team_overrides", "team": <team>, "key": <key>, "reason": <reason>}`; a product_overrides.jsonl entry is
`{"source": "product_overrides", "seq": <seq>, "product": <canonical id>, "key": <key>, "reason": <reason>}`. Team
entries come first, ordered by team and then key; product entries follow in ascending seq.

### summary.json

`release`, `compile_date`, `status_counts` (`active`, `orphaned`, `retired`: counts of catalog products),
`active_by_team` (team to its number of active products, for every team with at least one), `rejected_overrides`
(`team_overrides` and `product_overrides`: counts of rejected entries) and `quota_total` (`config`, `dev`, `prod`: the
sum of the quota values in that document).

### report.json

`tool` (`"dpcc"`), `documents`, mapping each of the five compile documents to the sha256 hex digest of its bytes in the
--out folder, or null when it is missing, and `ok`, true when all five are present. export-report exits 0 when ok is
true and 1 otherwise.
