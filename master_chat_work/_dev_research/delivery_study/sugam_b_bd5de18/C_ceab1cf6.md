# C card: ceab1cf6 (envelope-config CLI repair)

Paths: T = `tests/test_output.py`, I = `instruction.md`, D = `environment/data/`, OC = `D/output_contract.md`, R = `trajectories/claude-opus-5/run_1/`, AG = the agent's `cli.py` inside `R/artifacts/app/out/tool.zip`. Test version matches the graded run (weights 0.5/76). There is no data drift.

## 1 Scores and verdict
- Recorded 65.47 overall, 50.0 tests (38/76), 80.95 rubric (offline judge: 15 criteria, #1 and #14 failed). Harness judge score 17.
- Verdict **GENUINE**: 36 points are wrong values and 2 points are format gates that are stricter than the contract.

## 2 Inventory
- Domain: media-encoding budget configuration. Archetype: debugging. Repair a broken CLI shipped as `tool.zip` in place, against a decoy-dense rule corpus, and generalise to held-back corpora.
- Files the agent sees: 62 files in D. Rule files use odd extensions (`.edn2`, `.xml2`, `.kv3`, `.tsv4`, `.html2`, `.properties2`, `.b64`…), about 3-15 KB each. Most rows are decoys (DEPRECATED, PHANTOM, ARCHIVED, INACTIVE) with one CANONICAL row per band. Also `defaults.json`, `env_overrides.json` (dev/prod deltas), `sample_config_dev/prod.json` (`"note": "context only - do not copy"`), OC 7440 B (shapes only; OC:5 "Every value is derived from the rule files under /app/data following the task brief"), and `tool.zip` (README.md, cli.py).
- Instruction: 5556 B, 761 words, 5 paragraphs. 23 artifacts are named.
- Tests: 39 checks, positive 76, negatives -11 (-5 hardcoded T:1504, -3 nested/dynamic T:1515, -3 network T:1524; registrations T:1582-1584). Weights: 6 hidden-corpus checks ×5, 3 shipped profile/config checks ×5 (config, dev, prod), delta report ×3, key_set ×3, and 26 checks ×1.
- Judge: 15 criteria, batched, positive 21, negative -16. Conduct: R1 runs shipped tool before edit 1, R2 reads source 1, R7 runs validator 3. Names-the-defect criteria R3-R6 at 3 each. Code quality R14 3, R15 1. Negatives R8 -1, R9 -1, R10 -5, R11 -1, R12 -3, R13 -5.
- Reward split: test 0.5/76, judge 0.5/21.

## 3 Test architecture
- **Expected-value production:** shipped answers are HARDCODED constants (T:103 "# Independently derived answers for the shipped corpus."; EXPECTED_MAIN T:104-134, EXPECTED_PROFILES T:135-148, EXPECTED_AUDIT T:149-163). There are 3 held corpora c1/c2/c3, each with a hardcoded base and expected config and profiles (T:165-312). There is no embedded reference function; the values come from the author's oracle (G9 rests on the comment "Independently derived").
- **Hidden corpora** are built from an embedded lzma/b85 tar (`CORPUS_B85`) by `_write_corpus` T:891. It applies `_reorder` T:879, which moves decoy rows ahead of canonical rows and so defeats first-row reads, and swaps `base_config`. `_held_run` T:911 extracts the agent's `out/tool.zip` (`_extract_tool` T:793: path and symlink guards, chmod 644) and runs `cli.py` as nobody (`_run` T:851: python -I, PYTHONHASHSEED 0, TASK_CTL_DATA, 60 s, own process group). `_grant_read` T:826 widens read access on 0600 editor files.
- **Hidden share:** 30/76 = 39% (six held checks ×5), so G3 is met. The remaining 61% are shipped-only checks against hardcoded constants.
- **Isolated vs whole-doc:** each artifact is checked whole with type-strict `_same` T:761. Held checks are split into derive (config) and profiles per corpus (`_held_config_ok` T:940, `_held_profiles_ok` T:946 needs both dev and prod).
- **Partial credit:** none inside checks. The instruction does not state whole-document exactness. It says only "follow it exactly for every artifact you emit" about shapes (I:5).
- **Mutation tests:** `tool_clamps_average_to_band_ceiling` T:1461 tightens a band ceiling below the pre-clamp average. Plus the 3 held corpora, each a targeted mutation per TRUTH.md:36 (c1 band 2 scale order, c2 width 1745→1746, c3 min interval 503 vs ceil 504).
- **Anti-cheat:** the hardcoded-marker negative greps the tool text for `str(EXPECTED_MAIN[max_bitrate_kbps])` and similar (T:1509). Held corpora with swapped base and reordered decoys make shipped-number copying fail.
- **Weight shares:** `stacking_check.py` reports 39 checks, positive 76. It flags many 1-point checks with `and`-chained comparisons (summary 0/6, convergence 0/4, selection_trace 0/3, validation_report 0/3, chain 0/3), which are TS-13 hints. Reading the code confirms they are single-artifact checks with several field equalities.
- **Key functions:** `_replay_transcript` T:1038-1081 (replays `_REPLAYED` = init/set/validate T:1027, and requires the replay to rebuild config.json byte for byte T:1076-1077). Delta report T:1169, ladder T:1228 and T:1262, provenance T:1364-1378.

## 4 Lever table (failed checks)
| id | w | rule graded | rule locations (quote) | sentence form | agent's reading | correct reading | why self-test missed | fully stated? | nearest |
|---|---|---|---|---|---|---|---|---|---|
| profile_dev, profile_prod, profile_delta_report, held profiles c1/c2/c3, bitrate_ladder, ladder_solution, ladder_ordering | 5+5+3+15+1+1+1 = 31 | the profile scale multiplies the **pre-clamp** average, then clamp, then quantise | I:5 "applying each profile's average-scale, priority, cycle-span, and reserve deltas in the documented order, which applies the scale before granularity"; I:3 main average "clamped to the band's allocation floor and ceiling and quantized to the documented granularity"; D/avg_formula.edn2:2 `(formula avg_pre …)`; no data file documents the profile order (grep for pre-clamp/scale/before/avg_pre: only avg_formula); TRUTH.md:11 defect 5 | implied by a word: "the scale before granularity" leaves *which* average open, and "documented order" points to no document | AG `solve_profile` :491-530, :503 `round_half_even(config["avg_bitrate_kbps"] * …, 1000)`, which scales the finished main average and then clamps and quantises. Final message step #44: "scale→clamp→granularity order". The agent believes it complied | scale `avg_pre` (dev 1425 / prod 2725 vs agent 1400 / 2700) | the synthetic corpora at t+8.9-9.1 (`genalt.py`) only checked that runs succeed and differ, with no independent expected value. The shipped samples are "do not copy" context, so the agent did not compare them (INFERRED) | NO. Both readings satisfy I:5 literally: **HIDDEN RULE** (IN-16 shape) | H5-like: kept the shipped bug's structure (shipped `cmd_profile` :94-102 scales the finished avg). NEW: "repair keeps the defect's operand" |
| held_c2 derive | 5 | odd width +1 after width rounding | D/width_even.html2:107 `<rule step="after-width-rounding" when="width % 2 == 1" apply="width + 1" status="CANONICAL"/>` | data rule element (attribute form) among decoy rows | AG :372 `quantize_nearest(width_pre, 2)` (half-even nearest, 1745→1744); `band_width_even` :149-157 reads only `<w>` rows. Step #11 read the file with `head -c 1800`, and line 107 lies beyond it (INFERRED) | 1746 | shipped band 0 width is already even (TRUTH:19), so a hidden-only separating case (W5) | YES, in data | L10 (general rule in a rarely joined field) |
| report_matches_contract | 1 | the init/set/validate replay rebuilds config.json byte for byte | T:1038-1081; OC:54-57 requires only that the transcript "includes the init, set, validate, and export-report subcommands, and every returncode is 0" | other: test stricter than contract | init on a work seed file, config built by derive | — | — | NOT stated (TS-19 "test stricter than contract") | gate |
| derivation_provenance | 1 | source child carries the file name as text | T:1373 `child.text`; OC:157-158 "source children name the data file each field was read from" | other: silent format | wrote it as the attribute `file="…"` | text content | — | NOT stated (silent format) | gate |

## 5 How the tests handle QC
- **TS-13:** 1-point artifact checks bundle 3-6 field equalities (stacking hints above), so this is MINOR (vendor v1:69 ruling). Profile checks are one artifact each.
- **TS-16:** negatives have narrow triggers. Hardcoded markers are 2 specific shipped numbers (T:1509), plus nested/dynamic code (T:1515) and network (T:1524).
- **TS-19:** held corpora stay inside "any other rule corpus laid out exactly like `/app/data`" (I:3), so they are learnable. Two checks are stricter than OC (transcript replay, provenance text). This is the shape of the TS-19 FAIL rulings ("test stricter than contract", "silent value type"), yet QC passed it, probably because each is 1 point. Shipped-only checks make up 61%, which is far above the "<=5%" note for shipped-only checks in QC_RULINGS. QC passed it anyway.
- **TS-20:** 5 core (held corpora, config, profiles), 3 sub-goal (key set, delta report), 1 minor artifacts. Matches 03_Tests_QC.md:51.
- **TS-26:** held derive and held profiles are separate checks for one corpus, and the shipped profile checks repeat the same fact class. The profile lever was paid 9 times (31 points), which is double-payment risk. QC passed it as "different corpora".
- **IN-15:** the negatives map to I:3 "never from the shipped numbers" and I:9 "Use only the Python standard library".
- **IN-16:** the profile scale operand has two readings (above). It was RISKY but passed.
- **AL-28:** writing config outside the tool is -5 in the judge (R10) only. Hardcoding is -5 in tests only. Each act sits in one layer.
- **CL-4:** the profile lever cascades into 9 checks. There is no exactness statement in I, but there is no single whole-doc check that zeroes many facts either. The cascade comes from repetition across corpora (G1 coupling).
- **JD-7:** R3-R6 ask the agent to *name* specific defects, a method-restating shape (J8 risk). R14/R15 are code quality and must be met by the oracle (INFERRED met).

## 6 Leak avoidance
| quote | W |
|---|---|
| I:1 "Those files are densely populated and carry decoy rows" | W1: says *that* decoys exist, never which rows |
| D/sample_config_dev.json:3 `"note": "context only - do not copy"` | W7: the visible control is fenced off from use as an answer |
| D/dev_avg_scale.properties2:1 "# dev avg scale context (authoritative deltas live in env_overrides.json)" | W2: the rule lives in a governing file, not beside use |
| D/width_even.html2:107 the rule as an attribute row, deep in a decoy-dense file | W3/W8: an odd visible carrier |
| I:5 "in the documented order, which applies the scale before granularity" | W3: a bare property, but this one under-specifies (the hidden-rule risk) |
- Shipped data does not separate the readings for either lever: band 0 width is already even, and the profile operand is checkable only against hardcoded test constants, never visible. So both separating cases are hidden-only (W5).
- No visible tests. The shipped `tool.zip` README is the only example.
- Naming: odd file extensions and status-labelled decoys. Held corpora reorder decoys ahead of canonical rows (T:879).
- LEAK_LIBRARY comparison: avoids "rule next to use" (RUN) because the deltas are pointed to another file. It also avoids "names reflexes" (SALV): the instruction does not list the 11 defects, though judge R3-R6 do.

## 7 Agent behaviour
- Read order: OC t+0.2, then defaults/env_overrides/samples, README, cli.py, then data files by `head`/`grep` at t+0.4-4.9 (partial reads of large files).
- At t+8.4 it deleted the shipped cli.py and wrote a fresh one (a single full program). This is inside "repair in place" by archive name, and judge R1/R2 passed.
- Graded logic was not changed after the first program (t+8.5 derive, t+8.6 profiles 1400/2700).
- Self-tests: 7 synthetic corpora (run-and-differ only), determinism, an archive rebuild. There was no independent expected value.
- Where it went wrong: the profile operand (carried over from the shipped bug's structure) and the width rule beyond its partial read.
- Final claim at t+12.4: "11 faults fixed", "deriving correct distinct ladders each time". It overclaims generality, and held c2 and all held profiles fail.

## 8 Passed checks
- Shipped config and held c1/c3 derive (15 points) passed, as did clamp-to-ceiling, the key set and most 1-point artifacts. The decoy filtering (status=CANONICAL per band) is easy for Opus because the status column is explicit and the instruction names the decoy classes (I:3).
- Determinism, convergence and archive checks passed. Opus routinely checks for determinism.

## 9 Take-aways
- SAFE: put rule rows in decoy-dense files and have hidden corpora reorder decoys ahead of canonical rows. This beats first-row reads without wording leaks.
- SAFE: a data rule element whose shipped instance is a no-op, with the separating case only in a held corpus (31% of the misses came from one such element).
- RISKY: a one-word ordering property ("scale before granularity") that leaves the operand open. This is the costliest lever (31 points), but it has two readings, so it is IN-16 exposure.
- RISKY: paying one lever across 9 checks (shipped + 3 held + 3 ladder views), which is TS-26/CL-4 exposure.
- AVOID: 1-point checks stricter than the output contract (transcript replay, provenance text form), which are the TS-19 FAIL shape.
- AVOID: grading 61% on hardcoded shipped constants. Keep held/hidden at 30% or more (met here at 39%) and say how the constants were derived.
