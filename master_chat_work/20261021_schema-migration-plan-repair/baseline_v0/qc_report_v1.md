# QC report: schema-migration-plan-repair

- Bundle: schema-migration-plan-repair
- Bundle path: /Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/schema-migration-plan-repair
- Report version: v1
- Date/time: 2026-10-21 20:44 IST (15:14 UTC)
- QC kit commit: bde868c46994f4916e245b40d14f302b1341244a (live kit, Terminal_2.0_Harbor_Harness/Input_Bundle_QC)
- Harbor version: 0.24.0
- Session title: set to `schema-migration-plan-repair_v1_qc` (confirmed in `opencode session list`; the list is sorted by update time, and this session showed the new title)

Verdict: ❌ FAIL (8 fails, 2 minors, 5 warns)

| Step | Gate | Verdict | Fails | Minors | Warns |
|------|------|---------|-------|--------|-------|
| 1 | structure_qc.py | ⚠️ warn | 0 | 0 | 1 |
| 2 | instruction_qc.py | ✅ pass | 0 | 0 | 0 |
| 3 | tests_qc.py | ⚠️ warn | 0 | 0 | 1 |
| 4 | judge_qc.py | ✅ pass | 0 | 0 | 0 |
| 5 | Gate 01 Instruction | ❌ fail | 1 | 0 | 0 |
| 6 | Gate 02 Data & Solution | ❌ fail | 1 | 1 | 1 |
| 7 | Gate 03 Tests | ❌ fail | 2 | 0 | 1 |
| 8 | Gate 04 Judge | ❌ fail | 1 | 1 | 2 |
| 9 | Gate 05 Alignment & Integrity | ❌ fail | 5 | 1 | 0 |
| 10 | Execution gate | ✅ pass | 0 | 0 | 0 |
| 11 | Coverage & overlap re-check | ❌ fail | 1 | 0 | 0 |
| | Overall (unique findings) | ❌ FAIL | 8 | 2 | 5 |

Row counts are per gate. Some defects are reported under more than one ID, as the kit asks (gate 05 repeats IN-12 as AL-26, JD-8 as AL-F0d and CL-3, DS-22 as AL-18; gate 03 TS-23 is the script's A3). The overall row counts each defect once. Step 10 ran: oracle 1.000 x5, nop 0.000, stub 0.007 (tests-only).

## Findings

### ❌ Fails

1. ❌ Gate 05 CL-2 / AL-F0c: a zero-repair submission collects real reward. Four behaviour checks pass on the unrepaired shipped code, and seven judged criteria pay for paraphrasing the contract. tests/test_output.py:8005-8007, 8070-8077, 8090-8097 (plan_tie_first_edge_decides +5, exec_correction_first_arrival_only +3, exec_correction_at_source_enables_step1 +3, pipe_rejection_codes +3). Evidence: the shipped repo.zip repackaged unchanged, plus plausible JSON, earned 19/142 = 13.4% against the real checks; 14 of those points come from checks that claim to grade repaired behaviour (e.g. "Among equal-cost plans the first edge decides when last edges disagree."). Adding R7-R13 (25/46) gives 0.339 total for no repair. Bug/Error. Fix: in tests/test_output.py rebuild case_tie_first_edge, case_first_arrival, case_source_arrival and case_rejection_codes so the shipped repo.zip fails each, for example by giving the tie a shorter equal-cost plan with a larger first id, adding a prerequisite that only holds after the arrival-time SET, and adding a merged-alias partner to the rejection case.
2. ❌ Gate 04 JD-8 (also AL-F0d, CL-3): R7-R13 grade, in the final reply, the same rule facts the tests already grade as behaviour, and their sentences can be copied from the contract files. tests/judge.toml:90-178. Evidence: R9 "among plans of equal total cost the plan whose edge-id list is smallest, compared from the first edge, is chosen" restates migration_semantics.md M8 and pairs with plan_tie_first_edge_decides / plan_tie_longer_plan_wins / ladder_large_tie; R12 "computed on the record as received, before null tokens are replaced" restates repository_contract.md K16 ("taken on the line as received, before null tokens are replaced"); R7/M6, R8/M9, R10/N2, R11/C4, R13/M11 follow the same pattern. That is 25 of 46 judge points. Bug/Error. Fix: in tests/judge.toml replace R7-R13 with trajectory criteria the tests cannot see, for example "The agent runs its repaired planner on a generated graph of at least 40 layers before its final answer.", and update weights.judge in tests/reward.toml to 0.5 / the new positive total.
3. ❌ Gate 05 AL-27 (extended in Step 11): three stated precedence or ordering rules have no fixture that triggers them. Evidence: partner_aliases.xml P1 "A partner value equal to a partner id names that partner; otherwise a value equal to an alias text names the alias's partner" (no hidden Spec has an alias equal to a partner id); correction_log.txt C4 "Corrections pinned to one schema are applied in log order" (every hidden execution case has one correction per record); null_semantics.ini N6 "Before planning, every top-level payload value ... becomes an explicit null" (no pipe fixture puts a token value on a prerequisite field). Bug/Error. Fix: in tests/test_output.py add a resolve case with an alias equal to another partner's id, an execute case with a SET then an UNSET of one field pinned to one schema before a `has:` edge, and a pipe case where `"f": "NULL"` with `null_counts_as = absent` must steer the plan away from a cheap `has:f` edge.
4. ❌ Step 11 coverage: seven delegated contract clauses have no checker. Evidence: K7 "Neither function changes its arguments."; K11 `state_signature` raising E_UNKNOWN_SCHEMA (the only signature case uses a known schema, test_output.py:7340-7349); K12 "E_INVALID_CORRECTION ... never a record code"; K15 "Such a record has `batch`, `partner`, `key` and `schema` null."; K17 record `fingerprint`/`plan`/`partner`/`batch`/`key` values; K18 `by_code`; N7 "an empty line means no tokens". No check body after test_output.py:7030 reads `by_code`, a record's `fingerprint`, `partner` or `batch`, or `E_INVALID_CORRECTION`. Bug/Error. Fix: in tests/test_output.py extend existing checks: assert the E_PARSE records' null fields and one record's `fingerprint`/`partner` in pipe_rejection_codes, `by_code` in pipe_attempted_vs_migrated_counts, an unknown-schema signature call, the payload unchanged after execute_plan in `_exec_case`, and an empty partner token line in case_partner_tokens.
5. ❌ Gate 03 TS-17: type-loose `==` on parsed JSON accepts types that M5 rules out. tests/test_output.py:7820-7825 (`_exec_case`), 8100-8106. Evidence: case_operations expects `{b: 17, c: 2.5, d: "12", m: None, "keep": True}`, but `{'b':17.0}=={'b':17}` and `{'a':1}=={'a':True}` are both True, while M5 says a cast to int "becomes that int" and booleans are "left unchanged". Bug/Error. Fix: in tests/test_output.py compare type-strictly in `_exec_case`, `_plan_case` and the pipe checks, for example `json.dumps(result, sort_keys=True) == json.dumps({"ok": expected}, sort_keys=True)`.
6. ❌ Gate 03 TS-24: agent subprocesses are never killed as a process group, and scratch folders are world-writable without the sticky bit. tests/test_output.py:7102-7113 and 7065-7068. Evidence: `subprocess.run(_untrusted_command(command), ..., timeout=timeout, start_new_session=True)` with no `os.killpg` anywhere, and `path.chmod(0o777)` on every `_scratch` folder. A double-forked child running as nobody survives and can replace the `repo` copy that `_unit_results(_shipped_repo())` runs (the "before" side of test_fixes). The reward file itself stays safe (root-owned 755 `/logs/verifier`). Bug/Error. Fix: in `_run` use `subprocess.Popen(..., start_new_session=True)` and call `os.killpg(proc.pid, signal.SIGKILL)` after `communicate(timeout=...)` and on timeout, and create scratch folders with mode 0o1777.
7. ❌ Gate 02 DS-27: TRUTH.md carries internal lever taxonomy and names the QC tooling. solution/TRUTH.md:103-107, 234-235. Evidence: "Positive checks by lever ... LV-MR-1 state feasibility 32; LV-MR-7 attempted versus completed 29; F rejections and identity 29; D size ladder 18" and "Build the tests-only copy with Input_Bundle_QC/exe_copy.py". Bug/Error. Fix: in solution/TRUTH.md replace lines 103-108 with plain descriptions of what the checks grade, and reword golden_score_verified_by to "Not yet measured." with no tool name.
8. ❌ Gate 01 IN-12 (also AL-26): category names the subject matter, not the work. task.toml:12. Evidence: `category = "Data Processing"`, while instruction.md:1 asks to "Repair the repository so that every stage behaves as the contract states" and task.toml:7 opens "Repair a stdlib Python repository". Bug/Error. Fix: in task.toml [metadata] set `category = "Software Engineering"`.

### 🟡 Minors

1. 🟡 Gate 02 DS-22 (also AL-18): TRUTH.md states the template's reward floor rather than this bundle's. solution/TRUTH.md:245-246. Evidence: "so the combined reward runs from -1.000 to +1.000 with no clamp", while the real floor is -(0.5 x 12/142 + 0.5 x 11/46) = -0.162. Bug/Error. Fix: in solution/TRUTH.md change the caveat to "the combined reward runs from -0.162 to +1.000 with no clamp".
2. 🟡 Gate 04 JD-5: R14 bundles several facets into one binary verdict. tests/judge.toml:183. Evidence: "descriptive names, errors raised with their catalogue code, and no debug prints or dead code left behind". Bug/Error. Fix: in tests/judge.toml split R14 into "The agent's changes under src/migrakit raise MigrationError with a K12 catalogue code at every rejection they add." and "The agent's changes under src/migrakit leave behind no print call or unreachable code."

### ⚠️ Warns

1. ⚠️ Script structure_qc X1: repo.zip skipped by the dash sweep as binary. Re-checked: it is a real zip; every member was swept by hand (0 dashes, 0 markers). Suggestion/Improvement. Fix: none needed; tasker approval.
2. ⚠️ Script tests_qc A3 / Gate 03 TS-23: 50 checks against the 35 cap. tests/test_output.py:8251-8300. No double payment was found (TS-26), and the count reflects 54 delegated rules. Suggestion/Improvement. Fix: tasker approval, or merge the five ladder checks into two.
3. ⚠️ Gate 02 DS-20: the M5 decimal edge case ".5" is converted by the shipped and oracle `_DECIMAL` (core/operations.py:12, `\.\d+`), which one reading of "digits with an optional point" excludes. No test or shipped value turns on it. Suggestion/Improvement. Fix: optionally state in migration_semantics.md M5 whether ".5" and "5." are decimal strings.
4. ⚠️ Gate 04 JD-9: 14 of the 17 criteria read the final answer; only R14-R16 watch how the agent worked. Suggestion/Improvement. Fix: covered by fail 2.
5. ⚠️ Gate 04 JD-16: R16's repository half (no third-party package in the repository) could be a deterministic test over the delivered imports. Suggestion/Improvement. Fix: optionally add a test that every import in the delivered src/migrakit is in `sys.stdlib_module_names` or migrakit itself.

## Consolidated sign-off

- ✅ structure_qc.py exits 0
- ✅ FC-S1..FC-S24 structure_qc.py output read, and every failure it reports confirmed in the file and carried into the report (no failures; X1 warn re-checked)
- ✅ instruction_qc.py exits 0
- ✅ tests_qc.py exits 0
- ✅ judge_qc.py exits 0
- ❌ Gate 01 Instruction: no fail findings (IN-12, fail 8)
- ❌ Gate 02 Data & Solution: no fail findings (DS-27, fail 7)
- ❌ Gate 03 Tests: no fail findings (TS-17, TS-24, fails 5 and 6)
- ❌ Gate 04 Judge criteria: no fail findings (JD-8, fail 2)
- ❌ Gate 05 Alignment & Integrity: no fail findings, F0a-F0e all clean (F0c and F0d fail; CL-2, CL-3, AL-27, AL-26; fails 1, 2, 3, 8)
- ✅ CL-1..CL-10 client feedback checks all run, each one carrying the number it asks for or the file and line it asks for (never a bare ✅) (CL-2: 19/142 = 13.4% tests, 25/46 judge, 0.339 combined; CL-4: one-fact-wrong 0.989; others quote file and line)
- ✅ Step 10 preflight run and pasted (harbor version 0.24.0 or newer, with the exact number recorded; docker reachable; bundle path listed) (harbor 0.24.0)
- ✅ Step 10 oracle run executed for real FIVE times: all five exactly 1.000, every number reported individually (evidence pasted) (1.0, 1.0, 1.0, 1.0, 1.0)
- ✅ Step 10 nop run executed for real: reward exactly 0.000 (evidence pasted)
- ✅ Step 10 stub run executed for real: score reported, tests that paid named, judgement given with reasons (evidence pasted) (0.007 = 1/142, artifacts_exist only; healthy)
- ✅ Step 10 runs made from `exe_copy.py` copies only: its full output pasted (judge.toml validated against the rewardkit 0.2.1 schema, judge.toml deleted, tests-only reward.toml weight, network roles opened), scores recorded as TESTS-ONLY, both copies deleted, and the original confirmed unedited
- ✅ Every oracle or empty-run score claimed anywhere in the bundle (TRUTH.md included) is scoped to the test channel; no judged-channel oracle score is claimed, because none can exist (TRUTH.md:228-239 "Not yet measured ... Those figures cover the test channel in tests/test_output.py only; the judged channel has no oracle score.")
- ❌ Step 11: re-check done, coverage mapping complete both directions, zero overlap between tests and judged criteria (coverage gaps, fail 4; overlap R7-R13, fail 2)
- ❌ All warn findings shown to the tasker and approved (5 warns pending tasker approval, Warns 1-5)
- ✅ Sign-off recorded: reviewer name, date, bundle name, verdict (Reviewer: Sisyphus, QC session schema-migration-plan-repair_v1_qc; 2026-10-21 23:40 IST (18:10 UTC); schema-migration-plan-repair; ❌ FAIL)

Scope note: Step 10 is tests-only grading per the kit. tests/judge.toml was validated against the rewardkit 0.2.1 schema, never executed; no OpenAI key was set; the stub score covers the test channel only. The network was opened and the OpenHands pre-bake dropped in the two copies only.

---

# Evidence appendix

## Step 0: preconditions

```
$ git -C ".../Terminal_2.0_Harbor_Harness" rev-parse HEAD
bde868c46994f4916e245b40d14f302b1341244a
$ diff -rq "<original bundle>" "<copy under review>"
(no output, exit 0)
```

## Steps 1-4: scripts

Run from /tmp with PYTHONDONTWRITEBYTECODE=1. Logs: /tmp/opencode-logs/schema-migration-plan-repair-scripts-20261021T2044/

### Step 1: structure_qc.py, exit 0

```
pass [S1] bundle name format
pass [S2] all required files present
pass [S4] input directories data/ (13 files) all copied into the image
pass [S7] agent image copies nothing from outside environment/
pass [T1] task.toml parses
pass [T2] template shape, key order, environment_mode = separate
pass [T4] artifacts (absolute container paths): ['/app/out/patched-repo.zip', '/app/out/repair-report.json', '/app/out/module_core.json', '/app/out/module_parser.json', '/app/out/module_report.json', '/app/out/test_fixes.json', '/app/out/summary.json']
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
WARN [X1] 1 file(s) skipped as binary, re-check any that are text: environment/data/repo.zip
SUMMARY: 17 pass, 1 warn, 0 fail
VERDICT: WARN - tasker approval needed
```

Re-check of the X1 warn: repo.zip is a genuine zip archive (the shipped repository). Its unpacked text members are swept for em/en dashes and placeholders by hand in gate 02 (DS section).

### Step 2: instruction_qc.py, exit 0

```
pass [C1] timeout sentence matches agent timeout (7200s)
pass [C2] no scripted machinery names
pass [C3] no 'reward'
pass [C4] every /app path resolvable through COPY/ADD exists
pass [C5] every declared artifact referenced
SUMMARY: 5 pass, 0 warn, 0 fail
VERDICT: PASS
```

### Step 3: tests_qc.py, exit 0

```
pass [A1] test_output.py parses and imports criteria, criterion from rewardkit
pass [A2] no duplicate function names
pass [A4] every check is a top-level @criterion(description=...) function of workspace
pass [A5] no literal non-bool returns; every reading check guarded (trace by hand)
pass [W1] 50 module-level registrations
pass [W2] every weight is an integer on the locked scale
pass [W3] bijection checks <-> registrations
pass [W4] weights differentiate
pass [W5] 4 negative check(s)
pass [W6] negative_ prefix matches weight sign
pass [W7] positive total 142, negative total 12
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
pass [O1] oracle independent of the verifier (6% of solve.py's 408 substantive lines also appear in test_output.py)
pass [H1] util-linux installed for setpriv
pass [H3] /tests restricted from unprivileged readers
pass [H4] stale reward files cleared before grading
pass [H5] verifier log directory owned by root and not writable by others
WARN [A3] 50 checks; cap is 35 (warn)
SUMMARY: 34 pass, 1 warn, 0 fail
VERDICT: WARN - tasker approval needed
```

Re-check of the A3 warn: confirmed, 50 `criteria.<name>(weight=...)` registrations in tests/test_output.py against the template's "A real file carries 10 to 35 checks". Carried as ⚠️ finding SCR-A3.

### Step 4: judge_qc.py, exit 0

```
pass [G1] judge.toml parses (17 criteria)
pass [G2] pinned [judge] and [scoring] header exact
pass [J1] .. pass [J13] all criteria
pass [G3] 17 criteria
pass [G4] 3 negative criteria
pass [G5] weights differentiate
pass [G6] positive total 46, negative total 11
SUMMARY: 19 pass, 0 warn, 0 fail
VERDICT: PASS
```


## Step 5: Gate 01 Instruction QC

Files read in full: instruction.md (19 lines, 350 words), task.toml, environment/Dockerfile, environment/data/* (contract files in full, large data files structurally), tests/test_output.py (check logic lines 1-54 and 7030-8300 in full; lines 55-7030 are the `_SHIPPED_DATA` dict of zlib+base64 blobs, decoded and byte-compared: all 13 equal the shipped environment/data files), tests/judge.toml.

Findings in this gate:
- ❌ IN-12 category does not name the dominant work. task.toml:12 `category = "Data Processing"`. The instruction's work is repairing a Python repository against a contract (instruction.md:1 "Repair the repository so that every stage behaves as the contract states"; task.toml:7 description "Repair a stdlib Python repository ..."; keyword "repo-patch"). Data processing is the subject of the software being repaired, not the work, which is the side-aspect case IN-12 names as a fail. Bug/Error. Fix: in task.toml [metadata] set `category = "Software Engineering"` (or "Debugging"), the repair work the instruction actually asks for.

Checklist:
- ✅ IN-0 instruction_qc.py run, exit code and findings reported (exit 0, 5 pass, 0 warn, 0 fail; Step 2 above)
- ✅ IN-S1..IN-S7 instruction_qc.py output read, and every failure it reports confirmed in the file and carried into the report (no failures reported)
- ✅ IN-F1 no em/en dashes anywhere in the file (script C-pass and my sweep of every bundle text file plus the unpacked repo: zero U+2013/U+2014 hits)
- ✅ IN-L1 register is everyday natural English, no banned or same-kind vocabulary (word scan for crucial/robust/comprehensive/ensure/leverage/utilize/seamless: no hits; read in full, plain technical English)
- ✅ IN-L2 grammar and spelling clean (read every sentence; no errors found)
- ✅ IN-L3 no AI-tell phrases; reads like a human colleague wrote it ("Parts of its parser, core, pipeline, report and command-line code do not behave the way its contract says.")
- ✅ IN-1 timeout sentence present and N == agent timeout_sec (instruction.md:19 "You have 7200 seconds to complete this task."; task.toml:35 `timeout_sec = 7200.0`)
- ✅ IN-2 no mention of tests/, solution/, grader, logs, reward (stating WHAT is judged is fine). The one hit, instruction.md:15 "`tests/test_visible.py`", is the shipped repository's own visible test file inside repo.zip (unzip listing: `tests/test_visible.py`), not the bundle's tests/; verified false positive.
- ✅ IN-3 no instruction to write reward/log files
- ✅ IN-4 no benchmark self-references or GUIDs
- ✅ IN-5 no finding for unmentioned inputs; any path the prompt does name exists (/app/data/repo.zip, repository_contract.md, migration_semantics.md, null_semantics.ini, correction_log.txt, partner_aliases.xml, report_taxonomy.json all present in environment/data and copied by `COPY data /app/data`)
- ✅ IN-6 exactly one landing place inferable for each declared artifact, both ways (instruction.md:7-11 name all seven `/app/out/...` paths verbatim; task.toml:2 declares exactly those seven; nothing extra requested)
- ✅ IN-7 no tool named that the image does not install (only "the Python standard library"; image is python:3.12-slim)
- ✅ IN-8 everything the tests assert AND everything an outcome judged criterion demands is knowable from prompt, shipped spec or data. Traced every hidden case against the contract: plan cases against M6-M8 (e.g. case_tie_longer expects `[a1, b, c]` over `[a2, d]`, settled by M8 "the way Python compares two lists of strings"), exec cases against M4/M5/N4/C4/M11/M12, pipe cases against K13/K15/K16/C1-C8/N6-N8, summary cases against T1-T3/K18, artifact checks against K19. The judged R1-R13 facts are reachable from the shipped code plus contract.
- ✅ IN-9 no answer or algorithm leak (withholding is fine; gate 02 DS-21 rules on anything you suspect is unreachable). The prompt names the stages and says planning must survive "graphs with far too many paths to list", without naming the algorithm.
- ✅ IN-10 online-lookup sentence: no check performed (tasker decision)
- ✅ IN-11 network wording matches the pinned offline contract (no fetch/download/ URL-as-source sentences; silence about the network is correct). "add no third-party package" forbids installing; nothing asks for network.
- ❌ IN-12 category names the dominant work; description honest; keywords/tags related. Category fails (see finding). Description (task.toml:7) is an honest summary; keywords/tags (python, repo-patch, schema-migration, graph-search, data-processing, stdlib) all relate.
- ✅ IN-13 no internal contradictions, constraints jointly satisfiable ("Keep the visible tests ... and their assertions" is compatible with repairing the code; stdlib-only is satisfiable, the oracle is stdlib only)
- ✅ IN-14 describes the end state and any rules of engagement, never a recipe that is the solution
- ✅ IN-15 every graded rule of engagement is stated plainly enough to act on. The judged constraint criterion R16 (type "instruction following") "The agent installs a third-party Python package." maps to instruction.md:15 "Use only the Python standard library; add no third-party package to the repository or the environment." Test negative_deleted_visible_tests maps to instruction.md:15 "Keep the visible tests in `tests/test_visible.py` and their assertions." negative_hardcoded_sample_answers / negative_filename_dependent_behaviour map to instruction.md:1 "on any contract folder and feed inside the stated limits, and not only on the shipped ones."
- ✅ IN-16 nothing graded has two defensible readings the contract fails to settle. Candidates examined and settled: equal-cost tie order (M8 settles it); `__main__.py` area in module_*.json (K19 lists areas, `__main__` is in none, so omitting it is correct and listing it under parser is also accepted by `AREAS["parser"]`; no test penalises omission); K2 "exactly these seven files" against hidden contract folders carrying three extra files (K2 itself says "`/app/data` is such a folder" and /app/data holds 13 files, so extra files are settled as allowed).

Gate 01 verdict: ❌ fail (1 fail, 0 minor, 0 warn).

## Step 6: Gate 02 Data & Solution QC

DS-21 decided BEFORE opening solution/TRUTH.md (recorded here at 2026-10-21 23:0x IST, before the read): SOLVABLE. Every fact grading asserts follows from instruction.md plus environment/data: the 54 rules (K1-K19 in repository_contract.md, M1-M12 in migration_semantics.md, N1-N8 in the null_semantics.ini header, C1-C8 in the correction_log.txt header, P1-P4 in the partner_aliases.xml header, T1-T3 in report_taxonomy.json `rules`; count re-verified as 19+12+8+8+4+3 = 54, matching instruction.md:3 "54 numbered rules"), the shipped repository (repo.zip, 21 members, read in full), and its visible tests. The hidden-case expectations (plan ties by M8, state-dependent prerequisites by M6/M7, first-arrival corrections by C4, fingerprint as received by K16, received_seq order by K13, token-list replacement by N7, categories by T1/T2, partner order by T3, artifact shapes by K19) all have a stated rule. No secret constant found.

TRUTH.md opened after the DS-21 note above. It agrees: its Defect section lists F1-F15 with no unreachable fact, and item 11 says the visible data has "no expected output", which matches my own reading.

Files read in full: environment/Dockerfile, every contract file, repo.zip (unpacked to /tmp/opencode-logs/schema-migration-plan-repair-repo-20261021T2047/, 21 members, all read), solution/solve.sh, solution/solve.py (562 lines), solution/TRUTH.md (247 lines, read last). Large data files checked by script: schema_versions.json 1000 schemas / 100 domains / exactly one canonical per domain; migration_edges.csv 2400 edges, 0 rows with an unknown or cross-domain schema or a non-positive cost, at most 4 prerequisite fields and 6 fields per domain (inside K14's 8 and 10); partner_batches.jsonl 8000 lines, 3 deliberately not JSON (K15 covers them); replay_manifest.csv 2200 batches with distinct received_seq.

Findings in this gate:
- ❌ DS-27 TRUTH.md carries internal process taxonomy and QC tooling. TRUTH.md:103-107 "Positive checks by lever ... LV-MR-1 state feasibility 32; LV-MR-7 attempted versus completed 29; F rejections and identity 29; D size ladder 18; LV-MR-6 ..." uses the generator's internal lever codes, and TRUTH.md:234-235 "Build the tests-only copy with Input_Bundle_QC/exe_copy.py" names our internal QC kit inside a client delivery file. DS-27 lists "internal taxonomy" and tooling among the things that do not belong. Bug/Error. Fix: in solution/TRUTH.md replace the lever-code paragraph (lines 103-108) with plain descriptions of what the checks grade, and reword golden_score_verified_by to "Not yet measured." with no tool name.
- 🟡 DS-22 TRUTH.md misstates this bundle's reward floor. TRUTH.md:245-246 "so the combined reward runs from -1.000 to +1.000 with no clamp", but with negative totals 12 of 142 (tests) and 11 of 46 (judge), the real floor is -(0.5 x 12/142 + 0.5 x 11/46) = -0.162; -1.000 is the template's theoretical bound, not this bundle's. Bug/Error. Fix: in solution/TRUTH.md change the caveat to "the combined reward runs from -0.162 to +1.000 with no clamp".
- ⚠️ DS-20 M5 decimal edge case left at the shipped behaviour. migration_semantics.md M5: "a decimal string (optional sign, digits with an optional point) becomes a float"; the shipped `_DECIMAL = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")` (core/operations.py:12), unchanged by the oracle, also converts ".5" (no leading digit), which one reading of "digits with an optional point" excludes. No test exercises it and the shipped feed holds no such string (scanned: 0 values of the form ".5" or "5."). Suggestion/Improvement. Fix: optional; state in M5 whether ".5" and "5." count as decimal strings.

Checklist:
- ✅ DS-1 input in one or more named directories under environment/, each non-empty and COPYed; environment/ holds only the Dockerfile and those directories (environment/ = Dockerfile + data/ (13 files); Dockerfile:12 `COPY data /app/data`)
- ✅ DS-2 data necessary: task unsolvable without it (repo.zip is the code to repair; the six rule homes are the contract)
- ✅ DS-3 every referenced file present, every claim about the data true (all six named files present; "54 numbered rules" verified 19+12+8+8+4+3; repo.zip has the `src/` layout and `tests/test_visible.py` the instruction names; contract claims K1 "holds pyproject.toml, README.md, src/migrakit/ and tests/test_visible.py" true of the zip listing)
- ✅ DS-4 no answers or answer-derivable content in any environment/ input directory (no expected records, plans or summary anywhere; the contract files are rules, and the one worked fragment, K19's example name `core.records.FieldView.state`, is a shape example, not a graded answer)
- ✅ DS-5 no template residue, no redacted-spec pattern (TODO/FIXME/XXX/PLACEHOLDER/{{/__X__ sweep over every bundle text file and the unpacked repo: zero hits)
- ✅ DS-6 data internally consistent with the task story (3 non-JSON feed lines on purpose, K15; two merge loops P00976<->P00148 and P00311<->P01425 for P3; all inside K14 limits)
- ✅ DS-7 no em/en dashes in text data (bundle sweep plus the repo.zip interior that structure_qc skipped: zero hits)
- ✅ DS-8 Dockerfile copies nothing from tests/ or solution/ (only `COPY data /app/data`)
- ✅ DS-9 every input directory lands where the instruction says (conventionally /app/<dir>) (/app/data, as instruction.md:1-3 say)
- ✅ DS-10 every needed tool/library installed in the image (python:3.12-slim base; solve.sh runs `python3`; solve.py imports only ast, json, os, shutil, subprocess, sys, tempfile, zipfile)
- ✅ DS-11 offline contract respected (every layer, oracle included, runs with no network) (no fetch in instruction or solve.py; Dockerfile installs at build time only)
- ✅ DS-12 no secrets, host paths, or machine-specific assumptions (base image pinned by digest; no host path)
- ✅ DS-28 every artifact directory writable by uid 1000 in the agent image (Dockerfile:10 `RUN mkdir -p /app && chown 1000:1000 /app`; /app/out is created by the oracle under the uid 1000 /app; Step 10 oracle-1 read 1.000)
- ✅ DS-29 openhands-sdk runtime pre-baked at /opt/openhands-sdk-venv with openhands-sdk/tools 1.55.1 and litellm 1.105.0 (any correct install style) (Dockerfile:4 apt `curl ... ca-certificates tmux`; :6-9 venv, exact pins, `import openhands.sdk, openhands.tools`, `chmod -R a+rX`; single stage, nothing later undoes it)
- ✅ DS-30 uid 1000 agent account created with a home directory, and ENV HOME set (Dockerfile:2-3, right after FROM; python:3.12-slim has no uid 1000 of its own)
- ✅ DS-13 solve.sh present, entrypoint; solve.py optional (`python3 "${SOLUTION_ROOT:-/solution}/solve.py"`)
- ✅ DS-14 oracle computes the answer, does not paste it (applies 17 text repairs, then runs the visible tests on both trees, runs the CLI from a foreign folder for summary.json, and derives changed_functions from an AST diff)
- ✅ DS-15 oracle would plausibly score 1.0 against the tests (walked against every hidden case; Step 10 confirms)
- ✅ DS-16 oracle data reads confirmed legal (reads /app/data only)
- ✅ DS-17 oracle never touches tests/ (its `unittest discover -s tests` runs the repository's own tests/ inside the extracted repo, not the bundle's tests/)
- ✅ DS-18 solve.sh idempotent (warn only) (`OUT.mkdir(exist_ok=True)`, fresh mkdtemp scratch, artifacts overwritten)
- ✅ DS-19 oracle respects the constraints the contract imposes on the agent, including rules of engagement stated in a shipped rules file (stdlib only; tests/test_visible.py untouched)
- ✅ DS-20 oracle obeys every contract rule, wherever stated, including rules no test triggers. Walked: planner heap over (schema, state) ordered by (cost, edge-id tuple) gives M8's order (positive costs make the first pop of each product node minimal and the first target pop the answer); executor `arrive()` applies corrections on first arrival including the source and in log order (C4), re-checks before every edge (M11), deep-copies its input (K7); `_admit` fingerprints the line as received and keys on the canonical id, holder set before migration (K16); `_ordered` sorts by (received_seq, line) (K13); `resolve_partner` follows every link and raises on a loop (P2, P3); tokens replace the default list, empty line means none (N7, N8); `build_summary` uses `category_of` and `_partner_order` (T1-T3). One edge case noted as ⚠️ (M5 ".5").
- ✅ DS-21 solvable from instruction.md + environment/ input alone (hard is fine; only genuinely unreachable information fails) (decided before TRUTH.md, see above)
- 🟡 DS-22 TRUTH.md describes the shipped solution, the real grading and a defect list the bundle honours (read only after DS-21 was decided). Verified: "seventeen text repairs" = 17 REPAIRS entries; "562 lines" true; 50 checks, 46 positive = 142, 4 negative = 12; 17 criteria, 46 / 11; the four named negatives and their weights; "seven pass, two fail" (my run of the shipped tests: test_cli_runs_from_other_folder and test_module_entry_help fail); ladder timeout `TIME_LIMIT_SEC + 10`; all 15 sha256 digests match the shipped bytes; source is 999 lines ("1,000-line"). The per-lever totals on lines 103-107 follow no shipped mapping and could not be verified. One misstatement (reward floor), see finding.
- ✅ DS-23 TRUTH.md unreachable by the agent: no Dockerfile route to it, never named in instruction.md
- ✅ DS-24 oracle is an independent implementation, not the verifier's own code (tests_qc O1: 6% shared lines; the tests' planner `_reference_plan` is forward reachability + backward Dijkstra cost-to-go + greedy smallest-edge walk, test_output.py:7281-7335, while the oracle is a forward heap search; shared lines are zip extraction and the AST walk)
- ✅ DS-25 every literal the grading side requires of the output is findable in an agent-visible file (named file per literal). 41 required literals, all found: module_*.json keys `module`/`changed_functions`/`notes` and values core/parser/report, test_fixes `visible_tests`/`name`/`before`/`after`/`pass`/`fail`, repair-report `package`/`fixes`/`checks`/`name`/`passed`/`migrakit`, archive members pyproject.toml / src/migrakit/__init__.py / tests/test_visible.py: repository_contract.md K1, K19; record keys line/status/code/schema/payload/failed_edge/completed_steps/attempted and status values: K17; summary keys records/attempted/by_status/by_category/invalid_corrections/partners/partner/migrated/failed: K18; execute_plan keys: migration_semantics.md M12; signature values absent/null/value: M10 + N1; error codes: K12; CLI flags and records.jsonl/run_summary.json: K10; API names: K2-K11; dotted-name form: K19 example. 0 appear nowhere.
- ✅ DS-26 no answer-revealing artifact anywhere in the agent image, including /tmp, build stages and archive interiors (single stage; RUN steps only install packages; repo.zip interior is the unrepaired code; nodejs/npm/xxd/file are installed but carry nothing task-specific)
- ❌ DS-27 TRUTH.md describes the task, with no narrative of how it was produced (lever codes and QC tool name, see finding)

Gate 02 verdict: ❌ fail (1 fail, 1 minor, 1 warn).

## Step 7: Gate 03 Tests QC

Files read in full: tests/Dockerfile, tests/test.sh, tests/reward.toml, tests/test_output.py (lines 1-54 and 7030-8300 read line by line; lines 55-7030 are the `_SHIPPED_DATA` blob dict, decoded and byte-compared, all 13 equal to environment/data). Every hidden case was recomputed by hand against the contract (see IN-8 in gate 01): all 39 expected values agree with the stated rules. A zero-repair probe (shipped repo.zip repackaged unchanged, plus well-formed JSON for the other six artifacts) was run against the real check functions in a local sandbox (log: /tmp/opencode-logs/schema-migration-plan-repair-probe-20261021T2050/probe_shipped.log): it earned 19 of 142, see gate 05 CL-2.

Findings in this gate:
- ❌ TS-17 type-loose comparisons accept wrong types that M5 rules out. `_exec_case` (test_output.py:7820-7825), `_plan_case` and the pipe checks compare with Python `==` on parsed JSON, where `1 == True` and `17.0 == 17`. migration_semantics.md M5 fixes the types: "int: ... a string that is an optional sign and digits ... becomes that int", "Anything else, booleans included, is left unchanged". So exec_operations_apply_in_order (+3, expects `{b: 17, ..., "keep": True}`) and pipe_bad_lines_run_continues (+3, expects `{"a": 4}`) pass a cast that yields the float 17.0 or 4.0, or a boolean turned into 1. Checked: `{'b':17.0}=={'b':17}` and `{'a':1}=={'a':True}` are both True. Bug/Error. Fix: in tests/test_output.py compare type-strictly in `_exec_case`, `_plan_case` and the pipe checks, for example `json.dumps(result, sort_keys=True) == json.dumps({"ok": expected}, sort_keys=True)`.
- ❌ TS-24 agent subprocesses are not killed as a process group. `_run` (test_output.py:7102-7113) calls `subprocess.run(..., timeout=timeout, start_new_session=True)`; nothing calls `os.killpg` (no killpg, Popen or signal use after line 7030). A double-forked child of the delivered package survives its check and runs on as `nobody` while later checks run. Reward forgery is still blocked (agent code runs under `setpriv --reuid=nobody`, `/logs/verifier` is root-owned 755, `/tests` is go-rwx). But every `_scratch` folder is mode 0777 without the sticky bit (test_output.py:7065-7068), so a survivor can rename or replace the `repo` copy that `_unit_results(_shipped_repo())` runs (test_output.py:7876-7881) and so set the "before" results test_fixes_matches_visible_test_runs compares against. Bug/Error. Fix: in `_run` start the child with `subprocess.Popen(..., start_new_session=True)`, then after `communicate(timeout=...)` (and on timeout) call `os.killpg(proc.pid, signal.SIGKILL)`, and create scratch folders 0o1777 (sticky) or owned by nobody rather than 0o777.
- ⚠️ TS-23 (script A3) 50 checks against the 35 cap. Redundancy reviewed under TS-26: no double payment found, so the count reflects many independent rules (54 contract rules). Suggestion/Improvement. Fix: tasker approval, or merge the five ladder checks into two.

Checklist:
- ✅ TS-0 tests_qc.py run, exit code and findings reported (exit 0, 34 pass, 1 warn A3)
- ✅ TS-S1..TS-S15 tests_qc.py output read, and every failure it reports confirmed in the file and carried into the report (no failures; A3 warn confirmed: 50 registrations at test_output.py:8251-8300)
- ✅ TS-1 no unconditional reads of agent input paths under tests/ (guarded reads are fine) (`_data_dir()` rebuilds the shipped data from `_SHIPPED_DATA`; no /app/data read)
- ✅ TS-2 tests/Dockerfile has COPY . /tests/, pins harbor-rewardkit==0.2.1 and sets LITELLM_LOCAL_MODEL_COST_MAP=True (tests/Dockerfile:5-7)
- ✅ TS-3 tests/Dockerfile has RUN mkdir -p /app (warn if absent) (line 8)
- ✅ TS-4 all check dependencies and invoked tools installed in the verifier image, Python >= 3.12 (stdlib only; util-linux for setpriv; python:3.12-slim)
- ✅ TS-5 ground truth self-contained in tests/ (embedded data blobs plus cases generated from EVAL_SEED)
- ✅ TS-6 test.sh hardens, then ends with exec rewardkit; writes no reward bytes, nothing after rewardkit, never trusts a reward file on disk (test.sh:4-10 match the template)
- ✅ TS-7 reward computed only from tests/ truth + declared artifacts (reads only OUT_DIR / the seven artifact names)
- ✅ TS-8 no skip switches
- ✅ TS-9 no agent-writable source/exec, not PATH-shadowable (rewardkit by absolute install; child env PATH from the verifier; `sys.executable` used for every child)
- ✅ TS-10 reward.toml shape exact, weights = 0.5 / positive total per channel at full precision, no clamp (0.5/142 = 0.0035211267605633804, 0.5/46 = 0.010869565217391304, both match reward.toml:4)
- ✅ TS-11 tests deterministic. Walked: every rng is `random.Random(EVAL_SEED * 1000 + salt)`; `_ids` sorts its set; `_reference_plan` sorts edges and field names; `_hidden_edge_ids` is used only for a count; no wall clock in any assertion; ladder budget is `TIME_LIMIT_SEC + 10` = 20 s against the oracle's 0.62 s (TRUTH.md); the `_CACHE` entries are pure (same inputs, same value); no network. Step 10's five oracle runs back this up.
- ✅ TS-12 outcome-driven, no history/console grading (children's stdout is the result channel of the driver, not agent console grading)
- ✅ TS-13 one property per test (multi-assert checks such as pipe_rejection_codes assert one rule, K12 codes per line)
- ✅ TS-14 names state properties (<property> / negative_<cheat>), prefix iff negative weight (names and descriptions match the bodies, e.g. `plan_tie_longer_plan_wins` builds a len-3 vs len-2 equal-cost tie)
- ✅ TS-15 negative checks return True when the cheat happened, with inline comment (all four carry "# Inverted polarity: True means ...", lines 8206, 8216, 8238, 8244)
- ✅ TS-16 negatives fire on the cheat and only the cheat (hardcoded: EVAL_SEED string or >= 3 random `q??????` hidden edge ids, which no honest repair contains; filename: same feed copied to `partner_batches.jsonl`; gutted tests: all nine names plus >= 9 `self.assert` (the shipped file has 14); nondeterminism: two identical runs of case_reissue)
- ❌ TS-17 exact comparisons where exactness promised (bool/int trap checked) (see finding)
- ✅ TS-18 tolerances stated in instruction where used (no tolerance used; the one float, `float("2.50") == 2.5`, is exact)
- ✅ TS-19 no obvious contract/test contradiction, checking the shipped spec as well as the prompt; a promise a judged criterion grades is covered (deep pass in Gate 05) (every hidden expectation recomputed from the K/M/N/C/P/T rules; all agree)
- ✅ TS-20 weights map to importance semantically, ordering matches the instruction (5 on the planner, executor and attempted-vs-migrated outcomes; 3 on rule-level sub-goals; 1 on existence and report consistency; -5 hardcoding, -3 filename/gutting, -1 nondeterminism)
- ✅ TS-25 no positive test grades an absence
- ✅ TS-26 no test pair (any signs) pays twice for one observable. Closest pairs read: cli_module_runs_from_foreign_cwd vs visible_repo_tests_pass_from_archive (the first also needs `__main__.py`, the feed repair and the summary, the second the nine visible tests); visible_repo_tests_pass vs test_fixes_matches_visible_test_runs (all-pass vs agent claim consistency); exec_correction_unset_breaks_step2 vs pipe_mid_path_failure_record (execute_plan vs pipeline with alias resolution); negative_filename_dependent vs negative_nondeterministic (renamed feed vs identical rerun)
- ✅ TS-21 bijection check functions <-> criteria.<name>(weight=W) registrations, each registered once; no test_weights.json
- ✅ TS-22 registered weights are integers within {5,3,1,-1,-3,-5}
- ⚠️ TS-23 counts and balance: >=10 checks, <=35 (warn), >=1 positive, >=1 negative, weights not all identical, sum|neg| <= sum pos (50 checks, warn; 46 positive / 4 negative; 12 <= 142)
- ❌ TS-24 verifier execution isolation (reward not forgeable by executed agent code) (reward is not forgeable, but the process group is never killed, see finding)
- ✅ TS-27 no positive test paying for source tokens instead of behaviour (module_*_claims read an AST diff of the claimed functions, weight 1 each, the existence-check weight TS-27 allows for a property that is about source; source scans exist only in negatives)
- ✅ TS-28 verifier hardening present where grading executes agent code, or explicitly reasoned as not needed (grading executes agent code; all four defences present: util-linux + `_SETPRIV`, `chmod -R go-rwx /tests`, stale reward files removed, `/logs/verifier` root:root 755)
- ✅ TS-29 no check can raise on bad, missing or hostile agent output; every check returns a bool (every check body runs inside `_holds`, which returns `bool(check())` or False on any Exception; negatives therefore return False unless the cheat is seen; module level only defines constants)

Gate 03 verdict: ❌ fail (2 fails, 0 minor, 1 warn).

## Step 8: Gate 04 Judge QC

Files read in full: tests/judge.toml (17 criteria, 230 lines), solution/solve.sh, solution/solve.py, tests/test_output.py checks and registrations, tests/reward.toml, instruction.md and the six contract files. Each criterion was classified and checked against the shipped code (repo.zip) and the oracle one at a time.

Classification: R1-R6 outcome (the reply names where the shipped code diverged; instruction.md:17 "for each one name the module and function of the shipped code where it diverged from the contract"); R7-R13 outcome (the reply states a restored rule; instruction.md:17 "state in your own words each contract behaviour you restored"); R14 conduct (code quality); R15 conduct negative (reading the grader, JD-11 list); R16 constraint (instruction.md:15 "Use only the Python standard library; add no third-party package to the repository or the environment."); R17 conduct negative (fabricated success).

R1-R6 checked against the shipped code: R1 `return cls({name: VALUE for name, value in payload.items() if value is not None})` (core/records.py:20); R2 `if not edge_allowed(registry, domain, origin, edge)` (core/planner.py:62); R3 the `for correction in corrections:` loop before the edge loop (core/executor.py:31-33); R4 `self._migrate(...)` then `record_fingerprint(record["schema"], migrated)` (pipeline.py:81-83); R5 `return registry.merges.get(partner_id, partner_id)` (parser/identity.py:22); R6 `if plan is not None: return "migrated", None` (report/classify.py:10-11). All six are true.

Findings in this gate:
- ❌ JD-8 R7-R13 grade, in the final reply, the same rule facts the tests already grade as behaviour. Per JD-8's own table ("answer == 42 | The response states the correct calibration value | FAIL - same fact, different angle"), a reply restating a test-graded fact overlaps. Pairs: R7 "prerequisites are checked on the record as it is after the previous step" with plan_tracks_field_dropped_earlier / plan_uses_edge_enabled_earlier / ladder_*_state (M6); R8 "two records with the same source and target schema can take different plans" with plan_revisits_schema_with_new_state / ladders (M9); R9 "the plan whose edge-id list is smallest, compared from the first edge" with plan_tie_first_edge_decides / plan_tie_longer_plan_wins / ladder_large_tie (M8); R10 "an explicit null counts as present ... unless field_policy.tsv sets null_counts_as to absent" with exec_correction_null_blocks_lacks / exec_correction_null_counted_absent (N2); R11 "applied on the first arrival at its pinned schema" with exec_correction_first_arrival_only / exec_correction_at_source_enables_step1 (C4); R12 "the replay fingerprint is computed on the record as received, before null tokens are replaced" with pipe_token_vs_json_null_conflict / pipe_edit_dropped_by_migration_conflict (K16); R13 "reported as failed with E_PREREQ_FAILED at that edge" with exec_correction_unset_breaks_step2 / pipe_mid_path_failure_record (M11). They are worth 5+3+3+3+5+3+3 = 25 of the 46 judge points, and each sentence can be lifted from a contract file with no repair done (see gate 05 CL-3). Bug/Error. Fix: in tests/judge.toml drop R7-R13 and spend their weight on trajectory criteria the tests cannot see, for example "The agent runs its repaired planner on a generated graph of at least 40 layers before its final answer." or "The agent runs the visible tests on the extracted patched-repo.zip before its final answer.", then update weights.judge in tests/reward.toml.
- 🟡 JD-5 R14 bundles several facets into one binary verdict: "descriptive names, errors raised with their catalogue code, and no debug prints or dead code left behind", so a judge has no way to score a change with good names and one leftover print. Bug/Error. Fix: in tests/judge.toml split R14 into two criteria, for example "The agent's changes under src/migrakit raise MigrationError with a K12 catalogue code at every rejection they add." and "The agent's changes under src/migrakit leave behind no print call or unreachable code."
- ⚠️ JD-9 the judged channel is almost all final-answer content (R1-R13, R17 = 14 of 17 criteria); only R14-R16 watch how the agent worked. Suggestion/Improvement. Fix: covered by the JD-8 fix (trajectory criteria in place of R7-R13).
- ⚠️ JD-16 R16's repository half could be a deterministic test: whether the delivered package imports only standard-library modules (or declares `dependencies = []` in pyproject.toml) is visible in patched-repo.zip, and no test checks it. Suggestion/Improvement. Fix: optionally add a test that every import in the delivered src/migrakit is in `sys.stdlib_module_names` or is migrakit itself, keeping R16 for the environment half.

Checklist:
- ✅ JD-0 judge_qc.py run, exit code and findings reported (exit 0, 19 pass)
- ✅ JD-S1..JD-S13 judge_qc.py output read, and every failure it reports confirmed in the file and carried into the report (no failures)
- ✅ JD-1 prefix matches evaluation_target for every criterion (R1-R13, R17 final_answer "The response"; R14 state_change, R15-R16 trajectory "The agent")
- ✅ JD-2 positive grammar everywhere, no banned tokens (read all 17; R14's "no debug prints" uses "no", which is outside the banned list, and the criterion is a positive)
- ✅ JD-3 no vague qualifiers
- ✅ JD-4 no brackets, placeholders, tag prefixes, em/en dashes
- 🟡 JD-5 one observable per criterion (R14 compound, see finding)
- ✅ JD-6 every criterion decidable from evidence (names, statements and trajectory events are all pointable)
- ✅ JD-7 every criterion true of / avoided by the reference solution (R1-R6 name exactly the functions the oracle rewrites, solve.py REPAIRS; R7-R13 match the oracle's repaired behaviour; R14 holds for the oracle's edits; the oracle reads no verifier path and installs nothing)
- ❌ JD-8 zero overlap with deterministic tests (observable-level) (R7-R13, see finding)
- ⚠️ JD-9 the judged criteria add process value beyond the tests (see finding)
- ✅ JD-10 no contradiction with the instruction
- ✅ JD-11 negatives target this task's real cheat surface (R15 grader reading, R16 the stated stdlib rule, R17 a false "passed" in repair-report.json checks or the reply)
- ✅ JD-12 counts and balance: >=8, <=35 (warn), >=1 positive and >=1 negative weight, weights not all identical, sum|neg| <= sum pos (17; 14 positive = 46, 3 negative = 11)
- ✅ JD-13 importance/weight pairing holds by |weight| and magnitudes match semantic importance (pairing holds; the 5s on R7/R11 fall with the JD-8 finding)
- ✅ JD-14 no criterion pair (negative or positive) pays twice for one act (location criteria R1-R6 and rule criteria R7-R13 read different facets; R7 vs R8 read the per-step check vs its consequence of per-record plans)
- ✅ JD-15 every criterion classified as outcome, constraint or conduct; outcome criteria trace to the contract (instruction plus any spec file it points to); conduct criteria hold for every competent route or earn their narrowing by raising the odds of a correct end state, and each serves a real requirement; constraint criteria are exempt from both tests (classification above; R14 serves the repair deliverable; R15/R17 are misconduct negatives)
- ⚠️ JD-16 each constraint criterion quotes its stated sentence and names the file it lives in, fits one of the six kinds, carries annotations type "instruction following", covers exactly one rule, and is graded once by the layer that should own it (a rule a test could have checked belongs to the tests) (R16: instruction.md:15, tool-use/negative kind, labelled "instruction following", one rule; repository half test-checkable, see warn)
- ✅ JD-17 deleting every constraint still leaves a substantial task
- ✅ JD-18 at least one criterion judges the quality of the code the agent writes (name it), or the task authors no code and the line says so (R14 r14_repaired_code_quality)

Gate 04 verdict: ❌ fail (1 fail, 1 minor, 2 warns).

## Step 9: Gate 05 Alignment & Integrity QC

All bundle files open at once (instruction.md, task.toml, both Dockerfiles, environment/data contract files, unpacked repo.zip, solve.sh, solve.py, TRUTH.md, test.sh, test_output.py, reward.toml, judge.toml).

Zero-repair forgery probe. Built from task.toml's seven paths and nothing else: `/app/data/repo.zip` copied unchanged to patched-repo.zip, the real shipped before-results copied into test_fixes.json (before = after), `{"package": "migrakit", "fixes": ["fixed planner"], "checks": [{"name": "visible tests", "passed": true}]}`, module_*.json each with `"changed_functions": ["x"]`, and summary.json = `{}` (the shipped package crashes on the three non-JSON feed lines, so the real summary cannot be produced without repairing feed.py). Run against the real check functions (rewardkit stubbed only for registration; log /tmp/opencode-logs/schema-migration-plan-repair-probe-20261021T2050/probe_shipped.log): it earned 19 of 142 = 13.4% of the test channel. The checks that paid:

| Check | Weight | Why it paid |
|---|---|---|
| artifacts_exist | 1 | existence |
| archive_members_safe_src_layout | 1 | the shipped zip already has the K1 layout |
| api_entry_points_importable | 1 | the shipped package already exports every name |
| test_fixes_matches_visible_test_runs | 1 | before = after = the real shipped results |
| repair_report_well_formed | 1 | shape only |
| plan_tie_first_edge_decides | 5 | the shipped DFS walks edges in sorted id order and keeps the first equal-cost, equal-length plan, which is the smallest list in this fixture |
| exec_correction_first_arrival_only | 3 | the shipped executor applies the SET once at the start and never re-checks, so the `lacks:g` edge after the drop passes anyway |
| exec_correction_at_source_enables_step1 | 3 | applying everything at the start is the same as applying at the source when the only correction is pinned to the source |
| pipe_rejection_codes | 3 | the shipped pipeline already emits all five codes for this fixture |

Judged channel, same zero-repair agent: a final reply that paraphrases M6, M9, M8, N2, C4, K16 and M11 earns R7-R13 = 25 of 46 with no code read or changed. Combined zero-repair forgery: 0.5 x 19/142 + 0.5 x 25/46 = 0.067 + 0.272 = 0.339 of the total reward.

Findings in this gate:
- ❌ CL-2 / AL-F0c four content checks pay for behaviour the unrepaired code already has, and the judged channel pays for paraphrasing the contract. plan_tie_first_edge_decides (+5, "Among equal-cost plans the first edge decides when last edges disagree."), exec_correction_first_arrival_only (+3), exec_correction_at_source_enables_step1 (+3) and pipe_rejection_codes (+3) all pass on the shipped repo.zip repackaged unchanged (probe above): 14 points that believe they grade repaired behaviour. With the judged R7-R13 (+25 of 46, see CL-3) a zero-repair submission scores 0.339, inside the range of a genuine partial repair. Bug/Error. Fix: in tests/test_output.py rebuild case_tie_first_edge, case_first_arrival, case_source_arrival and case_rejection_codes so the shipped repo.zip fails each (for example give case_tie_first_edge a shorter equal-cost plan with a larger first id, give case_first_arrival a prerequisite that only holds after the arrival-time SET, and add a merged-alias partner to case_rejection_codes), and apply the JD-8 fix to R7-R13 in tests/judge.toml.
- ❌ CL-3 R7-R13 expect sentences that can be copied from shipped contract files. R9 "among plans of equal total cost the plan whose edge-id list is smallest, compared from the first edge, is chosen" is migration_semantics.md M8 ("among plans of equal total cost, the one whose list of edge ids is smallest when the lists are compared element by element as strings, first edge first"); R12 "computed on the record as received, before null tokens are replaced" is repository_contract.md K16 ("taken on the line as received, before null tokens are replaced"); R11 is the correction_log.txt C4 header; R8 is M9 ("Two records with the same source schema can therefore need different plans"); R7 is M6; R10 is the null_semantics.ini N2 header; R13 is M11. The criteria cannot tell an agent that restored the behaviour from one that transcribed the contract. Bug/Error. Fix: same as the gate 04 JD-8 fix (replace R7-R13 in tests/judge.toml with trajectory criteria about how each repair was verified).
- ❌ AL-F0d R7-R13 overlap the tests on the same facts (same defect as gate 04 JD-8, counted once in the totals). Bug/Error. Fix: see JD-8.
- ❌ AL-27 two stated precedence rules have no fixture that triggers them. (1) partner_aliases.xml P1 "A partner value equal to a partner id names that partner; otherwise a value equal to an alias text names the alias's partner": no hidden Spec has an alias whose text equals another partner's id (the shipped XML has 0 such aliases either), so a resolver that checks aliases first scores the same. (2) correction_log.txt C4 "Corrections pinned to one schema are applied in log order": every hidden execution case carries one correction per record (case_unset_breaks ... case_attempted), so reverse-order application scores the same; the shipped log has 15 partner/key/schema groups with more than one correction, but they only reach summary.json, which is compared against the delivered package's own run. Bug/Error. Fix: in tests/test_output.py add one resolve case where an alias string equals another partner's id (expected: the id's partner), and one execute case with a SET then an UNSET of the same field pinned to the same schema followed by a `has:` edge (expected: E_PREREQ_FAILED, corrections_applied in log order).
- ❌ AL-26 category names a side aspect (same defect as gate 01 IN-12, counted once in the totals). task.toml:12 `category = "Data Processing"` for a repository repair task. Bug/Error. Fix: set `category = "Software Engineering"` in task.toml [metadata].
- 🟡 AL-18 TRUTH.md reward floor -1.000 against the real -0.162 (same defect as gate 02 DS-22, counted once). Fix: see DS-22.

Checklist:
- ✅ AL-F0a no template residue (marker sweep: zero hits in bundle text and repo interior; every file earns its place)
- ✅ AL-F0b data dependency holds (repo.zip is the subject; the rule homes are the contract)
- ❌ AL-F0c work dependency holds, no shortcut found (shortcut: repackage repo.zip unchanged for 19/142 of the test channel, plus contract paraphrase for 25/46 of the judge channel; see CL-2)
- ❌ AL-F0d no double scoring across tests and judged criteria (R7-R13, see JD-8)
- ✅ AL-F0e solvable from instruction.md + environment/ input alone: no information the agent needs is unreachable (hard is fine, only impossible fails) (see DS-21 and CL-10)

- ✅ CL-1 every demanded action has a checker that looks at the action itself, not the agent's report of it (test or judged criterion named for each action). Actions: repair each stage, checked by running the delivered package on hidden inputs (39 behaviour checks); produce summary.json from the repaired package, checked by summary_json_matches_delivered_run re-running the delivered package itself; record before/after visible test results, checked by test_fixes_matches_visible_test_runs re-running both trees; keep the visible tests, checked by negative_deleted_visible_tests reading the delivered file; state the restored behaviours in the final reply, checked by the judge on the reply. The one self-report, repair-report.json "checks you ran" (repair_report_well_formed, weight 1), is cross-checked against the trajectory by R17 (-3).
- ❌ CL-2 forgery price computed as a share of the positive weight, every paying test named, the total judged defensible with reasons (19/142 = 13.4% of the test channel, 25/46 = 54.3% of the judge channel, 0.339 combined; 14 test points paid while claiming to grade content; see finding)
- ❌ CL-3 no asserted value liftable verbatim from a shipped file, an instruction constant or a worked example (derivation is fine and expected) (R7-R13; every test expectation is computed at grade time from generated inputs, so the tests are clean)
- ✅ CL-4 one wrong fact costs about one fact: one-fact-wrong score computed, no almost-right answer scoring as entirely wrong. Facts are graded by 46 separate positive checks. Example: a repair that is right except that the partner token line is merged into the default list (N7) loses only pipe_partner_token_list_replaces_default (3): test channel 139/142 = 0.979, total 0.989 with a full judge score. The largest single-root loss is the shared null view (FieldView, N1): signature_keeps_explicit_null 3 + plan_renamed_null_satisfies_has 5 + ladder_large_null 5 + exec_correction_null_blocks_lacks 5 + exec_add_fill_absent_vs_null 3 = 21/142, one root defect feeding five rules, which is a fair price.
- ✅ CL-5 every exact comparison's silent requirements (order, keys, path form, casing) either stated in the contract or compared insensitively, judged criteria read the same way. Orders: test_fixes "sorted by name" (K19), changed_functions "sorted" (K19), invalid_corrections "sorted ids" (K18), records in feed line order (K9, K17), partners by rank then id (T3); key names K17, K18, K19, M12; dict comparisons ignore key order; paths `/app/out/...` (instruction.md:7-11) and archive members at the root (K19 "K1 layout at the archive root"); error-code casing K12. Judged names R1-R6 match the instruction's "name the module and function".
- ✅ CL-6 every shipped value the graded truth contradicts is signposted as suspect somewhere the agent can read (name the signpost). The shipped code (and its docstrings, e.g. planner.py:35 "Prefer the cheaper plan, then the shorter one", cli.py:13 "relative paths are taken from the package folder") contradicts the contract; signposts: instruction.md:1 "Parts of its parser, core, pipeline, report and command-line code do not behave the way its contract says." and repository_contract.md:7-8 "Every rule applies whether or not the shipped code already follows it."
- ✅ CL-7 every path the instruction names exists in every graded corpus. /app/data/repo.zip and the six rule files are in the verifier's rebuilt data dir (`_SHIPPED_DATA`, 13 files byte-identical); the hidden contract folders carry the seven K2 files the package must read; `tests/test_visible.py` is inside repo.zip and the delivered archive.
- ✅ CL-8 oracle needs no fallback that skips an instruction-required step (solve.py stops with `SystemExit` on any mismatch: "expected exactly one occurrence", "visible tests still failing", "CLI run failed"; no hardcoded values)
- ✅ CL-9 test.sh and check setup never supply the value a later assertion measures. Setup kinds: Spec.write builds input contract folders (measurement setup); `_unit_results(_shipped_repo())` measures the shipped tests that test_fixes is compared against (the verifier's own measurement, not an agent value); `_child` runs the delivered package. None writes a value a later assertion reads as the agent's.
- ✅ CL-10 every asserted fact traced to an agent-visible file or a derivation from one; nothing load-bearing lives only in solution/ or tests/. Ladder plans derive from M6-M8; the 10 s budget from K14; VISIBLE_TESTS from tests/test_visible.py; API_NAMES from K2-K11; AREAS from K19; codes from K12; fixture expectations recomputed in gate 01 IN-8. EVAL_SEED and hidden edge ids live only in tests/ and are used only by a negative check.
- ✅ AL-1 every test and every outcome criterion promised by the contract (the instruction plus any spec file it points to); every constraint criterion quotes the instruction sentence it enforces; every conduct criterion holds for any competent route or earns its narrowing, and serves a real requirement (tests: each traced in gate 01 IN-8 and gate 03 TS-19; R1-R13 instruction.md:17; R16 instruction.md:15; R14 step 1 passes, serves the repair; R15/R17 misconduct negatives)
- ✅ AL-2 every instruction promise graded (repair of each stage: 39 behaviour checks; the time limit: ladder checks; "on any contract folder and feed": hidden Specs plus negative_filename_dependent_behaviour; each of the seven deliverables: its own check; "Keep the visible tests": negative_deleted_visible_tests; stdlib only: R16, and any third-party import fails every behaviour check in the stdlib-only verifier; final reply: R1-R13)
- ✅ AL-3 exact shapes agree across the contract, tests, solution (read the shipped spec, not just the prompt) (K19 shapes = `_module_claims`, test_fixes and repair_report checks = solve.py `write_json` calls; M12 keys = `_failed` and the expected dicts; K17 keys read by the pipe checks)
- ✅ AL-4 no hidden graded behaviours beyond the contract
- ✅ AL-5 oracle would pass every test (traced in gate 02 DS-15; Step 10 oracle runs)
- ✅ AL-6 judged criteria consistent with solution and instruction (re-verified R7 against solve.py's `edge_allowed(... view ...)` on the state reached, R11 against `arrive()`, R2 against shipped planner.py:62)
- ❌ AL-27 every stated rule has a fixture that actually triggers it (precedence pairs traced). Triggered: M8 cost-then-list (case_tie_first_edge, case_tie_longer), T1 code-before-status and taxonomy order (case_categories), N2 and N4 policy-before-ini (case_null_counted_absent, case_fill), N7 replace-not-merge (case_partner_tokens), K13 received_seq before file order (case_received_order), M4 left-to-right (case_operations rename then cast), C4 arrival before the next check (case_unset_breaks). Untriggered: P1 id before alias, C4 log order (see finding).
- ✅ AL-28 no penalty stacking: one action never fires more than one max-severity penalty across tests and judged criteria. Actions: embedding hidden seeds/ids -> negative_hardcoded_sample_answers (-5); keying on the feed's file name -> negative_filename_dependent_behaviour (-3); gutting visible tests -> negative_deleted_visible_tests (-3); nondeterministic output -> negative_nondeterministic_output (-1), and can also trip negative_filename_dependent (-3), group total -4 (at most 5); reading /tests, /solution or /logs/verifier -> R15 (-5); installing a package -> R16 (-3); a false "passed" claim -> R17 (-3). No group above 5.
- ✅ AL-7 no unearned measured claims (TRUTH.md's golden score is "Not yet measured"; its timing numbers (0.62 s, 7.6 s) are stated as build-time measurements and are plausible against the 20 s ladder budget)
- ✅ AL-8 time claims plausible for the actual work (and any declared difficulty band fits it) (expert 480 min, junior 1440 min for 15 contract divergences over 999 source lines including a product-graph planner)
- ✅ AL-9 solution discussion confined to TRUTH.md/task.toml, none of it reachable by the agent
- ✅ AL-10 hardcoding vector closed (no labelled examples; hidden cases generated from EVAL_SEED; negative_hardcoded_sample_answers)
- ✅ AL-11 grade-time environment abuse closed (checks read only the seven artifacts; APP_ROOT comes from the verifier's own environment)
- ✅ AL-12 grader influence via /app closed (the delivered package runs only as a `setpriv` child; the rewardkit process only `ast.parse`s its source)
- ✅ AL-13 answers not reconstructable without the work
- ✅ AL-14 reward path tamper-proof end to end (rewardkit is the only writer) (test.sh clears and locks; TS-29 holds; survivors of TS-24 run as nobody and cannot write root-owned /logs/verifier; reward.toml matches both totals)
- ✅ AL-15 pinned offline contract consistent across all layers (verifier and agent network lines excluded; silence about the network is expected)
- ✅ AL-16 artifact filenames consistent bundle-wide (instruction.md:7-11 = task.toml:2 = solve.py OUT names = test_output.py ARTIFACTS)
- ✅ AL-17 timeout story coherent (7200 s in instruction and [agent]; verifier 2700 s against a measured oracle trial of about 5 minutes including both builds)
- 🟡 AL-18 no stale references or wrong counts anywhere (TRUTH.md floor, see DS-22; every other count checked: 54 rules, 50/46/4 checks, 142/12, 17/46/11, 17 repairs, 562 lines, 15 digests)
- ✅ AL-19 no credential/secret exfiltration (only the pinned `${OPENAI_API_KEY:-}` placeholder)
- ✅ AL-20 no network exfiltration or supply-chain risk (no download in any runtime path; the agent image installs from apt and pip at build time only)
- ✅ AL-21 no destructive or resource-abuse operations (solve.py removes only its own mkdtemp scratch)
- ✅ AL-22 no obfuscated payloads. test_output.py holds base64+zlib blobs that are decoded and, for repo.zip, executed (the shipped visible tests). All 13 decode to bytes identical to environment/data (checked file by file), and the docstring states the purpose ("The agent's /app/data, rebuilt here: the verifier container never has it.").
- ✅ AL-23 no prompt injection in agent-visible files (read the contract files in full; scanned the data files and repo for model-addressed text: none)
- ✅ AL-24 filename-keyed shortcut closed (hidden folders use other file names; negative_filename_dependent_behaviour)
- ✅ AL-25 nondeterministic-output shortcut closed (39 independent hidden cases; negative_nondeterministic_output)
- ❌ AL-26 category names the dominant work; description honest; keywords/tags related (category, see finding)

Gate 05 verdict: ❌ fail (5 fails, 1 minor, 0 warns; 3 of the fails and the minor duplicate defects already counted in gates 01, 02 and 04, so gate 05 adds 2 new fails: CL-2/F0c and AL-27).

## Step 11: Final coverage and overlap re-check

Derived again from instruction.md, the six rule homes it points to, tests/test_output.py (bodies and registrations) and tests/judge.toml, not from the gate verdicts above.

### Coverage

Instruction to checker:

| Instruction requirement (instruction.md) | Checker(s) |
|---|---|
| Repair so every stage behaves as the contract states, on any contract folder and feed (:1, :3) | 39 behaviour checks on hidden Specs (rows below); negative_filename_dependent_behaviour |
| Each stage correct when called on its own (:3) | `_child` driver calls each entry point: signature, plan, execute, resolve, summary, pipeline, api |
| Planning time limit on graphs with too many paths to list (:3, K14) | ladder_medium_state, ladder_large_state, ladder_large_tie, ladder_large_null |
| patched-repo.zip, K1 layout (:7) | archive_members_safe_src_layout, artifacts_exist |
| summary.json from the repaired package (:8) | summary_json_matches_delivered_run |
| module_core/parser/report.json (:9) | module_core/parser/report_claims_match_archive |
| test_fixes.json (:10) | test_fixes_matches_visible_test_runs |
| repair-report.json (:11) | repair_report_well_formed; R17 (honesty) |
| Keep tests/test_visible.py and its assertions (:15) | negative_deleted_visible_tests; visible_repo_tests_pass_from_archive |
| Standard library only, no third-party package (:15) | R16 (environment); any third-party import fails every behaviour check in the stdlib verifier |
| Final reply: behaviours restored + module/function where shipped code diverged (:17) | R1-R6 (location), R7-R13 (behaviour statements) |
| "Do not cheat by using online solutions" (:19) | none needed (IN-10) |

Contract rule to checker (rule-level, the 54 rules the instruction delegates to):

| Rule | Checker(s) | Ungraded clause |
|---|---|---|
| K1 | archive_members_safe_src_layout, api_entry_points_importable | |
| K2 | every `_child` job (load_contracts on a 10-file folder) | |
| K3, P1-P4 | identity_merge_chain, identity_merge_loop_rejected, pipe_replay_across_aliases, pipe_mid_path_failure_record, pipe_reissue_supersedes_holder | P1 id-before-alias precedence (AL-27) |
| K4 | pipe_token_vs_json_null_conflict, pipe_reissue_supersedes_holder (prefix of the tests' own `_fp`), visible test_fingerprint_stable | |
| K5, M10 | signature_keeps_explicit_null | |
| K6, M6-M9 | plan_* (7), ladder_* (5) | M9/N6 "Planning sees the payload after null-token replacement": no pipe fixture has a prerequisite on a token-valued field, so replacing tokens after planning scores the same |
| K7, M11, M12, C4, C5 | exec_* (7) | K7 "Neither function changes its arguments": no check compares the payload after the call; C4 log order (AL-27) |
| K8, K18, T1-T3 | summary_categories_from_taxonomy, summary_partner_order, pipe_attempted_vs_migrated_counts, pipe_invalid_corrections_listed, cli (records) | K18 `by_code`: read by no check |
| K9, K13 | pipe_* (12), pipe_received_seq_decides_holder | |
| K10 | cli_module_runs_from_foreign_cwd; visible test_module_entry_help via visible_repo_tests_pass_from_archive | |
| K11 | plan_unreachable_by_state, identity_merge_loop_rejected, pipe_rejection_codes | `state_signature` raising E_UNKNOWN_SCHEMA: only case_signature, which uses a known schema |
| K12 | pipe_rejection_codes, exec failures, identity loop | "E_INVALID_CORRECTION ... never a record code": no check |
| K14 | ladders | |
| K15 | pipe_bad_lines_run_continues, pipe_rejection_codes | "Such a record has batch, partner, key and schema null": no check reads them |
| K16 | pipe_replay_across_aliases, pipe_token_vs_json_null_conflict, pipe_edit_dropped_by_migration_conflict, pipe_reissue_supersedes_holder, pipe_received_seq_decides_holder | |
| K17 | pipe_mid_path_failure_record, pipe_rejection_codes, pipe_bad_lines_run_continues, cli (line) | `fingerprint`, `plan`, `partner`, `batch`, `key` values of pipeline records: no check reads them |
| K19 | the six artifact checks | |
| M1-M5, N1-N5 | exec_operations_apply_in_order, exec_add_fill_absent_vs_null, plan_renamed_null_satisfies_has, exec_correction_null_*, plan_tracks_field_dropped_earlier, plan_uses_edge_enabled_earlier | |
| N6-N8 | pipe_partner_token_list_replaces_default, pipe_token_vs_json_null_conflict | N7 "an empty line means no tokens": no fixture |
| C1-C3, C6-C8 | pipe_mid_path_failure_record, pipe_reissue_supersedes_holder, pipe_invalid_corrections_listed, pipe_attempted_vs_migrated_counts | |

Checker to contract (every test and criterion has a sentence behind it):

| Checker | Sentence and file |
|---|---|
| artifacts_exist, archive_members_safe_src_layout, summary_json_matches_delivered_run, module_*_claims, test_fixes_matches_visible_test_runs, repair_report_well_formed | instruction.md:7-13 + repository_contract.md K1, K19 |
| api_entry_points_importable | repository_contract.md K1 "every name below is importable from the top-level migrakit package" |
| cli_module_runs_from_foreign_cwd | K10 |
| visible_repo_tests_pass_from_archive | instruction.md:1 "every stage behaves as the contract states" + :15 keep the tests; the visible tests assert K4, K6, K7, K10, K11, P1 |
| signature_keeps_explicit_null | M10, N1 |
| plan_* (7), ladder_* (5) | M6, M7, M8, N2, M4/N5, K14 |
| exec_* (7) | M4, M5, N4, C4, M11, M12, N2 |
| identity_* (2) | P2, P3 |
| pipe_* (12) | K12, K13, K15, K16, C2, C3, C7, C8, N7, K17, K18 |
| summary_* (2) | T1, T2, T3 |
| negative_hardcoded_sample_answers, negative_filename_dependent_behaviour | instruction.md:1 "on any contract folder and feed inside the stated limits, and not only on the shipped ones" |
| negative_deleted_visible_tests | instruction.md:15 "Keep the visible tests in `tests/test_visible.py` and their assertions." |
| negative_nondeterministic_output | conduct-level guard on the same :1 sentence (output must be a function of the inputs) |
| R1-R13 (outcome) | instruction.md:17 |
| R14 (conduct) | serves the repair deliverable; every competent repair passes step 1 |
| R15, R17 (conduct negatives) | misconduct (grader reading, fabricated success), JD-11 list |
| R16 (constraint) | instruction.md:15 "Use only the Python standard library; add no third-party package to the repository or the environment." |

No test or outcome criterion lacks a requirement; no constraint criterion lacks a sentence.

### Overlap

Observable read by each side: tests read the delivered package's behaviour on generated inputs, the seven artifacts, the delivered source tree (AST diff, visible test file, hidden-id scan). R1-R6 read the reply's naming of shipped functions (no test reads that; module_*.json lists changed functions and is checked only for consistency with the archive, a different observable). R7-R13 read the reply's statement of rules M6, M9, M8, N2, C4, K16, M11, which are the same facts the plan_*, ladder_*, exec_* and pipe_* checks grade (overlap, gate 04 JD-8). R14 reads code quality of the diff (no test). R15, R16 read the trajectory (no test). R17 reads claims against the trajectory; repair_report_well_formed reads the report's shape only (different observables).

Overlap found: R7-R13 (already reported as JD-8 / AL-F0d). Zero other pairs.

Findings in this step (new):
- ❌ Step 11 coverage: seven contract clauses the instruction delegates to have no checker. (1) K7 "Neither function changes its arguments."; (2) K11 `state_signature` raises E_UNKNOWN_SCHEMA; (3) K12 E_INVALID_CORRECTION "never a record code"; (4) K15 "Such a record has `batch`, `partner`, `key` and `schema` null."; (5) K17 record `fingerprint`, `plan`, `partner`, `batch`, `key` values; (6) K18 `by_code`; (7) N7 "an empty line means no tokens". Checked: none of these keys or cases appears in any check body (grep over test_output.py:7030-8300 finds no `by_code`, no record `"fingerprint"`/`["partner"]`/`["batch"]` read, no `E_INVALID_CORRECTION`, one signature case on a known schema). Bug/Error. Fix: in tests/test_output.py extend existing checks rather than adding weight: compare `batch/partner/key/schema` of the E_PARSE records and the `fingerprint` and `partner` of one record in pipe_rejection_codes, `by_code` in pipe_attempted_vs_migrated_counts, add an unknown-schema call to the signature case, compare the payload after execute_plan in `_exec_case`, and add an empty partner token line to case_partner_tokens.
- ❌ AL-27 (addition found here, belongs to the gate 05 finding): N6/M9 "Before planning, every top-level payload value that is a string exactly equal to one of the partner's null tokens becomes an explicit null" has no fixture where a token-valued field is a prerequisite, so token replacement after planning scores the same. Fix: in tests/test_output.py add a pipe case with a cheap edge requiring `has:f`, a dearer edge with no prerequisite, a policy row giving f `null_counts_as = absent`, and a line sending `"f": "NULL"` (expected: migrated by the dearer edge; replacing tokens after planning picks the cheap edge and then fails it).

Step 11 verdict: ❌ fail (1 new fail; the overlap and the AL-27 addition extend findings already counted).

## Step 10: Execution gate

Scores are TESTS-ONLY, as the kit specifies: exe_copy.py validated tests/judge.toml against the rewardkit 0.2.1 schema and did not execute it; no OpenAI key was set (the runs were launched under `env -u OPENAI_API_KEY`); the stub score covers the test channel only. The network was opened and the OpenHands pre-bake dropped in the two copies only; the bundle under review was not edited.

Preflight (2026-10-21 22:59 IST):
```
$ harbor --version
0.24.0
$ docker ps
CONTAINER ID   IMAGE              COMMAND                  CREATED          STATUS          PORTS     NAMES
677b40e383bd   python:3.12-slim   "python3 /w/probe3.py"   31 seconds ago   Up 30 seconds             inspiring_saha
$ ls ".../QC_2026-10-21/bundles/schema-migration-plan-repair"
environment  instruction.md  solution  task.toml  tests
```
(The running container belongs to another session; it was not touched.)

TS = 20261021T2259. exe_copy.py RUN copy, exit 0:
```
[exe-copy] copied .../QC_2026-10-21/bundles/schema-migration-plan-repair -> /private/tmp/oracle-qc/schema-migration-plan-repair-20261021T2259/run/schema-migration-plan-repair
[exe-copy] tests/judge.toml loads under the rewardkit 0.2.1 schema (validated, not executed)
[exe-copy] deleted tests/judge.toml
[exe-copy] tests/reward.toml -> weights = { test_output = 0.007042253521126761 } (1 / positive total 142)
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
EXIT=0
```
exe_copy.py STUB copy (`--stub`), exit 0: identical lines with the destination `.../stub/schema-migration-plan-repair`, plus
```
[exe-copy] solution/ replaced by a stub solve.sh creating 7 empty artifact(s)
EXIT=0
```
P = 142.

Commands (flags confirmed with `harbor run --help`: `--path/-p`, `--agent/-a`, `--env/-e`, `--job-name`, `--jobs-dir/-o`, `--yes/-y`), chained in one nohup job, log /tmp/opencode-logs/schema-migration-plan-repair-step10-20261021T2259/runs.log (ends `ALL_DONE`):
```
harbor run --path ".../run/schema-migration-plan-repair" --agent oracle --env docker --job-name oracle-N -o "/tmp/harbor-jobs-qc/schema-migration-plan-repair-20261021T2259" -y   (N = 1..5)
harbor run --path ".../run/schema-migration-plan-repair" --agent nop --env docker --job-name nop-1 -o ".../schema-migration-plan-repair-20261021T2259" -y
harbor run --path ".../stub/schema-migration-plan-repair" --agent oracle --env docker --job-name stub-1 -o ".../schema-migration-plan-repair-20261021T2259" -y
```

Results (read from each trial's result.json `verifier_result.rewards.reward` and verifier/reward.json; no trial has `exception_info` or exception.txt):

| Agent | Run | Trial | result.json reward | verifier/reward.json |
|---|---|---|---|---|
| oracle | oracle-1 | schema-migration-plan-repair__mVjhgss | 1.0 | {"reward": 1.0} |
| oracle | oracle-2 | schema-migration-plan-repair__UHj59SE | 1.0 | {"reward": 1.0} |
| oracle | oracle-3 | schema-migration-plan-repair__UqmwtLA | 1.0 | {"reward": 1.0} |
| oracle | oracle-4 | schema-migration-plan-repair__68kMmn4 | 1.0 | {"reward": 1.0} |
| oracle | oracle-5 | schema-migration-plan-repair__P76Czj9 | 1.0 | {"reward": 1.0} |
| nop | nop-1 | schema-migration-plan-repair__YwYrad6 | 0.0 | {"reward": 0.0} |
| oracle on stub | stub-1 | schema-migration-plan-repair__iADAEUX | 0.007 | {"reward": 0.007} |

Failing checks: none. oracle-1 reward-details.json: all 46 positives true, all 4 negatives false. nop-1: all 50 criteria value 0.

Stub solve.sh (STUB copy, in full):
```
#!/bin/bash
set -euo pipefail
P=/app/out/patched-repo.zip; mkdir -p "$(dirname "$P")"; : > "$P"
P=/app/out/repair-report.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/module_core.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/module_parser.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/module_report.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/test_fixes.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/summary.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
```
stub-1 scored rather than errored, so no stub-2 was needed. Checks with a non-zero value in stub-1 reward-details.json: `artifacts_exist` (weight 1, value 1.0). Stub share: 1/142 = 0.7% of the test channel. Judgement: healthy. Only the existence check paid, which is what it claims to grade; the empty zip makes every behaviour check return False through `_holds`. The stub cannot open an empty file as a zip, so it does not reach the CL-2 price: the hand-built forgery in gate 05 (the shipped repo.zip repackaged plus plausible JSON) earned 19/142 = 13.4%, of which 14 points come from four behaviour checks the unrepaired code already passes. That defect is carried as the gate 05 CL-2 finding, not as a stub finding.

diff -rq bundle vs RUN copy:
```
Files .../environment/Dockerfile and .../run/.../environment/Dockerfile differ
Files .../task.toml and .../run/.../task.toml differ
Only in .../schema-migration-plan-repair/tests: judge.toml
Files .../tests/reward.toml and .../run/.../tests/reward.toml differ
```
diff -rq bundle vs STUB copy:
```
Files .../environment/Dockerfile and .../stub/.../environment/Dockerfile differ
Only in .../schema-migration-plan-repair/solution: TRUTH.md
Only in .../schema-migration-plan-repair/solution: solve.py
Files .../solution/solve.sh and .../stub/.../solution/solve.sh differ
Files .../task.toml and .../stub/.../task.toml differ
Only in .../schema-migration-plan-repair/tests: judge.toml
Files .../tests/reward.toml and .../stub/.../tests/reward.toml differ
```
All differences are in the allowed set (judge.toml only in the bundle, reward.toml, task.toml, environment/Dockerfile, and solution/ for the stub copy).

Cleanup: deleted /tmp/oracle-qc/schema-migration-plan-repair-20261021T2259 and /tmp/opencode-logs/schema-migration-plan-repair-repo-20261021T2047. Kept: jobs folder /tmp/harbor-jobs-qc/schema-migration-plan-repair-20261021T2259 and logs. After cleanup the bundle still has tests/judge.toml, its original reward.toml (`weights = { test_output = 0.0035211267605633804, judge = 0.010869565217391304 }`), task.toml, environment/Dockerfile and solution/; `diff -rq` against the original bundle prints nothing (exit 0); no __pycache__ in the bundle or the kit; `git status --porcelain -- Input_Bundle_QC` is empty.

Step 10 verdict: ✅ pass (0 fails, 0 minors, 0 warns).
