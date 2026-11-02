# 08 registry-lock-footprint-resolution (claude-opus-5, run_1): overall 27.40 %, tests 2.16 %, rubric 52.63 %

Paths: copy dir `tasks_copy_20261022T0105/08_registry-lock-footprint-resolution/` (called T). Notes: `notes/08.md`. All "UNVERIFIED" marks are guesses from static reading (no runs).

## 1. Shape
- Bundle: `instruction.md` (13 lines, 552 words), `task.toml`, `environment/Dockerfile` + `environment/data/` (29 files), `solution/` (solve.sh, solve.py 26.5 KB, TRUTH.md 16 KB), `tests/` (test_output.py 2608 lines / 112 KB, judge.toml, reward.toml, test.sh, Dockerfile).
- Data (T/environment/data): 10 `.md` docs (calibration, conventions, feature-policy, footprint-policy, identity-policy, index-format 5.2 KB, licence-policy, rehearsal-decodes, report-schema, resolution-policy), 3 `.csv` (package-registry 18 rows, workspaces 5, workspace-requirements), 1 `example-report.json`, 15 binary `.pidx` shards of 146-640 bytes (2 rehearsal, 5 calibration, 8 field). 14 doc files. Binary format with 11 optional transforms, 6 withheld constants (10 candidates each = 60 candidates).
- Outputs (task.toml:3): `/app/out/optimize.py` + 9 JSON documents (5 scenario_*, perf_report, bottleneck_analysis, data_quality, recommendations).
- Tests: 35 criteria = 31 positive (weights 4x1 shipped + 11x5 trap + 16x5 held_out = 139) + 4 negative (-5,-5,-5,-3 = -18) (test_output.py:2540-2580). Judge: 9 criteria = positive 19 (R1-R5 w3, R8 w3, R9 w1), negative -8 (R6 -3, R7 -5) (judge.toml). reward.toml:3: each channel half (0.5/139, 0.5/19).
- Timeouts: agent 10800 s, verifier 3600 s (task.toml); program run limit 60 s (test_output.py:1844). Verifier mode `separate`.
- Run: 43 trajectory steps, 63 min, 818k prompt / 24k completion tokens.

## 2. Is the low score genuine? (static screen)
Classification (deciding line, T/tests/test_output.py):
| check | class | deciding line |
| --- | --- | --- |
| delivers_every_document, shipped_index_is_decoded, shipped_workspaces_are_settled, shipped_derivation_is_recorded | READ | :2294-2319 read `workspace/"out"/*.json` only (`_decode_problems(workspace / "out", ...)` :2309) |
| negative_hardcoded_sample_answers | READ | :2496 reads program source text |
| 11 trap_* | EXEC | :2331-2332 `_trap` -> `_run_staged` -> `subprocess.Popen(_untrusted_command([sys.executable, str(script), ...]))` :1938-1939 |
| 16 held_out_* | EXEC | :2399-2402 `_held_out` -> `_run_staged` |
| negative_filename_dependent, negative_reads_supplied_answer, negative_nondeterministic | EXEC | :2514, :2524, :2531 (`_shipped_pair` runs the program twice) |

- No EXEC check passed. ctrf: all 27 positive EXEC checks failed. The 3 EXEC negatives show "passed" only because an unrunnable program yields empty documents on both runs, so `renamed != plain` is False (:2270-2280, :2514-2515); that is not evidence the program ran.
- How the tests run the program: `_untrusted_command` (:1878-1889) prefixes `setpriv --reuid=nobody --regid=nogroup --clear-groups` when euid is 0 (:1865). The only chmods are on staged INPUT copies (`_relax` :1898-1901, out dir 0777 :1932). Nothing makes `/app/out/optimize.py` or `/app/out` readable by nobody. `tests/test.sh:7-8` and `tests/Dockerfile` chmod only `/logs/verifier` and `/tests` (`chmod -R go-rwx /tests`), plus `mkdir -p /app` as root.
- Trajectory: the editor `create` made every program 0600: step 24 `ls -la /app/work` shows `-rw------- 1 agent agent` for each .py; steps 35, 36, 41 show `-rw------- 1 agent agent 41156 ... optimize.py` while python-written JSON files are `-rw-r--r--`. The agent's own runs worked as uid agent (steps 29, 36, 37: 0.08-0.10 s, 9 documents, byte-identical on a renamed copy). Artifacts go agent container -> host -> verifier container with `upload_file` at the same path (Harbor `artifact_handler.py:230-254`); the file mode on arrival is UNVERIFIED (host copies lost modes in git: all 0644 in T).
- Delivered documents match what the READ checks need for decode and record: `shipped_index_is_decoded` and `shipped_derivation_is_recorded` passed. One READ check failed for a real defect (below), so part of the loss is genuine.
- Other breakers: runtime 0.08 s vs 60 s; no hardcoded paths (optimize.py:1110-1117 takes both directories from argv); stdlib only (optimize.py:12-18); `setpriv` present (tests/Dockerfile:2-4).
- Bound: even with a runnable program the 16 held_out checks would fail on the same real defect (step 4), so the recoverable amount is about the trap tier: (3 + 55)/139 = 41.7 % tests, ~47 % overall instead of 27.4 % (UNVERIFIED).
- QC blind spot: the oracle does `cp /solution/solve.py /app/out/optimize.py` (T/solution/solve.sh:6), which yields a readable file, so Step 10 cannot see the problem.
Label: SUSPECT - 27 of 27 EXEC checks failed incl. all 11 single-transform decode traps although the same decoder reproduced all shipped READ decode figures; the program was a 0600 file (traj steps 35/36/41) run as `setpriv nobody` with no chmod in the tests (test_output.py:1938-1939, 1898-1901).

## 3. Instruction anatomy
- Goal first (instruction.md:1): "A package registry publishes its index as binary shards ... Six registry constants were withheld ... exactly one assignment of the six reproduces every one of those figures. The documents state every rule, but not the order in which the rules act on one another."
- Deliverable (:3): one program `/app/out/optimize.py` taking an input directory and an output directory; "freshly built directories ... each carrying its own withheld constants ... so every figure it writes has to come from the directory in front of it"; sixty seconds per run. Nine documents listed by absolute path (:5); form: "JSON with two space indentation, keys in ascending order and a closing newline" (graded, test_output.py:2199-2206).
- Leaves for the agent: the byte format (index-format.md), which transform applies in which order, how to recover the constants, the plan search, every rule detail. Rules live in 10 data docs; the prompt only lists them by kind (:1).
- Procedure vs end state: end state plus five "working rules" (:9) that are almost word for word the judge criteria R1-R5: "State the falsifier of each rival in the session at the moment you set that rival aside", "Write out the comparison of reproduced and published control figures before you read any field shard with the recovered constants", "Before you settle any workspace, write out the governing licence family of every package whose rename chain carries more than one name", clean regeneration, replay on a renamed copy. These are conduct/order rules; no algorithm is given.
- Asks the agent to report: nothing (no final-message content). Tone: one dense paragraph per topic, long sentences, no headings or bullets.
- Side by side with ours (emberforge 448, vendor 571, schema 350, district 408 words; 08 is 552): length is not different. Ours add inline output conventions and sizes (district: "Energy is in whole ticks, money in whole cents ... sorted keys and a trailing newline", "up to 22 sites"; emberforge "up to 48 requisitions", "38 seconds on 2 CPUs"), name a start file (vendor: "Start with `/app/data/format_contract.md`"; district: "Treat schema.md as the authority"), and end with a required account in the final message. 08 does none of these.
- Hypothesis check ("ours tell the agent too precisely what to do"): for 08 the evidence is weak. 08 is as explicit as ours about the end state and more explicit about order of work; it is less explicit about where rules are and about hidden-input size. The score gap here is explained by grading (27 of 31 positive checks run the program on unseen populations; weight 135/139) and by the process judge, not by a vaguer prompt. UNVERIFIED beyond this one task.

## 4. Every failed positive check and every fired negative
ctrf: 35 tests, 28 failed positives, 0 fired negatives; all covered below. (Passed positives: delivers_every_document, shipped_index_is_decoded, shipped_derivation_is_recorded, all w1. The 4 negatives did not fire; with the program unrunnable they could not.)

Cause key: P = program not executed by verifier (permission, SUSPECT, UNVERIFIED); Q = the inverted `quarantined_records` defect (real, in every scenario document).

| check (w) | what it checks / rule and where | what the agent did (traj step / artifact) | cause |
| --- | --- | --- | --- |
| shipped_workspaces_are_settled (1) | the 5 shipped scenario docs, bottleneck, plan keys of perf_report equal truth (:2063-2088). `quarantined_records` rule: resolution-policy.md:17-19 "quarantined ... published fewer than the quarantine days before it"; the field is only named in report-schema.md:17 | optimize.py:983-991 counts records with `snapshot - day >= quarantine` (the eligible ones) under the name quarantined_records; artifact values 38/41/36 (step 34). Copy of the eligible loop at optimize.py:520-532 without inversion | read but misapplied (Q); other fields UNVERIFIED but derivation record passed so passes/divergence/footprint likely right |
| trap_mask_bytes (5) | keystream XOR mask on artifact bytes; index-format.md:66 | optimize.py:333-337 matches the CRC keystream (salt+nonce+key+ordinal LE); shipped bytes exact (shipped_index_is_decoded passed) | P (predicted PASS if run) |
| trap_chain_version (5) | version codes as differences; index-format.md:67 | optimize.py:210-213 cumulative sum | P (predicted PASS) |
| trap_delta2_day (5) | second order day; index-format.md:68 | optimize.py:215-220 `stored + 2*d1 - d2` | P (predicted PASS) |
| trap_drift_key (5) | block key = nonce XOR sum of earlier true bytes; index-format.md:69 | optimize.py:325-340 | P (predicted PASS) |
| trap_block_permute (5) | inverse shuffle; index-format.md:70 | optimize.py:289-315 | P (predicted PASS) |
| trap_backref_deps (5) | ring tags; index-format.md:71 | optimize.py:233-251 (`ring[span - tag]`, front insert, drop last) | P (predicted PASS) |
| trap_endian_island (5) | big endian nonce and counts; index-format.md:72 | optimize.py:118, 177, 195 | P (predicted PASS); this flag is absent from shipped field_03 (0x07bf) but present in calibration shards |
| trap_biased_count (5) | count bias; index-format.md:73 | optimize.py:144-153 and parse to area end, optimize.py:181-187 | P (predicted PASS) |
| trap_rot_status (5) | rotated status word; index-format.md:74 | optimize.py:221-228 (rotr by (base + k%8)%16) | P (predicted PASS) |
| trap_xref_key (5) | companion shard nonce XOR key; index-format.md:75 | optimize.py:131-141, 193-194 | P (predicted PASS) |
| trap_split_tail (5) | pad after trailer; index-format.md:76 | optimize.py:274-277 | P (predicted PASS); absent from shipped field_06 (0x03ff) |
| held_out_tie_footprint (5) | footprint ties: larger code sum then plan text; footprint-policy.md:5-8 | tie order implemented optimize.py:795-798 `(total, -code_sum, text)` | P + Q (Q alone fails it: `_plan_problems` diffs whole scenario docs :2070-2075) |
| held_out_temporal_edge (5) | exactly quarantine days old is eligible; resolution-policy.md:13-14 | implemented `<` strict skip, optimize.py:734; the quarantined count uses the same test inverted | P + Q |
| held_out_invert_chain (5) | earliest name governs licence; licence-policy.md:13-16 | optimize.py:455 | P + Q |
| held_out_flip_licence (5) | OR/AND family rule; licence-policy.md:9-11 | optimize.py:420-427 | P + Q |
| held_out_empty_copyleft (5) | population with no copyleft package | not special-cased | P + Q |
| held_out_feature_cycle (5) | fixpoint across chains; feature-policy.md:11-20 | settle() loops to fixpoint, optimize.py:689-714 | P + Q |
| held_out_add_entity (5) | extra package moves plans | generic search | P + Q |
| held_out_yank_wave (5) | yanked excluded; resolution-policy.md:11 | optimize.py:730 | P + Q |
| held_out_scale_bytes (5) | 10x bytes, 2x shards | generic; search cost UNVERIFIED (branch and bound optimize.py:807-846) | P + Q (+ possible time risk, UNVERIFIED) |
| held_out_unregistered_burst (5) | unregistered targets; identity-policy.md:13-15 | optimize.py:781-783, 817-819 | P + Q |
| held_out_allow_copyleft (5) | all workspaces allow copyleft; licence-policy.md:18-19 | optimize.py:723 | P + Q |
| held_out_narrow_roots (5) | narrower requirements; resolution-policy.md:26 | optimize.py:747-762 | P + Q |
| held_out_wide_catalogue (5) | wider version catalogue | generic | P + Q |
| held_out_no_backref (5) | no repeated dependency entry | generic | P + Q |
| held_out_extend_chain (5) | longer rename chain; identity-policy.md:3-6 | optimize.py:445-470 | P + Q |
| held_out_early_snapshot (5) | earlier snapshot days | generic | P + Q |
Points: 28 failed positives lose 135 of 139 weight (97.1 %). Of that, the trap tier (55) depends only on P; the held_out tier (80) fails on Q regardless of P (UNVERIFIED that no second defect exists); shipped (1) is Q.
Checks that a lazy agent also passes: `delivers_every_document` (existence and serialised form only); all 4 negatives (no firing for a program that does nothing). Judge: R6 (no write under /app/data) and R7 (no false agreement claim) are free for a quiet agent.

## 5. Levers
| lever | family | where documented | weight share lost | triggered this run |
| --- | --- | --- | --- | --- |
| Program run as dropped uid on an agent-written 0600 file | NEW (harness/permission) | not documented anywhere the agent sees; test_output.py:1878-1889, 1917-1953 | trap tier 55/139 = 39.6 % of tests (19.8 pp overall); gates all 135/139 = 97.1 % (UNVERIFIED) | probably yes |
| Whole-document equality on hidden populations: one wrongly derived side field (`quarantined_records`) voids every compare | NEW (field cascade) / A (cross-file: schema names it, resolution-policy defines it) | report-schema.md:17, resolution-policy.md:17-19 | 80/139 = 57.6 % of tests (28.8 pp) + 1/139 | yes (Q) |
| Conduct order rules judged on the trajectory (R1-R3) | NEW (ordering/timing of write-ups) | instruction.md:9; judge.toml R1-R3 | 9/19 = 47.4 % of judge (23.7 pp) | yes |
| Eleven stacked transforms with withheld constants, shuffle before drift, companion shard | B dependent chain + E stacked constraints | index-format.md:64-78 | 0 lost for skill (decoder correct), 55/139 only via P | handled |
| Candidate elimination against controls, exactly one assignment, falsifier labels | A/B | calibration.md, conventions.md:3-20 | 0 lost | handled |
| Governing licence from earliest name (against instinct), divergence list | A | licence-policy.md:13-16, conventions.md:18-20 | 0 lost | handled |
| Feature fixpoint + pass count | B | feature-policy.md:11-20 | 0 lost | handled |
| False agreement claim (negative -5) | F-like honesty trap | judge R7 | 0 (not fired) | no |

## 6. Judge
| id | w | met? | why |
| --- | --- | --- | --- |
| R1 falsifier of each rival when set aside | 3 | NO | printed all rivals only in step 31 after `recover()` had rejected them; searches in steps 16/19/21/26 set candidates aside silently |
| R2 control comparison before reading field shards | 3 | NO | step 23 `explore.py` decoded field shards with hard-coded recovered constants; table only at step 31 |
| R3 licence families of multi-name chains before settling | 3 | NO | first settlement run at step 29, families printed at step 31 |
| R4 clean regenerate | 3 | yes | steps 35-36 |
| R5 renamed copy compare | 3 | yes | step 37 |
| R6 write under /app/data (-3) | | not fired | step 38 check |
| R7 false agreement claim (-5) | | not fired | table matched (derivation record check passed) |
| R8 code quality | 3 | yes | 41 KB program, functions and docstrings |
| R9 plain reader on rehearsal shards | 1 | yes | steps 9-13 |
Rubric = 10/19 = 52.63 %. Criteria avoid paying twice: TRUTH.md:137-145 states that tests grade document values and the judge grades only conduct and program readability; no judge criterion restates a figure. R1-R3 are tied to the order of events in the trajectory, so they can be failed by an agent that builds everything and demonstrates afterwards (as here).

## 7. How it passes QC and still beats the agent
- Everything is documented: transforms (index-format.md:64-78), earliest-name licence (licence-policy.md:13-16), inclusive quarantine boundary (resolution-policy.md:13-14), fixpoint and pass counting (feature-policy.md:11-20), byte conservation (footprint-policy.md:15-21). The instruction states the five conduct rules, so IN-15 is satisfied.
- What makes traps easy to miss: `quarantined_records` is named in report-schema.md:17 with no definition and defined two files away in resolution-policy.md:17-19 using the word "quarantined" for the opposite subset of the one the eligibility rule uses; the agent copied the eligibility loop and forgot to flip the test. The ordered write-ups (R1-R3) are cheap in isolation but are lost when evidence is staged after the build.
- Anti-cheat: 4 negatives (digit scan of source for shipped answers test_output.py:2494-2505; shard renamed copy :2509-2515; poisoned example report :2519-2525; run twice for determinism :2529-2534) and hidden populations carrying their own constants (corpus_params :625-638; calibration shards always carry all flags :713, field flags vary :743-746).
- QC gap: Step 10 uses the oracle, which copies a readable file, so a 0600 agent program would never be seen. Also positive weight 135/139 sits on EXEC checks, so one execution failure zeroes the channel (no READ fallback for partial credit).

## 8. Trajectory story
- 43 steps, 63 min of agent time; large gaps (about 9 min) between steps 22-28 look like long model thinking (timestamps 08:02 to 08:44).
- Read order: `ls` (3), index-format (4), conventions + calibration + report-schema (5), five policies (6), rehearsal-decodes + registry + workspaces + requirements + example (7), xxd of all shards (8). No doc left unread.
- Built: plain reader (9-13), full decoder (14), constant search (15-16, 19, 26), ring test (20-21), field exploration with hard-coded constants (22-23; first judge violation), then one 41 KB optimize.py (28), a 0.1 s run (29), a stage script printing the rule evidence (30-31), document dump (32-34), clean regenerate (35-36), renamed copy diff (37), checks (38-40), cleanup (41), finish (43).
- First wrong turn for tests: step 28, inverted quarantined count. First wrong turn for the judge: step 23.
- Self-test: byte-identical outputs on a renamed copy of the same data only; no second population. The agent never viewed or reasoned about `quarantined_records` after writing it (values printed at step 34 were not checked against the policy).
- Final message (step 43): claims "all six matched before any field shard was read with the recovered constants" - contradicted by step 23 (judge R2). Claim of divergence = three forbidden workspaces is consistent with the passed record check.

## 9. Reusable patterns / things to avoid
- Put 97 % of the weight on running the delivered program over hidden populations with their own constants: it blocks hardcoding, but make the run robust (chmod the program and its directory in the test, or copy it into a root-owned readable path) or one permission fault zeroes everything.
- Add a READ fallback tier of existence/serialised-form checks per document type so a runner failure does not erase all partial credit.
- A field named in the schema but defined only in another policy (`quarantined_records`) is a strong cross-file trap; keep it, and compare whole documents so one misread field matters.
- Judge conduct rules tied to ordering ("before you read any field shard", "at the moment you set that rival aside") cost an agent that builds first and demonstrates later; the instruction states them but they are cheap to forget. Keep them to a few and phrase as observable events.
- Avoid: oracle that copies a readable file while agents create 0600 files (QC Step 10 blind spot); avoid negatives that read as free points for a program that does not run.
- Rules written in 10 docs without a "where to start" pointer plus conduct rules did not make the prompt vaguer than ours; the prompt style is not the lever here.

```json
[
  {"task":"08_registry-lock-footprint-resolution","name":"exec_under_dropped_uid_on_agent_file","family":"NEW","mechanism":"27 EXEC checks run the delivered optimize.py via setpriv nobody; the editor creates the file 0600, nothing in tests chmods it","where_documented":"tests/test_output.py:1878-1889,1917-1953 (not visible to the agent)","weight_share":0.396,"triggered":true,"cause_of_failure":"other: program not executed by verifier (UNVERIFIED)","evidence":"traj steps 35/36/41 show -rw------- optimize.py; all 27 EXEC checks failed while READ decode checks passed"},
  {"task":"08_registry-lock-footprint-resolution","name":"whole_document_equality_field_cascade","family":"NEW","mechanism":"every held-out check diffs whole scenario documents, so one wrongly derived field (quarantined_records) fails all 16","where_documented":"report-schema.md:17; resolution-policy.md:17-19","weight_share":0.576,"triggered":true,"cause_of_failure":"read but misapplied (inverted condition)","evidence":"optimize.py:983-991 counts non-quarantined records; shipped_workspaces_are_settled failed"},
  {"task":"08_registry-lock-footprint-resolution","name":"ordered_write_ups_before_actions","family":"NEW","mechanism":"judge criteria R1-R3 require evidence statements before specific actions in the session","where_documented":"instruction.md:9; judge.toml R1-R3","weight_share":0.474,"triggered":true,"cause_of_failure":"other: built first, demonstrated after (output order)","evidence":"step 23 explore.py read field shards with recovered constants; stage.py only at steps 30-31 after optimize.py ran at 28-29"},
  {"task":"08_registry-lock-footprint-resolution","name":"eleven_transform_decoder_stack","family":"B","mechanism":"sequential transforms (shuffle before drift key, companion shard) with five withheld constants","where_documented":"index-format.md:64-78","weight_share":0.0,"triggered":false,"cause_of_failure":"none for skill; points only lost through the permission lever","evidence":"shipped_index_is_decoded passed; calibration controls matched (step 26)"},
  {"task":"08_registry-lock-footprint-resolution","name":"earliest_name_governs_licence","family":"A","mechanism":"licence of a renamed package comes from the earliest name; divergence list from the newest-name reading","where_documented":"licence-policy.md:13-16; conventions.md:18-20","weight_share":0.0,"triggered":false,"cause_of_failure":"none","evidence":"shipped_derivation_is_recorded passed"},
  {"task":"08_registry-lock-footprint-resolution","name":"candidate_elimination_with_falsifiers","family":"A","mechanism":"exactly one of 10^6 assignments reproduces six controls; every rival gets a first-failing control label","where_documented":"calibration.md; conventions.md:3-20","weight_share":0.0,"triggered":false,"cause_of_failure":"none","evidence":"step 26 total full matches: 1; record check passed"}
]
```

## Phase B: Docker replay of the saved run (tests only)

Method: Harbor 0.24.0 on Docker, QC Step 10 copies built by `exe_copy.py` (judge removed, tests-only weights, network opened). `solution/solve.sh` was replaced by a script that copies the saved `trajectories/claude-opus-5/run_1/artifacts/app/` files into `/app` as the oracle agent (uid 1000, the same uid as the real agent), then sets modes. V600: every delivered `.py` 0600, other files 0644. V644: every file 0644. One run per variant, 22 Oct 2026 09:19-09:24 IST (03:49-03:54 UTC). The oracle log of each trial confirms the mode (`-rw-------` in V600, `-rw-r--r--` in V644). No trial raised an exception. The judge was not run, so the rubric figure below is the recorded one.

| variant | tests reward | per-check result vs recorded ctrf.json |
|---|---|---|
| V600 | 0.0216 | identical (0 of 35 checks differ): faithful replay |
| V644 | 0.4173 | 11 checks change, all fail -> pass: the 11 `trap_*` checks (w5 each, 55/139). All 16 `held_out_*` checks and `shipped_workspaces_are_settled` still fail; no negative fires |

Verdict: BROKEN GRADE for the trap tier, confirmed; the held-out loss is GENUINE. V600 reproduces the record, so the 0600 `optimize.py` was unreadable to `setpriv nobody`. Readable, the decoder passes every single-transform trap (the step 4 "predicted PASS" rows are now observed). The held-out tier fails even when the program runs, which fits the inverted `quarantined_records` count (`optimize.py:983-991`). That this is the only defect remains UNVERIFIED. Corrected overall: 0.5 x 41.73 + 0.5 x 52.63 = 47.18 %, not 27.40 %. Lever shares become: harness 19.8 pp overall (observed), cross-file-field cascade 29.1 pp (genuine).
