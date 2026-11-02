# Leak audit: sensor-network-lsq-correlated-adjustment

- Bundle: master_chat_work/bundles/sensor-network-lsq-correlated-adjustment (newest file 25 Oct 02:23; tree sha 772589ab1588 per REDESIGN_REPORT r2).
- Trajectory: jobs/.../claude-opus-5/Run 1 (25 Oct 06:31): tests 100 / rubric 75 / overall 87.5 (report.json: 28 pass, 2 fail = the 2 negative-weight detectors, which are inverted polarity and are meant to fail; judge R9 pass, R10 fail, R11 fail).
- Run vs bundle: `agent/instruction.txt` is byte-identical to `instruction.md` (diff = same). All 58 file sizes in the agent's `ls -la /app/data` (step 3) equal the bundle's `environment/data` sizes (0 mismatches), so the run saw this bundle.
- Audit only. Scratch copies of xlsx/docx/pdf/sqlite under OUT/_scratch/sensor-network-lsq-correlated-adjustment/.

## Step 1: agent-visible surface

| path | size | note |
|---|---|---|
| /app/data/ (58 files, ~2.1 MB) | `COPY data /app/data` (environment/Dockerfile last lines) | the whole visible surface; WORKDIR /app; `chown 1000:1000 /app`; agent `user = "1000:1000"` (task.toml:[agent]) |
| schema.md | 20,345 B (341 lines) | the contract; carries all three score levers (lines 20-26, 54-57, 112-129) |
| instruction.md | 2,533 B | goal, deliverables, 4 figures to report, "will also be run on other extracts" |
| source shards (4) | north csv 29 KB, south tsv 30 KB, west psv 31 KB, east jsonl 54 KB | |
| traverse_closure_register.csv | 413 B | lever A input, 12 rows |
| control_mark_register.csv | 983 B | lever B input, 40 marks, 8 with `set_out_from` |
| stale_cached_solution.json | 327 B | prior-epoch decoy |
| deprecated_precorrection_coords.csv | 7,611 B | decoy |
| `_b` twins: weight_diagnostics_ledger_b.tsv, epoch_presence_ledger_b.jsonl, observation_index_b.xml, session_orientation_notes_b.yml, sigma_convention_manifest_b.yaml | same size as originals (122076, 98212, 116871) | redundant mirrors |
| redundancy_notes.md | 51,448 B | `cmp` says byte-identical to raw_field_book_south.md |
| adjustment_control_workbook.xlsx | 12,308 B | control values, see below |
| field_survey_dossier.docx | 2,231 B | context + per-obs district notes |
| datum_authority_record.pdf | 3,130 B | datum components + per-obs district authority index |
| archive_backfill.db / archive_ledger.sqlite | 24 KB / 69 KB | meta.role = `backfill-decoy` / `audit-cross-check`; empty value columns |

NOT visible: `tests/` and `solution/` are not in the image. Proof: environment/Dockerfile only `COPY data /app/data` (no tests/solution/TRUTH). tests/Dockerfile is a separate verifier image (`COPY . /tests/`), task.toml `[verifier] environment_mode = "separate"`; tests/test.sh runs `chmod -R go-rwx /tests` then rewardkit with `--workspace /app`. Tests are placed after the agent finishes (separate environment). No `__pycache__`, `.DS_Store`, `.git*`, `*~` found under environment/ (find returned nothing).

Does any shipped file hold the expected output, a digest of it, or a script that computes it? No. observation_weight_manifest `naive_weight` is the faulty figure. The ledgers restate district/epoch/kind only. stale_cached_solution.json is NOT near the expected output: stale unknowns run -0.006..+0.006 in a fixed ladder pattern (index 0 = -0.006000, 1 = 0.001000, ...); the oracle free solution (agent artifacts/unknowns.csv, origin CIVET) is 0.0043413601, -0.0031798377, 0.0061036634, ... with different sign pattern. Not a near match.

Binary documents (python zipfile / zlib on scratch copies; pdftotext absent):
- xlsx sheet1: "This workbook is the ONLY place the four control values below are recorded"; u_constrained 3, tuning_k 2.5, blunder_crit 3.5, datum_origin_station 2, k_squared 25/4; plus an observation table (obs_id, kind, ..., region). sheet2 "datum control sheet": same values, `constrained_components ALPHA.x, ALPHA.y, FICUS.x`, `note: components not listed are FREE; do not count them`, `datum_origin_name CIVET`.
- docx: sign convention, azimuth mod 400, id transposition (3 sentences that restate schema 5-7), then `Note OBxxxxx: district D, epoch E, kind K` per observation.
- pdf (6 pages): datum components, "Every component not listed above is a FREE unknown", "u is recorded in the control workbook", then `OBxxxxx | District | E# | AUTHORISED` per observation (e.g. `OB00095 | South | E3 | AUTHORISED`).

## Step 2: checklist A-J

| | Y/N | evidence |
|---|---|---|
| A names | Y (base-task decoys), N (levers) | `stale_cached_solution.json`, `deprecated_precorrection_coords.csv` (header `# DEPRECATED pre-correction offsets`, column `status=deprecated`), `legacy_orientation_offsets.tsv` (`status=retired`), `residual_prior_epoch.tsv`, `*_b` twins, `redundancy_notes.md`, column `naive_weight`, `archive_backfill.db` meta `role=backfill-decoy`, `session_correlation.csv` `status=decoy`, `registry mark_status=abandoned`. Lever files are named for what they are (`traverse_closure_register.csv`, `control_mark_register.csv`) and are real inputs, not decoys. |
| B tone | Y (mild) | schema.md:3-7 "All load-bearing arithmetic is exact ... no trigonometry, square root or floating point is needed"; schema.md:1 "(authoritative)"; every ref file ends its header with "schema.md is the contract." (58-file pattern); datum_constraint_spec.json `u_source`: "recorded ONLY in adjustment_control_workbook.xlsx ... intentionally not restated here"; instruction.md:1 "its figures cannot be reused". No CAPS/bold warnings on the levers. |
| C rules naming the separating case | Y | schema.md:121-127 (A, amount + method of the second sharing), schema.md:22-26 (B, recursion), schema.md:54-57 (C, district of kept shard). See map. |
| D shipped data showing the separating case | partial | Shipped groups do not separate the readings (REDESIGN_REPORT: W5 measured). But: shipped extract has fits groups North/3 (basis 29120 < closure 29773) and West/2 (45671 < 45874) whose "absorbed < closure" printout made the agent stop and re-read 8b (steps 31-32). Shipped `region` == kept-shard district for every record (agent step 19: region Counter equals shard name per shard). Every district-bearing ledger names the kept district of the 6 superseded ids. |
| E visible tests / validators | N | none shipped. The agent built its own checks (steps 25-41). |
| F repo/history | N | no .git, no TODO/FIXME in env files. |
| G leftovers / words | partial | grep: `decoy` appears in schema.md:36 ("restates, cross-checks, or decoys these observations") and in session_correlation.csv, archive_backfill.db meta, reference_unit_registry.csv (`decoy,ignore` rows). No Harbor/QC/lever/rubric/trap/hidden/grader/oracle/board sha in env files or instruction. `anubis:` comment exists only in environment/Dockerfile, which is not copied into the container. |
| H cross-file consistency | Y (redundant statements) | the set_out_from rule is said in schema.md:20-26 and again in station_registry.csv header ("set_out_from names a mark in control_mark_register.csv (schema.md section 1)") and control_mark_register.csv header. The district of each observation is stated in 15+ files. session_correlation.csv:5-6 says "do NOT use a diagonal 1/variance weight" (older graded rule said twice). xlsx/docx/pdf each re-point to the workbook for control values. No file disagrees with another in a way that points at a trap. |
| I judge/conduct hints | N (not visible), with caveat | judge.toml is in tests/ (not visible). instruction.md does not tell the agent to recompute closure/centring/district counts. R9 was nevertheless met by habit (steps 31-32); R10, R11 not. Instruction does list exact figures to report (R1-R4), which is a disclosed deliverable not a hidden test. |
| J what the agent used | Y | see findings F1-F4 with step/line evidence. |

## Test to leak map (tests/test_output.py)

| hidden test | weight in file | visible sentence / data revealing it |
|---|---|---|
| artifact_set_exists_and_parses | 1 | instruction.md paragraph 3 lists every path; schema.md section 16 gives the shape |
| challenge/eval/audit `*_model_test_document`, `_unknowns_documents`, `_residual_documents`, `_observation_sets`, `_rollup_documents`, `_summary_reports` (18) | 3 each | whole of schema.md 2-16; hidden extracts are announced by instruction.md:3 ("will also be run on other extracts in the same format"); no extra hidden rule beyond schema |
| control_values_on_hidden_extracts | 3 | schema.md:136, 164, 192, 199 (workbook cells by label) and instruction/`provenance_summary` fields; xlsx sheet1 "ONLY place" |
| superseded_records_on_hidden_extracts | 3 | schema.md:50-57, 298-306 |
| canonical_serialization_on_hidden_extracts | 3 | schema.md:236-237 "sorted keys and a trailing newline" |
| test_traverse_closure_rows_shipped | w3 | schema.md:112-129; traverse_closure_register.csv; shipped branches visible as printable per-group totals (steps 31-32) |
| test_eval_traverse_closure_rows_hard (separating group, eval only) | w5 | schema.md:121-127: "every micrometre of the closure magnitude is shared again, in proportion to basis by largest remainder ... across only the lengths whose share was the floor or more". Literal transliteration (no fits test on pass 2) is the correct reading. Not genuinely hidden. |
| test_centring_chain_rows_shipped | w3 | schema.md:20-26, station_registry/control_mark_register |
| test_challenge_centring_chain_rows_hard (depth 2-3 chains) | w5 | schema.md:22-26: centring variance "of a station or of a control mark" includes "the centring variance of the mark it names" (self-referential definition). Not genuinely hidden. |
| test_district_rollups_shipped | w3 | schema.md:54-57, 244-245 |
| test_audit_district_rows_hard (region != district) | w5 | schema.md:54-57 "The district of an observation is the district of the shard that holds its kept record". Not genuinely hidden. |
| test_negative_weight_hardcoded_sample_answers, _external_dependency | -5, -3 | instruction.md:3 "only the Python standard library", "nothing may be tied to the shipped values" (disclosed, correct) |
| judge R1-R4 | 3 each | instruction.md:5 asks for these four figures |
| judge R9, R10, R11 (recompute closure, centring, district count) | 3 each | none visible; R9 met incidentally; R10, R11 missed |

Genuinely hidden: the contents of the three hidden extracts (separating group, depth-2/3 chain, relabelled region) and judge R9-R11 wording. Everything the hidden extracts test is fully specified by one literal sentence in schema.md.

## Findings

| id | cat | severity | file:line + quote | evidence it helped the agent | proposed fix (NOT applied) | QC rule touched + risk | touches tests/data |
|---|---|---|---|---|---|---|---|
| F1 | C | HIGH | schema.md:123-127 "A length whose share then falls below the floor absorbs nothing, and every micrometre of the closure magnitude is shared again, in proportion to basis by largest remainder, ties settled as above, across only the lengths whose share was the floor or more" (names amount, method and population; hidden `test_eval_traverse_closure_rows_hard`) | Step 24 program has pass 2 as an unconditional `largest_remainder(magnitude, eligible)` inside the else branch (no re-entry of the fits test). Agent reasoning (openhands_sdk.txt:6196, step ~31) "The contract requires the full magnitude to be reshared among eligible lengths". Step 32 even evaluated a survivor set with basis 27480 < closure 29773 and kept the literal reading. Final message names the fits branch. Eval hidden extract passed. | State the closure as a rule over outcomes (what each length absorbs) without describing the second pass procedure, or move the rule to the register file header and let the contract define only the quantities (basis, floor, closure) | W1-W3/H7 wording rule; risk: removing the procedure makes the rule underdetermined (G5/G8 fairness) | schema.md only (and TRUTH/solve unchanged) |
| F2 | C | HIGH | schema.md:22-26 "The centring variance of a station or of a control mark is `(centring_mm / 1000)^2` ... when its own `mount` is `tripod` ..., plus, when its `set_out_from` is filled, the centring variance of the mark it names." The defined term is used inside its own definition for a mark, which spells out the chain | Agent reasoning (openhands_sdk.txt:2275) "plus recursively added variance from any set_out_from mark"; (openhands_sdk.txt:2583) "trace the set_out_from chains ... for cycles"; step 24 `mark_var()` recursive with memo and cycle guard. Hidden challenge extract (depth 2-3) passed. | Define the figure only for a setup (one level) and give the register a column whose chain is not stated (e.g. `parent_setup`), so depth is data, not text | H6 recursion lever; risk: if depth is not derivable from data, G5 | schema.md; data register column rename would touch tests generator |
| F3 | C | HIGH | schema.md:54-57 "The district of an observation is the district of the shard that holds its kept record: obs_source_district_north.csv is North, ..." (maps to `test_audit_district_rows_hard`, `_owned_rows`) | Agent reasoning (openhands_sdk.txt:2415) "the region column tracks the shard while district depends on whichever shard's record was kept"; (openhands_sdk.txt:2562) "The district for each adjustment comes from the district of the kept record". Code ignores `region`. Audit hidden extract passed. | Drop the sentence defining district by kept shard; let `observation_provenance.psv` / registry define district and make the contract say only "district per section 2 table" (and let `region` be a line field that may disagree) | W1-W3, H3 defined-term lever; risk: ambiguity if both `region` and the shard identify a district (G8) | schema.md (+ maybe data) |
| F4 | D | MEDIUM | 15+ shipped files restate the kept district per obs: district_rollup_*, misclosure_audit_*, crosscheck_ledger_epoch*, weight_diagnostics_ledger[_b], instrument_pairing_ledger, provenance_hashes.psv, observation_provenance.psv (`OB00095\|South`), session_orientation_notes[_b], raw_field_book_*, monument_visit_log.txt, redundancy_notes.md, observation_index[_b].xml, archive_ledger.sqlite, docx notes, pdf authority index (`OB00095 \| South \| E3 \| AUTHORISED`) | Steps 36-38: agent grepped the 6 superseded ids in the ledgers (step 37) and wrote "district/epoch/count of all 1040 observations ... match the cross-check ledgers exactly" in its final message; step 38 compared its district Counter to ledger counts (260/260/261/259). | Remove district from all cross-check ledgers (keep id, epoch, kind) so the kept-shard district is not echoed 15 times | G10 cross-file; risk: ledgers become less plausible as restatements | data (ledgers) |
| F5 | D | MEDIUM | traverse_closure_register.csv rows North,3,-29773,187 and West,2,-45874,242 against shipped basis sums 29120 and 45671 | Step 31 output "North 3 absorbed_total 29120.0" vs closure 29773; agent debugged (openhands_sdk.txt:6196 "North 3 shows a closure of -29773 but absorbed only 29120 ... discrepancies I need to investigate"); step 32 re-derived pass 2 on that group; final message: "the basis_sum <= |closure| branch fires for North/3 and West/2". Shipped self-test forced the agent to study the exact branch logic once. | Make every shipped group fall into proportional/drop only, or equalise all totals so no "unexplained shortfall" appears | W5 (shipped must not separate); risk: lowers shipped partial credit | data (register) |
| F6 | A | MEDIUM | file names `stale_cached_solution.json`, `deprecated_precorrection_coords.csv`, `*_b` twins, `redundancy_notes.md` (byte-identical to raw_field_book_south.md), header lines `# DEPRECATED pre-correction offsets`, archive_backfill.db meta `role=backfill-decoy`, schema.md:36 "decoys these observations", schema.md:215-227 (section 15 lists every decoy file by name) | Step 10 printed the decoy files; agent excluded all of them with no sign of being tempted; `decoys_ignored` in provenance_summary was filled from the closed list (schema.md:308-314). No decoy cost anything. | Rename decoys neutrally (`prior_run_cache.json`, `offset_table_v1.csv`), drop "decoy" words, remove the section-15 enumeration so decoy status has to be deduced | A names, W5; risk: `decoys_ignored` test needs an anchored list (test_control_values reads exact names) | data + schema + tests |
| F7 | D | MEDIUM | `decoys_ignored` closed list (schema.md:308-314) mixes true decoys with real sources (`station_registry.csv`, `session_correlation.csv`, `reference_unit_registry.csv`, `iteration_policy.yaml`) | Agent noted (openhands_sdk.txt:2585) "make sure I identify at least three genuinely unused" files; picked from section 15 | none needed unless F6 is acted on; accepting any listed file makes the test trivial | n/a | tests |
| F8 | B | LOW | instruction.md:1 "An earlier adjustment run on this network produced weights that do not hold up, so its figures cannot be reused." and :3 "It will also be run on other extracts in the same format, so nothing may be tied to the shipped values." | Tells the agent a hidden rerun exists; agent wrote a general program (expected behavior, and unavoidable for a reusable-program task) | keep; wording is necessary | instruction fairness; no change | N |
| F9 | H | LOW | session_correlation.csv:5-6 "Form the weight block as the exact inverse C^{-1}; do NOT use a diagonal 1/variance weight for these members." plus station_registry.csv header re-stating the `set_out_from` rule | Agent applied block weights (older graded noise lever); not tied to the three scoring levers | delete the "do NOT" sentence | W1 | data |
| F10 | I | LOW | judge.toml R9-R11 echo the three levers (closure absorption, centring variance, district count) as "recompute" behaviours; not visible | Agent met R9 incidentally (steps 31-32), R10/R11 not; rubric 75 | none; judge is hidden | n/a | N |

## What is clean

- tests/, solution/, TRUTH.md, judge.toml, reward.toml: not in the image (environment/Dockerfile copies only data/). Separate verifier image; tests chmod go-rwx.
- No expected output, digest or script computing it in any shipped file; stale_cached_solution.json is far from the oracle unknowns.
- No `__pycache__`, `.DS_Store`, `.git`, backup or `~` files; no TODO/FIXME; no words harbor/QC/lever/rubric/trap/hidden/grader/oracle/board sha in agent-visible files.
- Lever file names (`traverse_closure_register.csv`, `control_mark_register.csv`) are honest inputs, not decoy-flavoured names; they do not hint at where a trap is.
- instruction.md has no steps, no hints on method, no emphasis, and is identical between bundle and run.
- Shipped extract does not separate the readings of any lever (per REDESIGN_REPORT W5 measurement); the leak is the contract wording, not the data.

Root cause of the 100: all three levers (A, B, C) are stated in schema.md in a form the agent can transliterate directly (F1-F3), so one sequential implementation of the contract passes hidden `_hard` tests. The agent wrote the program in one pass (step 24) and never revised graded logic.

TOP_LEAK: F1 schema.md:121-127 states the amount, method and population of the second closure sharing (with F2 recursive centring definition and F3 district-of-kept-shard sentence), so literal transliteration passes all three hidden separating extracts
COUNTS: C=0 H=3 M=4 L=3
