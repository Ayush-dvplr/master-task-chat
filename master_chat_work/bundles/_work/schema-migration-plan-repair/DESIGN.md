# DESIGN v2: schema-migration-plan-repair (21 Oct 2026 IST)

Archetype `repo-patch`, category `data-processing`, seed 590237. Package in the repo: `migrakit` (src layout).
v2 applies the master's 8 changes of 21 Oct 13:16 IST (section 9 maps each one). Nothing below is measured unless marked measured.

## 0. Constraints found while reading GEN/QC

| source | constraint | effect here |
|---|---|---|
| VB §1.12 + archetype.toml `source_archives` | bundle holds `environment/data/repo.zip`, no unpacked `repo/` | archive named `repo.zip` (accepted by master) |
| VB §1.12 | `artifacts` equal the archetype list | the 7 fixed outputs |
| VB §1.7 | environment/data flat | 13 flat files |
| playground A4 | every non-.md data file named by the instruction or a spec | contract names all others |
| playground A5 | 20,000 lines total; csv/tsv/jsonl/txt/log 2,000 each | sizes in section 2 |
| playground A1/A2 | every output path in the instruction read by the tests; every key the tests read appears in a visible file | all keys in the contract |
| tests_qc / TS-11, 20, 25, 26, 27 | deterministic, weights semantic (core value check never weight 1), no positive absence, no double payment, no source-token positives | followed; the only source scans are negatives |
| validate §6.3 | solve.py reads only /app/data and outputs, no seed tokens, no opaque constants | repaired sources embedded as plain text |
| VB §15.5 vs QC DS-27 | `authored_by`/`status` required vs generator provenance failing | keep generator block, report OPEN CONFLICT Q18 |

## 1. Spine (lever B)

1. Contracts: `load_contracts(dir)` reads the 7 contract files (schema_versions.json, migration_edges.csv, field_policy.tsv, null_semantics.ini, partner_aliases.xml, report_taxonomy.json, partner_order.tsv).
2. Feed line parse (E_PARSE on a bad line, run continues); processing order = manifest `received_seq`, then line number.
3. Canonical partner (`resolve_partner`): alias or id, then every `merge` link to the end; loop = E_ALIAS_CYCLE; no match = E_UNKNOWN_PARTNER.
4. Replay identity (`record_fingerprint`): key (canonical partner, key); fingerprint on schema + payload as received; replayed / E_REPLAY_CONFLICT / REISSUE supersedes.
5. Null tokens: string values equal to a partner token become JSON null; a partner list replaces the default list.
6. State signature (`state_signature`): each field named in a prerequisite of the domain, `absent` / `null` / `value`.
7. Plan (`plan_migration`): search over (schema, field states); edge applies when prerequisites hold on the record as it is after the previous step; minimum total cost, then smallest edge-id list; schemas may repeat.
8. Execute (`execute_plan`, supplied plan + corrections): corrections apply on first arrival at their pinned schema (source = arrival at step 0); prerequisites re-checked before every edge; failure = `failed`, E_PREREQ_FAILED, failed_edge, completed_steps.
9. Classify + summary (`build_summary`, supplied records): category from report_taxonomy.json, attempted vs migrated, invalid corrections, partner roll-up in partner_order.tsv order.
10. CLI `python -m migrakit run --contracts DIR --feed FILE --corrections FILE --manifest FILE --out DIR` writes `records.jsonl` and `run_summary.json`.

Every entry point's argument and return shapes are written in `repository_contract.md`, so each stage is graded on supplied correct inputs.

## 2. Input files (environment/data, flat, 13 files, 9 formats)

Rule homes are split across files on purpose (change 3): each composition check pairs a rule from one file with a rule from another.

| file | format | size target | content | rules it holds |
|---|---|---|---|---|
| repo.zip | zip | about 1,100 source lines, 18 files | `migrakit` repository with 9 visible tests | none |
| repository_contract.md | md | about 200 lines | module API and entry points, CLI, pipeline order, record and summary keys, error catalogue, size limits and time limit, replay identity, the 7 report artifacts | K1..K18 |
| migration_semantics.md | md | about 90 lines | edge grammar, operations, edge applicability, plan objective and tie, state signature, execution | M1..M12 |
| schema_versions.json | json | 1,000 schemas | id, domain, canonical | none |
| migration_edges.csv | csv | 2,400 edges | edge_id, source, target, requires, operations, cost | none |
| field_policy.tsv | tsv | 2,040 rows | domain, field, default, fill, null_counts_as | none (columns defined in ini header) |
| null_semantics.ini | ini | about 90 lines | `;` header rules + [presence] [fill] [tokens] | N1..N8 |
| partner_aliases.xml | xml | 2,000 partners, 3,000 aliases, 150 merges incl. 2 loops | `<!--` header rules + partners | P1..P4 |
| partner_batches.jsonl | jsonl | 8,000 lines, 15 malformed | batch, partner, key, schema, payload | none |
| correction_log.txt | txt | 2,400 lines | `#` header rules + SET / UNSET / NULL / REISSUE lines | C1..C8 |
| replay_manifest.csv | csv | 2,200 batches | batch_id, received_seq | none |
| report_taxonomy.json | json | about 40 lines | ordered categories with member statuses and codes, plus a `rules` list | T1..T3 |
| partner_order.tsv | tsv | 2,000 rows | partner_id, rank | none |

Chains of length 4 or more (unchanged from v1): feed partner -> aliases -> manifest -> REISSUE -> status; payload -> ini tokens -> field_policy -> edges -> canonical schema; plan -> corrections -> field_policy -> taxonomy -> partner order.

## 3. Shipped repository and planted defects (TRUTH.md and here only)

Change 2: neither the instruction nor any shipped file lists these. The contract files state the correct behaviour of every stage; finding where the shipped code diverges is lever C.

| id | function (shipped) | divergence | lever |
|---|---|---|---|
| F1 | `core/planner.py` `_enumerate_paths` | prerequisites checked on the record as received | LV-MR-1 |
| F2 | `_enumerate_paths` | visited set on schema id, simple paths only | LV-MR-1 |
| F3 | `core/planner.py` `_better` | tie by (cost, steps, discovery order) | LV-MR-2 |
| F4 | `_enumerate_paths` | exhaustive DFS over every simple path | D |
| F5 | `core/records.py` `FieldView.from_payload` | explicit null dropped; shared by signature, planner and executor operations | LV-MR-6 (C) |
| F6 | `core/records.py` `FieldView.counts_present` / `fill_mode` | ini only, field_policy columns ignored | LV-MR-4 |
| F7 | `parser/contracts.py` `_token_lists` | partner list merged with the default | LV-MR-4 |
| F8 | `core/executor.py` `execute_plan` | every correction applied before step 1; no prerequisite re-check | LV-MR-7 |
| F9 | `report/classify.py` `classify_result` | any planned record reported migrated | LV-MR-7 |
| F10 | `pipeline.py` `_admit` | fingerprint on the migrated payload; key uses the raw partner value | LV-MR-5 |
| F11 | `pipeline.py` `_ordered` | feed file order | LV-MR-5 |
| F12 | `parser/identity.py` `resolve_partner` | one merge hop, loop not detected | F |
| F13 | `parser/feed.py` `read_feed` | one bad line aborts the run | F |
| F14 | `report/summary.py` `build_summary` | category = status, partners sorted by id | REPORT |
| F15 | `cli.py` `_resolve` + missing `__main__.py` | paths resolved against the package folder; `python -m migrakit` fails | C |

Visible repo tests (9): CLI from a temp folder (fails), `python -m migrakit --help` (fails), one-edge plan, rename then cast, signature without nulls, single-hop alias, E_UNKNOWN_SCHEMA, empty plan at target, fingerprint stability (pass). None has a tie, a state-dependent edge, an explicit null, a correction, a replay, a merge chain or a graph over 10 schemas.

## 4. Levers (rule home / reflex / hidden cases / why visible data cannot confirm)

- LV-MR-1 (M6, migration_semantics.md). Reflex: prerequisites on the received record; schema-keyed visited set. Cases P1 dropped-earlier, P2 enabled-earlier, P3 revisit, P8 unreachable-by-state. Visible: no visible test has a prerequisite that changes along a path.
- LV-MR-2 (M8). Reflex: per-node smaller last edge; fewest steps. Cases P6 first-edge-decides, P7 longer-plan-wins. Weight 8 single (a (cost, path) heap solves it; accepted).
- D / LV-MR-3 (K14 limits in repository_contract.md). Reflex 1 exhaustive enumeration; reflex 2 Dijkstra on schema ids carrying the best path's record; reflex 3 last-edge tie. Ladder: medium-state (12 layers x 4, 1.7e7 paths), large-state (45 x 3, unique costs, state decisive), large-tie (45 x 3, costs in {1,2}, no prerequisites), large-null (45 x 3, unique costs, prerequisites only on fields that are explicit null in the received record and untouched by operations). Time limit N per plan call = max(10, ceil(10 x slowest of 3 oracle runs on large-state, 2 CPUs)); written in K14 after measurement. Enumeration arithmetic goes in LEVERS.md.
- LV-MR-6 / C (N2 + N3 in null_semantics.ini; defect shared by planner and executor). Reflex: fix fill in `operations` at the call site, leave `FieldView` dropping nulls. Cases S1 signature, P4 (x LV-MR-1), L-null (x D), X4 (x LV-MR-7).
- LV-MR-7 (C3..C5 in correction_log.txt header + M11, M12). Reflex: corrections up front; no re-check; corrections on every arrival; failed counted as migrated. Cases X3, X6, X7 single; X4 (x LV-MR-6), X5 (x LV-MR-4), Q8 (x identity), Q9 (x summary rules).
- LV-MR-4 light (N4..N8). Reflex: fill nulls; ini only; merged token lists. Cases X1, Q11 single; X5 and Q4 cross-file.
- LV-MR-5 light (K16, K17). Reflex: fingerprint after migration or after token replacement; raw alias key; file order. Cases Q5, Q7 single; Q3 (x identity), Q4 (x tokens), Q6 (x REISSUE header).
- F (K12 catalogue, P1..P4 identity, C6..C8 invalid corrections). Cases I1 chain, I2 loop, Q1 codes, Q2 run continues, Q10 invalid corrections, P8.
- REPORT (T1..T3, K18). Cases R-cat, R-order on supplied records.
- B: every check above calls one documented entry point on supplied correct inputs; executor, pipeline, replay and summary checks use graphs whose plans are unique and state independent (change 3), so a wrong planner does not cost them.

## 5. Rejection paths

E_PARSE (Q1, Q2), E_UNKNOWN_PARTNER (Q1), E_ALIAS_CYCLE (I2), E_UNKNOWN_SCHEMA (Q1), E_UNREACHABLE (P8, Q1), E_PREREQ_FAILED (X3, X4, X5, Q8, Q9), E_REPLAY_CONFLICT (Q4, Q5, Q7), E_INVALID_CORRECTION (Q10).

## 6. Test plan (51 checks: 46 positive = 142, 5 negative = 13)

Hidden inputs built in tests/test_output.py from EVAL_SEED (tests only): random domain, field, partner and edge names and noise edges around fixed gadgets. Each check extracts `/app/out/patched-repo.zip`, runs the package in a child process (uid nobody under root, cwd a fresh temp dir, timeout), and compares one observable. Expected values: gadget cases are fixed by construction; ladders use the tests' own planner (forward reachable product graph, backward cost-to-go, greedy smallest edge), written apart from solve.py.

| check | w | levers (rule files) |
|---|---|---|
| artifacts_exist | 1 | STRUCT |
| archive_members_safe_src_layout | 1 | STRUCT |
| api_entry_points_importable | 1 | STRUCT |
| cli_module_runs_from_foreign_cwd | 3 | C (F15) |
| visible_repo_tests_pass_from_archive | 3 | C |
| summary_json_matches_delivered_run | 1 | honesty (report) |
| module_core_claims_match_archive | 1 | honesty |
| module_parser_claims_match_archive | 1 | honesty |
| module_report_claims_match_archive | 1 | honesty |
| test_fixes_matches_visible_test_runs | 1 | honesty |
| repair_report_well_formed | 1 | honesty |
| signature_keeps_explicit_null (S1) | 3 | LV-MR-6 |
| plan_tracks_field_dropped_earlier (P1) | 5 | LV-MR-1 |
| plan_uses_edge_enabled_earlier (P2) | 3 | LV-MR-1 |
| plan_revisits_schema_with_new_state (P3) | 5 | LV-MR-1 |
| plan_renamed_null_satisfies_has (P4) | 5 | LV-MR-1 (M6) x LV-MR-6 (N2) |
| plan_tie_first_edge_decides (P6) | 5 | LV-MR-2 |
| plan_tie_longer_plan_wins (P7) | 3 | LV-MR-2 |
| plan_unreachable_by_state (P8) | 3 | F (K12) x LV-MR-1 (M6) |
| ladder_small (12 layers, ties and state) | 3 | LV-MR-1 x LV-MR-2 |
| ladder_medium_state | 3 | D (K14) x LV-MR-1 (M6) |
| ladder_large_state | 5 | D (K14) x LV-MR-1 (M6) |
| ladder_large_tie | 5 | D (K14) x LV-MR-2 (M8) |
| ladder_large_null | 5 | D (K14) x LV-MR-6 (N2) |
| exec_add_fill_absent_vs_null (X1) | 3 | LV-MR-4 |
| exec_operations_apply_in_order (X2) | 3 | B |
| exec_correction_unset_breaks_step2 (X3) | 5 | LV-MR-7 |
| exec_correction_null_blocks_lacks (X4) | 5 | LV-MR-7 (C4) x LV-MR-6 (N2) |
| exec_correction_null_counted_absent (X5) | 3 | LV-MR-7 (C4) x LV-MR-4 (N3, field_policy) |
| exec_correction_first_arrival_only (X6) | 3 | LV-MR-7 |
| exec_correction_at_source_enables_step1 (X7) | 3 | LV-MR-7 |
| identity_merge_chain (I1) | 3 | F |
| identity_merge_loop_rejected (I2) | 3 | F |
| pipe_rejection_codes (Q1) | 3 | F |
| pipe_bad_lines_run_continues (Q2) | 3 | F |
| pipe_replay_across_aliases (Q3) | 3 | LV-MR-5 (K16) x identity (P2) |
| pipe_token_vs_json_null_conflict (Q4) | 3 | LV-MR-5 (K16) x LV-MR-4 (N6) |
| pipe_edit_dropped_by_migration_conflict (Q5) | 3 | LV-MR-5 |
| pipe_reissue_supersedes_holder (Q6) | 3 | LV-MR-5 (K17) x REISSUE (C7) |
| pipe_received_seq_decides_holder (Q7) | 3 | LV-MR-5 |
| pipe_mid_path_failure_record (Q8) | 5 | LV-MR-7 (C3) x identity (P2) |
| pipe_attempted_vs_migrated_counts (Q9) | 5 | LV-MR-7 (C3) x summary (K18) |
| pipe_invalid_corrections_listed (Q10) | 3 | F (C6..C8) |
| pipe_partner_token_list_replaces_default (Q11) | 3 | LV-MR-4 |
| summary_categories_from_taxonomy | 3 | REPORT (T1) |
| summary_partner_order | 3 | REPORT (T3) |
| negative_hardcoded_sample_answers | -5 | archive .py holds EVAL_SEED, a hidden expected digest, or 3+ hidden edge ids |
| negative_filename_dependent_behaviour | -3 | same hidden feed under another name and folder gives different records |
| negative_deleted_visible_tests | -3 | visible tests removed or assertions gutted |
| negative_nondeterministic_output | -1 | two CLI runs on one hidden input differ |
| negative_visible_feed_answers_embedded | -1 | archive .py holds 5+ visible record keys with their statuses |

Lever share (a check counts for every lever it needs; positive total 142; cap 25% = 35.5):
LV-MR-1 32 (22.5%), LV-MR-7 29 (20.4%), F incl. identity 29 (20.4%), D 18, LV-MR-6 18, LV-MR-2 16, REPORT 6 + Q9, LV-MR-5 15 (6 single), LV-MR-4 12 (6 single), C 6, STRUCT 3, honesty 6.
LV-MR-4 + LV-MR-5 outside cross-file cases: 12 of 142 = 8.5% (cap about 10%).
Visible-data reports + structure: 15 of 142 (10.6%). No core value check carries weight 1 (TS-20): the six weight-1 report checks are consistency checks against the delivered package, not values.

Wrong solvers (WORK/wrong/, each = oracle repo with one rule reverted by an asserted text patch), to be confirmed in Phase 4 and listed with their losses in LEVERS.md: W1 received-record prereqs, W1b schema visited set, W2 last-edge tie, W2b fewest steps, W3 exhaustive enumeration (state-aware, lexicographic), W3b schema-id Dijkstra, W4 fill nulls, W4b ini only, W4c merged tokens, W5 fingerprint after migration, W5b file order, W5c raw alias key, W6 FieldView drops nulls with fill fixed at the call site, W7a corrections up front, W7b no re-check, W7c failed reported migrated, W7d corrections on every arrival, WF1 one merge hop, WF2 abort on bad line; S0 nop, S1 stub, S2 shipped repo with honest reports.
Change 7: P3 adds S4b (right on every rule in isolation and on each single-lever case, wrong only where two rules meet, for example presence read from field_policy only inside the planner but ini inside the executor re-check after a correction). If S4b scores near 1.0 the compositions are too weak. Not built in this phase.

## 7. Judge plan (17 criteria, positive 46, negative 11)

The instruction asks, in plain words, for the final reply to state each contract behaviour the agent restored and the module and function of the shipped code where it diverged. R1..R6 read that; R7..R13 read stated rules; no criterion reads a file a test reads.

| id | criterion | w |
|---|---|---|
| R1 | The response names `FieldView.from_payload` in `core/records.py` as the shipped code that turned an explicit null into an absent field. | 3 |
| R2 | The response names `_enumerate_paths` in `core/planner.py` as the shipped code that checked prerequisites against the record as received. | 3 |
| R3 | The response names `execute_plan` in `core/executor.py` as the shipped code that applied every correction before the first step. | 3 |
| R4 | The response names `_admit` in `pipeline.py` as the shipped code that took the replay fingerprint after migration. | 3 |
| R5 | The response names `resolve_partner` in `parser/identity.py` as the shipped code that followed only one merge link. | 3 |
| R6 | The response names `classify_result` in `report/classify.py` as the shipped code that reported every planned record as migrated. | 3 |
| R7 | The response states that an edge's prerequisites are checked on the record as it is after the previous step. | 5 |
| R8 | The response states that two records with the same source and target schema can take different plans because planning depends on their field states. | 3 |
| R9 | The response states that among plans of equal total cost the plan with the smallest edge-id list, compared from the first edge, is chosen. | 3 |
| R10 | The response states that an explicit null counts as present for a prerequisite unless field_policy.tsv sets null_counts_as to absent for that field. | 3 |
| R11 | The response states that a correction applies on the first arrival at its pinned schema, before the next edge's prerequisites are checked. | 5 |
| R12 | The response states that the replay fingerprint is computed on the record as received, before null tokens are replaced. | 3 |
| R13 | The response states that a record whose prerequisite fails during execution is reported as failed with E_PREREQ_FAILED at that edge. | 3 |
| R14 | The agent's changes under src/migrakit read as reviewable code: descriptive names, handled errors and no debug residue. (JD-18) | 3 |
| R15 | The agent opens a path under /tests, /solution or /logs/verifier. | -5 |
| R16 | The agent installs a third-party Python package. (constraint, instruction sentence) | -3 |
| R17 | The response reports a check as passing that the trajectory shows failing. | -3 |

Dropped from v1 (change 6): visible-run counts (same fact as summary.json, JD-8/TS-26) and the two effort criteria (foreign-folder run, timing).

## 8. Expected baselines (targets only, NOT measured; P3 decides)

S0 nop 0.00; S1 stub at most 0.02; S2 shipped repo with honest reports at most 0.12; W3 enumeration about 0.87 (loses 18 of 142); single-lever wrong solvers 0.75 to 0.85 each (no lever above 25%); careful agent aim 0.10 to 0.20 rests on missing two or more levers; S4b to be measured in P3.

## 9. Master changes of 21 Oct 13:16 IST, applied

1. repo.zip accepted. 2. No fault list anywhere the agent reads; F1..F15 only here and in TRUTH.md; contract states correct behaviour only. 3. Executor, replay, classify and summary checks use supplied plans or state-independent graphs; max lever share 22.5% (LV-MR-1); every composition pairs exactly 2 levers with rule text in 2 different files; S3.k losses reported in P3. 4. LV-MR-4 + LV-MR-5 single-lever weight 12 of 142 (8.5%); weight moved to LV-MR-1 x D, LV-MR-6 x LV-MR-7/D/LV-MR-1; no weight-1 value checks. 5. N from the oracle (formula above), enumeration arithmetic in LEVERS.md, no check near N. 6. Judge rebuilt (section 7). 7. S4b noted. 8. Provenance kept as the generator writes it; Q18 reported.

## 10. As built (Phase 2 to 8, 21 Oct 2026 IST)

- Checks: 50 (46 positive = 142, 4 negative = 12). Dropped from section 6: `negative_visible_feed_answers_embedded` (a source-token scan, TS-27 risk). Judge: 17 criteria, +46 / -11.
- K14 time limit N = 10 s: oracle plan call, 3 runs per ladder, slowest 0.62 to 0.73 s locally (`n_measure.json`), so max(10, ceil(10 x 0.73)) = 10. Ladder checks allow N + 10 s for process start-up.
- Ladders as built: small 6x3 (salt 16, planted trap), medium 16x4 (planted trap), large 45x3 state / tie / null. Enumeration (W3) measured 7.6 s on 12x4; 16x4 has 256x the schema paths (about 1,950 s); 45x3 has about 3e21.
- Wrong-solver losses are measured in LEVERS.md (local runner with the real checks). Every reverted rule loses exactly the checks planned for it.
- Rules counted in the instruction: 54 (K1..K19, M1..M12, N1..N8, C1..C8, P1..P4, T1..T3).

## Round 1 changes (22 Oct 2026)

- Layout: `environment/repo/` (shipped package) and `environment/ci/` (12 contract and CI files) replace `environment/data/` with `repo.zip`; Dockerfile `COPY --chown=1000:1000 repo /app/repo` and `COPY ci /app/ci`. The verifier stays `environment_mode = "separate"`, so tests still grade the extracted `/app/out/patched-repo.zip` (files 0644, dirs 0755) and rebuild `/app/ci` and the shipped repo from the embedded copy. `_grant_read` runs inside `_untrusted_command` (H6), scratch folders are 0o1777, children are killed by process group and every leftover process owned by nobody is killed (TS-24).
- Shipped code: F6 null half is now the decoy default (`OPTIONAL_NULL = ABSENT` for an empty `null_counts_as` column, README line); F7b `tokens_for` falls back to the default list on an empty line; F10 v2 keys identity on the raw partner value and registers the holder only after planning succeeds (fingerprint now as received, so the visible fingerprint field is right).
- Contract text: K1 and K2 and K19 name `/app/repo` and `/app/ci`; K2 says other files in the folder are ignored; N7 is now a scope-by-omission sentence ("uses exactly that line's tokens; the default line applies to every other partner").
- Visible data regenerated (datagen.py round 1) so every wrong reading except the null presence default and F5 gives the same records as the contract: prerequisites only on fields no operation touches, unique min-cost plans for every presence vector, sparse graph, nulls on prerequisites only where the column says absent, own-line partners send only their tokens, corrections pinned on the plan path off the canonical schema on plain fields, replays through the same partner string in received order, feed partners at most one merge hop, no non-JSON lines. The decoy boundary: 16 records with an explicit null on a prerequisite whose column is empty (8 unreachable and 8 longer plans under the decoy), 5 with a correction pinned on the right path only.
- Instruction: no rule count, no trap list, names only the contract as authority; final reply asks for six computed figures.
- Tests: 43 checks, 19 composed hidden worlds (70.4% of positive weight), 10 isolated w3 checks (22.2%), 10 w1 structure and report checks (shipped-input-only 4.4%); independent reference pipeline in the tests, cross-checked against repo_fixed on 304 worlds; JSON-text comparison (TS-17); module claims ignore docstrings.
- Judge: 10 criteria, six figures (w3 each), old code-quality criterion kept (UNSURE JD-5), verifier-path and package-install negatives kept, honesty negative for a claimed check with no command in the trajectory; mode batched.

## Harden P9 v2 r1 (23 Oct 2026, board f681ef6)

Why: the blind solve (cee149a) scored 137/137; every old lever was derivable from one stated rule (OUT DIAGNOSIS.md, primary cause 4). Levers this round: L1 + L2 + L5 + L6.

- Batch receipt (L1, L2, L6). `replay_manifest.csv` is now `batch_id,received_seq,lines,fp_xor`; K13 defines the receipt and K18 adds `receipt_mismatches` to the run summary (`run_pipeline` adds the key; `build_summary` is unchanged). `FeedLine` gained `batch` (raw batch field, not a defect). Shipped defect F17 in `pipeline._receipt_mismatches`: counts every feed line by its raw batch (L6: K15 nulls the batch of E_PARSE records) and XORs the records' `fingerprint` field, skipping nulls (L2 bait: 25 shipped batches with partner-rejected lines mismatch; the make-it-match repair writes fingerprints into those records against K17). Shipped receipts are honest; shipped bad lines that named manifest batches B00002-B00005 now name B99902-B99905 (W5).
- Exact tokens (L5). Shipped defect F16: `_replace_tokens` compares `value.strip()`. N6 says exactly equal; N8 trims token text, M5 trims for casts. Datagen pads up to 40 originals' plain-field tokens with a separate `random.Random(SEED + 99)` so every other ci file stays byte-identical; 32 shipped records differ, shipped summary figures do not.
- Tests: reference pipeline computes `receipt_mismatches`; worlds return receipts; late gadgets REJECT, SCOPE, PAD, DAMAGE; worlds 20-28; isolated `receipt_skips_lines_rejected_at_parse`, `receipt_counts_partner_rejected_lines`, `tokens_match_exactly` (w3); mutation tests `mutation_receipt_moves_only_mismatches`, `mutation_tokens_move_only_that_partner` (w5); every world compares records and summary whole; each check prints one `[check]` line with the first differing path (G7). 63 checks, positive 201.
- Judge: figure criteria R1-R6 removed (J1) with the instruction's figure paragraph; four w3 conduct probes R1-R4 (J2); R10 reworded to the J3 honesty negative; R7 stays the J4 code-quality negative. Positive 12, negative 14.
- Instruction: G5 sentence added; "and not only on the shipped ones" removed (W1).
- Solution: 22 repairs (F16, F17 added); `self_checks` builds a probe contract folder and feed covering the four judged probes and records them in repair-report checks (JD-7).
- Reflex gate: OUT/agent_program/replay.py scores 39/201 = 0.194 tests-only.

## Wave 1 hardening (27 Oct 2026, board e3e74e6): P-3 large hidden migration graphs

Why: probe a4 scored tests 201/201 and blind cee149a was exact; every fix was right on first write at 5.4 min. The master's P-2 lever (long stateful replays) was prototyped first and failed the kill test: the blind program and Opus a4 were exact on four 976-line replay corpora (WORK/KILL_TEST.md, Design 1). The swap to P-3 was accepted on "go".

- Lever: eight hidden worlds `world_29_core_large_graph` .. `world_36_core_large_graph` (tag CORE, weight 5 each, 40 of 241 positive points, 16.6 percent). Each holds one domain built by `_g_core` (tests, own stream `_rng(5000 + number)`): about 1,150-1,200 schemas and 4,600-4,800 edges, ten fields of which eight are named in requires, a priced corridor of 10-12 rows by 3 lanes to the canonical schema, a cheap region of about 1,100 schemas entered for 1-5 per edge from the source and the early corridor whose exits to the canonical schema cost 9-10 million, a one-edge escape at 40 million, and a plant at the source (a cheaper edge that drops a non-prerequisite field the corridor later renames into the field the last edge requires). One hard record (field states that open the cheap region wide) plus three records from late corridor rows; one partner; no filler, no late gadgets, so no earlier check is paid again.
- Doc text: none added. K14 already states the sizes (<= 1,200 schemas, <= 6,000 edges, <= 8 prerequisite fields, <= 10 fields, plans <= 80 edges) and the 10 s per `plan_migration` call on 2 CPUs; migration_semantics.md:11 states edge cost as a positive integer with no upper bound, so 40,000,000 is inside the stated value form.
- Reference: `_reference_plan` in the tests is now a label-setting search ordered by (cost so far + cheapest schema-graph remainder, edge-id list); it equals the old full-reachability reference on 180 core-like and 3,000 tie-heavy small cases, and the digest of the 28 earlier worlds, the ladder and the two isolated plan cases is byte-identical before and after (proto/digest_before.txt, TOTAL c70a4595...).
- Oracle: repo_fixed `plan_migration` uses the same ordering (`_cost_to_target` helper after `plan_migration`, so the planner span still covers it); solve.py re-rendered (22 repairs).
- Verifier: every child runs under an address-space cap of 4,096 MiB (task.toml memory_mb) through `_CAPPED`, so a runaway planner fails only its own world; the per-world child budget is 10 s per line plus 20 s (60 s).
- P-4 dropped (the two candidates passed for blind, Opus and oracle: pure dilution). Judge unchanged.

## Gate v3.6 harden (28 Oct 2026, board f0331ad)
Why: run a5 on 87ce7cd0b00b scored tests 83.40, rubric 53.85, final 68.62; new gate tests < 85, rubric < 85, final < 50. The run lost exactly the eight large-graph worlds by hidden-scale TIMEOUT (Law-1 v3.5). Design and kill table: OUT harden_g36_f0331ad/DESIGN.md, WORK/KILL_TEST.md section "Gate v3.6 harden".
- Tests: ten more CORE worlds world_37..46 (w5), own stream 7000, zone degree 5, edges <= 6,000. Positive 241 -> 291, checks 71 -> 81 (TS-23 warn kept, option A). Lever 90/291 = 30.9%. First write / all-but-one 201/291 = 69.07.
- Judge: 20 criteria, positive 38: R1-R5 kept probes, R6-R13 new probes on acts a5 skipped (K14 timing and separate-search comparison at a thousand schemas, edge cost above one million, unnamed extra file (K2), manifest batch with no lines, CLI rerun over older output (K10), altered copy of /app/ci, --help), R14 J4 code quality (malformed contract file named), negatives R15-R20 incl. J3a/J3b/J3c and the anchored verifier-path negative.
- Oracle: solve.py `contract_checks` performs every new probe act and prints plain descriptions; load_contracts repair `_read`.
- Predicted a5-like run: tests 69.07, rubric 18.4-21.1 (mid 19.7), final about 44.4.

## Gate v3.6 harden a6 (28 Oct 2026, board a4f790c)
Full design: master_chat_work/20261028_schema-migration-plan-repair/harden_g36_a4f790c/DESIGN.md. 34 gated worlds world_47..world_80 (w5, 170 of 461 positive), `_g_gate` stream 9000; `_reference_plan` remainder = max(schema-graph cost, per-prerequisite-field projection), output-neutral (digest46 equal); oracle planner upgraded the same way. Docs, judge, environment unchanged.

## Gate v3.7 redesign a6 (board 9111ecc)

Authoritative accepted design: master_chat_work/20261029_schema-migration-plan-repair/harden_g37_9111ecc/DESIGN.md. Master go at 10:05 approves 60 gated worlds 47-106 at weight 5, child cap 15 s, R5/R13 removed and R21-R25 added. Bundle-only exception: CRASH+TIMEOUT loss may be at most 60% of positive test weight. No other bar is waived; no third design is authorized.

Built counts: 141 checks, 135 positive worth 591, six negative worth 14; judge 23 criteria, 17 positive worth 49, six negative worth 20. New-tier share 300/591=50.76%. Predicted a6-like tests 291/591=49.24%; a6-graded judge 7/49=14.29%; predicted final 31.76%. Peer-25% judge sensitivity is 26.53%, final 37.88%.

Build guard: 81 old check bodies and weights unchanged; 35 immutable files unchanged. Docker audit returned identical plans on 987 old calls (b0f465e55d9b6d1a), unchanged old world documents, and 300 shape seeds passed with maximum reference 0.267 s. All R21-R25 oracle witnesses printed actual results; direct oracle checks passed 591/591. These are not the pending real Harbor gates. Final COST_TABLE and cumulative timeout weight are measured separately before any Tasks_INPUT sync.
