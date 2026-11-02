# RECHECK_FIX 7b203bc (b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042, P12 fix v1)

Kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271 (same as QC v1). BUNDLE before = b93175ac2263 = QC copy 02c7202. Session rename: name_session.py printed `codex: no match` / `opencode: ['ses_e73541f1fffekRzZfwFT2IvEVs']` (listed, not verified as this session).
Noise check (Always 13): PREV_QC_COPY 02c7202 is byte-identical to BUNDLE and v1 is the first QC round, so no finding has a previous PASS; no NOISE label applies.
Levers (WORK/LEVERS.md, no designed levers on record): L1 column-4 paid, L2 clash cover, L3 admission bar, L4 precedence flip at the cutover, L5 reinsurer epoch split, L6 factor clip. (L7 remainder tie-break measured 0 points, not a lever.)

## Recheck table

| ID | label | rule quote (kit file:line) | evidence (bundle file:line) | decision | playbook row | effect L1..L6 | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| G01-1 IN-13 | REAL | 01_Instruction_QC.md:43 "Internal consistency: the instruction must not contradict itself" | instruction.md:5 puts unresolved claims in the ledger as EXCLUDED/UNRESOLVABLE_CHAIN, then "claims whose reinsurer cannot be resolved to a canonical identifier do not appear in any ledger"; output_contract.md:51 "whose reinsurer resolved to a canonical identifier", :61 "because unresolved rows do not appear in any ledger" vs :74; solve.py:876-887 writes the row | fix: delete the clause in instruction.md:5, drop the two contract clauses | IN-13 | none x6 | n/a | instruction.md, output_contract.md |
| G01-2 IN-8 | REAL | 01_Instruction_QC.md:38 "Everything that grades the agent must be satisfiable by an agent holding only the prompt and the container" | judge.toml R18, R20, R23 grade closing-message content the instruction never asks for (instruction.md:9 asks only the 14 integers, quantity names and the settling logs) | fix (AYUSH): R18, R20, R23 retargeted to trajectory conduct; weights and types kept | JD-8 / IN-8 | none x6 | n/a | judge.toml |
| G01-3 IN-15 | REAL | 01_Instruction_QC.md:45 "Every graded rule of engagement is stated somewhere the agent can read it" | test_output.py negative_module_opens_network_or_shells_out (-1) bans subprocess/os.system and socket/urllib/http imports; instruction.md:3 says only "there is no network" | fix: one sentence in instruction.md:3 (rule of engagement, not a lever) | IN-15 (state once in the governing file; the instruction governs engagement) | none x6 | n/a | instruction.md |
| G01-4 AL-26 (minor) | REAL | 05_Alignment_Integrity_QC.md:59 metadata truthfulness | instruction.md:1,:5 and task.toml:7 say "three excess layers"; attachment_rules.md:3 and solve.py LAYERS have retention + two excess layers | fix wording "two excess layers (working and cat)" | AL-26 | none x6 | n/a | instruction.md, task.toml |
| G01-W1 (warn) | REAL | 01_Instruction_QC.md (IN-13 wording) | instruction.md:9 "State each as a plain integer" after "seven quantities" | fix "State each of the fourteen numbers as a plain integer" | wording | none x6 | n/a | instruction.md |
| G02-1 DS-21 | REAL | 02_Data_Solution_QC.md:70 "Solvable from what the agent actually receives" | chain_ladder_rules.md:7 and data_quality_counting.md:21-23 point to source_declarations.properties for precedence (none there); derivation_policy.ini:6-7 `order_book`/`registry` name no source; solve.py:551-552 PRE claim_tx>cession>fixed_width, POST cession>claim_tx>fixed_width | fix: derivation_policy.ini precedence lines name the three sources in solve.py's order; docs point there; solve.py reads them | DS-21 (declare the rule in the governing file) | L4 none (the flip stays a reading of the cutover; the order was already the graded answer) | n/a | derivation_policy.ini, chain_ladder_rules.md, data_quality_counting.md, solve.py |
| G02-2 DS-3 | REAL | 02_Data_Solution_QC.md:19 "every claim ... about the data ... is true of the actual bytes" | source_declarations.properties:4 offsets claim_ref:0:11,... vs width 92 and solve.py:453-461 0:12,12:32,32:40,40:48,48:62,62:92 | fix offsets line; solve.py reads it | DS-3 | none x6 | n/a | source_declarations.properties, solve.py |
| G02-3 DS-3 | REAL | 02_Data_Solution_QC.md:19 | amendment_rules.md:11, attachment_rules.md:11 "fails the hidden-extract check, because A and B each ship a different ratio/retro factor"; extracts A/B ship the same declarations; instruction.md:3 "and with other declarations in force" | fix: delete both sentences and the clause (QC first option); "at other scales" kept and made true (G03-2) | DS-3 / IN-17 (delete announcing sentence) | none x6 | n/a | amendment_rules.md, attachment_rules.md, instruction.md |
| G02-4 DS-19 | REAL | 02_Data_Solution_QC.md:67 "solution code must respect constraints the contract imposes" | solve.py:48-61 regex "That constant fraction is" absent from shipped counterfactual_parameters.md (falls back to 0.08 literal); :213-217 tolerance <= 2 vs alae_rules.md:5 one dollar; :31-33 APRIL_CUTOVER literal; :453-461 offsets literal | fix: fit fraction from claim_adjustment_log.log (coarsest decimal with every row within one dollar), read cutover and offsets from declarations; outputs byte-identical on shipped/A/B (proved by seal) | DS-19 | none x6 | n/a | solve.py |
| G02-5 DS-20 / G03-3 TS-19 | REAL | 02_Data_Solution_QC.md:68 "The oracle obeys the contract"; 03_Tests_QC.md:50 | data_quality_counting.md rules for log_continuations, out_of_horizon_rows, duplicate_identical/conflicting, gap_shifted give values that differ from the sealed 2/5/0/155/0; output_contract.md:73 vs data_quality_counting.md:37-39; amendment_rules.md:7 0.25 raise never applied by solve.py build_ledger; claims_retracted sealed 0 vs 10 RETRACTED rows | fix (AYUSH docs match reference): rules reworded to what the reference counts (rule stated, no figure, no trap pointer); 0.25 raise stated as counterfactual-7 only. Two code fixes where no wording can make the sealed value true: claims_retracted counts RETRACTED ledger rows (0 -> 10), gap_shifted counts rows placed by the declared next-cycle rule (shipped stays 0). See Deviations. | DS-20 (AYUSH sanctioned docs-to-reference) | none x6 | n/a | data_quality_counting.md, output_contract.md, amendment_rules.md, solve.py, tests blob |
| G02-6 DS-20 / G04-1 JD-7 | REAL | 02_Data_Solution_QC.md:68; 04_Judge_QC.md:76 "Every criterion must be satisfied ... by the shipped oracle" | judge R1 2999382, R2 21, R3 115, R4 1294476, R6 1847061, R7 3020677 vs oracle 2972752, 20, 114, 1294465, 1830654, 2994037; counterfactual_parameters.md describes allocation re-runs the code never does; attachment_rules.md:11 "including pair 4" names the 0.50 retro row while pair 4 uses 1.10 | fix (AYUSH): counterfactual_parameters.md reworded to what compute_counterfactuals computes; attachment_rules retro line drops "including pair 4"; judge R1-R14 set to the oracle's 14 integers; weights kept | JD-7 / DS-20 (AYUSH) | none x6 | n/a | counterfactual_parameters.md, attachment_rules.md, judge.toml, solve.py comments |
| G02-7 DS-6 (minor) | REAL | 02_Data_Solution_QC.md:22 | endorsement_circulars_p2/p3.jsonl 0 bytes; cycle_marks.csv H02 end 2032-02-01T00:00:00Z = H03 start (also attachment_windows.csv) | fix: every cycle end equal to the next start moved back one second (cycle_marks.csv, attachment_windows.csv); the 30 circular lines split 10/10/10 over p1/p2/p3 in order; seal of shipped identical (every digest, scalar, audit section) | DS-6 | none x6 | n/a | cycle_marks.csv, attachment_windows.csv, endorsement_circulars_p1-3.jsonl |
| G02-8 DS-22 | REAL | 02_Data_Solution_QC.md:78 "TRUTH.md describes the bundle that actually shipped" | TRUTH.md:7,15,16,24,39,52,64,70,74 | fix: TRUTH.md rewritten by script, last edit | DS-22 | none x6 | n/a | solution/TRUTH.md |
| G02-9 (minor) | REAL | 02_Data_Solution_QC.md (dead code) | solve.py:282-295 unreachable block naming undefined names | fix: delete; a retracted claim with an unresolved reinsurer now keeps its RETRACTED row (allocation_rules.md precedence); seal of shipped/A/B unchanged except claims_retracted (row G02-5) | DS dead code | none x6 | n/a | solve.py |
| G03-1 TS-24/28 | REAL | 03_Tests_QC.md:68, :73 | tests/Dockerfile `USER 1001:1001`, `chown -R 1001:1001 /logs/verifier`, `COPY --chown=1001:1001 . /tests/`; test_output.py _run/_rerun_bytes run the agent module as the verifier uid | fix per QC: verifier runs as root, /logs/verifier root:root 755, agent copy runs via setpriv as uid 1002 after chmod a+rX of staged room | TS-24 | none x6 | n/a | tests/Dockerfile, test_output.py |
| G03-2 TS-20/26 | REAL | 03_Tests_QC.md:51, :53 | cross_artifact_identity_triangle_holds w5 passes on all-zero outputs; extract A = shipped data with 3 docs changed, so alpha re-pays shipped digests | fix: triangle w5 -> w1; extract A regenerated as a different corpus (every claim CLM-nnnnn with nnnnn a multiple of 5 removed from every claim-keyed file: 128 admitted claims vs 158 shipped, plus AL-27 trigger rows), digests resealed | TS-20, TS-26 | none x6 (A stays a full corpus; every lever still separates on A) | n/a | test_output.py, reward.toml |
| G03-4 TS-16 | REAL | 03_Tests_QC.md:47 "fire on the cheat and ONLY on the cheat" | test_output.py:649 `banned_literal_strings` matched against every string constant incl. docstrings | fix: skip docstrings; count the literal only when it is compared or assigned | TS-16 | none x6 | n/a | test_output.py |
| G03-5 TS-13/14 (minor) | REAL | 03_Tests_QC.md:44, :45 | development_spine_exact digests ledger_backbone; ibnr_carryforward_exact digests ledger_spine; methodology_audit_attachment_exact also asserts counterfactual absence | fix: rename to ledger_backbone_exact / ledger_spine_exact; split the absence assert into its own check methodology_audit_holds_only_declared_sections w1; attachment check stays w3 (exe_copy W2 accepts only weights 1, 3, 5, so w2+w1 sharing is impossible; P +1, see Deviations) | TS-13 (split sharing weight), TS-14 | none x6 | n/a | test_output.py, TRUTH.md |
| G03-6 TS-5 (minor) | REAL | 03_Tests_QC.md:29 | test_output.py:20-21 names solution/rebuild_fixtures.py, which does not ship | fix comment wording | TS-5 | none x6 | n/a | test_output.py |
| G04-2 JD-11 | REAL | 04_Judge_QC.md:88 | R34 names 0.80/0.40; attachment_factors.csv:3-4 ship 0.75 and 0.50; "hidden extracts ship different factors" false | fix per QC wording | JD-11 | none x6 | n/a | judge.toml |
| G04-3 JD-8/16 | REAL | 04_Judge_QC.md:77, :93 | R33 reads the ledger `layer` column also graded by treaty_cession_walk_exact and ledger_backbone_exact | fix: code path only, type "task completion" | JD-8 | L2 none (tests still grade the layer column) | n/a | judge.toml |
| G04-4 JD-14 | REAL | 04_Judge_QC.md:91 | R25 "no pip/apt/conda" duplicates R32; R31 overlaps R1-R14 exactness | fix per QC wording | JD-14 | none x6 | n/a | judge.toml |
| G04-5 JD-15/6 (minor) | REAL (R19 only) | 04_Judge_QC.md:92, :72 | R19 CLM-00011 row has col4 = col5 = 93124, so col-5 reading cannot be told apart | fix R19 to a claim whose cols 4, 5, 7 all differ; R16/R17 weights KEPT (AYUSH) | JD-6; JD-15 KEEP | L1 harder (R19 now separates col 4 from col 5) | n/a | judge.toml |
| G04-6 JD-3/5 (minor) | REAL | 04_Judge_QC.md:69, :71 | R35 vague clauses; R22 two observables; R23 "naming one binding-capacity cell" | fix per QC wording | JD-3, JD-5 | none x6 | n/a | judge.toml |
| G05-1 AL-3 | REAL | 05_Alignment_Integrity_QC.md:34 "Exact-shape agreement" | output_contract.md:31 "eleven integers ... one integer per quantity" vs instruction.md:9 two per quantity (14) | fix wording | AL-3 | none x6 | n/a | output_contract.md |
| G05-2 CL-3 | REAL | Final_checklist.md:490 "whether they can be lifted straight out of something the agent already has" | methodology_audit_attachment_exact asserts layer_count 3 and layer_names given verbatim by output_contract.md:21 | fix: drop those asserts and the example; keep authority_file + attachment_rule | CL-3 | L2 none | n/a | test_output.py, output_contract.md |
| G05-3 CL-4 | FALSE_POSITIVE | Final_checklist.md:491 "An instruction that states out loud that only an exact match counts has set that bar deliberately" | instruction.md:5 "Every figure is a whole number of dollars and exact equality is the bar, so a figure that is merely close is wrong." | REBUT / KEEP (AYUSH) | CL-4 REBUT | none | n/a | none |
| G05-4 AL-2 | REAL | 05_Alignment_Integrity_QC.md:33 "Everything promised is graded" | instruction.md:7 "add nothing to the output directory beyond the nine documents and the program" ungraded | fix: new weight-1 check output_directory_holds_exactly_ten_documents | AL-2, NEW-CHECK | none x6 | n/a | test_output.py, reward.toml |
| G05-5 AL-27 | REAL | 05_Alignment_Integrity_QC.md:38 "which graded input would come out differently if the solver broke exactly this rule? - no such input means the rule is ungraded" | dq_block_unit_rows, dq_paren_negatives, dq_duplicate_identical, dq_gap_shifted 0 in shipped/A/B; no ZERO/CAP_ZERO or ZERO/NO_QUALIFIED_LAYER rows | fix: one triggering row per rule in hidden A/B only (kit needs a graded input, not a shipped one, so no PAUSE); a new weight-3 check grades A/B data_quality and ledger outcomes; WORK/RULE_COVERAGE.md | AL-27 | none x6 (shipped unchanged) | n/a | test_output.py (extracts, blob), reward.toml |
| G05-6 AL-28 | REAL | 05_Alignment_Integrity_QC.md:39 "No penalty stacking" | negative_hardcoded_sample_answers (-5) and negative_output_independent_of_the_corpus (-3) fire together on a canned-output module | fix: output_independent returns False when the hardcoded negative fires | AL-28 | none x6 | n/a | test_output.py |
| G05-7 AL-8 (warn) | REAL | 05_Alignment_Integrity_QC.md:44 | task.toml:16 expert_time_estimate_min 420 with agent timeout 10800 s | fix 180 | AL-8 | none x6 | n/a | task.toml |
| S11-1 AL-2 | REAL | 05_Alignment_Integrity_QC.md:33 | output_contract.md:23-29 endorsements, reserve_state, chain_ladder, allocation sections ungraded | fix: new weight-1 check methodology_audit_remaining_sections_exact vs sealed shipped/A/B | AL-2, NEW-CHECK | none x6 | n/a | test_output.py, reward.toml |
| Oracle x3 (kit x5) | KEEP | Final_checklist Step 10 | oracle run 3 times | KEEP (Ayush rule) | n/a | none | n/a | none |

QL coverage FAIL rows (IN-15, DS-19, TS-19, JD-15/16, AL-1, AL-2, AL-3/4/27, Step 11): each maps to a gate finding above and is closed by that row.

## Gate results
- Docker block 2 (final bytes, TS 20261030T185856-8a42, copies from live exe_copy.py): oracle x3 1.0 / 1.0 / 1.0, owner-only 1.0, nop 0.0, AFTER replay 0.1159 (8/69). Block 1 (TS 20261030T181721-7116) gave the same before test.sh/Dockerfile/A5 edits.
- precheck.sh last line: PRECHECK CLEAN. xref_check: 40 entries, 0 findings. tests_qc: 37 pass, 0 warn, 0 fail. stacking_check: PASS (OUT/STACKING_CHECK.md).
- Trap survival PASS (every lever >= 100% of its before loss). Vacuity PASS. RULE_COVERAGE.md: 6 rules, every row >= 1 failed check.
- BUNDLE tree after = 595cfde13e3f (before b93175ac2263); Tasks_INPUT copy = 595cfde13e3f.

## Deviations from master directions
- G02-5 (docs match reference): two values could not be made true by wording, so solve.py was fixed instead: `claims_retracted` counted a field the code never set (sealed 0 against 10 RETRACTED ledger rows; now 10 shipped, 10 A, 9 B) and `gap_shifted` counted the same never-set field (now counts ledger rows whose instant sits in no cycle window; shipped stays 0). Check-itself-was-the-defect; the saved run still loses summary_claim_counts_exact (admitted 157 vs 158, dropped_late 0 vs 5) and data_quality_anomaly_tallies_exact.
- G03-5 / G05-2: methodology_audit_attachment_exact keeps weight 3 (authority_file + attachment_rule), the counterfactual-absence assert moved to a new weight-1 check `methodology_audit_holds_only_declared_sections` instead of a negative (playbook TS-13 split; a weight-2 split was refused by exe_copy W2: weights must be in {1,3,5}). P +1.
- G04-6 R35: QC proposed an 80-line function cap; the oracle's main() is 193 lines, so an 80-line cap would make the oracle fail its own J4 criterion (JD-7). Cap set at 200 lines.
- G03-2: extract A rebuilt as shipped minus every claim whose number is a multiple of 5, removed from every claim-keyed file (128 admitted vs 158). The saved module dies on new A (`ValueError: alae_rules.md declares no pro-rata fraction`): old A's alae_rules.md declared a fixed 0.08 the shipped corpus never declares (DS-3), so the saved run newly loses byte_identical_rerun 1 and program_runs_and_exits_clean 1. Within the band (see Score band).
- G05-5: triggers added to A/B only; graded through one new weight-3 check `hidden_extract_quality_tallies_and_outcomes_exact` (A and B: twelve data_quality keys and ledger outcome digest vs sealed). The live kit AL-27 (05_Alignment_Integrity_QC.md:38) asks only that a graded input constructs the case; no PAUSE needed.
- Side fix: solve.py write_artifacts raised shutil.SameFileError when run in place as /app/out/reserving.py --out /app/out (exit 1 after writing all nine documents); it now skips the self-copy. environment/Dockerfile `ENV HOME` moved to line 2 (precheck FC-S24, pre-existing). Inline try/except in each check body (tests_qc A5) with unchanged behaviour.

## Touched rules
| id | touched how | rules re-checked | verdict |
|---|---|---|---|
| ledger_backbone_exact | renamed from development_spine_exact | TS-13, TS-14, TS-25 | PASS, test_output.py criterion desc names the seven fields digested |
| ledger_spine_exact | renamed from ibnr_carryforward_exact | TS-13, TS-14, TS-25 | PASS |
| cross_artifact_identity_triangle_holds | weight 5 -> 1 | TS-20, TS-26, CL-2 | PASS, passes on zeros so minor detail |
| methodology_audit_attachment_exact | layer_count/layer_names asserts dropped, absence assert moved out | CL-3, TS-13, TS-25 | PASS, values must be read from errata_2032-04.md |
| methodology_audit_holds_only_declared_sections | new w1 | TS-13, TS-14, TS-25, TS-26, NEW-CHECK | PASS, vacuity probe loses it |
| methodology_audit_remaining_sections_exact | new w1 (S11-1) | TS-13, TS-20, TS-25, TS-26, CL-4 | PASS, shipped + A + B sealed audit sections |
| hidden_extract_quality_tallies_and_outcomes_exact | new w3 (AL-27 grader) | TS-13, TS-19, TS-20, TS-25, TS-26, CL-4 | PASS, every AL-27 mutant loses it (RULE_COVERAGE.md) |
| output_directory_holds_exactly_ten_documents | new w1 (G05-4) | TS-13, TS-14, TS-25, AL-2 | PASS |
| negative_hardcoded_sample_answers | banned instant only when compared or assigned | TS-16, AL-28 | PASS, oracle never fires (oracle runs) |
| negative_output_independent_of_the_corpus | silent when hardcoded fires | AL-28 | PASS, hardcoding group 8 -> 5 |
| _run/_rerun_bytes | setpriv uid 1002, verifier root, serial lock | TS-24, TS-28 | PASS, oracle x3 1.0 |
| R1-R14 | integers set to reference | JD-7, J1 | PASS, harness/cf.py on final data = R1..R14 |
| R18, R20, R23 | retargeted to trajectory conduct | JD-2, JD-5, JD-8, IN-8, JD-15 | PASS, start "The agent", target trajectory |
| R19 | CLM-00056 row (419741/419817/419906) | JD-6, JD-7 | PASS, columns 4, 5, 7 differ |
| R22 | read event only | JD-5, JD-16 | PASS |
| R25 | stdlib imports only | JD-14 | PASS, no overlap with R32 |
| R31 | exact value wrapped in range/tilde | JD-14, J3 | PASS |
| R33 | code path only, type task completion | JD-8, JD-16 | PASS, no ledger column |
| R34 | shipped factors 0.75/0.50 | JD-11, JD-7 | PASS, oracle has no such literal |
| R35 | J4 concrete clauses, 200-line cap | JD-3, JD-7, J4 | PASS, oracle longest 193 |

## Vacuity probe
Unedited shipped environment, empty /app/out, graded by the bundle tests in Docker: `{"P": 69, "earned": 0, "fired": []}` (run at P 68 before the W2 weight fix; the added w1 check needs the ten documents, so still 0). Judge: every positive needs stated integers, actions in the trajectory, or a delivered module; a do-nothing agent earns none. PASS.

## Side effects
| FIX id | ids re-checked | result |
|---|---|---|
| G02-1/G02-2/G02-4 (decl reads) | DS-19, DS-21, CL-8, CL-10 | seal1 identical except claims_retracted |
| G02-7 (cycle ends, circular split) | DS-6, AL-27, R5/R14 | seal identical; R1-R14 from final data |
| G03-1 (setpriv) | TS-24, TS-28, AL-11/12/14, round notes C | serial lock added after first run showed concurrent kills |
| G03-2 (new A) | TS-20, TS-26, AL-10, AL-24 | alpha digests now differ from shipped |
| G04 judge edits | precheck J3, J4, J9, J10 | PRECHECK CLEAN |
| G01-1 / G05-1 docs | IN-13, AL-3, AL-18 | xref_check 0 findings |

## Noise keeps
None (first QC round; no earlier PASS to compare).

## Trap survival
| lever | before loss | after loss | ratio | separating cases kept | verdict |
|---|---|---|---|---|---|
| L1 paid col 7 | 40/67 | 43/69 | 1.08 | yes | PASS |
| L2 per-claim retention | 26/67 | 26/69 | 1.00 | yes | PASS |
| L3 no admission bar | 42/67 | 46/69 | 1.10 | yes | PASS |
| L4 single precedence | 46/67 | 50/69 | 1.09 | yes | PASS |
| L5 no epoch split | 19/67 | 19/69 | 1.00 | yes | PASS |
| L6 unclipped factor | 37/67 | 37/69 | 1.00 | yes | PASS |

## Score band
final = 0.5 x tests% + 0.5 x judge%.
| check / criterion | before | after | why |
|---|---|---|---|
| tests total (replay of saved out) | 12/67 = 17.91% | 8/69 = 11.59% | see rows below |
| cross_artifact_identity_triangle_holds | 5 | 1 | weight 5 -> 1 (G03-2) |
| methodology_audit_attachment_exact | 3 | 3 | |
| byte_identical_rerun | 1 | 0 | saved module raises on new A (needs a declared fraction old A carried; DS-3) |
| program_runs_and_exits_clean | 1 | 0 | same |
| exact_serialization_format, artifacts_present_and_parse | 2 | 2 | |
| methodology_audit_holds_only_declared_sections | n/a | 1 | new |
| output_directory_holds_exactly_ten_documents | n/a | 1 | new |
| methodology_audit_remaining_sections_exact, hidden_extract... | n/a | 0 | new, lost |
| every other check | 0 | 0 | lost before for wrong values, still lost |
| judge (current text) | 14/66 = 21.21% | 17/66 = 25.76% | R20 retargeted: trajectory steps 18, 22, 23, 24 count late rows, duplicates, restatement gaps, paren negatives, collapse from source files (earned); R18 new: step 6 cats errata_2032-04.md before step 28 first writes reserving.py (earned); R23 new: no per-cell walk, closing says "no cell's capacity binds" (lost); R19 new: 419741 never shown (lost); R1-R14: closing 3015547, 0, 8, 2404196, 0, 184, 217, 80, 0, 0, 0, 0, 16, 0 match neither old nor new integers (lost both) |
| predicted final | 19.56 | 18.68 | diff -0.88, inside +-5; saved run 19.38 sits between |
Judge criteria whose text changed since 27 Oct (saved run judged on older text): R16, R17, R19, R26, R33, R34, R35; R35 earned INFERRED (saved module: specific excepts, longest function 87 lines).

## QC_RULINGS rows
- IN-15 | rule of engagement network/subprocess negative | added to instruction.md:3 | QC fail | REAL | graded rule was unstated.
- TS-19 | dq counts / ALAE raise | docs reworded to reference (Ayush) | QC fail | REAL | contract and oracle disagreed.
- TS-20 | triangle w5 passes on zeros | weight 1 | QC fail | REAL |.
- TS-26 | alpha re-paid shipped digests | A now a different corpus | QC fail | REAL |.
- AL-28 | hardcoded -5 + output-independent -3 on one act | latter silent when former fires | QC fail | REAL |.
- JD-7 | judge integers vs oracle | judge = oracle integers | QC fail | REAL |.
- JD-15 | R16/R17 weight 3 trajectory | weights kept (Ayush), R19 fixed | QC minor | REAL (R19) / KEEP (weights) |.

## Lessons for the master
- rewardkit runs criteria on threads; any test that kills solver processes by uid must serialise its runs | template_change: _COMMON_RULES_v5 round notes C (add "rewardkit threads criteria")
- exe_copy W2 refuses weight 2; a TS-13 split of a weight-3 check gives 3 + 1, not 2 + 1 | template_change: QC_FIX_PLAYBOOK_v3 TS-13 row
- QC "Fix:" line caps (80-line function) can break JD-7 against the oracle; measure the oracle first | no change: covered by G1
