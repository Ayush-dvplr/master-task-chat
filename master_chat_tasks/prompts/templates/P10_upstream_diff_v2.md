# P10 Upstream change diff (PL generator or QC), template v2 (23 Oct 2026; v1 + _COMMON_RULES_v2 path + Lessons for the master)

Use this when Ayush says "generator updated" or "QC updated", or when a fingerprint check fails. Ayush pulls the clone himself first. The master chat gives him the command.

=== PASTE BELOW ===

You are measuring exactly what changed in the PL generator and/or the Input Bundle QC since the last recorded fingerprints, and what each change means for authoring tasks. Read only.

First read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES_v2.md`. Ignore its rule 1 (stop on fingerprint change); measuring that change is your job.

## Inputs
- Clone: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/` (read only; HEAD now `[[NEW_HEAD_OR_CHECK]]`, previously `[[OLD_HEAD]]`)
- Old fingerprints: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/fingerprints/{pl_generator,qc}.json`
- Old maps: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261020_analysis/reports/qc/qc_checks.json`, `.../reports/pl_generator/validator_rules.json`, `.../reports/pl_generator/archetypes.json`
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/[[DATE]]_upstream/`

## Steps
1. Re-hash both folders with the same exclusions as the fingerprint files (generator: skip `ayush sah tasks`, `memory`, `__pycache__`; QC: skip `__pycache__`). List added, removed and modified files.
2. Run `git log --oneline [[OLD_HEAD]]..HEAD -- "Input Bundle Generator New" Input_Bundle_QC`, plus `git show --stat` for each commit. Use `git diff [[OLD_HEAD]] HEAD -- <file>` for each modified file.
3. For QC: for every changed hunk, name the check ID, its old and new wording, severity and threshold, and whether it is now script-owned. Match on ID AND wording, because renumbering happens.
4. For the generator: report changes to CLI flags, archetypes and their fixed artifacts, `task.toml` and Dockerfile templates, validator rules (id, severity), reward or judge shape, and data volume rules.
5. Impact table, of the form "change, then what a builder or fixer must now do differently, then which templates are affected (P2..P15, `_COMMON_RULES_v2`, `knowledge/LEVER_RULES_v3.md`, `knowledge/qc_authoring_checklist`, `knowledge/archetypes.md`)".
6. Existing bundles: run the 4 QC scripts and the validator on each bundle under `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/` (skip `_work`). List any new FAIL.
7. Write new fingerprint files to OUT (same JSON shape, new head). Do not overwrite the ones in `master_chat_tasks/`; the master chat installs them.

## Deliverables (OUT)
- `UPSTREAM_DIFF.md`: commits, file changes, the check and rule changes table, the impact table, and existing-bundle results.
- `changes.json`: `[{"component":"qc|generator","id":"","kind":"added|removed|reworded|severity|threshold|ownership|cli|template","old":"","new":"","impact":"","templates":[]}]`
- `fingerprint_pl_generator.json`, `fingerprint_qc.json`

Report ending (E3): every report file you write ends with a section "## Lessons for the master" of at most 5 lines (what the master should change in prompts, rules or records; "none" if nothing).

Done when: every modified file is accounted for, the JSON parses, and nothing in the clone changed (`git status` before and after). Final reply: the commit count, changed check IDs, the templates to update, the bundles with new FAILs, and paths.
