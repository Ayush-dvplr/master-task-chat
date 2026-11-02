# Way A: re-grade the same saved run (cb612aa)

Way A means: change only tests/, judge.toml, reward.toml (and solution/ for the oracle); keep instruction.md and environment/ byte-identical; grade the recorded artifacts again with no new agent run.

**Verdict: FEASIBLE_RISKY.** The mechanism exists and is self-labelled, and the edits can pass QC. But the pipeline does not count a re-graded old run as round evidence, and tests written while looking at that run are fitted to it.

## (a) Is it mechanically possible? Yes, with conditions.
- Harbor 0.24.0 (installed, the version recorded in job-lock.json) ships `harbor trials regrade SOURCE -p TASK_PATH` (`…/site-packages/harbor/cli/trials.py:995`) and a job-level form (`cli/jobs.py:2803`, which prints the regrade delta). In the repo src it is `H/src/harbor/trial/regrade.py`.
- How it works (`regrade.py` doc l.1-13, `_seed_from_source` l.383-389, `_run` l.392-408): it copies `agent/` and `artifacts/` into a fresh trial, runs the separate-mode verifier with the new tests, and **re-runs the rewardkit judge**, because the judge lives inside the verifier (finalize.log step 3). The source trial is never modified.
- Preconditions, with code and current state:
  1. The verifier is separate mode with no `[[steps]]` (`check_task_regradable` l.79-95). All six pipeline tasks have `task.toml:23` set to `environment_mode="separate"`.
  2. Task names match (`_validate_regradable` l.278-305).
  3. Every artifact the new task declares has a manifest entry with status ok/empty and bytes on disk (`_validate_artifact_coverage` l.307-381). **cold-chain fails this**: harden_w1 added `/app/repo/src/task/core.py` to `task.toml:2`, but it is missing from the latest run's `artifacts/manifest.json`. Sentinel, tariff, schema, district and metered are covered.
- The output is recorded as a regrade: `source_trial = SourceTrialConfig(action="regrade")` (`cli/trials.py:990-1020`, `models/trial/config.py:489,501`, `models/job/lock.py:91-121`). The new `task_checksum`/digest is the new bundle's dirhash (`models/task/task.py:216-231`). So nobody can mistake a regrade for an agent run, which is good.
- UNKNOWN: whether `scripts/finalize_task_output.py` and `package_rfp_bundles.py` accept a regrade trial dir. Neither mentions `source_trial`. Settling check: `grep -n "source_trial\|regrade" H/scripts/*.py` (I already ran it: 0 hits). Then dry-run `package_rfp_bundles.py` on a scratch copy of a regraded dir.

## (b) Is it QC- and pipeline-legal? QC: yes. Pipeline rules: no.
- QC grades the bundle, not the agent run. Way A edits pass QC under the same rules as any edit (LEGITIMACY_RULES.md kinds 1-3), plus the oracle gate (`Final_checklist.md:390`, 5 fresh oracle runs at exactly 1.000, nop exactly 0.000) and DS-22 sha recompute. No QC rule ID forbids grading a saved trajectory. `Final_checklist.md:401/:404` ("freshly executed runs of the exact bytes being shipped"; copying numbers = automatic fail) is about the **oracle/nop execution gate**, but its spirit applies: the agent run did execute against the shipped instruction and environment bytes, while the verifier bytes are new.
- Pipeline rules point the other way:
  - `LEVER_RULES_v3.md:211`: the fresh blind read is "the only measure of a round … never the old agent program".
  - `:213`: "Not evidence: differential fuzz of an old program on a changed bundle".
  - `:207`: the gate counts real harness runs.
  - `KNOWLEDGE.md:6, :46`: flow build -> QC -> runs under gate.

  A regrade is literally "an old program on a changed bundle". Under the current rules it **cannot be the push run** unless Ayush overrides `:211/:213`. The user's 27 Oct rule says "1 run on a QC-passed bundle". The recorded run was not graded by a QC-passed bundle. Whether a regrade satisfies that sentence is a ruling for Ayush. UNKNOWN; settling check: ask Ayush.
- Packaging trap: `package_rfp_bundles.py` packages Tasks_INPUT as it is **at packaging time** (`_task_source` l.152-172, `package()` l.233-238), while it copies `report.json`/score values "never recomputed" (l.73-75). If you edit tests and **do not** regrade, Output_RFP ships new tests next to old scores. Only a regraded run, or a new run, makes the shipped tests match the shipped score.

## (c) Does it give a trustworthy gate? Mostly no.
- Overfit by construction. Tests designed while looking at the run's trip points will catch that run with certainty. The real question is whether they catch the **next** run. Same-bytes run variance is ±17.55 pp tests and ±20.03 pp final (sentinel checksum 2e46383072) and ±20.81 pp tests (LEVER_RULES_v3.md:145 G13). A margin earned on one fitted run says nothing about a new one.
- The judge is re-run on regrade (LLM `gpt-5.6-sol`), so even Way A rubric scores are not deterministic. Judge-only variance on a fixed trajectory is UNKNOWN. Settling check: regrade one run twice against its **unchanged** bundle and diff the rubric values.
- Tests-100 runs (10 of 21; TRIP_METHOD.md §4) have no test trip to mine. Way A can push their tests below 100 only by adding a lever test the recorded program fails. That is a legitimate move only if the lever is a stated rule the fixture never constructed (AL-27, e.g. schema's larger hidden graphs). It is not legitimate if the test targets that program's quirks.
- Where Way A is useful and legal today: as a **diagnostic** before Way B. Regrade the last run against the hardened bundle to confirm that (1) the new tests are wired and score the old artifacts as designed and (2) no new check fails on correct output, which would be a false negative. This is the same number designers already hand-compute ("probe program 0/48 -> 83.7", metered DESIGN.md:30). It just comes from the harness instead of a hand script, and it costs no agent run.

## Per-task eligibility (instruction and environment unchanged since the run, and artifacts covered)
| task | eligible | evidence |
|---|---|---|
| schema-migration | **yes** | HARDEN_REPORT.md:11 "No agent-visible text changed"; :57 changed only tests/test_output.py, tests/reward.toml, solution/solve.py, solution/TRUTH.md; artifacts ok |
| sentinel | yes, for a QC v7 fix that touches only judge.toml or tests | attempt 7 artifacts all ok (8 of 8) |
| metered-usage | UNKNOWN | no HARDEN_REPORT for w2. Settling check: diff `Tasks_INPUT/metered-usage-rating-pipeline/{instruction.md,environment}` against `H/Output_RFP/metered-usage-rating-pipeline/` (packaged at run time) |
| tariff | no | env changed: environment/ci/vouchers.csv 198->210 rows (HARDEN_REPORT.md:11); probe staged copy predates rounds 2-3 (DESIGN.md:7) |
| district-heat | no | new sentence in environment/data/schema.md:162-163 (HARDEN_REPORT.md:12-14) |
| cold-chain | no | env, instruction.md:9 and new artifact core.py changed (HARDEN_REPORT.md:10-14); fails artifact coverage |
