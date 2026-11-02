# C — af6f42c3 (security policy compiler: repair a broken CLI, compile spine, profiles and 50 corpus aggregates)

Paths are relative to the task folder unless noted. Ids used below: T = `tests/test_output.py`, K = `environment/data/config_contract.md`, I = `instruction.md`.

## 1 Scores and verdict
- Scores: overall 69.5, tests 45.83 (44 of 96 positive points), rubric 93.18. Sources: `run_1/report.json`, `pass_summary.json`.
- Step 1 verdict: **PARTLY** (`A_af6f42c3.md`). The graded test file is the same as the repo's: every ctrf name is present and the weight is 0.5/96.
- Genuine test points lost: **26** for certain (one wrong value: spine scope), plus 10 mixed. The other 16 were lost to a key-name gate only.

## 2 Inventory
- Domain: security/ops configuration compiler. Archetype: repair a broken shipped tool (`tool.zip`), then drive it to produce derived artifacts. It is a coupled pipeline: the journal replay feeds the spine, which feeds the shift, which feeds all 50 corpora.
- Files the agent sees (`environment/data`):
  - 50 corpora `c01..c50` in 20 wire formats (csv, tsv, psv, colon, caret, json, jsonl, xml, ini, fixed, md, kv, properties …), each ~3.8–15.6 KB.
  - `change_journal.jsonl`: 9000 ops (base 1776, core 1725, edge 1817, dmz 1811, mgmt 1871).
  - `config_contract.md`, `config_schema.json`, `defaults.json`, `env_overrides.json`, `validation_rules.json` (bounds, allowed_modes, journal_envs, corpus_bounds keyed by corpus stem), `tool.zip`.
- Instruction: 652 words, 21 numbered requirements (`wc -w`).
- Tests: 35 checks. Positive weight 96 (5×9, 3×10, 1×7 per T:1007-1041). Negatives total −19: credentials −3, hardcoded −5, nested −5, fake transcript −3, network −3.
- Judge: `tests/judge.toml` holds 14 criteria in batched mode, positive 44, negative −8 (R7 −5, R8 −3). They are conduct criteria (R1, R2, R4–R6, R12, R13), one figure-reasoning criterion (R11 chained bound) and one code-quality criterion (R14).
- Reward: `tests/reward.toml` test 0.5/96, judge 0.5/44, so the split is 50/50.

## 3 Test architecture
- **How expected values are produced.** They are re-derived at test time from zlib/base64 copies of every shipped file embedded in the test (`_BLOBS` T:71-129; docstring T:1-9 "every reference value is recomputed here from the shipped evidence embedded below, never read from the agent's answer files"). Key functions:
  - `op_ok` T:382
  - `replay(seed, env)` T:403-413
  - `wanted_config` T:420-425, which calls `replay(seed_doc, "base")`
  - `wanted_profile` T:428-437
  - `rekey_shift` T:416
  - `reduce_corpus` T:320
  - `wanted_aggregates` T:337
- **Hidden vs shipped.** There is no hidden or reseeded input. Every check grades the shipped data. Runs of the tool (`tool_round_trips`, `tool_compile_reproduces_rollups` via `_run_compile` T:465-477) also use the shipped data. The agent's CLI runs under `setpriv` as nobody, with `python -I`, cwd /tmp and a 120 s limit (`run_tool` T:511-518).
- **Whole document vs one key per check.**
  - `config_matches_policy` compares the whole document: `load("config.json") == wanted_config()` (T:543-544).
  - Profiles are compared whole, per zone (T:547-551).
  - Aggregates are graded once per wire family (plain, symbol, structured), each worth 5.
  - Mirror views, the index and coverage are checked only for consistency with the agent's own `aggregates.json` (T:3-9). This decouples them from correctness.
- **Partial credit:** none inside a check. `_holds` (T:521-526) turns any exception into False.
- **Gate.** `_agent_agg` (T:554-558) asserts `set(agg) == set(wanted_aggregates())`. Every consistency check calls through it, so a key-name mismatch zeroes them all.
- **Negatives** are polarity-inverted: a negative "holds" only when a cheat is present (T:8-9). Examples:
  - `_neg_hardcoded` (T:799-803): the sum of the expected aggregates appears in the tool text.
  - `_neg_fake_transcript` (T:812-822): `report.json` claims a validate returncode of 0 that the live CLI cannot reproduce.
  - `_neg_network` (T:825-829).
- **Mutation tests:** none.
- **stacking_check.py:** reports 35 checks, positive 96, negative −19, judge 14/44 batched. It gives few class hints because the checks are wrapped in `_holds`. Reading the code: about 100% of the weight is shipped-only, and roughly 45/96 points ride on the spine → shift → corpus coupling (config 5, families 15, views 13, zone_totals 3, index 5, posture 3, validation and summary 8).

## 4 Lever table (failed checks)
| id | w | rule graded | rule locations (quote) | sentence form | agent's reading | correct reading | why self-test missed | fully stated? | nearest |
|---|---|---|---|---|---|---|---|---|---|
| config_matches_policy | 5 | the spine replays only `env == "base"` journal ops | K:14-27 "Replay `change_journal.jsonl` … valid only when … its `env` is listed in `journal_envs`" (journal_envs includes base, core, edge, dmz, mgmt); K:35 profile replays "the valid journal operations whose `env` is that zone"; I:9 "Generate the base spine"; reference T:408 `op["env"] == env`, T:425 `replay(seed_doc, "base")` | scope by omission. The env filter appears only in the profile paragraph; "base" appears only as an adjective in "base spine" | step #11 (t+2.4) replays all valid ops of every env → rekey 21845 | spine = base-env ops only → rekey 30576 (my recomputation in Step 1) | its `verify.py` (t+22.6) checked its own claims against its own replay; nothing visible distinguishes the readings, and profiles still match because the zone replays overwrite every key that differs (`profiles_match` passed) | **HIDDEN RULE**. The literal contract K:14-27 favours the agent's reading | H3 (denominator/scope) / L6 (scope carried by a definition) |
| aggregates_{plain,symbol,structured}_match | 15 | effective upper bound hi + (R mod 97) + (J mod 31) | I:11, K:52-62 "the corpora plant rows above their published `hi` so the combined shift selects which of them count" | plain sentence; cascades from the row above | shift 25 (R 21845) | shift 26 | as above | stated; the error is inherited from R | cascade of L6 (G1 coupling) |
| zone_totals_match / posture_match | 3 + 3 | counted rows per zone / sums | K:180-185 | plain | from shift 25 | shift 26 | as above | stated | cascade (INFERRED) |
| aggregates_{csv,tsv,xml,ini,env,md,txt} | 13 | text views equal agent agg, keyed by corpus name | K:166 "an object mapping each corpus name"; corpus table K:84-90 names `c01_cve_severity.csv` with its extension; stems only in `validation_rules.json` corpus_bounds keys; gate T:554-558 | other: key vocabulary left implicit | keyed output by filename with extension (agent `cli.py:433` uses the stem only for the bounds lookup) | stems | consistency between its own files held | NOT stated (the "corpus name" vocabulary is ambiguous) | NEW (gate on an unstated key vocabulary) |
| corpus_index_match / validation_report_correct | 5 + 5 | index values; `command_failures == []`, `rejected_ops` a list | T:637; T:664-665; K:190-193 names the fields without types | silent value type | wrote 0 and 2113 (counts) | list, list | own schema of its own making | NOT stated (TS-19 silent type) | NEW (silent type) |
| summary_correct | 3 | artifact names plus agg-consistent totals | T:681, through the gate | gate | key gate | — | — | — | gate |

## 5 How the tests handle QC
- **TS-13 (one property per check).** Mostly one per check: family split T:561; one document per check. `_profiles_match` bundles four zones in one check. QC accepted it (district-heat v3:176 "whole-document per view is one property").
- **TS-16 (honest work never trips a negative).** Each negative fires only on a cheat artifact: hardcoded sum (T:799-803), live validate rerun contradicting the transcript (T:812-822). The honest run tripped none (ctrf: all negatives "failed").
- **TS-19 (test no stricter than the contract; types stated).** RISKY and still passed.
  - The reference spine scope (T:408/425) is stricter than the literal K:14-27.
  - The validation_report types are unstated (T:664-665 vs K:190-193).
  - QC_RULINGS:49 rates a "certificate value type … stated nowhere" as FAIL (CL-5, dispatch v1:41). Here the same shape passed.
- **TS-20 (weights by importance).** 5/3/1 tiers by importance (T:1007-1041); negatives −5/−3.
- **TS-26 (one observable paid once).** Views are graded for consistency, not re-graded for value (T:3-9). This is an explicit design that avoids paying the value six times. But the key gate makes 13 points depend on a single naming fact anyway.
- **IN-15 (rules stated in readable files).** Rules are delegated from I to K; the kit allows this (`01_Instruction_QC.md:45`).
- **IN-16 (two readings).** The spine scope has two defensible readings. Nothing in the shipped data settles it, and it is graded. That meets all three parts of `01_Instruction_QC.md:46`, yet it passed QC. RISKY.
- **AL-28 (one act penalised in one layer).** Hardcoding: test −5 and judge R7 −5. They target different acts (R7 is "retrieves a task-specific repaired cli", i.e. an online lookup), so there is no double layer for one act.
- **CL-4 (one wrong fact costs about one fact).** One fact (R) moves config 5 + families 15 + zone 3 + posture 3, plus parts of index and validation. That is amplification. The instruction states the coupling outright at I:11 ("a misclassified journal op moves the effective bound of every corpus"). That is the kit's deliberate-bar exemption (`Final_checklist.md:491` "An instruction that states out loud …"), applied to coupling rather than to exactness.
- **JD-7 (oracle meets judge criteria).** R11 (chained bound reasoning) and R12 (verifies serialized bytes) are conduct and figure criteria that the oracle's transcript can meet. The agent passed 13 of 14.

## 6 Leak avoidance
- Wording, with the matching W-rule:
  - W3/W4 bare property: K:14-27 "valid only when all hold: its `env` is listed in `journal_envs`". The filter that matters is absent; its presence in K:35 for zones is the only signal.
  - W2: the rule sits away from its use. "base spine" appears in I:9 and the zone filter in K:35, two files apart. Nothing ties them together.
  - W1 inverted, the coupling is advertised rather than hidden: I:11 "a misclassified journal op moves the effective bound of every corpus". The authors tell the agent that the pipeline is fragile but not where. That is safe because it names a consequence, not a rule.
  - W5: the shipped data cannot separate the readings by any visible check. The profiles reconcile under both readings (the zone replay overwrites the differing keys), and there is no example output.
- Visible tests or examples: none. `sample` outputs absent.
- Naming: the corpus stems exist only as keys of `validation_rules.json`.
- LEAK_LIBRARY comparison:
  - Row "2-file split pointed together" (CR-5): they did NOT point the two halves together. Our CR-5 leaked because the instruction said "see X and Y".
  - Row "shipped boundary rows let agent watch rule fire" (RUN): here the shipped outputs agree under both readings, so watching proves nothing.

## 7 Agent behaviour
- Order of work:
  - t+0.1: read the contract.
  - t+0.3–3.2: read all data.
  - t+2.4 (step #11): its replay sketch already took all envs.
  - t+12.0: `cli.py` created. t+12.8: `build.py`. t+13.1: first full run.
- The graded logic never changed after the first program. Later edits were audit and format only.
- Self-tests:
  - consistency audits (t+16–18.5)
  - determinism (t+19.2)
  - `verify.py` (t+22.6–23.2), which re-checks its own claims with its own replay. It covers serialization, determinism and the integer grammar (lever J). It does not cover spine scope (lever R).
- Final claim (t+25.4): "complete, deterministic, and fully verified", "R = 21845 → shift 20 + 5 = 25". Reality: R is 30576 and the shift is 26, so 52 of 96 points were lost.

## 8 Passed checks
- **Integer-grammar classification of the journal:** `rejected_ops_match` 5. It is stated exhaustively in I:10 and K:16-27 as an enumerated reject list. Opus transliterates enumerations.
- **Profiles:** 5. They are robust to the spine error, as described above.
- **Tool mechanics:** report_transcript_real 5, digest 3, manifest 5, round trips 5, canonical bytes 3, zip deterministic 3, compile reproduces 3 and deterministic 1, trailer 1, regular files 1, scalar types 3. All are format or mechanics checks against a fully specified `json.dumps` call (K:160-164) that the agent self-checks byte for byte.

## 9 Take-aways
- SAFE (adopt): grade mirror views for consistency with the agent's own primary output, not re-graded for value. This pays an observable once (TS-26) and keeps negatives cheat-only.
- SAFE: announce the coupling in the instruction ("one wrong upstream fact moves every downstream figure"). This invokes the CL-4 deliberate-bar exemption without naming which fact.
- RISKY: scope carried by an omitted filter whose literal reading favours the agent. It passed QC here, but it meets all three IN-16 parts. Ours should state the scope plainly in the governing file and keep the separating case hidden (L6 within W3).
- AVOID: gate many checks on an unstated key vocabulary (file name vs stem). It priced 13 points on naming, not reasoning. State key forms explicitly.
- AVOID: unstated value types for graded keys (TS-19/CL-5). It passed here but failed for us.
- RISKY: 100% shipped-only grading. It works only when the shipped outputs agree under both readings; there is no rerun tier to catch hardcoding (compare G3).
