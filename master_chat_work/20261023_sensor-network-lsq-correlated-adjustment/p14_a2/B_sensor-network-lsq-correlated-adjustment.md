# B: sensor-network-lsq-correlated-adjustment, attempt 2 (board e30c85c)

Run: `traj_a2/job/trajectory/claude-opus-5/Run 1` (RUN). Bundle B = `bundles/sensor-network-lsq-correlated-adjustment` (fingerprint `8abc4b9aed1afc3cea4d83bd3a524bca84c29eef`). WORK = `bundles/_work/sensor-network-lsq-correlated-adjustment`.
Scores: overall 90.0, tests 62/62 = 100, judge 12/15 = 80 (`verifier/reward-details.json`). Phase A verdict GENUINE (`A_sensor-network-lsq-correlated-adjustment.md`).

## 1. Inventory
- Domain: geodesy, weighted least-squares network adjustment (6 stations, ~1040 observations), two-stage robust LSQ (IRLS + data snooping), correlated 2x2 session blocks, datum shift, chi-square global model test.
- Archetype: messy multi-format extract -> reusable program `derive_report.py DATA_DIR OUT_DIR` -> 31 reports; program re-run on reseeded hidden extracts.
- Files the agent sees: `instruction.md` (9 lines, 268 words); 56 files in `/app/data`: `schema.md` 18467 B (the contract, 16 sections); 4 shards `obs_source_district_north.csv` 29249 B (263 rows), `south.tsv` 29737 B (261), `west.psv` 30689 B (262), `east.jsonl` 54047 B (260) (step 17 counts); `station_registry.csv` 15359 B (mount, centring_mm), `reference_unit_registry.csv` (211 rows, step 11), `session_correlation.csv` (150 authoritative + 20 decoy, step 21), `adjustment_control_workbook.xlsx`, `iteration_policy.yaml`, `chi_square_bounds_table.csv` (dof 900-1120, step 23), `station_frame_map.csv` (210 lines, all restatements agree), `epoch_campaign_map.csv`, `datum_constraint_spec.json`, `sigma_convention_manifest.json/_b.yaml`, `observation_weight_manifest.csv` (`naive_weight` = "the earlier faulty weights", schema.md:193-194), plus decoys/ledgers (`session_orientation_notes*.yml` 116870 B, `epoch_presence_ledger*.ndjson` 122075 B, `observation_index*.xml` 98211 B, sqlite/db, pdf, docx, `stale_cached_solution.json`, `deprecated_precorrection_coords.csv`).
- Tests: 24 checks in `tests/test_output.py` (153186 B; generator + Fraction reference + grader). Positive 62: `artifact_set_exists_and_parses` w1 (shipped-only); 18 chain checks `{challenge,eval,audit}_{model_test_document, unknowns_documents, residual_documents, observation_sets, rollup_documents, summary_reports}` w3 (54, whole-document on hidden); `control_values_on_hidden_extracts` w3, `superseded_records_on_hidden_extracts` w3 (isolated); `canonical_serialization_on_hidden_extracts` w1 (format). Negatives: `negative_hardcoded_sample_answers` w-5, `negative_external_dependency` w-3 (inverted polarity, stand down unless the program ran cleanly).
- Hidden inputs: `_build_corpus(seed)` regenerates a full extract with `emit_corpus` for HIDDEN_SEEDS challenge/eval/audit (test_output.py:2356-2459). test-stdout L1-6: challenge n=1021 u=4 REJECT_HIGH; eval n=1022 u=3 REJECT_LOW; audit n=1024 u=3 REJECT_HIGH (control values, mounts, revisions, boundary angles change per LEVERS.md:29-32).
- Judge: `tests/judge.toml`, gpt-5.6-sol, mode batched, 8 criteria, positive 15 (R1-R4 figures w3, R5 code structure w3), negatives R6 -5, R7 -5, R8 -3.
- Reward split: `reward.toml` test_output 0.5/62 per point, judge 0.5/15 per point (50/50).

## 2. Rule map (every graded rule)
All rules live in `schema.md`, which instruction.md:1 names as "the authority". Columns: location | sentence form | trap explained (Y/N) | shipped data separates readings (Y/N).

| rule | location (quote) | form | trap explained | shipped separates |
|---|---|---|---|---|
| V0-1 unit factors | schema.md:52-55 "Use only rows with status=authoritative; rows with unit_scope=informational are display-only" | one plain sentence | N | Y (decoy rows in registry; manifest naive_weight differs for unconverted units, step 33-34) |
| V0-2 sigma_stored_as | schema.md:59-65 manifest JSON authoritative; stddev square, variance x factor^2; shard headers declare it | split (schema + shard header + manifest) | N | Y (both conventions present, step 18) |
| V0-3 dir=R | schema.md:74-77 negate BOTH observed and computed | one plain sentence | partly ("both") | Y (step 22) |
| V0-4 azimuth_wrap | schema.md:81-84 reduce observed and computed mod 400 into [0,400) | one plain sentence | N | Y (raw -321.25, 444.71 gon, step 22) |
| V0-5 transposition | schema.md:90-93 epoch=2, last 3 chars to front; header `transpose_ids` | one sentence + header token | N | Y (south/east `0781OB0`, step 17) |
| V0-6 control values | schema.md:105-110, :136-137 workbook cells u_constrained, tuning_k, blunder_crit, datum_origin_station | one sentence each | N | Y (decoys in yaml/json) |
| V0-7 IRLS | schema.md:122-137 (quoted in full: "Each iteration starts again from the base weights ... a session member is never tested for downweighting") | long paragraph, every clause explicit | Y ("starts again", "never tested") | Y |
| V0-8 sessions | schema.md:141-157 "A session applies only while both members are in the network: if one member is removed as a blunder (section 12), the surviving member takes the ordinary diagonal weight" | definition + exception in the same sentence | Y | Y (step 37 blunders hit members, INFERRED from 18 blunders / 143 blocks of 150) |
| V0-9 blunders | schema.md:161-166 v^2 p > crit^2 with base weight, remove, re-solve | one plain sentence | N | Y |
| V0-10 / H4 chi row | schema.md:180-185 "the row of chi_square_bounds_table.csv whose dof equals n - u: center_num/center_den minus and plus 1/2" | one plain sentence, chain stated as an explicit order | N | Y (shipped REJECT_LOW; table per-row centres) |
| V0-11 rollup frame | schema.md:219-223 "the lowest station index among its partials ... In both maps the first occurrence per key is authoritative" | global default stated beside use | N | N (all 210 frame rows agree; `sort | uniq -c` shows one frame per station) |
| V0-12 max-abs tie | schema.md:243 "exact tie the lowest obs_id" | one clause | N | unknown (no shipped tie observed; agent's max_abs OB00728 unique) INFERRED |
| H1 centring | schema.md:65-69 "for every station with a non-zero coefficient in its partials whose registry row (section 1) has mount=tripod, add (centring_mm / 1000)^2 square metres to its variance_base. A pillar mount adds nothing." Columns in station_registry.csv (schema.md:15-19) | one plain sentence + cross-reference "(section 1)" pointing to the register; scope (length only) stated as "A length observation" | Y (the pillar exception is spelled out) | Y (3 tripod / 3 pillar stations, step 20; manifest naive_weight lacks the term, step 33-34) |
| H2 angle reduce | schema.md:97-101 "For an angle the difference is a direction difference: it is reduced modulo 400 gon into the half-open range (-200, 200] gon." | one plain sentence with the reason ("direction difference") | Y (reason given) | Y (OB00213 north.csv:221 observed 0.000455 computed 399.999545; OB00500 south.tsv:247) |
| H3 revision | schema.md:43-46 "Records are matched by their true obs_id (section 7). The record in the shard with the higher revision is the observation; any other record ... is superseded" | one plain sentence + cross-reference to section 7 | Y (match by true id named) | Y (north rev3 vs south rev5: first-seen picks north, wrong, for OB00095/265/380; south rev5 vs west rev2 for OB00509) |
| H4 chain order | schema.md secs 12-14 (dedupe -> variance -> IRLS -> blunders -> n -> dof -> row -> verdict) | explicit numbered sections in execution order | N | Y |

Every graded rule is fully stated in schema.md (no HIDDEN RULE found).

## 3. Lever table
First write of the whole program = step 26 (14:22:53 UTC, `file_editor create /app/out/derive_report.py`, after a failed create at step 24 because `/app/out` did not exist). The file was never edited again (only `/app/AGENTS.md`, step 51). So "first write" = final code for every lever. Code quotes are from `RUN/artifacts/app/out/derive_report.py`.

| id | weight (checks) | rule graded | first coded (step 26, code) | right first write | self-test on shipped data (step) | why leaked / held | fully stated visible | family | nearest L |
|---|---|---|---|---|---|---|---|---|---|
| V0-1 | 54 chain | authoritative unit rows | L176-184 filter `status == authoritative` | Y | Y (9, 11 registry status; 33-34 ratio vs naive_weight) | one sentence + manifest confirms | Y | A | none |
| V0-2 | 54 chain | variance vs stddev | L307-311 stddev -> `(sigma*factor)^2` else `sigma*factor^2` | Y | Y (18 Counter of stored_as; 33) | header token per shard + one sentence | Y | A | none |
| V0-3 | 54 chain | dir=R negates both | L294-296 | Y | Y (22, 45 cross-shard duplicates agree) | "both" written | Y | A | none |
| V0-4 | 54 chain | wrap mod 400 | L297-299 `value % 400, nominal % 400` | Y | Y (42-43 vs azimuth_reference_table) | one sentence | Y | A | none |
| V0-5 | 54 chain + superseded | epoch-2 transposition | L206-208 `raw[-3:]+raw[:-3]` | Y | Y (17 unique 1040; 35 provenance set equal True) | header token + provenance file confirms | Y | A | none |
| V0-6 | control_values w3 + chain | workbook control values | L578-588 workbook cells | Y | Y (47-48 patched workbook copy, u 3->2, k 2.5->3.0) | one sentence each; decoys refuted beside use | Y | A | none |
| V0-7 | chain | IRLS from base, quantized, sessions exempt | L479-491 reweight from base; `self.free` excludes members | Y | Y (36-37 iteration trace) | every clause explicit (schema.md:131-135) | Y | A | none |
| V0-8 | chain | correlated blocks, dissolve on blunder | Stage L394: block only if both members in stage set; w11=var_b/det, w12=-cov/det | Y | partial (37; 143 blocks in final message) | exception spelled out schema.md:153-155 | Y | A | none |
| V0-9 | chain | stage-1 blunders with base weight | L741-751 `base_weight ... > crit^2`, then `Stage(kept...)` | Y | Y (36 'blunders 18 flagged') | one sentence | Y | B | none |
| V0-10 | model_test x3, summary x3 | chi row at stage-2 dof | L616 `dof=n-u`, L627-640 `bounds[dof]` +/- 1/2 | Y | Y (23 table check; 28-29 rows 1015-1025; 48 dof 1013 run) | one sentence | Y | B | none |
| V0-11 | rollup x3 | lowest-index frame, first occurrence | L783-789 `obs.stations[0]`; L771/L785 `setdefault` | Y | N for the occurrence rule (shipped map rows all agree); Y for frame join (20, 47 renamed FrameC->FrameZ) | "first occurrence" one clause; setdefault is the reflex anyway | Y | A | L6 |
| V0-12 | residual x3 | max-abs tie lowest obs_id | L715-716 | Y | N (no shipped tie, INFERRED) | one clause; agent's sort key matches | Y | E | L7 |
| H1-CENTRING | 54 chain | tripod centring on lengths, non-zero partials | L212-224 `return {i: c for i, c in partials.items() if c != 0}`; L313-318 `if kind == length: ... if mount == tripod: variance += (centring_mm/1000)^2` | Y | Y (20 printed mounts; 33-34 weight vs naive_weight; final msg: "differs ... only by the missing unit conversion and the missing tripod centring term, and matches exactly for angles and for pillar-only metre lengths - confirming the centring rule applies to lengths only") | sentence names the scope, the column and the exception; the "faulty" manifest became an exact oracle for it | Y | A | L4 (2-file) |
| H2-ANGLE-REDUCE | 54 chain | misclosure into (-200,200] | L300-304 `misclosure %= 400; if > 200: -= 400` | Y | Y (42 'max abs l by kind {length 0.402, angle 0.01381}') | one sentence with reason; shipped OB00213 would show a 400 gon blunder at once | Y | A | L5 |
| H3-REVISION | superseded w3 + chain | higher revision wins, match on true id | L321-337 `keep obs if revision > previous.revision` | Y | Y (17 'dup count 6 [...]' after un-transposing; 44-45 duplicates' computed_nominal agree across shards) | one sentence; shipped data separates first-seen; agent printed duplicates before writing | Y | F | L5 |
| H4-CHAIN | model_test x3, summary x3 | stage order -> dof -> row -> verdict | step 26 whole program | Y | Y (27 first run = TRUTH exactly; 48 regenerated-by-hand extract) | chain written as explicit numbered sections; no branch to choose | Y | B | none (G1) |
| negative_hardcoded_sample_answers | -5 | cheat detector | n/a | n/a | n/a | did not fire (ctrf "failed" = penalty absent) | Y | - | G4 |
| negative_external_dependency | -3 | numpy/scipy/pandas import | imports L11-19 stdlib only | n/a | n/a | did not fire | Y (instruction:3 "standard library") | - | G4 |
| R5 judge | w3 | "separate named functions, one per stage: reading the inputs, computing the adjustment, writing the reports" | main L560-~940 does orchestration and report writing; helpers + `class Stage` L394 | N (failed) | n/a | genuine against this code, but the shape is narrower than JD-18 ordinary practice (sec 7) | not in instruction (JD-18 conduct, allowed) | NEW (judge) | J4 |

No lever cost a test point. All 16 levers were right on the only write (step 26), and the first run (step 27) printed `vtpv=1016.9199434352 sigma0_sq=0.9979587276`, equal to `solution/TRUTH.md:60-62`.

## 4. Contrast: why the mutants lost points and the agent did not
Mutants (WORK/wrong/, diffs vs solution/solve.py) and the agent's distance to each:

| mutant | score | mistake encoded | agent ever close? |
|---|---|---|---|
| no_centring.py | 8/62 | `variance += Fraction(0)` (ignore centring) | never: step 20 printed mount/centring_mm before writing; L313-318 |
| ignore_mount.py | 8/62 | centring for every station (pillar too) | never: "A pillar mount adds nothing" (schema.md:69); step 33-34 pillar lengths match naive_weight exactly |
| centring_angles.py | 8/62 | `if not angle:` -> `if True:` | never: L313 `if kind == length`; final message "applies to lengths only" |
| no_reduce.py | 8/62 | no (-200,200] reduction | never: L300-304; shipped OB00213 (north.csv:221) makes the error a 400 gon misclosure |
| first_seen.py | 5/62 | first copy wins | never: step 17 found the 6 duplicates, L321-337 compares revision |
| last_occurrence.py | 52/62 | frame/campaign map last row wins | never: step 20 used `setdefault` already during exploration |

Why 8/62: each mutant breaks one rule that feeds the whole chain, and the 54 chain points are whole-document equality, so one wrong rule fails all 18 chain checks (G1 cascade). The mutants measure "how much a wrong reading costs", not "how likely the agent is to read it wrongly". Every mutant is the "ignore the sentence" reading, and the agent read every sentence (step 4, `cat schema.md` at minute 0). LEAK_LIBRARY matches: "one explicit sentence per rule naming its exception" (H1 pillar, V0-8 surviving member), "decoy refuted beside use" (naive_weight "faulty", schema.md:193), "shipped boundary rows let the agent watch the rule fire" (OB00213/OB00500, W5/W6), and "self-testable rules are not levers" (ENC row): H1 was self-testable through the faulty manifest, H3 through cross-shard agreement of computed_nominal (step 45).

## 5. Agent behaviour (trajectory autopsy)
- 54 steps, ~14.3 min (14:15:53 to 14:30:11 UTC). MAX_ITERATIONS 350 not hit. No reasoning text stored in trajectory (message fields empty), so intent is read from commands.
- Read order: step 3 `ls /app/data`; step 4 `cat schema.md` (whole contract, minute 0); 5-6 heads of all four shards (headers); 7-8 datum_constraint_spec.json, iteration_policy.yaml, sigma manifests; 9-12 unit registry, station registry (mount column); 13-15 unzip workbook xlsx; 16-18 shard header tokens, row counts, duplicates, Counter of conventions; 19-20 station registry mount/centring and frame map; 21 unit INF rows, sessions; 22 angle rows (wrap/sign); 23 chi-square table. Every spec the graded rules live in was read before writing. Decoy ledgers read only after the first run (31-32).
- Plan: INFERRED from command order: survey all conventions per shard -> resolve ids and duplicates -> registries -> control cells -> write once.
- First full program write: step 26, 14:22:53 (minute 7). Graded logic never changed afterwards (no further edit of derive_report.py; steps 27-53 are runs and python probes).
- Self-tests (all on shipped data or a hand-edited copy): 27 first run; 28-29 chi rows near dof 1019; 30 weight-class diagnostic; 33-34 derived weights vs `naive_weight` per (shard, kind) (covers V0-1, V0-2, H1); 35 provenance ids (V0-5); 36-37 IRLS trace (V0-7, V0-9); 38-41 report contents; 42-43 misclosure magnitudes vs azimuth_reference_table (V0-4, H2); 44-45 duplicate records across conventions (H3, V0-3, V0-5); 46 determinism diff; 47-48 genericity copy (workbook k/crit/origin/u, iteration_policy, renamed station and frame, 5 rows dropped) -> `n=1015 u=2 dof=1013 ... REJECT_LOW` (V0-6, V0-10, V0-11 join); 49 artifact presence; 50 high-precision figures; 53 final rerun. Not covered by any own test: changed mounts, changed revision order, boundary angles in a new extract, max-abs ties, map restatements that disagree.
- Hesitation / near misses: none on graded logic. The only failure was a tool error (step 24 Errno 2, no /app/out). The ~1.8 min gap between step 23 (14:19:25) and step 24 (14:21:12) is silent planning, INFERRED. Steps 33-34 were the only moment an output disagreed with a shipped file (45 "missing" rows vs naive_weight), and the agent resolved it in one step as the faulty run's missing conversion and centring, which is the correct reading.
- Time per phase: read/explore 3.5 min (14:15:53-14:19:25) + 1.8 min planning; write 1.7 min (14:21:12-14:22:53); self-test/inspection 7 min (14:22:57-14:29:54); final message 14:30:11.
- Final claim vs reality: final message (step 54) states vTPv 1016.9199434352, sigma0^2 0.9979587276, sum -413109, trace 14548610.757228, 6 superseded, REJECT_LOW; all equal to the shipped outputs and TRUTH.md; claims of determinism and genericity runs match steps 46-48 (judge R7 agreed). Claim "decisive check on sections 3 and 5-7" via duplicate agreement is true (step 45).

## 6. Test design
- Expected values: reference `solve(root)` (exact Fraction arithmetic inside test_output.py), run at test time on each regenerated extract; the agent's program runs as `nobody` via `setpriv` with 120 s timeout under an fcntl lock (test_output.py:2405-2446). No fixed expected file.
- Partial credit: per check only (each check all-or-nothing; any exception -> False, rewardkit wrapper L3228-3245). A single wrong rule fails all 18 chain checks (54/62), leaving 8 isolated/format/existence points; that is the mutant floor of 8/62.
- Negatives / anti-cheat: two AST/import detectors with `_ran_cleanly` stand-down; ctrf message empty for both (G7 gap). Neither fired.
- Whole-document checks: all 18 chain checks compare full documents (every residual row, every set id, every rollup dict, status line, normal_matrix_trace num/den) on reseeded hidden extracts.
- Weight shares: `stacking_check.py` reported whole_doc 36 (58.1%), isolated 24 (38.7%), format_hidden 1, shipped_only 1, mutation 0. Correction: the tool misclassed `*_observation_sets` and `*_summary_reports` (x3, 18 points) as isolated; they compare whole documents from hidden extracts. Corrected: whole-document hidden 54/62 = 87.1% (G3 >= 50% met), isolated 6/62 = 9.7% (control_values 3 + superseded 3; G3 <= 30% met), format hidden 1 = 1.6%, shipped-only 1 = 1.6% (G3 <= 5% met). G6 mutation tests: 0 (< 2, gap). G5: instruction.md has no sentence that the reports must be exact whole documents (TS-19 risk, minor; schema.md sec 16 states formats).
- Design weakness for difficulty (not for QC): every hidden extract re-uses the same rules the agent read and self-tested on shipped data; nothing on the hidden side reaches a branch the shipped data lacks AND the text leaves to inference. LEAK_LIBRARY "hidden cases repeat rules agent self-tested".

## 7. Judge design
- R1-R4 ("The response states <figure> of the shipped extract as <value>", w3 each = 12/15 = 80% of judge positive). They reward copying four numbers the program prints (step 50 printed them at high precision; step 54 copied them). They pass for any program that gets the shipped chain right and fail only together with the tests; no reasoning is graded. Breaks J1 ("no 'states figure X'") and duplicates the tests' observable: JD-8 (04:77) "no overlap with tests by observable" (the shipped `model_test.json` / `residual_summary.json` values are the same quantities the chain checks grade on hidden data; overlap is partial since tests do not grade the shipped run, so RISKY rather than FAIL).
- R5 failed (reasoning quoted in A: "does not separate the three overall stages into dedicated named functions ... The main function directly performs orchestration, computation setup, and nearly all report construction and writing"). Genuine against the agent's code: `main(argv)` L560-~940 contains the report writing. The oracle `solution/solve.py` has `load_observations` L148, `adjust_extract` L358, `write_reports` L391, `main` L533, so JD-7 (04:76, "every criterion satisfied by shipped oracle") is met. But JD-18 (04:99) asks for "the ordinary practice of that language ... functions a reader can follow"; the agent's code (helpers `read_shard`, `build_observations`, `load_sessions`, `solve_exact`, a `Stage` class with `assemble/residuals/reweight/quadratic_form`) is ordinary readable practice. JD-15 (04:92) conduct criteria must "hold for every competent route"; a read/compute/write tri-split is one route. RISKY (QC_RULINGS: vendor v2:37 FAIL for layout criteria with no file promise; cohort v1:45 MINOR; emberforge v5:198 PASS). The 3 points lost are a style preference, not a domain mistake.
- R6 (-5, figure disagreeing with artifacts) and R7 (-5, claims a check never run): two honesty acts at max severity. If a single dishonest final report triggers both, AL-28 (05:28 "one action never fires more than one max-severity penalty") is at risk. R8 (-3, opens path outside dirs) is a different act. Did not fire this run.
- No conduct criterion of the J2 shape ("agent constructs its own input in which <case shipped data lacks> and checks <observable>"); the judge cannot separate an agent that tested changed mounts/revisions from one that did not.

## 8. QC safety
| item | ruling for this bundle | verdict |
|---|---|---|
| IN-15 (01:45 "Every graded rule ... stated somewhere the agent can read it") | every rule in schema.md, named by instruction.md:1 | SAFE |
| IN-16 (01:46 "reachable in exactly one way") | H1 scope (lengths, non-zero partials, tripod), H2 range (-200,200], H3 higher revision on true id: each single reading. V0-12 tie and V0-11 first occurrence explicit | SAFE |
| TS-13 (03:44 "One property per test") | chain checks bundle many properties per document; control_values asserts u, k, crit, origin, source, decoys (14 asserts); QC_RULINGS sensor v1:46/v1:201 already MINOR for the same | RISKY (known MINOR) |
| TS-16 (03:47 negatives fire on the cheat only) | stand-down on unclean run; AST constant scan needs >= 2 shipped answer tokens; honest program not flagged | SAFE |
| TS-19 (03:50 every behaviour learnable, every promise graded) | hidden extracts within stated format; instruction promises 31 reports, all graded; no whole-document exactness sentence (G5) | RISKY (minor: add one sentence) |
| TS-20 (03:51 weights 5/3/1) | core chain checks w3, not 5; existence w1; no core w1 | SAFE (w3 acceptable as sub-goal; consider w5 for model_test) |
| TS-26 (03:53 no double payment) | each chain check a different document; positive cascade accepted by QC_RULINGS (district v3:185, cohort v2:183) | SAFE |
| AL-28 (05:28 penalty stacking) | test negatives -5/-3 are code acts; judge R6/R7 both -5 on the final-message act | RISKY (R6+R7 can fire together on one false final reply) |
| JD-7 (R5) | oracle meets it | SAFE |
| JD-15/JD-18 (R5) | specific tri-split narrower than ordinary practice | RISKY |
| J1/JD-8 (R1-R4) | figure-copy criteria | RISKY |

None of H1-H4 cost points; none would be NOT ALLOWED. To make any of them cost points, the rule must stop being reflexive without becoming hidden; the QC line that bounds this is IN-15/IN-16 (see GROUP_SUMMARY sec 3).

## 9. Writing style (quotes that made the rule reflexive)
1. schema.md:66-69 "for every station with a non-zero coefficient in its partials whose registry row (section 1) has mount=tripod, add (centring_mm / 1000)^2 ... A pillar mount adds nothing." Names column, file, scope and the exception in one sentence: breaks W1 (explains the trap) and W3 (not a plain form; it is a fully parameterised instruction).
2. schema.md:99-101 "For an angle the difference is a direction difference: it is reduced modulo 400 gon into the half-open range (-200, 200] gon." Gives the reason and the exact range; plus shipped OB00213 (north.csv:221, observed 0.000455 vs computed 399.999545) lets the agent watch it fire: breaks W1 and W5/W6.
3. schema.md:44-46 "Records are matched by their true obs_id (section 7). The record in the shard with the higher revision is the observation" pre-empts both reflexes (raw-id match, first-seen) in the same breath: breaks W1; shipped north rev3/south rev5 duplicates separate the readings: W5.
4. schema.md:193-194 "observation_weight_manifest.csv column naive_weight: the earlier faulty weights." plus instruction.md:1 "produced weights that do not hold up". A decoy whose error is exactly the missing levers becomes an oracle: the agent diffed it (steps 33-34) and confirmed H1 and V0-1 ("differs ... only by the missing unit conversion and the missing tripod centring term"). Breaks W7 (control must be honest-wrong in a way that does not decode the rule) and LEAK_LIBRARY "decoy refuted beside use".
5. schema.md:153-155 "A session applies only while both members are in the network: if one member is removed as a blunder (section 12), the surviving member takes the ordinary diagonal weight" states the exception at the definition: W1.

## Lessons for the master
- Tests 100 is genuine: one write at minute 7, never edited, first run equal to TRUTH; mutant scores measured cost-of-error, not likelihood of error.
- Every H-lever was a single explicit sentence with its exception, and shipped data separated each reading; the agent coded all four on the first write.
- The "faulty" naive_weight manifest is a confirmation oracle for H1; decoys that encode exactly the missing rule must go.
- Judge R1-R4 are figure copies (J1); R5's read/compute/write tri-split is narrower than JD-18 ordinary practice and is the only genuine judge loss.
- The agent's own genericity test changed control values only (steps 47-48), never mounts, revisions or boundary angles: that blind spot is the only lever space left.
