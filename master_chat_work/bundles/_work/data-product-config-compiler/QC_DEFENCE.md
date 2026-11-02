# QC_DEFENCE 13a9939 + harden r1 (e317de1) data-product-config-compiler

One entry per lever and per cascade. Rule texts from checks.json; PASS precedents from QC_RULINGS.md; fallbacks are
QC_FIX_PLAYBOOK_v2 rows, DO column only, written out for this bundle (file, change).
Harden r1: NL-1, NL-3, NL-4 are the counted levers; LV-CC-1/2/4 stay as background rules (entries below, updated).
Line numbers are BUNDLE/environment/data/config_contract.md after harden r1.

## NL-1 assignment of an owner on D = latest-started row (H3 defined term)
- Rules touched: IN-15, IN-16, AL-27, TS-19, CL-4, DS (owners.csv format).
- IN-15 "every graded rule of engagement is stated plainly enough to act on": glossary :38-39 "Assignment of an owner on
  date D: of the owner's owners.csv rows with active_from on or before D, the one with the latest active_from."; :40-42
  active owner and "Their team on D is the team of their assignment on D."; owners.csv :63-65 "An owner may have several
  rows; no two rows of one owner share an active_from." (so "latest" is always one row). Instruction delegates every rule
  to the contract (PASS precedent district-heat v3:119, cohort v2:119).
- IN-16 "one reading": the defined term picks one row by a total order (distinct active_from), then one test on that row's
  active_to. No other sentence names a covering row. PASS precedent cohort v2:120 (definition with a branch is one reading).
- AL-27 fixture: hidden corpora plant 14 owners with a later-started row (other team; open, ended between D and D+45, or
  after); none in shipped data (W5). Generator asserts reflexes first/last covering row change config.json and
  latest_covering changes the shifted tier.
- TS-19: planted rows keep distinct active_from, dates inside [old start + 1, D], teams from the stated team set.
- CL-4: team plants use teams of equal weight, so a wrong team moves team, settings, deploy and summary rows, never quota
  (alone 31.7%, one-fact 4.2%; COST_TABLE.md).
- Fallback: playbook IN-16 DO: add one settling clause to the glossary entry ("rows that started earlier do not count,
  even when they still cover D"), no example. Playbook AL-27 DO: raise the number of hidden planted owners in gen_core.

## NL-3 quota_cap with re-share of given-back units (H7 re-entry)
- Rules touched: IN-15, IN-16, AL-27, TS-19, TS-13, CL-4, LV-ENUM.
- IN-15: schema_registry.json declares `quota_cap` optional integer 1-100000; Quota :140-145 "A product whose settings in
  that document carry `quota_cap` and that holds more units than its cap gives the excess back and keeps its cap. Every
  product keeps the units it holds. The units given back are handed out again by largest remainder in proportion to
  weight among the products still holding less than their cap or carrying no cap, with Q the units given back and W the
  sum of their weights, and each cap applies again after the round. This repeats until a round gives nothing back; units
  that no product can take are not handed out."
- IN-16: Q and W of each round are named; "keeps the units it holds" settles additive vs restart; termination and the
  leftover are stated. No worked example (W6). LV-ENUM clean: no list of cases.
- AL-27: shipped data carries 4 product caps that bind in round one only (restart = additive there, generator asserts);
  hidden: about 10% of active products capped (some bind only after a re-share), an env_dev tier cap; capped tier (30%)
  and rescaled tier (env_prod default cap, units left unassigned). Asserts: restart differs on all three quota docs.
- TS-13: three capped rows (config/dev/prod) own the quota column of the capped tier; quota_hard rows own the main tier.
- Fallback: playbook IN-16 DO: one clause "a product that took part in an earlier round keeps those units" in :140-145.
  Playbook AL-27 DO: raise cap rate in gen_capped.

## NL-4 text-layer values read by the digits 0 to 9 only; others passed over (H1 bare property)
- Rules touched: IN-15, IN-16, AL-27, TS-19, DS-25, LV-ENUM.
- IN-15: Text layers :87-93 "integer as one or more of the digits 0 to 9; boolean as `true` or `false` in any letter
  case; ... Text that does not read as its key's type is passed over, and the key keeps the value the earlier layers gave
  it. Every text-layer key is in the schema, and text layers never list anything in validation_report.json."
- IN-16: one reading per type (character set named; letter case named); the passed-over outcome is stated once.
  LV-ENUM clean: no list of rejected spellings.
- AL-27: shipped carries ASCII plants (`+N`, words such as `on`) in products.ini and both env files (bare-property H1 may
  ship, W5); hidden adds fullwidth digits and more words. Asserts: lenient reading changes config.json.
- DS-25: shipped files stay ASCII-only (datagen asserts); non-ASCII digits only in hidden corpora.
- Fallback: playbook IN-16 DO: none needed beyond the bare property; playbook AL-27 DO: raise odd_rate in gen_core.

## LV-CC-1 active owner on D includes `RETIRE owner=` events (H3; background since harden r1)
- Harden r1: glossary now :40-42 ("Active owner on date D: an owner whose assignment on D has active_to empty or on or
  after D, and who has no `RETIRE owner=<owner>` event ..."); the defence below still holds.
- Rules touched: IN-15, IN-16, AL-27, TS-19, TS-13, TS-26.
- IN-15 "every graded rule of engagement is stated plainly enough to act on": the glossary of config_contract.md defines
  "Active owner on date D" with both clauses (owners.csv interval covering D, and no `RETIRE owner=<owner>` event dated on
  or before D); the deprecation.log block lists `RETIRE owner=` as an event kind. Instruction delegates every rule to the
  contract. PASS precedent: district-heat v3:119, cohort v2:119 ("rules are in X" delegation).
- IN-16 "one reading": the definition is a conjunction with a stated date bound; selectors and team overrides use the
  defined term "products whose team is <name>" and team is defined only for active products. PASS precedent: cohort v2:120
  (definition with a branch is one reading).
- AL-27 "every stated rule has a triggering fixture": shipped log has no owner event (W5, master note); every hidden corpus
  retires 8-12 owners whose products are matched by team selectors and team overrides; M1 adds owner events dated after D.
- TS-19: the hidden generator emits owner events only for owners present in owners.csv, dates inside the release year.
- Fallback: playbook IN-16 DO: add one settling clause to the glossary entry in config_contract.md ("an owner retired in
  deprecation.log on or before D is not active on D, whatever owners.csv says"), no example, no warning. Playbook AL-27 DO:
  raise the number of hidden log-retired owners in the embedded generator (never in shipped data).

## LV-CC-2 JSON override values keep their JSON type (H1 / L5; background since harden r1)
- Harden r1: the enumeration in the Malformed overrides list is removed (LV-ENUM); reason 3 now reads "`type`: the
  value does not have the key's type" (:109) and the type statement stays once in the product_overrides.jsonl block
  (:74-77). The quoted list in the IN-15 bullet below is the build text and no longer ships.
- Rules touched: IN-15, IN-16, AL-27, TS-19, TS-13.
- IN-15: stated twice as L5 requires: the product_overrides.jsonl field block names the accepted JSON type for each schema
  kind, and the Malformed overrides list names "a JSON string for an integer or boolean key, whatever text it holds; a JSON
  boolean for an integer key; a number with a fraction or exponent; null for a key that is not optional" with reason
  `type`. team_overrides.json block says its values follow the same typing.
- IN-16: every JSON value kind is settled for every schema kind (integer, boolean, string, enum, list, optional), which is
  what schema v3:32 FAIL asked for. The text-layer reading (quoted and bare alike) is a separate section naming the four
  text files; JSON files are named as JSON layers. PASS precedent district-heat v3:120 (global default with an exception
  stated elsewhere is one reading). The generator never draws a space-padded string (open case avoided, cohort v2:120).
- AL-27: separating rows ship (quoted weight, replicas, alerts_enabled, pii_scan, retention_days) and are reseeded hidden.
- Fallback: playbook IN-16 DO: one general clause in the product_overrides.jsonl block ("a JSON string is never read as a
  number or a boolean"), no example. Playbook AL-27 DO: more hidden quoted rows on weight.

## LV-CC-4 product ids canonical at every comparison, including deprecation.log (H4 / L10; background since harden r1)
- Rules touched: IN-15, IN-16, AL-27, TS-19.
- IN-15/IN-16: Identifiers section: "Product ids are compared after converting them to upper case and removing every
  hyphen. Output documents write the canonical form." deprecation.log block: "`product=` names a product id". One global
  rule written once (W3 bare property). PASS precedent district-heat v3:120.
- AL-27: shipped log ids canonical (W5); hidden logs write about 60% of retire ids lower or mixed case with hyphens, all of
  which canonicalise to a catalog id; unknown ids drawn outside the catalog id space.
- TS-19: hidden ids use only letters, digits and hyphens.
- Fallback: playbook AL-27 DO: more hidden mixed-form retire ids. Playbook IN-15 DO: restate the rule as a bare property in
  the deprecation.log block of config_contract.md (same file), no example.

## Cascade C-ROW: row-owned families and the COUPLING quota (all levers; CL-4)
- Rules touched: TS-13, TS-26, TS-20, AL-28, CL-4.
- Harden r1 layout: 10 families (status_team merges catalog_status and team) each w3 + `_hard` w5, three capped rows
  w5, six generic rows and layout w1; P=120.
- Build layout: 11 families (catalog_status, team, settings_int, settings_other, config_quota, dev_deploy, dev_quota,
  prod_deploy, prod_quota, rejected_overrides, summary), each visible w3 and hidden `_hard` w5, each owning disjoint fields.
  TS-13 PASS precedent district-heat v3:176, emberforge v5:161. TS-26 PASS precedent district-heat v3:185, cohort v2:183
  (visible and `_hard` read different inputs; families own different fields).
- CL-4: instruction.md states that each output document must match the contract whole and exactly on these files and on
  fresh data (exemption sentence); the spread of a slip comes from the stated COUPLING quantity (quota denominator over
  active products and resolved weights). One-fact-wrong per lever is measured in COST_TABLE.md.
- TS-20: `_hard` and mutations w5 core, visible and robustness w3, existence w1. PASS precedent cohort v2:181.
- AL-28: tests carry no negatives; judge negatives name single cheating acts. PASS precedent cohort v2:242, district-heat
  v3:251.
- Fallback: playbook TS-26 DO: narrow one family's owned fields (e.g. drop replicas from dev_deploy rows if QC calls it the
  same observable as settings_int). Playbook TS-23 DO: keep WARN A3 if checks exceed 35; never merge lever checks.

## Cascade C-MUT: mutations and rejection paths
- Rules touched: TS-19, AL-27, TS-26, DS-25.
- Error strings and exit codes stated verbatim in config_contract.md (DS-25); R1 and R2 trigger them on hidden copies.
  M1 (second date), M2 (rescaled cluster quota), M3 (shuffled override lines, renamed data dir) read different observables
  from the `_hard` family checks; R3 determinism compares two runs. No check uses agent output as input (TS-26).
- Fallback: playbook TS-19 DO: add the generated case or bring the generator inside the stated bounds.

## Judge (J1-J9)
- Rules touched: JD-7, JD-15, JD-18, JD-8, JD-11.
- JD-7: R1-R7 and R10 are performed by the solve.sh self-check stage (separate module, recomputes from /app/data, prints
  `check R<n> ok`); R8 met by the repaired tool as solve.sh writes it; R9 by the final response text solve.sh prints.
- JD-15: conduct criteria labelled conduct; honesty and grader-read negatives labelled as such.
- JD-8/J8: recompute criteria name the act of comparing a figure family, never the figure or the rule a test grades.
- JD-11: no criterion penalises writing under /app/data (read-only for uid 1000).
- Fallback: playbook JD-7 DO: add the act to solution/selfcheck.py; JD-15 DO: relabel; JD-18 DO: name the concrete shape.

## Lessons for the master
QC_DEFENCE can be mostly cloned per lever kind (L5, L10 entries were near copies of the metered build) | no change: reuse is intended
