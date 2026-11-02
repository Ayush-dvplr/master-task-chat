# C_8da8ba3d: security-config CLI repair and multi-artifact reconcile

Task root `Perfect_for_Delivery/Sugam_Agrawal/8da8ba3d-5e8e-5804-9995-d32d520a9e69/` (T). Run `T/trajectories/claude-opus-5/run_1/`. Step numbers are 0-based indices into `agent/trajectory.json` `steps`.

## 1. Scores and verdict
- Overall 61.92. Tests 87/112 = 77.68. Rubric 12/26 = 46.15.
- Verdict: **GENUINE** (see A_8da8ba3d.md). The run had no crash, no gate and no path fault.
- Genuine test points lost: 25/112 = **22.3 points of the tests score**. 20 of them come from one unfixed arithmetic fault (pbkdf), which is graded by 4 checks. The other 5 come from one comment-format change in the PEM artifact.

## 2. Inventory
- Domain: security policy platform ops. Archetype: repair a shipped broken CLI (`tool.zip`: `cli.py` + `README.md`), drive it over a corpus, and publish 22 artifacts in 12 formats.
- Files the agent sees: 56 entries in `/app/data`. They include the contract files `config_schema.json`, `validation_rules.json`, `env_overrides.json`, `defaults.json` and `hardening_profiles.yaml`, two `sample_config_{dev,prod}.json` hint files ("hints only and must not be copied", instruction.md:19), and about 48 policy files in csv/tsv/jsonl/yaml/toml/ini/properties/conf/txt/pem. The corpus has context-only distractors with header comments, e.g. `pbkdf_profiles.yaml:1` "# pbkdf reference profiles (context; not used as base)". There is no rules document (.md). Every rule lives in the instruction, in field values, or in the shipped code.
- Instruction: 109 lines, 881 words. It names the fault classes only ("faults in argument routing, key normalization, and derivation arithmetic", instruction.md:2-3) and gives per-artifact filters (:56-101).
- Tests: `tests/test_output.py` 1057 lines, 36 checks (30 positive = +112, 6 negative = -24, registrations :1022-1057). Weights are 5/3/1. Negatives: -5 x3, -3 x3.
- Judge: `tests/judge.toml` mode "batched" (:3), 10 criteria (8 positive = +26, R9 -5 and R10 -3).
- Reward split: tests 0.5/112 and judge 0.5/26 (TRUTH.md "Load-bearing work"), which gives 50/50.

## 3. Test architecture
- **Expected values are fixed literal constants** produced by the reference solution: `EXPECTED_CONFIG` (:104-130), `EXPECTED_PROFILE_DEV` (:132), `EXPECTED_PROFILE_PROD` (:160). The docstring (:11-13) says: "The verifier container has no /app/data mount (separate mode) ... expected derived values are encoded as EXPECTED_* constants computed by the reference solution". There is a separate verifier image (`tests/Dockerfile`, python:3.12-slim + rewardkit 0.2.1).
- **There are no hidden inputs.** Every value check grades the agent's outputs on the shipped corpus. The only "unseen" inputs are CLI probes run as `nobody` through `setpriv` (`_setpriv_prefix` :293, `run_repaired_cli` :309, with a clean env and a 90 s timeout):
  - `init` against an embedded schema copy (:503-511, inside `report_records_full_cli_transcript` :481);
  - `set --key Rotation_Days --value -42` (`set_preserves_key_and_coerces_negative` :909);
  - `validate` against the delivered config (:878);
  - a bare invocation must exit non-zero (:900).
  These probes act as small behaviour mutations. They are not reruns on a mutated corpus.
- **Isolation.** Each artifact check reads one file and compares one figure or shape against `EXPECTED_CONFIG`. Examples: cipher line count == 154 (:660-672), egress allow-lines == 129 and sorted (:675-688), PEM `# score=` sum == 936 (:691-702), compliance total and row sum == 548 (:705-721), XML children == 4 config scalars (:742-756). The three config/profile checks (:388, :410, :419) are **whole-document** `all(cfg.get(k)==v for k in EXPECTED)` comparisons over 25 keys. A single wrong key fails all three, and the pbkdf "law" check (:445) grades the same key a fourth time. That makes one fact worth 20/112 = 17.9 test points.
- **Laws as tests.** `pbkdf_iterations_obeys_power_of_two_multiplier_law` (:445-462) requires `cfg % 100000 == 0`, ratio a power of two > 1, dev*2 == cfg and prod == cfg*2. `rate_limit_burst_is_three_times_rps` (:465-478) requires burst == 3*rps across all three files. Both are derivation-fault detectors written as invariants, so the test checks the shape of the fix and not only the value.
- **Partial credit:** none inside a check. Credit is per artifact only.
- **Negatives / anti-cheat** (each one fires only on a positively present act, with "Fires only when ..." comments): network imports (:927), URL/secret material in outputs (:938), sample-hint string copied into config (:956-966), nested value or dynamic key in config (:969-982), a byte-identical copy of the shipped broken cli.py inside the delivered zip (:985-1000, via `_SHIPPED_CLI_SHA256`), and an expected scalar literal inside the body of `derive_values` (:1003-1012, which searches `EXPECTED_CONFIG` pbkdf/rps/trust-anchor numbers).
- **Weight shares** (stacking_check said "isolated 94.6%, shipped_only 6, G3 hidden 0%"). Corrected by reading the code:
  - hidden or mutated corpus reruns: 0%;
  - CLI behaviour probes: init 5 + set 1 + validate 5 + bare 1 = 12/112 = 10.7%;
  - everything else is fixed-literal comparison on shipped data;
  - the 25 keys of the main config underpin about 60 of the 112 points through `EXPECTED_CONFIG` lookups, but each artifact check uses only its own key.

## 4. Lever table (every failed check)
| id | w | rule graded | all locations (file:line quote) | sentence form | agent's reading (step) | correct reading | why self-test missed | fully stated visibly? | nearest |
|---|---|---|---|---|---|---|---|---|---|
| config_matches_expected_derived_values (:388) | 5 | pbkdf = base * 2**max_tier | instruction.md:2-3 "faults in ... derivation arithmetic"; :29-31 "according to the interaction rules each file declares through its own field values"; shipped cli.py:159 `int(defaults["base_pbkdf_iters"]) + (2 ** max_tier)`; defaults.json:4 `"base_pbkdf_iters": 100000`; env_overrides.json:4-5,12-13 `pbkdf_scale_num/den` (1/2, 2/1); validation_rules.json:11-14 bounds [50000, 100000000]. Only TRUTH.md:30-33 states it: "the `2 ** max_tier` term only reads as a scale factor, and `env_overrides.json` scales pbkdf multiplicatively" | implied by a definition (a fault in code with a weak semantic carrier) | final step 40: "`pbkdf_iterations = base_pbkdf_iters + 2**max_active_tier` (100032) was left as-is. Unlike the two faults I fixed, it has no internal contradiction (no second code path disagrees, no field-name semantics violated, and it sits well inside its bounds), so I had no evidence it was injected" | treat `2**tier` as a multiplier (iterations scale geometrically; the profiles scale pbkdf by a ratio) | the agent's validate step checked bounds only (step 35 "bound pbkdf_iterations :: 100032 PASS"). No shipped value pins pbkdf: the samples carry none and the profiles file is labelled context | **HIDDEN RULE** (inferred-only fault) | NEW: "unflagged fault in shipped code"; nearest L2/H5 (make-it-match in reverse: no contradiction, so no repair) |
| profile_dev_matches_expected (:410) | 5 | same key, dev = cfg*1/2 | same | same | dev 50016 (step 32) | 1600000 | same | HIDDEN RULE (same root) | stacking on one fact |
| profile_prod_matches_expected (:419) | 5 | same key, prod = cfg*2 | same | same | prod 200064 | 6400000 | same | HIDDEN RULE (same root) | stacking on one fact |
| pbkdf_iterations_obeys_power_of_two_multiplier_law (:445) | 5 | cfg % 100000 == 0 and ratio a power of two | test only; the description says "base times a power of two" | test-only law | as above | as above | as above | HIDDEN RULE | stacking on one fact |
| trust_anchor_manifest_pem_blocks (:691) | 5 | PEM carries `# score=<n>` comment lines summing to 936 | instruction.md:71-76 "Each contains only the active, allowed, or non-deprecated entries, ordered by id, and stays consistent with the count-style scalars"; format only in shipped emitter cli.py:471-478 `lines.append(f"# score={r['score']}")`; test regex `^# score=(\d+)` (:698) | other: format carried only by the shipped code that the agent was asked to repair | step 27 rewrote the emitter ("The PEM manifest sliced raw text producing stray blank lines → replaced with a block parser", step 40); output lines `# anchor anchor-0001 score=18` | keep the shipped `# score=` line | the self-check (step 33-35) parsed its own format, `# anchor (\S+) score=` | HIDDEN RULE (format not stated anywhere a reader of the contract would look) | NEW: "working emitter improved away"; nearest H5 |

The burst fault (`(factor+1)`, cli.py:189) and the session_ttl sign fault (cli.py:175) have the **same** sentence form as pbkdf, and the agent fixed both (steps 21-22). Each had a visible carrier: burst had a second code path in `emit-profile` using the bare factor, and session_ttl had a field name containing "reduction". The agent says this was its decision rule (step 40: "no second code path disagrees, no field-name semantics violated").

## 5. How the tests handle QC
- **TS-13 (one property):** most checks grade one artifact. `rate_limit_burst_is_three_times_rps` (:465) and-chains 3 files, and `session_policy_xml...` (:742) chains 4 children. That is one property per view. stacking_check flagged both as hints, and QC passed them.
- **TS-16 (negatives fire on cheat only):** every negative states "Fires only when ... positively present" (:957, :970, :986, :1004). The unrepaired-cli negative compares a sha against the shipped file, which is narrow.
- **TS-19 (every graded behaviour learnable):** this is RISKY yet it passed.
  - The pbkdf law (:445) and the multiplicative formula appear in no agent-visible file. The visible text gives only the fault class (instruction.md:2-3).
  - The PEM `# score=` format is learnable only from the code being repaired.
  - QC_RULINGS TS-19 :46 has "test stricter than the contract FAIL" (vendor). Here the contract says "faults in derivation arithmetic" and nothing more.
  - INFERRED: QC accepted it because "the shipped code shows the formula and the fault class is named", i.e. delegation to the code.
- **TS-20 (weights):** core value checks 5, artifact shape/count checks 3 or 5, presence and probes 1 (:1022-1051). There are no all-identical weights. Note that "compliance_map total" (5) and "cipher count" (5) are weighted the same as the main config (5).
- **TS-26 (no double payment):** pbkdf is paid 4 times (:388, :410, :419, :445) and burst 4 times (the three whole-doc checks + :465). These are positive cascades. QC_RULINGS :125 says "TS-26 and AL-28 failures ... were all on negatives, never on positive cascades", which is consistent with this passing. stacking_check flagged 2 groups as CHECK BY HAND.
- **IN-15 (rule stated):** the derivation rules are delegated to "the interaction rules each file declares through its own field values" (instruction.md:29-31). PLAYBOOK 01:45 allows delegation, but here the delegated-to files carry values, not rules. RISKY yet passed.
- **IN-16 (one reading):** `base + 2**tier` versus `base * 2**tier` are two defensible readings, and nothing visible settles them. The agent named this ambiguity explicitly (step 40). Per QC_RULINGS IN-16 :19-27 this should be a FAIL ("two readings, nothing settles"), yet it passed. INFERRED: QC read "derivation arithmetic faults" as settling it.
- **AL-28 (negative stacking):** six distinct acts, each with its own observable. stacking_check grouped `forbidden_secret -3 + delivered_cli_unrepaired -5 + hard_coded_derivation_constants -3 + judge R9 -5` as UNMATCHED. By reading the code, they are different acts (output content, zip bytes, source literal, provenance), so it PASSES on acts.
- **CL-4 (one wrong fact costs about one fact):** it does not hold. One wrong scalar costs 17.9 test points (4 checks), and the instruction never says that whole-document exactness counts. It is RISKY yet passed. (Compare 4ee6, which states the cascade in its instruction.)
- **JD-7 (oracle satisfies every criterion):** RISKY yet passed. R1 adds "documents a cryptographic hash check of the extracted contents against the manifest" (judge.toml:14), R2 "per-key provenance comments in each file" (:27, for JSON outputs), and R8 "ships a companion type stub (.pyi)" (:105). `grep -n -i 'pyi\|provenance' solution/solve.py` returns no hits. The oracle cannot satisfy R2 or R8 as written, which is a JD-7 FAIL by the kit. INFERRED: these clauses were added after QC, or QC missed them.

## 6. Leak avoidance
- Wording quotes:
  - "faults in argument routing, key normalization, and derivation arithmetic" (:2-3): class names only, no fault list (W1, W10).
  - "according to the interaction rules each file declares through its own field values" (:29-31): the rule is pushed into data (W2).
  - "Other files in the corpus provide security domain context and are not required to be consumed" (:15-16): a decoy licence that also hides which files matter (W3).
  - "The `sample_config_*.json` files are hints only and must not be copied" (:19): honest control (W7).
- Shipped data does **not** separate the readings for pbkdf. No visible figure shows the right value: the samples carry no pbkdf, `pbkdf_profiles.yaml` is labelled context, and the bounds admit both values. The agent therefore cannot watch the rule fire (W5/W6 satisfied by omission).
- Visible tests or examples: none. The instruction's one example ("the line count of `cipher_priority.txt` equals `active_cipher_count`", :76) is a consistency rule and not a value.
- Naming: test names leak the laws (`..._power_of_two_multiplier_law`, `..._three_times_rps`), but the tests are not visible to the agent.
- The rule sits in the code under repair, far from any prose. The fault is hidden among three same-class faults, and two of those carry contradictions that reward the "fix only contradictions" heuristic.
- LEAK_LIBRARY comparison: our CR-3 / V0 rows leaked because each rule was one explicit sentence (W3). Here there is **no** sentence, so the trap cannot leak through wording. That is beyond our W3 "plain forms": it is an unstated fault. The vendor STATE row (exception in its own sentence) is the opposite design.

## 7. Agent behaviour
- Order:
  - steps 2-4: listing, then reads all contract JSON + samples;
  - step 5: zip listing;
  - step 6: safe extract;
  - steps 7-9: reads the whole cli.py (sees :159 at step 7);
  - steps 10-17: data profiling, including pbkdf_profiles.yaml at step 14;
  - step 13: runs the shipped derive, getting pbkdf 100032 and burst 5956.
- First edits at step 18 (12:02:32, minute 5). Pipeline driver `run_pipeline.py` created at step 30 (12:03:54, minute 6.6). First full run at step 31 (minute 6.7).
- Graded logic changed after the first run? No. Steps 31-39 are runs and checks only. The pbkdf decision was made before the first run and was restated at the end.
- Self-tests: `verify.py` (steps 33-35) checks the format, required keys, all bounds, profile keys and trailers, artifact counts against config, and TOML parse. Step 36 greps for secrets. Step 37 checks rerun byte-determinism. Step 39 checks trailing bytes. None of these can see pbkdf (the bounds pass) or the PEM format (the agent's own regex).
- Where it went wrong:
  1. A conscious heuristic: repair only faults that have a visible contradiction.
  2. It "improved" a working emitter's comment format.
- Final claim vs reality: "Pipeline reconciled and published", with a flagged doubt about pbkdf. That doubt was the actual 20-point loss. The claim about PEM ("replaced with a block parser") was wrong in effect.

## 8. Passed checks (87 points) and why they were easy
- Format and shape (config sort/indent :397, key set/types :369, trailers :428, report transcript :481, digest :519, checksum manifest :815, validation/summary :839): these are stated literally in the instruction (:38-101).
- Count and sum consistency artifacts (cipher, egress, compliance, mfa toml, attestation, xml, env, canary, rate_limits, rotation, audit ini, policy matrix): each filter is one plain instruction sentence ("non-deprecated `internal` or `admin` endpoint, sorted by endpoint", :59-61), and each value comes from a correct config key.
- Burst law (:465): the fault had a second, contradicting code path.
- CLI probes (init/set/validate/bare): the fault classes are named and the probes are generic.
- Negatives: honest work never trips them.

## 9. Take-aways
- ADOPT (RISKY): "repair a fault that has no internal contradiction". Opus explicitly fixes only faults that a second code path or a field name contradicts. One silent fault cost 18 points here. It is risky because of IN-15/IN-16/TS-19: QC can rule it unstated. To be QC-safe, a visible carrier must exist that settles it without contradicting the code, e.g. a data file whose values only fit one form.
- ADOPT (SAFE): invariant-shaped tests ("A is a power-of-two multiple of B", "X = 3*Y across all profiles"). They grade the fix's shape, are cheap, and pass TS-13.
- ADOPT (SAFE): negatives keyed to exact artifacts (a sha of the shipped broken file, an expected literal inside a named function), which are narrow per TS-16.
- ADOPT (RISKY): formats carried only by the shipped code (`# score=` lines). Opus rewrites working emitters it deems ugly. The trap is real, but it is a TS-19 risk because no contract text states the format.
- AVOID: grading one scalar in 4 checks without an instruction sentence that claims whole-document exactness (CL-4). AVOID judge clauses the oracle does not satisfy (.pyi stub, per-key provenance comments in JSON), which is JD-7.
- AVOID relying on fixed literals with no hidden rerun when the lever is a code fault: a hard-coded answer is caught only by the narrow derive-body literal negative.
