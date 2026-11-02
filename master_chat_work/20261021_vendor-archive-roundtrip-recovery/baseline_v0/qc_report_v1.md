# QC report: vendor-archive-roundtrip-recovery

- Bundle: vendor-archive-roundtrip-recovery
- Bundle path: /Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/vendor-archive-roundtrip-recovery
- Report version: v1
- Date and time: 2026-10-21 20:47 IST (2026-10-21 15:17 UTC)
- QC kit commit: bde868c46994f4916e245b40d14f302b1341244a (Terminal_2.0_Harbor_Harness/Input_Bundle_QC, live)
- Harbor version: 0.24.0
- Session title: vendor-archive-roundtrip-recovery_v1_qc (update applied to ses_ea0f9f9e7ffeLpOMD684LbMvvw; session list shows it, listed second by update time after the parent master chat)

- Report completed: 2026-10-21 23:45 IST (18:15 UTC)

Verdict: ❌ FAIL (26 fails, 10 minors, 4 warns)

| Step | Gate | Verdict | Fails | Minors | Warns |
|------|------|---------|-------|--------|-------|
| 1 | structure_qc.py (exit 0) | ✅ pass | 0 | 0 | 0 |
| 2 | instruction_qc.py (exit 0) | ✅ pass | 0 | 0 | 0 |
| 3 | tests_qc.py (exit 0) | ⚠️ warn | 0 | 0 | 1 |
| 4 | judge_qc.py (exit 0) | ✅ pass | 0 | 0 | 0 |
| 5 | Gate 01 Instruction | 🟡 minor | 0 | 2 | 0 |
| 6 | Gate 02 Data & Solution | ❌ fail | 2 | 2 | 0 |
| 7 | Gate 03 Tests | ❌ fail | 6 | 3 | 1 |
| 8 | Gate 04 Judge | ❌ fail | 2 | 1 | 2 |
| 9 | Gate 05 Alignment & Integrity | ❌ fail | 12 | 2 | 0 |
| 10 | Execution gate (tests-only) | ❌ fail | 1 | 0 | 0 |
| 11 | Coverage & overlap re-check | ❌ fail | 3 | 0 | 0 |
| | Overall | ❌ FAIL | 26 | 10 | 4 |

Step 10 ran in full: oracle 0.1241 x5, nop 0.0, stub 0.0207 (tests-only). The script warns structure_qc X1 (two .varc files skipped as binary) and tests_qc A5 x4 were re-verified as false positives and carry no count. tests_qc A3 (48 checks > 35) is the one script warn. Several findings in different gates share one root cause and are counted in each gate that owns them: the setpriv permission defect (TS-24 = AL-5 = Step 10 oracle), the judge/test overlap (JD-8 = F0d = Step 11 overlap) and the untriggered rules (TS-14 basic_reset = AL-27 = AL-2 = Step 11 coverage).

## Findings

### ❌ Fails

1. ❌ Gate 03 TS-24 / TS-19: every check that runs agent code fails for every submission, the oracle included, because the runner drops to `nobody` over root-owned inputs. tests/test_output.py L806-807 `return ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups", *base, *extra]`; L833 `tempfile.NamedTemporaryFile(...)` (0600), L870/L889 `tempfile.mkdtemp()` (0700); probe `PermissionError: [Errno 13] Permission denied: '/tmp/tmpo_yy1fj0.varc'`. Bug/Error. Fix: in tests/test_output.py chmod each temp segment/manifest/doc to 0o644 and each mkdtemp() dir to 0o777 (or chown to nobody) before running the agent program.
2. ❌ Step 10 oracle: all five oracle runs read 0.1241 (18/145), not 1.000; the 33 checks that execute decode.py/encode.py fail (list in Step 10). Bug/Error. Fix: apply finding 1, then re-run the whole Step 10.
3. ❌ Gate 05 AL-5: the oracle cannot pass the shipped tests (same cause, oracle-1..5 reward.json `"reward": 0.1241`). Bug/Error. Fix: as finding 1.
4. ❌ Gate 05 AL-7: solution/TRUTH.md L74-75 "The oracle scores 1.0 on the test channel, measured locally with the real checks" is false for the shipped verifier (0.1241). Bug/Error. Fix: keep that sentence in TRUTH.md only once a fixed bundle reads 1.000 on all five Step 10 oracle runs.
5. ❌ Gate 05 F0c / CL-2 / CL-3: reciting the spec in the final reply earns about half the reward with no codec. R1-R9 (33/36 judged points) are facts copied from format_contract.md L45-46, L56, L65, L101-103, L110-112, L121-124, L148-156, revision_notes.md L12-15, escape_rules.md L10-11; forgery price 0.0414 (tests, 12/145) + 0.4583 (judge) = 0.4997. va5_magic_over_version and report_roundtrip pay a forgery while claiming to grade content. Bug/Error. Fix: in tests/judge.toml shrink R1-R9 to at most a third of the judged positive total or replace them with trajectory criteria; in tests/test_output.py make va5_magic_over_version also require the clean base segment to decode to a document, and make report_roundtrip recompute the digests itself.
6. ❌ Gate 05 CL-1: report_roundtrip (L1517-1526) only reads the agent's own hashes in roundtrip_report.json; it never runs encode.py on the examples. Bug/Error. Fix: in report_roundtrip run `_encode(workspace, row["decoded"])` per decoded_examples.jsonl row and compare its sha256 with `rebuilt_sha256` and with sha256 of the row's hex.
7. ❌ Gate 04 JD-8: R1, R2, R5 and R6 restate facts already graded in report files (report_format `crc_covers_offsets`/`sync_byte`/`mode_ids`, L1170-1172; report_error_analysis `precedence`, L1510-1511). Bug/Error. Fix: in tests/judge.toml replace R1, R2, R5, R6 with trajectory/process criteria and update weights.judge in tests/reward.toml.
8. ❌ Gate 05 F0d: same overlap seen cross-layer. Bug/Error. Fix: as finding 7.
9. ❌ Step 11 Overlap: same four pairs. Bug/Error. Fix: as finding 7.
10. ❌ Gate 04 JD-13: R3, R5 and R7 (weight 5, critically_important) pay for one summary sentence each while the codec-quality criterion R10 gets 3; R1-R9 hold 0.458 of total reward. Bug/Error. Fix: in tests/judge.toml lower R3, R5, R7 to weight 1 or 3 with importance "important".
11. ❌ Gate 02 DS-24: solve.py's codec restates the verifier's reference codec with renamed identifiers, including unstated quirks (solve.py L168-170 vs test_output.py L361-363 len<16 `record_count_overflow`; `malformed_frame` L292 vs L405; uvarint >63 / sleb128 >70 limits; same salvage probe copy L339-350 vs L449-463). Bug/Error. Fix: rewrite solution/solve.py's decoder, encoder and salvage independently from the contract files.
12. ❌ Gate 02 DS-22: solution/TRUTH.md L62-63 "42 positive checks ... 6 negative checks" vs test_output.py L1653-1700: 43 positives (145) and 5 negatives (23). Bug/Error. Fix: change TRUTH.md L62-63 to "43 positive checks" and "5 negative checks".
13. ❌ Gate 03 TS-19 / Gate 05 AL-3: encode.py is graded on documents that are not decode documents: `_r_raw/_r_delta/_r_dict` (L757-783) omit `field`, `unit`, `canonical_id` and set `"value": None` on delta/dict records, against decoder_appendix.md L20-21 "reads one decode document" and L38-49 (26 points: va2_*, va4_modified_shortest, compA_ext, compA_all). Bug/Error. Fix: build each encode fixture by decoding a real segment with `decode_segment(..., SCHEMA)` and editing the one changed field with `value` kept consistent.
14. ❌ Gate 05 AL-3: same shape mismatch, counted cross-layer. Bug/Error. Fix: as finding 13.
15. ❌ Gate 03 TS-19 / Gate 05 CL-5 / AL-1: test_output.py L1541 `row["name"][:3] in ("cap", "rej", "eva", "sam", "fie")` bans names the contract allows (decoder_appendix.md L79-80 "starts with `cap`, `rej`, `eval`, `sample` or `field`"). Bug/Error. Fix: use `row["name"].startswith(("cap", "rej", "eval", "sample", "field"))`.
16. ❌ Gate 05 CL-5: same rule counted under the client check. Bug/Error. Fix: as finding 15.
17. ❌ Gate 03 TS-16 / TS-14: negative_reads_training_corpus_at_runtime (L1597-1605, -5) greps source for "/app/data", so a comment costs 5 while a split-string runtime read passes; the oracle strips its own docstring (solve.py L419-422) to escape it. Bug/Error. Fix: delete the check and its registration (L1596-1605, L1698).
18. ❌ Gate 03 TS-26: negative_filename_dependent_behaviour (L1584-1593, -5) and negative_nondeterministic_output (L1638-1650, -3) both read repeated-decode identity of one payload under random temp names. Bug/Error. Fix: delete negative_filename_dependent_behaviour (L1584-1593, L1697).
19. ❌ Gate 05 AL-28: penalties stack: determinism -5 + -3 = 8 in tests; catalog hardcoding fires negative_hardcoded_sample_answers (-5) and judge R12 (-3). Bug/Error. Fix: drop negative_filename_dependent_behaviour, and retarget R12 in tests/judge.toml at a different act (for example copying catalog tallies into format_report.json) or drop it.
20. ❌ Gate 03 TS-14: basic_reset (L1254, fixture L933 `[_r_raw(20, 5, ...), _r_reset(), _r_raw(21, 6, ...)]`) claims "clears state" but no post-reset record depends on state. Bug/Error. Fix: change the fixture at L933 to `[_r_raw(20, 5, wide=True), _r_reset(), _r_delta(21, 4), _r_raw(22, 6, wide=True), _r_dict(23, 0)]`.
21. ❌ Gate 05 AL-27: untriggered rules: reset clearing state, reserved offset 15 (format_contract.md L150-151), the `rec_count * 5` bound (L153-154, only 65535 used), trailer_crc_mismatch `expected`/`found` (L155-156, never compared). Bug/Error. Fix: add fixtures for a post-reset delta, byte 15 = 1 alone, rec_count = avail // 5 + 1, and a crc-only fault compared against the full error object.
22. ❌ Gate 05 AL-2: the same four promises have no checker. Bug/Error. Fix: as finding 21.
23. ❌ Step 11 Coverage (requirements): the same four rules are unchecked. Bug/Error. Fix: as finding 21.
24. ❌ Step 11 Coverage (tests): negative_rebinds_verifier_dependencies (L1608-1635, -5) punishes assigning `open`/`zlib.crc32`/`struct.unpack` in the agent's own program, which no contract sentence forbids and which cannot affect a subprocess-isolated verifier. Bug/Error. Fix: delete it and its registration (L1608-1635, L1699).
25. ❌ Gate 05 CL-10 / AL-4: how a long key that names no canonical field decodes (field = key text, unit/canonical_id null) lives only in test_output.py L234-241 and solve.py L157-158; capture_alpha.varc ships such a key ("temp_0003"; field_layouts.csv row 3 is current_0003); graded via report_decoded_examples (L1544). Bug/Error. Fix: add that rule to format_contract.md "Field names", or regenerate capture_alpha.varc with canonical names.
26. ❌ Gate 05 AL-18: solution/TRUTH.md L63-64 and test_output.py L4-5 describe a hidden corpus rebuilt "from a seed"; `EVAL_SEED`/`CHALLENGE_SEED` (L747-748) are never used and the hidden cases are hand-built fixtures (L927-1114). Bug/Error. Fix: reword both to "hand-built hidden fixtures" and delete L746-748.

### 🟡 Minors

1. 🟡 Gate 01 IN-L2: dropped hyphens, instruction.md L1 "long lived", L7 "in band", L13 "re encoded", "non shortest". Suggestion/Improvement. Fix: write "long-lived", "in-band", "re-encoded", "non-shortest".
2. 🟡 Gate 01 IN-L2: instruction.md L9 "do not put any capture answers you were not given into them" has no clear referent. Suggestion/Improvement. Fix: replace with "the reports cover the shipped catalog and the examples you build yourself, and nothing else."
3. 🟡 Gate 02 DS-6: capture_alpha.varc long key "temp_0003" names no field in field_layouts.csv, against format_contract.md L72-73. Bug/Error. Fix: regenerate it with canonical names (tests/test_output.py build_alpha_beta L719) or state the unknown-long-key rule.
4. 🟡 Gate 02 DS-6: escape_rules.md L11-13 "An escape byte as the last thing in the window pairs with the byte before the window ends" is self-contradictory. Suggestion/Improvement. Fix: "An escape byte that is the last byte of the window has no partner inside it; the frame is damaged."
5. 🟡 Gate 03 TS-13: compA_value L1467, compA_len L1478, heavy_salvage_recovers L1414-1415, report_error_analysis L1510-1513 each assert two or more properties. Suggestion/Improvement. Fix: split compA_value and compA_len into value/length and field-name checks.
6. 🟡 Gate 03 TS-17: plain `==` at L1372, L1501, L1544 lets 1 pass for true despite appendix L4-5 fixing value types. Suggestion/Improvement. Fix: use `_docs_equal(...)` there.
7. 🟡 Gate 03 TS-15: negative_reads_training_corpus_at_runtime and negative_rebinds_verifier_dependencies lack the inversion comment (L1603, L1633). Suggestion/Improvement. Fix: add "# cheat present -> True; negative weight punishes" on those return lines.
8. 🟡 Gate 04 JD-5: R10 judges decode.py and encode.py in one verdict. Suggestion/Improvement. Fix: split R10 per program.
9. 🟡 Gate 05 AL-17: 49 agent subprocesses x 60 s (`_run` L811) = 2940 s worst case > task.toml L22 `timeout_sec = 2700.0`. Bug/Error. Fix: lower `_run`'s timeout to 20 s or raise [verifier] timeout_sec to 3600.
10. 🟡 Gate 05 F0a: generator tooling in the verifier (`__main__` blocks L680-698, L1716-1720, `_write_corpus` L1703-1713), unused seed constants, and an unused `width` column in field_layouts.csv. Suggestion/Improvement. Fix: delete the tooling from tests/test_output.py and drop or document the `width` column.

### ⚠️ Warns

1. ⚠️ tests_qc A3 / Gate 03 TS-23: 48 checks, above the 35 cap (L1653-1700). Suggestion/Improvement.
2. ⚠️ Gate 03 TS-16: negative_rebinds_verifier_dependencies (-5) guards an attack a subprocess cannot mount (also Step 11 fail 24). Suggestion/Improvement.
3. ⚠️ Gate 04 JD-11: R11 is the template's generic /tests negative; neither path exists in the separate-mode agent container. Suggestion/Improvement.
4. ⚠️ Gate 04 JD-9: nine of twelve criteria recite spec facts; little process signal. Suggestion/Improvement.

## Consolidated sign-off

- ✅ structure_qc.py exits 0
- ✅ FC-S1..FC-S24 structure_qc.py output read, and every failure it reports confirmed in the file and carried into the report (no failures; X1 warn verified false positive)
- ✅ instruction_qc.py exits 0
- ✅ tests_qc.py exits 0
- ✅ judge_qc.py exits 0
- ✅ Gate 01 Instruction: no fail findings (2 minors)
- ❌ Gate 02 Data & Solution: no fail findings (DS-24, DS-22)
- ❌ Gate 03 Tests: no fail findings (6 fails, findings 1, 13, 15, 17, 18, 20)
- ❌ Gate 04 Judge criteria: no fail findings (JD-8, JD-13)
- ❌ Gate 05 Alignment & Integrity: no fail findings, F0a-F0e all clean (F0a 🟡, F0c ❌, F0d ❌, plus CL/AL fails)
- ✅ CL-1..CL-10 client feedback checks all run, each one carrying the number it asks for or the file and line it asks for (never a bare ✅) (CL-2 0.0828 test channel / 0.4997 total; CL-4 0.8759 for one fact wrong; others quote file and line; fails CL-1, CL-2, CL-3, CL-5, CL-10)
- ✅ Step 10 preflight run and pasted (harbor version 0.24.0 or newer, with the exact number recorded; docker reachable; bundle path listed), or the failing preflight command named with its exact error (harbor 0.24.0)
- ❌ Step 10 oracle run executed for real FIVE times: all five exactly 1.000, every number reported individually (evidence pasted) (0.1241, 0.1241, 0.1241, 0.1241, 0.1241)
- ✅ Step 10 nop run executed for real: reward exactly 0.000 (evidence pasted) (0.0)
- ✅ Step 10 stub run executed for real: score reported, tests that paid named, judgement given with reasons (evidence pasted) (0.0207 = 3/145, three parse checks at weight 1; healthy)
- ✅ Step 10 runs made from `exe_copy.py` copies only: its full output pasted (judge.toml validated against the rewardkit 0.2.1 schema, judge.toml deleted, tests-only reward.toml weight, network roles opened), scores recorded as TESTS-ONLY, both copies deleted, and the original confirmed unedited (network opened and OpenHands pre-bake dropped in the copies only; no OpenAI key; judge.toml validated, not executed)
- ✅ Every oracle or empty-run score claimed anywhere in the bundle (TRUTH.md included) is scoped to the test channel; no judged-channel oracle score is claimed, because none can exist (TRUTH.md L74-75 says "on the test channel"; its value is false, carried as AL-7)
- ❌ Step 11: re-check done, coverage mapping complete both directions, zero overlap between tests and judged criteria (Step 11 findings 9, 23, 24)
- ❌ All warn findings shown to the tasker and approved (4 warns listed above, awaiting tasker approval)
- ✅ Sign-off recorded: reviewer name, date, bundle name, verdict (Sisyphus, QC session vendor-archive-roundtrip-recovery_v1_qc; 2026-10-21 IST; vendor-archive-roundtrip-recovery; ❌ FAIL)


# Evidence appendix

## Step 0: preconditions

```
$ git -C ".../Terminal_2.0_Harbor_Harness" rev-parse HEAD
bde868c46994f4916e245b40d14f302b1341244a
$ diff -rq <original> <copy>
(no output, exit 0)
```

## Steps 1-4: scripts

### structure_qc.py

```
structure_qc: vendor-archive-roundtrip-recovery
============================================================
pass [S1] bundle name format
pass [S2] all required files present
pass [S4] input directories data/ (12 files) all copied into the image
pass [S7] agent image copies nothing from outside environment/
pass [T1] task.toml parses
pass [T2] template shape, key order, environment_mode = separate
pass [T4] artifacts (absolute container paths): ['/app/decode.py', '/app/encode.py', '/app/out/decoded_examples.jsonl', '/app/out/format_report.json', '/app/out/roundtrip_report.json', '/app/out/error_analysis.json']
pass [T14] [task] authors: 1 entry, valid shape
pass [T7] [metadata] category: 'Data Processing' (no fixed vocabulary; whether it describes the dominant work is judged by reading)
pass [T12] network_mode pinned per role
pass [T13] pinned values exact
pass [T15] [verifier.env] judge wiring exact
pass [S8] every artifact directory is writable by uid 1000
pass [S9] openhands-sdk runtime pre-baked at /opt/openhands-sdk-venv
pass [S10] uid 1000 agent account with HOME created
pass [X1] no em/en dashes in text files
pass [X3] no file over 100 MB
WARN [X1] 2 file(s) skipped as binary, re-check any that are text: environment/data/capture_alpha.varc, environment/data/capture_beta.varc
============================================================
SUMMARY: 17 pass, 1 warn, 0 fail
VERDICT: WARN - tasker approval needed
structure_qc exit=0
```

### instruction_qc.py

```
instruction_qc: vendor-archive-roundtrip-recovery
============================================================
pass [C1] timeout sentence matches agent timeout (7200s)
pass [C2] no scripted machinery names
pass [C3] no 'reward'
pass [C4] every /app path resolvable through COPY/ADD exists
pass [C5] every declared artifact referenced
============================================================
SUMMARY: 5 pass, 0 warn, 0 fail
VERDICT: PASS
instruction_qc exit=0
```

### tests_qc.py

```
tests_qc: vendor-archive-roundtrip-recovery
============================================================
pass [A1] test_output.py parses and imports criteria, criterion from rewardkit
pass [A2] no duplicate function names
pass [A4] every check is a top-level @criterion(description=...) function of workspace
pass [W1] 48 module-level registrations
pass [W2] every weight is an integer on the locked scale
pass [W3] bijection checks <-> registrations
pass [W4] weights differentiate
pass [W5] 5 negative check(s)
pass [W6] negative_ prefix matches weight sign
pass [W7] positive total 145, negative total 23
pass [D1] no unconditional reads of the agent input paths ['/app/data'] under tests/
pass [B1] rewardkit runs once, as the last line
pass [B2] no skip switches
pass [B3] no sourcing or PATH shadowing
pass [B4] test.sh writes no reward itself (read the whole script)
pass [B5] no exit, return or || paths
pass [K1] FROM present
pass [K2] COPY . /tests/ present
pass [K3] mkdir -p /app present
pass [K4] third-party imports installed (none beyond stdlib)
pass [K5] harbor-rewardkit==0.2.1 pinned
pass [K7] LITELLM_LOCAL_MODEL_COST_MAP=True set
pass [K6] verifier base Python 3.12 or newer (or not a python:X.Y image)
pass [R5] no criteria-bearing input beyond test_output.py and judge.toml
pass [R1] reward.toml parses with reward and scoring tables only
pass [R3] channel weights equal 0.5 / positive total
pass [R2] [[reward]] shape pinned
pass [R4] [scoring.test_output] aggregation = "weighted-sum"
pass [O1] oracle independent of the verifier (15% of solve.py's 435 substantive lines also appear in test_output.py)
pass [H1] util-linux installed for setpriv
pass [H3] /tests restricted from unprivileged readers
pass [H4] stale reward files cleared before grading
pass [H5] verifier log directory owned by root and not writable by others
WARN [A3] 48 checks; cap is 35 (warn)
WARN [A5] check decoded_examples_present (line 1221) reads agent output with no try/except; confirm bad output returns False instead of raising
WARN [A5] check report_decoded_examples (line 1530) reads agent output with no try/except; confirm bad output returns False instead of raising
WARN [A5] check negative_reads_training_corpus_at_runtime (line 1597) reads agent output with no try/except; confirm bad output returns False instead of raising
WARN [A5] check negative_rebinds_verifier_dependencies (line 1609) reads agent output with no try/except; confirm bad output returns False instead of raising
============================================================
SUMMARY: 33 pass, 5 warn, 0 fail
VERDICT: WARN - tasker approval needed
tests_qc exit=0
```

### judge_qc.py

```
judge_qc: vendor-archive-roundtrip-recovery
============================================================
pass [G1] judge.toml parses (12 criteria)
pass [G2] pinned [judge] and [scoring] header exact
pass [J1] all criteria
pass [J2] all criteria
pass [J3] all criteria
pass [J4] all criteria
pass [J5] all criteria
pass [J6] all criteria
pass [J7] all criteria
pass [J8] all criteria
pass [J9] all criteria
pass [J10] all criteria
pass [J11] all criteria
pass [J12] all criteria
pass [J13] all criteria
pass [G3] 12 criteria
pass [G4] 2 negative criteria
pass [G5] weights differentiate
pass [G6] positive total 36, negative total 8
============================================================
SUMMARY: 19 pass, 0 warn, 0 fail
VERDICT: PASS
judge_qc exit=0
```

### Script re-verification notes

- structure_qc WARN [X1] (varc files skipped as binary): re-checked with `xxd`; both `capture_alpha.varc` (56 bytes) and `capture_beta.varc` (57 bytes) are genuine binary VARC1 segments (`5641 5243 3102 0103 ...`, frame bytes `aa0c 0974 656d 705f...`), not text. Verified false positive; no dash or placeholder can hide in them.
- tests_qc WARN [A3] 48 checks over the 35 cap: confirmed, 48 `criteria.<name>(weight=...)` registrations at lines 1653-1700. Carried as a warn (gate 03).
- tests_qc WARN [A5] x4: re-read each body. `decoded_examples_present` (L1221) and `report_decoded_examples` (L1530) wrap their reads in `fn()` passed to `_holds`, which catches `Exception` (L1183-1187). `negative_reads_training_corpus_at_runtime` (L1597) and `negative_rebinds_verifier_dependencies` (L1609) also return `_holds(fn)`. All four return False on bad or missing output instead of raising. Verified false positives.

## Step 5: Gate 01 Instruction QC

Files read in full: instruction.md (15 lines), task.toml, environment/Dockerfile, every file under environment/data (tables and catalog analysed in full by script, prose files read line by line), tests/test_output.py (1720 lines, all), tests/judge.toml (165 lines, all).

Findings (gate 01):

- 🟡 IN-L2 Hyphens are dropped from compound words throughout the prompt, which reads as spelling slips. instruction.md L1 "long lived telemetry archives", L7 "a segment with in band damage", L13 "when a record is re encoded", L13 "a non shortest integer". Suggestion/Improvement. Fix: in instruction.md write "long-lived", "in-band", "re-encoded" and "non-shortest" (hyphen-minus is allowed; only em/en dashes are banned).
- 🟡 IN-L2 One sentence is hard to parse. instruction.md L9 "The reports describe the shipped catalog and examples you build yourself; do not put any capture answers you were not given into them." The agent is given no capture answers, so "answers you were not given" has no clear referent. Suggestion/Improvement. Fix: replace the clause in instruction.md L9 with "the reports cover the shipped catalog and the examples you build yourself, and nothing else."

Checklist:

- ✅ IN-0 instruction_qc.py run, exit code and findings reported (exit 0, "SUMMARY: 5 pass, 0 warn, 0 fail")
- ✅ IN-S1..IN-S7 instruction_qc.py output read, and every failure it reports confirmed in the file and carried into the report (no failures reported)
- ✅ IN-F1 no em/en dashes anywhere in the file (read all 15 lines; script X1 pass; only hyphen-minus in "`--stream`", "`--salvage`")
- ✅ IN-L1 register is everyday natural English, no banned or same-kind vocabulary ("normative description" in L3 is a technical term of art for a spec, not inflated register; no "crucial"/"robust")
- ❌ IN-L2 grammar and spelling clean (dropped hyphens L1, L7, L13; awkward clause L9; see Findings, 🟡)
- ✅ IN-L3 no AI-tell phrases; reads like a human colleague wrote it (opens "A data engineering team is migrating long lived telemetry archives...")
- ✅ IN-1 timeout sentence present and N == agent timeout_sec (L15 "You have 7200 seconds to complete this task."; task.toml L35 `timeout_sec = 7200.0`)
- ✅ IN-2 no mention of tests/, solution/, grader, logs, reward (stating WHAT is judged is fine) (L11 "Both programs will be run in a clean Python 3.12 ... against captures you have not seen" states the acceptance surface, not the machinery)
- ✅ IN-3 no instruction to write reward/log files
- ✅ IN-4 no benchmark self-references or GUIDs (L11 "VARC1 is invented for this task" names no benchmark)
- ✅ IN-5 no finding for unmentioned inputs; any path the prompt does name exists (all 12 `/app/data/...` paths in L3 exist in environment/data, which `COPY data /app/data` lands; script C4 pass)
- ✅ IN-6 exactly one landing place inferable for each declared artifact, both ways (L7 `/app/decode.py`, L8 `/app/encode.py`, L9 the four `/app/out/...` paths, exactly the six in task.toml L2; nothing undeclared is asked for)
- ✅ IN-7 no tool named that the image does not install (only `python3` / "Python 3.12" is named; image is `python:3.12-slim`)
- ✅ IN-8 everything the tests assert AND everything an outcome judged criterion demands is knowable from prompt, shipped spec or data (conduct criteria are exempt, see JD-15) (decode shape in decoder_appendix.md L23-55, error objects in format_contract.md L148-156, salvage shape in appendix L57-69, report keys in appendix L71-140, judged facts R1-R9 all in format_contract.md/escape_rules.md/revision_notes.md. One test is stricter than the contract on example names (`row["name"][:3] in ("cap", "rej", "eva", "sam", "fie")` vs appendix L79-80 "No `name` starts with `cap`, `rej`, `eval`, `sample` or `field`"): that defect is in test_output.py and is reported under gate 03 TS / gate 05 CL-5, not against the prompt)
- ✅ IN-9 no answer or algorithm leak (withholding is fine; gate 02 DS-21 rules on anything you suspect is unreachable) (the prompt points at the spec and lists the topics of the final account, L13, without giving any value)
- ✅ IN-10 online-lookup sentence: no check performed (tasker decision)
- ✅ IN-11 network wording matches the pinned offline contract (no fetch/download/ URL-as-source sentences; silence about the network is correct) (L11 "there is nothing about it to find anywhere else"; no fetch verbs)
- ✅ IN-12 category names the dominant work; description honest; keywords/tags related (category "Data Processing": the work is recovering a retired archive format and decoding/re-encoding its captures, a data-migration codec job; description task.toml L7 matches the instruction point for point; keywords/tags "python", "binary-format", "decoder", "encoder", "stdlib" all on-subject)
- ✅ IN-13 no internal contradictions, constraints jointly satisfiable ("cannot import helper modules you leave beside them" L11 agrees with baking tables into each program; exit 0 on rejection agrees across L7 and appendix L11-12)
- ✅ IN-14 describes the end state and any rules of engagement, never a recipe that is the solution (L5-11 describe deliverables and constraints; the method is left to the spec files)
- ✅ IN-15 every graded rule of engagement is stated plainly enough to act on (judge.toml has no `type = "instruction following"` criterion; the test-side rules are "cannot read anything under `/app/data` while they run" and "Keep both programs deterministic", both L11, both actionable. That `negative_reads_training_corpus_at_runtime` greps source text rather than runtime reads is a test defect, reported in gate 03)
- ✅ IN-16 nothing graded has two defensible readings the contract fails to settle (both readings written out, or no finding) (examined: raw width on re-encode. Reading A keep the document's `wide` bit; reading B write a changed raw value narrow when it fits, or at the `width` in field_layouts.csv, following format_contract.md L167-168 "written in the canonical shortest form for that field". va2_modified_bytes and compA_ext grade reading A (field 20 has width 2 in field_layouts.csv yet `_r_raw(20, 999, wide=True)` must encode 4 bytes). The contract settles it: the encoder receives only the document, cannot tell a changed raw value from an unchanged one, and L164-166 require byte-exact reproduction of unmodified segments, so only reading A satisfies both sentences. No finding; the unused `width` column is raised as residue under gate 05 F0a)


## Step 6: Gate 02 Data, Environment & Solution QC

Files read in full: environment/Dockerfile, every prose and JSON file under environment/data, revision_map.ini (structure and sections), field_layouts.csv and symbol_table.tsv (head, tail and full-file parity), capture_alpha.varc and capture_beta.varc (xxd), capture_catalog.jsonl (3.2 MB, 17,700 lines: full-file parity and full decode by script, head read by eye), solution/solve.sh, solution/solve.py (588 lines), then solution/TRUTH.md last. Also read: instruction.md, task.toml, tests/test_output.py, tests/judge.toml.

Data parity, run in a scratch dir from the generator half of tests/test_output.py (L1-728, executed without rewardkit), compared byte for byte with the shipped files:

```
catalog lines 17700 equal_to_shipped True
field_layouts equal True
symbol_table equal True
revision_map equal True sections ['revision_4', 'revision_5', 'revision_6', 'revision_7']
alpha equal True beta equal True
ok 15200 errors {'reserved_not_zero': 461, 'unsupported_version': 495, 'trailer_crc_mismatch': 510, 'record_count_overflow': 532, 'bad_magic': 502} modes {'delta': 15216, 'dict': 7867, 'raw': 15694} unknown_longkeys_in_catalog 0
wide raw records fitting int16: 135
alpha record 0: {"raw_key": null, "long_key": true, "mode": "raw", "wide": true, ..., "key_str": "temp_0003", ..., "field": "temp_0003", "unit": null, "canonical_id": null}
```

DS-21 decided before opening TRUTH.md: solvable. Every graded fact traces to an agent-visible file: header layout and CRC coverage (format_contract.md L25-48, crc_profiles.json), framing and modes (format_contract.md L50-97), escaping and salvage (escape_rules.md), remap (revision_notes.md + revision_map.ini), names/units/aliases (field_layouts.csv, symbol_table.tsv), rejection order and error objects (format_contract.md L142-160), all output shapes (decoder_appendix.md). The hidden fixtures (fx_eval_basic, fx_va1..fx_va6, fx_heavy, fx_compA) only combine these stated rules. TRUTH.md, read afterwards, agrees ("the contract ... is complete").

Findings (gate 02):

- ❌ DS-24 The oracle's codec restates the verifier's reference codec with renamed identifiers, so its 1.000 cannot disagree with the grader. Identical quirks the contract never states appear in both: solve.py L168-170 `if len(data) < HDR: rc = struct.unpack_from("<H", data, 11)[0] if len(data) >= 13 else -1; return {"error": "record_count_overflow", "record_count": rc}` vs test_output.py L361-363 `if len(buf) < HEADER_SIZE: rc = struct.unpack_from("<H", buf, 11)[0] if len(buf) >= 13 else -1; return {"error": "record_count_overflow", "record_count": rc}`; the unstated `{"error": "malformed_frame", "detail": ...}` (solve.py L292, test_output.py L405); the same check order and guards in the frame parser (solve.py L197-231 vs test_output.py L250-286, e.g. `if sel >> 5:` both, `back < 0 or back >= len(...)` solve.py L253 vs L321); the same uvarint `> 63` and sleb128 `> 70` limits (solve.py L64/L104 vs L64/L113); the same salvage probe-state copy (solve.py L339-350 vs L449-463); the same unknown-long-key fallback (field = key text, solve.py L157-158 vs L235-241). tests_qc O1 reports 15% shared lines only because of renaming. The graded logic (decode, encode, salvage) is the shared part. Bug/Error. Fix: rewrite solution/solve.py's decoder, encoder and salvage path from the contract files alone (without the verifier's quirks such as the len<16 record_count_overflow branch), so Step 10 agreement is between two independent implementations.
- ❌ DS-22 TRUTH.md's Verification section misstates the test channel's composition. solution/TRUTH.md L62-63 "carries 42 positive checks with a positive weight total of 145 and 6 negative checks with a combined weight of -23"; tests/test_output.py L1653-1700 register 43 positive checks (total 145) and 5 negative checks (5+5+5+5+3 = 23), and TRUTH.md L69-71 itself names five negatives. Bug/Error. Fix: in solution/TRUTH.md L62-63 change "42 positive checks" to "43 positive checks" and "6 negative checks" to "5 negative checks".
- 🟡 DS-6 The shipped example stream uses a long key that names no canonical field, which contradicts the contract's own definition, and no rule covers that case. capture_alpha.varc bytes `aa0c 0974 656d 705f 3030 3033` = long key "temp_0003"; field_layouts.csv row 3 is `3,current_0003,percent,2` and no row is named temp_0003; format_contract.md L72-73 "A long key is an unsigned LEB128 length followed by that many UTF-8 bytes, which spell a canonical field name directly". Only graded indirectly (report_decoded_examples compares a self-built example's decode with the reference, which outputs field = key text, unit and canonical_id null). solve.py's own example uses another non-canonical key, `"key_str": "temp_0001"` (L461). Bug/Error, low blast radius. Fix: either regenerate capture_alpha.varc in tests/test_output.py build_alpha_beta (L719) with canonical names (for example "current_0003"), or add one sentence to format_contract.md "Field names" stating that a long key matching no `name` decodes with `field` = the key text and `unit` and `canonical_id` null.
- 🟡 DS-6 One escaping sentence in the spec reads as self-contradictory. environment/data/escape_rules.md L11-13 "An escape byte as the last thing in the window pairs with the byte before the window ends, never with a byte outside it." An escape byte that is last in the window has no following byte inside the window. Both the oracle (solve.py L126-127 "escape at window edge") and the verifier (L138-139) treat it as a damaged frame. Not graded by any fixture. Suggestion/Improvement. Fix: in escape_rules.md L11-13 write "An escape byte that is the last byte of the window has no partner inside the window; the frame is damaged, and the byte after the window is never consumed."

Checklist:

- ✅ DS-1 input in one or more named directories under environment/, each non-empty and COPYed; environment/ holds only the Dockerfile and those directories (environment/ = Dockerfile + data/ with 12 files; Dockerfile L26 `COPY data /app/data`; script S4 pass)
- ✅ DS-2 data necessary: task unsolvable without it (field names need field_layouts.csv/symbol_table.tsv/revision_map.ini, which hold 2100 generated names, 2100 aliases and 1020 remap lines; format_report tallies need capture_catalog.jsonl; the codec rules exist only in the .md files)
- ✅ DS-3 every referenced file present, every claim about the data true (all 12 files named in instruction.md L3 exist; catalog has the five stated keys, lowercase hex, 2500 header-damaged lines; alpha/beta are seq 0/1 of stream 3 with flags 1/0; schema_registry `"canonical_field_count": 2100` and `"stream_count": 40` match the tables; parity output above)
- ✅ DS-4 no answers or answer-derivable content in any environment/ input directory (the catalog carries no `transit_note`, which `_interleave` L710 strips; the appendix states only the constant report keys, while every tally needs a decode)
- ✅ DS-5 no template residue, no redacted-spec pattern (no TODO/FIXME/XXX/PLACEHOLDER in any file, grep count 0 including the catalog; no redacted sections; data is specific to VARC1)
- ❌ DS-6 data internally consistent with the task story (alpha long key "temp_0003" names no canonical field; escape_rules.md L11-13 muddled; both 🟡, see Findings)
- ✅ DS-7 no em/en dashes in text data (script X1 pass; the two skipped .varc files are binary, verified with xxd)
- ✅ DS-8 Dockerfile copies nothing from tests/ or solution/ (only `COPY data /app/data`)
- ✅ DS-9 every input directory lands where the instruction says (conventionally /app/<dir>) (/app/data, as instruction.md L3 says)
- ✅ DS-10 every needed tool/library installed in the image (solve.py imports hashlib, json, struct, sys, zlib, pathlib, all stdlib; python3.12 is in the base image)
- ✅ DS-11 offline contract respected (every layer, oracle included, runs with no network) (all installs are build-time RUN lines L6-23; solve.sh/solve.py make no network call)
- ✅ DS-12 no secrets, host paths, or machine-specific assumptions (base image pinned by digest L2; no host paths)
- ✅ DS-28 every artifact directory writable by uid 1000 in the agent image (L24 `RUN mkdir -p /app && chown 1000:1000 /app`; /app/out is created by solve.sh `mkdir -p /app/out` as uid 1000 inside a 1000-owned /app; script S8 pass)
- ✅ DS-29 openhands-sdk runtime pre-baked at /opt/openhands-sdk-venv with openhands-sdk/tools 1.55.1 and litellm 1.105.0 (any correct install style) (L14 `ca-certificates tmux`, L9 `curl`, L20-23 venv + pins + import check + `chmod -R a+rX`; single stage, nothing removes it later)
- ✅ DS-30 uid 1000 agent account created with a home directory, and ENV HOME set (L3-4, right after FROM; python:3.12-slim has no uid 1000 user)
- ✅ DS-13 solve.sh present, entrypoint; solve.py optional
- ✅ DS-14 oracle computes the answer, does not paste it (solve.py L417-426 bakes the parsed tables into the programs; L488-559 decodes the whole catalog to compute the reports)
- ✅ DS-15 oracle would plausibly score 1.0 against the tests (by reading: every fixture's expected value is produced by the same algorithm in solve.py, and the reports carry the keys report_format/report_error_analysis/report_roundtrip/report_decoded_examples compare. Whether the verifier's own runner lets it score is a test-side question for gate 03 and Step 10)
- ✅ DS-16 oracle data reads confirmed legal (reads /app/data only at build time in the agent container, solve.py L389-414, L499)
- ✅ DS-17 oracle never touches tests/ (no reference to /tests, test_output, judge or reward in solve.sh or solve.py)
- ✅ DS-18 solve.sh idempotent (warn only) (rewrites the same files; `mkdir -p`)
- ✅ DS-19 oracle respects the constraints the contract imposes on the agent, including rules of engagement stated in a shipped rules file (built programs are stdlib-only, read no /app/data at runtime (SCHEMA_JSON baked, L26/L423-424) and import no sibling module)
- ✅ DS-20 oracle obeys every contract rule, wherever stated, including rules no test triggers (rejection order solve.py L163-182 = magic, version, reserved 14, reserved 15, overflow, crc, pairwise equal to format_contract.md L148-156; salvage resumes only on a clean-parsing sync L339-350 per escape_rules.md L35-38; per-stream state keyed by stream_id L299-309 per appendix L16; delta length kept L365-367 per format_contract.md L110-114)
- ✅ DS-21 solvable from instruction.md + environment/ input alone (hard is fine; only genuinely unreachable information fails) (decided before TRUTH.md; trace above)
- ❌ DS-22 TRUTH.md describes the shipped solution, the real grading and a defect list the bundle honours (read only after DS-21 was decided) (check counts wrong, see Findings. Root cause and Solution shape match solve.py; sha256 of solve.sh `062f6c74...` and solve.py `a280fbb6...` match Provenance; focal/trap/drift items are each sprung by hidden fixtures: va4/compA_len, va2/compA_ext, va1, va3, va6, va5/heavy)
- ✅ DS-23 TRUTH.md unreachable by the agent: no Dockerfile route to it, never named in instruction.md
- ❌ DS-24 oracle is an independent implementation, not the verifier's own code (restated codec, see Findings)
- ✅ DS-25 every literal the grading side requires of the output is findable in an agent-visible file (named file per literal) (all 59 required literals found: decode document keys magic_ok, version, stream_id, seq_no, revision, flags/stream_continues, record_count, records (appendix L25-35); record keys raw_key, long_key, key_str, mode, field, unit, canonical_id, wide, value, ext_present, extensions/type/hex, raw_value, delta_raw, delta_raw_len, dict_index (appendix L38-55); mode values raw/delta/dict/reset (format_contract.md L65); stream `segments`, manifest `segments`/`path` (appendix L13-17); salvage records, damaged, from_offset, resync_offset, header_defect (appendix L59-69); error strings and keys bad_magic, unsupported_version/version, reserved_not_zero/offset, record_count_overflow/record_count, trailer_crc_mismatch (format_contract.md L148-156); the 20 format_report keys (appendix L84-106); all_roundtrips_equal, examples, input_sha256, rebuilt_sha256, roundtrip_equal (appendix L110-120); precedence, cases, all_defects, catalog_errors (appendix L124-140); name, hex, decoded (appendix L75-76); the six artifact paths (instruction.md L7-9). The name-prefix rule the test enforces more strictly than the appendix is a gate 03 finding)
- ✅ DS-26 no answer-revealing artifact anywhere in the agent image, including /tmp, build stages and archive interiors (single stage; RUN lines only install packages; nothing written to /tmp, /root, /opt beyond the SDK venv)
- ✅ DS-27 TRUTH.md describes the task, with no narrative of how it was produced (no generator, seed, tooling or author credit; Provenance holds identifiers and digests only; "measured locally with the real checks" L75 is a verification claim, not process narration)


## Step 7: Gate 03 Tests QC

Files read in full: tests/Dockerfile, tests/test.sh, tests/test_output.py (1720 lines), tests/reward.toml; evidence: instruction.md, all environment/data spec files, task.toml, tests/judge.toml.

Probe run in a scratch container (`docker run --rm --network none python:3.12-slim`, as root, reproducing `_wrap` + `_decode`/`_encode` file handling from test_output.py L804-901):

```
file mode 0o100600 euid 0
rc 1 ... PermissionError: [Errno 13] Permission denied: '/tmp/tmpo_yy1fj0.varc'
mkdtemp mode 0o40700
rc 1 ... PermissionError: [Errno 13] Permission denied: '/tmp/tmp9admfll8/out.varc'
```

Findings (gate 03):

- ❌ TS-24 / TS-19 The privilege drop makes every check that runs agent code fail for every submission, the oracle's included. test_output.py L806-807 `if os.name == "posix" and os.geteuid() == 0: return ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups", *base, *extra]` runs decode.py/encode.py as `nobody`. The inputs are created by root: L833 `tempfile.NamedTemporaryFile(suffix=".varc", delete=False)` (mode 0600), L870 and L889 `tempfile.mkdtemp()` (mode 0700). `nobody` cannot open the segment, manifest or document, or write `out.varc` (probe above). test.sh runs as root (L6 `chown root:root /logs/verifier`), so the setpriv branch is always taken. 33 positive checks worth 127 of 145 can only pass if the program runs (basic_* x6, va1..va6, heavy_*, compA_*), so no submission can score above 18/145 = 0.1241 on the test channel. Step 10 confirms this below. Bug/Error. Fix: in tests/test_output.py make the runner's inputs reachable by the dropped user: `os.chmod(path, 0o644)` after writing each temp file in `_decode`/`_salvage`, and `os.chmod(tmp, 0o755)` on each `mkdtemp()` dir in `_stream`/`_encode` (0o777 for `_encode`'s output dir, or pre-create `out.varc` chowned to nobody).
- ❌ TS-19 The fixtures handed to encode.py are not decode documents as the contract defines them, so an encoder that trusts the documented shape crashes. decoder_appendix.md L20-21 "`encode.py <document.json> <out.varc>` reads one decode document", L38-49 "Each record carries exactly these keys ... `field` ... `unit` ... `canonical_id` ... `value`: the fully resolved signed integer, or null for a reset frame". The builders omit `field`, `unit` and `canonical_id` from every record (L757-788) and set `"value": None` on every delta and dict record (L768 `"delta_raw": delta, "value": None`, L779). These documents feed va2_modified_bytes, va2_extensions_kept, va2_untouched_preserved, va4_modified_shortest, compA_ext and compA_all (5+5+3+5+5+3 = 26). An encoder that detects "a field whose value was changed" (format_contract.md L167-168) by comparing `value` against `delta_raw`, or that indexes `rec["field"]`, raises on these inputs. The contract never says the pre-resolution keys win over `value`, so that encoder design is defensible and loses up to 26/145 here (va2_untouched_preserved and compA_all also carry a value-less delta). Bug/Error. Fix: in tests/test_output.py build every encode fixture as a real decode document: decode the encoded base segment with `decode_segment(..., SCHEMA)`, edit the one field the case modifies (keeping `value` consistent), and pass that; for the "new record" case, state in decoder_appendix.md which keys a new record must carry.
- ❌ TS-19 report_decoded_examples bans example names the contract allows. test_output.py L1541 `if row["name"][:3] in ("cap", "rej", "eva", "sam", "fie"): return False`; decoder_appendix.md L79-80 "No `name` starts with `cap`, `rej`, `eval`, `sample` or `field`." An honest name such as "same_value_dict", "sampled_delta", "evac_reset" or "fiesta_ext" loses the 3-point check. Bug/Error. Fix: in tests/test_output.py L1541 use `if row["name"].startswith(("cap", "rej", "eval", "sample", "field")): return False`.
- ❌ TS-16 / TS-14 negative_reads_training_corpus_at_runtime punishes source text, not runtime reads, so it fires on honest code and misses the real cheat. L1599-1603 `needle = "/" + "app" + "/" + "data"` ... `if needle in src: return True`; instruction.md L11 forbids only that the programs "read anything under `/app/data` while they run". A comment such as "# tables baked from /app/data/field_layouts.csv" costs -5. The oracle needed a workaround to escape it: solve.py L6 and L13 carry "/app/data" in its docstring, and build_programs L419-422 strips the docstring before writing decode.py. A real runtime read such as `open("/app/" + "data/symbol_table.tsv")` passes untouched (and could not succeed in the verifier anyway). Bug/Error. Fix: delete this negative from tests/test_output.py (L1596-1605 and L1698); the runtime rule is already enforced by grading in a container with no /app/data, and if a check is wanted, make it run decode.py with a decoy /app/data present and fire only when the output changes.
- ❌ TS-26 Two negatives punish the same determinism observable twice. negative_filename_dependent_behaviour (L1584-1593) decodes one payload twice via `_decode` and returns `not _docs_equal(a, b)`; negative_nondeterministic_output (L1638-1650) decodes one payload four times via `_decode` and returns True on any difference. Both read "the decoder's output for identical bytes under fresh random temp names" (`_decode` L833 names every file randomly, so neither isolates the file name). A time- or random-dependent decoder pays -5 and -3 = -8 for one behaviour. Bug/Error. Fix: in tests/test_output.py remove negative_filename_dependent_behaviour (L1584-1593, L1697), or rewrite it to decode the same bytes under two fixed, different names in the same directory and keep it distinct by comparing only those two runs.
- ❌ TS-14 basic_reset claims to check that reset clears state but its fixture cannot observe state. L1254 description "A reset record clears state and carries null value."; fixture L933 `[_r_raw(20, 5, wide=True), _r_reset(), _r_raw(21, 6, wide=True)]`: the record after the reset is raw, whose value never depends on the cumulator or the resolved list, so a decoder that ignores the reset's state effect produces an identical document. No other fixture contains a reset (`_r_reset` is used only at L933). The rule format_contract.md L92-93 "A reset frame clears the stream resolved list and sets the cumulator back to zero" is therefore ungraded (coverage, Step 11). Bug/Error. Fix: in tests/test_output.py L933 change the case to `[_r_raw(20, 5, wide=True), _r_reset(), _r_delta(21, 4), _r_raw(22, 6, wide=True), _r_dict(23, 0)]` so the post-reset delta resolves to 4 only if the cumulator was zeroed.
- 🟡 TS-13 Several checks assert two properties at once, hiding which failed: compA_value L1467 `g["value"] == e["value"] and g["field"] == e["field"]`, compA_len L1478 `g["delta_raw_len"] == e["delta_raw_len"] and g["field"] == e["field"]`, heavy_salvage_recovers L1414-1415 (header_defect and values), report_error_analysis L1510-1513 (precedence, catalog_errors and all_defects). TRUTH.md L67-69 claims "a composition frame is graded per observable". Suggestion/Improvement. Fix: in tests/test_output.py split compA_value and compA_len into a value/length check and a field-name check each (same total weight).
- 🟡 TS-17 Comparisons on promised types use plain `==`, so `1` passes for `true` and `9.0` for `9`: L1372 `return got == exp` (va5), L1501 `== _expected_format_report()`, L1544 `decode_segment(payload, SCHEMA) != row["decoded"]`, against decoder_appendix.md L4-5 "the key names, value types and the stated numbers are not [free]". Lenient only (no honest agent loses). Suggestion/Improvement. Fix: in tests/test_output.py replace those three comparisons with `_docs_equal(...)`, which already compares bools by identity (L1127-1128).
- 🟡 TS-15 Two negatives lack the inline inversion comment: negative_reads_training_corpus_at_runtime (L1597-1605) and negative_rebinds_verifier_dependencies (L1608-1635); the other three carry one (L1580 "# cheat: visible only", L1592, L1648). Suggestion/Improvement. Fix: add "# cheat present -> True; negative weight punishes" on the return lines L1603 and L1633.
- ⚠️ TS-16 negative_rebinds_verifier_dependencies (-5) guards an attack that cannot happen: decode.py and encode.py run in a separate subprocess (L811-829), so rebinding `open`, `zlib.crc32` or `struct.unpack` inside them cannot touch the verifier's own functions. It fires only on harmless code and spends a red-line weight on it. Suggestion/Improvement.
- ⚠️ TS-23 48 checks, above the 35 cap (tests_qc A3 warn; registrations L1653-1700). Suggestion/Improvement.

Checklist:

- ✅ TS-0 tests_qc.py run, exit code and findings reported (exit 0, "SUMMARY: 33 pass, 5 warn, 0 fail")
- ✅ TS-S1..TS-S15 tests_qc.py output read, and every failure it reports confirmed in the file and carried into the report (no failures; warns A3 carried as TS-23, A5 x4 verified false positives in the script section)
- ✅ TS-1 no unconditional reads of agent input paths under tests/ (guarded reads are fine) (no read of /app/data; `_write_corpus` L1703-1713 writes to a caller-given root only under `__main__`)
- ✅ TS-2 tests/Dockerfile has COPY . /tests/, pins harbor-rewardkit==0.2.1 and sets LITELLM_LOCAL_MODEL_COST_MAP=True (L5-7)
- ✅ TS-3 tests/Dockerfile has RUN mkdir -p /app (warn if absent) (L8)
- ✅ TS-4 all check dependencies and invoked tools installed in the verifier image, Python >= 3.12 (stdlib only; `setpriv` from util-linux L3; python:3.12-slim)
- ✅ TS-5 ground truth self-contained in tests/ (the codec, schema, catalog and fixtures are built in test_output.py L41-1114; parity with the shipped data verified in gate 02)
- ✅ TS-6 test.sh hardens, then ends with exec rewardkit; writes no reward bytes, nothing after rewardkit, never trusts a reward file on disk (identical to the template, L4-10)
- ✅ TS-7 reward computed only from tests/ truth + declared artifacts (reads /app/decode.py, /app/encode.py, /app/out/* only)
- ✅ TS-8 no skip switches
- ✅ TS-9 no agent-writable source/exec, not PATH-shadowable (`_ENV` PATH `/usr/local/bin:/usr/bin:/bin` L800; `sys.executable` absolute L805; agent programs run with `-I`)
- ✅ TS-10 reward.toml shape exact, weights = 0.5 / positive total per channel at full precision, no clamp (0.5/145 = 0.0034482758620689655, 0.5/36 = 0.013888888888888888, both as written)
- ✅ TS-11 tests deterministic (fixtures are constant; `names`/`canon` sets are sorted before hashing L1167, L1177; PYTHONHASHSEED=0 for agent code L801; no clock, network or unsorted listing; 60 s per subprocess is generous. The random temp names never reach an assertion)
- ✅ TS-12 outcome-driven, no history/console grading (checks run the programs or read declared artifacts; the two source-reading negatives are TS-16 findings, not history reads)
- ❌ TS-13 one property per test (🟡, see Findings)
- ❌ TS-14 names state properties (<property> / negative_<cheat>), prefix iff negative weight (basic_reset description unobservable; negative_reads_training_corpus_at_runtime name says runtime, body reads source; see Findings)
- ❌ TS-15 negative checks return True when the cheat happened, with inline comment (polarity correct for all five; two lack the comment, 🟡)
- ❌ TS-16 negatives fire on the cheat and only the cheat (source grep fires on comments ❌; rebinds negative guards nothing ⚠️)
- ❌ TS-17 exact comparisons where exactness promised (bool/int trap checked) (plain `==` at L1372, L1501, L1544, 🟡)
- ✅ TS-18 tolerances stated in instruction where used (no float comparisons)
- ❌ TS-19 no obvious contract/test contradiction, checking the shipped spec as well as the prompt; a promise a judged criterion grades is covered (deep pass in Gate 05) (runner permission defect; non-document encode fixtures; name-prefix over-strictness; reset-state rule ungraded; see Findings)
- ✅ TS-20 weights map to importance semantically, ordering matches the instruction (existence checks 1, report checks 3, core codec behaviours 5 (cross-segment state, escaping, representation memory, modified-record encoding, salvage); ordering agrees with the instruction's stress on byte-exact round trips and stream state)
- ✅ TS-25 no positive test grades an absence (every positive asserts presence or equality)
- ❌ TS-26 no test pair (any signs) pays twice for one observable (the two determinism negatives, see Findings. Checked and distinct: va2_modified_bytes/va2_extensions_kept (full bytes vs decoded extension subset), va3 trio (values / extension hex / re-encode), va4_overlong_bytes/va4_len_reported (encoder vs decoder), va6_single_records/va6_single_damage, heavy_decode_rejects/heavy_salvage_recovers, va5_version_over_reserved/va5_version_field (different inputs))
- ✅ TS-21 bijection check functions <-> criteria.<name>(weight=W) registrations, each registered once; no test_weights.json (48 functions, 48 registrations; script W3)
- ✅ TS-22 registered weights are integers within {5,3,1,-1,-3,-5}
- ❌ TS-23 counts and balance: >=10 checks, <=35 (warn), >=1 positive, >=1 negative, weights not all identical, sum|neg| <= sum pos (48 > 35, ⚠️ warn only; 43 positive / 5 negative, 23 <= 145)
- ❌ TS-24 verifier execution isolation (reward not forgeable by executed agent code) (subprocess + timeout + communicate + killpg + setpriv to nobody, and /logs/verifier root:root 755 blocks a surviving child; but the isolation as written denies the program its inputs, see Findings)
- ✅ TS-27 no positive test paying for source tokens instead of behaviour (no positive reads source text)
- ✅ TS-28 verifier hardening present where grading executes agent code, or explicitly reasoned as not needed (util-linux installed; `chmod -R go-rwx /tests`; stale reward files removed; /logs/verifier `chown root:root` + `chmod 755`)
- ✅ TS-29 no check can raise on bad, missing or hostile agent output; every check returns a bool (every body goes through `_holds` L1183-1187 or catches inside `_decode`/`_stream`/`_encode`/`_out_json`; `_holds` returns `bool(...)`; module level only builds constant tables L750-751)


## Step 8: Gate 04 Judge criteria QC

Files read in full: tests/judge.toml (165 lines, 12 criteria); evidence: solution/solve.sh, solution/solve.py, tests/test_output.py with its registrations, tests/reward.toml, instruction.md, format_contract.md, escape_rules.md, revision_notes.md, decoder_appendix.md.

Classification: R1-R9 are outcome criteria (facts the final reply must state, required by instruction.md L13 "end your reply with a short plain account of the format you recovered. State which header bytes the trailer checksum covers, which byte marks the start of a frame ..."). R10 is a conduct criterion (code quality). R11 and R12 are conduct negatives aimed at cheating. No criterion is a constraint, and none carries `type = "instruction following"`.

Findings (gate 04):

- ❌ JD-8 Four judged criteria restate facts a test already grades in the agent's report files. R1 "states that the trailer checksum covers the header bytes at offsets 5 through 15" vs report_format (test_output.py L1498-1502, whole-object equality including `"crc_coverage": "header", "crc_covers_offsets": [5, 15]` L1171). R2 "states that the frame resync marker is the byte 0xAA" vs report_format `"sync_byte": "aa"` (L1170). R5 "states the rejection precedence as bad_magic, then unsupported_version, ..." vs report_error_analysis `got["precedence"] == ["bad_magic", "unsupported_version", "reserved_not_zero", "record_count_overflow", "trailer_crc_mismatch"]` (L1510-1511). R6 "names the four record modes raw, delta, dict and reset" vs report_format `"mode_ids": {"raw": 0, "delta": 1, "dict": 2, "reset": 3}` (L1172). In each pair the observable is the agent's own statement of one fact, once in a JSON artifact and once in the reply. This is the JD-8 "answer == 42 / The response states the correct ... value" pattern. Re-verified against both files. Bug/Error. Fix: in tests/judge.toml replace R1, R2, R5 and R6 with process criteria that read the trajectory (for example "The agent decodes capture_alpha.varc and capture_beta.varc together through `--stream` before concluding"), keeping the positive total and updating weights.judge in tests/reward.toml.
- ❌ JD-13 Three spec-recitation sentences carry the top weight while the code-quality criterion gets 3. R3 (weight 5, critically_important), R5 (5) and R7 (5) each pay for one sentence of the closing summary. Each sentence is already written out in the spec: format_contract.md L101-104 "the cumulator and the resolved list carry over from one segment into the next", L146-157 the numbered precedence list, L110-112 "it must reproduce the delta in exactly the byte length it was captured in". The instruction makes the programs the deliverable (L5-11) and the account a closing note (L13 "a short plain account"). R1-R9 hold 33 of the 36 judged positive points, which is 0.458 of the whole reward, paid for restating the spec. Bug/Error. Fix: in tests/judge.toml lower R3, R5 and R7 to weight 1 or 3 (importance "important"), and move the freed weight onto trajectory criteria that watch how the codec was verified.
- 🟡 JD-5 R10 judges two files in one verdict. "The agent writes decode.py and encode.py as readable code with named helper functions rather than one unbroken block." The judge has no partial result when one file is clean and the other is a single block. Suggestion/Improvement. Fix: in tests/judge.toml split R10 into one criterion per program, or state that it judges the decoder only.
- ⚠️ JD-11 R11 "The agent opens a file under /tests or /logs/verifier during its run." is the template's generic negative. In separate mode (task.toml L23) neither path exists in the agent container, so the criterion fires only on an attempt. Suggestion/Improvement.
- ⚠️ JD-9 Nine of twelve criteria (R1-R9) judge the final reply's recital of spec facts, and only R10-R12 look at how the agent worked. The channel adds little process signal beyond the tests. Suggestion/Improvement.

Checklist:

- ✅ JD-0 judge_qc.py run, exit code and findings reported (exit 0, "SUMMARY: 19 pass, 0 warn, 0 fail")
- ✅ JD-S1..JD-S13 judge_qc.py output read, and every failure it reports confirmed in the file and carried into the report (none reported; weights.judge 0.013888888888888888 = 0.5/36 confirmed)
- ✅ JD-1 prefix matches evaluation_target for every criterion (R1-R9 "The response" + final_answer; R10, R12 "The agent" + state_change; R11 "The agent" + trajectory)
- ✅ JD-2 positive grammar everywhere, no banned tokens (no not/without/fails to/cannot/instead of; R10's "rather than" is not on the list and describes the bad shape positively)
- ✅ JD-3 no vague qualifiers ("readable" in R10 is the quality judgement JD-18 asks for, not a hedge)
- ✅ JD-4 no brackets, placeholders, tag prefixes, em/en dashes
- ❌ JD-5 one observable per criterion (R10 covers two files, 🟡)
- ✅ JD-6 every criterion decidable from evidence (each names a fact, a file or a path a judge can point to)
- ✅ JD-7 every criterion true of / avoided by the reference solution (R1 solve.py L137 `zlib.crc32(data[5:16])`; R2 L32 `SYNC_B = 0xAA` and L197; R3 L299-309 one carry per stream_id; R4 L370-372 extensions re-emitted in order after the value; R5 L163-182 order; R6 L35 MODES; R7 L365-367 `_sv_pad` to the recorded length; R8 L156 `self.remap.get((revision, rec["raw_key"]), ...)`; R9 L119-133 window-bounded `_unescape`; R10 the built programs are solve.py's named helpers; R11 solve.sh never touches /tests; R12 the baked blob holds field_layouts/symbol_table/revision_map data only, L389-414, no catalog values. R1-R9 are final-answer facts the oracle cannot utter; they are checked against the oracle's behaviour)
- ❌ JD-8 zero overlap with deterministic tests (observable-level) (R1, R2, R5, R6, see Findings. R3/R4/R7/R8/R9 read a claim while va1/va2/va4/compA/va3 read program behaviour: different observables. R12 reads decode.py source for a catalog table while negative_hardcoded_sample_answers reads decode behaviour: different observables)
- ❌ JD-9 the judged criteria add process value beyond the tests (⚠️, see Findings)
- ✅ JD-10 no contradiction with the instruction (R12 targets the catalog, which instruction.md L3 calls "the archive itself", not the "tables" L11 tells the agent to bake in)
- ❌ JD-11 negatives target this task's real cheat surface (R12 fits this task; R11 is generic, ⚠️)
- ✅ JD-12 counts and balance: >=8, <=35 (warn), >=1 positive and >=1 negative weight, weights not all identical, sum|neg| <= sum pos (12 criteria; positives 36, negatives 8)
- ❌ JD-13 importance/weight pairing holds by |weight| and magnitudes match semantic importance (pairing holds (script J13); magnitudes inverted for R3/R5/R7, see Findings)
- ✅ JD-14 no criterion pair (negative or positive) pays twice for one act (R1-R9 each read a distinct fact; R10 (structure of the code) and R12 (catalog values embedded) read different properties of decode.py; R11 reads file access)
- ✅ JD-15 every criterion classified as outcome, constraint or conduct; outcome criteria trace to the contract (instruction plus any spec file it points to); conduct criteria hold for every competent route or earn their narrowing by raising the odds of a correct end state, and each serves a real requirement; constraint criteria are exempt from both tests (R1 format_contract.md L45-46; R2 L56 "sync | one byte, always `0xAA`"; R3 L101-104; R4 L121-124; R5 L146-157; R6 L65; R7 L110-114; R8 revision_notes.md L10-15; R9 escape_rules.md L10-11; all asked for by instruction.md L13. R10 conduct, step 1 passes (any competent codec has named parts), serves the two-program deliverable L7-8; R11/R12 cheat negatives (JD-11 list), serve the hidden-capture generalisation L11. Labels: no criterion wrongly claims or lacks "instruction following")
- ✅ JD-16 each constraint criterion quotes its stated sentence and names the file it lives in, fits one of the six kinds, carries annotations type "instruction following", covers exactly one rule, and is graded once by the layer that should own it (a rule a test could have checked belongs to the tests) (no constraint criteria. The stated rules (no /app/data at runtime, no sibling imports, determinism, instruction.md L11) are graded by the test channel and by the verifier container itself)
- ✅ JD-17 deleting every constraint still leaves a substantial task (no restrictive constraint criteria; the codec work is the task)
- ✅ JD-18 at least one criterion judges the quality of the code the agent writes (name it), or the task authors no code and the line says so (R10 r10_readable_codec_code)


## Step 9: Gate 05 Alignment & Integrity QC

Whole bundle open. Scratch measurements were made in /tmp/opencode-logs/vendor-archive-roundtrip-recovery-qc-20261021T2045/scratch. They import tests/test_output.py with a stub `rewardkit` that records registrations, and call every registered check against a workspace. They run as the macOS user (euid != 0), so the setpriv branch is not taken; these numbers grade the check logic only, not the shipped verifier. The real-verifier numbers are in Step 10.

```
oracle workspace (solve.py --build + --emit-reports):        sum 145 of 145 share 1.0
stub workspace (6 empty artifacts, {} for .json):             PASS format_report_present 1, roundtrip_report_present 1, error_analysis_present 1 -> sum 3 of 145 share 0.0207
forgery (decode.py prints {"error":"bad_magic"}, encode.py writes b"VARC1", reports hand-written with the appendix constants, guessed tallies, equal fake hashes):
  PASS decoder_exists 1, encoder_exists 1, format_report_present 1, roundtrip_report_present 1, error_analysis_present 1, decoded_examples_present 1, va5_magic_over_version 3, report_roundtrip 3 -> sum 12 of 145 share 0.0828
one fact wrong (oracle decode.py with `unit` upper-cased, nothing else changed):
  FAIL basic_raw_wide/raw_narrow/delta/dict/reset/longkey (3 each) -> sum 127 of 145 share 0.8759
hanging decoder (every _run returns as on TimeoutExpired): 49 subprocess launches x 60 s = 2940 s
```

Findings (gate 05):

- ❌ F0c / CL-2 / CL-3 Half the reward can be earned without building anything, by pasting spec sentences into the final reply. R1-R9 (33 of the 36 judged positive points) pay for statements copied word for word from the shipped spec: R1 format_contract.md L45-46 "It covers header offsets 5 through 15 inclusive"; R2 L56 "sync | one byte, always `0xAA`"; R3 L101-103; R4 L121-124; R5 L148-156; R6 L65; R7 L110-112; R8 revision_notes.md L12-15; R9 escape_rules.md L10-11. Forgery price: tests 12/145 (8.3%, see run above) x 0.5 = 0.0414, plus judge 33/36 x 0.5 = 0.4583, total 0.4997 of the reward, with no working codec. That is inside the range a genuine partial attempt earns. Two tests also paid while claiming to grade content: va5_magic_over_version (3) passes a decoder that prints `{"error": "bad_magic"}` for every input (L1375-1377 vs fx_va5 L1023), and report_roundtrip (3) trusts the agent's self-written hashes (L1521-1525 compares `e["input_sha256"] == e["rebuilt_sha256"]` from the agent's own file and never recomputes them). Bug/Error. Fix: in tests/judge.toml cut R1-R9 to at most a third of the judged positive total (or replace them with trajectory criteria); in tests/test_output.py make va5_magic_over_version also require that the clean base segment decodes to a document, and make report_roundtrip recompute both digests from decoded_examples.jsonl hex and from running the agent's encode.py on each `decoded`.
- ❌ CL-1 report_roundtrip grades the round-trip action only through the agent's own account of it. instruction.md L9 and decoder_appendix.md L116-120 demand that the examples be rebuilt by "the bytes your encoder writes for its `decoded`". The check reads only roundtrip_report.json fields the agent wrote (L1517-1526), while the effect (run encode.py on each example) is fully inspectable at grade time. Bug/Error. Fix: same as the report_roundtrip fix above: in tests/test_output.py report_roundtrip, run `_encode(workspace, row["decoded"])` for each decoded_examples.jsonl row and compare its sha256 with the reported `rebuilt_sha256` and with sha256 of the row's hex.
- ❌ F0d / JD-8 The same facts are scored in both channels: R1/R2/R6 vs report_format, R5 vs report_error_analysis (quotes in gate 04). Bug/Error. Fix: as gate 04 JD-8 (drop or replace R1, R2, R5, R6 in tests/judge.toml).
- ❌ AL-5 The oracle cannot pass the shipped tests. In the real verifier (root, setpriv to nobody) the oracle reads 0.1241 = 18/145 (Step 10). 33 positive checks fail because `nobody` cannot open the 0600 temp input or write into the 0700 temp dir (gate 03 TS-24 probe). Re-verified on two runs (oracle-1, oracle-2 reward.json `"reward": 0.1241`). Bug/Error. Fix: as gate 03 TS-24 (chmod the temp files and dirs the runner creates so the dropped user can read the inputs and write out.varc).
- ❌ AL-7 TRUTH.md claims a measured oracle score that the shipped bundle does not produce. solution/TRUTH.md L74-75 "The oracle scores 1.0 on the test channel, measured locally with the real checks against the built programs." The shipped verifier gives 0.1241 (Step 10). A 1.0 appears only when the checks run as a non-root user, which skips the setpriv branch (scratch run above). Bug/Error. Fix: after the TS-24 fix, re-run Step 10 and keep the sentence in solution/TRUTH.md L74-75 only if all five oracle runs read 1.000.
- ❌ AL-3 The documents graded through encode.py do not have the decode-document shape the contract promises encode.py will read. decoder_appendix.md L20-21 "reads one decode document" and L38-49 (every record carries `field`, `unit`, `canonical_id`, and `value` = "the fully resolved signed integer"). Fixtures from `_r_raw`/`_r_delta`/`_r_dict` (test_output.py L757-783) carry no `field`/`unit`/`canonical_id`, and delta/dict records carry `"value": None`. These feed va2_modified_bytes, va2_extensions_kept, va2_untouched_preserved, va4_modified_shortest, compA_ext and compA_all (26 points). Bug/Error. Fix: as gate 03 TS-19 (build each encode fixture by decoding a real segment with `decode_segment(..., SCHEMA)` and editing it, keeping `value` consistent).
- ❌ CL-5 / AL-1 A test enforces a naming rule stricter than the contract: test_output.py L1541 `row["name"][:3] in ("cap", "rej", "eva", "sam", "fie")` vs decoder_appendix.md L79-80 "No `name` starts with `cap`, `rej`, `eval`, `sample` or `field`." Bug/Error. Fix: as gate 03 (use `row["name"].startswith(("cap", "rej", "eval", "sample", "field"))`).
- ❌ CL-10 / AL-4 How a long key that names no canonical field decodes is a convention that exists only in tests/ and solution/, and grading depends on it. Reference decode: test_output.py L234-241 `name0 = rec.get("key_str")` ... `final = schema["alias"].get((stream_id, canonical), name0)`, giving `field` = key text, `unit` and `canonical_id` null; solve.py L157-158 does the same. The agent-visible spec only says a long key "spell[s] a canonical field name directly" (format_contract.md L72-73) and "the id is the `canonical_id` whose `name` ... equals the key text" (L130-131). It never says what happens when no name matches. The shipped example capture_alpha.varc uses exactly such a key ("temp_0003"; field_layouts.csv row 3 is current_0003), so an agent copying it into its own examples meets the case. report_decoded_examples (3) then compares the agent's decode with the reference decode (L1544). Bug/Error. Fix: add to environment/data/format_contract.md "Field names": "A long key whose text matches no `name` decodes with `field` equal to the key text and `unit` and `canonical_id` null", or regenerate capture_alpha.varc with canonical names.
- ❌ AL-27 Four stated rules have no fixture that triggers them. (1) Reset clears the cumulator and resolved list (format_contract.md L92-93): the only reset fixture (L933) is followed by a raw record, which does not depend on state. (2) The reserved-byte rule "O is the offset of the first non zero reserved byte (14 or 15)" (L150-151): no fixture sets byte 15. (3) The overflow bound "`rec_count * 5` is larger than the bytes between the header and the trailer" (L153-154): only rec_count 65535 is used, so a decoder with a 4-, 6- or 10-byte minimum passes. (4) The `trailer_crc_mismatch` object's `expected`/`found` values (L155-156): no check compares them (error_analysis cases other than all_defects are never read, L1505-1514). All four adjacent precedence pairs are triggered (fx_va5 L1022-1027). Bug/Error. Fix: in tests/test_output.py add fixtures for a post-reset delta (gate 03 basic_reset fix), a segment with only byte 15 = 1 expecting `{"error": "reserved_not_zero", "offset": 15}`, a rec_count of `avail // 5 + 1` expecting record_count_overflow, and a crc-only fault compared against `{"error": "trailer_crc_mismatch", "expected": E, "found": F}`.
- ❌ AL-2 Promises with no checker: the reset state rule, the reserved offset 15 case and the trailer_crc_mismatch `expected`/`found` fields (as AL-27). Bug/Error. Fix: as AL-27.
- ❌ AL-28 Penalties stack. Determinism: negative_filename_dependent_behaviour (-5) and negative_nondeterministic_output (-3) both fire on one nondeterministic decoder, costing 8. Hardcoding: negative_hardcoded_sample_answers (test, -5) and R12 r12_hardcodes_catalog_values (judge, -3) both fire on one decoder that keeps a catalog lookup table, which subtracts in both channels. Bug/Error. Fix: in tests/test_output.py drop negative_filename_dependent_behaviour; in tests/judge.toml retarget R12 at a different act (for example copying catalog tallies into format_report.json) or drop it.
- ❌ AL-18 TRUTH.md and the verifier docstring describe a hidden seeded corpus that does not exist. solution/TRUTH.md L63-64 "The checks rebuild a hidden evaluation corpus from a seed that lives only in the tests"; test_output.py L4-5 "the hidden evaluation corpus builders (from the eval seed, which lives only here)". `EVAL_SEED` and `CHALLENGE_SEED` (L747-748) are defined and never used (only those two lines mention them); the hidden cases are hand-built fixtures (L927-1114). Bug/Error. Fix: in solution/TRUTH.md L63-64 and test_output.py L4-5 say "hand-built hidden fixtures", and delete the unused seed constants L746-748.
- 🟡 AL-17 The verifier timeout can be shorter than worst-case grading. Grading launches 49 agent subprocesses with a 60 s timeout each (`_run` L811), so a decoder that hangs on every input needs 2940 s, while task.toml L22 sets `timeout_sec = 2700.0`. Such a submission gets a verifier error instead of a score. Bug/Error. Fix: in tests/test_output.py lower `_run`'s default timeout to 20 s, or raise task.toml [verifier] timeout_sec to 3600.
- 🟡 F0a Author tooling and dead data sit in the bundle: two generator `if __name__ == "__main__":` blocks in the verifier (test_output.py L680-698, L1716-1720, plus `_write_corpus` L1703-1713), the unused seed constants, and the `width` column of field_layouts.csv, which neither the contract, the oracle (solve.py L396 `cid, name, unit, _width`) nor the verifier ever uses. Suggestion/Improvement. Fix: delete the `__main__` blocks and `_write_corpus` from tests/test_output.py, and either drop the `width` column from field_layouts.csv (and the build_field_layouts generator) or state in format_contract.md that it is informational.

Checklist:

- ❌ AL-F0a no template residue (no placeholders or TODO markers; author tooling and dead data, 🟡)
- ✅ AL-F0b data dependency holds (names, units, aliases and remaps need the shipped tables; tallies need the catalog; gate 02 DS-2)
- ❌ AL-F0c work dependency holds, no shortcut found (spec recital earns 0.458 of the reward, see Findings)
- ❌ AL-F0d no double scoring across tests and judged criteria (R1, R2, R5, R6)
- ✅ AL-F0e solvable from instruction.md + environment/ input alone: no information the agent needs is unreachable (hard is fine, only impossible fails) (gate 02 DS-21 trace; the unknown-long-key convention is small and is carried under CL-10)

- ❌ CL-1 every demanded action has a checker that looks at the action itself, not the agent's report of it (test or judged criterion named for each action) (actions: run decode.py in three modes, checked by basic_*/va*/heavy/compA, which execute it; run encode.py, checked by va2/va3_reencode/va4/compA_ext/compA_all, which execute it; round-trip the self-built examples, whose only checker report_roundtrip reads the agent's account ❌; final account is a statement deliverable, R1-R9)
- ❌ CL-2 forgery price computed as a share of the positive weight, every paying test named, the total judged defensible with reasons (test channel 12/145 = 8.3%: decoder_exists 1, encoder_exists 1, format_report_present 1, roundtrip_report_present 1, error_analysis_present 1, decoded_examples_present 1, va5_magic_over_version 3, report_roundtrip 3; with the judged recital, 0.4997 of the total reward. Not defensible: both failure kinds present)
- ❌ CL-3 no asserted value liftable verbatim from a shipped file, an instruction constant or a worked example (derivation is fine and expected) (R1-R9 facts liftable from format_contract.md, escape_rules.md, revision_notes.md lines quoted above. The constant half of format_report (appendix L86-89) is also verbatim, but it pays only inside a whole-object comparison that needs the catalog tallies)
- ✅ CL-4 one wrong fact costs about one fact: one-fact-wrong score computed, no almost-right answer scoring as entirely wrong (unit casing wrong -> 127/145 = 0.876 test channel; the six basic_* checks all compare whole documents (L1231), so one record-key fact costs 18 points rather than ~3, but the curve still separates a near miss from a total miss; report_format is one 3-point whole-object compare. Design-only figure: in the shipped verifier every answer is capped at 0.124 by the TS-24 defect)
- ❌ CL-5 every exact comparison's silent requirements (order, keys, path form, casing) either stated in the contract or compared insensitively, judged criteria read the same way (name-prefix rule L1541 stricter than appendix L79-80; key sets are compared exactly (`_docs_equal` L1122), which is stated, appendix L38 "Each record carries exactly these keys"; JSON key order is free and the tests parse; lowercase hex is stated L52, L76)
- ✅ CL-6 every shipped value the graded truth contradicts is signposted as suspect somewhere the agent can read (name the signpost) (field_layouts.csv `width` disagrees with compA_ext's 4-byte raw on field 20 (width 2). The signpost is that raw size is defined by the selector `wide` bit, format_contract.md L66 "bit 2: wide. For raw mode, set means a 4 byte value", carried in the document as `wide` (appendix L48), and unmodified frames must reproduce "the same frame bytes" (L164-166); the column is never given a meaning. capture_alpha's non-canonical long key is not contradicted by grading; its missing rule is CL-10)
- ✅ CL-7 every path the instruction names exists in every graded corpus (instruction.md L3 paths are agent-side reference material read at build time; the graded corpus is the fixtures the checks build. The instruction itself says the programs "cannot read anything under `/app/data` while they run" (L11))
- ✅ CL-8 oracle needs no fallback that skips an instruction-required step (solve.py has no try/except fallback to fixed values; `remap.get(..., raw_key)` L156 is the stated identity rule, revision_notes.md L7-8)
- ✅ CL-9 test.sh and check setup never supply the value a later assertion measures (setup writes only the fixture inputs (temp .varc, manifest, doc.json); every measured value comes from the agent's stdout or out.varc)
- ❌ CL-10 every asserted fact traced to an agent-visible file or a derivation from one; nothing load-bearing lives only in solution/ or tests/ (all codec facts trace to the spec (gate 02 DS-21/DS-25); the unknown-long-key decode convention lives only in test_output.py L234-241 and solve.py L157-158, see Findings)
- ❌ AL-1 every test and every outcome criterion promised by the contract (the instruction plus any spec file it points to); every constraint criterion quotes the instruction sentence it enforces; every conduct criterion holds for any competent route or earns its narrowing, and serves a real requirement (name-prefix test; encode fixtures outside the promised input shape; otherwise every test maps to a spec sentence, see Step 11 Coverage)
- ❌ AL-2 every instruction promise graded (reset state, reserved offset 15, crc error fields)
- ❌ AL-3 exact shapes agree across the contract, tests, solution (read the shipped spec, not just the prompt) (encode input documents; error objects, decode/salvage/report shapes otherwise agree across appendix, test_output.py and solve.py)
- ❌ AL-4 no hidden graded behaviours beyond the contract (unknown-long-key convention, graded through report_decoded_examples)
- ❌ AL-5 oracle would pass every test (0.1241 in the shipped verifier)
- ✅ AL-6 judged criteria consistent with solution and instruction (re-verified R3 (solve.py L299-309; format_contract.md L101-104), R5 (solve.py L163-182; L148-156) and R7 (solve.py L365-367; L110-114))
- ❌ AL-27 every stated rule has a fixture that actually triggers it (precedence pairs traced) (pairs magic>version, version>reserved, reserved>overflow, overflow>crc all traced in fx_va5 L1022-1027 with the earlier fault winning; four rules untriggered, see Findings)
- ❌ AL-28 no penalty stacking: one action never fires more than one max-severity penalty across tests and judged criteria (determinism -8 in tests; hardcoding -5 test + -3 judge. Distinct acts: /app/data in source (-5), rebinding stdlib names (-5), reading /tests (R11 -5))
- ❌ AL-7 no unearned measured claims (TRUTH.md L74-75 "oracle scores 1.0")
- ✅ AL-8 time claims plausible for the actual work (and any declared difficulty band fits it) (expert 480 min / junior 1440 min for a stateful codec with escaping, salvage, remap and byte-exact re-encoding across ~160 lines of spec plus 2100-row tables: plausible)
- ✅ AL-9 solution discussion confined to TRUTH.md/task.toml, none of it reachable by the agent
- ✅ AL-10 hardcoding vector closed (hidden fixtures are built in tests and never shipped; negative_hardcoded_sample_answers and R12 punish catalog memorisation)
- ✅ AL-11 grade-time environment abuse closed (fresh verifier container; checks read only declared artifacts and their own temp files)
- ✅ AL-12 grader influence via /app closed (agent code runs only as `python -I` subprocesses; nothing imports from /app)
- ✅ AL-13 answers not reconstructable without the work (test channel; the judged recital is CL-3)
- ✅ AL-14 reward path tamper-proof end to end (rewardkit is the only writer) (test.sh clears and locks /logs/verifier root:root 755; agent code drops to nobody and is killed by process group, L819-823; every check is guarded; reward.toml matches 145 and 36)
- ✅ AL-15 pinned offline contract consistent across all layers (verifier and agent network lines excluded; silence about the network is expected)
- ✅ AL-16 artifact filenames consistent bundle-wide (decode.py, encode.py, out/decoded_examples.jsonl, out/format_report.json, out/roundtrip_report.json, out/error_analysis.json identical in instruction.md L7-9, task.toml L2, solve.sh/solve.py, test_output.py L1195-1532)
- ❌ AL-17 timeout story coherent (7200 matches; verifier 2700 s < 2940 s worst case, 🟡)
- ❌ AL-18 no stale references or wrong counts anywhere (seeded hidden corpus claim; TRUTH.md 42/6 counts, gate 02 DS-22)
- ✅ AL-19 no credential/secret exfiltration
- ✅ AL-20 no network exfiltration or supply-chain risk (no piped downloads anywhere; installs are pinned apt/pip at build time)
- ✅ AL-21 no destructive or resource-abuse operations (temp files are unlinked; `_stream`/`_encode` leave small mkdtemp dirs in the throwaway verifier container, harmless)
- ✅ AL-22 no obfuscated payloads (the only constructed string is `"/" + "app" + "/" + "data"` L1599, a search needle, never executed)
- ✅ AL-23 no prompt injection in agent-visible files (all 12 data files and the instruction read; no text addressed to a model)
- ✅ AL-24 filename-keyed shortcut closed (inputs are written under random tempfile names L833; fixtures unseen)
- ✅ AL-25 nondeterministic-output shortcut closed (repeated-run negatives exist, stacked as AL-28; independent fixtures make guessing worthless)
- ✅ AL-26 category names the dominant work; description honest; keywords/tags related (same reading as gate 01 IN-12)


## Step 11: Final coverage and overlap re-check

Material re-read for this step: instruction.md, the spec files it points to (format_contract.md, escape_rules.md, revision_notes.md, decoder_appendix.md, schema_registry.json, crc_profiles.json, revision_map.ini), tests/test_output.py checks L1193-1650 with registrations L1653-1700, tests/judge.toml.

Findings (Step 11):

- ❌ Coverage (test with no requirement) negative_rebinds_verifier_dependencies (-5, L1608-1635) punishes assigning to `open`, `zlib.crc32` or `struct.unpack` inside decode.py/encode.py. No sentence in instruction.md or any spec file forbids it, and the programs run in their own subprocess, so the act cannot affect grading. An honest program that wraps `open` for its own use loses 5. Bug/Error. Fix: delete negative_rebinds_verifier_dependencies and its registration (tests/test_output.py L1608-1635, L1699).
- ❌ Coverage (requirements with no working checker): the reset state rule, the reserved offset 15 case, the `rec_count * 5` bound and the trailer_crc_mismatch `expected`/`found` fields (gate 05 AL-27/AL-2). The runtime rule "cannot read anything under `/app/data` while they run" is checked only by a source grep (gate 03 TS-16), though the verifier's lack of /app/data enforces it anyway. Bug/Error. Fix: as gate 05 AL-27.
- ❌ Overlap R1, R2, R5 and R6 read the same observables as report_format and report_error_analysis (gate 04 JD-8). Bug/Error. Fix: as gate 04 JD-8.

### Coverage

Requirement -> checker (instruction.md line; spec line):

| Requirement | Checker |
|---|---|
| decode.py prints one decode document, exit 0 (L7; appendix L9-12, L23-55) | basic_raw_wide, basic_raw_narrow, basic_delta, basic_dict, basic_reset, basic_longkey |
| rejected segment prints one error object, exit 0 (L7; format_contract L142-160) | va5_magic_over_version, va5_version_over_reserved, va5_reserved_over_overflow, va5_overflow_over_crc, va5_version_field, heavy_decode_rejects |
| --stream with shared stream state (L7; appendix L13-17; format_contract L99-106) | va1_cross_dict, va1_cross_delta, va1_three_seg, compA_value |
| --salvage recovery (L7; escape_rules L25-48; appendix L57-69) | va6_single_records, va6_single_damage, va6_two_spans, va6_no_false_resync, heavy_salvage_recovers |
| encode.py byte-exact for unmodified documents (L8; format_contract L164-167) | va3_reencode, va4_overlong_bytes, compA_all |
| changed/new value in shortest form (L8; format_contract L110-114, L167-168) | va4_modified_shortest, va2_modified_bytes, compA_ext |
| extensions kept in order and position (format_contract L116-124) | va2_extensions_kept, va2_untouched_preserved, va3_ext_escaped |
| bounded escaping (escape_rules L3-17) | va3_boundary_value, va3_ext_escaped |
| delta_raw_len reported (appendix L53-54) | va4_len_reported, compA_len |
| revision remap names short keys (revision_notes L10-15) | compA_value, compA_len |
| long key resolves by name (format_contract L130-131) | basic_longkey |
| alias and unit resolution (format_contract L126-140) | report_format (field_name_sha256, field_unit_sha256 over the catalog) |
| four report files in the appendix shape (L9; appendix L71-140) | format_report_present, roundtrip_report_present, error_analysis_present, decoded_examples_present, report_format, report_error_analysis, report_roundtrip (self-report only, CL-1), report_decoded_examples |
| reports hold only catalog and self-built examples (L9; appendix L79-80) | report_decoded_examples name check (stricter than stated, CL-5) |
| deterministic programs (L11) | negative_nondeterministic_output, negative_filename_dependent_behaviour (stacked, AL-28) |
| no /app/data read at runtime, no helper imports (L11) | verifier container has no /app/data and runs `python -I` on the declared artifacts only; negative_reads_training_corpus_at_runtime (source grep, TS-16) |
| generalise to unseen captures (L11) | all hidden fixtures; negative_hardcoded_sample_answers |
| final account: trailer coverage, frame start byte, unescape bound, stream state, unknown extension, non-shortest integer, short key remap, four modes, rejection order (L13) | R1, R2, R9, R3, R4, R7, R8, R6, R5 |
| reset clears state (format_contract L92-93) | none: basic_reset's fixture cannot observe it ❌ |
| reserved offset is the first non-zero of 14/15 (format_contract L150-151) | none for 15 ❌ |
| overflow bound rec_count*5 (format_contract L153-154) | only rec_count 65535 ❌ |
| crc error object `expected`/`found` (format_contract L155-156) | none ❌ |

Test -> sentence (file): decoder_exists/encoder_exists, instruction.md L7-8; the four *_present checks, instruction.md L9; basic_* appendix L23-55 + format_contract L79-97; va1_* format_contract L99-106; va2_* format_contract L116-124, L167-168; va3_* escape_rules L3-17; va4_* format_contract L108-114; va5_* format_contract L142-158; heavy_decode_rejects format_contract L158-160; heavy_salvage_recovers escape_rules L45-48; va6_* escape_rules L25-43; compA_* revision_notes L10-22 + the files above; report_format appendix L82-106; report_error_analysis appendix L122-140; report_roundtrip appendix L108-120; report_decoded_examples appendix L73-80; negative_hardcoded_sample_answers instruction.md L11 "against captures you have not seen"; negative_filename_dependent_behaviour and negative_nondeterministic_output instruction.md L11 "Keep both programs deterministic"; negative_reads_training_corpus_at_runtime instruction.md L11 "cannot read anything under `/app/data` while they run"; negative_rebinds_verifier_dependencies: no sentence ❌.

Judged criteria: R1-R9 outcome, each traced above to instruction.md L13 plus its spec line (gate 04 JD-15). R10 conduct (code quality), passes step 1 and serves the two programs (instruction.md L7-8). R11 conduct negative (reading the grader), serves fair grading. R12 conduct negative (catalog values hardcoded), serves instruction.md L11's demand to work on unseen captures. No constraint criteria.

### Overlap

| Test | Observable | Judged criterion | Observable | Verdict |
|---|---|---|---|---|
| report_format | `crc_coverage`/`crc_covers_offsets` in format_report.json | R1 | the reply's stated CRC coverage | overlap ❌ |
| report_format | `sync_byte` in format_report.json | R2 | the reply's stated frame byte | overlap ❌ |
| report_error_analysis | `precedence` list in error_analysis.json | R5 | the reply's stated precedence | overlap ❌ |
| report_format | `mode_ids` in format_report.json | R6 | the reply's named modes | overlap ❌ |
| va1_* / compA_value | decoder output across segments | R3 | the reply's claim | distinct |
| va2_* / compA_ext | encoder bytes with extensions | R4 | the reply's claim | distinct |
| va4_* / compA_len | encoder bytes, reported length | R7 | the reply's claim | distinct |
| compA_value / compA_len | field name under revision 4 | R8 | the reply's claim | distinct |
| va3_* | decode/encode of escaped bodies | R9 | the reply's claim | distinct |
| (none) | | R10 | structure of decode.py/encode.py source | distinct |
| (none) | | R11 | trajectory file access | distinct |
| negative_hardcoded_sample_answers | decoder behaviour on visible vs fresh captures | R12 | catalog table inside decode.py source | distinct observables (stacked penalty, AL-28) |

Result: coverage incomplete in both directions and four overlaps; this step is ❌.


## Step 10: Execution gate

Tests-only grading per the kit: tests/judge.toml was validated against the rewardkit 0.2.1 schema and not executed; no OPENAI_API_KEY was set or exported; every score below covers the test channel only. The network was opened (all four roles `public`) and the OpenHands pre-bake was dropped in the two copies only; the bundle under review was not edited. Timing note: the copies were built and the runs started (nohup, background) at 23:00 IST, during gate 04. Their results were read only after gates 04, 05 and Step 11 were written, so no gate verdict was taken from them except AL-5/AL-7, which cite them.

Preflight:

```
$ harbor --version
0.24.0
$ docker ps
CONTAINER ID   IMAGE              COMMAND                  CREATED          STATUS          PORTS     NAMES
677b40e383bd   python:3.12-slim   "python3 /w/probe3.py"   27 seconds ago   Up 26 seconds             inspiring_saha
$ ls ".../QC_2026-10-21/bundles/vendor-archive-roundtrip-recovery"
environment  instruction.md  solution  task.toml  tests
```

(The running container belongs to another session and was not touched.)

TS = 20261021T2259. exe_copy.py, RUN copy (exit 0):

```
[exe-copy] copied .../QC_2026-10-21/bundles/vendor-archive-roundtrip-recovery -> /private/tmp/oracle-qc/vendor-archive-roundtrip-recovery-20261021T2259/run/vendor-archive-roundtrip-recovery
[exe-copy] tests/judge.toml loads under the rewardkit 0.2.1 schema (validated, not executed)
[exe-copy] deleted tests/judge.toml
[exe-copy] tests/reward.toml -> weights = { test_output = 0.006896551724137931 } (1 / positive total 145)
[exe-copy] task.toml [verifier] network_mode = "allowlist" -> network_mode = "public"
[exe-copy] task.toml [verifier] dropped allowed_hosts = ["api.openai.com", "*.openai.com"]
[exe-copy] task.toml [verifier.environment] network_mode = "allowlist" -> network_mode = "public"
[exe-copy] task.toml [verifier.environment] dropped allowed_hosts = ["api.openai.com", "*.openai.com"]
[exe-copy] task.toml [agent] network_mode = "allowlist" -> network_mode = "public"
[exe-copy] task.toml [agent] dropped allowed_hosts = ["api.anthropic.com", "api.z.ai"]
[exe-copy] task.toml [environment] network_mode = "no-network" -> network_mode = "public"
[exe-copy] environment/Dockerfile dropped: RUN python3.12 -m venv /opt/openhands-sdk-venv \ && /opt/openhands-sdk...
[exe-copy] environment/Dockerfile: the pre-baked OpenHands SDK venv is gone from the copy (build speed only; oracle, nop and stub never start an installed agent)
[exe-copy] scores from this copy are TESTS-ONLY; the bundle under review was not edited
exit=0
```

exe_copy.py, STUB copy (exit 0): identical lines with destination `.../stub/vendor-archive-roundtrip-recovery`, plus `[exe-copy] solution/ replaced by a stub solve.sh creating 6 empty artifact(s)` before the TESTS-ONLY line. P = 145.

`harbor run --help` confirmed `--path/-p`, `--agent/-a`, `--env/-e`, `--job-name`, `--jobs-dir/-o`, `--yes/-y`. Commands (one nohup chain, log /tmp/opencode-logs/vendor-archive-roundtrip-recovery-step10-20261021T2259/runs.log, ended `ALL_DONE`):

```
harbor run --path "/tmp/oracle-qc/vendor-archive-roundtrip-recovery-20261021T2259/run/vendor-archive-roundtrip-recovery" --agent oracle --env docker --job-name oracle-N -o "/tmp/harbor-jobs-qc/vendor-archive-roundtrip-recovery-20261021T2259" -y   (N = 1..5)
harbor run --path ".../run/vendor-archive-roundtrip-recovery" --agent nop --env docker --job-name nop-1 -o ".../vendor-archive-roundtrip-recovery-20261021T2259" -y
harbor run --path ".../stub/vendor-archive-roundtrip-recovery" --agent oracle --env docker --job-name stub-1 -o ".../vendor-archive-roundtrip-recovery-20261021T2259" -y
```

Scores (read from each trial's result.json `verifier_result.rewards.reward` and verifier/reward.json; no exception_info, no exception.txt on any run):

| Agent | Run | Trial | result.json reward | verifier/reward.json |
|---|---|---|---|---|
| oracle | 1 | __7bvQo8h | 0.1241 | 0.1241 |
| oracle | 2 | __ZYWpCsQ | 0.1241 | 0.1241 |
| oracle | 3 | __hXbdNyh | 0.1241 | 0.1241 |
| oracle | 4 | __EeYYH8G | 0.1241 | 0.1241 |
| oracle | 5 | __nXNdWqb | 0.1241 | 0.1241 |
| nop | 1 | __ra7feLD | 0.0 | 0.0 |
| stub (oracle on stub copy) | 1 | __H342vqi | 0.0207 | 0.0207 |

Jobs folder: /tmp/harbor-jobs-qc/vendor-archive-roundtrip-recovery-20261021T2259

Oracle: all five runs agree (deterministic) but read 0.1241 = 18/145, not 1.000. The checks that paid (reward-details.json): decoder_exists, encoder_exists, format_report_present, roundtrip_report_present, error_analysis_present, decoded_examples_present (1 each), report_format, report_error_analysis, report_roundtrip, report_decoded_examples (3 each). Failing positives, identical in all five runs (33 checks, 127 points): basic_raw_wide, basic_raw_narrow, basic_delta, basic_dict, basic_reset, basic_longkey, va1_cross_dict, va1_cross_delta, va1_three_seg, va2_modified_bytes, va2_extensions_kept, va2_untouched_preserved, va3_boundary_value, va3_ext_escaped, va3_reencode, va4_overlong_bytes, va4_len_reported, va4_modified_shortest, va5_magic_over_version, va5_version_over_reserved, va5_reserved_over_overflow, va5_overflow_over_crc, va5_version_field, heavy_decode_rejects, heavy_salvage_recovers, va6_single_records, va6_single_damage, va6_two_spans, va6_no_false_resync, compA_value, compA_len, compA_ext, compA_all. These are exactly the checks that execute decode.py/encode.py. test-stdout.txt shows only `reward: 0.1241` (no traceback; `_run` swallows the failure). The cause is the gate 03 TS-24 defect: as root the runner drops to `nobody` via setpriv, and `nobody` cannot read the 0600 temp input or write into the 0700 temp dir (probe in gate 03). The same checks score 145/145 against the same built programs when run as a non-root user (gate 05 scratch run). This is a real defect, not noise.

Nop: exactly 0.0, no check paid.

Stub solve.sh (STUB copy, in full):

```bash
#!/bin/bash
set -euo pipefail
P=/app/decode.py; mkdir -p "$(dirname "$P")"; : > "$P"
P=/app/encode.py; mkdir -p "$(dirname "$P")"; : > "$P"
P=/app/out/decoded_examples.jsonl; mkdir -p "$(dirname "$P")"; : > "$P"
P=/app/out/format_report.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/roundtrip_report.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/error_analysis.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
```

stub-1 scored (no retry needed). Non-zero checks: format_report_present (+1), roundtrip_report_present (+1), error_analysis_present (+1) = 3/145 = 2.07% of P, reward 0.0207. Judgement: healthy. The three checks that paid are existence/parse checks weighted 1, and their descriptions claim nothing more ("is present and parses as a JSON object"). No content check paid. Compared with the gate 05 CL-2 forgery price (12/145 = 8.3% on the test channel, from hand-written plausible artifacts paying va5_magic_over_version and report_roundtrip as well), the empty stub sits well below it. Those two content checks that a forgery can pay are carried under CL-2. The stub score covers the test channel only.

diff -rq bundle vs RUN copy:

```
Files .../environment/Dockerfile and .../run/.../environment/Dockerfile differ
Files .../task.toml and .../run/.../task.toml differ
Only in .../bundles/vendor-archive-roundtrip-recovery/tests: judge.toml
Files .../tests/reward.toml and .../run/.../tests/reward.toml differ
```

diff -rq bundle vs STUB copy:

```
Files .../environment/Dockerfile and .../stub/.../environment/Dockerfile differ
Only in .../bundles/vendor-archive-roundtrip-recovery/solution: TRUTH.md
Only in .../bundles/vendor-archive-roundtrip-recovery/solution: solve.py
Files .../solution/solve.sh and .../stub/.../solution/solve.sh differ
Files .../task.toml and .../stub/.../task.toml differ
Only in .../bundles/vendor-archive-roundtrip-recovery/tests: judge.toml
Files .../tests/reward.toml and .../stub/.../tests/reward.toml differ
```

Only allowed differences. Cleanup: deleted /tmp/oracle-qc/vendor-archive-roundtrip-recovery-20261021T2259 only (re-listed: gone). Bundle under review still has tests/judge.toml, its original tests/reward.toml, task.toml, environment/Dockerfile and solution/ (TRUTH.md, solve.py, solve.sh); `diff -rq` against the original bundle prints nothing (exit 0); `find` shows no __pycache__ in the bundle or the kit. Jobs and logs kept as evidence.

Findings (Step 10):

- ❌ Step 10 oracle All five oracle runs read 0.1241, not 1.000. Failing checks: the 33 listed above, every check that executes the agent's programs. Cause: tests/test_output.py L806-807 setpriv drop to nobody over root-owned 0600/0700 temp inputs (gate 03 TS-24). Bug/Error. Fix: in tests/test_output.py `_decode`/`_salvage` `os.chmod(path, 0o644)` after writing the temp segment, and in `_stream`/`_encode` `os.chmod(tmp, 0o777)` on each `mkdtemp()` dir (with the manifest/doc chmod 0o644), then re-run the whole gate.

