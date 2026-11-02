Bundle: emberforge-vault-settlement
Bundle path: /Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/emberforge-vault-settlement
Report version: v1
Date/time: 2026-10-21 18:56 IST (13:26 UTC)
QC kit commit: bde868c46994f4916e245b40d14f302b1341244a
Harbor version: 0.24.0
Session title: set to `emberforge-vault-settlement_v1_qc` on ses_ea15ca9ccffeaSofoPYq6quwMK. Note: `opencode session list` shows it as the second row (a parallel QC session, district-heat-flex-procurement_v1_qc, was created in the same minute and sorts first); the title is on the correct session.

Verdict: ❌ FAIL (3 fails, 3 minors, 3 warns)

| Step | Gate | Verdict | Fails | Minors | Warns |
|------|------|---------|-------|--------|-------|
| 1 | structure_qc.py | ✅ pass | 0 | 0 | 0 |
| 2 | instruction_qc.py | ✅ pass | 0 | 0 | 0 |
| 3 | tests_qc.py | ⚠️ warn | 0 | 0 | 1 |
| 4 | judge_qc.py | ✅ pass | 0 | 0 | 0 |
| 5 | 01_Instruction_QC | ❌ fail | 1 | 0 | 0 |
| 6 | 02_Data_Solution_QC | 🟡 minor | 0 | 1 | 0 |
| 7 | 03_Tests_QC | 🟡 minor | 0 | 1 | 1 |
| 8 | 04_Judge_QC | 🟡 minor | 0 | 1 | 1 |
| 9 | 05_Alignment_Integrity_QC | ❌ fail | 3 | 0 | 1 |
| 10 | Execution gate | ✅ pass | 0 | 0 | 0 |
| 11 | Coverage and overlap re-check | ❌ fail | 2 | 0 | 0 |
| | Overall | ❌ FAIL | 3 | 3 | 3 |

Overall counts are distinct defects. Gate 05 AL-4 is the same defect as gate 01 IN-16, Step 11 re-found IN-16 and AL-3, and the tests_qc A3 warn is the same item as gate 03 TS-23, so the per-row counts add up to more than the overall row.

Step 10 tests-only results: oracle 1.0 / 1.0 / 1.0 / 1.0 / 1.0, nop 0.0, stub 0.0 (0 of 155).

## Findings

### ❌ Fails

1. ❌ Gate 01 IN-16 (also gate 05 AL-4, re-found in Step 11). The contract does not settle whether a salvage that repeats an already-redeemed forge, and is also outside its own credit window, carries `UNCREDITED_SALVAGE` beside `SALVAGE_ALREADY_CREDITED`, and a graded check depends on the answer. environment/data/invariants.md:15-16 "An entry carries a finding for every condition that holds of it, so one entry may carry more than one." (the N3 exemption list names only scope, standing, missing forge and unresolved edition) against rulebook_salvage.md:54-55 "Every later salvage naming that forge entry is not settled, whatever its own day and whatever the window would otherwise say of it."; tests/test_output.py:837-846 returns at the S6 test before the window test. Under the literal N3 reading, lv1a gains L0057, L0059, L0060, L0265 and L0267 `UNCREDITED_SALVAGE`, and `cap_and_floor_one_findings` (weight 5) fails; the slice and the shipped season settle the same way under both readings, so calibration cannot settle it. **Bug/Error.**
   Fix: add to environment/data/rulebook_salvage.md S6 (and the identical text in RULEBOOK_TEXTS in tests/test_output.py) the sentence "A salvage refused under this rule is not tested against the credit window and carries only `SALVAGE_ALREADY_CREDITED`."

2. ❌ Gate 05 AL-3 / CL-5 / CL-6 (re-found in Step 11). record_shapes.md says the item separator is `", "`, but the graded form uses a bare comma at the end of each indented line, so writing exactly what the spec says fails `structure_canonical_serialisation`. environment/data/record_shapes.md:21-22 "indented by two spaces, with `", "` between items and `": "` after each key"; tests/test_output.py:2053-2055 `separators=(",", ": ")` and line 2732 `assert raw == _canon(json.loads(raw))`. Reproduced: `json.dumps(obj, indent=2, separators=(", ", ": "))` leaves `"1, \n"` with a trailing space and does not equal `_canon`. Weight 1 of 155. **Bug/Error.**
   Fix: in environment/data/record_shapes.md lines 21-22 (and RULEBOOK_TEXTS["record_shapes.md"] in tests/test_output.py) replace "with `\", \"` between items" with "with `\",\"` ending every item that is followed by another (no trailing space)".

3. ❌ Gate 05 AL-27. The `RETIRED_REAGENT` tie-break is stated but never triggered: no graded season has an edition with two retired reagents. environment/data/finding_codes.md:37-39 "Where the edition has lines for more than one retired reagent, the detail names the first of them in ascending reagent order." Retired reagents per graded season: lv2a `['R02']`, lv2b `['R03']`, all others none. A variant that names the last retired reagent instead changes no observable in any of the 16 seasons. **Bug/Error.**
   Fix: in tests/test_output.py `_lever_retired` (line 2443) also retire a second reagent that shares an edition with the first, so that at least one refused forge carries two retired lines and `retired_reagent_*_findings` separates the two tie-breaks.

### 🟡 Minors

4. 🟡 Gate 02 DS-22. TRUTH.md misstates how many requisitions the isolated-rule seasons have. solution/TRUTH.md:105-107 "Every reseeded season keeps the levers it does not own out of reach: ... and four requisitions."; cl_partition has 2 and cl_quiet has 5. No grading impact. **Suggestion/Improvement.**
   Fix: in solution/TRUTH.md line 107 replace "and four requisitions" with "and at most five requisitions (two in cl_partition, five in cl_quiet)".

5. 🟡 Gate 03 TS-20. The negative for planting an import hook the grader would load, which is an attack on the verifier, has the "rare, minor" weight, while replaying answers has -3. tests/test_output.py:3188 `criteria.negative_rebinds_verifier_dependencies(weight=-1)`. **Suggestion/Improvement.**
   Fix: change tests/test_output.py line 3188 to `criteria.negative_rebinds_verifier_dependencies(weight=-5)`.

6. 🟡 Gate 04 JD-5. R5 puts three separately decidable code-quality facts into one binary criterion. tests/judge.toml:66 "... each settlement stage sits in a named function, every except clause names the exception it handles, and the file carries no dead, duplicated or debug code." **Suggestion/Improvement.**
   Fix: split R5 in tests/judge.toml into one binary criterion per fact (named stage functions; named exceptions; no dead, duplicated or debug code), renumber the later ids, and set `weights.judge` in tests/reward.toml to `repr(0.5 / new positive total)`.

### ⚠️ Warns

7. ⚠️ Gate 03 TS-23 (tests_qc A3). There are 50 checks against the 35-check cap (tests/test_output.py:3139-3188). Each one reads a distinct season and observable pair. **Suggestion/Improvement.** The tasker needs to approve this.

8. ⚠️ Gate 04 JD-16. R7 (tests/judge.toml:92, the third-party import in /app/out/settle_vault.py) enforces a rule on a declared artifact that a deterministic AST check could settle. **Suggestion/Improvement.** Fix: add a negative check in tests/test_output.py that parses the program with `ast` and returns True when an imported top-level module is not in `sys.stdlib_module_names`, weight -3, then drop R7 and update both reward.toml weights.

9. ⚠️ Gate 05 CL-5. Values are compared type-strictly, but nothing states the JSON type of the non-count numeric fields `grade` (vault_audit.json, 21 points) and `ordinal` (reconciliation.json, 18 points). The contract only says "Every count, unit and ember figure is a whole number" (record_shapes.md:23-24), and `_same` treats `"1"` and `1` as different. **Suggestion/Improvement.** Fix: add to record_shapes.md (and RULEBOOK_TEXTS) "Grades, tiers, ordinals and every other numeric column are written as JSON numbers."

## Consolidated sign-off

- ✅ structure_qc.py exits 0
- ✅ FC-S1..FC-S24 structure_qc.py output read, and every failure it reports confirmed in the file and carried into the report (17 pass, 0 failures)
- ✅ instruction_qc.py exits 0
- ✅ tests_qc.py exits 0 (with the A3 warn, finding 7)
- ✅ judge_qc.py exits 0
- ❌ Gate 01 Instruction: no fail findings (finding 1)
- ✅ Gate 02 Data & Solution: no fail findings (one minor, finding 4)
- ✅ Gate 03 Tests: no fail findings (one minor and one warn, findings 5 and 7)
- ✅ Gate 04 Judge criteria: no fail findings (one minor and one warn, findings 6 and 8)
- ❌ Gate 05 Alignment & Integrity: no fail findings, F0a-F0e all clean (F0a-F0e are clean; AL-3, AL-4 and AL-27 fail, findings 1-3)
- ✅ CL-1..CL-10 client feedback checks all run, each one carrying the number it asks for or the file and line it asks for (never a bare ✅) (CL-2 forgery price 5/155 = 3.2%; CL-4 one wrong fact gives 150/155 = 0.968; CL-5 and CL-6 fired, finding 2)
- ✅ Step 10 preflight run and pasted (harbor version 0.24.0 or newer, with the exact number recorded; docker reachable; bundle path listed) (harbor 0.24.0)
- ✅ Step 10 oracle run executed for real FIVE times: all five exactly 1.000, every number reported individually (evidence pasted) (1.0, 1.0, 1.0, 1.0, 1.0)
- ✅ Step 10 nop run executed for real: reward exactly 0.000 (evidence pasted) (0.0)
- ✅ Step 10 stub run executed for real: score reported, tests that paid named, judgement given with reasons (evidence pasted) (0.0, no check paid; healthy)
- ✅ Step 10 runs made from `exe_copy.py` copies only: its full output pasted (judge.toml validated against the rewardkit 0.2.1 schema, judge.toml deleted, tests-only reward.toml weight, network roles opened), scores recorded as TESTS-ONLY, both copies deleted, and the original confirmed unedited (no OpenAI key was set; the network was opened and the OpenHands pre-bake dropped in the copies only)
- ✅ Every oracle or empty-run score claimed anywhere in the bundle (TRUTH.md included) is scoped to the test channel; no judged-channel oracle score is claimed, because none can exist (TRUTH.md claims no score)
- ❌ Step 11: re-check done, coverage mapping complete both directions, zero overlap between tests and judged criteria (the mapping is complete and there is zero overlap, but the re-check is not clean: it re-found findings 1 and 2)
- ❌ All warn findings shown to the tasker and approved (findings 7-9 are waiting for the tasker)
- ✅ Sign-off recorded: reviewer name, date, bundle name, verdict (Sisyphus, QC session emberforge-vault-settlement_v1_qc; 2026-10-21 20:00 IST (14:30 UTC); emberforge-vault-settlement; ❌ FAIL)



# Evidence appendix

## Step 0: preconditions

```
$ git -C ".../Terminal_2.0_Harbor_Harness" rev-parse HEAD
bde868c46994f4916e245b40d14f302b1341244a
$ diff -rq ".../master_chat_work/bundles/emberforge-vault-settlement" ".../QC_2026-10-21/bundles/emberforge-vault-settlement"
(no output, exit 0)
```

## Steps 1-4: scripts

### Step 1: structure_qc.py (exit 0)

```
structure_qc: emberforge-vault-settlement
============================================================
pass [S1] bundle name format
pass [S2] all required files present
pass [S4] input directories data/ (36 files) all copied into the image
pass [S7] agent image copies nothing from outside environment/
pass [T1] task.toml parses
pass [T2] template shape, key order, environment_mode = separate
pass [T4] artifacts (absolute container paths): ['/app/out/settle_vault.py', '/app/out/summary.json', '/app/out/vault_audit.json', '/app/out/reconciliation.json', '/app/out/data_quality.json', '/app/out/allocation.json', '/app/out/workshop_cinderhall.json', '/app/out/workshop_gloamworks.json', '/app/out/workshop_slagmoor.json', '/app/out/workshop_verdigris.json', '/app/out/guild_ashen_compact.json', '/app/out/guild_tidebound_league.json']
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
============================================================
SUMMARY: 17 pass, 0 warn, 0 fail
VERDICT: PASS
```

### Step 2: instruction_qc.py (exit 0)

```
instruction_qc: emberforge-vault-settlement
============================================================
pass [C1] timeout sentence matches agent timeout (7200s)
pass [C2] no scripted machinery names
pass [C3] no 'reward'
pass [C4] every /app path resolvable through COPY/ADD exists
pass [C5] every declared artifact referenced
============================================================
SUMMARY: 5 pass, 0 warn, 0 fail
VERDICT: PASS
```

### Step 3: tests_qc.py (exit 0, 1 WARN)

```
tests_qc: emberforge-vault-settlement
============================================================
pass [A1] test_output.py parses and imports criteria, criterion from rewardkit
pass [A2] no duplicate function names
pass [A4] every check is a top-level @criterion(description=...) function of workspace
pass [A5] no literal non-bool returns; every reading check guarded (trace by hand)
pass [W1] 50 module-level registrations
pass [W2] every weight is an integer on the locked scale
pass [W3] bijection checks <-> registrations
pass [W4] weights differentiate
pass [W5] 5 negative check(s)
pass [W6] negative_ prefix matches weight sign
pass [W7] positive total 155, negative total 7
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
pass [O1] oracle independent of the verifier (4% of solve.py's 785 substantive lines also appear in test_output.py)
pass [H1] util-linux installed for setpriv
pass [H3] /tests restricted from unprivileged readers
pass [H4] stale reward files cleared before grading
pass [H5] verifier log directory owned by root and not writable by others
WARN [A3] 50 checks; cap is 35 (warn)
============================================================
SUMMARY: 34 pass, 1 warn, 0 fail
VERDICT: WARN - tasker approval needed
```

Re-verification of the WARN: tests_qc W1 counts 50 module-level `criteria.<name>(weight=...)` registrations; confirmed by counting the registration block at the end of tests/test_output.py (see gate 03). Carried as ⚠️ A3.

### Step 4: judge_qc.py (exit 0)

```
judge_qc: emberforge-vault-settlement
============================================================
pass [G1] judge.toml parses (9 criteria)
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
pass [G3] 9 criteria
pass [G4] 4 negative criteria
pass [G5] weights differentiate
pass [G6] positive total 19, negative total 14
============================================================
SUMMARY: 19 pass, 0 warn, 0 fail
VERDICT: PASS
```

## Step 5: Gate 01 Instruction QC

Verdict: ❌ FAIL (1 fail, 0 minors, 0 warns)

Files read in full: instruction.md (13 lines), task.toml, environment/Dockerfile, every file in environment/data/ (36), tests/test_output.py (3197 lines), tests/judge.toml.

Analysis tooling (scratch only, /tmp/opencode-logs/emberforge-vault-settlement-analysis-20261021T1856/): a copy of tests/test_output.py imported with a stub `rewardkit` module, used to (a) regenerate the shipped corpus, (b) settle the slice under all 840 register draws, (c) settle the season proper under the recovered draw, (d) settle each grader season under alternative readings of the rulebooks. Nothing in the bundle was modified.

### Findings

❌ IN-16 A graded finding record has two defensible readings for a salvage that is both a repeat of an already-redeemed forge and outside its own credit window, and no agent-visible file settles which codes it carries. **Bug/Error.**
- Reading A (literal N3): the entry carries both `SALVAGE_ALREADY_CREDITED` and `UNCREDITED_SALVAGE`. environment/data/invariants.md:15-16 "An entry carries a finding for every condition that holds of it, so one entry may carry more than one."; the N3 exemption list (invariants.md:16-21) names only scope, standing, missing forge and unresolved edition as refusals that are "never tested against ... the credit window or the one-salvage-per-forge rule" - the one-salvage rule is not on it; finding_codes.md:22-23 "`UNCREDITED_SALVAGE` - the entry is a salvage whose named forge does not fall in the salvage credit window."
- Reading B (what the grader does): only `SALVAGE_ALREADY_CREDITED`. rulebook_salvage.md:54-55 "Every later salvage naming that forge entry is not settled, whatever its own day and whatever the window would otherwise say of it." can be read as "the window is not consulted". tests/test_output.py:837-846 checks `redeemed` first and `continue`s before the window test.
- Graded: `cap_and_floor_one_findings` (weight 5, season lv1a). Reproduced: under reading A the lv1a finding record gains `('L0057','UNCREDITED_SALVAGE')`, `('L0059',...)`, `('L0060',...)`, `('L0265',...)`, `('L0267',...)` (L0057: salvage by S009 on day 166 naming L0055, already redeemed by L0056 on day 131; after the IE rename to S009-x the window for S009-x holds no settled A08-family forge). The slice and the season proper settle identically under both readings (checked: data_quality.json equal), so the calibration controls cannot pick between them. Re-verified twice (scripted diff and the L0057 trace).
- Files searched for a tiebreak: invariants.md, finding_codes.md, rulebook_salvage.md, record_shapes.md, calibration_slice.md, calibration_controls.json, example_workshop_report.json.
- Fix: add one sentence to environment/data/rulebook_salvage.md S6 (and its copy in RULEBOOK_TEXTS in tests/test_output.py) stating that a salvage refused under S6 is not tested against the credit window and carries only `SALVAGE_ALREADY_CREDITED`, or else change the grader to emit both codes and say so.

### Checklist

- ✅ IN-0 instruction_qc.py run, exit code and findings reported (exit 0, 5 pass)
- ✅ IN-S1..IN-S7 instruction_qc.py output read, and every failure it reports confirmed in the file and carried into the report (no failures reported)
- ✅ IN-F1 no em/en dashes anywhere in the file (structure_qc X1 pass; read by eye: only hyphen-minus in "live-service", "stdlib-only", "byte-identical", "data-quality", "reagent-vault")
- ✅ IN-L1 register is everyday natural English, no banned or same-kind vocabulary (no hit on the banned list or "crucial"/"robust"; plain sentences such as "Read everything in that directory before you start.")
- ✅ IN-L2 grammar and spelling clean ("What must be true when you stop." and "Rules of engagement." are deliberate heading-style fragments, not errors)
- ✅ IN-L3 no AI-tell phrases; reads like a human colleague wrote it
- ✅ IN-1 timeout sentence present and N == agent timeout_sec ("You have 7200 seconds to complete this task." vs task.toml `[agent] timeout_sec = 7200.0`)
- ✅ IN-2 no mention of tests/, solution/, grader, logs, reward (stating WHAT is judged is fine) ("A record counts only when it matches the settled season exactly." states the acceptance bar, names no machinery)
- ✅ IN-3 no instruction to write reward/log files
- ✅ IN-4 no benchmark self-references or GUIDs
- ✅ IN-5 no finding for unmentioned inputs; any path the prompt does name exists (`/app/data/` from `COPY data /app/data`; `/app/data/record_shapes.md` exists; `/app/out` is agent-created under `/app`, which Dockerfile line 21 chowns to 1000)
- ✅ IN-6 exactly one landing place inferable for each declared artifact, both ways (all 12 task.toml artifacts appear verbatim in instruction.md lines 7 and 9; the prompt asks for no undeclared file; the final message is not a file)
- ✅ IN-7 no tool named that the image does not install ("stdlib-only Python 3" on python:3.12-slim)
- ✅ IN-8 everything the tests assert AND everything an outcome judged criterion demands is knowable from prompt, shipped spec or data (conduct criteria are exempt, see JD-15) (record shapes in record_shapes.md; draw recoverable: exactly one of the 840 register draws reproduces calibration_controls.json + example_workshop_report.json - RS-C/half-even/GFS/opening-plus-acquired; R2-R4 values 124974, L0305/L0290 and the seven multi-finding entries follow from settling the season under that draw; the one reading conflict is raised under IN-16; R5 is a conduct code-quality criterion, exempt)
- ✅ IN-9 no answer or algorithm leak (withholding is fine; gate 02 DS-21 rules on anything you suspect is unreachable) (the draw is withheld and recoverable from the slice; no worked solution in the prompt)
- ✅ IN-10 online-lookup sentence: no check performed (tasker decision)
- ✅ IN-11 network wording matches the pinned offline contract (no fetch/download/ URL-as-source sentences; silence about the network is correct) ("no network calls while it runs" is a rule on the delivered program, not a fetch)
- ✅ IN-12 category names the dominant work; description honest; keywords/tags related ("Data Processing" fits a settlement engine over CSV/JSON; description lists the draw recovery, identity, editions, scarcity fixpoint, allocation and reconciliation the instruction and rulebooks ask for; keywords/tags all on-topic)
- ✅ IN-13 no internal contradictions, constraints jointly satisfiable ("Work only from /app/data/. Never write into it." is compatible with writing /app/out)
- ✅ IN-14 describes the end state and any rules of engagement, never a recipe that is the solution
- ✅ IN-15 every graded rule of engagement is stated plainly enough to act on (R6 "writes ... under /app/data" <- "Never write into it."; R7 stdlib import <- "must use the Python standard library alone, with no third-party packages"; R8 network <- "no network calls while it runs")
- ❌ IN-16 nothing graded has two defensible readings the contract fails to settle (both readings written out, or no finding) - see Findings (SALVAGE_ALREADY_CREDITED vs UNCREDITED_SALVAGE co-occurrence, graded by cap_and_floor_one_findings)

Additional IN-16 candidate examined and dismissed: canonical identity for a handle merged into a handle that had already been renamed earlier (lv2a: S001 merged into S023 on day 113, S023 renamed to S023-x on day 57). rulebook_identity.md I2 "following each result in turn, until no further rename or merge applies to it" settles it the way the grader does (S001 -> S023 -> S023-x), and no graded observable differs in any season, so no finding.

## Step 6: Gate 02 Data, Environment & Solution QC

Verdict: 🟡 MINOR (0 fails, 1 minor, 0 warns)

Files read in full: environment/Dockerfile, all 36 files in environment/data/, solution/solve.sh, solution/solve.py (1113 lines), solution/TRUTH.md (read last, after DS-21 was decided), plus instruction.md, task.toml, tests/test_output.py, tests/judge.toml as evidence.

DS-21 conclusion written before TRUTH.md was opened: solvable. The only withheld facts are the four conventions; settling the slice under all 7x5x6x4 = 840 register draws with the grader's own engine leaves exactly one draw reproducing both calibration_controls.json and example_workshop_report.json (RS-C, half-even, GFS, opening-plus-acquired; 21 draws reproduce the controls alone, the example cuts them to one). Every rule the settlement needs is in the rulebooks; every graded key, code and filename is in record_shapes.md / finding_codes.md / instruction.md. TRUTH.md, read afterwards, agrees ("that is the least publication that leaves exactly one of the 840 draws").

Oracle evidence (scratch run, not Step 10): solve.py run as a subprocess on the shipped corpus and on all 16 grader seasons rebuilt from tests/test_output.py; every record equals the grader's settlement on every season (`mismatched=[]` for all 16, visible season byte-identical in canonical form), each run 2.6-4.4 s on the host.

### Findings

🟡 DS-22 TRUTH.md misstates the requisition count of the isolated-rule seasons. solution/TRUTH.md:105-107 "Every reseeded season keeps the levers it does not own out of reach: ... a reference other than `consumed`, and four requisitions." Rebuilt from tests/test_output.py SEASONS: cl_partition has 2 requisitions (`_mut_partition` drops slagmoor and verdigris requests) and cl_quiet has 5 (`_trigger_quiet_rules` appends RQ05); the other non-ladder seasons have 4. No grading impact. **Suggestion/Improvement.**
Fix: in solution/TRUTH.md line 107 replace "and four requisitions" with "and at most five requisitions (two in cl_partition, five in cl_quiet)".

### Checklist

- ✅ DS-1 input in one or more named directories under environment/, each non-empty and COPYed; environment/ holds only the Dockerfile and those directories (structure_qc S4: "data/ (36 files) all copied into the image"; Dockerfile line 23 `COPY data /app/data`)
- ✅ DS-2 data necessary: task unsolvable without it (the rulebooks, register and slice are the only source of the rules and the draw)
- ✅ DS-3 every referenced file present, every claim about the data true (record_shapes.md exists; the four in-scope workshops and two guilds the instruction names are exactly what A2 yields from workshop_registry.csv - brackenvault and quenchspar are tier 1 and opened day 13; "Exactly one draw" verified, see above; calibration_controls.json `entries_total: 36` equals the 36 rows of calibration_crafting_ledger.csv)
- ✅ DS-4 no answers or answer-derivable content in any environment/ input directory (calibration_controls.json and example_workshop_report.json are the slice's outputs, not the graded seasons'; every value check grades a reseeded season the agent never sees; the season-proper answers R2-R4 appear in no data file)
- ✅ DS-5 no template residue, no redacted-spec pattern (`grep -rn -E "TODO|FIXME|XXX|PLACEHOLDER"` over the bundle: no hits; every data file is regenerated byte-for-byte by tests/test_output.py `_build_corpus_dir`, 36/36 equal, 12/12 rulebook texts equal)
- ✅ DS-6 data internally consistent with the task story (L0305 is a planted 999-unit bulk order appended at the end of crafting_ledger.csv, day 27, patch P02 consistent; R14 retired from P05 by `_plant_visible`; N1 sorting makes file order irrelevant)
- ✅ DS-7 no em/en dashes in text data (structure_qc X1 pass)
- ✅ DS-8 Dockerfile copies nothing from tests/ or solution/ (only `COPY data /app/data`)
- ✅ DS-9 every input directory lands where the instruction says (conventionally /app/<dir>) (`/app/data`)
- ✅ DS-10 every needed tool/library installed in the image (solve.py imports csv, json, sys, bisect, itertools, pathlib, typing - all stdlib; base python:3.12-slim)
- ✅ DS-11 offline contract respected (every layer, oracle included, runs with no network) (solve.sh: `mkdir -p`, `cp`, `python3`; no fetch; the uv/openhands install runs at build time only)
- ✅ DS-12 no secrets, host paths, or machine-specific assumptions (base image pinned by digest)
- ✅ DS-28 every artifact directory writable by uid 1000 in the agent image (line 21 `RUN mkdir -p /app && chown 1000:1000 /app`; /app/out is created by solve.sh/agent as uid 1000; structure_qc S8 pass)
- ✅ DS-29 openhands-sdk runtime pre-baked at /opt/openhands-sdk-venv with openhands-sdk/tools 1.55.1 and litellm 1.105.0 (any correct install style) (lines 6-17; single-stage build, nothing later removes it)
- ✅ DS-30 uid 1000 agent account created with a home directory, and ENV HOME set (lines 3-4; python:3.12-slim has no uid 1000 of its own)
- ✅ DS-13 solve.sh present, entrypoint; solve.py optional
- ✅ DS-14 oracle computes the answer, does not paste it (solve.sh copies solve.py to /app/out/settle_vault.py and runs it; solve.py recovers the draw by exhaustive search and settles from the CSVs)
- ✅ DS-15 oracle would plausibly score 1.0 against the tests (matches the grader on all 16 seasons and the visible season; defaults `/app/data` `/app/out` per main(); deterministic; writes canonical JSON with trailing newline)
- ✅ DS-16 oracle data reads confirmed legal (reads only the data directory it is given)
- ✅ DS-17 oracle never touches tests/ (`grep -n -E "/tests|test_output|judge|reward"` on solve.sh and solve.py: no hits; both read in full)
- ✅ DS-18 solve.sh idempotent (warn only) (`mkdir -p`, `cp` overwrite, write_text overwrite)
- ✅ DS-19 oracle respects the constraints the contract imposes on the agent, including rules of engagement stated in a shipped rules file (stdlib only, no network, never writes /app/data)
- ✅ DS-20 oracle obeys every contract rule, wherever stated, including rules no test triggers (check order in `_forge` lines 517-534: cap judged first on the would-be charge, then floor, then retired reagent, all recorded, cap closes regardless - matches A4/V4/V9/N3; `_salvage` lines 559-568: S6 then S2 window; E3 via `_governing_day`; V2 same-day acquisitions applied `<= entry["day"]`. The S6-versus-N3 co-occurrence the oracle resolves as "SAC only" is the ambiguity reported under gate 01 IN-16; the oracle and grader agree on it. Inactive rules A5, A6, E5, H7, I6 are each declared absent "in this season" by their own rulebook text and none is triggered by any graded season)
- ✅ DS-21 solvable from instruction.md + environment/ input alone (hard is fine; only genuinely unreachable information fails) (see the pre-TRUTH conclusion above)
- 🟡 DS-22 TRUTH.md describes the shipped solution, the real grading and a defect list the bundle honours (read only after DS-21 was decided) - see Findings (requisition count). Verified true: 50 checks, 45 positive = 155, 5 negative = -7 (tests_qc W7); judge 9 criteria, +19 / -14 (judge_qc G6); 38 s limit (`_AGENT_TIMEOUT = TIME_LIMIT_SECONDS = 38`); sandbox account (tests/Dockerfile line 6 `useradd --uid 4001`); Solution shape steps 1-6 match solve.py; trap 6 verified - with E3 replaced by the salvage's own day, or with S6 removed, zero of the 840 draws reproduce the slice; no graded season uses the TRUE draw; digests `043fa527...` and `13dfb9f9...` equal `shasum -a 256` of solve.py and test_output.py
- ✅ DS-23 TRUTH.md unreachable by the agent: no Dockerfile route to it, never named in instruction.md
- ✅ DS-24 oracle is an independent implementation, not the verifier's own code (tests_qc O1: 4% shared lines; solve.py is class-based with its own branch-and-bound `Requests.best_total` + per-seat Q8 fixing, versus the grader's single DFS `_allocate`; shared content is the register table copied from convention_register.md)
- ✅ DS-25 every literal the grading side requires of the output is findable in an agent-visible file (named file per literal) (scripted: all 56 key names in the grader's records appear back-quoted in record_shapes.md; all 9 codes in finding_codes.md; all 11 record filenames in instruction.md line 9; list orders stated in record_shapes.md and invariants.md N3)
- ✅ DS-26 no answer-revealing artifact anywhere in the agent image, including /tmp, build stages and archive interiors (single stage; RUN steps install apt packages, uv and the openhands venv only)
- ✅ DS-27 TRUTH.md describes the task, with no narrative of how it was produced (Provenance holds uuid, instance_id, task_name, two digests, language; no authored_by, no generator or tooling credit)

## Step 7: Gate 03 Tests QC

Verdict: 🟡 MINOR (0 fails, 1 minor, 1 warn)

Files read in full: tests/Dockerfile (11 lines), tests/test.sh (10 lines), tests/reward.toml (7 lines), tests/test_output.py (3197 lines: corpus generator 1-502, loader and settlement engine 505-911, assembly and allocation 914-1335, harness and rulebook texts 1337-2214, mutations and seasons 2216-2577, observables 2580-2675, test bodies 2677-2858, rewardkit wrappers and 50 registrations 2861-3188), plus instruction.md, every environment/data spec file, task.toml and tests/judge.toml as evidence.

Lever isolation evidence (scratch): grader variants with one rule read wrongly were run on all 16 seasons. Counting every forge except those at a closed workshop in the `consumed` reference changes only lv3a/lv3b observables; skipping floor/retired tests at an already-closed workshop changes only lv2a/lv2b findings. So a program wrong on one lever loses that lever's checks only, as the comment at test_output.py:2351-2353 claims.

### Findings

🟡 TS-20 The negative check for planting an import hook the grader would load, an attack on the verifier itself, carries the scale's "rare, minor" weight. tests/test_output.py:3188 `criteria.negative_rebinds_verifier_dependencies(weight=-1)`, description line 3133 "running the program plants a module or path hook where the grader would import it."; replaying sample answers, a lesser cheat, carries -3 (line 3184). Gate 03's scale: "-5 = a red-line cheat; ... -1 = rare, minor". **Suggestion/Improvement.**
Fix: in tests/test_output.py line 3188 change the registration to `criteria.negative_rebinds_verifier_dependencies(weight=-5)` (negative total becomes 11, still far below the positive 155).

⚠️ TS-23 50 checks against the 35-check cap (tests_qc A3 WARN, confirmed: 50 `criteria.` registrations at lines 3139-3188). The count follows from 6 lever seasons x 5 observables plus 4 ladder rungs, 6 isolated rules, 5 structure checks and 5 negatives; each check reads a distinct season/observable pair. **Suggestion/Improvement.** Tasker approval needed.

### Checklist

- ✅ TS-0 tests_qc.py run, exit code and findings reported (exit 0, 34 pass, 1 warn A3)
- ✅ TS-S1..TS-S15 tests_qc.py output read, and every failure it reports confirmed in the file and carried into the report (no failures; the A3 warn confirmed and carried as TS-23)
- ✅ TS-1 no unconditional reads of agent input paths under tests/ (guarded reads are fine) (`/app/data` is touched only at lines 2701-2720 and 2802-2819 behind `if default_data.exists():` and is recreated from the grader's own corpus; tests_qc D1 pass)
- ✅ TS-2 tests/Dockerfile has COPY . /tests/, pins harbor-rewardkit==0.2.1 and sets LITELLM_LOCAL_MODEL_COST_MAP=True (lines 7-9)
- ✅ TS-3 tests/Dockerfile has RUN mkdir -p /app (warn if absent) (line 10)
- ✅ TS-4 all check dependencies and invoked tools installed in the verifier image, Python >= 3.12 (imports are stdlib + rewardkit; `setpriv` from util-linux line 4; python:3.12-slim)
- ✅ TS-5 ground truth self-contained in tests/ (every corpus is rebuilt by `build_corpus`/`_build_corpus_dir` from seeds and RULEBOOK_TEXTS; truth comes from the grader's own `settle`)
- ✅ TS-6 test.sh hardens, then ends with exec rewardkit; writes no reward bytes, nothing after rewardkit, never trusts a reward file on disk (lines 4-10 match the template exactly)
- ✅ TS-7 reward computed only from tests/ truth + declared artifacts (reads /app/out/settle_vault.py and the eleven /app/out records, all declared)
- ✅ TS-8 no skip switches
- ✅ TS-9 no agent-writable source/exec, not PATH-shadowable (agent code runs only as a setpriv subprocess; nothing imported from /app)
- ✅ TS-10 reward.toml shape exact, weights = 0.5 / positive total per channel at full precision, no clamp (`repr(0.5/155)` = 0.0032258064516129032 and `repr(0.5/19)` = 0.02631578947368421, both equal to line 4)
- ✅ TS-11 tests deterministic (no clock, random or network in any assertion; the PRNG is a seeded xorshift; `_read_dir` sorts its glob; sets are used for membership only; rewardkit's worker threads are serialised by `_GRADE_LOCK` (line 2864) and the one test that mutates /app/out restores it from a copy in `finally` (lines 2716-2723) after priming the `delivered()` cache (line 2700); the 38 s limit against oracle runs of 2.6-4.4 s on the host. Five-run agreement is confirmed in Step 10. Could not verify from source whether rewardkit 0.2.1 imposes a per-check timeout on threads waiting on the lock: the harness repo vendors rewardkit 0.1.7, not 0.2.1)
- ✅ TS-12 outcome-driven, no history/console grading (stdout/stderr of the program are read only for the error message)
- ✅ TS-13 one property per test (`structure_program_takes_directories` checks the one argument contract instruction.md line 7 states; each season check reads one observable)
- ✅ TS-14 names state properties (<property> / negative_<cheat>), prefix iff negative weight (descriptions match bodies; e.g. `cap_and_floor_one_findings` -> `_holds("lv1a", _obs_findings)`)
- ✅ TS-15 negative checks return True when the cheat happened, with inline comment (lines 3111, 3117, 3123, 3129, 3135 "# inverted: True only when ...")
- ✅ TS-16 negatives fire on the cheat and only the cheat (each requires the honest outcome to be absent: replay needs `got != want` and `got == shipped`; name-dependence and /app/data-dependence first require two identical runs; determinism needs two runs to differ; hook needs a new `sitecustomize.py`/`usercustomize.py`/`rewardkit*`/`.pth` file. An honest stdlib program trips none)
- ✅ TS-17 exact comparisons where exactness promised (bool/int trap checked) (`_same` compares `json.dumps(..., sort_keys=True)`, so `1` and `true` and `1.0` differ; instruction: "A record counts only when it matches the settled season exactly.")
- ✅ TS-18 tolerances stated in instruction where used (no floats anywhere; "Every count, unit and ember figure is a whole number")
- ✅ TS-19 no obvious contract/test contradiction, checking the shipped spec as well as the prompt; a promise a judged criterion grades is covered (deep pass in Gate 05) (the one reading conflict, SAC vs UNCREDITED co-occurrence in lv1a, is owned by gate 01 IN-16)
- 🟡 TS-20 weights map to importance semantically, ordering matches the instruction - see Findings (verifier-hook negative at -1). Positives: 1 for presence/form, 5 for findings and workshop figures of each lever season, 3 for derived records and isolated rules, 3 for the 12-request rung and 5 for 24/48 - consistent with TRUTH's focal levers
- ✅ TS-25 no positive test grades an absence (every positive needs a produced record equal to the grader's; `structure_findings_canonical_form` asserts `pairs` non-empty)
- ✅ TS-26 no test pair (any signs) pays twice for one observable (each season check reads a different record of a different season; workshop figures read admitted/rejected/charge/cap per workshop while guild reports read the guild roll-up and reagent flow; no positive grades determinism, so the determinism negative stands alone)
- ✅ TS-21 bijection check functions <-> criteria.<name>(weight=W) registrations, each registered once; no test_weights.json (tests_qc W3)
- ✅ TS-22 registered weights are integers within {5,3,1,-1,-3,-5} (tests_qc W2)
- ⚠️ TS-23 counts and balance: >=10 checks, <=35 (warn), >=1 positive, >=1 negative, weights not all identical, sum|neg| <= sum pos - 50 checks (warn); 155 positive vs 7 negative
- ✅ TS-24 verifier execution isolation (reward not forgeable by executed agent code) (`_run_delivered` lines 2186-2213: subprocess via `setpriv --reuid=4001 --regid=4001 --clear-groups`, `start_new_session`, `communicate(timeout=38)`, `_end_group` kills the process group and then every uid-4001 process via /proc, so a setsid daemon is also swept; corpus dirs opened read-only 0o755/0o644; uid 4001 cannot write /logs/verifier (root 755) or read /tests (go-rwx))
- ✅ TS-27 no positive test paying for source tokens instead of behaviour (`structure_program_delivered` only checks the file compiles and exceeds 500 characters, weight 1 as an existence check; every value check runs the program)
- ✅ TS-28 verifier hardening present where grading executes agent code, or explicitly reasoned as not needed (grading executes agent code; util-linux line 4, sandbox uid 4001 line 6, `rm -f` stale rewards, `chown root:root` + `chmod 755` on /logs/verifier, `chmod -R go-rwx /tests`)
- ✅ TS-29 no check can raise on bad, missing or hostile agent output; every check returns a bool (every check body is `_passes(test)` or `_holds(name, observe)`, both `try/except Exception` returning bool, lines 2867-2881; module level defines constants, functions and registrations only)

## Step 8: Gate 04 Judge criteria QC

Verdict: 🟡 MINOR (0 fails, 1 minor, 1 warn)

Files read in full: tests/judge.toml (9 criteria), plus solution/solve.sh, solution/solve.py, tests/test_output.py, tests/reward.toml, instruction.md and the environment/data spec files as evidence.

Classification: R1-R4 outcome (final-message facts the instruction demands); R5 conduct (JD-18 code quality); R6-R8 constraint; R9 conduct/misconduct (fabricated claim).

Value check for the outcome criteria (grader engine on the shipped season under the recovered draw, and the oracle's own records, which agree byte for byte): draw RS-C / half-even / GFS / opening-plus-acquired (R1); `season_charge_ember: 124974` (R2); `cap_reached` true for gloamworks and verdigris only, first CAP_REACHED in settlement order gloamworks L0305 (day 27), verdigris L0290 (day 147) (R3); entries with more than one finding exactly L0010, L0021, L0024, L0139, L0159, L0201 with CAP_REACHED + RETIRED_REAGENT and L0305 with CAP_REACHED + STOCK_FLOOR (R4).

### Findings

🟡 JD-5 R5 bundles three separately decidable facts about the code into one binary verdict. tests/judge.toml:66 "The agent writes /app/out/settle_vault.py as code a reviewer would accept: each settlement stage sits in a named function, every except clause names the exception it handles, and the file carries no dead, duplicated or debug code." A file meeting two of the three leaves the judge no partial verdict (gate 04 JD-S6: "A quality judgement is split into yes/no criteria, each naming one decidable fact."). Borderline because all three are facets of one act (code quality). **Suggestion/Improvement.**
Fix: in tests/judge.toml split R5 into separate binary criteria, for example R5 "The agent writes /app/out/settle_vault.py with each settlement stage in its own named function." (weight 1), and a new criterion "The agent writes /app/out/settle_vault.py with every except clause naming the exception it handles." (weight 1), renumbering the following ids and updating `weights.judge` in tests/reward.toml to 0.5 / the new positive total.

⚠️ JD-16 R7 grades a rule over a declared artifact that a deterministic test could settle. tests/judge.toml:92 "The agent delivers /app/out/settle_vault.py with an import of a module from outside the Python standard library." The file is a declared artifact the verifier receives, and no test checks its imports. **Suggestion/Improvement.**
Fix: add a negative check in tests/test_output.py that parses /app/out/settle_vault.py with `ast` and returns True when a top-level module of any `Import`/`ImportFrom` is outside `sys.stdlib_module_names`, register it at -3, and drop R7 (updating both reward.toml weights).

### Checklist

- ✅ JD-0 judge_qc.py run, exit code and findings reported (exit 0, 19 pass)
- ✅ JD-S1..JD-S13 judge_qc.py output read, and every failure it reports confirmed in the file and carried into the report (no failures; `weights.judge = 0.02631578947368421` = repr(0.5/19))
- ✅ JD-1 prefix matches evaluation_target for every criterion (R1-R4 final_answer "The response ..."; R5-R9 state_change/trajectory "The agent ...")
- ✅ JD-2 positive grammar everywhere, no banned tokens (R9 "that its own trajectory shows it never ran" describes the bad act happening; "never" is not a banned token)
- ✅ JD-3 no vague qualifiers ("exactly" is a count; R5 "a reviewer would accept" is immediately defined by the colon list)
- ✅ JD-4 no brackets, placeholders, tag prefixes, em/en dashes
- 🟡 JD-5 one observable per criterion - see Findings (R5)
- ✅ JD-6 every criterion decidable from evidence (R1-R4 name exact values; R6 reads the trajectory's commands on /app/data; R7/R8 read the delivered source; R9 compares the final message to the trajectory)
- ✅ JD-7 every criterion true of / avoided by the reference solution (R1-R4 values equal the oracle's records; solve.py stages are named methods `_resolve`, `_forge`, `_salvage`, `_read_indices`, `stable`, `fund`, `compile_records`; its one except clause names `(ArithmeticError, ValueError, KeyError)` (line 1063); solve.sh writes only /app/out; solve.py imports stdlib only and opens no socket)
- ✅ JD-8 zero overlap with deterministic tests (observable-level) (no test reads the final message, the agent's /app/data writes, the program's import list, network use or claims; tests read the program's records on reseeded seasons, and on the shipped season only presence and written form)
- ✅ JD-9 the judged criteria add process value beyond the tests (R1-R4 grade the final-message facts no test can see; R5 code quality; R9 honesty)
- ✅ JD-10 no contradiction with the instruction
- ✅ JD-11 negatives target this task's real cheat surface (writing into /app/data, third-party imports, network use, fabricated verification claims; grader-reading is impossible in the agent container and replaying answers is owned by the test negative)
- ✅ JD-12 counts and balance: >=8, <=35 (warn), >=1 positive and >=1 negative weight, weights not all identical, sum|neg| <= sum pos (9 criteria; +19 / -14)
- ✅ JD-13 importance/weight pairing holds by |weight| and magnitudes match semantic importance (R3/R4 the season facts that need the composition rules at 5; R1 draw at 3 critically_important; R6 the one red-line constraint at -5)
- ✅ JD-14 no criterion pair (negative or positive) pays twice for one act (R1-R4 read four different facts; R5 code shape vs R7 import list vs R8 network use are distinct observables)
- ✅ JD-15 every criterion classified as outcome, constraint or conduct; outcome criteria trace to the contract (instruction plus any spec file it points to); conduct criteria hold for every competent route or earn their narrowing by raising the odds of a correct end state, and each serves a real requirement; constraint criteria are exempt from both tests (R1-R4 <- instruction.md line 13 "Your final message must state the four conventions you recovered, each value quoted exactly as the register writes it, the season's total charge, the identifier of the entry that closed each workshop that reached its charge cap, and the identifier of every forge entry that carries more than one finding together with the codes it carries."; R5 conduct serving the delivered-program requirement, holds for every competent route; R9 conduct serving the final-message requirement)
- ⚠️ JD-16 each constraint criterion quotes its stated sentence and names the file it lives in, fits one of the six kinds, carries annotations type "instruction following", covers exactly one rule, and is graded once by the layer that should own it (a rule a test could have checked belongs to the tests) - R6 <- instruction.md "Never write into it." (scope, judge owns it: /app/data is not uploaded); R7 <- "The program you deliver must use the Python standard library alone, with no third-party packages" (tool-use; test-checkable, see Findings); R8 <- "no network calls while it runs" (tool-use; judge owns it); all three `type = "instruction following"`, one rule each
- ✅ JD-17 deleting every constraint still leaves a substantial task
- ✅ JD-18 at least one criterion judges the quality of the code the agent writes (name it), or the task authors no code and the line says so (R5)

## Step 9: Gate 05 Alignment & Integrity QC

Verdict: ❌ FAIL (3 fails, 0 minors, 1 warn)

Whole bundle held open: instruction.md, task.toml, both Dockerfiles, all 36 data files, solve.sh, solve.py, TRUTH.md, test.sh, test_output.py, reward.toml, judge.toml.

Rule-trigger evidence (scratch): grader variants each breaking exactly one stated rule, run on all 16 graded seasons; "GRADED-HIT" = a registered check that reads an observable which changes.

| rule broken in the variant | graded hit |
|---|---|
| S6 para 2: a window-rejected salvage still redeems its forge | lv1a/lv1b/lv2a/lv2b/lv3a/lv3b/cl_quiet findings |
| Q9: a capped workshop's requisition gets nothing | guild reports of lv1a, lv1b, lv2a, lv2b, lv3a, lv3b, cl_partition |
| V9: a retired reagent is not returned by salvage | lv2a vault, reconciliation, guild reports |
| STOCK_FLOOR detail names the last short reagent | lv1a, lv1b, cl_quiet findings |
| RETIRED_SMITH detail names the handle, not the canonical identity | lv1b, lv3b, cl_quiet findings |
| RETIRED_REAGENT detail names the last retired reagent | none in any season (see AL-27) |
| E3 salvage governed by its own day / S6 removed | slice reproduces 0 of 840 draws, so nothing settles |
| `consumed` reference skips forges at a closed workshop | lv3a, lv3b, all five observables |
| floor/retired not tested at an already-closed workshop | lv2a, lv2b findings |

### Findings

❌ AL-3 / CL-5 / CL-6 record_shapes.md states the item separator as `", "`, but the graded written form has no space after the comma at the end of an indented line, so writing exactly what the spec says loses the serialisation check. **Bug/Error.**
- Contract: environment/data/record_shapes.md:21-22 "Each record is one JSON object in UTF-8, indented by two spaces, with `", "` between items and `": "` after each key".
- Assertion: tests/test_output.py:2732 `assert raw == _canon(json.loads(raw))`, with `_canon` (lines 2053-2055) `json.dumps(obj, indent=2, sort_keys=False, separators=(",", ": "), ensure_ascii=False) + "\n"`.
- Reproduced twice: `json.dumps(obj, indent=2, separators=(", ", ": "), ensure_ascii=False) + "\n"` gives `'{\n  "a": [\n    1, \n    2\n  ], '...` (trailing space) and is not equal to `_canon`. The published calibration_controls.json and example_workshop_report.json show the graded form (0 lines ending in ", "), but nothing marks the spec sentence as the less reliable of the two. Cost: `structure_canonical_serialisation`, weight 1 of 155.
- Fix: in environment/data/record_shapes.md line 21-22 (and the identical text in RULEBOOK_TEXTS["record_shapes.md"] in tests/test_output.py) replace "with `\", \"` between items" with "with `\",\"` ending every item that is followed by another (no trailing space)".

❌ AL-27 The RETIRED_REAGENT detail tie-break is stated but no graded input ever has an edition with two retired reagents, so a solver breaking it loses nothing. **Bug/Error.**
- Rule: environment/data/finding_codes.md:37-39 "`RETIRED_REAGENT` - the retired reagent. Where the edition has lines for more than one retired reagent, the detail names the first of them in ascending reagent order."
- Fixtures: every graded season retires at most one reagent (lv2a `['R02']`, lv2b `['R03']`, all others `[]`; the shipped season R14 only, which is not value-graded). The variant naming the last retired reagent changes no observable in any of the 16 seasons.
- Fix: in tests/test_output.py `_lever_retired` (line 2443) retire a second reagent that shares an edition with the first (e.g. also `_retire(main, <second plain reagent on the same edition>, retire_rank)`) so at least one refused forge carries two retired lines, and confirm `retired_reagent_*_findings` then differs under the wrong tie-break.

❌ AL-4 The finding record graded in lv1a encodes one reading of an ambiguous rule (only SALVAGE_ALREADY_CREDITED for a repeat salvage that is also outside its window), which the contract does not settle. Same defect as gate 01 IN-16; one fix closes both. **Bug/Error.**
Fix: as gate 01 IN-16 - state in environment/data/rulebook_salvage.md S6 (and its RULEBOOK_TEXTS copy) that a salvage refused under S6 is not tested against the credit window.

⚠️ CL-5 The type of non-count numeric fields is compared type-strictly but only "Every count, unit and ember figure is a whole number" (record_shapes.md:23-24) is stated. `grade` in vault_audit.json rows (read by 7 vault checks, 21 points) and `ordinal` in reconciliation.json patch rows (6 checks, 18 points) are neither counts, units nor ember; `_same` (test_output.py:2664-2666) makes `"1"` differ from `1`. A JSON number is the natural form of a numeric CSV column and the published slice summary uses numbers throughout, so this is not raised as a fail. **Suggestion/Improvement.** Tasker approval needed.
Fix: in record_shapes.md after "Every count, unit and ember figure is a whole number." add "Grades, tiers, ordinals and every other numeric column are written as JSON numbers." (and the same in RULEBOOK_TEXTS).

### Checklist

- ✅ AL-F0a no template residue (no `{{`, `__X__`, `<TAG>`, TODO/FIXME/XXX/PLACEHOLDER anywhere; every data file regenerated byte-for-byte by the grader)
- ✅ AL-F0b data dependency holds (the rules, the register and the slice exist only in environment/data)
- ✅ AL-F0c work dependency holds, no shortcut found (every value check settles a reseeded season under its own draw; forgery earns 5 of 155, see CL-2)
- ✅ AL-F0d no double scoring across tests and judged criteria (tests read records of reseeded seasons and presence/form on the shipped one; criteria read the final message, the trajectory and the program source)
- ✅ AL-F0e solvable from instruction.md + environment/ input alone: no information the agent needs is unreachable (hard is fine, only impossible fails) (gate 02 DS-21; every graded season's own slice publication identifies its draw uniquely: for each of the 16 SEASONS draws, exactly 1 of 840 draws reproduces its controls + example on the shared slice, which mutations never touch)
- ✅ CL-1 every demanded action has a checker that looks at the action itself, not the agent's report of it (test or judged criterion named for each action) (deliver the program -> the tests run it themselves on 16 seasons plus the shipped one; "Running it must leave the settled season in /app/out" -> `structure_records_delivered` and `structure_program_takes_directories` (no-argument run into /app/out); final message -> R1-R4 read it. No checker reads an agent-written status field)
- ✅ CL-2 forgery price computed as a share of the positive weight, every paying test named, the total judged defensible with reasons (a fake program over 500 characters that writes hand-made, canonically serialised, internally tallied records to whatever directory it is given earns `structure_program_delivered` 1 + `structure_records_delivered` 1 + `structure_program_takes_directories` 1 + `structure_canonical_serialisation` 1 + `structure_findings_canonical_form` 1 = 5 of 155 = 3.2% of the test channel, 1.6% of total reward; if it replays the shipped summary `negative_hardcoded_sample_answers` takes 3 back (net 2 of 155). Every season check pays 0. All five that pay are presence/form checks at weight 1 that do not claim to grade content. Defensible)
- ✅ CL-3 no asserted value liftable verbatim from a shipped file, an instruction constant or a worked example (derivation is fine and expected) (value checks compare against seasons the agent never sees; the R1-R4 values appear in no data file; calibration_controls.json is the slice's summary, not the season's)
- ✅ CL-4 one wrong fact costs about one fact: one-fact-wrong score computed, no almost-right answer scoring as entirely wrong (one wrong finding row in one season costs that season's findings check: 150/155 = 0.968 test channel, 0.984 total with the judge channel full; one wrong composition rule costs one lever, e.g. the closed-workshop `consumed` slip loses only lv3a/lv3b = 38 points, 117/155 = 0.755)
- ❌ CL-5 every exact comparison's silent requirements (order, keys, path form, casing) either stated in the contract or compared insensitively, judged criteria read the same way - see Findings (item separator contradicts record_shapes.md; numeric-type warn). Verified clean: dict key order is ignored by `_same` (`sort_keys=True`) and by `_canon(json.loads(raw))`; every list order is stated (record_shapes.md, invariants.md N3); filenames are given in instruction.md line 9; finding codes and detail semantics in finding_codes.md; R1 "each written exactly as the register writes it" matches the instruction's "quoted exactly as the register writes it"
- ❌ CL-6 every shipped value the graded truth contradicts is signposted as suspect somewhere the agent can read (name the signpost) - the `", "` separator in record_shapes.md:22 against the graded `","`; the published slice files show the graded form but nothing marks the spec sentence as wrong (see Findings). Every other shipped value checked agrees with grading
- ✅ CL-7 every path the instruction names exists in every graded corpus (`_build_corpus_dir` writes all 11 season records, all 11 `calibration_` records, calibration_controls.json, example_workshop_report.json and all 12 rulebook/spec texts byte-identical to the shipped ones into every graded corpus)
- ✅ CL-8 oracle needs no fallback that skips an instruction-required step (solve.py `recover` lines 1059-1074 skips only draws whose settlement raises and exits with an error unless exactly one survives; no hardcoded draw or values)
- ✅ CL-9 test.sh and check setup never supply the value a later assertion measures (setup builds the input corpus and runs the agent's program; `structure_program_takes_directories` copies the grader's corpus into /app/data and restores the agent's /app/out afterwards - both measurement setup, not value supply)
- ✅ CL-10 every asserted fact traced to an agent-visible file or a derivation from one; nothing load-bearing lives only in solution/ or tests/ (season draws: published per season in its own controls/example and recoverable uniquely; caps, pools, ceilings, multipliers: season_charter.json; time limit and 48-requisition bound: instruction.md line 7; shapes: record_shapes.md; codes: finding_codes.md; R1-R4 values: derived from the shipped season)
- ✅ AL-1 every test and every outcome criterion promised by the contract (the instruction plus any spec file it points to); every constraint criterion quotes the instruction sentence it enforces; every conduct criterion holds for any competent route or earns its narrowing, and serves a real requirement (full map in Step 11)
- ✅ AL-2 every instruction promise graded (map in Step 11; "Do not look up an online solution" is the IN-10 sentence and carries no check by rule)
- ❌ AL-3 exact shapes agree across the contract, tests, solution (read the shipped spec, not just the prompt) - see Findings (item separator). All 56 key names agree between record_shapes.md, the grader and solve.py
- ❌ AL-4 no hidden graded behaviours beyond the contract - see Findings (same defect as IN-16)
- ✅ AL-5 oracle would pass every test (solve.py equals the grader on all 16 seasons and the shipped season; deterministic; trips no negative)
- ✅ AL-6 judged criteria consistent with solution and instruction (re-verified R3, R4 and R1 against the settled shipped season and the 840-draw search)
- ❌ AL-27 every stated rule has a fixture that actually triggers it (precedence pairs traced) - see Findings (RETIRED_REAGENT multi-reagent tie-break). Traced and triggered: A4+V4 on one forge (lv1), V9+A4 (lv2), `consumed` reference (lv3), Q8 tie (cl_priority), merge chain I2-I4 (cl_identity), A2 both boundaries, Q1, Q2, Q3, Q5 non-scarce, I4 retire of a surviving handle, V2 same-day acquisition, S2 same-day salvage, STOCK_FLOOR multi-reagent detail, N1 out-of-order file (cl_quiet), E3 and S6 (slice), Q9 (guild reports), S6 para 2, RETIRED_SMITH canonical detail
- ✅ AL-28 no penalty stacking: one action never fires more than one max-severity penalty across tests and judged criteria (replaying answers -> `negative_hardcoded_sample_answers` -3 only (a replay is name- and /app/data-independent and deterministic, so the other three test negatives stay False); directory-name dependence -1; nondeterminism -1 (the other two require identical repeat runs); /app/data reading -1; hook planting -1; writing /app/data R6 -5; third-party import R7 -3; network R8 -3; fabricated claim R9 -3. Each act maps to one penalty)
- ✅ AL-7 no unearned measured claims (TRUTH.md makes no score claims; "All five fail against an honest solution" is checked in Step 10)
- ✅ AL-8 time claims plausible for the actual work (and any declared difficulty band fits it) (expert 330 min / junior 1200 min for draw recovery by exhaustive slice search, a scarcity fixpoint, nine finding codes and a 48-request branch-and-bound)
- ✅ AL-9 solution discussion confined to TRUTH.md/task.toml, none of it reachable by the agent
- ✅ AL-10 hardcoding vector closed (no positive value check runs on the shipped season; replay is penalised)
- ✅ AL-11 grade-time environment abuse closed (the grader reads only its own temp corpora, the program's output dirs and the declared /app/out files; corpora opened read-only to uid 4001)
- ✅ AL-12 grader influence via /app closed (nothing imported or sourced from /app; the program runs as uid 4001 via setpriv; hook files are a negative)
- ✅ AL-13 answers not reconstructable without the work
- ✅ AL-14 reward path tamper-proof end to end (rewardkit is the only writer) (test.sh clears and locks; checks cannot raise; uid-4001 processes swept; reward.toml totals 155 and 19 match)
- ✅ AL-15 pinned offline contract consistent across all layers (verifier and agent network lines excluded; silence about the network is expected)
- ✅ AL-16 artifact filenames consistent bundle-wide (task.toml artifacts = instruction.md lines 7/9 = `SHIPPED_RECORDS` + `PROGRAM` in test_output.py = solve.sh target)
- ✅ AL-17 timeout story coherent (7200 s in both; verifier 3300 s against at most 28 program runs x 38 s = 1064 s plus grader settling)
- ✅ AL-18 no stale references or wrong counts anywhere (the one wrong count, TRUTH.md "four requisitions", is reported under gate 02 DS-22; test_output.py:2100 `_AGENT_TIMEOUT = 180` is overwritten at line 2570 before any use and states nothing to the agent)
- ✅ AL-19 no credential/secret exfiltration
- ✅ AL-20 no network exfiltration or supply-chain risk (the only piped download is exactly `curl -LsSf https://astral.sh/uv/install.sh | sh` in environment/Dockerfile line 11)
- ✅ AL-21 no destructive or resource-abuse operations (`shutil.rmtree` targets only the grader's own /app/data copy and /app/out, which it restores)
- ✅ AL-22 no obfuscated payloads
- ✅ AL-23 no prompt injection in agent-visible files (all 36 data files and instruction.md read)
- ✅ AL-24 filename-keyed shortcut closed (seasons live in random mkdtemp paths; `negative_filename_dependent_behaviour`)
- ✅ AL-25 nondeterministic-output shortcut closed (exact equality on 16 seasons; `negative_nondeterministic_output`)
- ✅ AL-26 category names the dominant work; description honest; keywords/tags related

## Step 11: Final coverage and overlap re-check

Verdict: ❌ FAIL (2 fails re-found, both already reported: gate 05 AL-3 and gate 01 IN-16; no new findings)

Re-derived from instruction.md, the spec files it points to (record_shapes.md, invariants.md, finding_codes.md, convention_register.md, calibration_slice.md and the seven rulebooks under /app/data), the 50 registrations in tests/test_output.py and the 9 criteria in tests/judge.toml.

### Coverage

Requirement -> checker:

| # | Requirement (file: sentence) | Checker |
|---|---|---|
| 1 | instruction.md l7 "Deliver one stdlib-only Python 3 program at `/app/out/settle_vault.py`." | `structure_program_delivered` (presence, compiles); stdlib half: R7 |
| 2 | l7 "It takes an optional data directory as its first argument and an optional output directory as its second, defaulting to `/app/data` and `/app/out`." | `structure_program_takes_directories` |
| 3 | l7 "It must settle whatever season it is pointed at rather than this one in particular, including a season drawn under other conventions" | 30 `cap_and_floor_*`/`retired_reagent_*`/`consumed_reference_*` checks and the 6 isolated-rule checks, each on a reseeded season under its own draw; `negative_hardcoded_sample_answers`; `negative_reads_training_corpus_at_runtime` |
| 4 | l7 "and a season with up to 48 requisitions" | `requisitions_12_allocation`, `requisitions_24_allocation`, `requisitions_48_first_allocation`, `requisitions_48_second_allocation` |
| 5 | l7 "it must finish any such season within 38 seconds on 2 CPUs" | the 38 s `communicate` timeout inside every program run (`_run_delivered`); a timeout fails the check reading that run |
| 6 | l7 "Two runs over the same corpus must write byte-identical files." | `negative_nondeterministic_output` |
| 7 | l9 the eleven records in `/app/out` | `structure_records_delivered`; no-argument half of `structure_program_takes_directories` |
| 8 | l11 "Every figure must agree with every other figure that reports the same quantity, and the conservation identity must close at zero." | vault, reconciliation, workshop-figure and guild-report checks of every season (exact equality to a truth whose residuals are 0) |
| 9 | l11 "The fields of every record, their order and the written form of each file are set out in `/app/data/record_shapes.md`." | `structure_canonical_serialisation` (written form), `structure_findings_canonical_form` (N3 order and tally), every value check (fields and list order) |
| 10 | l11 "A record counts only when it matches the settled season exactly." | `_same` exact comparison in every value check |
| 11 | l13 "Work only from `/app/data/`. Never write into it." | R6 (writes); the program-side reading is covered by item 3's checks, which point it at other directories |
| 12 | l13 "must use the Python standard library alone, with no third-party packages" | R7 |
| 13 | l13 "no network calls while it runs" | R8 |
| 14 | l13 "Do not look up an online solution, write-up, or answer key for this task." | none, by IN-10 rule |
| 15 | l13 final message: four conventions / total charge / closing entries / multi-finding entries | R1 / R2 / R3 / R4 |
| 16 | Each rule in the rulebooks the reseeded seasons exercise | see the gate 05 rule-trigger table; the RETIRED_REAGENT two-reagent tie-break (finding_codes.md:37-39) has no fixture (gate 05 AL-27) |

No requirement is left without a checker.

Test -> sentence it enforces:

| Test(s) | Sentence and file |
|---|---|
| `structure_program_delivered` | instruction.md l7 "Deliver one stdlib-only Python 3 program at `/app/out/settle_vault.py`." |
| `structure_records_delivered` | instruction.md l9 "Running it must leave the settled season in `/app/out`. ..." |
| `structure_program_takes_directories` | instruction.md l7 "It takes an optional data directory ... defaulting to `/app/data` and `/app/out`." |
| `structure_canonical_serialisation` | record_shapes.md l21-26 "Each record is one JSON object in UTF-8, indented by two spaces, with `", "` between items ..." - the assertion contradicts the `", "` wording (gate 05 AL-3, re-found) |
| `structure_findings_canonical_form` | invariants.md N3 l21-23 "ordered by entry identifier and then by code ... how many findings it recorded under each code"; record_shapes.md l69-72 |
| `cap_and_floor_{one,two}_*` (10) | rulebook_admission.md A4 l41-44 "A forge that the vault floor or a retired reagent also refuses is still judged against the cap"; rulebook_scarcity.md V4; invariants.md N3; plus record_shapes.md for each record. `cap_and_floor_one_findings` also turns on the S6/N3 reading (gate 01 IN-16, re-found) |
| `retired_reagent_{one,two}_*` (10) | rulebook_scarcity.md V9 l41-49; A4 l41-44; finding_codes.md RETIRED_REAGENT |
| `consumed_reference_{one,two}_*` (10) | convention_register.md l58-62 "`consumed` - the units of the reagent called for by every forge entry the season tests against the vault floor ..." |
| `requisitions_{12,24,48_first,48_second}_allocation` | rulebook_requisitions.md Q1-Q8; instruction.md l7 "up to 48 requisitions ... within 38 seconds" |
| `priority_tie_allocation` | rulebook_requisitions.md Q8 l39-44 |
| `cap_boundary_workshop_figures` | rulebook_admission.md A4 l32-39 |
| `partition_guild_reports` | rulebook_admission.md A2; invariants.md N5-N6; record_shapes.md Guild reports |
| `temporal_boundary_vault_audit` | rulebook_editions.md E1; rulebook_scarcity.md V2 "An acquisition recorded for a day the season calendar does not cover is not credited" |
| `merge_chain_smith_rows` | rulebook_identity.md I2-I5 |
| `quiet_rules_findings` | finding_codes.md; A2 l15-21; Q1-Q5; I4; V2; S2 "strictly before the salvage's own day"; N1 |
| `negative_hardcoded_sample_answers` | instruction.md l7 "settle whatever season it is pointed at rather than this one in particular" |
| `negative_filename_dependent_behaviour` | instruction.md l7 same sentence (output must follow content, not the path) |
| `negative_nondeterministic_output` | instruction.md l7 "Two runs over the same corpus must write byte-identical files." |
| `negative_reads_training_corpus_at_runtime` | instruction.md l7 "It takes an optional data directory as its first argument" |
| `negative_rebinds_verifier_dependencies` | no sentence; an anti-tamper negative that no honest route can trip (grader integrity), so it penalises no legitimate approach |

Judged criteria, by kind:

| Criterion | Kind | Burden met |
|---|---|---|
| R1, R2, R3, R4 | outcome | instruction.md l13 "Your final message must state the four conventions you recovered, each value quoted exactly as the register writes it, the season's total charge, the identifier of the entry that closed each workshop that reached its charge cap, and the identifier of every forge entry that carries more than one finding together with the codes it carries." Values verified against the settled season |
| R6 | constraint (scope) | instruction.md l13 "Never write into it." |
| R7 | constraint (tool use) | instruction.md l13 "The program you deliver must use the Python standard library alone, with no third-party packages" |
| R8 | constraint (tool use) | instruction.md l13 "no network calls while it runs" |
| R5 | conduct (code quality) | every competent route writes reviewable code; serves l7 "Deliver one ... program"; weight 3, not a preference at 5 |
| R9 | conduct (honest reporting) | every competent route passes; serves the l13 final-message requirement |

### Overlap

| Observable | Read by tests | Read by criteria |
|---|---|---|
| program's records on 16 reseeded seasons (findings, workshop figures, vault, reconciliation, guild reports, allocation, smith rows) | 41 positive value checks | none |
| presence / written form of the shipped season's 11 records and the program file | 5 structure checks | none |
| program's run-to-run, path and /app/data dependence; hook files | 4 test negatives | none |
| replay of the shipped summary | `negative_hardcoded_sample_answers` | none |
| final message facts | none | R1-R4 |
| source quality of settle_vault.py | none (`structure_program_delivered` only compiles it) | R5 |
| agent writes under /app/data | none (not uploaded in separate mode) | R6 |
| import statements of settle_vault.py | none (tests run the program; a missing module crashes the run, a different observable) | R7 |
| network use of the program | none | R8 |
| final message vs trajectory | none | R9 |

Zero overlap between tests and judged criteria.

## Step 10: Execution gate

Verdict: ✅ PASS (0 fails, 0 minors, 0 warns)

Tests-only grading per the kit: `exe_copy.py` validated tests/judge.toml against the rewardkit 0.2.1 schema and deleted it from the copies, so judge.toml was validated, not executed; no OpenAI key was set (the runs were launched under `env -u OPENAI_API_KEY`); the stub score covers the test channel only. The network was opened to `public` and the OpenHands pre-bake dropped in the two copies only; the bundle under review still declares `[environment] network_mode = "no-network"` and keeps its Dockerfile unchanged. These scores are evidence about grading, not about the offline policy being enforceable on this host.

### Preflight

```
$ harbor --version
0.24.0
$ docker ps
CONTAINER ID   IMAGE                                                                    COMMAND                  CREATED          STATUS                    PORTS     NAMES
558f966b16be   emberforge-vault-settlement__2ywfgxe__env-main                           "sh -c 'sleep infini…"   36 minutes ago   Up 36 minutes                       emberforge-vault-settlement__2ywfgxe__env-main-1
42b182749587   harbor-prebuilt:harbor-docker-egress-control-sidecar--e9f39ce1643ee690   "/opt/egress-sidecar…"   36 minutes ago   Up 36 minutes (healthy)             emberforge-vault-settlement__2ywfgxe__env-harbor-docker-egress-control-sidecar-1
c29fd964678d   schema-migration-plan-repair__dndzsqs__env-main                          "sh -c 'sleep infini…"   38 minutes ago   Up 38 minutes                       schema-migration-plan-repair__dndzsqs__env-main-1
a680a9ac4d01   harbor-prebuilt:harbor-docker-egress-control-sidecar--e9f39ce1643ee690   "/opt/egress-sidecar…"   38 minutes ago   Up 38 minutes (healthy)             schema-migration-plan-repair__dndzsqs__env-harbor-docker-egress-control-sidecar-1
$ ls ".../QC_2026-10-21/bundles/emberforge-vault-settlement"
environment
instruction.md
solution
task.toml
tests
```

(The running containers belong to other sessions and were not touched.) TS = 20261021T1923.

### exe_copy.py output

RUN copy (exit 0):
```
[exe-copy] copied /Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/emberforge-vault-settlement -> /private/tmp/oracle-qc/emberforge-vault-settlement-20261021T1923/run/emberforge-vault-settlement
[exe-copy] tests/judge.toml loads under the rewardkit 0.2.1 schema (validated, not executed)
[exe-copy] deleted tests/judge.toml
[exe-copy] tests/reward.toml -> weights = { test_output = 0.0064516129032258064 } (1 / positive total 155)
[exe-copy] task.toml [verifier] network_mode = "allowlist" -> network_mode = "public"
[exe-copy] task.toml [verifier] dropped allowed_hosts = ["api.openai.com", "*.openai.com"]
[exe-copy] task.toml [verifier.environment] network_mode = "allowlist" -> network_mode = "public"
[exe-copy] task.toml [verifier.environment] dropped allowed_hosts = ["api.openai.com", "*.openai.com"]
[exe-copy] task.toml [agent] network_mode = "allowlist" -> network_mode = "public"
[exe-copy] task.toml [agent] dropped allowed_hosts = ["api.anthropic.com", "api.z.ai"]
[exe-copy] task.toml [environment] network_mode = "no-network" -> network_mode = "public"
[exe-copy] environment/Dockerfile dropped: RUN curl -LsSf https://astral.sh/uv/install.sh | sh \ && . "$HOME/.loc...
[exe-copy] environment/Dockerfile: the pre-baked OpenHands SDK venv is gone from the copy (build speed only; oracle, nop and stub never start an installed agent)
[exe-copy] scores from this copy are TESTS-ONLY; the bundle under review was not edited
EXIT=0
```

STUB copy (exit 0):
```
[exe-copy] copied /Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/emberforge-vault-settlement -> /private/tmp/oracle-qc/emberforge-vault-settlement-20261021T1923/stub/emberforge-vault-settlement
[exe-copy] tests/judge.toml loads under the rewardkit 0.2.1 schema (validated, not executed)
[exe-copy] deleted tests/judge.toml
[exe-copy] tests/reward.toml -> weights = { test_output = 0.0064516129032258064 } (1 / positive total 155)
[exe-copy] task.toml [verifier] network_mode = "allowlist" -> network_mode = "public"
[exe-copy] task.toml [verifier] dropped allowed_hosts = ["api.openai.com", "*.openai.com"]
[exe-copy] task.toml [verifier.environment] network_mode = "allowlist" -> network_mode = "public"
[exe-copy] task.toml [verifier.environment] dropped allowed_hosts = ["api.openai.com", "*.openai.com"]
[exe-copy] task.toml [agent] network_mode = "allowlist" -> network_mode = "public"
[exe-copy] task.toml [agent] dropped allowed_hosts = ["api.anthropic.com", "api.z.ai"]
[exe-copy] task.toml [environment] network_mode = "no-network" -> network_mode = "public"
[exe-copy] environment/Dockerfile dropped: RUN curl -LsSf https://astral.sh/uv/install.sh | sh \ && . "$HOME/.loc...
[exe-copy] environment/Dockerfile: the pre-baked OpenHands SDK venv is gone from the copy (build speed only; oracle, nop and stub never start an installed agent)
[exe-copy] solution/ replaced by a stub solve.sh creating 12 empty artifact(s)
[exe-copy] scores from this copy are TESTS-ONLY; the bundle under review was not edited
EXIT=0
```

P (positive total) = 155.

### Runs

Commands (all seven chained under one `nohup bash -c '...; echo ALL_DONE'`, flags confirmed with `harbor run --help`: `--path/-p`, `--agent/-a`, `--env/-e`, `--job-name`, `--jobs-dir/-o`, `--yes/-y`):
```
harbor run --path "/tmp/oracle-qc/emberforge-vault-settlement-20261021T1923/run/emberforge-vault-settlement" --agent oracle --env docker --job-name oracle-{1..5} -o "/tmp/harbor-jobs-qc/emberforge-vault-settlement-20261021T1923" -y
harbor run --path ".../run/emberforge-vault-settlement" --agent nop --env docker --job-name nop-1 -o "/tmp/harbor-jobs-qc/emberforge-vault-settlement-20261021T1923" -y
harbor run --path "/tmp/oracle-qc/emberforge-vault-settlement-20261021T1923/stub/emberforge-vault-settlement" --agent oracle --env docker --job-name stub-1 -o "/tmp/harbor-jobs-qc/emberforge-vault-settlement-20261021T1923" -y
```
Log: /tmp/opencode-logs/emberforge-vault-settlement-step10-20261021T1923/runs.log (started 19:23:54 IST, ALL_DONE 19:58 IST; every `harbor run` exit=0; oracle-1 console "Trials 1, Exceptions 0, Mean 1.000, Total runtime: 8m 19s").

Rewards read from each trial's result.json `verifier_result.rewards.reward` and verifier/reward.json (no exception_info, no exception.txt in any trial):

| Agent | Run | Trial dir | result.json reward | verifier/reward.json |
|---|---|---|---|---|
| oracle | 1 | emberforge-vault-settlement__QuGNCay | 1.0 | 1.0 |
| oracle | 2 | emberforge-vault-settlement__Z5xxsbA | 1.0 | 1.0 |
| oracle | 3 | emberforge-vault-settlement__vnKwuo3 | 1.0 | 1.0 |
| oracle | 4 | emberforge-vault-settlement__jTQ27BE | 1.0 | 1.0 |
| oracle | 5 | emberforge-vault-settlement__PEQhSgc | 1.0 | 1.0 |
| nop | 1 | emberforge-vault-settlement__fxQvsMu | 0.0 | 0.0 |
| stub (oracle on stub copy) | 1 | emberforge-vault-settlement__KNaLUbJ | 0.0 | 0.0 |

oracle-1 reward-details.json: 50 criteria, 45 non-zero (all 45 positives), no negative fired. Failing checks: none. The five oracle runs agree, so no nondeterminism was observed.

### Stub judgement

a. STUB copy solution/solve.sh, in full:
```
#!/bin/bash
set -euo pipefail
P=/app/out/settle_vault.py; mkdir -p "$(dirname "$P")"; : > "$P"
P=/app/out/summary.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/vault_audit.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/reconciliation.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/data_quality.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/allocation.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/workshop_cinderhall.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/workshop_gloamworks.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/workshop_slagmoor.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/workshop_verdigris.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/guild_ashen_compact.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
P=/app/out/guild_tidebound_league.json; mkdir -p "$(dirname "$P")"; echo '{}' > "$P"
```
b. stub-1 reward-details.json: 50 criteria, checks with a non-zero value: none.
c. stub-1 scored rather than errored, so no stub-2 was needed.
d. Stub score 0.0 = 0 of P = 155 (0%). Healthy: the empty program fails `structure_program_delivered` (`len(src) > 500`), the `{}` records fail the non-empty checks, and every value check needs the program to run. The gate 05 CL-2 forgery price (a hand-written program and plausible records, no work) is 5 of 155 (3.2%), all from weight-1 presence/form checks; the stub earns less than that because it does not even write a 500-character program. No check paid while claiming to grade content.

### Diffs against the bundle under review

RUN copy:
```
Files .../emberforge-vault-settlement/environment/Dockerfile and /tmp/oracle-qc/.../run/emberforge-vault-settlement/environment/Dockerfile differ
Files .../emberforge-vault-settlement/task.toml and /tmp/oracle-qc/.../run/emberforge-vault-settlement/task.toml differ
Only in .../emberforge-vault-settlement/tests: judge.toml
Files .../emberforge-vault-settlement/tests/reward.toml and /tmp/oracle-qc/.../run/emberforge-vault-settlement/tests/reward.toml differ
```
STUB copy:
```
Files .../emberforge-vault-settlement/environment/Dockerfile and /tmp/oracle-qc/.../stub/emberforge-vault-settlement/environment/Dockerfile differ
Only in .../emberforge-vault-settlement/solution: TRUTH.md
Only in .../emberforge-vault-settlement/solution: solve.py
Files .../emberforge-vault-settlement/solution/solve.sh and /tmp/oracle-qc/.../stub/emberforge-vault-settlement/solution/solve.sh differ
Files .../emberforge-vault-settlement/task.toml and /tmp/oracle-qc/.../stub/emberforge-vault-settlement/task.toml differ
Only in .../emberforge-vault-settlement/tests: judge.toml
Files .../emberforge-vault-settlement/tests/reward.toml and /tmp/oracle-qc/.../stub/emberforge-vault-settlement/tests/reward.toml differ
```
Every difference is on the allowed list (judge.toml only in the bundle, reward.toml, task.toml, environment/Dockerfile, and solution/ contents for the stub copy only).

### Cleanup

Deleted only /tmp/oracle-qc/emberforge-vault-settlement-20261021T1923. Kept the jobs folder /tmp/harbor-jobs-qc/emberforge-vault-settlement-20261021T1923 and the log folder. Bundle under review afterwards: tests/ = Dockerfile, judge.toml, reward.toml, test.sh, test_output.py; solution/ = TRUTH.md, solve.py, solve.sh; task.toml still `network_mode = "no-network"`; `diff -rq` against the original bundle prints nothing (exit 0); `find ... -name __pycache__` over the bundle and the kit finds nothing.

Jobs folder: /tmp/harbor-jobs-qc/emberforge-vault-settlement-20261021T1923

## Housekeeping

Scratch analysis (grader copy with a stub rewardkit, rule variants, oracle comparison scripts) is kept as evidence in /tmp/opencode-logs/emberforge-vault-settlement-analysis-20261021T1856/; the temporary corpora those scripts created under $TMPDIR (prefix `efv_`) were deleted. No earlier vN.md existed in the report folder, so there is no "Compared with" section.
