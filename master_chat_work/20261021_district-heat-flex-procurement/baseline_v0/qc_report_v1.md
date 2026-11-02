# QC report: district-heat-flex-procurement

- Bundle: district-heat-flex-procurement
- Bundle path: /Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/district-heat-flex-procurement
- Report version: v1
- Date/time: 2026-10-21 18:58 IST (13:28 UTC)
- QC kit: Terminal_2.0_Harbor_Harness/Input_Bundle_QC at commit bde868c46994f4916e245b40d14f302b1341244a
- Harbor version: 0.24.0
- Session title: district-heat-flex-procurement_v1_qc (opencode session list shows it on session ses_ea15ccd57ffeCL3zLNqb4Dm96L, listed second because a sibling session updated in the same minute)


Verdict: ❌ FAIL (11 fails, 5 minors, 4 warns)

| Step | Gate | Verdict | Fails | Minors | Warns |
|------|------|---------|-------|--------|-------|
| 1 | structure_qc.py | ✅ pass (exit 0) | 0 | 0 | 0 |
| 2 | instruction_qc.py | ✅ pass (exit 0) | 0 | 0 | 0 |
| 3 | tests_qc.py | ⚠️ warn (exit 0) | 0 | 0 | 1 |
| 4 | judge_qc.py | ✅ pass (exit 0) | 0 | 0 | 0 |
| 5 | 01 Instruction | ❌ fail | 1 | 0 | 0 |
| 6 | 02 Data & Solution | ❌ fail | 1 | 2 | 0 |
| 7 | 03 Tests | ❌ fail | 1 | 1 | 4 |
| 8 | 04 Judge criteria | ❌ fail | 2 | 2 | 0 |
| 9 | 05 Alignment & Integrity | ❌ fail | 6 | 0 | 0 |
| 10 | Execution gate | ✅ pass (oracle 1.000 x5, nop 0.000, stub -0.0072) | 0 | 0 | 0 |
| 11 | Coverage and overlap re-check | ❌ fail (confirms gate 05 AL-27 and gate 03 TS-19; no new finding) | 0 | 0 | 0 |
| - | Overall (unique findings; the tests_qc A3 warn and gate 03 TS-23 are one finding) | ❌ FAIL | 11 | 5 | 4 |

Step 10 scores are tests-only: judge.toml was validated against the rewardkit 0.2.1 schema and not executed, no OpenAI key was used, and the network opening and OpenHands drop were made in the copies only.

## Findings

### ❌ Fails

1. ❌ Gate 01 IN-16 - `waiver_signed_missing` has two defensible readings for the skipped waiver line of an unknown-region site, and a graded check turns on it. schema.md lines 37-40 ("the lines of ... `continuity_waivers.csv` ... for its `event_id` and `site_id` are skipped") vs line 319 ("waiver rows with an empty `waiver_signed`"); the reference (test_output.py lines 175-177) counts the skipped line; `mixed_rejection_counts_case` (3) expects 3 where the skip reading gives 2 (scratch run: the skip reading scores 136/139). Bug/Error. Fix: in environment/data/schema.md section 9 write "waiver rows with an empty `waiver_signed`, counted over every data row of `continuity_waivers.csv`, including lines skipped for an unknown-region site".
2. ❌ Gate 02 DS-24 - The oracle's graded search restates the verifier's reference, down to a dead `scale` knob that exists only for the verifier's DH2 switch. solve.py lines 228-236, 262, 281-282 (`search_scale` always `return 1`; `search_units` unreachable raw-Wh branch; `caps = [scale * c + (scale + 1) // 2 - 1 ...]` with the same comment as test_output.py line 301) vs test_output.py lines 279-302, and the same state key, dominance rule, way counting and five-tuple scoring (test 294-343 vs solve 261-321). The search decides 69 of 139 points, so oracle 1.000 there cannot disagree with the grader. Bug/Error. Fix: rewrite the portfolio search in solution/solve.py as an independent method (for example branch-and-bound over sites with an admissible bound and exact tie counting), delete `search_scale`, `search_units` and the `scale` arithmetic, and re-run Step 10.
3. ❌ Gate 03 TS-19 - Two graded hidden extracts give a site 5 offers, beyond the contract's maximum of 4. instruction.md line 3 "up to 4 offers per site" and schema.md lines 143-144; test_output.py line 774 (`"ABCD"[:rng.pick([3, 4, 4, 4])]`) plus lines 781-783 (twin appended to an existing site): `large_tie` L08 and L14 and `large_tie_shuffled` L01 carry 5 offers; `large_tie_count_case` (5) and `large_tie_greatest_tuple_shuffled_case` (5) grade them. Bug/Error. Fix: in tests/test_output.py `_large_spec`, take each twin's source from a site with 3 offers and assert at most 4 offers per site in `large_passes`, then re-run Step 10.
4. ❌ Gate 04 JD-7 - R9 is false of the reference program, which carries dead code. judge.toml line 118 "no dead or duplicated code blocks" vs solve.py lines 228-236 (`search_units` second `return` can never run), line 264 (`measure` is `half_up(total, 1)`), line 325 (`report_ticks` never uses `ex`). Bug/Error. Fix: remove `search_scale`, `search_units`, the `scale` arithmetic and the unused `ex` parameter from solution/solve.py (same edit as finding 2).
5. ❌ Gate 04 JD-6 - R10's condition "that the shipped data never exercised" cannot be decided from the closing message. judge.toml line 131, `evaluation_target = "user_facing_message"`; whether a rule is exercised depends on /app/data, which exercises some rules (36 orphan profile rows, 1054 pools with residual ties) and not others. Bug/Error. Fix: in tests/judge.toml set R10 `evaluation_target = "trajectory"` with "The agent runs a command on /app/data that shows zero records triggering a named schema.md rule."
6. ❌ Gate 05 AL-27 - SAFETY_HOLD over COOLDOWN is never triggered. schema.md lines 129-130; no graded extract has a site with both flags whose label is compared; swapping the two scores 139/139. Bug/Error. Fix: in tests/test_output.py add a `hold=True, cool=True` site to the `waiver` case and include its `site_label` in the observable.
7. ❌ Gate 05 AL-27 - The CERTIFICATE_PENDING label is never graded. schema.md line 151; only `waiver_precedence_case` compares labels and it has no plain pending site; labelling pending sites CLEAR scores 139/139. Bug/Error. Fix: in tests/test_output.py add a `pending=True, status="EXPIRED"` site to the `waiver` case.
8. ❌ Gate 05 AL-27 - Objective components 4 (overdelivery) and 5 (offer count) and their order after component 3 are never triggered. schema.md lines 167-180; swapping 3 and 4, swapping 4 and 5, or dropping 5 all score 139/139. Bug/Error. Fix: in tests/test_output.py add one case whose two best portfolios tie on components 1-3 and differ in overdelivery (cheaper one overdelivering) and one that ties on 1-4 and differs in offer count, each compared on `selected_offer_ids`.
9. ❌ Gate 05 AL-27 - "Beneficiaries with weight 0 receive nothing and are not listed" is never triggered. schema.md line 217; listing them with 0 cents scores 139/139. Bug/Error. Fix: in tests/test_output.py give one recipient `weight=0` in the `residual` case.
10. ❌ Gate 05 CL-2 - The judged channel pays a no-program forgery. Test channel forgery 4/139 = 2.9% (the four format checks; defensible). Judged: R5, R13, R14, R15, R10 and R17 = 18/45 for a reply written from schema.md, with R10 and R17 paying for claims the judge cannot check. Total reward with no program: 0.2144, or 0.3478 with the cheap steps R1, R2, R3, R16. Bug/Error. Fix: in tests/judge.toml reweight R5, R10, R13, R14, R15, R17 to 1 each, tie R10 and R17 to trajectory evidence (R17: "The agent runs derive_report.py on an extract it built with an event-region of 20 or more sites and prints the elapsed seconds"), and move the freed weight to criteria that need a working program.
11. ❌ Gate 05 CL-3 - R5, R13 and R15 grade sentences that can be copied from schema.md. R5 (judge.toml line 66) = schema.md lines 201-203; R13 (line 170) = schema.md lines 108-110; R15 (line 196) = schema.md lines 13-14 and 51; 9 of 45 judge points cannot tell a solver from a transcriber. Bug/Error. Fix: in tests/judge.toml replace R5, R13 and R15 with facts the agent produces, for example "The response states the total `grant_funded_cents` its program reported for the shipped data", or merge them into one weight-1 criterion.

### 🟡 Minors

12. 🟡 Gate 02 DS-22 - TRUTH.md says the shipped data rejects no profile row; it rejects 36. solution/TRUTH.md lines 69-71 "no profile or site row is rejected"; shipped profiles.tsv has 36 rows whose offer_id is not in offers.csv (and 14 orphan offers). Bug/Error. Fix: in solution/TRUTH.md line 71 write "the only rejected rows are 14 orphan offers and their 36 orphan profile rows; no row is out of range, duplicated or in an unknown region".
13. 🟡 Gate 02 DS-22 - TRUTH.md Root cause describes the verifier's search, not solve.py. Lines 172-174 "the greatest and smallest sorted id tuples"; solve.py keeps one tuple (`prefer` = `max`, lines 239-241, 305). Bug/Error. Fix: in solution/TRUTH.md line 173 change it to "the greatest sorted id tuple".
14. 🟡 Gate 03 TS-14 - `mixed_rejection_counts_case` grades the whole data_quality.json while its description promises only the rejection order. test_output.py lines 1450-1454. Bug/Error. Fix: compare only `orphan_offer_rows`, `orphan_profile_rows`, `out_of_range_profile_rows`, `duplicate_profile_rows`, `unknown_region_site_rows`, or rename and redescribe it as a whole-file check.
15. 🟡 Gate 04 JD-5 - R9 bundles three observables (names, except clauses, dead/duplicated code). judge.toml line 118. Bug/Error. Fix: split R9 into "except clauses each name a specific exception type" and "no unreachable or duplicated code blocks".
16. 🟡 Gate 04 JD-15 - R4 ("states the five objective components and the final tie rule in its own words before coding the optimiser", line 53, weight 3) is a preference. Bug/Error. Fix: replace it with "The agent compares its optimiser with plain enumeration on at least one event-region of six or more sites before concluding." or drop it.

### ⚠️ Warns

17. ⚠️ Gate 03 TS-23 / tests_qc A3 - 41 checks, over the cap of 35. Suggestion/Improvement. Fix: merge same-extract pairs (the `large_20_*` and `large_22_*` pairs first) or get tasker approval.
18. ⚠️ Gate 03 TS-16 - `negative_reads_tests_or_reward_files` (-5) fires on any `test_output`, `/tests` or `/logs/` substring (lines 1490-1491), which an honest helper name or debug path can contain. Suggestion/Improvement. Fix: match `"/tests/"` and `"/logs/verifier"` path prefixes only and drop `test_output`.
19. ⚠️ Gate 03 TS-24 - A `setsid` daemon from one agent run escapes `killpg` and can rewrite cached `out/` folders (box `chmod(0o777)`, line 909) before a second check re-reads them, side-stepping the 30 s limit; reward.json itself is safe (root-owned /logs/verifier, program runs as nobody). Suggestion/Improvement. Fix: cache the parsed JSON dicts in `run_agent` instead of the folder.
20. ⚠️ Gate 03 TS-20 - `unknown_region_site_row_report_case` (5) outweighs `ordinary_extract_segment_files_match` (3). Suggestion/Improvement. Fix: swap the two weights.

## Consolidated sign-off

- ✅ structure_qc.py exits 0
- ✅ FC-S1..FC-S24 structure_qc.py output read, and every failure it reports confirmed in the file and carried into the report (17 pass, no failures)
- ✅ instruction_qc.py exits 0
- ✅ tests_qc.py exits 0 (with the A3 warn, finding 17)
- ✅ judge_qc.py exits 0
- ❌ Gate 01 Instruction: no fail findings (finding 1)
- ❌ Gate 02 Data & Solution: no fail findings (finding 2)
- ❌ Gate 03 Tests: no fail findings (finding 3)
- ❌ Gate 04 Judge criteria: no fail findings (findings 4, 5)
- ❌ Gate 05 Alignment & Integrity: no fail findings, F0a-F0e all clean (F0a-F0e clean; findings 6-11)
- ✅ CL-1..CL-10 client feedback checks all run, each one carrying the number it asks for or the file and line it asks for (never a bare ✅) (CL-2 4/139 tests and 0.2144-0.3478 total; CL-4 one-rule-wrong 0.8129-0.9784; the others with quoted lines in gate 05)
- ✅ Step 10 preflight run and pasted (harbor version 0.24.0 or newer, with the exact number recorded; docker reachable; bundle path listed) (harbor 0.24.0)
- ✅ Step 10 oracle run executed for real FIVE times: all five exactly 1.000, every number reported individually (evidence pasted) (1.0, 1.0, 1.0, 1.0, 1.0)
- ✅ Step 10 nop run executed for real: reward exactly 0.000 (evidence pasted) (0.0)
- ✅ Step 10 stub run executed for real: score reported, tests that paid named, judgement given with reasons (evidence pasted) (when the preflight showed this machine cannot run the harness, mark all three run lines ⏸️ rather than ✅ or ❌, keep the preflight line ✅ because it was attempted and reported, and state plainly that the bundle is not cleared to ship until the runs happen elsewhere) (-0.0072: artifact_set_exists_and_parses +1, canonical_serialization_and_integer_units +1, negative_missing_substantive_sections -3; healthy)
- ✅ Step 10 runs made from `exe_copy.py` copies only: its full output pasted (judge.toml validated against the rewardkit 0.2.1 schema, judge.toml deleted, tests-only reward.toml weight, network roles opened), scores recorded as TESTS-ONLY, both copies deleted, and the original confirmed unedited
- ✅ Every oracle or empty-run score claimed anywhere in the bundle (TRUTH.md included) is scoped to the test channel; no judged-channel oracle score is claimed, because none can exist (TRUTH.md lines 158-159 "No oracle score exists for Channel B"; Provenance scores null)
- ❌ Step 11: re-check done, coverage mapping complete both directions, zero overlap between tests and judged criteria (mapping complete and zero overlap, but four requirements have no checker: findings 6-9)
- ❌ All warn findings shown to the tasker and approved (findings 17-20 awaiting tasker approval)
- ✅ Sign-off recorded: reviewer name, date, bundle name, verdict (reviewer: Sisyphus, QC session district-heat-flex-procurement_v1_qc; 2026-10-21 IST; district-heat-flex-procurement; ❌ FAIL)

---

# Evidence appendix

## Step 0 preconditions

```
$ git -C ".../Terminal_2.0_Harbor_Harness" rev-parse HEAD
bde868c46994f4916e245b40d14f302b1341244a
$ diff -rq <original> <copy>
(no output, exit 0)
```

## Steps 1-4: scripts

### structure_qc.py

```
structure_qc: district-heat-flex-procurement
============================================================
pass [S1] bundle name format
pass [S2] all required files present
pass [S4] input directories data/ (14 files) all copied into the image
pass [S7] agent image copies nothing from outside environment/
pass [T1] task.toml parses
pass [T2] template shape, key order, environment_mode = separate
pass [T4] artifacts (absolute container paths): ['/app/out/derive_report.py', '/app/out/summary.json', '/app/out/policy_audit.json', '/app/out/data_quality.json', '/app/out/region_North.json', '/app/out/region_South.json', '/app/out/region_West.json', '/app/out/region_East.json', '/app/out/segment_commercial.json', '/app/out/segment_public.json']
pass [T14] [task] authors: 1 entry, valid shape
pass [T7] [metadata] category: 'Optimization' (no fixed vocabulary; whether it describes the dominant work is judged by reading)
pass [T12] network_mode pinned per role
pass [T13] pinned values exact
pass [T15] [verifier.env] judge wiring exact
pass [S8] every artifact directory is writable by uid 1000
pass [S9] openhands-sdk runtime pre-baked at /opt/openhands-sdk-venv
pass [S10] uid 1000 agent account with HOME created
pass [X1] no em/en dashes in text files
pass [X3] no file over 100 MB
============================================================
SUMMARY: 17 pass, 0 warn, 0 fail
VERDICT: PASS
exit=0
```

### instruction_qc.py

```
instruction_qc: district-heat-flex-procurement
============================================================
pass [C1] timeout sentence matches agent timeout (7200s)
pass [C2] no scripted machinery names
pass [C3] no 'reward'
pass [C4] every /app path resolvable through COPY/ADD exists
pass [C5] every declared artifact referenced
============================================================
SUMMARY: 5 pass, 0 warn, 0 fail
VERDICT: PASS
exit=0
```

### tests_qc.py

```
tests_qc: district-heat-flex-procurement
============================================================
pass [A1] test_output.py parses and imports criteria, criterion from rewardkit
pass [A2] no duplicate function names
pass [A4] every check is a top-level @criterion(description=...) function of workspace
pass [A5] no literal non-bool returns; every reading check guarded (trace by hand)
pass [W1] 41 module-level registrations
pass [W2] every weight is an integer on the locked scale
pass [W3] bijection checks <-> registrations
pass [W4] weights differentiate
pass [W5] 4 negative check(s)
pass [W6] negative_ prefix matches weight sign
pass [W7] positive total 139, negative total 16
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
pass [O1] oracle independent of the verifier (2% of solve.py's 402 substantive lines also appear in test_output.py)
pass [H1] util-linux installed for setpriv
pass [H3] /tests restricted from unprivileged readers
pass [H4] stale reward files cleared before grading
pass [H5] verifier log directory owned by root and not writable by others
WARN [A3] 41 checks; cap is 35 (warn)
============================================================
SUMMARY: 34 pass, 1 warn, 0 fail
VERDICT: WARN - tasker approval needed
exit=0
```

### judge_qc.py

```
judge_qc: district-heat-flex-procurement
============================================================
pass [G1] judge.toml parses (17 criteria)
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
pass [G3] 17 criteria
pass [G4] 2 negative criteria
pass [G5] weights differentiate
pass [G6] positive total 45, negative total 10
============================================================
SUMMARY: 19 pass, 0 warn, 0 fail
VERDICT: PASS
exit=0
```

Script results: structure_qc exit 0 (17 pass); instruction_qc exit 0 (5 pass); tests_qc exit 0 (34 pass, 1 WARN A3: 41 checks, cap 35); judge_qc exit 0 (19 pass). No script FAIL to re-verify. A3 re-verified by counting registrations in tests/test_output.py (see gate 03).

## Gate 01 - Instruction QC (instruction.md)

Files read in full: instruction.md (26 lines), task.toml, environment/Dockerfile, environment/data/schema.md (325 lines), environment/data/program.ini, tests/judge.toml (230 lines), tests/test_output.py (all 1569 lines; lines 57-70 are 14 zlib+base64 blobs, decoded and confirmed byte-identical to the 14 shipped files in environment/data/).

Verdict: ❌ FAIL (1 fail, 0 minors, 0 warns)

Findings

- ❌ IN-16 A graded count has two defensible readings and nothing in the contract picks one. schema.md lines 37-40: "it is skipped and counted, it is not a site row for any purpose, and the lines of `site_state.jsonl`, `continuity_waivers.csv`, `rate_cards.xml` and `recipient_weights.tsv` for its `event_id` and `site_id` are skipped." schema.md line 319: "`waiver_signed_missing`: waiver rows with an empty `waiver_signed`." Reading A (reference, test_output.py lines 175-177, counts before the `in site` filter): every data row of continuity_waivers.csv with an empty waiver_signed counts, including the skipped line of an unknown-region site. Reading B: the line of an unknown-region site is skipped, so it is never read and does not count. Checker: `mixed_rejection_counts_case` (weight 3, test_output.py lines 1450-1456) compares the whole data_quality.json on the `mixed_rows` extract, where site S-X has region code Z9 and an empty waiver_signed; I ran the test file's own reference in scratch: reference `waiver_signed_missing` = 3, skip reading = 2, so the check turns on this choice. Searched schema.md sections 1, 2, 9 and instruction.md for a tiebreak: none (the `rows` counts say "data rows" explicitly, waiver_signed_missing does not). Bug/Error. Fix: in environment/data/schema.md section 9 change the `waiver_signed_missing` line to "waiver rows with an empty `waiver_signed`, counted over every data row of `continuity_waivers.csv`, including lines skipped for an unknown-region site" (or change the reference and the case to the skip reading and say so).

Checklist

- ✅ IN-0 instruction_qc.py run, exit code and findings reported (exit 0, 5 pass, 0 warn, 0 fail; pasted in Steps 1-4)
- ✅ IN-S1..IN-S7 instruction_qc.py output read, and every failure it reports confirmed in the file and carried into the report (no failures reported)
- ✅ IN-F1 no em/en dashes anywhere in the file (script C-checks and structure_qc X1 pass; read all 26 lines, only hyphen-minus)
- ✅ IN-L1 register is everyday natural English, no banned or same-kind vocabulary (read every line; plain workplace words such as "pick", "work out", "keeping to"; no crucial/robust)
- ✅ IN-L2 grammar and spelling clean (British "programme" used consistently; no errors found)
- ✅ IN-L3 no AI-tell phrases; reads like a human colleague wrote it ("A district-heating company runs a winter demand-response programme.")
- ✅ IN-1 timeout sentence present and N == agent timeout_sec ("You have 7200 seconds to complete this task." vs task.toml `timeout_sec = 7200.0` under [agent])
- ✅ IN-2 no mention of tests/, solution/, grader, logs, reward (stating WHAT is judged is fine) ("It will also be run on other extracts in the same schema" states a deliverable requirement, not the mechanism; no grader/checker/test file named)
- ✅ IN-3 no instruction to write reward/log files (none)
- ✅ IN-4 no benchmark self-references or GUIDs (none)
- ✅ IN-5 no finding for unmentioned inputs; any path the prompt does name exists (`/app/data` and `/app/data/schema.md` land via `COPY data /app/data`; `/app/out/...` is agent-created, /app is `chown 1000:1000`)
- ✅ IN-6 exactly one landing place inferable for each declared artifact, both ways (all ten task.toml artifacts are spelled as exact paths in lines 3 and 5; no undeclared deliverable requested)
- ✅ IN-7 no tool named that the image does not install (obvious misses) ("Use only the Python 3.12 standard library"; image is python:3.12-slim)
- ✅ IN-8 everything the tests assert AND everything an outcome judged criterion demands is knowable from prompt, shipped spec or data (conduct criteria are exempt, see JD-15) (every report key, order, unit and rule the reference computes maps to schema.md sections 1-9; the 30 s limit and 22 sites x 4 offers are stated in instruction line 3 and schema.md section 3; R5/R13/R14/R15/R17/R10 ask exactly for the six reply items in instruction lines 19-24; the IN-16 case above is an ambiguity, not an unknowable expectation)
- ✅ IN-9 no answer or algorithm leak (withholding is fine; gate 02 DS-21 rules on anything you suspect is unreachable) (the reply items name topics, not values; no algorithm for the exact search is given)
- ✅ IN-10 online-lookup sentence: no check performed (tasker decision)
- ✅ IN-11 network wording matches the pinned offline contract (no fetch/download/ URL-as-source sentences; silence about the network is correct) (no network wording at all)
- ✅ IN-12 category names the dominant work; description honest; keywords/tags related (category "Optimization": the stated difficulty is the exact best portfolio over up to 22 sites x 4 offers, more than 10^15 portfolios, within 30 s; description's "thirteen linked files in seven formats" checked: 13 data files besides schema.md in ini/json/csv/tsv/fixed-width/jsonl/xml; keywords and tags all on-subject)
- ✅ IN-13 no internal contradictions, constraints jointly satisfiable (program lives in /app/out and writes its nine reports into OUT_DIR=/app/out; no conflicting sentence)
- ✅ IN-14 describes the end state and any rules of engagement, never a recipe that is the solution (bullets in lines 9-15 state required properties, not steps)
- ✅ IN-15 every graded rule of engagement is stated plainly enough to act on (no judge criterion carries `type = "instruction following"`; tests grading engagement rules: `negative_external_dependency_or_network` backed by "Use only the Python 3.12 standard library"; `negative_reads_tests_or_reward_files` backed by "Do not cheat")
- ❌ IN-16 nothing graded has two defensible readings the contract fails to settle (both readings written out, or no finding) (see Findings: waiver_signed_missing for skipped waiver lines)

## Gate 02 - Data, Environment & Solution QC

Files read in full: environment/Dockerfile, environment/data/schema.md, program.ini, solution/solve.sh, solution/solve.py (512 lines), tests/test_output.py (code lines), tests/judge.toml, instruction.md, task.toml; the 12 bulk data files were parsed and checked by script (claims below); solution/TRUTH.md opened last, after DS-21 was decided.

DS-21 conclusion recorded before opening TRUTH.md: solvable. Every graded value follows from a rule in schema.md sections 1-9 applied to the extract (ticks 2.3, ties 2.4, caps 2.5, labels 2.6, eligibility 3, the five components 5, credits 6, funded pool and largest remainder 7, report shapes 8-9); the 30 s / 22-site / 4-offer bound is stated (instruction line 3, schema section 3) and an exact state-merging or bound-based search is a known technique; no constant exists only in tests/ or solution/. The waiver_signed_missing ambiguity (gate 01 IN-16) leaves one reading reachable, so it is not unreachable information.

Verdict: ❌ FAIL (1 fail, 2 minors, 0 warns)

Findings

- ❌ DS-24 The oracle's graded search restates the verifier's own reference, including a dead knob that exists only to serve the verifier's wrong-reading switch. tests/test_output.py lines 279-302: `scale = wh_tick if "DH2" in lazy else 1` ... `cap_seg = {g: floors_here[g][0] * scale ...}` ... `# largest unit total whose ticks stay within each ceiling: tk(x) <= c  <=>  x <= scale * c + ceil(scale / 2) - 1` / `bound = [scale * c[0] + (scale + 1) // 2 - 1 for c in caps] + ...`. solution/solve.py lines 228-236, 262, 281-282: `def search_scale(ex: Extract) -> int: ... return 1`, `def search_units(offer, scale): if scale == 1: return offer.relief, offer.recovery / return offer.relief_wh, offer.recovery_wh` (unreachable branch), `floor_cap = [floor * scale for floor, _ in floor_of]`, `# half_up(x, scale) <= c exactly when x <= scale * c + ceil(scale / 2) - 1` / `caps = [scale * c + (scale + 1) // 2 - 1 ...]`. Both then run the same merge: state = 2n interval sums + one capped segment-relief slot per segment (test lines 294-304 vs solve.py 261-284), keep the lower `(cost_weight*cost, count)` per state, add `ways` on equality, take the extreme id tuple (test 320-325 vs solve.py 300-305), and score the final states with the same five-tuple (test 331-343 vs solve.py 310-321). tests_qc O1 reports 2% shared lines only because names were changed. The search decides the large, tick, tie and dup/range portfolio checks (large 26 + tick 25 + tie 3 + dup/range portfolio 10 + ordinary portfolios 5 = 69 of 139 points), so an oracle 1.000 there cannot disagree with the grader and proves nothing about it. TRUTH.md line 209-211 claims "the verifier, whose own reference was written separately". Bug/Error. Fix: rewrite the portfolio search in solution/solve.py as an independent method (for example a branch-and-bound over sites with an admissible lower bound and exact tie counting), delete `search_scale`/`search_units` and the `scale` arithmetic, and re-run Step 10 so the two implementations agreeing is evidence.
- 🟡 DS-22 TRUTH.md says the shipped data rejects no profile row, but it rejects 36. solution/TRUTH.md lines 69-71: "The shipped data never triggers items 1 and 3 to 10: ... and no profile or site row is rejected." Item 3 (lines 34-36) includes orphan profile rows; the shipped profiles.tsv has 36 rows whose offer_id is not in offers.csv (counted directly; also `orphan_profile_rows: 36` and `orphan_offer_rows: 14` from the test file's reference on the shipped data), e.g. `W26-6317-HX79794-Q 2 6000 0`. Bug/Error. Fix: in solution/TRUTH.md line 71 replace "no profile or site row is rejected" with "the only rejected rows are 14 orphan offers and their 36 orphan profile rows; no row is out of range, duplicated or in an unknown region".
- 🟡 DS-22 TRUTH.md Root cause describes the verifier's search, not solve.py. solution/TRUTH.md lines 172-174: "keeping the cheapest and then smallest partial portfolio per state, with a count of equal ones and the greatest and smallest sorted id tuples, is exact"; solve.py line 300/305 keeps one tuple per state (`prefer(held[3], entry[3])` = `max`); only test_output.py lines 320-325 keep both `lo` and `hi`. Bug/Error. Fix: in solution/TRUTH.md line 173 change "the greatest and smallest sorted id tuples" to "the greatest sorted id tuple".

Checklist

- ✅ DS-1 input in one or more named directories under environment/, each non-empty and COPYed; environment/ holds only the Dockerfile and those directories (structure_qc S4 "data/ (14 files) all copied into the image"; `COPY data /app/data`)
- ✅ DS-2 data necessary: task unsolvable without it (schema.md is the only rulebook; format checks compare /app/out key sets and array lengths against the reference on the shipped data, test lines 1096-1139)
- ✅ DS-3 every referenced file present, every claim about the data true (verified by script: sites (event_id, site_id) unique; site_state, waivers and rate cards one per site row; targets and feeder lines exactly one per event/region/interval (12000 = 500 events x 4 regions x 6 intervals); floors and pools at most one per key; codes upper case; region codes in other files all options of [region_codes]; every event_id known; fixed-width lines 37 chars as columns 1-37 state)
- ✅ DS-4 no answers or answer-derivable content in any environment/ input directory (schema.md has no worked values; data files are raw inputs; no output-shaped file)
- ✅ DS-5 no template residue, no redacted-spec pattern (TODO/FIXME/XXX/PLACEHOLDER sweep: data files 0 hits; hits only inside base64 blobs of tests/test_output.py lines 57-69, false positives)
- ✅ DS-6 data internally consistent with the task story (500 winter events of 6 intervals, 8 feeder codes in 4 regions, booleans typed, waiver statuses within the four values)
- ✅ DS-7 no em/en dashes in text data (structure_qc X1 pass)
- ✅ DS-8 Dockerfile copies nothing from tests/ or solution/ (only `COPY data /app/data`)
- ✅ DS-9 every input directory lands where the instruction says (conventionally /app/<dir>) (/app/data in instruction line 1 and Dockerfile line 26)
- ✅ DS-10 every needed tool/library installed in the image (python:3.12-slim; solve.py imports configparser, csv, json, sys, xml.etree, dataclasses, pathlib, all stdlib)
- ✅ DS-11 offline contract respected (every layer, oracle included, runs with no network) (solve.sh only mkdir/cp/python3; installs happen at build time)
- ✅ DS-12 no secrets, host paths, or machine-specific assumptions (base image pinned by public ECR digest; no secrets)
- ✅ DS-28 every artifact directory writable by uid 1000 in the agent image (`RUN mkdir -p /app && chown 1000:1000 /app` before COPY; /app/out is created by the agent or solve.sh `mkdir -p /app/out`; S8 pass)
- ✅ DS-29 openhands-sdk runtime pre-baked at /opt/openhands-sdk-venv with openhands-sdk/tools 1.55.1 and litellm 1.105.0 (any correct install style) (Dockerfile lines 6-23, single stage, not undone later; S9 pass)
- ✅ DS-30 uid 1000 agent account created with a home directory, and ENV HOME set (lines 3-4 right after FROM; python:3.12-slim has no uid 1000 user)
- ✅ DS-13 solve.sh present, entrypoint; solve.py optional
- ✅ DS-14 oracle computes the answer, does not paste it (solve.sh copies solve.py as the program and runs it on /app/data)
- ✅ DS-15 oracle would plausibly score 1.0 against the tests (walked every rule above against the reference; confirmed by Step 10)
- ✅ DS-16 oracle data reads confirmed legal (reads only argv[1] = /app/data)
- ✅ DS-17 oracle never touches tests/ (no /tests path in solve.sh or solve.py)
- ✅ DS-18 solve.sh idempotent (warn only) (`mkdir -p`, `cp` overwrite, program overwrites its nine files)
- ✅ DS-19 oracle respects the constraints the contract imposes on the agent, including rules of engagement stated in a shipped rules file (stdlib only; writes only /app/out)
- ✅ DS-20 oracle obeys every contract rule, wherever stated, including rules no test triggers (label order solve.py 214-225 = SAFETY_HOLD, COOLDOWN, CONTINUITY_WAIVED, CERTIFICATE_PENDING, CLEAR as 2.6; profile precedence 94-101 = orphan, out-of-range, duplicate as section 1; cap after uplift line 331; funded pool line 361; leftover cents by (remainder, id) descending line 352; per-value ticks 183-184; half-up line 21)
- ✅ DS-21 solvable from instruction.md + environment/ input alone (hard is fine; only genuinely unreachable information fails) (conclusion above, recorded before TRUTH.md)
- ❌ DS-22 TRUTH.md describes the shipped solution, the real grading and a defect list the bundle honours (read only after DS-21 was decided) (two minors: orphan profile rows claim, Root cause tuple claim; Verification counts all correct: 41 checks, +139/-16, 17 criteria +45/-10, group sums 4+11+15+26+25+23+8+27 = 139, 21 hand-built extracts; Provenance sha256 of solve.sh 44b69de8... and solve.py ef7f677b... match)
- ✅ DS-23 TRUTH.md unreachable by the agent: no Dockerfile route to it, never named in instruction.md
- ❌ DS-24 oracle is an independent implementation, not the verifier's own code (see Findings)
- ✅ DS-25 every literal the grading side requires of the output is findable in an agent-visible file (named file per literal) (75 distinct key and label literals from the reference outputs: 71 appear in schema.md; the other 4, `East`, `South`, `West`, `commercial`, are region and segment names from program.ini, as schema 8 says; the nine file names all appear in instruction.md line 5)
- ✅ DS-26 no answer-revealing artifact anywhere in the agent image, including /tmp, build stages and archive interiors (single stage; only apt packages, the openhands venv and /app/data)
- ✅ DS-27 TRUTH.md describes the task, with no narrative of how it was produced (no authored_by, no generator or tooling credits; Provenance holds ids and digests)

## Gate 03 - Tests QC (tests/)

Files read in full: tests/Dockerfile (9 lines), tests/test.sh (10 lines), tests/test_output.py (1569 lines; blobs decoded and confirmed identical to the shipped data), tests/reward.toml (7 lines); evidence: instruction.md, schema.md, task.toml, judge.toml. Hidden extracts were rebuilt in scratch from the file's own `case_spec`/`_ordinary_spec` to check them against the contract.

Verdict: ❌ FAIL (1 fail, 1 minor, 4 warns)

Findings

- ❌ TS-19 Two graded hidden extracts break the contract's stated size bound of 4 offers per site. instruction.md line 3: "Those extracts can hold an event and region with up to 22 sites and up to 4 offers per site"; schema.md lines 143-144: "up to 22 sites with candidate offers and up to 4 candidate offers per site". tests/test_output.py line 774 gives each large site `"ABCD"[:rng.pick([3, 4, 4, 4])]` offers and lines 781-783 then append a twin offer to an existing site: `for (index, letter), twin in zip(twins, "ZY"): ... offers.append(_offer(eid, source["sid"], twin, ...))`. Rebuilt in scratch: `large_tie` sites L08 and L14 carry 5 offers each, `large_tie_shuffled` site L01 carries 5. Checks graded on these extracts: `large_tie_count_case` (5) and `large_tie_greatest_tuple_shuffled_case` (5). An agent that sizes its search or its 30 s budget to the promised bound (fixed 4-mode encodings, a meet-in-the-middle split sized for 5 choices per site) can lose 10 of 139 points for trusting the contract. Re-verified a second time from the counts printed by the spec. Bug/Error. Fix: in tests/test_output.py `_large_spec`, add each twin only to a site whose original offer count is 3 (or pick the twin's source from 3-offer sites, and assert `max(offers per site) <= 4` inside `large_passes`), then re-run Step 10.
- 🟡 TS-14 `mixed_rejection_counts_case` grades far more than its name and description say. tests/test_output.py line 1450: description "Orphan, out-of-range, duplicate and unknown-region rows in one extract follow the stated order of rejection in data_quality.json."; lines 1453-1454 compare the whole object: `lambda f: json.dumps(f["data_quality.json"], sort_keys=True)`, which also settles the 12 `rows` counts, `waiver_signed_missing`, `ineligible_offer_count`, `empty_candidate_groups`, `zero_floor_count` and `unallocated_pool_count` (and so carries the gate 01 IN-16 ambiguity). Bug/Error. Fix: in tests/test_output.py change the observable to `_quality(f, "orphan_offer_rows", "orphan_profile_rows", "out_of_range_profile_rows", "duplicate_profile_rows", "unknown_region_site_rows")`, or rename the check and its description to say it grades the whole data_quality.json.
- ⚠️ TS-23 41 checks, over the cap of 35 (tests_qc A3 WARN, confirmed: 41 registrations at lines 1529-1569). Several are pairs on one extract (`large_20_*`, `large_22_*`, `duplicate_profile_row_*`, `out_of_range_interval_*`, `unknown_region_site_row_*`). Suggestion/Improvement. Fix: merge each same-extract pair whose second observable follows from the first (for example the two `large_20_*` and two `large_22_*` checks) or get tasker approval for 41.
- ⚠️ TS-16 `negative_reads_tests_or_reward_files` (-5) uses broad substrings. tests/test_output.py lines 1490-1491: `any(token in lowered for token in ("/tests", "/logs/", "test_output", "judge.toml", "reward.toml", "rewardkit"))`. An honest program with a variable or helper named `test_output`, or a debug path such as `/tmp/tests/` or `/var/logs/`, would be fined 5 points. Suggestion/Improvement. Fix: match whole path prefixes only (`"/tests/"` at a string start, `"/logs/verifier"`) and drop the bare `test_output` token.
- ⚠️ TS-24 A daemon started by the agent program can outlive its run and rewrite cached outputs that later checks re-read. tests/test_output.py lines 908-926: the run box is `box.chmod(0o777)` and the result folder is cached (`_CACHE[key] = result`); `os.killpg(proc.pid, signal.SIGKILL)` kills only the process group, so a grandchild that calls `setsid()` survives (as `nobody`). It cannot touch `/logs/verifier` (root:root 755) or `/tests` (go-rwx), so reward.json is not forgeable, but it could finish a slow computation past the 30 s limit and rewrite `out/` before a second check on the same extract (`large_*_interval_quantities_case`, `*_count_case`) re-reads it. Suggestion/Improvement. Fix: in `run_agent`, after the wait, read all nine JSON files into memory and cache the parsed dicts instead of the folder, then `chmod -R 0o555` / delete the box.
- ⚠️ TS-20 One edge-case check outweighs a core settlement check. `unknown_region_site_row_report_case` (weight 5, line 1564) grades only `site_count` and the label list on a 2-site extract; `ordinary_extract_segment_files_match` (weight 3, line 1534) grades every segment file of a 64-event-region extract including bid costs, credits and floor attainment. Suggestion/Improvement. Fix: in tests/test_output.py swap these two weights (report case 3, segment files 5).

Checklist

- ✅ TS-0 tests_qc.py run, exit code and findings reported (exit 0, 34 pass, 1 WARN A3)
- ✅ TS-S1..TS-S15 tests_qc.py output read, and every failure it reports confirmed in the file and carried into the report (no failures; the A3 warn carried as TS-23)
- ✅ TS-1 no unconditional reads of agent input paths under tests/ (guarded reads are fine) (no /app/data read; shipped data rebuilt from `_SHIPPED_DATA` in `visible_root()`)
- ✅ TS-2 tests/Dockerfile has COPY . /tests/, pins harbor-rewardkit==0.2.1 and sets LITELLM_LOCAL_MODEL_COST_MAP=True (lines 5-7)
- ✅ TS-3 tests/Dockerfile has RUN mkdir -p /app (warn if absent) (line 8)
- ✅ TS-4 all check dependencies and invoked tools installed in the verifier image, Python >= 3.12 (imports all stdlib; `setpriv` from util-linux line 3; python:3.12-slim)
- ✅ TS-5 ground truth self-contained in tests/ (reference implementation, seeded generators and embedded data all in test_output.py)
- ✅ TS-6 test.sh hardens, then ends with exec rewardkit; writes no reward bytes, nothing after rewardkit, never trusts a reward file on disk (lines 4-10 match the template)
- ✅ TS-7 reward computed only from tests/ truth + declared artifacts (reads /app/out/*.json and runs /app/out/derive_report.py, all declared)
- ✅ TS-8 no skip switches
- ✅ TS-9 no agent-writable source/exec, not PATH-shadowable (agent program run with `sys.executable` and absolute script path; setpriv by name from the root-owned image PATH)
- ✅ TS-10 reward.toml shape exact, weights = 0.5 / positive total per channel at full precision, no clamp (0.5/139 = 0.0035971223021582736, 0.5/45 = 0.011111111111111112, recomputed)
- ✅ TS-11 tests deterministic (all generators use the seeded `Rng`; dict iteration is insertion-ordered, sets only used for membership/length; tempdir names never graded; the 30 s run limit is the stated contract; `_LOCK` serialises agent runs and reference work so they do not compete for CPU; confirmed by five identical oracle runs in Step 10)
- ✅ TS-12 outcome-driven, no history/console grading (agent stdout/stderr go to DEVNULL)
- ✅ TS-13 one property per test (multi-field observables are one rule each, e.g. `cap_after_uplift_case` = capped credit + its cap-binding count)
- ❌ TS-14 names state properties (<property> / negative_<cheat>), prefix iff negative weight (minor: `mixed_rejection_counts_case` description narrower than its body)
- ✅ TS-15 negative checks return True when the cheat happened, with inline comment (lines 1470, 1484, 1498, 1518 "True means the cheat happened")
- ❌ TS-16 negatives fire on the cheat and only the cheat (warn: broad tokens in `negative_reads_tests_or_reward_files`; the other three cannot fire on honest work: hardcoded check needs the shipped summary on a different extract, import check uses `sys.stdlib_module_names` which contains `__future__`, hollow-summary check needs a missing required key)
- ✅ TS-17 exact comparisons where exactness promised (bool/int trap checked) (region and grant views compare `json.dumps` strings, so `true` vs `1` differ; whole-file `==` comparisons could accept `true` for 1 but `canonical_serialization_and_integer_units` rejects bools and floats in the same program's output)
- ✅ TS-18 tolerances stated in instruction where used (no tolerances; all integers)
- ❌ TS-19 no obvious contract/test contradiction, checking the shipped spec as well as the prompt; a promise a judged criterion grades is covered (deep pass in Gate 05) (fail: 5 offers per site in two large extracts)
- ❌ TS-20 weights map to importance semantically, ordering matches the instruction (warn: unknown-region report 5 vs ordinary segment files 3)
- ✅ TS-25 no positive test grades an absence (every positive compares produced values or requires files and keys to exist)
- ✅ TS-26 no test pair (any signs) pays twice for one observable (paired checks read different fields: ids vs intervals, portfolio vs count, count vs site_count/labels; checks of one rule on different extracts read different observables)
- ✅ TS-21 bijection check functions <-> criteria.<name>(weight=W) registrations, each registered once; no test_weights.json (W3 pass; 41 functions, 41 registrations)
- ✅ TS-22 registered weights are integers within {5,3,1,-1,-3,-5} (W2 pass)
- ❌ TS-23 counts and balance: >=10 checks, <=35 (warn), >=1 positive, >=1 negative, weights not all identical, sum|neg| <= sum pos (warn: 41 checks; +139 / -16 balance fine)
- ❌ TS-24 verifier execution isolation (reward not forgeable by executed agent code) (reward not forgeable: subprocess with 30 s timeout, `setpriv --reuid=nobody`, output to DEVNULL, `killpg` then `wait`; warn for the cached-output rewrite vector)
- ✅ TS-27 no positive test paying for source tokens instead of behaviour (source is read only by the two negatives)
- ✅ TS-28 verifier hardening present where grading executes agent code, or explicitly reasoned as not needed (grading executes agent code; util-linux installed, `chmod -R go-rwx /tests`, stale reward files removed, `/logs/verifier` root:root 755)
- ✅ TS-29 no check can raise on bad, missing or hostile agent output; every check returns a bool (every check body wrapped in `try ... except Exception: return False`; module level only defines constants, functions and registrations)

## Gate 04 - Judge criteria QC (tests/judge.toml)

Files read in full: tests/judge.toml (17 criteria, 230 lines); evidence: solution/solve.sh, solution/solve.py, tests/test_output.py with registrations, tests/reward.toml, instruction.md, environment/data/schema.md.

Classification (JD-15), each read from its description: R1, R2, R3, R6, R7, R8 conduct, odds-raising (they serve schema.md sections 1-9, the unknown-region rule at schema line 37, the cap rule 2.5/6 that the shipped data never triggers (cap_binding_count 0), the remainder ties of section 7, and "must not depend on the shipped records" in instruction line 3); R4 conduct, preference; R9 conduct, code quality (JD-18); R11, R12 conduct negatives on misconduct (grader reads, fabricated verification); R16 conduct, serves instruction line 5 "Run it on the shipped data so these files exist"; R5, R10, R13, R14, R15, R17 outcome, tracing to instruction lines 19, 24, 20, 21, 22, 23 and to schema.md sections 7, 2.3, 2.6/7 and 1. No criterion is a constraint; none carries `type = "instruction following"`, and none needs it.

Verdict: ❌ FAIL (2 fails, 2 minors, 0 warns)

Findings

- ❌ JD-7 R9 is not satisfied by the reference solution: the oracle's own derive_report.py carries dead code. tests/judge.toml line 118: "The agent writes derive_report.py with descriptive function names, specific exception types in every except clause and no dead or duplicated code blocks." solution/solve.py (copied to /app/out/derive_report.py by solve.sh line 6) lines 228-236: `def search_scale(ex: Extract) -> int: ... return 1` and `def search_units(offer, scale): if scale == 1: return offer.relief, offer.recovery` / `return offer.relief_wh, offer.recovery_wh`, whose second return can never run because `scale` is always 1; `measure()` (line 264) is `half_up(total, 1)`, an identity, and `report_ticks` (line 325) never uses its `ex` parameter. A judge applying R9 to the oracle's program answers no. Re-verified by reading every caller of `search_scale` (only line 255). Bug/Error. Fix: delete `search_scale`, `search_units`, the `scale` arithmetic and the unused `ex` parameter from solution/solve.py (this is also the DS-24 fix), so the reference program meets R9.
- ❌ JD-6 R10's key condition cannot be decided from what the judge sees. tests/judge.toml line 131: "The response names at least one contract rule that the shipped data never exercised." with `evaluation_target = "user_facing_message"` and `type = "factuality and hallucination"`. Whether a rule is exercised depends on /app/data, which the judge never receives; the shipped data leaves many rules unexercised (no ties, no cap-binding offer, no CONTINUITY_WAIVED label, no duplicate, out-of-range or unknown-region row, every profile and target Wh value a multiple of 1000) but also exercises others (36 orphan profile rows, 1054 pools with residual ties), so a reply naming "residual ties" is wrong and the judge cannot tell it from a right one. Bug/Error. Fix: in tests/judge.toml change R10 to `evaluation_target = "trajectory"` with description "The agent runs a command on /app/data that shows zero records triggering a named schema.md rule.", so the evidence sits where the judge can read it.
- 🟡 JD-5 R9 bundles three separate observables. tests/judge.toml line 118: "descriptive function names, specific exception types in every except clause and no dead or duplicated code blocks"; a program with good names and a bare `except` leaves the judge no partial verdict. Bug/Error. Fix: split R9 into two criteria, for example "The agent writes derive_report.py whose except clauses each name a specific exception type." and "The agent writes derive_report.py with no unreachable or duplicated code blocks.", keeping the weights within the 45 positive total.
- 🟡 JD-15 R4 is a preference, not an odds-raising method. tests/judge.toml line 53: "The agent states the five objective components and the final tie rule in its own words before coding the optimiser." (weight 3). Two agents that both implement section 5 exactly, one of which restated it in prose first, are equally good; writing the restatement does not change the program. Bug/Error. Fix: replace R4 with an observable that raises the odds, for example "The agent compares its optimiser with plain enumeration on at least one event-region of six or more sites before concluding.", or drop it and move its 3 points elsewhere.

Checklist

- ✅ JD-0 judge_qc.py run, exit code and findings reported (exit 0, 19 pass)
- ✅ JD-S1..JD-S13 judge_qc.py output read, and every failure it reports confirmed in the file and carried into the report (no failures; weights.judge 0.011111111111111112 = 0.5/45 checked in gate 03)
- ✅ JD-1 prefix matches evaluation_target for every criterion (R5, R10, R12, R13, R14, R15, R17 "The response" with user_facing_message; the other ten "The agent" with trajectory)
- ✅ JD-2 positive grammar everywhere, no banned tokens (read all 17; "no dead or duplicated" uses "no", not a banned token)
- ✅ JD-3 no vague qualifiers (counts given where needed: "at least six", "at least one"; "small hand-made case" describes the artefact, not a threshold)
- ✅ JD-4 no brackets, placeholders, tag prefixes, em/en dashes
- ❌ JD-5 one observable per criterion (minor: R9)
- ❌ JD-6 every criterion decidable from evidence (fail: R10)
- ❌ JD-7 every criterion true of / avoided by the reference solution (fail: R9 vs solve.py dead code; checked the rest: R16 = solve.sh line 7 runs the final program on /app/data; R5 = solve.py line 361 `max(0, pool - credit_total)`; R13 = lines 183-184 per-value `half_up`; R14 = line 338 doubles only when `label_for(site) == "CONTINUITY_WAIVED"`; R15 = lines 98-101 keep the first row; R11/R12 avoided, the oracle never touches /tests and makes no claim)
- ✅ JD-8 zero overlap with deterministic tests (observable-level) (R5/R13/R14/R15/R17 read the closing message, the tests read program output on hidden extracts; R11 reads shell commands, `negative_reads_tests_or_reward_files` reads program source; R9 reads naming, except clauses and dead code, `negative_external_dependency_or_network` reads imports; R16 reads the order of the last edit and the last run, `artifact_set_exists_and_parses` reads file existence)
- ✅ JD-9 the judged criteria add process value beyond the tests (R1-R3, R6-R8, R16 watch how the agent worked; R11, R12 watch boundaries and honesty)
- ✅ JD-10 no contradiction with the instruction
- ✅ JD-11 negatives target this task's real cheat surface (R11 grader reads, R12 claiming verified output after a failing last run; hardcoding is on the test side)
- ✅ JD-12 counts and balance: >=8, <=35 (warn), >=1 positive and >=1 negative weight, weights not all identical, sum|neg| <= sum pos (17 criteria; +45 / -10)
- ✅ JD-13 importance/weight pairing holds by |weight| and magnitudes match semantic importance (15 positives important at 3; R11, R12 critically_important at -5, red lines)
- ✅ JD-14 no criterion pair (negative or positive) pays twice for one act (each pair reads a different act: R1 reading vs R4 restating, R2 sampling vs R3 code check, R6 cap case vs R7 remainder case, R8 second-input comparison vs R16 final run, R12 honesty of the claim vs R16 the run itself)
- ❌ JD-15 every criterion classified as outcome, constraint or conduct; outcome criteria trace to the contract (instruction plus any spec file it points to); conduct criteria hold for every competent route or earn their narrowing by raising the odds of a correct end state, and each serves a real requirement; constraint criteria are exempt from both tests (minor: R4 preference at 3; all six outcome criteria trace to instruction lines 19-24 and schema.md)
- ✅ JD-16 each constraint criterion quotes its stated sentence and names the file it lives in, fits one of the six kinds, carries annotations type "instruction following", covers exactly one rule, and is graded once by the layer that should own it (a rule a test could have checked belongs to the tests) (no constraint criteria; the stated stdlib-only rule is graded by the test `negative_external_dependency_or_network`)
- ✅ JD-17 deleting every constraint still leaves a substantial task (no restrictive constraint criteria; the task is the exact search plus settlement)
- ✅ JD-18 at least one criterion judges the quality of the code the agent writes (name it), or the task authors no code and the line says so (R9 `r9_code_quality`)

## Gate 05 - Alignment & Integrity QC (whole bundle)

Method for the trigger-depth and partial-credit checks: in scratch (/tmp/opencode-logs/district-heat-flex-procurement-qc-20261021T1856/sim.py) the test file's own `reference()` was plugged in as the "agent" (its `run_agent` replaced by a function that writes the reference's reports for the extract it is given) and every registered check was scored. Sanity row: the unmodified reference scores 139/139. Each wrong reading was then switched on, one at a time, using the file's own `lazy` flags or a one-line patch of the reference, and the test-channel score recorded:

| Wrong reading | Test score | Checks lost |
|---|---|---|
| none (reference) | 139/139 = 1.0000 | - |
| DH2 raw Wh inside the search | 114/139 = 0.8201 | the five tick_* cases |
| DH3 raw pool shared | 113/139 = 0.8129 | five funded_* cases + ordinary summary |
| DH4dup / DH4range / DH4unknown | 128/139 = 0.9209 each | the two or three checks of that rule + mixed |
| H1 / H1order / DH5raw / DH5none / DH5ben | 0.8849 / 0.9424 / 0.9424 / 0.9065 / 0.9640 | waiver cases |
| H2 / H3 / H4 / H5c / H5t | 0.8705 / 0.9424 / 0.9424 / 0.9784 / 0.9784 | tie / cap / residual / rounding cases |
| held sites lose candidates | 128/139 = 0.9209 | ordinary x3 |
| objective components 1<->2 / 2<->3 swapped | 0.9209 / 0.8849 | ordinary x3 (+ tick_floor) |
| objective components 3<->4 swapped | 139/139 = 1.0000 | none |
| objective components 4<->5 swapped | 139/139 = 1.0000 | none |
| component 5 (offer count) dropped | 139/139 = 1.0000 | none |
| COOLDOWN ranked above SAFETY_HOLD | 139/139 = 1.0000 | none |
| pending sites labelled CLEAR (no CERTIFICATE_PENDING) | 139/139 = 1.0000 | none |
| weight-0 beneficiaries listed with 0 cents | 139/139 = 1.0000 | none |
| waiver_signed_missing skips unknown-region lines (IN-16 reading B) | 136/139 = 0.9784 | mixed_rejection_counts_case |

Verdict: ❌ FAIL (6 fails, 0 minors, 0 warns; plus cross-references to gate 03 TS-19, gate 02 DS-22 and gate 04 JD-7 that are not counted again)

Findings

- ❌ AL-27 The SAFETY_HOLD-over-COOLDOWN step of the label ranking is never triggered. schema.md lines 129-130: "in this ranking from highest to lowest: `SAFETY_HOLD`, `COOLDOWN`, `CONTINUITY_WAIVED`, `CERTIFICATE_PENDING`, `CLEAR`". No graded extract has a site with both `safety_hold` and `cooldown` true where its label is compared (`held_waiver` S-HOLD has only hold, `cooldown_waiver` S-COOL only cooldown; label values are compared only in `waiver_precedence_case`); swapping the two scores 139/139. Bug/Error. Fix: in tests/test_output.py add a site with `hold=True, cool=True` to the `waiver` case spec and include its `site_label` in that case's observable.
- ❌ AL-27 The CERTIFICATE_PENDING label is never graded. schema.md line 151: "`CERTIFICATE_PENDING` when `routine_certificate_pending` is `Y`". `waiver_precedence_case` (lines 1193-1200) sees only CONTINUITY_WAIVED and CLEAR; the grant cases depend only on whether a weight doubles; the ordinary checks never compare `compliance_counts` or `site_labels`. A program that labels every pending site CLEAR scores 139/139. Bug/Error. Fix: in tests/test_output.py add a pending site with no valid waiver (for example `pending=True, status="EXPIRED"`) to the `waiver` case so its label and the count tables show CERTIFICATE_PENDING.
- ❌ AL-27 Objective components 4 and 5, and their place in the order, are never triggered. schema.md lines 167-180: "compared in this order ... 3. blended cost ... 4. overdelivery ... 5. the number of offers in the portfolio." Swapping components 3 and 4, swapping 4 and 5, or dropping component 5 all score 139/139: no graded extract has two feasible portfolios equal on components 1-3 that differ on overdelivery or offer count. Bug/Error. Fix: in tests/test_output.py add two hand-built cases, one where the two best portfolios tie on components 1-3 and differ in overdelivery (with the cheaper one overdelivering, so the 3-before-4 order also shows), and one where they tie on 1-4 and differ in offer count, each compared on `selected_offer_ids`.
- ❌ AL-27 "Beneficiaries with weight 0 receive nothing and are not listed" is never triggered. schema.md line 217. No hand-built grant case has a weight-0 recipient, and the ordinary checks compare only candidate counts, ids, intervals, segment files and totals, never `grants`; listing weight-0 beneficiaries with 0 cents scores 139/139. Bug/Error. Fix: in tests/test_output.py give one recipient `weight=0` in the `residual` case (whose observable already includes `grants`).
- ❌ CL-2 The judged channel pays a no-program forgery and pays a factual claim it cannot check. Test channel: a forger writing one plausible, correctly shaped file per declared path and a do-nothing derive_report.py earns only the four format checks, `artifact_set_exists_and_parses`, `canonical_serialization_and_integer_units`, `report_keys_match_schema`, `report_arrays_in_schema_order` = 4/139 = 2.9% (every value check reruns the program on unseen extracts; defensible). Judged channel: a closing message written from schema.md alone earns R5, R13, R14, R15 (rules stated in schema.md), R10 (names any rule) and R17 (states any size and seconds) = 18/45 = 40%. Total reward for no program: 0.5 x 4/139 + 0.5 x 18/45 = 0.2144, or 0.3478 if the forger also does the cheap reading steps R1, R2, R3 and runs its fake program after its last edit (R16). Against the simulated honest scores above (one rule wrong leaves 0.81-0.98 of the test channel), 0.21-0.35 of total reward is within the range of a weak genuine attempt, and R10 (`type = "factuality and hallucination"`) pays while claiming to grade a fact the judge cannot verify (gate 04 JD-6). Bug/Error. Fix: in tests/judge.toml reweight R5, R10, R13, R14, R15 and R17 to 1 each and tie R10 and R17 to trajectory evidence (R10 as in the JD-6 fix; R17 as "The agent runs derive_report.py on an extract it built with an event-region of 20 or more sites and prints the elapsed seconds"), moving the freed weight to conduct criteria that need the program to exist.
- ❌ CL-3 Three judged criteria grade sentences that can be copied from schema.md. R5 (judge.toml line 66) "the pool minus the event-region credit cents, and 0 when the credits exceed the pool" = schema.md lines 201-203 "The funded pool F is the grant pool minus the event-region's credit cents ..., or 0 when that difference is negative."; R13 (line 170) "rounds each Wh value to ticks before values are added together" = schema.md lines 108-110 "A Wh value read from any file becomes ticks ... as soon as it is read, before it is added to anything"; R15 (line 196) "the first of two repeated profile rows in file order is kept" = schema.md lines 13-14 and 51 ("`profiles.tsv` below uses the file order to decide which of two repeated rows is kept", "an earlier row with the same `offer_id` and `interval` was kept: a duplicate profile row"). 9 of 45 judge points cannot tell a solver from a transcriber. (R14 needs sections 2.6 and 7 combined, so it is derived, not copied.) Bug/Error. Fix: in tests/judge.toml replace R5, R13 and R15 with facts the agent has to produce, for example "The response states the total `grant_funded_cents` its program reported for the shipped data", or fold them into one weight-1 criterion.
- ❌ AL-1 Same defect as gate 03 TS-19 (two graded extracts carry 5 offers per site against the stated maximum of 4); not counted again.
- ❌ AL-6 Same defect as gate 04 JD-7 (R9 is false of the reference program); not counted again.
- ❌ AL-18 Same defects as gate 02 DS-22 (TRUTH.md line 71 "no profile or site row is rejected" against 36 orphan profile rows; line 173 tuple claim); not counted again.

Checklist

- ✅ AL-F0a no template residue (no unresolved markers; every file earns its place: 13 data files read by the program, schema.md is the contract, the embedded blobs rebuild the shipped extract for the format checks)
- ✅ AL-F0b data dependency holds (schema.md carries every rule; format checks need the shipped extract's 500 events and 10000 site rows)
- ✅ AL-F0c work dependency holds, no shortcut found (test channel: every value check reruns the program on extracts it has never seen; hardcoding the shipped summary is fined -5)
- ✅ AL-F0d no double scoring across tests and judged criteria (gate 04 JD-8 mapping; re-checked in Step 11)
- ✅ AL-F0e solvable from instruction.md + environment/ input alone: no information the agent needs is unreachable (hard is fine, only impossible fails) (gate 02 DS-21; the IN-16 ambiguity leaves one reading reachable)

- ✅ CL-1 every demanded action has a checker that looks at the action itself, not the agent's report of it (test or judged criterion named for each action) (write the program: run by every value check; run it on the shipped data: `artifact_set_exists_and_parses` + R16 in the trajectory; finish in 30 s on 22 sites: `run_agent` timeout 30 in the six large checks; stdlib only: `negative_external_dependency_or_network`; the reply items are reports by design, R5/R10/R13/R14/R15/R17)
- ❌ CL-2 forgery price computed as a share of the positive weight, every paying test named, the total judged defensible with reasons (test channel 4/139 = 2.9%, defensible; whole reward 0.2144-0.3478 with the judged reply criteria, fail)
- ❌ CL-3 no asserted value liftable verbatim from a shipped file, an instruction constant or a worked example (derivation is fine and expected) (tests: nothing liftable, every expected value comes from unseen extracts; judged: R5, R13, R15 liftable from schema.md)
- ✅ CL-4 one wrong fact costs about one fact: one-fact-wrong score computed, no almost-right answer scoring as entirely wrong (one rule wrong: 0.8129 (DH3, focal) to 0.9784 (H5t, H5c) of the test channel; one wrong data_quality field costs 3/139 = 0.9784; no single comparison settles more than 26 points)
- ✅ CL-5 every exact comparison's silent requirements (order, keys, path form, casing) either stated in the contract or compared insensitively, judged criteria read the same way (list orders: schema 8.1 "ascending by `event_id`", "ascending", 8.2 "ascending by `event_id` and then by region name", 8.4 "ascending by `event_id` and then `site_id`"; key sets: schema 8.1-9; region and segment names "from `program.ini`"; output file names: instruction line 5; JSON parsed before comparing, so whitespace and key order do not matter for values)
- ✅ CL-6 every shipped value the graded truth contradicts is signposted as suspect somewhere the agent can read (name the signpost) (no shipped value contradicts graded truth: values are graded only on unseen extracts, and the informational fields `mode_label` and event `name` are flagged "informational" in schema.md lines 28 and 43)
- ✅ CL-7 every path the instruction names exists in every graded corpus (/app/data and schema.md exist in the agent image; every hidden extract written by `write_extract` (lines 540-605) holds all 13 data files schema.md section 1 lists; schema.md itself is not in the hidden extracts, and nothing tells the program to read it: section 1 lists the 13 data files and section 9 counts 12 of them)
- ✅ CL-8 oracle needs no fallback that skips an instruction-required step (solve.py `.get(..., (0, 0))` defaults sit on keys schema.md says always exist or default to 0; no hardcoded values, no try/except)
- ✅ CL-9 test.sh and check setup never supply the value a later assertion measures (setup writes input extracts and runs the program; expected values come from `reference()` in memory; nothing writes into /app/out)
- ✅ CL-10 every asserted fact traced to an agent-visible file or a derivation from one; nothing load-bearing lives only in solution/ or tests/ (every reference rule maps to schema.md sections 1-9; constants `wh_per_tick` and `millicents_per_cent` come from each extract's program.ini; the 30 s limit is in instruction line 3)
- ❌ AL-1 every test and every outcome criterion promised by the contract (the instruction plus any spec file it points to); every constraint criterion quotes the instruction sentence it enforces; every conduct criterion holds for any competent route or earns its narrowing, and serves a real requirement (TS-19 cross-reference; conduct criteria per gate 04, R4 minor)
- ✅ AL-2 every instruction promise graded (instruction lines 3, 5, 9-15, 19-24 each mapped in Step 11)
- ✅ AL-3 exact shapes agree across the contract, tests, solution (read the shipped spec, not just the prompt) (gate 02 DS-25: 71 of 75 literals in schema.md, 4 from program.ini; solve.py writes the same keys)
- ✅ AL-4 no hidden graded behaviours beyond the contract
- ✅ AL-5 oracle would pass every test (rule-by-rule walk in gate 02 DS-15/DS-20; confirmed by Step 10)
- ❌ AL-6 judged criteria consistent with solution and instruction (R9 vs solve.py, see JD-7; R14 and R5 re-verified against solve.py lines 338 and 361)
- ❌ AL-27 every stated rule has a fixture that actually triggers it (precedence pairs traced) (four untriggered rules above; triggered pairs: COOLDOWN over CONTINUITY_WAIVED (`cooldown_waiver`, H1order), CONTINUITY_WAIVED over CERTIFICATE_PENDING (`waiver`, H1), objective 1 before 2 and 2 before 3 (ordinary), orphan/out-of-range/duplicate precedence (`mixed_rows`), funded pool after credits (`funded*`))
- ✅ AL-28 no penalty stacking: one action never fires more than one max-severity penalty across tests and judged criteria (hardcoding the shipped summary -> `negative_hardcoded_sample_answers` -5 only; naming grader paths in the program -> `negative_reads_tests_or_reward_files` -5; non-stdlib import -> -3; hollow summary -> -3; shell read of /tests -> R11 -5; false verified claim -> R12 -5; each a different act)
- ✅ AL-7 no unearned measured claims (TRUTH.md Provenance: `golden_score_measured: null`, "No oracle score exists for Channel B")
- ✅ AL-8 time claims plausible for the actual work (and any declared difficulty band fits it) (expert 360 min / junior 1080 min for 13 files in 7 formats, an exact search beyond 10^15 portfolios and about 40 interacting rules)
- ✅ AL-9 solution discussion confined to TRUTH.md/task.toml, none of it reachable by the agent
- ✅ AL-10 hardcoding vector closed (values graded only on unseen extracts; the shipped-summary replay is fined)
- ✅ AL-11 grade-time environment abuse closed (checks read only /app/out and their own scratch extracts)
- ✅ AL-12 grader influence via /app closed (derive_report.py only ever runs as a `nobody` subprocess; nothing under /app is imported)
- ✅ AL-13 answers not reconstructable without the work
- ✅ AL-14 reward path tamper-proof end to end (rewardkit is the only writer) (test.sh template; TS-29 guards; `/logs/verifier` root-owned 755 and the program runs as `nobody`; reward.toml matches 139 and 45)
- ✅ AL-15 pinned offline contract consistent across all layers (verifier and agent network lines excluded; silence about the network is expected)
- ✅ AL-16 artifact filenames consistent bundle-wide (task.toml artifacts = instruction line 3/5 = test `ARTIFACT_JSON` + `out/derive_report.py` = what solve.py writes)
- ✅ AL-17 timeout story coherent (7200 s in instruction and [agent]; verifier 2700 s covers 26 program runs of at most 30 s plus the reference work; Step 10 verifier durations below)
- ❌ AL-18 no stale references or wrong counts anywhere (DS-22 cross-reference)
- ✅ AL-19 no credential/secret exfiltration (only the pinned `${OPENAI_API_KEY:-}` placeholder)
- ✅ AL-20 no network exfiltration or supply-chain risk (no piped downloads; apt and pip at build time from pinned images)
- ✅ AL-21 no destructive or resource-abuse operations (test.sh `rm -f` limited to three reward files; scratch under tempfile)
- ✅ AL-22 no obfuscated payloads (the 14 base64 blobs are zlib data, decoded and byte-identical to environment/data; they are written as files, never executed)
- ✅ AL-23 no prompt injection in agent-visible files (schema.md read in full; data files swept for model-directed text, 0 hits)
- ✅ AL-24 filename-keyed shortcut closed (hidden extracts use the same file names with new content)
- ✅ AL-25 nondeterministic-output shortcut closed (26 extracts compared exactly)
- ✅ AL-26 category names the dominant work; description honest; keywords/tags related (as IN-12)

## Step 10 - Execution gate

Scores are TESTS-ONLY, per the kit: exe_copy.py validated tests/judge.toml against the rewardkit 0.2.1 schema and did not execute it; no OpenAI key was set (runs launched under `env -u OPENAI_API_KEY`), so the judged channel was never scored and the stub score covers the test channel only. The network was opened to "public" and the OpenHands pre-bake dropped in the two copies only; the bundle under review still declares `no-network` / `allowlist` and keeps its pre-bake. Harbor 0.24.0, harbor-rewardkit 0.2.1 (tests/Dockerfile pin).

Verdict: ✅ PASS (0 fails, 0 minors, 0 warns)

Preflight:

```
$ harbor --version
0.24.0
$ docker ps
CONTAINER ID   IMAGE                                                  ...  NAMES
558f966b16be   emberforge-vault-settlement__2ywfgxe__env-main         ...  (another session)
42b182749587   harbor-prebuilt:harbor-docker-egress-control-sidecar-- ...
c29fd964678d   schema-migration-plan-repair__dndzsqs__env-main        ...  (another session)
a680a9ac4d01   harbor-prebuilt:harbor-docker-egress-control-sidecar-- ...
0ea9aa2a17da   district-heat-flex-procurement__qscx9s4__env-main      ...  (another session, 2 hours old; not touched)
fd04ce094333   harbor-prebuilt:harbor-docker-egress-control-sidecar-- ...
$ ls ".../QC_2026-10-21/bundles/district-heat-flex-procurement"
environment  instruction.md  solution  task.toml  tests
```

TS = 20261021T1921. `harbor run --help` confirmed `--path/-p`, `--agent/-a`, `--env/-e`, `--job-name`, `--jobs-dir/-o`, `--yes/-y`.

exe_copy.py, RUN copy (exit 0):

```
[exe-copy] copied /Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/district-heat-flex-procurement -> /private/tmp/oracle-qc/district-heat-flex-procurement-20261021T1921/run/district-heat-flex-procurement
[exe-copy] tests/judge.toml loads under the rewardkit 0.2.1 schema (validated, not executed)
[exe-copy] deleted tests/judge.toml
[exe-copy] tests/reward.toml -> weights = { test_output = 0.007194244604316547 } (1 / positive total 139)
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

exe_copy.py, STUB copy (`--stub`, exit 0): identical lines with the stub destination, plus `[exe-copy] solution/ replaced by a stub solve.sh creating 10 empty artifact(s)`; exit=0. P = 139.

Commands (chained under one `nohup bash -c '...; echo ALL_DONE'`, log /tmp/opencode-logs/district-heat-flex-procurement-step10-20261021T1921/runs.log):

```
harbor run --path "/tmp/oracle-qc/district-heat-flex-procurement-20261021T1921/run/district-heat-flex-procurement" --agent oracle --env docker --job-name oracle-N -o "/tmp/harbor-jobs-qc/district-heat-flex-procurement-20261021T1921" -y   (N = 1..5)
harbor run --path ".../run/district-heat-flex-procurement" --agent nop --env docker --job-name nop-1 -o "/tmp/harbor-jobs-qc/district-heat-flex-procurement-20261021T1921" -y
harbor run --path "/tmp/oracle-qc/district-heat-flex-procurement-20261021T1921/stub/district-heat-flex-procurement" --agent oracle --env docker --job-name stub-1 -o "/tmp/harbor-jobs-qc/district-heat-flex-procurement-20261021T1921" -y
ALL_DONE Wed Oct 21 19:51:46 IST 2026
```

Results, read from each trial's result.json `verifier_result.rewards.reward` and verifier/reward.json (no `exception_info`, no exception.txt in any trial):

| Agent | Run | Trial | result.json reward | verifier/reward.json | Verifier time |
|---|---|---|---|---|---|
| oracle | oracle-1 | district-heat-flex-procurement__nHqQbSN | 1.0 | {"reward": 1.0} | 4m14s |
| oracle | oracle-2 | district-heat-flex-procurement__DH2ndf7 | 1.0 | {"reward": 1.0} | 3m36s |
| oracle | oracle-3 | district-heat-flex-procurement__HfDpwLU | 1.0 | {"reward": 1.0} | 2m20s |
| oracle | oracle-4 | district-heat-flex-procurement__ai2vzkD | 1.0 | {"reward": 1.0} | 2m49s |
| oracle | oracle-5 | district-heat-flex-procurement__q6uZR2F | 1.0 | {"reward": 1.0} | 1m58s |
| nop | nop-1 | district-heat-flex-procurement__DYTmZdW | 0.0 | {"reward": 0.0} | 0m48s |
| oracle on stub | stub-1 | district-heat-flex-procurement__APawoPg | -0.0072 | {"reward": -0.0072} | 1m04s |

All five oracle runs read exactly 1.000 (oracle-1 reward-details: channel score 139.0, 37 of 37 positives paid, no negative fired); nop reads exactly 0.000 (no check non-zero). No failing check, no rewardkit crash, no disagreement across the five oracle runs. Verifier times are far inside `[verifier] timeout_sec = 2700.0` (AL-17).

Stub solve.sh (STUB copy, in full):

```
#!/bin/bash
set -euo pipefail
P=/app/out/derive_report.py; mkdir -p "$(dirname "$P")"; : > "$P"
P=/app/out/summary.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/policy_audit.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/data_quality.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/region_North.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/region_South.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/region_West.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/region_East.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/segment_commercial.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/segment_public.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
```

stub-1 checks with a non-zero value (verifier/reward-details.json): `artifact_set_exists_and_parses` (weight 1, value 1), `canonical_serialization_and_integer_units` (weight 1, value 1), `negative_missing_substantive_sections` (weight -3, value 1). Channel score -1.0, reward -1/139 = -0.0072. No retry was needed (stub-1 scored rather than errored).

Stub judgement: healthy. The stub was paid 2 of P = 139 (1.4%) by two existence/serialisation checks that claim nothing more than that (an empty `{}` really is a sorted, integer-only object), and the hollow-summary negative took 3 back, so faking the shape costs. Every value check reran the empty derive_report.py, which exits 0 without creating OUT_DIR, so `run_agent` returned None and all 33 value checks read 0. This agrees with the gate 05 CL-2 test-channel forgery price of 4/139 = 2.9% (a forger with correctly keyed files would also collect `report_keys_match_schema` and `report_arrays_in_schema_order`); the stub run says nothing about the judged channel, where CL-2 found the problem.

diff -rq bundle vs RUN copy:

```
Files .../bundles/district-heat-flex-procurement/environment/Dockerfile and /tmp/oracle-qc/district-heat-flex-procurement-20261021T1921/run/district-heat-flex-procurement/environment/Dockerfile differ
Files .../task.toml and .../run/district-heat-flex-procurement/task.toml differ
Only in .../bundles/district-heat-flex-procurement/tests: judge.toml
Files .../tests/reward.toml and .../run/district-heat-flex-procurement/tests/reward.toml differ
```

diff -rq bundle vs STUB copy:

```
Files .../environment/Dockerfile and .../stub/district-heat-flex-procurement/environment/Dockerfile differ
Only in .../bundles/district-heat-flex-procurement/solution: TRUTH.md
Only in .../bundles/district-heat-flex-procurement/solution: solve.py
Files .../solution/solve.sh and .../stub/district-heat-flex-procurement/solution/solve.sh differ
Files .../task.toml and .../stub/district-heat-flex-procurement/task.toml differ
Only in .../bundles/district-heat-flex-procurement/tests: judge.toml
Files .../tests/reward.toml and .../stub/district-heat-flex-procurement/tests/reward.toml differ
```

Only the allowed differences appear.

Cleanup: deleted /tmp/oracle-qc/district-heat-flex-procurement-20261021T1921 only (`ls` now reports "No such file or directory"). Bundle under review afterwards: tests/ holds Dockerfile, judge.toml, reward.toml (`weights = { test_output = 0.0035971223021582736, judge = 0.011111111111111112 }`), test.sh, test_output.py; solution/ holds TRUTH.md, solve.py, solve.sh; task.toml still `allowlist` x3 and `no-network`; environment/Dockerfile still carries the openhands block; `diff -rq` against the original bundle prints nothing (exit 0); no `__pycache__` in the bundle or the kit.

Jobs folder (kept as evidence): /tmp/harbor-jobs-qc/district-heat-flex-procurement-20261021T1921

## Step 11 - Final coverage and overlap re-check

Re-derived from instruction.md, environment/data/schema.md (the spec the instruction names as "the authority on every rule, unit and output field"), tests/test_output.py (checks and registrations, lines 1072-1569) and tests/judge.toml, not from the gate verdicts. Where the mapping needed to know whether an input actually triggers a rule, the scratch scoring table in gate 05 was used as evidence.

Verdict: ❌ FAIL (0 new fails; it confirms gate 05 AL-27 x4 and gate 03 TS-19, which are counted there)

### Coverage

Requirement -> checker (instruction = I, schema.md = S):

| # | Requirement (file, line/section) | Checker(s) |
|---|---|---|
| 1 | Program at /app/out/derive_report.py, `python3 ... DATA_DIR OUT_DIR` (I line 3; S 8) | every value check via `run_agent` (line 911 runs exactly that command); `artifact_set_exists_and_parses` (1) |
| 2 | Reusable on other extracts, no dependence on shipped records (I line 3) | all 26 hidden-extract checks; `negative_hardcoded_sample_answers` (-5) |
| 3 | Up to 22 sites x 4 offers, each run within 30 s (I line 3; S 3) | `large_20_*`, `large_22_*`, `large_tie_*` (26 points, 30 s limit in `run_agent`); R17 (report) |
| 4 | Python 3.12 standard library only (I line 3) | `negative_external_dependency_or_network` (-3) |
| 5 | Run on shipped data so the nine files exist (I line 5) | `artifact_set_exists_and_parses`, `report_keys_match_schema`, `report_arrays_in_schema_order`; R16 |
| 6 | Exact best portfolio, interval limits, one mode per site (I line 9; S 5) | `ordinary_extract_portfolios_match`, the six large checks, `tick_feasibility_case`, `tick_recovery_ceiling_case`, `tie_break_greatest_tuple_case` |
| 6a | Component 1 shortfall, 2 floor deficit, 3 blended cost (S 5) | ordinary checks (1<->2, 2<->3 swaps lose 11 and 16 points), `tick_shortfall_order_case`, `tick_floor_deficit_case` |
| 6b | Component 4 overdelivery and component 5 offer count, in that order after 3 (S 5 lines 179-180) | NONE (3<->4 swap, 4<->5 swap and dropping 5 all score 139/139) -> gate 05 AL-27 |
| 7 | Cost, credits and grants as separate figures (I line 10; S 6, 8.1) | `ordinary_extract_segment_files_match` (bid_cost_cents, credit_cents), `cap_after_uplift_case`, funded checks |
| 8 | Funded = allocated + unallocated (I line 11; S 7) | funded checks (`grant_view` reads all three), `ordinary_extract_summary_and_totals_match` |
| 9 | Summary agrees with region and segment files (I line 12; S 8.3) | `ordinary_extract_summary_and_totals_match` (summary + four region totals), `ordinary_extract_segment_files_match` |
| 10 | Integer ticks, cents, basis points; no floats or booleans (I line 13; S 2.1, 8) | `canonical_serialization_and_integer_units`; every value comparison |
| 11 | Sorted keys, trailing newline, array orders (I line 14; S 8.1-8.4) | `canonical_serialization_and_integer_units`, `report_arrays_in_schema_order`; list comparisons in the value checks |
| 12 | Empty groups, missing optional fields, zero denominators (I line 15; S 9) | `mixed_rejection_counts_case` (empty_candidate_groups 3, waiver_signed_missing, zero_floor_count, unallocated_pool_count); floor_attainment 10000 at floor 0 in `ordinary_extract_segment_files_match` |
| 13 | Rejected rows: orphan, out-of-range, duplicate in that order; unknown-region sites (I line 15; S 1) | `duplicate_profile_row_*`, `out_of_range_interval_*`, `unknown_region_site_row_*`, `mixed_rejection_counts_case` |
| 14 | Exact boundaries and half-up rounding (I line 15; S 2.2, 2.3) | `tick_feasibility_case` (two 15 Wh = 4 ticks over a 34 Wh = 3 tick ceiling), `per_value_tick_quantisation_case`, `funded_pool_after_site_rounding_case` (two half cents) |
| 15 | Ties: greatest sorted id tuple; tied_portfolio_count (S 2.4, 5, 8.4) | `tie_break_greatest_tuple_case`, `tick_created_tie_case`, `large_tie_count_case`, `large_tie_greatest_tuple_shuffled_case` |
| 16 | Cap binds base + uplift; cap_binding_count (S 2.5, 6) | `cap_after_uplift_case`, `funded_pool_after_capped_credit_case` |
| 17 | Funded pool after credits, floored at 0 (S 7) | `funded_pool_case`, `funded_pool_after_capped_credit_case`, `funded_pool_residual_tie_case`, `funded_pool_after_site_rounding_case`, `funded_pool_waived_weight_case` |
| 18 | Largest remainder, leftover cents by remainder then descending id; residual cents and residual ties (S 7, 2.4, 8.4) | `residual_ties_descending_id_case`, `funded_pool_residual_tie_case` |
| 19 | Weight-0 beneficiaries receive nothing and are not listed (S 7 line 217) | NONE (listing them with 0 cents scores 139/139) -> gate 05 AL-27 |
| 20 | Waived recipients count twice only when labelled CONTINUITY_WAIVED (S 7, 2.6) | `held_waiver_weight_case`, `cooldown_waiver_weight_case`, `funded_pool_waived_weight_case` |
| 21 | Label CONTINUITY_WAIVED over CERTIFICATE_PENDING; COOLDOWN over CONTINUITY_WAIVED; SAFETY_HOLD over CONTINUITY_WAIVED (S 2.6) | `waiver_precedence_case`; `cooldown_waiver_weight_case`; `held_waiver_weight_case` |
| 21a | SAFETY_HOLD over COOLDOWN; the CERTIFICATE_PENDING label itself (S 2.6, 4) | NONE (both variants score 139/139) -> gate 05 AL-27 |
| 22 | Eligibility by dispatch_authorized only; labels never change eligibility (S 3) | `mixed_rejection_counts_case` (ineligible_offer_count), ordinary checks (held sites losing candidates loses 11) |
| 23 | data_quality row counts for 12 files (S 9) | `mixed_rejection_counts_case` |
| 24 | Region codes resolve through [region_codes]; any code of the region in targets/feeders/floors/pools (S 1) | every hidden extract (`write_extract` alternates N1/N2 etc., lines 594-602) |
| 25 | Reply: funded-pool cents (I line 19) | R5 |
| 26 | Reply: energy rounding in the search (I line 20) | R13 |
| 27 | Reply: waived recipient weight (I line 21) | R14 |
| 28 | Reply: which repeated profile row is kept (I line 22) | R15 |
| 29 | Reply: largest event-region run and its seconds (I line 23) | R17 |
| 30 | Reply: a rule the shipped data never exercises (I line 24) | R10 |
| 31 | Do not cheat (I line 26) | R11 (-5), `negative_reads_tests_or_reward_files` (-5) |

Requirements with no checker: 6b, 19, 21a (four rules, reported as gate 05 AL-27 fails).

Test -> the sentence it enforces:

| Test (weight) | Sentence and file |
|---|---|
| artifact_set_exists_and_parses (1) | I line 5 "Run it on the shipped data so these files exist"; S 8 "Every JSON file holds one object" |
| canonical_serialization_and_integer_units (1) | I lines 13-14; S 8 "sorted keys at every level and ends with a newline. Every number is a JSON integer: no floats and no booleans" |
| report_keys_match_schema (1) | S 8.1, 8.2, 8.4, 9 key lists |
| report_arrays_in_schema_order (1) | I line 14 "order every array as schema.md says"; S 8.1 "ascending", 8.2, 8.4 |
| ordinary_extract_portfolios_match (5) | I lines 3, 9; S 3, 5, 8.1 |
| ordinary_extract_segment_files_match (3) | I line 10; S 6, 8.2 |
| ordinary_extract_summary_and_totals_match (3) | I lines 11-12; S 7, 8.1 totals, 8.3 |
| waiver_precedence_case (3) | S 2.6 "`CONTINUITY_WAIVED` applies to a site row whose routine certificate is pending and whose continuity waiver is valid"; S 8.1/8.4 compliance_counts |
| tie_break_greatest_tuple_case (3) | S 2.4 "the greatest identifier wins. ... A set of identifiers compares as the tuple of its members sorted ascending"; S 5 "Remaining ties follow the programme conventions" |
| cap_after_uplift_case (3) | S 2.5 "A cap always binds the final rate"; S 6 "A chosen offer is cap binding when its site's base plus uplift is greater than the cap" |
| residual_ties_descending_id_case (3) | S 2.4 "served in descending identifier order"; S 7, 8.4 |
| per_value_tick_quantisation_case (3) | S 2.3 "every energy sum is a sum of such ticks" |
| large_20/22_site_portfolio_case (5 each), large_20/22_site_interval_quantities_case (3 each) | I line 3 "up to 22 sites and up to 4 offers per site ... within 30 seconds"; S 3 |
| large_tie_count_case (5), large_tie_greatest_tuple_shuffled_case (5) | S 8.4 `tied_portfolio_count`; S 2.4; S 1 "Row order inside any file carries no meaning" (inputs break I line 3 / S 3 "up to 4 offers per site", gate 03 TS-19) |
| tick_feasibility/shortfall_order/created_tie/floor_deficit/recovery_ceiling_case (5 each) | S 2.3 "A Wh value read from any file becomes ticks ... before it is added to anything"; S 5 |
| funded_pool_case, _after_capped_credit, _residual_tie, _waived_weight (5 each), _after_site_rounding (3) | S 7 "The calculation order ... the funded pool F is the grant pool minus the event-region's credit cents ... or 0"; S 2.3 per-site cents |
| held_waiver_weight_case (5), cooldown_waiver_weight_case (3) | S 7 "counted twice when the site row's compliance label is `CONTINUITY_WAIVED`"; S 2.6 ranking |
| duplicate_profile_row_portfolio_case (5), _count_case (3) | S 1 profiles kind 3; S 9 duplicate_profile_rows |
| out_of_range_interval_portfolio_case (5), _count_case (3) | S 1 profiles kind 2; S 9 |
| unknown_region_site_row_count_case (3), _report_case (5) | S 1 sites.csv "skipped and counted, it is not a site row for any purpose"; S 9 |
| mixed_rejection_counts_case (3) | S 1, S 9 (all data_quality keys; the waiver_signed_missing count is the gate 01 IN-16 ambiguity) |
| negative_hardcoded_sample_answers (-5) | I line 3 "must not depend on the shipped records" |
| negative_reads_tests_or_reward_files (-5) | I line 26 "Do not cheat" |
| negative_external_dependency_or_network (-3) | I line 3 "Use only the Python 3.12 standard library" |
| negative_missing_substantive_sections (-3) | S 8.3 summary keys |

No test enforces something the contract never asked for.

Judged criteria:

| Criterion | Kind | Sentence or requirement served |
|---|---|---|
| R1 reads schema.md to the end | conduct, odds-raising | serves every rule in S ("Treat schema.md as the authority", I line 1) |
| R2 samples six data files | conduct, odds-raising | serves the joins of S 1 |
| R3 checks codes vs program.ini | conduct, odds-raising | serves S 1 unknown region rule |
| R4 restates objective | conduct, preference (gate 04 minor) | S 5 |
| R5 states funded pool | outcome | I line 19; S 7 |
| R6 hand-made cap case | conduct, odds-raising | S 2.5, 6 (never triggered by shipped data) |
| R7 hand-made equal remainders | conduct, odds-raising | S 7, 2.4 |
| R8 compares two inputs | conduct, odds-raising | I line 3 "must not depend on the shipped records" |
| R9 code quality | conduct (JD-18) | the deliverable is code |
| R10 names an unexercised rule | outcome | I line 24 |
| R11 grader reads (-5) | conduct negative | I line 26 |
| R12 false verified claim (-5) | conduct negative | honest reporting |
| R13 per-value ticks | outcome | I line 20; S 2.3 |
| R14 waiver weight rule | outcome | I line 21; S 2.6, 7 |
| R15 first repeated row kept | outcome | I line 22; S 1 |
| R16 final run on /app/data | conduct | I line 5 |
| R17 largest run and seconds | outcome | I line 23 |

No constraint criteria; every outcome criterion quotes an instruction sentence.

### Overlap

Observables read by the tests: (a) the nine JSON files and derive_report.py under /app/out (existence, parse, serialisation, key sets, array orders; four format checks and `negative_missing_substantive_sections`); (b) the JSON files derive_report.py writes when the verifier runs it on 26 unseen extracts (all value checks and `negative_hardcoded_sample_answers`); (c) the text of derive_report.py (grader-path tokens; import names).

Observables read by the judged criteria: (d) the trajectory: what the agent read (R1, R2, R3), stated before coding (R4), built and ran (R6, R7, R8, R16), shell commands on /tests or /logs/verifier (R11), and how derive_report.py is written (R9: naming, except clauses, dead code); (e) the closing message (R5, R10, R12, R13, R14, R15, R17).

Pairs checked for a shared observable: R9 vs `negative_external_dependency_or_network` (both read the source, but code style vs import roots: different properties); R11 vs `negative_reads_tests_or_reward_files` (shell commands vs program text); R16 vs `artifact_set_exists_and_parses` (order of last edit and last run vs file existence); R5/R13/R14/R15 vs the funded, tick, waiver and duplicate checks (a sentence in the reply vs numbers the program writes on unseen extracts); R17 vs the large checks (a claimed time vs the verifier's own 30 s limit). No test and criterion read the same observable: zero overlap.
