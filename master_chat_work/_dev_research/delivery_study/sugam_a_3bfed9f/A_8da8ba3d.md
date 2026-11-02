# A_8da8ba3d: verdict GENUINE

Task root: `Perfect_for_Delivery/Sugam_Agrawal/8da8ba3d-5e8e-5804-9995-d32d520a9e69/`. Run: `trajectories/claude-opus-5/run_1/`.
Scores: overall 61.92, tests 87/112 = 77.68, rubric 12/26 = 46.15.

## Artefact screen
- `result.json`: exception_info null. Agent ran 11:57:16 to 12:08:01Z, about 11 min, 41 steps. No timeout.
- `verifier/test-stdout.txt` prints only the reward. No traceback, no Permission denied.
- Every output file named in the instruction is in `artifacts/app/out/` (22 files including tool.zip). All presence and parse checks PASS.
- `tests/test_output.py:1-13` docstring: the verifier has no `/app/data` mount, so expected values are `EXPECTED_*` constants computed by the reference solution. Every check is guarded so an exception means False. No negative fired.
- Diff of agent `config.json`, `profile_dev.json` and `profile_prod.json` against `EXPECTED_CONFIG/_PROFILE_DEV/_PROFILE_PROD`: one key differs, `pbkdf_iterations` (agent 100032 / 50016 / 200064, expected 3200000 / 1600000 / 6400000). There are no extra keys and no missing keys.
- Conclusion: there is no crash, no path problem and no environment fault. All 25 lost points come from wrong values or a wrong format.

## Failed checks (25 of 112 points)
| check | w | cause | kind |
|---|---|---|---|
| config_matches_expected_derived_values (:388) | 5 | pbkdf_iterations 100032 vs 3200000 | wrong VALUE |
| profile_dev_matches_expected (:410) | 5 | pbkdf 50016 vs 1600000 | wrong VALUE (same root) |
| profile_prod_matches_expected (:419) | 5 | pbkdf 200064 vs 6400000 | wrong VALUE (same root) |
| pbkdf_iterations_obeys_power_of_two_multiplier_law (:445) | 5 | 100032 % 100000 != 0, so the ratio is not a power of two | wrong VALUE (same root) |
| trust_anchor_manifest_pem_blocks (:691) | 5 | test sums `re.findall(r"^# score=(\d+)", ...)`. The agent rewrote the emitter to print `# anchor <id> score=<n>`, so the sum is 0 and not 936 | wrong FORMAT |

## Root causes
1. **pbkdf derivation fault was left unfixed (20 points, 4 checks on one value).** The shipped `cli.py:159` reads `int(defaults["base_pbkdf_iters"]) + (2 ** max_tier)`. TRUTH.md:30-33 says the intended form is `base * 2 ** max_tier` "(the `2 ** max_tier` term only reads as a scale factor, and `env_overrides.json` scales pbkdf multiplicatively)". The instruction only says there are "faults in ... derivation arithmetic" (instruction.md:2-3) and that each file declares its interaction rules "through its own field values" (:29-31). No sentence anywhere gives the multiplicative formula. The agent saw lines 155-159 (steps 7-8), fixed the two other arithmetic faults (step 21 session_ttl sign, step 22 burst factor) and left pbkdf alone. 100032 is inside the bounds [50000, 1e8], so the CLI's own validate step passed.
   The rule is a HIDDEN RULE that has to be inferred from the shape of the formula. It is graded four times on one value, which stacks 20 points on one fact (CL-4 / TS-26 risk). QC passed it.
2. **PEM score comment format (5 points).** The `# score=N` line format exists only in the shipped emitter (`cli.py:471-478`). The instruction (:71-76) gives no comment format. At step 27 the agent "improved" a working emitter. Its self-check at step 33 used its own regex, so the change went unnoticed. The format is implied by shipped code and is never stated.

## Gate check
There is no single gate. The 4 pbkdf checks all fall on one wrong value. That is stacking on one fact, not a gate that zeroes unrelated tests: 87 points of unrelated checks passed.

## Rubric note (does not affect test points)
The judge's R1, R2 and R8 each have an extra unstated clause that the agent was failed on: "documents a cryptographic hash check ... against the manifest" (judge.toml:14), "per-key provenance comments in each file" (:27, for JSON files), and "ships a companion type stub (.pyi)" (:105). The judge's reasoning quotes "the stricter criterion is not fully met". None of these clauses is in instruction.md. These are rubric points lost to hidden judge requirements, which is INFERRED to be a JD-7 / IN-15 risk. R6 (argv recorded as "python3" instead of sys.executable, plus a hard-coded returncode 0) is a genuine judge loss.

Genuine test points lost: 25/112 = 22.3 points of tests score.
