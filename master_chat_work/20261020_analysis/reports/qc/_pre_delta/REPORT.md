# Input_Bundle_QC analysis (Harbor 0.24)

Generated 2026-10-20 (IST) from git HEAD `1096b2447dd408b57094f189846b97041e5110de` (branch `main`). The last commit that touched the QC folder is `e4054885` (2026-10-18 17:34 IST). Read-only analysis. Nothing in the clone was changed.

Path abbreviations used in every citation:
- `QC/` = `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`
- `FC` = `QC/Final_checklist.md`, `ST` = `QC/Starter.md`, `01`..`05` = the gate files (for example `03` = `QC/03_Tests_QC.md`)
- `GEN/` = `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/`, `VB` = `GEN/validate_bundle.py`

Companion files: `qc_checks.json` (307 entries, one per check ID), `caps.json` (53 limits), `authoring_checklist.md`, `fingerprint.json`, `RUN_LOG.md`.

## A. Workflow (Starter.md order)

| Step | What | Tool | Source |
|---|---|---|---|
| 0 | Need the QC folder (11 files) and the bundle path. If the path is missing, ask for it and stop. Read `Final_checklist.md` in full: it is the authority for templates, verdicts, output format and run order | read | ST:39-57, FC:9-10 |
| 1-4 | `structure_qc.py`, `instruction_qc.py`, `tests_qc.py`, `judge_qc.py`, each run with the bundle path. Record every pass/warn/fail line and the exit code (0 pass, 1 fail, 2 usage). Do not stop on a failure. Re-verify every script FAIL by hand | script | ST:59-73, FC:476-486 |
| 5 | Gate 01: judges instruction.md. Also reads task.toml, environment/, test_output.py, judge.toml | manual + script recheck | ST:85-87 |
| 6 | Gate 02: judges environment/ and solution/ (TRUTH.md read last, after DS-21 is decided) | manual | ST:88, ST:105-111, 02:12-18 |
| 7 | Gate 03: judges tests/Dockerfile, test.sh, test_output.py, reward.toml | manual + script recheck | ST:89 |
| 8 | Gate 04: judges tests/judge.toml against solution, tests, instruction and spec | manual + script recheck | ST:90 |
| 9 | Gate 05: whole bundle, cross-layer. CL-1..CL-10 may never be ticked on a reading alone | manual | ST:91-98 |
| 10 | Execution gate (see below) | exe_copy.py + harbor | ST:127-166, FC:652-891 |
| 11 | Fresh-eyes coverage and overlap re-check from disk (instruction, spec file, test_output.py, judge.toml) | manual | ST:168-175, FC:893-935 |

Rules for every gate: read every in-scope file in full, copy the checklist verbatim and mark each item ✅/❌, quote evidence, re-verify each FAIL, write "could not verify" rather than guess, and do not batch IDs (ST:13-37, ST:113-125, FC:937-944).

Step 10 in detail (FC:652-891):
1. Preflight: `harbor --version` (must be 0.24.0 or newer; `uv tool install harbor==0.24.0 --force` is the only install allowed), `docker ps`, `ls "<bundle>"`. If any of them fails, mark Step 10 ⏸️ NOT RUN and quote the error (FC:654-689, FC:832-842).
2. `exe_copy.py "<bundle>" /tmp/step10run` and `... /tmp/stubrun --stub` (FC:706-709). The script refuses (exit 1) when judge.toml does not load under the rewardkit 0.2.1 schema, when tests_qc A1-A4 or W1-W7 fail, or when there is no positive weight. It exits 2 if DEST already exists (QC/exe_copy.py:233-249). On the copy it deletes judge.toml, rewrites reward.toml to `test_output = 1/positive total`, sets all four network roles to `public` and drops their `allowed_hosts`, drops every Dockerfile instruction that mentions openhands, and with `--stub` replaces solution/ with a solve.sh that writes empty artifacts (`{}` for .json) (QC/exe_copy.py:13-33, 157-223, 251-265).
3. Seven runs, each with `-y`: oracle five times (`oracle-1`..`oracle-5`), `nop-1`, and `stub-1`, which is the oracle agent on the stub copy (FC:735-743, FC:749-754).
4. Read each score from `result.json` `verifier_result.rewards.reward` or `verifier/reward.json`. An errored trial (`exception_info` or `exception.txt`) has no score (FC:809-824).
5. Pass bar: all five oracle runs exactly 1.000, reported one by one. nop exactly 0.000. The stub has no fixed number: report the score, which tests paid, and a judgement (FC:792-807, FC:876-888). Scores are TESTS-ONLY and the judged channel is never executed (FC:694-704, ST:144-146).
6. Delete both copies. The original bundle must never be edited (FC:787-790).

Verdict combination: each finding gets fail, minor, warn or pass. The bundle verdict is the worst finding present. ⏸️ NOT RUN never moves the verdict, but it blocks shipping (FC:946-956, ST:182-190). The scripts only emit FAIL, WARN ("tasker approval needed") or PASS (QC/structure_qc.py:1033). MINOR exists only in the model gates.

The final report must contain (ST:177-198, FC:958-1001):
- the verdict line with counts;
- a per-gate summary table with one row per script, one per model gate, one for Step 10, one for Step 11, and the overall verdict;
- findings worst first: ID, one-sentence defect, file:line, quote, Bug/Error or Suggestion/Improvement, and a `Fix:` line on every fail and minor (FC:974-976);
- the consolidated sign-off checklist (FC:1181-1217), where every ❌ has a matching finding.

## B. Every check

The full list is in `qc_checks.json`: 307 entries, each with every source `path:line`, method, script, severity, threshold, files read and `needs_judge_run`. Two extra keys appear where useful: `aliases` and `notes`. Every ID token found anywhere in the 12 files appears in the JSON (coverage checked by script, see RUN_LOG.md).

| Gate | IDs | Count | Script-backed (both) | Manual only |
|---|---|---|---|---|
| 01 | IN-0, IN-S1..S7, IN-F1, IN-L1..L3, IN-1..IN-16 | 28 | 14 | 14 |
| 02 | DS-1..DS-30 | 30 | 10 | 20 |
| 03 | TS-0, TS-S1..S15, TS-1..TS-29 | 45 | 31 | 14 |
| 04 | JD-0, JD-S1..S13, JD-1..JD-18 | 32 | 20 | 12 |
| 05 | AL-F0a..e (= FC F0a..e), CL-1..CL-10 (also in FC), AL-1..AL-28 | 43 | 2 | 41 |
| final | FC-S1..S24, plus 9 synthesized IDs: FC-STEP10-*, FC-STEP11-*, FC-SIGNOFF-WARNS | 33 | 24 | 8 (+1 script) |
| script | structure S1-S10, T1-T15, X1-X3; instruction P1-P3, C1-C6; tests A1-A5, W1-W7, D1, B1-B5, K1-K7, R1-R5, O1, H1, H3-H5; judge J1-J13, G1-G6; H2 (cited, not implemented); EXE-R1..R4 (synthesized) | 96 | - | - |

Which script check backs which gate check, in brief:
- S1-S10 / T1-T15 / X1-X3 → FC-S1..S24, DS-1/5/7/8/13/23/28/29/30
- P1-P3 / C1-C6 → IN-S1..S7
- A/W/D/B/K/R/O/H → TS-S1..S15 and DS-24
- J/G → JD-S1..S12
- R3 → JD-S13

The `notes` field of every script entry names the gate IDs it backs.

`needs_judge_run=true` (15 entries) means local evidence is reading only. Only a real judged run with `OPENAI_API_KEY` can prove these: TS-S10, TS-10, R3, JD-S13 (combined two-channel reward; Step 10 rewrites reward.toml), TS-S11, K7 (the litellm deadlock appears only behind the allowlist, FC:463-469), JD-S2, G2 (judge model and atif-trajectory hand-off), JD-6, JD-7 (no oracle trajectory exists, FC:1211-1213), FC-S12, T12 (allowlist enforcement; Step 10 opens every role), FC-S19, T15 (key wiring), and FC-STEP10-SCOPE.

## C. Hard FAIL list by file

- **Tree**:
  - name regex (S1)
  - missing required file, including solution/TRUTH.md and tests/reward.toml (S2)
  - any extra entry, `cheat/`, `tests/test_weights.json` or `tests/rubric.json` (S3)
  - empty environment/data (S4)
  - reward.txt/json, reward-details.json, ctrf.json, .DS_Store, __pycache__, .git, .pytest_cache (S5)
  - CRLF in a .sh file (S6)
  - em/en dash in any text file (X1)
  - `{{X}}`, `__X__` or `<TAG>` placeholders (X2)
  - a file over 100 MB (X3)

  QC/structure_qc.py:26-69, FC:33-48.
- **instruction.md**:
  - timeout sentence missing or N ≠ `[agent] timeout_sec` (C1/IN-1)
  - names test.sh, test_output.py, judge.toml, reward.toml, rewardkit, solve.sh, solve.py, TRUTH.md, /logs/verifier or reward/CTRF files (C2)
  - says "the grader", "the checker", or describes negative checks, weights or judge prompts (IN-2, manual)
  - the word "reward" (C3)
  - a named /app path that does not exist (C4/IN-5)
  - a declared artifact never pointed at, or two plausible landing places (C5/IN-6)
  - a named tool that is not installed (IN-7)
  - an unreachable graded expectation (IN-8)
  - an answer or algorithm leak (IN-9)
  - fetch, download or URL-as-source wording (IN-11)
  - category, description or keywords untruthful (IN-12)
  - contradictions (IN-13)
  - a recipe in place of a requirement (IN-14)
  - an unstated graded rule (IN-15)
  - an unsettled graded ambiguity (IN-16)
  - banned register, AI-tells, repeated grammar errors (P2, P3, IN-L1..L3)

  01:51-240, 01:320-330, QC/instruction_qc.py:19-32.
- **task.toml**:
  - parse failure; any template key, table or order deviation; extra section; `docker_image` (T1, T2)
  - `environment_mode` ≠ "separate" (T2)
  - schema_version ≠ "1.4" (T3)
  - a non-absolute artifact, `..` or a backslash (T4)
  - description over 100 words or more than one paragraph (T5)
  - empty keywords, category or tags (T6-T8)
  - a non-positive time; junior ≤ expert (T9-T11)
  - network roles not exactly pinned; `allow_internet` (T12)
  - task name ≠ `terminal-bench/<dir>`; version, platforms, null_floor, discrimination_weight or user not pinned; non-positive int sizing; gpus ≠ 0; mcp_servers ≠ [] (T13)
  - author placeholder, single word, lowercase, handle or role, or non-@ethara.ai email (T14)
  - `[verifier.env]` anything but `OPENAI_API_KEY = "${OPENAI_API_KEY:-}"` (T15)

  FC:104-222, QC/structure_qc.py:417-645.
- **environment/Dockerfile**:
  - COPY/ADD of `.`, `..`, solution, tests, TRUTH.md or task.toml (S7/DS-8/DS-23)
  - artifact dir not writable by uid 1000 (S8/DS-28)
  - any missing piece of the openhands-sdk pre-bake or a wrong pin (S9/DS-29)
  - no uid 1000 account with home and `ENV HOME` (S10/DS-30)
  - a needed tool missing (DS-10)
  - a runtime fetch (DS-11/AL-15)
  - secrets or host paths (DS-12)
  - an answer anywhere in the image (DS-26)
  - a piped download other than the exact uv installer (AL-20)

  02:84-170, 02:271-286, 05:339-350.
- **environment/data**: not necessary (DS-2), untrue claims (DS-3), answers or derivable answers (DS-4), template residue or a redacted DRAFT spec (DS-5), a required output literal missing from every visible file (DS-25), a shipped wrong value with no signpost (CL-6), injection text (AL-23). 02:44-80, 02:251-270.
- **solution/**: solve.sh missing (S2/DS-13); pasted answer (DS-14); a test it would fail (DS-15/AL-5); reads tests/ (DS-17); breaks a contract constraint (DS-19/DS-20); copied verifier logic, O1 ≥35% (DS-24/O1); a fallback branch (CL-8). 02:174-224, 05:119-123.
- **TRUTH.md**: missing (S2); describes another mechanism, wrong counts or weights, or dishonest labels (DS-22); reachable by the agent (DS-23); production narration, generator, archetype, seed, tooling or `authored_by` (DS-27). 02:290-337.
- **tests/ (test_output.py, test.sh, tests/Dockerfile)**:
  - unconditional /app/data read (D1/TS-1)
  - missing `COPY . /tests/`, rewardkit pin, or `LITELLM_LOCAL_MODEL_COST_MAP` (K2/K5/K7/TS-2)
  - missing deps or Python < 3.12 (K4/K6/TS-4)
  - test.sh not ending in the exact rewardkit line, writing reward bytes, `exit`/`return`/`||`, SKIP switches, sourcing /app, PATH shadowing (B1-B5/TS-6, 8, 9)
  - fewer than 10 checks (A3)
  - duplicate names, a malformed `@criterion`, braces in a description, a literal non-bool return (A1-A5)
  - registration errors, a weight outside the scale, a broken bijection, identical weights, no positive or no negative, prefix/sign mismatch, negatives outweighing positives (W1-W7)
  - plus TS-5, 7, 11, 12, 14-20, 24-29 (manual)

  03:53-261, 03:428-438.
- **reward.toml**: the shape is not exactly `[[reward]] name/aggregation/weights{test_output, judge}` + `[scoring.test_output]` (R1, R2, R4); a weight ≠ `0.5/positive total` at exact float (R3); any extra criteria-bearing file (R5). QC/tests_qc.py:613-699.
- **judge.toml**:
  - no `[judge]` or no criterion (G1)
  - header ≠ the five pinned keys, or a `reasoning_effort` or other extra key (G2)
  - fewer than 8 criteria, no positive/negative, identical weights, negatives outweighing positives (G3-G6)
  - key set or order wrong, `negate`/`points` (J1)
  - ids not R1..Rn (J2)
  - name duplicate or regex fail (J3)
  - not binary (J4)
  - weight outside the scale (J5)
  - annotations keys or order (J6)
  - enums, kind/category disagreement, residue not one sentence (J7)
  - prefix mismatch (J9)
  - negative-grammar tokens (J10)
  - listed vague words (J11)
  - brackets, placeholders, dashes, tag prefixes (J12)
  - importance pairing (J13)
  - plus JD-5..8, 10, 11, 13-18 (manual)

  QC/judge_qc.py:14-64, 04:494-512.
- **Cross-layer (gate 05)**: every AL-F0*, every CL-*, AL-1..7, 9..16, 18 (unless trivial), 19..28. 05:438-448.

## D. Judgment-only checks (109 entries with method=manual)

Each check below gives what the reviewer looks for, with the source wording in quotes, and how bundles fail it. The fresh-scaffold failures come from reading the two probe bundles (section I); they are predictions, not gate runs.

- **Overlap (JD-8, AL-F0d, FC Step 11.2)**: "name the observable each side reads. Same observable = overlap = fail, regardless of wording" (04:148-150). Typical failure: a judged "writes every requested output artifact... using the deterministic filenames" constraint next to an `artifacts_exist` test, both reading the artifact paths (probe R11).
- **Double payment (TS-26, JD-14)**: "Pair every test against every other test - negative against positive, positive against positive, negative against negative" (03:221-234, 04:197-209). Typical failure: a positive `transform_avoids_network_dependencies_and_shelling_out` paired with `negative_network_dependency_or_shell_cheat` (probe).
- **Absence-grading positives (TS-25)**: "if it passes because something bad is missing... it hands its points to any solver that simply did nothing wrong" (03:211-220). Typical failure: positive `transform_does_not_write_outside_output_dir` (probe).
- **Trigger depth (AL-27)**: for each precedence pair, "find the graded input with both conditions present and the assertion that the earlier one wins" (05:220-232).
- **Truth against the oracle (JD-7)**: "Check EVERY criterion against solve.sh / solve.py line by line" (04:141-147).
- **Negative grammar beyond the token list (JD-2)**: "Never write 'the agent does not ...' with a negative weight... Never turn a bad behaviour into a positive" (04:94-98). The script only bans 5 tokens (QC/judge_qc.py:129-135), so phrasings like "never", "no", "refuses to" or "leaves ... unopened" are left to the reviewer. The probe fmt bundle uses "refusing to introduce third-party packages".
- **Compound criteria (JD-5)**: "unrelated observables joined by 'and'". Probe R3: "handles exact FX monetary conversion, signed values, joins, deterministic sort order, and fixed region/segment aggregates".
- **Code-quality criterion (JD-18)**: required whenever the deliverable is code. Neither probe judge.toml carries one.
- **Conduct two-step (JD-15, AL-1)**: "would every competent route to a correct end state satisfy this criterion?", then "does that approach make a correct end state more likely, or is it just a preference?" (04:256-267).
- **Constraint validity (JD-16)**: quote the sentence and file, one of six kinds, one rule, graded once by the owning layer (04:295-341).
- **Constraints carrying the task (JD-17)**: 04:342-352.
- **Reachability**: IN-8, IN-15, IN-16, DS-21, DS-25, CL-5, CL-10, AL-1, AL-3, AL-4. DS-25 asks for a count: "18 of 24 required keys appear in /app/data/SCHEMA.md, these 6 appear nowhere" (02:266-268). DS-21 defaults to pass: "name the exact piece of information... and show that it appears in no agent-visible file" (02:247-250).
- **Machinery in prose (IN-2)**: "describing the mechanism that checks them (test names, weights, negative checks, judge prompts, reward files) is a fail" (01:66-68). Both probe instructions say "The verifier runs it..." and "The verifier is adversarial: it checks for code that reads the reference corpus..., for behaviour that keys on the input filename...". The script raises only WARN C6.
- **TRUTH.md process narration (DS-27)**: "Generated bundles carry an `authored_by` value emitted by the generator... it comes out" (02:332-335). Both probes carry `authored_by: harbor-generator`, `status: generated_reference`, `archetype:`, `generator_seed:`, and the probe prose mentions "the playground's ablation run".
- **Forgery price (CL-2), partial credit (CL-4), wrong shipped value (CL-6), grading supplying the value (CL-9)**: CL-2 and CL-4 each require a computed number in the sign-off; CL-6 and CL-9 require a quoted file:line (05:41-140, FC:1031-1179).
- **Others**:
  - weight semantics and ordering (TS-20, JD-13)
  - determinism hunt list (TS-11)
  - source-token grading (TS-27)
  - penalty stacking >5 (AL-28)
  - recipe versus constraint (IN-14)
  - metadata truthfulness (IN-12, AL-26)
  - difficulty honesty (AL-8)
  - security audit (AL-19..23)
  - verifier isolation (TS-24, TS-28)

## E. Judge / rubric rules and reward arithmetic

- **Header**: exactly five keys in order: `judge = "openai/gpt-5.6-sol"`, `mode = "individual"`, `timeout = 300`, `atif-trajectory = "/logs/agent/trajectory.json"`, `weight = 1.0`. Then `[scoring] aggregation = "weighted-sum"`. There is no `reasoning_effort`, and the only top-level tables are judge, scoring and criterion (FC:234-243, FC:288-297, QC/judge_qc.py:100-110, 159-184).
- **Criterion keys**: `id, name, description, type, weight` in that order, then `[criterion.annotations]` with `mode, type, evidence, residue, kind, category, evaluation_target, importance`. Constraint criteria add `contract_sentence, contract_file`; conduct criteria add `serves`; outcome criteria add nothing. Order is checked (04:54-74, QC/judge_qc.py:112, 126-127, 195-207).
- **Allowed values**:
  - `type = "binary"`
  - weight ∈ {±1, ±3, ±5}, integer only
  - mode `judged`
  - annotations type ∈ VALUE, EFFECT, ABSENCE, INVARIANT, ORDERING, DIVERGENCE
  - kind ∈ outcome, constraint, conduct
  - category ∈ task completion, instruction following, tool use, agent behavior, factuality and hallucination, safety and boundaries (spelled with "and")
  - evaluation_target ∈ final_answer, user_facing_message, trajectory, state_change
  - importance ∈ critically_important (|w| 3 or 5), important (|w| 1 or 3)
  - kind constraint ⇔ category instruction following

  QC/judge_qc.py:116-125, 225-244, 287-293.
- **Grammar**: start with "The response" for final_answer/user_facing_message and "The agent" for trajectory/state_change. Banned: not, without, fails to, cannot, instead of. No vague words (approximately, around, about, roughly, mostly, typically, often, properly, correctly, clearly, adequately, many, several, few, repeatedly; "some" warns). No brackets, placeholders, dashes or tag prefixes. A negative criterion describes the bad act happening and carries a negative weight (04:94-137, QC/judge_qc.py:129-145, 300-324).
- **Counts**: at least 8 criteria (FAIL), more than 35 is a WARN, at least one positive and one negative, weights not all identical, Σ|neg| ≤ Σpos. There is no minimum number of instruction-following criteria (04:169-176).
- **Reward**: `reward = Σ(test weights that passed) × 0.5/P_t + Σ(judge weights judged yes) × 0.5/P_j`, where P is that channel's positive total. A failed negative adds 0. The result spans 1.0 (all positives, no negatives) through 0.0 (nothing) to -1.0 (worst). rewardkit rounds to 4 decimals and nothing clamps the value (FC:403-429, 03:99-115, 04:84-92). Example: weights `{ test_output = 0.08333333333333333, judge = 0.05 }` for P_t = 6 and P_j = 10 (FC:409). The Step 10 copy uses `test_output = 1/P_t` only (QC/exe_copy.py:145-154).
- **evaluation_target guidance**: judged criteria should watch HOW the agent worked, through trajectory and state_change (JD-9, 04:159-162). Tool-use and ordering rules must be judged, because tests may not read history (TS-12, 03:135-149).

## F. Instruction rules

- **Mandatory**: "You have N seconds to complete this task." with N == `[agent] timeout_sec`. The script accepts commas, e.g. 7,200 (QC/instruction_qc.py:211-227).
- **Length**: the QC sets no length cap; none was found in any of the 12 files. The generator validator fails at 6000 characters or more (VB:439-444).
- **Banned**:
  - em/en dashes anywhere
  - the listed high-register words plus same-kind words (crucial and robust are judged by hand)
  - AI-tells ("it's important to note", "let's dive", "in this task, you will")
  - machinery tokens, "reward", "the grader/checker" prose, `/logs`
  - instructions to write a reward file
  - "benchmark" self-references and GUIDs
  - download, fetch, clone, install or browse wording, or a URL as a source
  - recipes
  - leaked constants or algorithms

  01:32-47, 01:51-240, QC/instruction_qc.py:62-83.
- **Allowed and not required**: describing WHAT is judged; pointing to a spec file in place of restating it; staying silent about inputs and the network; layout of any kind; "kindly" and "please note"; the online-lookup sentence, which has no check at all (01:30, 01:61-68, 01:72-87, 01:136-151, FC:1225-1228).
- **Must disclose**: one inferable landing place per declared artifact (IN-6); every graded rule of engagement (IN-15); every graded literal or tolerance, which may live in a shipped spec (IN-8, TS-18, DS-25).
- **Must not disclose**: TRUTH.md (IN-2, DS-23); test names, weights, negative checks (IN-2).
- **Metadata**:
  - description: non-empty, one paragraph, at most 100 words (T5)
  - category: truthful about the dominant work; no fixed vocabulary (T7, IN-12, AL-26)
  - keywords and tags: at least one each, related to the subject (T6, T8)
  - author: `name` in "Ram Lakhan" form (at least two capitalised words, hyphen and apostrophe forms allowed, no placeholder words), `email` ending in `@ethara.ai` and built from the name, otherwise WARN (FC:209-217, FC:572-593, QC/structure_qc.py:113-128, 336-405)
  - no difficulty key (FC:220)
  - expert < junior (T10)

## G. Caps and limits

All 53 are in `caps.json` with sources. The headline ones:

| Limit | Severity | Source |
|---|---|---|
| test checks ≥10 / >35 | FAIL / WARN | QC/tests_qc.py:273-276 |
| judge criteria ≥8 / >35 | FAIL / WARN | QC/judge_qc.py:368-371 |
| weights ∈ {±1, ±3, ±5}, ≥1 pos & ≥1 neg, not identical, Σ\|neg\| ≤ Σpos (both channels) | FAIL | tests_qc.py:144, 377-401; judge_qc.py:113, 375-394 |
| importance ↔ \|w\| | FAIL | judge_qc.py:290-293 |
| description ≤100 words, 1 paragraph | FAIL | structure_qc.py:600-603 |
| keywords/tags/authors ≥1 | FAIL | structure_qc.py:371, 604-607 |
| author email built from name | WARN | structure_qc.py:399-402 |
| bundle name 3-64 chars | FAIL | structure_qc.py:108 |
| file ≤100 MB | FAIL | structure_qc.py:960-982 |
| O1 overlap ≥35% / ≥20% / <30 lines | FAIL / WARN / WARN | tests_qc.py:742-749 |
| rewardkit ==0.2.1, Python ≥3.12, openhands-sdk/tools 1.55.1, litellm 1.105.0, harbor ≥0.24.0 | FAIL (harbor: Step 10 precondition) | tests_qc.py:145, 587; structure_qc.py:834; FC:663 |
| judge timeout 300, weight 1.0 | FAIL | judge_qc.py:103, 107 |
| reward weights 0.5/P exact float | FAIL | tests_qc.py:681-685 |
| oracle 5 × 1.000, nop 0.000 | FAIL | FC:794-807 |
| penalty stack per action >5 | FAIL | 05:239-242 |
| instruction length | none in QC; VB <6000 chars | VB:444 |

Ayush ignores the >35 count WARNs on purpose. Both are WARN only (03:441, 04:518).

## H. Cross-reference with validate_bundle.py

**Coverage**: `validate_bundle.py` runs all four live QC scripts from the sibling `Input_Bundle_QC/`: structure (§3.3), instruction (§3.4), judge (§7.5) and tests (§7.6) (VB:1225, 1236-1264, 1310-1311, 1345-1346). Any QC FAIL is therefore a validator FAIL. A QC WARN becomes INFO and does not block (VB:1258-1261). The validator covers no model-gate check (01-05 manual items, CL-*, Step 10, Step 11), with two partial exceptions:
- §6.3 static solvability audit of solve.py: seeds, verifier paths, opaque constants (VB:912-1012), a partial DS-21/CL-10;
- §15.x TRUTH.md structure (VB:1015-1222), a partial DS-22.

**Stricter than QC, so not a conflict**:

| Rule | VB |
|---|---|
| data/ must be flat (QC allows subdirs) | VB:316 |
| CRLF fails in any file (QC warns outside .sh) | VB:415-428 |
| TODO/FIXME/XXX/PLACEHOLDER fail, zip interiors too (QC X2 warns) | VB:36-39, 330-405 |
| instruction under 6000 chars, an absolute path in backticks | VB:439-453 |
| single FROM digest-pinned to public.ecr.aws | VB:29-32, 503-510 |
| one apt RUN with xxd, file, curl, bash, nodejs, npm, procps, ca-certificates | VB:513-538 |
| `WORKDIR /app` and the exact line `RUN mkdir -p /app && chown 1000:1000 /app` | VB:541-557 |
| the only COPY is `COPY data /app/data` and it is the last line | VB:560-572 |
| at least 6 inputs and 6 artifacts | VB:791-824 |
| `negative_hardcoded_sample_answers` required for every archetype | VB:671-674 |
| format-recovery only: solve.py required, seeds/`_write_corpus`/`__main__` in test_output.py, recommended cheat negatives | VB:1288, 1326-1384 |
| TRUTH.md at least 4000 chars, H1 title, 8 sections in order, focal/drift/trap labels with at least 2 focal, provenance keys, digests match, positive total and negatives named | VB:1015-1222 |

**Conflicts**:
1. `authored_by` and `status` are REQUIRED non-empty TRUTH.md provenance keys in the validator (VB:1025-1034, 1145-1155). QC DS-27 fails `authored_by` and any tooling attribution (02:329-337). A bundle cannot satisfy both: keep the key to pass VB and it fails DS-27; drop it and VB §15.5 fails.
2. The online-lookup sentence is REQUIRED by VB §2.5 (VB:464-471). QC says NO check of any kind (01:136-137, FC:1225-1228). This is harmless, because keeping the sentence passes both.
3. VB §1.6a treats a valid `cheat/` overlay as OK (VB:277-306). QC S3 fails any `cheat/` (QC/structure_qc.py:236-238). Net effect: VB still fails through §3.3 running structure_qc.
4. `--semantic` cats `/logs/verifier/reward.txt` (VB:1559-1564, 1581-1586), but rewardkit writes `reward.json` and test.sh writes no reward (FC:81-86, 03:75-82). It also runs the full judge.toml with no key, which by design is a verifier error (03:86-91). Read only, not run: `--semantic` cannot succeed on a QC-conformant bundle (UNVERIFIED by execution).
5. `c_2_seconds` accepts any "seconds" word (VB:456-461), while QC C1 requires N == timeout. This is weaker, but QC C1 also runs through §3.4.

## I. Run evidence (SCRATCH, throwaway bundles)

Commands and exit codes are in RUN_LOG.md. The generator was run from a SCRATCH copy with `IBG_MEMORY=off` and `PYTHONDONTWRITEBYTECODE=1`, seed `20261020`, with `--author "Ram Lakhan <ram.lakhan@ethara.ai>"`. Without `--author` the generator refuses: "ERROR: --author is required: QC FC-S18 fails an empty [task].authors" (exit 2).

| Bundle | archetype | structure_qc | instruction_qc | tests_qc | judge_qc | validate_bundle | exe_copy / --stub |
|---|---|---|---|---|---|---|---|
| qc-probe-bundle | data-pipeline (auto) | exit 0: 17 pass, 0 warn, 0 fail | exit 0: 5 pass, 1 warn (C6), 0 fail | exit 0: 35 pass, 0 warn, 0 fail (17 checks, P=51, N=16, O1 2%) | exit 0: 19 pass, 0 warn, 0 fail (11 criteria) | exit 0: 40 passed, GATE PASS | 0 / 0 (1/51) |
| qc-probe-fmt | format-recovery | exit 0: 17/0/0 | exit 0: 5/1 (C6)/0 | exit 0: 35/0/0 (29 checks, P=72, N=23) | exit 0: 19/0/0 (12 criteria, P=34, N=10) | exit 0: 49 passed, GATE PASS | 0 / 0 (1/72) |

What a fresh scaffold fails before any authoring: no script FAILs, and the only script output to clear is WARN C6. The failures sit in the manual gates. By reading the probe bundles (no model gate was run), these are the likely FAILs:
1. **DS-27**: TRUTH.md provenance carries `authored_by: harbor-generator`, `status: generated_reference`, `archetype: ...` and `generator_seed: ...`, and the prose mentions "generator seed" and "the playground's ablation run". Every generated bundle fails this, and VB conflict 1 means it cannot simply be deleted without failing VB §15.5.
2. **IN-2 / IN-S5**: the instructions describe the verifier ("The verifier runs it against freshly generated data..."; fmt: "The verifier is adversarial: it checks for code that reads the reference corpus..., for behaviour that keys on the input filename..."). The second names the negative checks.
3. **TS-25 / TS-26**: positive absence tests (`transform_avoids_network_dependencies_and_shelling_out`, `transform_does_not_write_outside_output_dir`), the first also paired with `negative_network_dependency_or_shell_cheat`. Also TS-20: `artifacts_exist` carries weight 3, where existence checks are 1.
4. **JD-5 / JD-8 / JD-16.4 / JD-18**: a compound outcome criterion (R3); a constraint criterion (R11) on artifact filenames that a test already reads; no code-quality criterion.
5. **CL-2 / CL-4 / Step 10**: these always need computed numbers and real harbor runs, so a fresh bundle cannot pass sign-off without them.

Step 10 harbor runs were not executed (see Not checked).

## J. Change tracking

The folder has 39 commits since 2026-08-10. The last 15 span 2026-09-08 to 2026-10-18; 8 of them landed between 2026-10-16 and 2026-10-18, often several a day. Authors: Sugam Agrawal (14), Shreeyank Doliya (1).

| Commit (IST) | Change | IDs / files |
|---|---|---|
| e4054885 10-18 17:34 | exe_copy strips the openhands pre-bake in Step 10 copies | exe_copy.py, FC, ST |
| 601b708a 10-18 15:09 | pins openhands-sdk/tools 1.55.1 and litellm 1.105.0; adds uid 1000 account check; allows the uv installer; drops reasoning_effort from [judge] | S9/DS-29/FC-S23, S10/DS-30/FC-S24, AL-20, G2 |
| cc468ae7 10-18 13:14 | requires the pre-baked openhands runtime (then unpinned); groups S8 output | S9/DS-29/FC-S23, S8 |
| 263361e0 10-18 11:34 | exe_copy opens [agent] network; adds uid 1000 artifact-dir check | S8/DS-28/FC-S22 |
| 8e26af41 10-18 01:56 | adds exe_copy.py; pins atif-trajectory; adds K7; brace-free descriptions | K7, A4, G2, Step 10 |
| bdba990e 10-17 01:07 | fails placeholder/blank author names and non-ethara.ai emails | T14/FC-S18 |
| 344a9e8d 10-16 22:21 | requires First Last author name; warns on email/name mismatch | T14/FC-S18 |
| 3e8feaca 10-16 22:11 | moves the test channel to rewardkit with reward.toml, signed integer weights, exact tree (rewrite of all 11 files) | A/W/B/K/R, J/G, S2/S3, TS-*, JD-* |
| c98b243e 10-14 11:01 | pins judge model to openai/gpt-5.6-sol | G2 |
| ffbb8940 10-13 15:37 | task.toml delivery schema; cross-file consistency | T2-T15, FC-S6..S21 |
| 90e67846 10-13 12:48 | rubric.json → judge.toml (04_Rubric_QC.md and rubric_qc.py deleted) | gate 04, judge_qc |
| 0b411a46 09-30 15:05 | corrects 1.1 deprecation; requires `-y`; documents the no-network host limit | Step 10 |
| 2ac9f2c1 09-30 13:34 | schema 1.4; adds client feedback checks | CL-1..CL-10, T3, T12 |
| b21fb851 09-15 13:46 | TRUTH.md moves to solution/ | S2, S7, DS-22/23 |
| 92295542 09-08 12:50 | audit fixes (AL-7 severity, Step 10 run count, etc.) | FC, 02, 03, 05 |

Patterns to watch:
- **IDs are renumbered, not stable.** At 92295542, DS-28 was "TRUTH.md describes the task" (today DS-27), DS-26 was "output shape" (today DS-25), and TS-26/27/28/29 meant what TS-25/26/27/28 mean today. Never key a prompt to an ID alone; key it to the ID plus its title, and re-read the live file.
- **Pins move.** Model, harbor, rewardkit and openhands versions all changed within 10 days.
- **One check is spread across files.** A new check usually lands in a script, a gate .md and FC together, as S9/DS-29/FC-S23 did.
- **Diffing a new QC version**: compare `fingerprint.json` hashes, then run `git log <old>..HEAD -- Input_Bundle_QC`, and diff the `Every ID` docstrings of the scripts and the checklist blocks of each gate.

## K. QC-safe authoring checklist

See `authoring_checklist.md` (the same content, ready to paste).

## Disagreements between QC sources

1. **H2**: 03:304-306 says "H1 and H2 ... fire only when the scripts call a tool the image never installs", but tests_qc.py implements only H1, H3-H5 (QC/tests_qc.py:37-39, 90-93, 754-797).
2. **JD-S13**: 04:448-452 says "the script recomputes the value", but judge_qc.py never reads reward.toml; tests_qc.py R3 does (QC/tests_qc.py:613-687).
3. **"some"**: judge_qc WARNs (QC/judge_qc.py:315-316), while 04:513-514 and 04:437-438 call it MINOR.
4. **Timeout with commas**: 01:256-258 says a comma-formatted number "reads as missing to the script", but the regex `[\d,]+` accepts it (QC/instruction_qc.py:211-215).
5. **Dashes in code**: IN-S1 says "anywhere in the file, prose or code" (01:245), but instruction_qc P1 scans code-stripped prose only (QC/instruction_qc.py:145-166). structure_qc X1 does cover the whole file (QC/structure_qc.py:987-989).
6. **Severity-guide gaps in 02**: DS-28, DS-29 and DS-30 say "fail" in their text (02:115, 02:152, 02:167), but the 02 severity guide omits them (02:381-390). The same applies to DS-1, DS-7 and DS-13, which are script FAILs.
7. **Severity-guide gaps in 05**: AL-6, AL-16 and AL-17 have no severity in the 05 guide (05:438-451). AL-18's text says "fail" (05:371-372), while the guide gives MINOR for a single stale number (05:449).
8. **AL-8**: the text says "If the claim is implausible, fail" (05:260), the guide says "warn: AL-8 borderline" (05:451), and the checklist mentions "any declared difficulty band" (05:414-415) although "There is no `difficulty` key" (05:261, FC:220).
9. **O1 small file**: tests_qc warns whenever solve.py has fewer than 30 substantive lines, and passes when there is no solve.py (QC/tests_qc.py:731-743). 02 DS-24 and 03 TS-S13 mention only 35% and 20% (02:209-210, 03:369-370).
10. **Fresh session or not**: FC says "Use a fresh session (no carried context) for each numbered gate" (FC:477-478), while Starter says "Run the gates sequentially yourself with fresh eyes" in one session (ST:100-103).
11. **S10 position**: FC-S24 and DS-30 say the account goes "right after `FROM`" (FC:549-552, 02:160), but S10 does not check position (QC/structure_qc.py:885-910).
12. **Work markers**: X2 WARNs on TODO/FIXME/XXX/PLACEHOLDER (QC/structure_qc.py:990-993), while FC-S14 says a marker that is not the task's own "is template residue and a fail" (FC:640-645). This is consistent (the script points, the reviewer rules), but the severities differ.
13. **C6 versus IN-2**: the script WARNs on grader/checker/verifier (QC/instruction_qc.py:237-239), but IN-2 fails "the grader" and "the checker" (01:56).
14. **IN-S6 'reward'**: the script FAILs (QC/instruction_qc.py:235-236), but the doc says a domain-legitimate use is a tasker-override case (01:271-273).
15. **T14 message**: the example says `email = "ada.lovelace@company.ai"` (QC/structure_qc.py:378-379), contradicting the @ethara.ai rule. Cosmetic.
16. **exe_copy fallback schema**: it allows `reasoning_effort`, `negate`, `points` and `optional` (QC/exe_copy.py:57-65), all of which judge_qc fails (QC/judge_qc.py:258-261, 169-170). This is only a refusal pre-check, so it is consistent in effect.
17. **validate_bundle versus QC**: see section H, conflicts 1-5.

## Not checked

- **Step 10 harbor runs** (oracle ×5, nop, stub) were not executed on the probe bundles. The probes are throwaway scaffolds and the brief asked for script output only. Docker image builds are long-running. Scores are therefore UNVERIFIED.
- **No model gate (01-05) or Step 11 was run.** The manual-gate predictions in section I come from my reading of the probe files.
- **exe_copy schema check**: `rewardkit` is not installed on the host (`ModuleNotFoundError`), so exe_copy validated judge.toml with its built-in fallback key sets, not `rewardkit.models` (QC/exe_copy.py:84-112).
- **`validate_bundle.py --semantic`** was not run, so conflict H.4 rests on reading alone.
- **No judged-channel behaviour was executed** (no OPENAI_API_KEY): model reachability, atif-trajectory hand-off, the K7 deadlock and the combined reward.
- **Harbor internals** cited by FC (artifact_handler.py, verifier.py skip_tests_upload, rewardkit 0.2.1 behaviour) were not read. They are UNVERIFIED here.
- **Severities the guides do not state** (AL-6, AL-16, AL-17, DS-6, DS-16) are recorded in `qc_checks.json` as inferred and marked in `notes`.
