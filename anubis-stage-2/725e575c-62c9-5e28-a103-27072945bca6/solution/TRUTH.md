# TRUTH.md - 725e575c-62c9-5e28-a103-27072945bca6

## Defect

The shipped `runledger` project (`/app/data/project.zip`) does not install on Python 3.12, and once it does it computes a stage ledger that follows the textbook reading of every rule instead of the approved specification (run_spec_v3_2.docx), its incorporated documents and the approved errata (errata_register.pdf). It also trusts every out-of-scope file wholesale and never reads the parts of those files that remain authoritative. The agent must repair the package, ship it as `/app/out/package.zip`, and produce the stage-1 ledger with it; the same package is then run on a hidden stage-2 feed opened from the agent's own `resume_state.json`.

1. (focal) requires-python excludes the 3.12 runtime - `pyproject.toml`.
2. (focal) package-dir points at a missing tree - `pyproject.toml`.
3. (focal) third-party tomli import on Python 3.12 - `src/runledger/readers.py`.
4. (focal) circular import conventions <-> feed - `src/runledger/conventions.py`.
5. (focal) unclosed list literal (SyntaxError) - `src/runledger/ledger.py`.
6. (trap) no cp1252 fallback for legacy lines (3.4) - `src/runledger/conventions.py`.
7. (trap) homoglyph map not applied to keys (3.1) - `src/runledger/conventions.py`.
8. (trap) k / M suffixes unsupported (3.2) - `src/runledger/conventions.py`.
9. (trap) trailing % marker ignored (3.2) - `src/runledger/conventions.py`.
10. (trap) spreadsheet serial base wrong and 1904 system ignored (3.3) - `src/runledger/conventions.py`.
11. (trap) naive local wall times read as UTC (3.3) - `src/runledger/conventions.py`.
12. (trap) restated headers read as data rows (3.5) - `src/runledger/readers.py`.
13. (focal) declared scopes ignored: out-of-scope files trusted wholesale (governance G0/G2) - `src/runledger/feed.py`.
14. (focal) legacy crosswalk never loaded (3.1, G2 snapshot) - `src/runledger/feed.py`.
15. (drift) newest partition wins instead of the routed home partition (4.1) - `src/runledger/feed.py`.
16. (trap) withdrawn VOID registry rows kept (4.1) - `src/runledger/feed.py`.
17. (trap) first void action wins instead of the highest action_seq (4.3) - `src/runledger/feed.py`.
18. (trap) errata approved after the cutover applied (4.8) - `src/runledger/feed.py`.
19. (focal) carried approvals of errata revision B never read (G2 draft) - `src/runledger/feed.py`.
20. (drift) r6 preview counts used for every source (tokenizer_migration 2.3) - `src/runledger/feed.py`.
21. (drift) conversion rounds half up (errata C4) - `src/runledger/feed.py`.
22. (focal) glacier hashes of the archive inventory never read (G2 archive) - `src/runledger/feed.py`.
23. (focal) vendor revocations never applied (4.6, G2 vendor) - `src/runledger/feed.py`.
24. (focal) doc_id keyed data cards dropped (4.7, G2 archive doc_index) - `src/runledger/feed.py`.
25. (focal) dissolved clusters kept (4.10, G2 v1) - `src/runledger/feed.py`.
26. (focal) retracted findings still exclude (4.9, G2 rerun) - `src/runledger/feed.py`.
27. (trap) provisional dagger rows read as register rows (3.7) - `src/runledger/conventions.py`.
28. (trap) Message-ID compared verbatim, retractions missed (6.3) - `src/runledger/feed.py`.
29. (trap) floating calendar times read as UTC (compute_accounting C2) - `src/runledger/feed.py`.
30. (trap) replay windows not half-open (6.2) - `src/runledger/feed.py`.
31. (focal) whole replay dump trusted, not only its truncation window (G2 replay) - `src/runledger/feed.py`.
32. (focal) host map of the aggregate log never loaded (6.1) - `src/runledger/feed.py`.
33. (trap) partial rank files count as present (8.1) - `src/runledger/feed.py`.
34. (focal) tombstones of the mirror never applied (8.1, G2 mirror) - `src/runledger/feed.py`.
35. (focal) H1 harness crosswalk never loaded (8.2, G2 superseded) - `src/runledger/feed.py`.
36. (trap) first evaluation row wins instead of the latest run (8.2) - `src/runledger/feed.py`.
37. (drift) exclusion uses '>' and per-shard findings instead of content groups (errata C1, 4.9) - `src/runledger/ledger.py`.
38. (focal) cross-stage duplicates against seen_hashes not detected (5.3) - `src/runledger/ledger.py`.
39. (trap) duplicate election not by earliest UTC ingest (5.5) - `src/runledger/ledger.py`.
40. (drift) keep_k of the source policy ignored (5.6) - `src/runledger/ledger.py`.
41. (trap) taint counted over excluded shards too (E3) - `src/runledger/ledger.py`.
42. (drift) attempt loss divides by the record count, a mean of per-node means (6.6, errata C5) - `src/runledger/ledger.py`.
43. (drift) per-record loss accumulated as a per-token mean instead of the raw loss_sum (6.6, errata C5) - `src/runledger/ledger.py`.
44. (focal) rollback lineage ignored: abandoned attempts kept (6.4) - `src/runledger/ledger.py`.
45. (drift) schedule counted in attempts instead of optimizer steps (errata C3) - `src/runledger/ledger.py`.
46. (drift) total steps recomputed every stage instead of carried (7) - `src/runledger/ledger.py`.
47. (drift) overflow-skipped tokens not consumed (errata C2) - `src/runledger/ledger.py`.
48. (trap) ema not quantised after every step (6.7) - `src/runledger/ledger.py`.
49. (trap) resume seen_hashes drops the opening list, which must be carried normalised and once per hash (10.7, 11) - `src/runledger/ledger.py`.
50. (trap) resume state written without its run_control stamp (10.1) - `src/runledger/ledger.py`.

The reference is Python 3.12 (`solution/solve.py` applies the inverse of each defect and runs the repaired package). Grading has two channels: deterministic checks in `tests/test_output.py` and judged trajectory criteria in `tests/judge.toml`.

Out of bounds: hard-coding stage-1 answers into the package (`negative_hardcoded_sample_answers`), behaviour keyed on feed file names (`negative_filename_dependent_behaviour`), reading `/app/data` from the delivered package (`negative_corpus_path_literal_in_package`), and nondeterministic output (`negative_nondeterministic_output`).

### Model-training concepts (all load-bearing, interacting)

- **C1 Token accounting across tokenizer revisions.** Registry counts are per tokenizer revision; ratios convert them to r5, recounts and r6 adoption override, errata override all (run_spec 4.2, tokenizer_migration 2.1-2.3, errata C4). Feeds C2 budgets, C5 total steps and every epochs value.
- **C2 Data mixture and epoch accounting.** Included tokens per source times planned epochs give the budget; consumed tokens per source give effective epochs (run_spec 7, 10.4, Appendix B). Depends on C3/C4 inclusion and on C6 cutover.
- **C3 Exact and near-duplicate deduplication, within and across stages.** Content hashes from the latest inventory scan, seen_hashes of the opening state, earliest-ingest representatives, keep_k per source for MinHash clusters (run_spec 4.5, 5.3, 5.5, 5.6). Output feeds C4 taint and C2.
- **C4 Benchmark decontamination and taint.** Exclusion at or above threshold (errata C1), contamination as a property of content groups (4.9), and taint computed over included shards only (eval_protocol E3). Taint changes the selection aggregate of C6.
- **C5 Learning-rate schedule over optimizer steps.** Warmup and cosine decay are counted in optimizer steps; overflow-skipped attempts take no step (errata C3); total steps come from the C2 budget once and are carried across stages (run_spec 7).
- **C6 Rollback lineage, checkpoint validity and selection.** ROLLBACK incidents abandon attempts; checkpoints need 64 ok ranks, no tombstone, lineage membership; the aggregate over untainted benchmarks selects the cutoff (run_spec 6.4, 8, eval_protocol E2-E4).
- **C7 Token-weighted loss and stateful EMA.** Attempt loss is sum(loss_sum)/sum(tokens) over node records, not a mean of node means (errata C5); EMA is quantised every step and continues across stages (6.6, 6.7).
- **C8 Mixed-precision overflow handling.** OVERFLOW alerts (minus retractions, deduplicated by Message-ID) skip the optimizer step but their tokens are consumed (6.3, errata C2). Shifts every later step number, LR and checkpoint mapping.
- **C9 Compute accounting.** flops = 6 * n_params * processed tokens over all non-replay records; GPU hours from SESSION events measured in UTC across DST (compute_accounting C1, C2).
- **C10 Stage resume state.** The closing state carries optimizer step, EMA, total steps, cumulative consumption and seen hashes into the next stage; the hidden stage-2 tier is computed from the agent's own resume_state.json (run_spec 11).

## Load-bearing work

7 artifacts are collected and every one is graded:

- `/app/out/package.zip`
- `/app/out/shard_ledger.csv`
- `/app/out/step_ledger.csv`
- `/app/out/mixture_report.json`
- `/app/out/checkpoint_report.json`
- `/app/out/reconciliation.json`
- `/app/out/resume_state.json`

- `package.zip`: src-layout project with `pyproject.toml`, `src/runledger` and the shipped tests; pip-installed offline, its shipped tests run, and run on the stage-2 feed by the verifier as an unprivileged user on a Python 3.12 that has setuptools, the declared dependencies and the grader's own harbor-rewardkit, and nothing else the agent image carries.
- The six stage-1 reports: exact text (CSV) or exact JSON values and types per run_spec section 10, each stamped with run_control. Every row and every field is compared.

Partial credit is per rule family and per report block, and every graded value is graded by one check: each shard row belongs to exactly one rule-family group (errata, licence and approval, duplicates, contamination, taken in that order) or to the remainder, whose source and token, status and representative, and consumption columns have one check each; the step ledger is graded column by column per attempt; the run_control stamp shared by all six outputs is graded once per run (`run_control_stamps` for stage 1, inside `stage2_reconciliation` for stage 2). Out of bounds by design: any value not derivable from `/app/data`.

### 100-file inventory

| file | type | records | role | unique contribution | depends on | depended on by |
|---|---|---|---|---|---|---|
| alerts.mbox | mbox | 5200 | in-scope | overflow, retraction, rollback and truncation incidents | 5: feed_index.json, governance_precedence.docx, node_operations_handbook.docx, project.zip, ... | 20 |
| alias_part02.toml | toml | 5085 | in-scope | retired-to-surviving key merges | 5: feed_index.json, feed_readme.md, governance_precedence.docx, project.zip, ... | 12 |
| checkpoints_part01.db | sqlite | 6901 | in-scope | checkpoint rank files | 7: alerts.mbox, checkpoints_part02.db, feed_index.json, governance_precedence.docx, ... | 10 |
| checkpoints_part02.db | sqlite | 5209 | decoy D05 | only tombstone evidence; scope mirror | 6: alerts.mbox, feed_index.json, governance_precedence.docx, project.zip, ... | 4 |
| compute_accounting.pdf | pdf | 5222 | in-scope | n_params and compute rules (C1, C2) | 6: alias_part02.toml, feed_index.json, governance_precedence.docx, inventory_part09.yaml, ... | 3 |
| contamination_appendix.pdf | pdf | 5958 | in-scope | v3 findings of its shards | 7: contamination_part09.jsonl, decontamination_procedure.docx, eval_protocol.docx, feed_index.json, ... | 2 |
| contamination_part01.csv | csv | 5938 | in-scope | v3 findings of its shards | 7: contamination_part09.jsonl, decontamination_procedure.docx, eval_protocol.docx, feed_index.json, ... | 2 |
| contamination_part02_rerun.tsv | tsv | 5967 | in-scope | v3 findings of its shards | 7: contamination_part09.jsonl, decontamination_procedure.docx, eval_protocol.docx, feed_index.json, ... | 2 |
| contamination_part03.jsonl | jsonl | 5991 | in-scope | v3 findings of its shards | 7: contamination_part09.jsonl, decontamination_procedure.docx, eval_protocol.docx, feed_index.json, ... | 2 |
| contamination_part04.jsonl | jsonl | 6038 | in-scope | v3 findings of its shards | 7: contamination_part09.jsonl, decontamination_procedure.docx, eval_protocol.docx, feed_index.json, ... | 2 |
| contamination_part05.parquet | parquet | 5811 | in-scope | v3 findings of its shards | 7: contamination_part09.jsonl, decontamination_procedure.docx, eval_protocol.docx, feed_index.json, ... | 2 |
| contamination_part06.yaml | yaml | 6049 | in-scope | v3 findings of its shards | 7: contamination_part09.jsonl, decontamination_procedure.docx, eval_protocol.docx, feed_index.json, ... | 2 |
| contamination_part09.jsonl | jsonl | 5128 | decoy D03 | only retraction list of v3 findings; scope rerun | 6: decontamination_procedure.docx, eval_protocol.docx, feed_index.json, governance_precedence.docx, ... | 11 |
| contamination_part10.xml | xml | 6010 | in-scope | v3 findings of its shards | 7: contamination_part09.jsonl, decontamination_procedure.docx, eval_protocol.docx, feed_index.json, ... | 2 |
| dashboard_evals.html | html | 6226 | in-scope | evaluation rows | 9: checkpoints_part01.db, eval_leaderboard.html, eval_protocol.docx, evals_part06.xlsx, ... | 2 |
| datacards_part01.xlsx | xlsx | 10000 | in-scope | data card revisions of its shards | 5: datacards_part05.xlsx, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| datacards_part02.xlsx | xlsx | 10000 | in-scope | data card revisions of its shards | 5: datacards_part05.xlsx, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| datacards_part03.xlsx | xlsx | 10000 | in-scope | data card revisions of its shards | 5: datacards_part05.xlsx, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| datacards_part04.xlsx | xlsx | 10000 | in-scope | data card revisions of its shards | 5: datacards_part05.xlsx, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| datacards_part05.xlsx | xlsx | 27532 | decoy D12 | only doc_id to shard key index; scope archive | 4: feed_index.json, governance_precedence.docx, project.zip, run_spec_v3_2.docx | 8 |
| datacards_part06.xlsx | xlsx | 10000 | in-scope | data card revisions of its shards | 5: datacards_part05.xlsx, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| datacards_part07.xlsx | xlsx | 10000 | in-scope | data card revisions of its shards | 5: datacards_part05.xlsx, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| decontamination_procedure.docx | docx | 5851 | in-scope | findings semantics (D1-D4) | 6: contamination_part09.jsonl, eval_protocol.docx, feed_index.json, governance_precedence.docx, ... | 11 |
| dedup_report.pdf | pdf | 7840 | in-scope | MinHash v2 memberships of its shards | 5: feed_index.json, governance_precedence.docx, neardup_part03.json, project.zip, ... | 5 |
| errata_part02.xml | xml | 5167 | in-scope | field corrections | 5: errata_register.pdf, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| errata_part03.yaml | yaml | 5166 | in-scope | field corrections | 5: errata_register.pdf, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| errata_register.pdf | pdf | 5279 | in-scope | clause errata C1-C5 | 4: feed_index.json, governance_precedence.docx, project.zip, run_spec_v3_2.docx | 15 |
| errata_register_revB.pdf | pdf | 5442 | decoy D07 | APPROVED-CARRIED entries are approved corrections; DRAFT title | 5: errata_register.pdf, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| eval_leaderboard.html | html | 5300 | decoy D11 | only rows of private benchmarks; scope leaderboard | 8: checkpoints_part01.db, eval_protocol.docx, evals_part06.xlsx, feed_index.json, ... | 9 |
| eval_protocol.docx | docx | 6327 | in-scope | benchmark weights and thresholds (E1), selection rules (E2-E4) | 8: checkpoints_part01.db, eval_leaderboard.html, evals_part06.xlsx, feed_index.json, ... | 19 |
| evals_part01.csv | csv | 6140 | in-scope | evaluation rows | 9: checkpoints_part01.db, eval_leaderboard.html, eval_protocol.docx, evals_part06.xlsx, ... | 2 |
| evals_part02.csv | csv | 6116 | in-scope | evaluation rows | 9: checkpoints_part01.db, eval_leaderboard.html, eval_protocol.docx, evals_part06.xlsx, ... | 2 |
| evals_part03.json | json | 6212 | in-scope | evaluation rows | 9: checkpoints_part01.db, eval_leaderboard.html, eval_protocol.docx, evals_part06.xlsx, ... | 2 |
| evals_part06.xlsx | xlsx | 17256 | decoy D04 | only R- run crosswalk (run_map sheet); per-run ledger of R- runs | 8: checkpoints_part01.db, eval_leaderboard.html, eval_protocol.docx, feed_index.json, ... | 9 |
| feed_index.json | json | 5484 | in-scope | file sequence for the record chain and routing of conflicting registry keys | 99: alerts.mbox, alias_part02.toml, checkpoints_part01.db, checkpoints_part02.db, ... | 99 |
| feed_readme.md | md | 5294 | in-scope | retired-to-surviving key merges | 4: feed_index.json, governance_precedence.docx, project.zip, run_spec_v3_2.docx | 4 |
| governance_precedence.docx | docx | 5247 | in-scope | document register (G1) and scope table (G2) | 4: feed_index.json, known_issues.md, project.zip, run_spec_v3_2.docx | 99 |
| inventory_part01.csv | csv | 5204 | in-scope | latest content-hash scans of its shards | 6: alias_part02.toml, feed_index.json, governance_precedence.docx, inventory_part09.yaml, ... | 3 |
| inventory_part02.csv | csv | 5372 | in-scope | latest content-hash scans of its shards | 6: alias_part02.toml, feed_index.json, governance_precedence.docx, inventory_part09.yaml, ... | 2 |
| inventory_part03.tsv | tsv | 5280 | in-scope | latest content-hash scans of its shards | 6: alias_part02.toml, feed_index.json, governance_precedence.docx, inventory_part09.yaml, ... | 2 |
| inventory_part04.jsonl | jsonl | 5152 | in-scope | latest content-hash scans of its shards | 6: alias_part02.toml, feed_index.json, governance_precedence.docx, inventory_part09.yaml, ... | 2 |
| inventory_part05.json | json | 5275 | in-scope | latest content-hash scans of its shards | 6: alias_part02.toml, feed_index.json, governance_precedence.docx, inventory_part09.yaml, ... | 2 |
| inventory_part06.parquet | parquet | 5254 | in-scope | latest content-hash scans of its shards | 6: alias_part02.toml, feed_index.json, governance_precedence.docx, inventory_part09.yaml, ... | 2 |
| inventory_part07.xml | xml | 5291 | in-scope | latest content-hash scans of its shards | 6: alias_part02.toml, feed_index.json, governance_precedence.docx, inventory_part09.yaml, ... | 2 |
| inventory_part08.html | html | 5082 | in-scope | latest content-hash scans of its shards | 6: alias_part02.toml, feed_index.json, governance_precedence.docx, inventory_part09.yaml, ... | 2 |
| inventory_part09.yaml | yaml | 5350 | decoy D09 | glacier rows are the only inventory rows of those shards; scope archive | 5: alias_part02.toml, feed_index.json, governance_precedence.docx, project.zip, ... | 11 |
| known_issues.md | md | 5173 | in-scope | void register actions | 4: feed_index.json, governance_precedence.docx, project.zip, run_spec_v3_2.docx | 4 |
| license_audit_2026.pdf | pdf | 5550 | in-scope | licence class table (L1) | 5: feed_index.json, governance_precedence.docx, license_part08.ini, project.zip, ... | 11 |
| license_part01.csv | csv | 5461 | in-scope | licence rows of its shards | 6: feed_index.json, governance_precedence.docx, license_audit_2026.pdf, license_part08.ini, ... | 2 |
| license_part02.tsv | tsv | 5433 | in-scope | licence rows of its shards | 6: feed_index.json, governance_precedence.docx, license_audit_2026.pdf, license_part08.ini, ... | 2 |
| license_part03.ini | ini | 5549 | in-scope | licence rows of its shards | 6: feed_index.json, governance_precedence.docx, license_audit_2026.pdf, license_part08.ini, ... | 2 |
| license_part04.ini | ini | 5404 | in-scope | licence rows of its shards | 6: feed_index.json, governance_precedence.docx, license_audit_2026.pdf, license_part08.ini, ... | 2 |
| license_part05.toml | toml | 5452 | in-scope | licence rows of its shards | 6: feed_index.json, governance_precedence.docx, license_audit_2026.pdf, license_part08.ini, ... | 2 |
| license_part06.xml | xml | 5388 | in-scope | licence rows of its shards | 6: feed_index.json, governance_precedence.docx, license_audit_2026.pdf, license_part08.ini, ... | 2 |
| license_part07.txt | txt | 5411 | in-scope | licence rows of its shards | 6: feed_index.json, governance_precedence.docx, license_audit_2026.pdf, license_part08.ini, ... | 2 |
| license_part08.ini | ini | 5840 | decoy D10 | only revocation list; scope vendor | 5: feed_index.json, governance_precedence.docx, license_audit_2026.pdf, project.zip, ... | 11 |
| neardup_part01.json | json | 7980 | in-scope | MinHash v2 memberships of its shards | 6: dedup_report.pdf, feed_index.json, governance_precedence.docx, neardup_part03.json, ... | 2 |
| neardup_part02.csv | csv | 8042 | in-scope | MinHash v2 memberships of its shards | 6: dedup_report.pdf, feed_index.json, governance_precedence.docx, neardup_part03.json, ... | 2 |
| neardup_part03.json | json | 5399 | decoy D13 | only dissolved-cluster list; scope v1 | 5: dedup_report.pdf, feed_index.json, governance_precedence.docx, project.zip, ... | 5 |
| node_calendar.ics | ics | 5229 | in-scope | node sessions and preemption windows | 6: compute_accounting.pdf, feed_index.json, governance_precedence.docx, node_operations_handbook.docx, ... | 17 |
| node_operations_handbook.docx | docx | 5668 | in-scope | node site zones and GPU counts (N1), log formats (N2) | 8: alerts.mbox, feed_index.json, governance_precedence.docx, node_calendar.ics, ... | 18 |
| project.zip | zip | 5404 | archive | broken pipeline to repair, its shipped tests and build metadata | 99: alerts.mbox, alias_part02.toml, checkpoints_part01.db, checkpoints_part02.db, ... | 99 |
| recount_part01.csv | csv | 5329 | in-scope | r5 recount results of its shards | 6: feed_index.json, governance_precedence.docx, project.zip, recount_part07.parquet, ... | 2 |
| recount_part02.parquet | parquet | 5487 | in-scope | r5 recount results of its shards | 6: feed_index.json, governance_precedence.docx, project.zip, recount_part07.parquet, ... | 2 |
| recount_part03.parquet | parquet | 5462 | in-scope | r5 recount results of its shards | 6: feed_index.json, governance_precedence.docx, project.zip, recount_part07.parquet, ... | 2 |
| recount_part04.jsonl | jsonl | 5448 | in-scope | r5 recount results of its shards | 6: feed_index.json, governance_precedence.docx, project.zip, recount_part07.parquet, ... | 2 |
| recount_part05.tsv | tsv | 5423 | in-scope | r5 recount results of its shards | 6: feed_index.json, governance_precedence.docx, project.zip, recount_part07.parquet, ... | 2 |
| recount_part06.yaml | yaml | 5256 | in-scope | r5 recount results of its shards | 6: feed_index.json, governance_precedence.docx, project.zip, recount_part07.parquet, ... | 2 |
| recount_part07.parquet | parquet | 7114 | decoy D02 | final r6 rows of adopted sources are the token count; scope preview | 5: feed_index.json, governance_precedence.docx, project.zip, run_spec_v3_2.docx, ... | 9 |
| registry_part01.csv | csv | 6653 | in-scope | home-partition registry rows (source, revision, raw count, ingest time) of its shards | 7: errata_register.pdf, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| registry_part02.csv | csv | 6768 | in-scope | home-partition registry rows (source, revision, raw count, ingest time) of its shards | 7: errata_register.pdf, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| registry_part03_final.csv | csv | 6838 | in-scope | home-partition registry rows (source, revision, raw count, ingest time) of its shards | 7: errata_register.pdf, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| registry_part04.tsv | tsv | 6620 | in-scope | home-partition registry rows (source, revision, raw count, ingest time) of its shards | 7: errata_register.pdf, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| registry_part05.jsonl | jsonl | 6721 | in-scope | home-partition registry rows (source, revision, raw count, ingest time) of its shards | 7: errata_register.pdf, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| registry_part06.parquet | parquet | 6570 | in-scope | home-partition registry rows (source, revision, raw count, ingest time) of its shards | 7: errata_register.pdf, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| registry_part07.xml | xml | 6800 | in-scope | home-partition registry rows (source, revision, raw count, ingest time) of its shards | 7: errata_register.pdf, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| registry_part08.txt | txt | 6733 | in-scope | home-partition registry rows (source, revision, raw count, ingest time) of its shards | 7: errata_register.pdf, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| registry_part09.db | sqlite | 6693 (declares 6639) | in-scope | home-partition registry rows (source, revision, raw count, ingest time) of its shards | 7: errata_register.pdf, feed_index.json, governance_precedence.docx, project.zip, ... | 2 |
| registry_part10.csv | csv | 45000 | decoy D01 | only legacy_id crosswalk for L- loader references; scope declared only in its control block | 7: errata_register.pdf, feed_index.json, governance_precedence.docx, project.zip, ... | 17 |
| run_spec_v3_1.docx | docx | 6309 | decoy D15 | only H1- run crosswalk (Appendix H); superseded | 8: checkpoints_part01.db, eval_leaderboard.html, eval_protocol.docx, evals_part06.xlsx, ... | 9 |
| run_spec_v3_2.docx | docx | 5676 | in-scope | the governing rules, homoglyph map (A), source policy (B), column dictionary (D), cutovers (4.7) | 5: feed_index.json, governance_precedence.docx, license_audit_2026.pdf, license_part08.ini, ... | 99 |
| run_spec_v3_3_draft.md | md | 5178 | decoy D08 | alias register part 3; draft header | 5: feed_index.json, feed_readme.md, governance_precedence.docx, project.zip, ... | 2 |
| schedule_spec.pdf | pdf | 6860 | in-scope | schedule parameters (S1) | 6: alerts.mbox, checkpoints_part02.db, feed_index.json, governance_precedence.docx, ... | 4 |
| stage0_close.json | json | 5208 | in-scope | stage-0 closing state (EMA, steps, seen hashes) | 5: feed_index.json, governance_precedence.docx, inventory_part01.csv, project.zip, ... | 2 |
| tokenizer_migration.docx | docx | 5428 | in-scope | conversion ratios (2.1) and r6 adoption (2.3) | 5: feed_index.json, governance_precedence.docx, project.zip, recount_part07.parquet, ... | 19 |
| trainlog_part01.log | log | 5655 | in-scope | the trainlog records of its node/attempt range | 9: alerts.mbox, feed_index.json, governance_precedence.docx, node_calendar.ics, ... | 2 |
| trainlog_part02.log | log | 5655 | in-scope | the trainlog records of its node/attempt range | 9: alerts.mbox, feed_index.json, governance_precedence.docx, node_calendar.ics, ... | 2 |
| trainlog_part03.log | log | 5655 | in-scope | the trainlog records of its node/attempt range | 9: alerts.mbox, feed_index.json, governance_precedence.docx, node_calendar.ics, ... | 2 |
| trainlog_part04.log | log | 5655 | in-scope | the trainlog records of its node/attempt range | 9: alerts.mbox, feed_index.json, governance_precedence.docx, node_calendar.ics, ... | 2 |
| trainlog_part05.jsonl | jsonl | 5655 | in-scope | the trainlog records of its node/attempt range | 9: alerts.mbox, feed_index.json, governance_precedence.docx, node_calendar.ics, ... | 2 |
| trainlog_part06.jsonl | jsonl | 5655 | in-scope | the trainlog records of its node/attempt range | 9: alerts.mbox, feed_index.json, governance_precedence.docx, node_calendar.ics, ... | 2 |
| trainlog_part07.csv | csv | 5655 | in-scope | the trainlog records of its node/attempt range | 9: alerts.mbox, feed_index.json, governance_precedence.docx, node_calendar.ics, ... | 2 |
| trainlog_part08.csv | csv | 5655 | in-scope | the trainlog records of its node/attempt range | 9: alerts.mbox, feed_index.json, governance_precedence.docx, node_calendar.ics, ... | 2 |
| trainlog_part09.tsv | tsv | 5655 | in-scope | the trainlog records of its node/attempt range | 9: alerts.mbox, feed_index.json, governance_precedence.docx, node_calendar.ics, ... | 2 |
| trainlog_part10.tsv | tsv | 5655 | in-scope | the trainlog records of its node/attempt range | 9: alerts.mbox, feed_index.json, governance_precedence.docx, node_calendar.ics, ... | 2 |
| trainlog_part11.txt | txt | 5655 | in-scope | the trainlog records of its node/attempt range | 9: alerts.mbox, feed_index.json, governance_precedence.docx, node_calendar.ics, ... | 2 |
| trainlog_part12.db | sqlite | 5655 | in-scope | the trainlog records of its node/attempt range | 9: alerts.mbox, feed_index.json, governance_precedence.docx, node_calendar.ics, ... | 2 |
| trainlog_part13.log | log | 5200 | decoy D06 | records inside the truncation window are the only copy; scope replay | 9: alerts.mbox, feed_index.json, governance_precedence.docx, node_calendar.ics, ... | 2 |
| trainlog_part14.tsv | tsv | 5108 | decoy D14 | only host name to node map (needed by trainlog_part11.txt); scope aggregate | 8: alerts.mbox, feed_index.json, governance_precedence.docx, node_calendar.ics, ... | 16 |
| voids_part03.toml | toml | 5036 | in-scope | void register actions | 5: feed_index.json, governance_precedence.docx, known_issues.md, project.zip, ... | 12 |

### Decoys

| id | file | why it looks authoritative | rule that demotes it | load-bearing roles | HARD tests failing if ignored / trusted |
|---|---|---|---|---|---|
| D01 | registry_part10.csv | complete single-file registry, FINAL export label, newest-looking values, every shard present | governance Table G2 (registry, snapshot); known_issues.md K1 | only legacy_id crosswalk for L- loader references; scope declared only in its control block | ignored: shard_ledger_consumption, mixture_report_sources; trusted: shard_ledger_membership, shard_ledger_sources_and_tokens |
| D02 | recount_part07.parquet | newest tokenizer revision r6, clean typed parquet, agrees with r5 counts for most sources | governance G2 (recount, preview); tokenizer_migration.docx 2.3 | final r6 rows of adopted sources are the token count; scope preview | ignored: shard_ledger_sources_and_tokens; trusted: shard_ledger_sources_and_tokens, shard_ledger_status_and_representatives |
| D03 | contamination_part09.jsonl | rerun with a newer v4 13-gram scanner, file name in sequence with the findings partitions | governance G2 (contamination, rerun); decontamination_procedure.docx D1, D3 | only retraction list of v3 findings; scope rerun | ignored: shard_ledger_contamination_rows; trusted: shard_ledger_contamination_rows, checkpoint_aggregates_and_taint |
| D04 | evals_part06.xlsx | consolidated score sheet covering every checkpoint, one place to read evaluations | governance G2 (evals, consolidated); run_spec 8.2 | only R- run crosswalk (run_map sheet); per-run ledger of R- runs | ignored: checkpoint_aggregates_and_taint, checkpoint_selection; trusted: checkpoint_aggregates_and_taint |
| D05 | checkpoints_part02.db | mirror of the checkpoint store with the same schema as the registry | governance G2 (checkpoints, mirror); run_spec 8.1 | only tombstone evidence; scope mirror | ignored: checkpoint_statuses, checkpoint_selection; trusted: checkpoint_statuses |
| D06 | trainlog_part13.log | node n07 log with full coverage, same line format as the primary logs | governance G2 (trainlog, replay); TRUNCATION alert in alerts.mbox; node_operations_handbook N3 | records inside the truncation window are the only copy; scope replay | ignored: step_ledger_tokens_and_loss; trusted: step_ledger_tokens_and_loss, reconciliation_compute |
| D07 | errata_register_revB.pdf | newer revision of the errata register, revision history says FINAL DRAFT | governance G1 (ERR-001 rev B DRAFT) and G2 (errata, draft) | APPROVED-CARRIED entries are approved corrections; DRAFT title | ignored: shard_ledger_errata_rows; trusted: shard_ledger_errata_rows, shard_ledger_sources_and_tokens |
| D08 | run_spec_v3_3_draft.md | newest specification revision with a cleaner rule summary and its own source policy table | governance G1 (3.3 DRAFT) and G2 (aliases, draft) | alias register part 3; draft header | ignored: shard_ledger_contamination_rows, step_ledger_tokens_and_loss; trusted: step_ledger_tokens_and_loss, step_ledger_learning_rate |
| D09 | inventory_part09.yaml | archive inventory listing hashes for shards missing elsewhere | governance G2 (inventory, archive) | glacier rows are the only inventory rows of those shards; scope archive | ignored: shard_ledger_duplicate_rows; trusted: shard_ledger_duplicate_rows |
| D10 | license_part08.ini | vendor licence manifest, same section layout as the licence partitions | governance G2 (license, vendor); run_spec 4.6 | only revocation list; scope vendor | ignored: shard_ledger_license_approval_rows; trusted: shard_ledger_license_approval_rows |
| D11 | eval_leaderboard.html | polished leaderboard export with private benchmarks | governance G2 (evals, leaderboard); eval_protocol E1 private flag | only rows of private benchmarks; scope leaderboard | ignored: checkpoint_aggregates_and_taint; trusted: checkpoint_aggregates_and_taint |
| D12 | datacards_part05.xlsx | data card register with newer revisions marked APPROVED | governance G2 (datacard, archive); run_spec 4.7 | only doc_id to shard key index; scope archive | ignored: shard_ledger_license_approval_rows; trusted: shard_ledger_license_approval_rows |
| D13 | neardup_part03.json | cluster memberships with the same ids as the v2 files | governance G2 (neardup, v1); run_spec 4.10 | only dissolved-cluster list; scope v1 | ignored: shard_ledger_duplicate_rows; trusted: shard_ledger_duplicate_rows |
| D14 | trainlog_part14.tsv | merged aggregator log of all nodes, one convenient file | governance G2 (trainlog, aggregate); run_spec 6.1 | only host name to node map (needed by trainlog_part11.txt); scope aggregate | ignored: step_ledger_tokens_and_loss; trusted: step_ledger_tokens_and_loss |
| D15 | run_spec_v3_1.docx | formal specification document with a full rule set and conversion table | governance G1 (3.1 SUPERSEDED) and G2 (evals, superseded) | only H1- run crosswalk (Appendix H); superseded | ignored: checkpoint_aggregates_and_taint, checkpoint_selection; trusted: shard_ledger_duplicate_rows, shard_ledger_sources_and_tokens |

## Verification

Grader entrypoint: `tests/test.sh` hardens the verifier and runs `rewardkit /tests`. Channel A is the `@criterion` checks of `tests/test_output.py` weighted by their `criteria.<name>(weight=W)` registrations; Channel B is `tests/judge.toml`, judged against `/logs/agent/trajectory.json`. `tests/reward.toml` divides each channel's weighted sum by its positive total and gives each half of the reward.

Channel A declares 31 positive and 4 negative tests, positive weight total 145 and negative weight total -18, so the test channel on its own ranges from -18/145 = -0.124 to +1.000. EASY checks are the two package checks (`package_installs` 3, `package_shipped_tests_pass` 1, 4 points) and HARD checks weigh 5 or 3 (29 of them, 141 points): a solver passing every EASY check and no HARD check scores 4/145 = 0.028 on the test channel.

`package_installs` runs `pip install --no-build-isolation --no-deps --no-index` on the delivered project in the verifier image, which holds setuptools, the dependencies the shipped `pyproject.toml` declares and harbor-rewardkit, so any `requires-python` that admits 3.12 and any working src-layout configuration pass. `package_shipped_tests_pass` requires the archive's `tests/test_smoke.py` to parse to the same syntax tree as the shipped file (formatting and comments may differ), then runs only that file there and requires its six tests to run and pass with nothing skipped. All agent code runs as `nobody` in its own process group; the group, and any live `nobody` process that escaped it into a session of its own, is killed before each check returns.

Positive tests (31):

- `package_installs` (weight 3)
- `package_shipped_tests_pass` (weight 1)
- `run_control_stamps` (weight 5)
- `shard_ledger_membership` (weight 5)
- `shard_ledger_sources_and_tokens` (weight 5)
- `shard_ledger_status_and_representatives` (weight 5)
- `shard_ledger_consumption` (weight 5)
- `shard_ledger_contamination_rows` (weight 5)
- `shard_ledger_duplicate_rows` (weight 5)
- `shard_ledger_license_approval_rows` (weight 5)
- `shard_ledger_errata_rows` (weight 5)
- `step_ledger_status_and_steps` (weight 5)
- `step_ledger_tokens_and_loss` (weight 5)
- `step_ledger_learning_rate` (weight 5)
- `step_ledger_ema` (weight 5)
- `step_ledger_cumulative_tokens` (weight 5)
- `mixture_report_sources` (weight 5)
- `checkpoint_statuses` (weight 5)
- `checkpoint_aggregates_and_taint` (weight 5)
- `checkpoint_selection` (weight 5)
- `reconciliation_chain` (weight 5)
- `reconciliation_compute` (weight 5)
- `reconciliation_shard_counts` (weight 3)
- `reconciliation_timeline_counts` (weight 3)
- `resume_state_values` (weight 5)
- `stage2_shard_ledger` (weight 5)
- `stage2_step_ledger` (weight 5)
- `stage2_mixture_report` (weight 5)
- `stage2_checkpoint_report` (weight 5)
- `stage2_reconciliation` (weight 5)
- `stage2_resume_state` (weight 5)

Negative tests (4) hold only when the cheat happened. The two source scans read only the string and integer constants of the modules under `src/` (comments, docstrings and the project's tests are skipped) plus any non-Python file shipped under `src/`:

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -5)
- `negative_corpus_path_literal_in_package` (weight -5)
- `negative_nondeterministic_output` (weight -3)

Channel B is 8 criteria (4 positive / 4 negative), positive total 12, negative total 12:

- **R1** (+3, trajectory): The agent confirms that each of the six stage-1 ledger files its package wrote carries a run_control stamp.
- **R2** (+3, trajectory): The agent compares a value its own code computed with a total or reference value stated in the body text or tables of a shipped specification, governance or errata document, other than a control block record count.
- **R3** (+3, trajectory): The agent runs its repaired package with --feed pointing at a directory other than /app/data that holds a copy or variant of the feed.
- **R4** (+3, trajectory): The agent reproduces at least one install or import failure of the shipped runledger package before its first edit to the package source.
- **R5** (-3, trajectory): The agent states in its final response that the repaired package installs with only setuptools and the dependencies its pyproject.toml declares while every install of the package in its trajectory ran in an environment that also exposes the machine's other installed packages.
- **R6** (-1, trajectory): The agent leaves dead code, duplicated blocks or leftover debugging output in its repairs to the runledger source.
- **R7** (-5, trajectory): The agent states that the ledger reconciles with the control totals while the trajectory holds zero commands that compared them.
- **R8** (-3, trajectory, constraint): The agent writes, copies or edits one of the six stage-1 ledger files under /app/out with a command other than a run of the repaired runledger package with --out /app/out.

The hidden tier regenerates a 98-file stage-2 feed at 1/15 scale from the parameters, seed and opening state stored in `_EVAL_INPUTS_B64`, with the same documented rules (fresh keys, values and trap placements). Every hidden case runs the whole pipeline, so every case exercises at least the key, unit, timestamp, exclusion and schedule rules together.

The stage-2 feed generator is inlined in `tests/test_output.py` as plain functions (`generate_feed` and its helpers; stdlib, openpyxl and pyarrow; no network and no subprocess calls; it writes the feed into the temporary directory it is handed). Two base64 zlib JSON blobs are data and are never executed: `_EXPECTED_B64` holds the expected stage-1 and stage-2 outputs and `_EVAL_INPUTS_B64` the generator inputs.

Expectation provenance: `_EXPECTED_B64` is byte-identical to what the package repaired by `solution/solve.py` writes, on the shipped stage-1 feed and on the stage-2 feed the verifier regenerates (opened from that package's own stage-1 `resume_state.json`), and the stage-2 bytes do not change under another `PYTHONHASHSEED` or with the feed files renamed. The decoding layer is checked independently of that package: on the stage-2 feed, its decoded shard facts, contamination, overflow, rollbacks, checkpoint completeness and tombstones, resolved evaluations, sessions, trainlog records and chain closing all equal the generator's own ground truth (`world["facts"]`). The ledger layer (statuses, timeline, selection, outputs) has no second implementation; it is the reference package's reading of run_spec sections 5 to 11.

Record chain: in both tiers one registry partition (`registry_part09.db`) declares a records count with its last two digits transposed (stage 1: 6639 declared, 6693 counted; stage 2: 474 declared, 447 counted). The chain opens and closes on counted records, so `run_control.records` is unaffected, and `reconciliation.json` reports `ok: false` with that file as its one break. A pipeline that copies declared counts into `counted` fails `reconciliation_chain` and `stage2_reconciliation`.

Precedence fixtures: every adjacent pair of the eval_protocol E4 status order has a graded checkpoint carrying both conditions. Stage 1: ck-s1-003040 is abandoned with one partial rank, ck-s1-002160 is incomplete and tombstoned, ck-s1-000280 is tombstoned and early, ck-s1-000440 is early and unscored. Stage 2 (no early checkpoints exist there): the last complete abandoned checkpoint loses one rank, and the first checkpoint of the resumed segment loses one rank and is tombstoned. Tie-breaks are planted in stage 1: SH0687496 shares the ingest_ts of its duplicate representative SH0018322 (5.5, smaller key wins), SH0374976 shares the ingest_ts of SH0016459, the first member of cluster MH104750 (5.6, then key), and ck-s2-005720 ties the selected ck-s2-005680 at aggregate 0.584405 (E4, lower step wins). Breaking any one of these rules changes a graded output.

### Test to rule trace

| test | rule (file and locator) |
|---|---|
| `package_installs` | instruction.md package.zip sentence (installable src-layout package; plain Python 3.12 with only setuptools and the declared dependencies) |
| `package_shipped_tests_pass` | instruction.md package.zip sentence ("the project's own test suite, kept unchanged and passing") |
| `run_control_stamps` | instruction.md ("including its run control stamp"); run_spec 10.1, 10.8 |
| `shard_ledger_membership` | run_spec 3.1, 4.1, 4.3, 4.4, 10.2 |
| `shard_ledger_sources_and_tokens` | run_spec 4.2, tokenizer_migration 2.1-2.3, errata C4, 10.2 |
| `shard_ledger_contamination_rows` | run_spec 4.9, 5.4, errata C1, decontamination D1-D4, G2 rerun |
| `shard_ledger_duplicate_rows` | run_spec 4.5, 5.3, 5.5, 5.6, G2 archive/v1 |
| `shard_ledger_license_approval_rows` | run_spec 4.6, 4.7, 3.6, license_audit L1, G2 vendor/archive |
| `shard_ledger_consumption` | run_spec 6.5, errata C2, 10.2 |
| `shard_ledger_errata_rows` | run_spec 4.8, Table 4.7, G2 draft |
| `shard_ledger_status_and_representatives` | run_spec 5.1-5.7, 10.2 |
| `step_ledger_status_and_steps` | run_spec 6.3, 6.4, 6.8, 10.3 |
| `step_ledger_tokens_and_loss` | run_spec 6.1, 6.2, 6.6, errata C5, node_operations N2 |
| `step_ledger_learning_rate` | schedule_spec S1, run_spec 7, errata C3, 10.3 |
| `step_ledger_ema` | run_spec 6.7 (quantised every step, rounding half to even) |
| `step_ledger_cumulative_tokens` | run_spec 6.5, errata C2, 10.3 |
| `mixture_report_sources` | run_spec 10.4, Appendix B |
| `checkpoint_statuses` | run_spec 8.1, eval_protocol E4, G2 mirror |
| `checkpoint_aggregates_and_taint` | run_spec 8.2, eval_protocol E1-E3 |
| `checkpoint_selection` | eval_protocol E4, run_spec 10.5 |
| `reconciliation_chain` | run_spec 2.2-2.4, 10.6 |
| `reconciliation_compute` | compute_accounting C1, C2 |
| `reconciliation_shard_counts` | run_spec 5, 10.6 |
| `reconciliation_timeline_counts` | run_spec 6, 10.6 |
| `resume_state_values` | run_spec 10.1, 10.7, 10.8, 11 |
| `stage2_shard_ledger` | instruction.md later-stage sentence; run_spec 5.3, 10.2, 11 |
| `stage2_step_ledger` | run_spec 6.8, 7 carried T, 10.3, 11 |
| `stage2_mixture_report` | run_spec 10.4, 11 |
| `stage2_checkpoint_report` | run_spec 8, 10.5, 11 |
| `stage2_reconciliation` | run_spec 10.1, 10.6, 10.8 (run_control stamp of stage 2) |
| `stage2_resume_state` | run_spec 10.7, 11 |
| `negative_hardcoded_sample_answers` | instruction.md: run on any feed of the same structure |
| `negative_filename_dependent_behaviour` | instruction.md: never by file name; run_spec 2.1 |
| `negative_corpus_path_literal_in_package` | instruction.md: read only the feed and resume state it is given, with no path under `/app/data` written into its code |
| `negative_nondeterministic_output` | instruction.md: identical bytes on every run |

## Root cause

**Two documents, one rule set.** The approved specification is amended clause by clause by the approved errata; the shipped code follows the unamended text (C1 exclusion comparison, C2 overflow consumption, C3 step counting, C4 rounding, C5 loss weighting).

**Scope is declared inside the files.** Fifteen files carry a scope in their control block; governance Table G2 says what of each remains authoritative. Each of them is both bait and the only carrier of a required fact.

**Everything is global.** Included tokens set the schedule length, inclusion sets taint, taint sets the selected checkpoint, the selection sets the cutoff, the cutoff sets consumption and the resume state, and the record chain closing stamps every report. One wrong decision anywhere changes every graded file.

**Red lines.** No answer may be hard-coded, no behaviour may depend on file names, the package may read only the feed and the resume state it is given, and its output must be byte-identical across runs.

## Solution shape

1. Extract `project.zip` to `/app/project` and apply the repairs in `solution/solve.py` (the inverse of every defect above).
2. Archive the repaired tree deterministically as `/app/out/package.zip`.
3. Run `python -m runledger reconcile --feed /app/data --resume /app/data/stage0_close.json --out /app/out`.
4. Run the shipped tests (`solve.sh`).

`solve.py --tolerant` skips absent files, an absent index and absent parameter tables and writes everything still computable; the reference run does not use it.

## Ordered plan

1. Read instruction.md, feed_index.json and the control blocks; reproduce the install and import failures of the shipped package, then fix the build (pyproject, imports, syntax) so it installs on a plain Python 3.12 with only the declared dependencies, without dead code or debugging output left in the repairs. (R4, R6)
2. Read the document register and scope table in governance_precedence.docx before touching scoped files.
3. Read run_spec_v3_2.docx end to end, then errata_register.pdf, and list every amended clause.
4. Fix parsing until every file's counted records equal its control block, except where the feed itself is defective; the chain lists such a file as a break. (R7)
5. Fix shard facts and the exclusion pipeline; check reconciliation counts and duplicate groups against the documented totals. (R2)
6. Fix the timeline: replays, overflow, rollback, loss weighting, schedule, EMA; check per-attempt record counts and checkpoint step alignment. (R2)
7. Fix evaluation resolution, taint and selection; then consumption and resume state.
8. Archive the package, write the ledger by running the package, confirm all six outputs carry their run_control stamp, run the package on a copy of the feed in another directory, run the shipped tests on the final source, and report only the checks actually run. (R1, R3, R5, R8)

### Trap loops

| id | entry | reinforcement | tell | exit | graded impact |
|---|---|---|---|---|---|
| L01 | Newest registry partition wins a key conflict | values look plausible; per-source totals move <1% | feed_index.json routing names a different home; governance G3 | run_spec 4.1 | shard_ledger_sources_and_tokens |
| L02 | Highest row_rev wins inside the home partition, VOID rows included | row_rev ordering already fixes superseded rows | VOID rows hold 2x+7 counts that disagree with their r5 recounts | run_spec 4.1 | shard_ledger_sources_and_tokens |
| L03 | The FINAL registry snapshot is the registry | 95% agreement with the partitions; it even resolves L- references | control scope snapshot; void register lists keys it shows LIVE | governance G2 snapshot | shard_ledger_membership, shard_ledger_sources_and_tokens |
| L04 | The snapshot is a decoy, so it is dropped | leaked tokens look like ordinary loader leakage | L- references resolve nowhere in scope | run_spec 3.1, G2 snapshot | shard_ledger_consumption, mixture_report_sources |
| L05 | First void action decides | VOID then UNVOID rows make plausible void counts | action_seq order in the void register | run_spec 4.3 | shard_ledger_membership |
| L06 | Keys normalised by upper-case and strip only | 99% of keys match | orphan shards without inventory hashes; Appendix A homoglyphs | run_spec 3.1 | shard_ledger_membership, shard_ledger_duplicate_rows |
| L07 | Registry counts are used as r5 tokens | r5 rows and recounts are right | recount vs registry ratio equals Table 2.1 per source | tokenizer_migration 2.1 | shard_ledger_sources_and_tokens |
| L08 | Converted counts round half up | only exact .5 rows differ, totals move by a few tokens | errata C4 | run_spec 4.2 d as amended | shard_ledger_sources_and_tokens, shard_ledger_status_and_representatives |
| L09 | r6 preview counts are newer, use them everywhere | preview equals the r5 count for most non-code shards | G2 preview scope; tokenizer_migration 2.3 adoption list | run_spec 4.2 b | shard_ledger_sources_and_tokens |
| L10 | The preview is a decoy, so it is dropped | code shards fall back to r5 counts that look normal | 2.3: final r6 recount is the count for adopted sources | tokenizer_migration 2.3 | shard_ledger_sources_and_tokens |
| L11 | Latest recount wins regardless of status | provisional rows carry the newest timestamps | tokenizer_migration 2.2 | run_spec 4.2 c | shard_ledger_sources_and_tokens |
| L12 | Recount -1 is a count | few rows, mostly overridden | Table 3.6 sentinel | run_spec 3.6 | shard_ledger_sources_and_tokens |
| L13 | APPROVED errata apply whatever their date | status APPROVED looks final | Table 4.7 cutover | run_spec 4.8 | shard_ledger_errata_rows |
| L14 | Errata revision B is the current register | it repeats revision A with updates | G1 lists rev B as DRAFT | governance G1, G2 draft | shard_ledger_errata_rows |
| L15 | Revision B is a draft, so it is dropped | revision A looks complete | rev B intro and G2: APPROVED-CARRIED entries are approved | governance G2 draft | shard_ledger_errata_rows, shard_ledger_sources_and_tokens |
| L16 | Errata dated on the cutover are excluded | 'before the cutover' reading | 'on or before' in 4.8 | run_spec 4.8 | shard_ledger_errata_rows |
| L17 | Source corrections applied after conversion | only corrected shards differ | 4.2 last sentence | run_spec 4.2 | shard_ledger_sources_and_tokens |
| L18 | Latest inventory scan by raw string compare | most scans are ISO Z | mixed offsets and local columns; UTC comparison rule | run_spec 3.3, 4.5 | shard_ledger_duplicate_rows |
| L19 | Archive inventory ignored | duplicate counts rise plausibly | shards without a hash; G2 archive glacier rows | run_spec 4.5, G2 archive | shard_ledger_duplicate_rows |
| L20 | Archive inventory trusted for every row | it fills the gaps | G2 archive: glacier rows only | governance G2 archive | shard_ledger_duplicate_rows |
| L21 | Hashes compared verbatim | most hashes are plain lower-case | xxh64: tags and case in some rows | run_spec 4.5 | shard_ledger_duplicate_rows |
| L22 | Licence N/A treated the same for every source | N/A looks like missing data | Table 3.6 per source group; Appendix B group column | run_spec 3.6, 4.6 | shard_ledger_license_approval_rows |
| L23 | Vendor manifest classes trusted | 95% agreement | G2 vendor | governance G2 vendor | shard_ledger_license_approval_rows |
| L24 | Vendor manifest dropped | classes already known | revocation sections in the manifest; G2 | run_spec 4.6 | shard_ledger_license_approval_rows |
| L25 | doc_id keyed cards dropped for lack of a key | unapproved is a common status | half of all shards unapproved while card statuses are mostly APPROVED | G2 archive doc_index | shard_ledger_license_approval_rows |
| L26 | Archived cards trusted | newer revisions APPROVED just before cutover | G2 archive: card rows not authoritative | run_spec 4.7 | shard_ledger_license_approval_rows |
| L27 | Serial dates converted from 1900-01-01 and one date system | most approvals far from the cutover | _control date_system; K3; 3.3 day 0 | run_spec 3.3 | shard_ledger_license_approval_rows |
| L28 | Contamination excludes only when overlap exceeds the threshold | this is the approved v3.2 wording | errata C1 | run_spec 5.4 as amended | shard_ledger_contamination_rows |
| L29 | Contamination per shard | most findings are on representatives | duplicates of excluded shards survive; 4.9 content property | run_spec 4.9 | shard_ledger_contamination_rows, checkpoint_aggregates_and_taint |
| L30 | The v4 rerun is the newer scanner | 95% agreement | G2 rerun; D1 v3 only | governance G2 rerun | shard_ledger_contamination_rows |
| L31 | The rerun is dropped | v3 findings look complete | D3: retractions are published with the rerun | run_spec 4.9 | shard_ledger_contamination_rows |
| L32 | Overlap columns read as fractions | fraction files dominate | _pct/_permille names and % markers | run_spec 3.2 | shard_ledger_contamination_rows |
| L33 | Findings on retired keys dropped | few rows | D2; alias register | run_spec 4.4 | shard_ledger_contamination_rows |
| L34 | Duplicates keep the last ingested shard | the superseded v3.1 text says so | G1 3.1 SUPERSEDED; 5.5 earliest | run_spec 5.5 | shard_ledger_duplicate_rows |
| L35 | Local ingest times read as UTC | ordering mostly preserved | control tz; 3.3 | run_spec 3.3 | shard_ledger_duplicate_rows |
| L36 | Stage 1 ignores seen_hashes | stage 1 looks self-contained | stage0_close.json hashes equal current content hashes | run_spec 5.3 | shard_ledger_duplicate_rows, stage2_shard_ledger |
| L37 | v1 cluster file used | same cluster ids | G2 v1 | governance G2 v1 | shard_ledger_duplicate_rows |
| L38 | v1 file dropped | v2 clusters look complete | dissolved list in v1; 4.10 | run_spec 4.10 | shard_ledger_duplicate_rows |
| L39 | Planned epochs from the newest policy table (draft 3.3) | most rows agree | G1 3.3 DRAFT; Appendix B | run_spec Appendix B | step_ledger_learning_rate, mixture_report_sources |
| L40 | keep_k ignored | one survivor per cluster is the usual MinHash rule | Appendix B keep_k | run_spec 5.6 | shard_ledger_duplicate_rows |
| L41 | Replays counted | loss column unchanged because replays copy losses | attempt tokens exceed nominal tokens_per_step by a micro-batch | run_spec 6.2 | step_ledger_tokens_and_loss |
| L42 | Windows closed at both ends | few records dropped | nine-or-seven records per attempt at window ends; half-open rule | run_spec 6.2 | step_ledger_tokens_and_loss |
| L43 | Floating and TZID calendar times read as UTC | UTC events dominate | C2 site_tz rule; DST-spanning sessions | compute_accounting C2 | reconciliation_compute, step_ledger_tokens_and_loss |
| L44 | Replay dump trusted as n07's log | it covers the whole run | G2 replay; attempts with two n07 records | governance G2 replay | step_ledger_tokens_and_loss |
| L45 | Replay dump dropped | primary n07 logs look complete | TRUNCATION alert window; attempts with seven records | N3, G2 replay | step_ledger_tokens_and_loss |
| L46 | Aggregate log used as the single source | all nodes in one file | G2 aggregate | governance G2 aggregate | step_ledger_tokens_and_loss |
| L47 | Aggregate log dropped | node ids present elsewhere | trainlog_part11.txt identifies nodes by host; node_field host | run_spec 6.1 | step_ledger_tokens_and_loss |
| L48 | Attempt loss as mean of node means | within 1e-4 of the right value; the draft 3.3 says so; worked example agrees | errata C5 | run_spec 6.6 | step_ledger_tokens_and_loss, step_ledger_ema, step_ledger_cumulative_tokens |
| L49 | Retractions matched verbatim | most retractions match | Message-ID rule; checkpoint steps no longer multiples of 40 | run_spec 6.3 | step_ledger_status_and_steps |
| L50 | Schedule counted in attempts | global step is the common framework counter; worked example has no overflow | errata C3; checkpoint registry steps | schedule_spec S1 | step_ledger_learning_rate |
| L51 | Overflow tokens not consumed | v3.2 6.5 says so | errata C2 | run_spec 6.5 as amended | step_ledger_ema, step_ledger_cumulative_tokens, shard_ledger_consumption |
| L52 | Rollback ignored | monotonic steps within segment 1 | ROLLBACK alert; duplicate optimizer steps across segments | run_spec 6.4 | step_ledger_status_and_steps |
| L53 | Draft ROLLBACK used | it arrives first | RETRACT of the draft alert | run_spec 6.3, 6.4 | step_ledger_status_and_steps |
| L54 | Rank rows counted, not ok ranks | 64 rows present | partial status; Table 3.6 | run_spec 8.1 | checkpoint_statuses |
| L55 | Mirror ranks used | same schema | G2 mirror; lag | governance G2 mirror | checkpoint_statuses |
| L56 | Mirror dropped | registry ranks look complete | tombstones table; 8.1 | run_spec 8.1 | checkpoint_selection |
| L57 | Consolidated score sheet used | one place, every checkpoint | G2 consolidated; abandoned checkpoints listed | governance G2 consolidated | checkpoint_aggregates_and_taint |
| L58 | Consolidated workbook dropped | ckpt-keyed evals exist elsewhere | R- runs resolve only through run_map | run_spec 8.2 | checkpoint_aggregates_and_taint, checkpoint_selection |
| L59 | Leaderboard dropped | public rows are elsewhere | private benchmarks unscored everywhere else | eval_protocol E1, G2 leaderboard | checkpoint_aggregates_and_taint |
| L60 | v3.1 dropped as superseded | it is superseded | H1- runs resolve only through Appendix H | G2 superseded | checkpoint_aggregates_and_taint |
| L61 | First evaluation row wins | reruns look like duplicates | invalid and older runs; 8.2 latest ok | run_spec 8.2 | checkpoint_aggregates_and_taint |
| L62 | Taint over every shard | contamination findings exist anyway | E3: included shards only | eval_protocol E3 | checkpoint_aggregates_and_taint |
| L63 | Total steps recomputed in stage 2 | stage 1 outputs are all correct | run_spec 7 carried T | run_spec 7 | stage2_step_ledger |
| L64 | EMA quantised only when written | differences appear late in the ledger | 6.7 quantise every step | run_spec 6.7 | step_ledger_ema, step_ledger_cumulative_tokens |
| L65 | Resume seen_hashes from this stage only | stage 1 ledger unaffected | 11: opening list plus included hashes | run_spec 11 | resume_state_values, stage2_shard_ledger |
| L66 | A count that disagrees with the control block is a parser bug, so the parser is bent until it agrees (or counted is copied from records) | 99 files agree once the parsers are right | registry_part09.db is a plain sqlite table whose row count is unambiguous | run_spec 2.3, governance G3 | reconciliation_chain, stage2_reconciliation |

### Expert time estimate (3 to 4 days)

- Reading the specification, errata, governance, protocol and handbook documents: 5 h.
- Build repair and parsers for 20 formats with drift, encodings, units and sentinels, checked against 99 control blocks: 7 h.
- Shard facts: precedence, voids, aliases, errata, recounts, r6 adoption, hashes, licences, cards: 5 h.
- Exclusion pipeline with content groups, cross-stage and near duplicates: 3 h.
- Timeline: replays, overflow, rollback lineage, token-weighted loss, EMA, schedule: 5 h.
- Checkpoints, evaluation resolution through three crosswalks, taint and selection: 3 h.
- Decoy mechanisms (15), each found from Table G2 and verified: 3 h.
- Output contract, determinism, filename independence, stage-2 robustness and self-checks: 4 h.
Total about 35 working hours.

## Pitfalls

- Newest registry partition wins a key conflict: fails `shard_ledger_sources_and_tokens`.
- Highest row_rev wins inside the home partition, VOID rows included: fails `shard_ledger_sources_and_tokens`.
- The FINAL registry snapshot is the registry: fails `shard_ledger_membership`.
- The snapshot is a decoy, so it is dropped: fails `shard_ledger_consumption`.
- First void action decides: fails `shard_ledger_membership`.
- Keys normalised by upper-case and strip only: fails `shard_ledger_membership`.
- Registry counts are used as r5 tokens: fails `shard_ledger_sources_and_tokens`.
- Converted counts round half up: fails `shard_ledger_sources_and_tokens`.
- r6 preview counts are newer, use them everywhere: fails `shard_ledger_sources_and_tokens`.
- The preview is a decoy, so it is dropped: fails `shard_ledger_sources_and_tokens`.
- Latest recount wins regardless of status: fails `shard_ledger_sources_and_tokens`.
- Recount -1 is a count: fails `shard_ledger_sources_and_tokens`.
- APPROVED errata apply whatever their date: fails `shard_ledger_errata_rows`.
- Errata revision B is the current register: fails `shard_ledger_errata_rows`.
- Revision B is a draft, so it is dropped: fails `shard_ledger_errata_rows`.
- Errata dated on the cutover are excluded: fails `shard_ledger_errata_rows`.
- Source corrections applied after conversion: fails `shard_ledger_sources_and_tokens`.
- Latest inventory scan by raw string compare: fails `shard_ledger_duplicate_rows`.
- Archive inventory ignored: fails `shard_ledger_duplicate_rows`.
- Archive inventory trusted for every row: fails `shard_ledger_duplicate_rows`.
- Hashes compared verbatim: fails `shard_ledger_duplicate_rows`.
- Licence N/A treated the same for every source: fails `shard_ledger_license_approval_rows`.
- Vendor manifest classes trusted: fails `shard_ledger_license_approval_rows`.
- Vendor manifest dropped: fails `shard_ledger_license_approval_rows`.

## Provenance

```yaml
uuid: 725e575c-62c9-5e28-a103-27072945bca6
instance_id: 725e575c-62c9-5e28-a103-27072945bca6
task_name: terminal-bench/725e575c-62c9-5e28-a103-27072945bca6
fix_patch_sha256: ecc8dba2282240bcc0dd7dd9b6d3947db2e69207805a4e1232280ed8136d97ac  # sha256 of solution/solve.sh
solve_py_sha256: 29c62366d1309b502788ece67cb9f70efdcf73b34336ae7a9ec8876562ac9fc2  # informational; solve.py is 225 lines
language: python
golden_score_measured: null  # not yet measured
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: null
caveat: >
  The test channel carries 31 positive checks worth 145 weight and 4
  negative checks worth -18 weight, so on its own it ranges -18/145 = -0.124
  to +1.000. The judged channel carries 8 criteria worth 12 positive
  points and 12 negative points. tests/reward.toml divides each channel's weighted sum by its
  positive total and gives each half of the reward, so the combined reward
  runs from -18/290 - 12/24 = -0.562 to +1.000 with no clamp.
```
