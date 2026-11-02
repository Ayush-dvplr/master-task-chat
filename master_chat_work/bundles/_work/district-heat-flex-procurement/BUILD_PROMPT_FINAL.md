
You are building ONE Harbor evaluation task (an "input bundle") from an approved
design. Work slowly and in order. Read before you write. Never guess: if
something is missing or two sources disagree, stop and ask me.

## INPUTS (fill these in)

- DESIGN: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/ayush sah tasks/_work/district-heat-flex-procurement/DESIGN.md`   (the approved design; source of truth for the task idea. Never put it inside the bundle folder: the generator refuses an existing folder and --force deletes it)
- SLUG: `district-heat-flex-procurement`                                (lowercase, digits, hyphens; becomes the bundle folder name)
- CATEGORY: `optimization`
- SEED: `731904`

Fixed values:
- Generator folder: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/`
- QC folder (the authority): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/ayush sah tasks/_qc/Input_Bundle_QC/`
  (a frozen copy of `QC assigned/Input_Bundle_QC`, taken 2026-10-19; use ONLY this copy for reading the QC docs and running structure_qc.py, instruction_qc.py, tests_qc.py, judge_qc.py and exe_copy.py. Note: validate_bundle.py and playground.py call their own sibling copy at `Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`, whose four .py scripts are byte-identical to this one; do not change that.)
- Archetype: `domain-calculation`
- Author: `Ayush Sah <ayush.sah@ethara.ai>`
- Bundle goes to: `ayush sah tasks/district-heat-flex-procurement/`
- Your scratch space: `ayush sah tasks/_work/district-heat-flex-procurement/`. Data generators, wrong
  implementations, notes and logs go here, NEVER inside the bundle. The bundle may
  hold only the exact files the QC allows.

## RULE 0: plan first, then follow the plan

1. Before touching anything, create `ayush sah tasks/_work/district-heat-flex-procurement/TODO.md` with every
   phase below as a checklist (one line per step), and `PLAN.md` with your concrete
   plan for this task: the file list, the rule list, the check list.
2. Work through TODO.md in order. Tick a line only when its exit check passed, and
   write one line of evidence next to it (command run, number seen).
3. If a step fails, write what failed in `_work/district-heat-flex-procurement/LOG.md`, fix it, re-run the
   check. Never skip a step, never tick on a guess.
4. At the end, TODO.md must be fully ticked with evidence.

## RULE 1: hard limits

- NEVER edit anything in the generator folder outside `ayush sah tasks/`
  (`generate_bundle.py`, `validate_bundle.py`, `playground.py`, `templates/`, docs),
  and never edit anything in the QC folder. Record `shasum -a 256` of
  `generate_bundle.py`, `validate_bundle.py` and `templates/domain-calculation/*`
  in LOG.md at the start and the end; they must match.
- Python 3.12 standard library only, in the task, the oracle and the data
  generators. No network at solve time. No YAML (no stdlib parser).
- No em dash or en dash in ANY file of the bundle, data included. Use `-`.
- Never claim a score you did not measure. Write "not measured" instead.

## RULE 2: read these first (Phase 0), and only these

Read fully, then write a 10-line summary of each into PLAN.md:
1. QC `Final_checklist.md`: "What a bundle looks like", "Key harness facts",
   "Authoritative task.toml template", "Authoritative judge.toml template",
   "Authoritative test channel templates", "Foundational checks",
   "Client feedback checks" (CL-1..CL-10).
2. QC `01_Instruction_QC.md`, `02_Data_Solution_QC.md`, `03_Tests_QC.md`,
   `04_Judge_QC.md`, `05_Alignment_Integrity_QC.md`: the rules and checklists.
3. The generator's `templates/domain-calculation/` folder: every file.
4. The DESIGN.

Do not invent rules that are not in these files. If you think a rule exists,
quote the file and line where you read it.

## THE KEY RULES YOU MUST OBEY (from the QC; quoted IDs are the QC check names)

Bundle shape
- Exactly: `instruction.md`, `task.toml`, `environment/{Dockerfile,data/}`,
  `solution/{solve.sh,solve.py,TRUTH.md}`, `tests/{Dockerfile,test.sh,test_output.py,judge.toml,reward.toml}`.
  Nothing else anywhere. No `README.md`, no `test_weights.json`, no `rubric.json`, no `cheat/`.
- Two containers: the grader runs in a separate container where `/app/data` DOES NOT
  EXIST. Tests read shipped data only from the embedded `_SHIPPED_DATA` copy (TS-1).
- The 10 artifact paths are fixed by the archetype and must not change:
  `/app/out/derive_report.py`, `summary.json`, `policy_audit.json`, `data_quality.json`,
  `region_North.json`, `region_South.json`, `region_West.json`, `region_East.json`,
  `segment_commercial.json`, `segment_public.json` (all under `/app/out/`).

Data (`environment/data/`)
- Flat folder, at least 12 files, at least 5 different formats from: `.csv`, `.tsv`,
  `.jsonl`, `.json`, fixed-width `.txt`, `.ini` (configparser), `.xml` (stdlib
  ElementTree), plus ONE contract file `schema.md`.
- CHAINED: draw the dependency graph in PLAN.md. Every file must need at least one other
  file to be interpreted (an id resolved through a lookup, a unit or rate defined
  elsewhere, an override table, a calendar, a version map). At least 3 chains of
  length 4 or more. Every file is load-bearing: deleting any one file must change
  the outputs (F0b, DS-2, playground ablation).
- Size: every record file (csv/tsv/jsonl/txt) at least 2,000 lines; all inputs
  together at least 20,000 lines.
- No answers or answer-derivable values in data (DS-4, CL-3). No generic
  `sample_NNN` files, no "DRAFT" or redacted spec (DS-5).
- If a shipped value is deliberately wrong (a trap), something the agent can read
  must mark it as suspect (CL-6).
- Generate data with a deterministic script in `_work/district-heat-flex-procurement/datagen.py` from SEED.

Contract (`environment/data/schema.md`)
- States every rule needed for every graded number, every rounding step with its
  mode, every precedence and tie-break, and EVERY output key name, value type and
  ordering the tests compare (DS-25, CL-5, CL-10). Integer cents or basis points;
  no floats in outputs.
- Hard rules from the DESIGN go here in full. A rule may be stated as a general
  convention in a different section than where it applies, but it MUST be written
  down. A rule that lives only in `solution/` or `tests/` makes the task impossible
  (DS-21, F0e, CL-10).

Instruction (`instruction.md`)
- Says WHAT to produce and the rules of engagement, never HOW (IN-14). Do not list
  input files. Point at `/app/data` and `schema.md`.
- Names all 10 artifact paths exactly once each, and the run command
  `python3 /app/out/derive_report.py DATA_DIR OUT_DIR` (IN-6).
- One line for every property a test checks (sorted keys, trailing newline, integer
  cents, an ordering, a total that must balance), without explaining the rule.
- Contains "You have N seconds to complete this task." with N equal to
  `[agent] timeout_sec` (IN-1).
- Never mentions tests, grader, checker, reward, logs, solution, TRUTH.md (IN-2).
- Plain everyday English. Banned: leverage, utilize, delve, meticulous,
  comprehensive, robust, seamless, crucial, facilitate, furthermore, moreover, and
  any word of that kind. No "It is important to note". Under 6,000 characters.

Oracle (`solution/`)
- `solve.sh` runs `solve.py`, which writes `/app/out/derive_report.py` and runs it on
  `/app/data` to produce the 9 JSON files. Runs as uid 1000, offline (DS-11, DS-28).
- Computes everything from the data, no pasted answers, no fallback to hardcoded
  values (DS-14, CL-8). Obeys every contract rule, including ones no test triggers
  (DS-20).
- Written independently of the tests: less than 20% shared lines with
  `test_output.py` (DS-24, tests_qc oracle-overlap).

Tests (`tests/test_output.py`, rewardkit)
- At least 10 checks (no upper cap for this task). Each is
  `@criterion(description="...")` with no braces in the description, takes only
  `workspace`, returns a bool, NEVER raises (wrap every read and parse), and is
  registered once with `criteria.<name>(weight=W)`, W in {5,3,1,-1,-3,-5}.
- Contains its OWN reference implementation, written separately from `solve.py`,
  plus a hidden-case generator seeded from `EVAL_SEED`. The verifier runs the
  agent's `derive_report.py` on hidden extracts as user nobody via `setpriv`, with
  a timeout, killing the process group before returning (TS-24, TS-28).
- Partial credit: grade per output file and per field group, so one wrong fact
  costs about one fact (CL-4). Never one whole-dict equality for everything.
- For EVERY hard rule: one hand-built hidden case where the lazy reading changes the
  answer, and a check that fails the lazy reading (AL-27).
- Positives never pay for an absence (TS-25) or for source-code text (TS-27). No two
  checks read the same observable (TS-26).
- Negatives named `negative_<cheat>`, return True when the cheat happened, with an
  inline comment saying so. Keep the template's four
  (`negative_hardcoded_sample_answers` is required by the validator). One act
  triggers at most one penalty, summed across tests and judge (AL-28). Sum of
  negative weights at most the sum of positive weights.
- Weights mean something: 5 core outcome, 3 important sub-goal or edge case,
  1 minor or existence (TS-20).

Judge (`tests/judge.toml`)
- Copy the pinned `[judge]` and `[scoring]` header from the template exactly.
- At least 8 criteria (no upper cap for this task), ids R1, R2, ... with no gaps,
  keys and annotations in the exact order the QC table gives.
- Mostly `kind = "conduct"`, `evaluation_target = "trajectory"`: what the agent
  read, measured, checked, admitted. NEVER re-grade what a test already checks
  (JD-8, F0d): no "outputs are correct", no "stdlib only", no "no hardcoding".
- `constraint` criteria only for rules the instruction states, with
  `contract_sentence` copied word for word from `instruction.md` and
  `category = "instruction following"`.
- At least one criterion on the quality of the code the agent writes (JD-18).
- Negatives: reading `/tests` or `/logs/verifier`, claiming success its own last run
  contradicts, and similar real cheats of THIS task.
- Positive grammar only: no "not", "without", "fails to", "instead of". No vague
  words (properly, clearly, many, several, often, repeatedly); use counts.
- "The agent ..." for trajectory criteria, "The response ..." for
  final_answer/user_facing_message ones.

task.toml
- Keep the generated file. Only edit `description` (one paragraph, at most 100
  words, honest), `keywords`, `tags` and the time estimates. Category must name the
  dominant work. Do not add or remove keys.

TRUTH.md
- Exactly 8 sections in order: Defect, Load-bearing work, Verification, Root cause,
  Solution shape, Ordered plan, Pitfalls, Provenance. At least 4,000 characters.
- Defect list: at least 2 `(focal)`, 1 `(drift)`, 1 `(trap)`, each naming the test
  that catches it.
- Describe the task only. No generator, archetype, template, seed, tooling or "I
  built" narrative (DS-27). In Provenance: remove the `archetype:` and
  `generator_seed:` lines and set `authored_by: null`; recompute
  `fix_patch_sha256` (sha256 of `solve.sh`) and `solve_py_sha256`.
- Must match the shipped code and the real weights (DS-22).

## PHASES (put each in TODO.md)

P0 Read (Rule 2) and write PLAN.md: data file table (name, format, lines, role,
   depends on), rule table (rule, where in schema.md, lazy reading, separating
   case), check table (name, weight, observable), judge table (id, kind, observable).
   STOP and show me PLAN.md. Continue only after I say go.

P1 Scaffold, from the generator folder:
   `python3 generate_bundle.py --out "ayush sah tasks" --category optimization --archetype domain-calculation --seed 731904 --name district-heat-flex-procurement --author "Ayush Sah <ayush.sah@ethara.ai>"`
   Exit check: the folder exists and the printed archetype is domain-calculation.

P2 Data: write `_work/district-heat-flex-procurement/datagen.py`, generate into `environment/data/`, delete
   the template's own data files. Exit check: line counts, format count, a dash scan
   (`grep -rnP '[\x{2013}\x{2014}]'` returns nothing), and the dependency graph
   drawn in PLAN.md.

P3 schema.md. Exit check: for every key and rule in the PLAN tables, quote the
   schema.md line that states it.

P4 Oracle. Exit check: `solve.sh` runs locally against a copy of the data and writes
   all 10 artifacts.

P5 Tests. After writing, re-embed the data: replace the `_SHIPPED_DATA` value with
   `{relative_name: base64(zlib.compress(bytes, 9))}` for every file in
   `environment/data/` (the generator did this once at scaffold time and will not
   redo it). Exit check: oracle output scores every positive and no negative.

P6 Judge.

P7 Instruction. Exit check: every `contract_sentence` in judge.toml appears word
   for word in instruction.md.

P8 task.toml edits, then rewrite `tests/reward.toml` with
   `test_output = 0.5 / (sum of positive test weights)` and
   `judge = 0.5 / (sum of positive judge weights)`, full float (Python repr).

P9 TRUTH.md, last, with fresh digests.

P10 Lazy baselines. In `_work/district-heat-flex-procurement/wrong/`, write one wrong implementation per hard
   rule (the lazy reading), plus "all lazy". Grade each with the real
   `test_output.py` (stub `rewardkit` locally, or run the docker grader) and record
   the test-channel fraction in a table. At least one realistic row must fall
   between 0.40 and 0.60. If a wrong implementation scores 1.0, its rule is not
   graded: fix the separating case.

P11 Validation, from the generator folder:
   - `python3 validate_bundle.py "ayush sah tasks/district-heat-flex-procurement" --archetype domain-calculation` -> GATE: PASS, 0 FAIL, 0 WARN
   - `python3 playground.py "ayush sah tasks/district-heat-flex-procurement"` -> 0 FAIL (oracle 1.0, nop 0.0, stub near 0, every ablation <= 0.5)
   - the four QC scripts: `structure_qc.py`, `instruction_qc.py`, `tests_qc.py`,
     `judge_qc.py` from the QC folder -> no FAIL.
   Fix and re-run until clean. Re-check the generator checksums.

P12 Report to me: bundle path, data file table, hard rules, baseline table,
   validator/playground/QC results (paste the summary lines), and a plain list of
   what was NOT verified. Do not run Harbor Step 10; I run it myself.

Ask me before you deviate from the DESIGN. Ask me before you delete anything
outside the bundle and `_work/district-heat-flex-procurement/`.
