# PREMORTEM: data-product-config-compiler (board 13a9939)

Written 2026-10-24 IST before any other WORK file. Subject: claude-opus-5 on its first pass.

## Task as the agent meets it
`/app/data/` holds the contract `config_contract.md`, 13 data files (base_layer.yaml, schema_registry.json, products.ini,
owners.csv, deprecation.log, selectors.rules, team_overrides.json, product_overrides.jsonl, env_dev.toml, env_prod.toml,
cluster_quota.json, release_manifest.json) and `tool.zip` (the shipped compiler: cli.py, loaders.py, resolve.py, quota.py,
emit.py, README.md). The instruction says: repair the tool so it does what the contract says, run it on /app/data with the
manifest's compile date, write the seven /app/out documents, deliver /app/out/tool.zip; it will also be run on fresh data.

## First 10 minutes (predicted, step by step)
1. Reads instruction.md, then `ls -la /app/data`, then config_contract.md top to bottom (about 250 lines, read once).
2. Unzips tool.zip to /app/tool, reads README.md, then cli.py, then skims loaders.py / resolve.py / quota.py / emit.py.
3. Runs `python3 cli.py compile --data /app/data --date <compile_date> --out /app/out`. Crash on the `--date` wiring (P1).
   Fixes it in one edit. Reruns: outputs appear.
4. Runs `python3 cli.py validate` (the tool has it): quota sums differ from cluster quota (P5, round()). Rewrites the
   allocation as largest remainder with the stated tie order. Correct on first write (Opus knows Hamilton allocation).
5. Spot-checks outputs against the data files it has open: sees `alerts_enabled` true in profile_dev where env_dev.toml says
   `false` (P2, `bool(text)`); fixes the TOML reader. Notices a product whose `tags` override is `[]` keeps the base tags
   (P4, `if value:`), fixes the merge, reads the merge table in the contract (absent inherits / null deletes / [] replaces).
   Sees two overrides for the same key resolved by file order, reads "ascending seq", fixes P3. Sees unsorted keys (P6).
6. Self-tests it writes: (a) rerun and diff twice (determinism); (b) assert sum of quotas == cluster quota per document;
   (c) a 3-product toy for the allocation; (d) count products by status and compare with the manifest catalog length;
   (e) grep a handful of product ids across files and confirm their settings by hand; (f) runs the zipped tool from /tmp.
7. Declares done once every visible symptom is gone. Its fixes follow symptoms on the shipped corpus; it audits a contract
   sentence against code only where the shipped output looked wrong or where the code is visibly odd.

## Its reading of every rule (first write)
| rule | Opus reading | right? |
| merge table (LV-CC-3) | exactly as written; the `[]` row ships and shows P4 | right (so LV-CC-3 is killed, see below) |
| precedence chain | as written | right |
| text-layer reading (quoted and bare alike) | as written; tool already does it | right (decoy) |
| JSON-layer strict typing (LV-CC-2) | keeps the tool's shared `coerce()`; reads "integer key" as "value that is an integer", so `"30"` -> 30 | WRONG |
| largest remainder + tie by id | as written | right |
| active owner on D (LV-CC-1) | CSV interval only; the tool's `owner_active()` already does that and every shipped owner event is a product event | WRONG |
| status retired/active/orphaned | as written, on top of its owner reading | right given input |
| product id canonical form (LV-CC-4) | sees `canon()` used in the ini, manifest and override loaders; assumes the loaders are uniform | WRONG |
| error strings / exit codes | copied from contract | right |

## Per lever: where the first-write program goes wrong, and why no self-test catches it
**LV-CC-1 (H3, scope of "active").** The selector and team-override scope is "products whose owner is active on D". The
contract glossary defines an active owner with two clauses: an owners.csv interval covering D, and no `RETIRE owner=`
event dated on or before D. The tool's `owner_active()` implements clause one correctly, and the deprecation loader keeps
only `product=` events. On shipped data no owner event exists, so every output is identical under both readings. Opus never
edits `owner_active()` because nothing it ran pointed there; self-tests (a)-(f) all agree with the tool. Hidden corpora
retire 8 to 12 owners in the log (owners.csv still open), owning 15 to 30 products that team selectors and team overrides
match: those products must be orphaned (team null, no team settings, quota 0, absent from profiles), which moves the active
set, the weight denominator, and so every quota in three documents.

**LV-CC-2 (H1/L5, strict JSON types).** The tool routes every layer through one `coerce(value, kind)` that turns `"30"` into
30, `"true"` into True and passes `True` for an integer key (`isinstance(True, int)`). The contract allows exactly that for
text layers (decoy: Opus checks it, finds it right) and forbids it for JSON layers, stating the rule twice (the
product_overrides field block and the malformed-override list). Separating rows ship: 20 to 30 quoted integers and booleans,
some on `weight`. Opus's self-tests cannot tell: no output document is wrong-looking, quota sums still match, and the
coerced values are in bounds. Its habit (H1) is that a lenient parse is a feature. Hidden corpora carry more of them,
including `weight`, which moves the denominator. The careless half of the fix (only product overrides, not
team_overrides.json, both of which call `coerce()`) is a second, independent loss inside the same lever.

**LV-CC-4 (H4/L10, canonical ids in the rarely joined field).** The Identifiers section states one general rule: product ids
are compared after upper-casing and removing every hyphen. The tool applies `canon()` in the ini, manifest and override
loaders (shipped overrides carry lower-case and hyphenated ids, so the rule is visibly in use and visibly working), but the
deprecation loader adds the raw `product=` text. Every shipped log id is already canonical, so nothing differs. Opus checks
canon() where it saw mixed ids and moves on. Hidden logs write 60 percent of retire ids mixed-case or hyphenated: those
products must be retired (settings null, quota 0, overrides naming them rejected `unknown_product`); under the tool's join
they stay active, which moves status, rejected list, denominator and every quota.

## LV-CC-3 verdict: killed as a scoring lever (IDEA kill-fallback applied)
The merge table is three short rows in a table, the shipped `[]` override visibly fails, and the P4 bug sits in the one
central merge function Opus reads in step 5. Its first-write program gets it right with high probability (about 70
percent). Per IDEA.md the scoring set becomes LV-CC-1, LV-CC-2, LV-CC-4; LV-CC-3 stays as graded load-bearing work
(settings_other rows) and is not counted in the cost table.

## Redesign applied before Phase 1
- Scoring set swapped as above (recorded in DESIGN.md "Deviations").
- LV-CC-1 strengthened through COUPLING (orphans drop out of the quota denominator) and through hidden owners whose
  products are matched by team selectors on weight and replicas, never by weight above 5.
- LV-CC-4 strengthened by hidden product overrides that name log-retired products with mixed ids (rejected list).

## Lessons for the master
Kill-fallback taken at premortem: a merge table that is visibly broken on shipped data is load-bearing, not a lever | no change: IDEA already names the fallback
