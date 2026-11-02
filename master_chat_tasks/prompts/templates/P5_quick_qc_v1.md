# P5 Quick QC, template v1 (21 Oct 2026)

A fast pass meant to catch most QC failures before the PL's full QC. It reports only and never fixes.

=== PASTE BELOW ===

You are running a fast, evidence-based QC pass on one Harbor 0.24 bundle. It is not the full QC. It covers the scripts plus the manual checks that fail most often. Report only; do not edit the bundle.

First read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`.

## Inputs
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/[[SLUG]]/` (read only)
- QC (live): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/[[DATE]]_[[SLUG]]/quickqc_r[[ROUND]]/`

## Step 1: scripts
Run each of these on BUNDLE and record every FAIL and WARN line verbatim, with the exit code:
- `structure_qc.py`
- `instruction_qc.py`
- `tests_qc.py`
- `judge_qc.py`
- `validate_bundle.py --archetype [[ARCHETYPE]]` (from GEN)
- `playground.py --skip-docker` (from GEN)

A WARN above 35 checks or criteria is approved (record it). Any other WARN must be listed with its fix.

## Step 2: manual checks
For each ID below, find the check in the live gate file (01 to 05 or `Final_checklist.md`) by ID AND wording, quote the rule, then quote the bundle evidence (`file:line`). Verdict: PASS, FAIL or COULD NOT VERIFY. Read each in-scope file in full; do not decide by grep.
- **Instruction:** IN-2 (no machinery), IN-6 (one landing place per artifact), IN-8 and IN-15 (every graded rule stated), IN-14 (no recipe), IN-16 (no unsettled ambiguity); also the script blind spots: comma timeout, dashes inside code, and grader, checker or verifier words.
- **Data and solution:** DS-2, DS-4, DS-21 (solvable from visible files), DS-24 (oracle independent), DS-25 (every required literal visible: give a count, like "N of M keys appear in <file>"), DS-27 (TRUTH provenance; if the validator and QC disagree, write `OPEN CONFLICT Q18`).
- **Tests:** TS-1 (no /app/data reads), TS-11 (determinism), TS-12, TS-20 (weight semantics), TS-25 (no absence positives), TS-26 (no double payment: pair every test with every other), TS-27 (no source-token grading), TS-28 (every third-party import installed in tests/Dockerfile).
- **Judge:** JD-2 (negative grammar beyond the script list), JD-5 (no compound criterion), JD-7 (true of the oracle, line by line), JD-8 (no overlap with any test: name the observable each side reads), JD-14, JD-15 (conduct two-step), JD-16, JD-18 (code-quality criterion).
- **Cross-layer:** AL-27 (trigger depth for every precedence pair), AL-28 (no penalty stack above 5 for one action).
- **Computed:**
  - CL-2: the forgery share, meaning the earned share of positive weight for hand-written fake artifacts. Name the paying tests.
  - CL-4: the one-fact-wrong score, meaning one wrong fact costs about one fact.

## Step 3: summary
`QUICKQC.md` contains:
- the script table;
- the manual table (ID, verdict, quoted rule, quoted evidence, one-line fix);
- the computed CL-2 and CL-4 numbers;
- open conflicts;
- `## Not checked`.

Also write `findings.json`, of the form `[{"id":"","verdict":"FAIL|PASS|CNV","file":"","line":0,"rule_quote":"","evidence_quote":"","fix":""}]`.

Done when: every ID above has a row, every script has its exit code, and the JSON parses. Final reply: FAIL count, WARN count, the IDs that failed, CL-2, CL-4, and paths.
