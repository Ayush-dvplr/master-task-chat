# beta-task-generator: reverse-engineering report

Source: `/Users/mac/Desktop/Terminal Bench/beta-task-generator/` @ `17e9f70` (3 commits, 2026-09-10/11, author `ayushsah-dev`). The source was read only; anything executed ran in a scratch copy (see `RUN_LOG.md`). Paths below are relative to the source root unless stated otherwise. `SNAP/` means `qc/snapshots/upstream-c6cc84f98f9e/`.

Key findings (detail in the sections cited):
- The controller writes no task content. It records work orders, hashes, receipts and gates; the coding agent authors everything (A).
- In code, hardness is measured only by the per-run gate (test < 90, rubric < 90, combined < 30) and the oracle/nop/stub check. Every technique that *creates* hardness is prose (D).
- 17 of the 22 keys in `config/defaults.json` are never read, and `qc/policy/beta.json` is never read. Thresholds are hard-coded elsewhere (H, K).
- The pinned QC digests match only CRLF bytes, so on macOS/Linux every QC and repair path is blocked (F.6, L).
- The tool has no data generation, no data-volume control and no format rules. The templates it learns from carry 3-8 KB of text data (H).
- Mode 12 QC Repair is the strongest and most reusable subsystem (F).

## A. Purpose and operating model

**What it is.** It is a local, stdlib-only Python controller (`pyproject.toml:4-16`, "Dependency-free controller foundation", `runtime = "stdlib-only"`, tests use `unittest`). Twelve Markdown playbooks sit on top of it. A coding agent (Claude Code or OpenCode) reads the playbooks and does the actual authoring. The README calls it an "agent-driven, local control center for producing difficult, fair Harbor input bundles" (`README.md:3`). The handbook says it is "a control center, not an automatic task factory" (`BETA-GENERATOR-HANDBOOK.md:40`).

**The controller writes no task content.** `tasks create`, `harden` and `overgenerate` only register `PENDING_AUTHORING` work orders (`generator-use-instruction.md:187-189`, `AGENTS.md:16-17`). Observed: `tasks create` writes a skeleton bundle holding only `instruction.md` ("# PENDING_AUTHORING ...") and a 3-line `task.toml` (RUN_LOG #13). The agent writes every task file. The controller records state, hashes, receipts, approvals and gates.

**What it refuses to do** (each is stated in the docs, and code backs it where noted):

| Refusal | Doc anchor | Code backing |
|---|---|---|
| Call models or Harbor automatically, install software, call external APIs | `README.md:4-5`, `generator-use-instruction.md:184-185` | No model or Harbor client exists anywhere in `core/`. The only network code is `assets download` (`core/asset_transfers.py`) and `sources check` (`git fetch`, `core/source_diff.py:43-55`) |
| Git commit, push, init or hooks | `generator-use-instruction.md:101-103` | `core/` has no git write calls. `source_diff.py` only runs `git init --bare` and `git fetch` into a temp dir under `workspace/upstream/` |
| Task families other than correction and derivation | `generator-use-instruction.md:54-56` | Ideas only: `core/ideas.py:11,109-110`, `core/refinement.py:12,174-178` |
| Rubric `state_change` | `generator-use-instruction.md:59-60` | Policy flag `config/defaults.json:23`. Whether code enforces it is covered in F |
| Infer the "latest" task or run | `AGENTS.md:10`, `playbooks/resume.md:3-4` | Every command needs an explicit ID (CLI arguments, see B) |
| Treat pasted text as approval | `AGENTS.md:24`, `CLAUDE.md:25-26` | Approvals exist only through the `proposals approve` CLI call (see B) |
| Ship drafts, ZIPs or generator history in the final folder | `generator-use-instruction.md:90-92,100-101` | `release export` only (see B) |

**Safety model.**
- *Write scopes.* A task mode may change only the selected or new bundle and its workspace records. Generator, policy, settings, snapshots and adapters need "a scoped proposal plus a separate operator approval" (`CLAUDE.md:23-26`, `generator-use-instruction.md:28-30`).
- *Proposals and approvals.* `create -> approve -> require_approval -> consume` (`core/API.md:97-114`). An approval binds the immutable proposal bytes, is consumed once and records `advisory_manual` assurance. Application re-checks the captured base hashes (`core/update.py:47-54`) and writes a backup (`core/update.py:22-31`).
- *Three separate change channels:*
  1. Settings: `settings propose/apply` over `workspace/settings/*` (`core/settings.py:38-61`).
  2. Source baselines: `sources baseline propose/apply` writes `workspace/settings/source-baseline.json` (`core/upstream.py:61-89`).
  3. Generator files: `updates propose/apply` with `--validation {compile,unit-tests}` (`core/updates_cli.py:20-54`).
- *Single-writer lock and transactions.* `workspace/write.lock` serializes writers. Transactions move through PREPARED, APPLYING, COMMITTED, RECOVERY_REQUIRED and ROLLED_BACK. "Lock age never grants takeover" (`core/API.md:47-58`).
- *Honesty about assurance.* Every doc says the protection is advisory, not tamper-proof against the same OS user (`generator-use-instruction.md:104-105`, `BETA-GENERATOR-HANDBOOK.md:48`).
- *Evidence vocabulary.* PASS, FAIL, WARN, NOT_RUN, BLOCKED, STALE, INCONCLUSIVE. "A missing/errored run is NOT_RUN, never PASS" (`generator-use-instruction.md:79-82`, `BETA-GENERATOR-HANDBOOK.md:181`). Observed: a fresh task gives `input_qc: NOT_RUN`, `difficulty_target: NOT_EVALUATED`, `release_ready: false` (RUN_LOG #16).
- *Authority order for documents:* operator entry and design guide, then defaults, then the playbook and prompts, then the pinned snapshot, then the archive (`references/curated/source-catalog.md:3-12`).

## B. Architecture map

### B.1 Layers

```
CLI (core/cli.py + 10 *_cli.py registrars)  ->  one JSON line on stdout; exit 0 on success, 2 on BetaError (core/cli.py:121-138)
   |
Services: revisions / ideas+refinement / mechanisms / analysis / assets / qc_runner+qc_semantics / qc-repair suite /
          runtime_intake+scores / verdicts / delivery / upstream+source_diff / settings / file_updates
   |
Foundation: state.Store (content-addressed objects + active manifest + journals + global lock),
            proposals (approve/consume), update/rollback, file_transactions, bundle_transactions, paths.safe_child, common (strict JSON, hashes)
```

`--root` defaults to the package directory (`core/cli.py:32,107`). Exception: `init` always reads `config/defaults.json` from the package and ignores `--root` (`core/cli.py:148`).

### B.2 Module table (all 61 `core/*.py` plus `tools/archive_sources.py`)

Paths under "Reads / writes" are under `--root`. "CLI" is the command that reaches the module.

| Module | Role (one line) | Reads -> writes | CLI |
|---|---|---|---|
| `__init__.py` | re-exports Store, BetaError, hashes | - | - |
| `__main__.py` | `raise SystemExit(main())` | - | `python -m core` |
| `cli.py` | argparse tree, foundation verbs, dispatch, JSON envelope | `config/defaults.json` (init) | init, status, resume, settings, tasks create/revise, proposals, rollback, recovery |
| `cli_types.py` | type aliases for registrars | - | - |
| `paths.py` | `safe_child` path jail: no empty, absolute, escaping or root path (`:8-18`) | - | all |
| `permissions.py` | JSON proposal scopes: `settings` -> `workspace/settings/`, `task:<id>`, `generator` -> `config/`; `.json` only (`:8-22`) | - | via proposals |
| `common.py` | strict JSON (no NaN, no duplicate keys, object root), atomic save, `file_hash`, `tree_hash` (`:32-115`) | any | all |
| `settings.py` | versioned settings; `profile_hash` = sha256 of `current.json` bytes | defaults -> `workspace/settings/{current,revisions/N}.json` | init, settings * |
| `bootstrap.py` | read-only `status` / `resume`; `release_ready` hard-coded False (`:86-87`) | manifest, settings, journals, `tasks/*/task.json` | status, resume |
| `state.py` | `Store`: objects `workspace/objects/<sha>.json`, `active-manifest.json`, journals `workspace/transactions/`, lock `workspace/write.lock` | -> same | every write |
| `models.py` | enums and record parsers; `max_tests >= 10` is the only settings range check (`:116`) | - | - |
| `proposals.py` | proposal -> single approval (bound to proposal-file hash) -> consume; `advisory_manual` | -> `workspace/proposals/<id>/{proposal,approval}.json` | proposals approve |
| `update.py` | apply an approved JSON proposal with base-hash check and backup (`:12-54`) | -> `workspace/backups/<id>.json` | settings apply, sources baseline apply |
| `rollback.py` | approved JSON-record rollback; refuses third-state targets | backups -> records | rollback propose/apply |
| `file_transactions.py` | crash-safe byte writes with base64 backups and journal | -> `workspace/file-transactions/*`, backups | updates apply/recover |
| `file_updates.py` | generator-file proposals; allow-list `core/ config/ playbooks/ prompts/ tests/` + `generator-use-instruction.md` (`:24-25`); candidate validation in a temp copy (`compileall` or `unittest`, no timeout, `:222-242`) | repo files -> proposals | updates propose/apply/rollback/rollback-apply |
| `bundle_transactions.py` | publish a bundle dir and records atomically; writes the PENDING_AUTHORING stub (`:97-104`) | -> `workspace/revision-transactions/*`, `workspace/tasks/<id>/revisions/<n>/<name>/` | tasks create/revise/harden/overgenerate/adopt |
| `revisions.py` | task and revision records; name regex `^[a-z0-9]+(?:-[a-z0-9]+)*$` (`:14`); `adopt` (no name validation), `verify` (tree hash) | -> `workspace/tasks/<id>/{task.json,revisions/<n>/revision.json}` | tasks * |
| `tasks_cli.py` | harden/overgenerate/adopt/verify handlers (only the `mode` string differs) | - | tasks * |
| `contracts.py` | contract-matrix validator (family, at least 5 constraints, reachability, duplicate observables, no `state_change`, conduct needs `competent_routes_satisfy`) | settings revisions | **none** (tests only) |
| `package_contracts.py` | exact Harbor layout for release: exact file sets, flat non-empty data, `environment_mode="separate"`, doc-leak markers (`:10-45`) | bundle; vendored `output_qc.py` | release check/export |
| `delivery.py` / `delivery_cli.py` | `release check` (4 gates PASS or PASS WITH EXCEPTIONS plus a current subject hash), `release export` (copy-verified, under `workspace/releases/` only) | -> `workspace/releases/<name>/`, `.verification.json` | release check/export, host doctor |
| `host_adapters.py` | `host doctor` probes `python/git/claude/opencode --version` (5 s timeout) | - | host doctor |
| `adapter_recovery.py` | blocks new transactions while any file, revision or release `pending.json` exists | - | all writes |
| `runtime_intake.py` | import Harbor run reports as receipts; Harbor field mapping (`:34-38`); oracle/nop/stub solvability (`:224-250`); policy matrix must equal settings (`:51-53`) | report.json -> receipts | runs import/policy-register/status/schema |
| `runs_cli.py` | argparse for `runs` | - | runs * |
| `scores.py` | decimal score parsing; `model_gate` test<90, rubric<90, combined<30, all strict (`:7-8,42-49`); `evaluate_matrix` (`:52-70`) | - | via runs / qc status |
| `verdicts.py` | per-gate reduction and release readiness (`input_qc`, `output_qc`, `solvability`, `difficulty_target`) | receipts | qc status, release check |
| `findings.py` | checker-line parser; 100-cap exception (rule N1 only, `:52-62`); waiver reduction (`:65-82`); 3-strike fingerprint counter (`:96-136`) | -> `workspace/qc/repairs/<h>.json` | qc repair-attempt/repair-status |
| `qc_snapshot.py` | validate pinned snapshot digest from `config/source_components.json` (`:29-47`); per-case context | snapshot | qc verify, qc-repair |
| `qc_runner.py` | run the 4 input checkers or `output_qc.py` as subprocesses, 120 s each; mutation guard; receipt | snapshot, bundle -> receipts | qc verify, qc-repair verify |
| `qc_receipts.py` | hash-bound receipt store; "current" = subject hash, integrity, dependencies and log hashes all match | -> `workspace/qc/{receipts,index}/` | all qc |
| `qc_semantics.py` | semantic (LLM/manual) review schema from pinned checklist IDs plus per-test and per-criterion IDs; waivers | snapshot `.md` -> receipts | qc semantic-schema/submit/waive |
| `qc_cli.py` | argparse for `qc` | - | qc * |
| `qc_repair.py` | Mode 12 case lifecycle: apply, status, resume, continue, attach-evidence, report | -> `workspace/qc-repairs/<case>/` | qc-repair * |
| `repair_intake.py` | open case, provenance binding, frozen context hashes | -> case.json, inputs/ | qc-repair open/bind-snapshot/confirm-subject |
| `repair_analysis.py` | Real / False positive / Vague analysis validation, Q-ID assignment, tables | -> `tables/<v>.json` | qc-repair analysis-schema/submit/table |
| `repair_selection.py` / `repair_selection_support.py` | narrow NL selection grammar, reanalysis, authorization | -> `selections/`, `authorizations/` | qc-repair select/selection-submit |
| `repair_dependencies.py` | dependency closure (tests<->weights, rubric/toml/instruction -> README/TRUTH), bijection, documented-count check | bundle | (internal) |
| `repair_revision.py` | new revision for a repair; hash-bound patch manifest (no shell field) | -> revision | qc-repair apply |
| `repair_verification.py` | post-repair diff/scope check, mechanical QC on the case snapshot, semantic reconcile, attempt counters | -> receipts, case | qc-repair verify/verification-submit |
| `repair_artifacts.py` | evidence copy with manifests; read-only snapshot copy | -> `inputs/` | (internal) |
| `repair_models.py` | enums (case status enum unused) | - | - |
| `repair_cli.py` | argparse for `qc-repair` (16 verbs) | - | qc-repair * |
| `ideas.py` / `refinement.py` / `ideas_cli.py` | idea record, 3 finalists, select, review rounds (limit 3) | -> `workspace/ideas/<id>/idea.json`, `task.json.refinement_rounds` | ideas * |
| `mechanisms.py` / `mechanisms_cli.py` | evidence-linked mechanism cards; fingerprint = sha256 of {visible_rule, trigger, wrong_interpretation, root_cause} | -> `workspace/mechanisms/{cards/<id>/<ver>.json,catalog.json}` | mechanisms * |
| `analysis.py` / `analysis_cli.py` | reference / benchmark / feedback inventory and analysis records, independent review | -> `workspace/analysis/{inventories,reports}/` | references/benchmarks/feedback * |
| `assets.py` / `asset_transfers.py` / `licenses.py` / `assets_cli.py` | licensed asset import/download, 1 GB cumulative budget, zip/tar safety, SSRF guard, SPDX allow-list | -> `workspace/tasks/<id>/revisions/<n>/assets/<asset_id>/`, `assets-budget.json`, `workspace/{staging,quarantine}/` | assets import/download |
| `upstream.py` | import a source folder as an immutable NOT_ACTIVE snapshot; baseline propose/activate | -> `workspace/sources/{snapshots,manifests}/` , `workspace/settings/source-baseline.json` | sources import/baseline |
| `source_diff.py` | shallow `git fetch` of a fixed upstream URL, file-level diff against the baseline | -> `workspace/upstream/<head>/{repository,report.json}` | sources check |
| `sources_cli.py` / `updates_cli.py` | argparse | - | sources *, updates * |
| `tools/archive_sources.py` | one-off builder: copies the sibling `upstream-review` checkout into `qc/snapshots/`, builds `references/archive` and `catalog.json`, writes `config/source_components.json` (`:223-283`) | parent dirs -> snapshot/config | not in CLI |

### B.3 Data flow: idea to delivered bundle

```
[Mode 4] ideas start ──> prompt A (manual ChatGPT) ──> agent critique ──> ideas submit (exactly 3 finalists)
   └─> USER: ideas select ──> review rounds (ideas submit review; ≤3, shared counter in task.json)
[Mode 1/3] tasks create|overgenerate ──> workspace/tasks/<id>/revisions/<n>/<id>/ (PENDING_AUTHORING stub + work order)
   └─> AGENT authors all files by hand (contract matrix, data, instruction, task.toml, Dockerfiles, oracle, tests, rubric, README, TRUTH)
       (optional) assets import/download ──> revisions/<n>/assets/<asset_id>/ (agent must copy into environment/data/ itself)
[Mode 6] qc verify --kind input ──> pinned Input_Bundle_QC/*.py ──> receipt (workspace/qc/receipts)
         qc semantic-schema/submit ──> semantic receipt;  qc waive (WARN/MINOR only)
         (operator runs Harbor outside beta) runs policy-register + runs import ──> runtime receipt (oracle×2, nop, stub, model runs)
         qc verify --kind output (output_qc.py on trajectory/output evidence)
         qc status ──> verdicts.readiness: input_qc, output_qc, solvability, difficulty_target
[Mode 12 if a QC report exists] qc-repair open → analysis → table → select → selection-submit → apply (new revision) → agent edits → verify → verification-submit → report
[Mode 2] tasks harden ──> new revision ──> back to Mode 6
release check (all 4 gates PASS / PASS WITH EXCEPTIONS, current hash) ──> release export ──> workspace/releases/<name>/ (folder, copy-verified)
```

Records the workflow relies on: `task.json` (revision pointer, `profile_hash`, `refinement_rounds`), `revision.json` (work order), `idea.json`, receipts and index, the qc-repair `case.json` with frozen context and attempt counters, and `assets-budget.json`.

## C. The 12 modes

The routing table is in `generator-use-instruction.md:32-47`. Analysis modes are read-only over the material supplied to them (`:49-50`). Every mode starts with `status` and an explicit ID (`generator-use-instruction.md:8-24`). The "Code" column says what the controller actually enforces. Everything else in a row is agent procedure written in prose.

| # | Mode / playbook | Inputs | Key steps (quoted or condensed from the playbook) | Outputs and records | Stop conditions | Code |
|---|---|---|---|---|---|---|
| 1 | Create `playbooks/create.md` | domain or accepted idea; family; deliverables; assets; constraints; target profile | "If no idea is selected ... show exactly three finalists and stop for the USER's choice" (`:10-12`). 1 contract matrix first (`:25-27`); 2 data inventory, licence, at most 1 GB, flat `environment/data/` (`:28-33`); 3 instruction "as WHAT, not a recipe" (`:34-35`); 4 task.toml, agent-neutral Dockerfile, independent oracle, hand-computed fixtures (`:36-38`); 5 at least 10 deterministic tests including "hidden/reseeded legal inputs, and delivered-program reruns" plus anti-cheat negatives (`:39-42`); 6 at least 8 rubric criteria, 5 stated constraints first, no `state_change` (`:43-46`); 7 README, then TRUTH last from disk (`:47-49`); then verify.md | `workspace/tasks/<id>/task.json`, `revisions/1/revision.json` (work order `kind: agent_authoring`), skeleton bundle (RUN_LOG #13); handoff report list (`:57-64`) | no selection; unknown licence or size; runtime permission; release blockers (`:66`) | `tasks create` (record and skeleton only) |
| 2 | Harden `playbooks/harden.md` | exact bundle path; goal or evidence; rounds consumed | Hash and preserve the baseline (`:8-11`). Diagnosis table separating "validity defect / weak difficulty / unsupported complaint" (`:13-21`). Repair: close disclosure; "Correct derivations ... rather than changing expected answers, removing edge tests, or lowering weights to silence QC" (`:25-28`); strengthen through "legal adversarial fixtures, rule interaction, completeness, boundary ownership, reconciliation, deterministic high precision, or program reruns. Do not add volume" (`:29-31`); rebuild the contract matrix and all-pairs map (`:35-37`) | new revision via `tasks harden` (copy of the prior revision, `PENDING_AUTHORING`); before/after observable table (`:54-55`) | three total rounds per bundle, then pause (`:45-47`) | `tasks harden` (revision copy only) |
| 3 | Overgenerate/refine `playbooks/overgenerate-refine.md` | domain or idea; later, real run evidence | "create 6-10 mechanism sketches. Reject reskins, hidden-information tricks, unsupported performance gates" (`:15-17`); compare "state transitions, contract breadth, interaction depth, gradeability, asset feasibility, likely shortcuts, and solvability" (`:18-20`); exactly 3 finalists (`:21-22`); build the choice using create.md (`:23`); ingest all attempts, "Never rerun until favorable or discard an attempt" (`:24-27`); "Diagnose failed observables, not just aggregate score" (`:28-30`); refine minimally (`:31-33`) | `tasks overgenerate` revision; per-round change and evidence record | 3 rounds per bundle total, never reset; pause and show options (`:35-40`) | `tasks overgenerate`; `runs import` for evidence |
| 4 | ChatGPT Ideas `playbooks/chatgpt-ideas.md` | domain; optional local reference; an existing task ID (CLI requirement, `BETA-GENERATOR-HANDBOOK.md:269`) | emit prompt A from `prompts/idea-workshop.md`; the user pastes it into ChatGPT (`:12-15`); critique on 8 axes (`:19-28`); targeted refinement requests (`:30-32`); exactly 3 finalists; record rejected ideas and nearest matches (`:36-38`); convert to the JSON envelope (`:40-45`) | `workspace/ideas/<idea-id>/idea.json` holding raw responses, finalists, refinements | user choice; 3 refinement rounds (`:34-36`) | `ideas start/submit/finalists/select/status`, schema-enforced (see E) |
| 5 | Upstream `playbooks/upstream.md` | update check or source folder | inventory without executing (`:10-15`); "Compare generator guidance, Input Bundle QC, and Output Bundle QC separately" (`:17-20`); keep raw upstream rules; "Unknown or changed rules invalidate old dispositions" (`:24-28`); proposal with exact paths, base hashes, diff, migration, rollback (`:30-32`) | `workspace/sources/snapshots/<id>/` (read-only), `workspace/sources/manifests/<id>.json`, `workspace/upstream/<head>/report.json` | proposal-specific approval (`:34-41`) | `sources import/check/baseline`, `updates *` (see I) |
| 6 | Verify `playbooks/verify.md` | exact bundle; profile and axes | 9-step evidence order (`:15-41`): hash and inventory; run deterministic checkers "on an isolated exact copy"; fresh semantic reviews; two-direction coverage; observable matrix; oracle and fixture review; beta run exception (2 oracle, 1 nop, 1 stub); per-run model gate; rehash | `workspace/qc/receipts/*`, semantic receipts, waivers, runtime receipts | stale, crash, missing evidence; "never label an input-only pass as all-QC clean" (`:12-13`) | `qc verify/semantic-*/waive/status`, `runs *`, `release check` |
| 7 | Resume `playbooks/resume.md` | explicit task, run or transaction ID | `status`, `resume TASK_ID`; `recovery TX {resume,rollback}` or `updates recover` (`:6-15`); reload mode, scope, counters and evidence; mark stale receipts; continue at the first incomplete gate (`:17-25`) | reconstructed state and next action | no ID ("return to the 11-mode menu", `:26`, a stale count) | `status`, `resume`, `recovery`, `updates recover` |
| 8 | Settings `playbooks/settings.md` | view, or exact changes | view; propose; separate approve; apply. "Unknown keys plus `schema_version` and `revision` are rejected" (`:24-26`) | `workspace/settings/revisions/<n>.json`, `current.json` | an agent cannot self-approve (`:28-30`) | `settings view/propose/apply` (`core/cli.py:161-188`) |
| 9 | Benchmark `playbooks/benchmark.md` | user folder; metadata JSON; question | inventory; record "PL accepted/marked" as metadata only (`:15-17`); "Normalize only comparable runs" (`:18-20`); read failing assertion targets (`:21-23`); cited matrix with counterexamples (`:24-26`) | inventory and analysis records; analysis ID | no execution of scripts; small-sample causality forbidden | `references inventory`, `benchmarks analyze/submit/status` |
| 10 | Feedback `playbooks/feedback.md` | verbatim feedback; affected bundle evidence | preserve it verbatim; classify as "confirmed bundle defect / legitimate difficulty or model failure / infrastructure / supported false positive / insufficient evidence" (`:16-20`); recurrence needs numerator and denominator (`:22-25`) | root cause, minimal repair, regression fixture, generator-improvement proposal (`:27-30`) | never invent a root cause | `feedback analyze/submit/status` |
| 11 | Reference Library `playbooks/reference-library.md` | inventory or query | start from `source-catalog.md` and `catalog.json`; dedupe same-run; label claims as measurement, pinned rule, hypothesis, contradiction or question (`:16-24`) | inventory and analysis | the archive is not policy | `references inventory/analyze/submit/status` |
| 12 | QC Repair `playbooks/qc-repair.md` | exact bundle plus exactly one report (file, folder or text); optional trajectory, output, snapshot | report-first: no QC run, no code execution, no revision during intake (`:3-6`); provenance binding (`:21-34`); 3-way analysis Real / False positive / Vague (`:44-47`); narrow natural-language selection (`:71-79`); dependency and risk reanalysis (`:84-109`); apply creates a new revision and a work order (`:111-119`); post-QC: diff, test/weight AST bijection, count claims, then mechanical QC (`:121-124`) | `workspace/qc-repairs/<case>/...` case, frozen tables, selections, report | 3 unsuccessful attempts pause; `COMPLETE_WITH_FINDINGS`; "harness-score impact unmeasured" (`:136-143`) | full CLI group `qc-repair` with 16 verbs (see F) |

Machine-readable form: `modes.json`.

## D. Hardness

### D.0 Bottom line

- **The beta generator measures hardness in code in exactly one place:** the per-run model gate (test < 90, rubric < 90, combined < 30, every run, strict) in `core/scores.py:42-70`. It is fed by imported Harbor reports.
- **Its only enforced hardness-adjacent gates** are the solvability triple (2 oracle = 1.0, 1 nop = 0.0, stub with every paying test reviewed; `core/runtime_intake.py:224-250`), exactly 3 finalists, a 3-round refinement cap on idea reviews, and the Mode 12 risk choice.
- **Everything that *makes* tasks hard is prose** for the authoring agent, plus the upstream PL generator's recipe pinned in `SNAP/generator_reference/`.
- **No measured evidence** of beta-made tasks being hard exists in the repository. The archive that holds earlier experiments is not shipped (G.2). The only measured numbers are upstream: HARDFMT reference runs "Opus reward 0.154" and "0.419" (`SNAP/generator_reference/FORMAT_SPEC.md:543-546`), and target "Opus 4.8 < 0.45" (`:588`).

### D.1 Technique catalogue

Columns: **Enf.** = code / prose / both / upstream-code (enforced by the pinned upstream checkers when `qc verify` runs) / upstream-prose. **Ev.** = measured evidence.

| # | Technique | How it works | Where | Enf. | Ev. |
|---|---|---|---|---|---|
| H1 | Solvability invariant ("hard, not impossible") | Every graded result is derivable from `instruction.md` + `environment/data/`. Hidden seeds may choose inputs, never supply needed values. "An undocumented rule is a defect, not difficulty" | `references/curated/design-guide.md:10-15`; `generator-use-instruction.md:70-72`; `SNAP/generator_reference/GENERATOR_TRAP_RECIPE.md:16-41`; upstream semantic gates DS-22, AL-F0e (`SNAP/Input_Bundle_QC/02_Data_Solution_QC.md:159-184`) | prose + upstream-prose (semantic review IDs are *required* by `core/qc_semantics.py:15-37`, so a reviewer must answer DS-22) | none |
| H2 | Difficulty from documented rule interaction | Prompt A: difficulty from "broad documented rule interaction, completeness obligations, boundary ownership, reconciliation, state coupling, or deterministic precision" plus "at least six interacting documented rules", "three legal edge cases", "likely reflex implementation and assumption inversion" | `prompts/idea-workshop.md:16-27`; finalist field "Six-rule interaction" (`:161`) | prose | none |
| H3 | Complexity-lever triple (upstream) | lever = (documented rule, forward transform, exact inverse); 2-3 **independent** levers, at least 1 stateful "isolation-breaker" so no record decodes alone; attach the heaviest lever to the "spine" | `GENERATOR_TRAP_RECIPE.md:45-108,63-70` | upstream-prose | upstream HARDFMT runs 0.154 / 0.419 |
| H4 | Partial-solver ceiling < 0.35 (upstream) | classify positive tests EASY (w1) or HARD (w5) and add HARD tests until `hard_total > 1.857 × easy_total`. "The lever is test COUNT, not weight magnitude". Loop back if the ceiling is ≥ 0.35 | `GENERATOR_TRAP_RECIPE.md:171-190,235-237` | upstream-prose (validator not in snapshot). **The beta does not adopt it**; it says "Preserve partial signal unless an intentional measured cliff is justified" (`design-guide.md:94-97`) | upstream calibration table `FORMAT_SPEC.md:580-588` |
| H5 | Overgenerate then refine | 6-10 mechanism sketches; reject reskins and hidden-info tricks; compare on transitions, breadth, interaction depth, gradeability, shortcuts, solvability; exactly 3 finalists; user picks | `playbooks/overgenerate-refine.md:15-23`; Prompt A asks for 8 (`idea-workshop.md:13`) | both: code enforces exactly 3 (`core/refinement.py:26-31`); the sketch count is prose | none |
| H6 | Shared 3-round refinement budget | 3 rounds per bundle total, successful or not, never reset across candidate switches or revisions; pause after round 3 | `generator-use-instruction.md:75-78`; `refinement.py:11,63-64,113` | both (code for idea reviews only; `tasks harden` does not count, `BETA-GENERATOR-HANDBOOK.md:1056`) | none |
| H7 | Hardening loop (Mode 2) | diagnosis table; weak difficulty = "free structural reward, dormant rule, answer disclosure, factorisable mainline, easy process criterion"; strengthen with "legal adversarial fixtures, rule interaction, completeness, boundary ownership, reconciliation, deterministic high precision, or program reruns"; "Do not add volume" | `playbooks/harden.md:13-31` | prose (CLI only copies the revision) | none |
| H8 | Per-run model gate | each required model run: test < 90, rubric < 90, (t+r)/2 < 30; equality fails; run count must match the policy exactly; "averages cannot hide a failing run" | `core/scores.py:7-8,42-70`; `generator-use-instruction.md:83-87` | code (constants hard-coded; `config/defaults.json:11-13` unread) | none in repo |
| H9 | Baselines: oracle / nop / stub | 2 oracle runs exactly 1.0, nop exactly 0.0 (upstream 5 oracle); the stub is "hand-built shape-only"; record every test that pays it with a rationale | `core/runtime_intake.py:224-250`; `playbooks/verify.md:33-36`; upstream stub ≈ 0 expectation and TS-28 "no source-token greps paying positive" (`SNAP/Input_Bundle_QC/Final_checklist.md:376-443`, `03_Tests_QC.md:112`) | code (counts and equality; the stub has no threshold) | none |
| H10 | Offline mutation / ablation = grader sensitivity only | "An ablation or mutant measures grader sensitivity, not the chance a model will fail" | `design-guide.md:97`; `BETA-GENERATOR-HANDBOOK.md:1213` | prose | none |
| H11 | Hidden or reseeded corpora and program reruns | tests use "hidden/reseeded corpora generated from published rules ... delivered-program reruns from a foreign working directory" | `design-guide.md:83-87`; `playbooks/create.md:39-41`; upstream templates regenerate eval sets from `EVAL_SEED` (e.g. `templates/data-pipeline/tests/test_output.py:287`, performance 1400/2400 events) | prose; upstream templates implement it | none |
| H12 | Anti-cheat negatives | task-specific negatives on the real shortcut surface; the upstream standard four: hard-coded sample answers −5, filename-dependent −5, reads `/app/data` at runtime −5, nondeterministic −3; ≥ 1 negative and `test_negative_` naming | `generator-use-instruction.md:128-131`; `design-guide.md:36-37,86-87`; `SNAP/generator_reference/CHEAT_VECTORS.md:13-103,190-202`; `tests_qc.py` W5/W6 (`:166-179`) | prose + upstream-code (W5/W6) | upstream ceiling arithmetic only (`CHEAT_VECTORS.md:25-29`) |
| H13 | Structural cheat closure | two Dockerfiles with non-overlapping COPY; the verifier in a separate image (`environment_mode="separate"`); reward-file forging blocked by a root-owned 0700 log dir and `setpriv` to nobody; no shipped `cheat/` | `CHEAT_VECTORS.md:105-131,206-215`; `design-guide.md:52-55`; `core/package_contracts.py:70` (code checks `separate`); upstream S3, S9, H1-H5 | both | none |
| H14 | Exact deterministic comparison | no `isclose`/`approx`; bit-exact floats; publish precision and rounding stages | `CHEAT_VECTORS.md:150-166`; `design-guide.md:13-14`; `generator-use-instruction.md:70-72` | prose | none |
| H15 | Contract matrix in both directions | requirement IDs → visible anchor, shapes, ties, precision, fixtures, test owner, rubric owner; every promise graded and every graded predicate promised | `generator-use-instruction.md:112-115`; `design-guide.md:65-79` | **code exists but is unreachable**: `core/contracts.py:8` (≥ 5 constraints, reachability, duplicate observables, no `state_change`, conduct needs `competent_routes_satisfy`) has no CLI caller | none |
| H16 | Rubric classification outcome / constraint / conduct | conduct is valid only if every competent route satisfies it or it demonstrably raises the odds of correctness; never penalize an unstated approach; executed numeric evidence only for distinct conduct | `design-guide.md:99-123`; `generator-use-instruction.md:65-69`; upstream RB-16/17/18 (`04_Rubric_QC.md:155-287`) | prose + upstream-prose | none |
| H17 | No double payment | same observable in tests and rubric = duplicate; dependency is not duplication; all-pairs overlap review; upstream: one agent action costs at most 5 across tests + rubric (AL-30) | `design-guide.md:89-92`; `05_Alignment_Integrity_QC.md:133-145` | prose + upstream-prose (contracts.py unreachable) | none |
| H18 | "Remove the restrictive constraints" test | mentally delete restrictive constraints and check substantial outcome work remains | `design-guide.md:120`; `playbooks/chatgpt-ideas.md:25`; upstream RB-18 | prose | none |
| H19 | Deterministic performance gates only | baseline, workload, repetitions, tolerance; prefer operation counts or relative measures; reject noisy timing | `design-guide.md:17-20`; upstream perf template `max(opt/base) <= 0.70` (`templates/performance/tests/test_output.py:374-387`) | prose; upstream template code | none |
| H20 | Independent oracle | build from the written contract; hand-computed minimal fixtures; "deliberately include a case that would reveal a shared plausible bug"; never copy verifier logic | `design-guide.md:76-79`; `generator-use-instruction.md:125-127`; upstream O1: ≥ 35 % shared substantive lines FAIL, ≥ 20 % WARN (`tests_qc.py:371-406`) | prose + upstream-code (O1) | none |
| H21 | Originality / underivability checks | candidates need non-empty `differences`, `closest_matches`, `mechanism_fingerprints`; `novelty: UNVERIFIED`; "family variant vs mechanism variant" | `core/ideas.py:104-126`; `BETA-GENERATOR-HANDBOOK.md:1195-1204`; upstream "genuinely novel ... Anything with an RFC ... is disqualified" (`CHEAT_VECTORS.md:170-186`) | code shape-only; **catalogue matching is broken** (E.1); novelty is human | none |
| H22 | Mechanism cards | `{visible_rule, trigger, wrong_interpretation, root_cause, output_ids, evidence_refs, counterexamples}`; fingerprint and evidence status re-checked for staleness | `core/mechanisms.py:18-130` | code (registry only; not consumed) | none |
| H23 | Assumption inversion, drift and trap defects | upstream TRUTH defect budget: ≥ 2 focal, ≥ 1 drift (expert instinct contradicts spec), ≥ 1 trap (invisible on the happy path) | `SNAP/generator_reference/FORMAT_SPEC.md:662-677`; templates' TRUTH (e.g. data-pipeline `TRUTH.md:45-62`); beta prompt field "reflex implementation and assumption inversion" | upstream-prose; beta prose | none |
| H24 | Trigger depth for rules | every precedence or tie chain needs a graded fixture carrying both faults; every rule needs an input that changes when the rule is broken (AL-29) | `05_Alignment_Integrity_QC.md:120-132`; beta "rule interaction ... legal adversarial fixtures" (`harden.md:29-31`) | upstream-prose | none |
| H25 | Archetype anti-monotony (upstream) | 8 archetypes, random choice within a per-category affinity list; selection RNG independent of content RNG | `SNAP/generator_reference/ARCHETYPE_SELECTION.md:22-98` | upstream-prose (generator script absent) | none |
| H26 | Observed-score difficulty bands (upstream output QC) | pooled mean: expert 0-25, hard 25-37.5, medium 37.5-50, easy 50-87.5; > 87.5 FAIL; per run, test% exactly 0 or 100 FAIL; rubric 100 rationed | `SNAP/Output_Bundle_QC/output_qc.py:1302-1325,1638-1742` | upstream-code (runs on `qc verify --kind output`) | — |
| H27 | Red-team hack trial and trial crux analysis (upstream frontier-bench) | adversarial charter that probes verifier blind spots; per-trial `difficulty_crux`, `near_miss`, `reward_hacking` | `SNAP/generator_reference/reference/frontier-bench/rubrics/hack-trial-prompt.md:3-30`; `trial-analysis.toml:1-29` | upstream-prose; **not used by beta** | none |
| H28 | Repair must not weaken difficulty | "Correct the derivation or implementation, not the expected answer or test strength"; QC repair asks for `difficulty_impact`; `likely easier/harder/unknown` forces `fix alone / harden separately / leave unresolved` | `generator-use-instruction.md:73-74`; `core/repair_selection.py:128-138` | both (label self-reported; no test-count or weight regression check, F.5) | none |
| H29 | Honest evidence discipline | never rerun until favorable or discard attempts; preserve all attempts; NOT_EVALUATED until a complete matrix exists | `playbooks/overgenerate-refine.md:26-27`; `design-guide.md:136-137`; code: exact run counts per model (`scores.py:64-66`), duplicate run IDs rejected (`runtime_intake.py:94-95`) | both (which runs get imported is still the operator's choice) | — |
| H30 | Large relevant input surfaces, pervasive precision, conjunction depth | listed only as "Reference hypotheses - not active automatically" | `design-guide.md:152-160` | prose (explicitly non-binding) | archive only (absent) |

### D.2 Cheat vectors covered

From `CHEAT_VECTORS.md:190-202` (upstream), plus beta extras:

| Vector | Mitigation | Enforced |
|---|---|---|
| hard-coded sample answers | negative −5 fires iff samples are 100 % and fresh eval is 0 % | upstream validator (absent); W5 needs ≥ 1 negative |
| filename-dependent behaviour | same bytes under two names, −5 | prose |
| reads `/app/data` at runtime | source scan, −5 | prose; upstream D1 forbids *tests* reading `/app/data` |
| nondeterminism | 4 reruns, −3 | prose |
| eval seed leak | two-image design | S9 + `environment_mode` (code) |
| answer files in data | no `sample_*.json`; DS-4/DS-27 | upstream-prose |
| loose tolerances | exact comparison | prose |
| online lookup | novel subject; prohibition sentence (QC no longer checks it, `Final_checklist.md:620-623`) | human |
| reward forging | root-owned 0700 logs, `setpriv` | upstream H1-H5 (warn/fail) |
| beta: free structural reward / stub payout | stub review of paying tests | code (list equality only) |
| beta: penalising unstated approaches (fairness) | forbidden | prose |

### D.3 Partial-credit design

- **Weights.** Legal values are `1, 3, 5, -1, -3, -5`, with an exact test/weight bijection. These rules are enforced upstream (`tests_qc.py:59,119-179`) and in Mode 12 (`core/repair_dependencies.py:37-40`).
- **Reward.** `reward = Σ passed weights / Σ positive weights`, clamped to [−1, 1] (`SNAP/generator_reference/FORMAT_SPEC.md:296-336`). Output QC recomputes `test%`, `rubric%` and `final = (t+r)/2` (`output_qc.py:874-972`).
- **Beta stance.** Preserve partial signal. Warns that "one spine read by many tests can collapse reward" and "do not manufacture low score by an impossible conjunction" (`design-guide.md:94-97`). This is the opposite emphasis to the upstream spine-and-ceiling recipe (H3/H4). The 0.24 generator must pick one, or make the choice explicit per task.

## E. Ideas pipeline

### E.1 Flow

| Stage | Who | What | Where |
|---|---|---|---|
| 1 Register | controller | `ideas start TASK_ID DOMAIN` needs an existing task record and refuses a paused task. It writes `workspace/ideas/idea-<uuid>/idea.json` with `status: awaiting_candidates`, `required_candidate_count: 3`, `allowed_families`, `automatic_model_execution: false`. It also looks for `prompts/idea-<domain>.md` or `prompts/idea.md`. Neither file exists, so `template_reference` is always null | `core/ideas.py:14-51` |
| 2 Generate | user, by hand in ChatGPT | the agent fills prompt A below; the user pastes it and brings back the reply | `playbooks/chatgpt-ideas.md:12-15` |
| 3 Critique | agent | 8 checks per candidate: family, real mechanism, visible contract and legal data, deterministic grading, "substantial task after restrictive constraints are removed", test/rubric ownership, assets and licence, hard-but-solvable interactions | `playbooks/chatgpt-ideas.md:19-28` |
| 4 Refine | agent then user | for each weakness: quote it, give the graded consequence, ask for one concrete change, state solvability bounds, name the acceptance check (prompt B) | `playbooks/chatgpt-ideas.md:30-32` |
| 5 Submit finalists | controller | the candidate envelope is validated: exactly 3 (`invalid_finalist_count`), distinct IDs, legal family, non-empty `differences`. Each candidate gets `novelty: "UNVERIFIED"` and `catalogue_matches` (its fingerprints intersected with the mechanism catalogue). Status becomes `awaiting_selection` | `core/refinement.py:17-48`, `core/ideas.py:104-126` |
| 6 Select | user | `ideas select IDEA_ID CANDIDATE_ID`; status becomes `refining`; a review schema is emitted | `core/ideas.py:63-97` |
| 7 Review / refine round | agent and controller | the review envelope is checked strictly (exact key sets). Family may not change. `accepted: true` needs every issue `resolved` and at least one evidence anchor whose file hash and `source_version` match on disk. Each submission consumes one round in `task.json.refinement_rounds`. At round 3 the status is `paused`, and a 4th submission fails with `refinement_exhausted` | `core/refinement.py:51-149` |
| 8 Hand-off | user | the chosen finalist goes to Mode 1 or 3 (`prompts/bundle-author-review.md` A) | `BETA-GENERATOR-HANDBOOK.md:271` |

Observed end to end in scratch: RUN_LOG #22-25.

**Weak points found in the code:**
- The novelty check cannot fire. Candidate `mechanism_fingerprints` are free strings such as `"ordered-reconciliation"` (`prompts/idea-workshop.md:50`). The catalogue fingerprints are SHA-256 hex digests of `{visible_rule, trigger, wrong_interpretation, root_cause}` (`core/mechanisms.py:32-40`). The set intersection at `core/refinement.py:32-41` therefore always comes out empty unless someone pastes a hex digest. Observed: `catalogue_matches: []` (RUN_LOG #22).
- An "accepted" review can be backed by a trivial evidence file. `{"schema_version":1,"source_version":"source-v1"}` marked `REVIEWER_OBSERVED` counts as VERIFIED (`core/refinement.py:226-228`). RUN_LOG #24-25 shows exactly this.
- Ideas are never scored. The controller has no numeric idea-quality metric, no ranking, and stores no rejected-idea list (the playbook asks for one in prose, `chatgpt-ideas.md:37-38`). Only the 3 finalists are persisted (`core/refinement.py:42-46`).
- The refinement budget is shared. The idea counter and the harden "rounds" in prose are the same `task.json.refinement_rounds` field. Only idea review submissions increment it in code (`core/refinement.py:112-148`). The handbook admits that `tasks harden` does not touch it (`BETA-GENERATOR-HANDBOOK.md:1056`).

### E.2 Prompt A: idea generation (verbatim, `prompts/idea-workshop.md:8-34`)

```text
You are proposing hard but fully solvable Harbor terminal-task ideas in the domain:
[DOMAIN]. The only allowed task families are correction and derivation. Use this local
reference only as background, if supplied: [REFERENCE SUMMARY OR "none"].

Generate 8 candidates. Each must be a genuinely distinguishable mechanism, not a renamed
scenario. Every graded result must be derivable from a concise instruction plus shipped
flat data; no hidden rule, secret constant, undocumented tie-break, or required network
fact. The instruction will state WHAT, not teach HOW. Difficulty should come from broad
documented rule interaction, completeness obligations, boundary ownership,
reconciliation, state coupling, or deterministic precision. Numeric performance is
allowed only when a reproducible target can be validated without noisy timing.

For each candidate return exactly these fields:
ID; title; correction_or_derivation; user-visible problem; deliverables; input artifact
types; mechanism family; state transitions; at least six interacting documented rules;
three legal edge cases; likely reflex implementation and assumption inversion; exact
grader observables; distinct rubric conduct evidence; anti-cheat surface; independent
oracle strategy; asset source/license/estimated bytes; nearest known pattern and the
behavioral difference; solvability argument; biggest risk.

A license declaration is only a lead. Do not represent it as legal proof or automated
copyright certification; identify permission evidence and notices that must be preserved.

Do not provide implementation code, test answers, generated data, hidden expectations,
or a recommendation to conceal rules. Do not choose a winner.
```

The structure is: role and domain, then family restriction, then the optional reference, then N=8 candidates with "mechanism not reskin", then the solvability invariant, then the sources of difficulty, then the performance caveat, then **19 fixed fields** per candidate, then the licence caveat, then the prohibitions (no code, no answers, no winner).

### E.3 Candidate envelope A2 (machine-consumed, `prompts/idea-workshop.md:42-75`)

`{"raw_response": str, "candidates": [ {candidate_id, title, family ∈ {correction, derivation}, mechanism_fingerprints: [str], closest_matches: [str], differences: [non-empty str, ≥1], structured_payload: {...}} × exactly 3 ]}`. These rules are enforced at `core/refinement.py:26-31` and `core/ideas.py:104-126`.

### E.4 Prompt B: targeted refinement (verbatim, `prompts/idea-workshop.md:79-92`)

```text
Revise candidate [ID] only. Preserve these strong parts: [PRESERVE]. The reviewed defect
is: [QUOTED WEAK PART]. It matters because: [GRADED CONSEQUENCE]. Make this concrete
change: [ONE REQUESTED CHANGE]. Keep every expected result derivable from the visible
contract and data. Do not hide or weaken a rule, change an expected answer merely to fit
a proposed implementation, duplicate the same observable across tests and rubric, or
add unlicensed/unknown assets.

Return the complete revised candidate in the same field order, plus:
revision_delta; expected_graded_effect; new_or_changed_contract_rules; acceptance_check;
remaining_risks. This is refinement round [N] of at most 3 total rounds for the bundle,
whether prior rounds succeeded or failed; changing candidates or revisions does not
reset that shared budget.
```

### E.5 Review envelope B2 (`prompts/idea-workshop.md:111-148`)

`{"raw_response": str, "review": {reviewer: {reviewer_id, reviewer_type ∈ {human, agent}, assurance: "ADVISORY_REVIEW"}, candidate_id, issues: [{rule, reason, requested_change, expected_impact, review_criterion, status ∈ {active, resolved}}], revision: {family, structured_payload, mechanism_fingerprints, differences}, evidence_refs: [{path, sha256, source_version, assurance}], accepted: bool}}`. The exact key sets are enforced (`core/refinement.py:65-67,83-92,171-173,189-190,210-211`).

### E.6 Prompt C: finalist payload shown to the user (verbatim, `prompts/idea-workshop.md:157-175`)

```text
Finalist 1 - <title> (<correction|derivation>)
Core work:
Distinct mechanism:
Six-rule interaction:
Deliverables and data:
Test-channel plan:
Rubric-channel plan:
Solvability proof plan:
Asset/license/size:
Known risks and unknowns:
Difference from finalists 2 and 3:

Finalist 2 - ...
Finalist 3 - ...

USER CHOICE REQUIRED: Reply with 1, 2, or 3. No bundle will be built before selection.
Refinement rounds already consumed for this bundle: <0-3>.
```

"Do not mark one preferred" (`:155`). Being a finalist means "idea-review ready, not QC clean, empirically hard, or release-ready" (`:177-179`).

### E.7 Related prompts

- `prompts/bundle-author-review.md` A: hand-off from an accepted idea to authoring (`:8-31`). B: hardening payload (`:35-55`). C: fresh independent review payload, "Do not read or trust the author conclusion before examining the bundle" (`:59-80`).
- Handbook prompt library (`BETA-GENERATOR-HANDBOOK.md:798-836`): ten reusable natural-language prompts (mode picker, Create, Harden, QC Repair, Upstream, Feedback, Benchmark, Independent review, Model fallback).
- Model lanes: "ChatGPT High reasoning for idea development and Claude Code ... for local authoring" (`BETA-GENERATOR-HANDBOOK.md:706`). ChatGPT is used only through manual copy/paste; there is no API key (`:687,714`).

## F. QC handling

### F.1 Policy layers

| Layer | File | Read by code? |
|---|---|---|
| Raw upstream checkers and guides | `SNAP/Input_Bundle_QC/{structure,instruction,tests,rubric}_qc.py` and `01..05_*.md`, `Final_checklist.md`; `SNAP/Output_Bundle_QC/output_qc.py`, `LLM_Review.md` | yes: run by `core/qc_runner.py:18,36`; checklist IDs parsed by `core/qc_semantics.py:15-37` |
| Pinned identity | `config/source_components.json` (3 component digests, commit `c6cc84f9...`, `source_commit_verified: true`) | yes, `core/qc_snapshot.py:29-47` |
| Local overlay | `qc/policy/beta.json` (caps 100/100, BETA-CAP-100 and BETA-ORACLE-2 waivers, personal_step10 2/1/1, required_groups, preserve_original_warnings, `missing_required_evidence_status: NOT_EVALUATED`) | **no**. Only `tests/test_archives.py:121-137` loads it. The behaviours are hard-coded instead: 100 cap at `core/findings.py:52-62`, 2/5 oracle runs at `core/runtime_intake.py:231` |
| Settings | `config/defaults.json` | mostly no (see H and `limits.json`) |

### F.2 Running pinned QC (`qc verify`, `core/qc_runner.py`)

- **Snapshot gate.** The snapshot digest is recomputed before every run and compared with `config/source_components.json`. A mismatch produces a **BLOCKED receipt**, not a crash (`core/qc_runner.py:34-35,79-90`).
- **Commands.** Each checker runs as `[sys.executable, -B, <script>, <bundle>]`, with `cwd` set to the script's directory, `PYTHONDONTWRITEBYTECODE=1`, a **120 s timeout per script** (`:29,95-105`), and `--json --sheet` for output QC (`:95-96`). The bundle is used in place, not copied (observed argv, RUN_LOG #18). This differs from `verify.md:19-20`, which says "on an isolated exact copy". Instead, a tree-hash before and after the run catches mutation (`:37,47-51`).
- **Execution status.** `COMPLETE`, `MALFORMED`, `EMPTY`, `TIMEOUT` or `ERROR`. The status is forced to ERROR when the exit code is not 0 or 1, when exit 0 comes with a FAIL line, when exit 1 has no FAIL line, when stderr is non-empty, or when the checker file changed during the run (`:111-117`).
- **Parsing.** Lines match `^(pass|PASS|FAIL|WARN|MINOR|SKIP) \[ID] msg`, and the first `N tests|criteria` becomes `count` (`core/findings.py:12-13,30-49`). Output QC must emit a JSON list of exactly one dict; `INFO` maps to blocking `MINOR` (`core/qc_runner.py:142-152`).
- **Receipt.** Records argv, cwd, checker hash, stdout/stderr and their hashes, timestamps, subject hash before and after, snapshot hash and dependencies. `receipt_id` = sha256 of the canonical JSON (`core/qc_receipts.py:23-49`).
- **Staleness.** A receipt is "current" only if all four hold: the subject tree hash matches, the receipt id recomputes, every dependency (package files, snapshot tree, parent receipt) matches, and the log hashes match (`core/qc_receipts.py:97-145`). A stale mechanical receipt simply drops out, and `qc status` then says NOT_RUN. Semantic receipts report STALE (`core/qc_semantics.py:221-224`). Re-running mechanical QC invalidates the semantic receipts and waivers that depend on it.

### F.3 Semantics and waivers

- **Verdict reduction** (`core/findings.py:65-82`). The blocking set is FAIL, WARN, MINOR, NOT_RUN, BLOCKED, STALE, INCONCLUSIVE. A blocking finding becomes an *exception* when:
  - it is the local cap case: `WARN` from `tests_qc.py` or `rubric_qc.py` with **rule `N1`** and count <= 100; or
  - a waiver matches it on scope, checker and rule, and its status is WARN or MINOR.

  The verdict is `PASS`, `PASS WITH EXCEPTIONS` or `FAIL`. FAIL, BLOCKED, NOT_RUN, STALE and INCONCLUSIVE can never be waived.
- **Gap.** The upstream test-count warning is rule **A3** (`SNAP/Input_Bundle_QC/tests_qc.py:106-109`), not N1. N1 is the rubric count (`rubric_qc.py:221-225`). So a bundle with 36-100 tests gets an un-excepted WARN, and `qc verify` fails until an operator runs `qc waive ... A3`. The documented "100 tests" cap is therefore not automatic.
- **Waivers.** `qc waive` takes 7 mandatory fields, must target a current receipt, the scope must equal the receipt kind, and it must name exactly one WARN or MINOR finding. It is stored as its own receipt with provenance `OPERATOR_APPROVED` and applied at read time (`core/qc_semantics.py:189-213`, `core/verdicts.py:23-24`). The raw findings are never rewritten.
- **Semantic review schema.**
  - Required IDs are every `- [ ] XX-n` checklist line from the five pinned guide files, plus `test:<name>` for each weight key and `criterion:<number>` for each rubric item. Output QC uses `L1..L5` (`core/qc_semantics.py:15-37,71,20`).
  - The schema refuses to build unless the set of `test_*` functions equals the weight keys (`:54-60`).
  - A submission must echo the exact reviewer context and cover exactly the required IDs. Each check needs evidence and anchors `{path, sha256}` that match the real files (`:128-186`).
  - `SKIP` counts as passing (`:153`).
- **Readiness.** `input_qc` and `output_qc` each need mechanical **and** semantic PASS or PASS WITH EXCEPTIONS (`core/verdicts.py:31-78`). `release_ready` = all four gates pass.

### F.4 Mode 12 QC Repair: deciding a finding is real

- **The judgement is external.** An agent or human submits the analysis. The controller validates its *structure* only:
  - `reported_issue` must be an exact substring of the frozen report (`core/repair_analysis.py:119-120`);
  - classification is exactly `Real`, `False positive` or `Vague` (`core/repair_models.py:22-25`);
  - `Vague` requires a `question` (`:125-126`);
  - `False positive` must have empty `dependent_files`, so it can never authorize an edit (`:128-129`);
  - every finding needs source anchors whose sha256 equals the current bytes (`:130-142`) and a rule triple `{checker, rule_id, source_version}`;
  - every report paragraph `R<n>` must appear exactly once across mapped, context and unparsed refs (`:106-111,156-160`).
- **Stable IDs.** The fingerprint is `sha256(checker\0rule_id\0reported_issue)`. A re-analysis keeps old `Q` IDs (`:57-76,152`).
- **Not checked by code:** that `rule_id` exists in the snapshot, that a "Real" finding is actually real, and the `verification` entries.
- **Provenance.** A report without `snapshot_hash`, `subject_hash` and `source_version` markers, or with contradictory ones, goes to `NEEDS_INPUT`. It is resolved by `bind-snapshot` (configured snapshot, or an external one with an attestation `{snapshot_id, sha256, qc_kind, statement}`, copied read-only) and `confirm-subject` (`core/repair_intake.py:18-20,42-88,115-163`). Intake never runs QC (`initial_qc_executed: false`, `:109`).

### F.5 Repair selection and hardness preservation

- **No ranking.** The user picks Q IDs. The NL grammar accepts only `fix`, `fix all`, `fix all except Qn`, `do not fix`/`exclude Qn`, `fix Qn` and `for Qn use <text>`; anything else gives `ambiguous_selection` (`core/repair_selection_support.py:15-43`).
- **Authorization** (`core/repair_selection.py:86-196`):
  - frozen context and scope hashes must match;
  - no unresolved questions and no selected Vague finding;
  - dependency closure may not add findings (`expanded_selection_required`);
  - a finding with impact `likely easier`, `likely harder` or `unknown` needs an explicit risk choice (`fix alone`, `harden separately` or `leave unresolved`, `:128-138`);
  - `allowed_paths` must be a subset of the analyzed `dependent_files`; `must_update` a subset of allowed;
  - `core/ config/ qc/ workspace/` are blocked (`repair_selection_support.py:70-73`);
  - hardening paths must not overlap excluded findings (`:159-161`);
  - computed dependents must be authorized: editing tests implies `test_weights.json`, and editing rubric, toml or instruction implies README and TRUTH (`core/repair_dependencies.py:13-28`).
- **Apply.** Creates a new revision plus a work order. A selection with only false positives completes without a revision (`core/qc_repair.py:42-113`). An optional patch manifest is hash-bound and has no shell field (`core/repair_revision.py:26-44`).
- **Verify** (`core/repair_verification.py:20-103`):
  - the real file diff must be non-empty, inside the allowed set, and cover the required set;
  - the test/weight AST bijection must hold;
  - README/TRUTH "N tests / N rubric criteria" claims must equal real counts (`repair_dependencies.py:31-51`);
  - mechanical QC runs **on the case-pinned snapshot**;
  - output QC requires fresh evidence whose `subject_hash` equals the revision.
- **Reconcile** (`:157-187`) uses raw statuses. Waivers and the N1 cap exception are *not* applied there, so a waived WARN still counts as unresolved. New blocking rules become new `Vague` findings that need a fresh selection. The attempt counter per `Real` finding rises on failure and resets on success. At 3 the case is `PAUSED`, and `apply` refuses a 4th (`core/qc_repair.py:71-76`).
- **What the code guards vs what is prose only:**

| Guard | Code? |
|---|---|
| edit only analyzed paths; actual diff in scope | yes |
| tests <-> weights bijection; documented counts | yes |
| same producer snapshot as the original report | yes |
| difficulty impact acknowledged by the user | partly: a self-reported label forces a risk choice |
| no test removal / no lowering of test count | **no** |
| no weight value change | **no** (keys only, `repair_dependencies.py:100-107`) |
| no instruction leak / answer disclosure | **no** in the repair path |
| no new `state_change` criterion | **no** (`contracts.py` is never called; only upstream `rubric_qc.py` E4 accepts it) |
| "preserve difficulty" | prose: `generator-use-instruction.md:73-74`, `harden.md:25-28`, `BETA-GENERATOR-HANDBOOK.md:1217-1221` |

- **Counter loophole.** The fingerprint includes the quoted text, so a reworded re-analysis restarts the counter. A second, independent counter (`qc repair-attempt`, `core/findings.py:96-136`) is not wired into Mode 12.

### F.6 Bugs and defects found

1. **Digest mismatch on LF checkouts (verified, RUN_LOG #5-8).** All three pinned digests in `config/source_components.json` match only when the snapshot's text files have CRLF endings. On this macOS/LF checkout, `qc verify` returns a BLOCKED receipt (`core/qc_runner.py:34-35`) and the `qc-repair` routes raise `snapshot_integrity`. That one cause accounts for 34 of the 38 failing tests (38 fail on LF, 4 fail with CRLF). There is no `.gitattributes`.
2. `core/qc_runner.py:101` calls `_execution_failure` with 4 positional arguments; the function takes 3 (`:156-158`). This is reachable only if a configured script is missing while the digest still matches. Found by reading; not executed.
3. Output-kind repair: `submit_verification_review` submits the semantic review against the bundle, but the receipt was registered against the evidence directory (`core/repair_verification.py:67-69,121`). It probably fails with `missing_mechanical_receipt`. UNVERIFIED: no test covers that step.
4. `open_repair_case` validates both input and output snapshots even for input-only repair (`core/repair_intake.py:39-40`).

## G. Scores and feedback

### G.1 Ingesting harness results (`runs`, `core/runtime_intake.py`, `core/scores.py`)

- **Harbor 0.23 report mapping** (`core/runtime_intake.py:34-38,160-168`, printed by `runs schema`, RUN_LOG #26). `test_score <- report.test_weights_percentage`, `rubric_score <- report.rubric_weights_percentage`, `combined_score <- report.final_reward`, `model <- report.model`. `harbor_report_hash` = sha256 of `report.json`. The rubric graded in the report must match the bundle's `tests/rubric.json` in hash, or row by row on 7 fields (`:172-195`).
- **Import rules** (`:63-115`):
  - `schema_version: 1`;
  - `runs[]` entries need `run_id, role ∈ {model, oracle, nop, stub, utility}, model, subject_hash, test/rubric/combined score, infrastructure_status, reward`;
  - every `subject_hash` must equal the current bundle tree hash;
  - duplicate run IDs are rejected;
  - evidence must live under the workspace (`:117-121`);
  - model runs need a registered policy receipt.
- **Policy.** `runs policy-register` accepts a matrix only if it **equals** `settings.required_run_matrix` (`:51-53`). The default is `null` (`config/defaults.json:10`), so until a settings proposal sets it, no policy can register and difficulty stays `NOT_EVALUATED`.
- **Score parsing.** Decimals in 0..100. `combined` must equal `(test + rubric)/2` exactly (`core/scores.py:11-39`).
- **Model gate.** `infrastructure_status == COMPLETE`, test < 90, rubric < 90 and combined < 30, all strict (`core/scores.py:42-49`). The constants are hard-coded at `:7-8`; `config/defaults.json:11-13` is never read.
- **Matrix evaluation.** For each policy row, the number of runs must equal `required_runs` exactly and **every** run must pass the gate. Unregistered models fail (`core/scores.py:52-70`). This is how "averages cannot hide a failing run" (`generator-use-instruction.md:86-87`) is enforced in code.
- **Solvability** (`core/runtime_intake.py:224-250`).
  - Requires exactly 2 oracle runs (5 if the report declares `profile: upstream`), 1 nop and 1 stub.
  - Oracle reward must be exactly `1.0` and nop exactly `0.0`, both with `COMPLETE` infrastructure.
  - The stub must list `paying_tests`, which must equal its `reviewed_tests`, plus a non-blank `judgement_rationale`. This is the code form of "inspect every test that pays it".
  - The stub has no score threshold (prose: `generator-use-instruction.md:81`).
  - The report itself declares the profile (`:79-81`), so a report could select the 2-run rule.
- **Verdict.** `runtime_status` gives NOT_RUN, STALE, NOT_EVALUATED, PASS or FAIL (`:198-221`). It feeds `solvability` and `difficulty_target` in `core/verdicts.py:31-67`.

### G.2 Diagnosis and feedback loops

| Loop | Mechanism | Code vs prose |
|---|---|---|
| Overgenerate/refine (Mode 3) | ingest all attempts; "Diagnose failed observables, not just aggregate score"; refine minimally; rounds capped at 3 | prose: `playbooks/overgenerate-refine.md:24-40`. Code: only `runs import` and the shared counter |
| Harden (Mode 2) | diagnosis table splitting validity defect / weak difficulty / unsupported complaint; before/after observable table | prose: `playbooks/harden.md:13-21,54-55` |
| Feedback (Mode 10) | verbatim intake, 5-way classification, numerator/denominator recurrence | `feedback analyze` stores `entries[{feedback_id, text, task_ids}]` with `status: pending_review` and `verdict: NOT_EVALUATED` (`core/analysis.py:89-121`). The review is external: `submit` requires `{reviewer, findings, missing_data_questions}`, and each finding is marked VERIFIED, UNVERIFIED or STALE against hashed evidence (`core/analysis.py:125-213`). Classification logic is prose only (`playbooks/feedback.md:12-25`) |
| Benchmark (Mode 9) | compare mechanisms with low scores, stratified by model, budget, judge and date; dedupe | `references inventory` hashes a folder (`core/analysis.py:22-70`). `benchmarks analyze` only asks for the missing `mechanism, assets, contracts, grader_version, model_version` (`:13-19,79-87`). There is no statistics code; everything else is prose (`playbooks/benchmark.md:12-26`) |
| Mechanism cards | `{visible_rule, trigger, wrong_interpretation, root_cause, output_ids, evidence_refs, counterexamples}` with evidence status VERIFIED, STALE or UNVERIFIED (RUNNER_OBSERVED needs a registered QC receipt) | code: `core/mechanisms.py:18-192`. Nothing consumes cards except the broken novelty intersection (E.1) |
| QC Repair report | always `harness_score_impact: "unmeasured"`; old trajectories marked historical | code: `core/qc_repair.py:225-228` |

**Measured evidence that any loop lowered scores:** none in this repository. The archive that might hold it (`references/archive/`, 3,202 files, 47.6 MB according to `references/catalog.json` `summary`) is git-ignored and absent. The design guide labels its lessons "Reference hypotheses - not active automatically" (`references/curated/design-guide.md:152-160`).

## H. Data and file formats

### H.1 What formats a generated task may contain

- **Beta controller.** It has no data-format code. The release check requires `environment/data/` to be non-empty and flat (regular files only). There is **no extension allow-list, size limit or count limit** (`core/package_contracts.py:39-43`). The root, `environment/`, `solution/` and `tests/` must contain exactly the fixed file sets (`:13-19,33-38`).
- **Upstream structure QC, which runs on `qc verify`:**
  - no extension rule;
  - `environment/data` flat and non-empty (S4, `SNAP/Input_Bundle_QC/structure_qc.py:173-182`);
  - **every file ≤ 100 MiB** (X4, `:557,585-586`);
  - files that look like text (first 8 KB has no NUL and is UTF-8) are swept for em or en dashes (X1), template markers or `TODO`/`FIXME`/`PLACEHOLDER` (X2), and the word `canary` (X3) (`:74-88,549-600`).

  Real-world text data containing those strings fails unless it is binary or the failure is waived (only WARN and MINOR can be waived, so FAIL-level X rules cannot be).
- **Upstream generator policy (prose):**
  - nested trees ship as one `.zip`, which counts as one input (`SNAP/generator_reference/FORMAT_SPEC.md:57-58`);
  - minimum inputs and artifacts are 6 each, or 10 for data-pipeline, domain-calculation and performance (`:53-60`);
  - no answer files such as `sample_*.json` (`CHEAT_VECTORS.md:135-146`);
  - a single digest-pinned `python:3.12-slim` image and **stdlib-only** archetypes (`FORMAT_SPEC.md:193-213,236-239`).
- **Formats actually present in the 8 upstream templates** (count of files under `templates/*/environment/data`): `json` 29, `csv` 20, `md` 14, `py` 11 (source trees, zipped at build), `jsonl` 4, `toml` 2, `txt` 1, `yaml` 1. There is no binary, Parquet, Excel, SQLite, PDF, image, audio, log-archive or compressed data format other than `.zip` source trees.
- **Asset intake (beta).** Any file type is accepted. `.zip` and `.tar` files are validated: no absolute or `..` members, no links, expanded size ≤ 1,000,000,000 bytes (`core/assets.py:19,146-174`). They are extracted into `payload/`.
  - Licences must come from 11 SPDX IDs (`Apache-2.0, BSD-2-Clause, BSD-3-Clause, CC-BY-4.0, CC0-1.0, GPL-2.0-only, GPL-3.0-only, ISC, MIT, MPL-2.0, Unlicense`) or match `LicenseRef-[A-Za-z0-9.-]+` (`core/licenses.py:11-26`).
  - A licence-evidence file is mandatory. Assurance is `declaration_only` unless `--permission-verified` is passed (`:41-52`).
  - Imported assets land in `workspace/tasks/<id>/revisions/<n>/assets/<asset_id>/`, **not** in the bundle's `environment/data/` (`core/assets.py:54`). The agent must copy them in by hand. Nothing records which asset bytes ended up in the bundle.
- **Downloads.**
  - HTTP(S) only; no URL credentials; private, loopback and link-local addresses rejected, including on redirects (`core/asset_transfers.py:35-59`);
  - a HEAD request with 15 s timeout first; then a known `Content-Length` or an explicit `--approved-max-bytes`;
  - the budget is reserved before streaming; 30 s timeout, 3 retries on 5xx; the stream is cut if it exceeds the reservation;
  - failed bytes are kept in `workspace/quarantine/` (`:62-183`).

### H.2 How data volume is decided

- **Nowhere in code.** The beta generator generates no data at all. The agent writes every file.
- **The prose pushes toward minimal data:**
  - "Create flat, necessary `environment/data/` inputs. Every file must support a graded case, cross-check, or disambiguation ... No answers, secret required constants, grader files, or pure decoys" (`generator-use-instruction.md:119-121`);
  - "Keep it only if needed for a graded case" (`playbooks/create.md:28-29`);
  - "Do not add volume or duplicate checks as decoration" (`playbooks/harden.md:31`);
  - "A PDF exists or the folder has many files" is listed as *insufficient* evidence that an asset matters (`BETA-GENERATOR-HANDBOOK.md:1211`).
- **The only pro-volume statement is a non-binding hypothesis:** "large relevant input surfaces ... can reduce capable-model scores" (`references/curated/design-guide.md:154-156`). Upstream: "Ship a broad set of relevant reference files" but no decoys (`FORMAT_SPEC.md:71-79`). DS-6 asks only that "sizes are reasonable" (`02_Data_Solution_QC.md:73-74`).
- **Upstream templates are tiny.** The visible `environment/data` totals are 3,426 to 7,596 bytes per archetype (repo-patch 3,426; cli-config 4,334; service-interaction 5,235; build-repair 5,853; data-pipeline 5,947; domain-calculation 6,521; performance 6,999; format-recovery 7,596). Measured in scratch with `cat | wc -c`. The data-pipeline CSVs total 56 lines.
- **Volume lives in the hidden verifier corpora,** regenerated from `EVAL_SEED`: 10 rows (repo-patch), 90 (domain-calculation), 1,400 or 2,400 events (performance), 24 + 10 captures (format-recovery). Source: the g3 notes on `templates/*/tests/test_output.py`. Spot-checked only for performance and data-pipeline; the rest is UNVERIFIED beyond those notes.

### H.3 Every size or count limit

See `limits.json` for the full list with sources. The ones that bound data:

| Limit | Value | Source | Enforced |
|---|---|---|---|
| cumulative task download/import budget | 1,000,000,000 B | `config/defaults.json:20`, read at `core/assets.py:94` | code (assets only, not bundle files) |
| archive expansion | 1,000,000,000 B | `core/assets.py:19` | code |
| per file in bundle | 100 MiB | `SNAP/Input_Bundle_QC/structure_qc.py:557` | upstream-code |
| `environment/data` | non-empty, flat | `core/package_contracts.py:39-43`; S4 | code + upstream-code |
| min inputs / artifacts | 6 (10 for 3 archetypes) | `FORMAT_SPEC.md:53-60` | upstream-prose (validator absent) |
| download timeouts | HEAD 15 s, GET 30 s, 3 retries | `core/asset_transfers.py:21,77,164` | code |
| checker timeout | 120 s per script | `core/qc_runner.py:29` | code |

### H.4 Where data volume or format variety is limited

1. **No data generator.** The beta has no code that produces, scales or validates data files. The two known weaknesses (data too small, too few formats) are not addressed anywhere in code.
2. **The policy rewards minimalism.** "Necessary only" and "no decoys" are mandatory. "Large input surfaces" is only a hypothesis (H.2).
3. **The references model small data.** The upstream templates the agent studies ship 3-8 KB of data in 5-8 text formats.
4. **Stdlib-only and a single `python:3.12-slim` image** (upstream generator policy) make Parquet, XLSX, HDF5 and similar impractical for both oracle and verifier. QC itself would accept third-party libraries declared in `tests/Dockerfile` (K4, `tests_qc.py:335-350`).
5. **Flat `environment/data`** forces nested inputs into a `.zip`.
6. **Text sweeps** (dash, `TODO`, `canary`) make realistic logs, documents and source dumps fail upstream QC.
7. **Assets are disconnected from bundles.** Imported assets sit outside the bundle, with no provenance link to the files actually shipped.

## I. Upstream and update handling

There are three distinct mechanisms. The handbook stresses that they are separate (`BETA-GENERATOR-HANDBOOK.md:760`).

### I.1 Pinning (build time): `tools/archive_sources.py`

- It hard-codes `CHECKPOINT = c6cc84f98f9e...` (`:31`). It copies `upstream-review/{Input_Bundle_QC, Output_Bundle_QC}` and `upstream-review/Input Bundle Generator New/{templates, reference, *.md}` from the **parent directory** into `qc/snapshots/upstream-<12>/` (`:223-237`).
- It writes `manifest.json` and `DEPENDENCIES.json`, then regenerates `config/source_components.json` with per-component `tree_digest`. `source_commit_verified` is set to `git rev-parse HEAD == CHECKPOINT` of the `upstream-review` checkout (`:281-283`).
- It also builds `references/archive/` and `references/catalog.json` from sibling folders (`hard_task_analysis`, `KNOWLEDGE`, `temp_upgrade`, `Tasks_INPUT`, `jobs`, `ouput`, `input_generator_alpha/*`, `:250-257`) and records protected-tree digests before and after.
- To refresh the pin you edit the constant and rerun the tool by hand. No CLI command does this.
- The upstream PL generator scripts (`generate_bundle.py`, `validate_bundle.py`) were **not** copied: `_copy_snapshot` takes only `templates/`, `reference/` and `*.md`. This is confirmed by the file list (only docs and templates under `generator_reference/`).
- Defect: the digests were computed on CRLF bytes (F.6 #1).

### I.2 Detecting change: `sources import` / `sources check`

- **`sources import FOLDER`** (`core/upstream.py:24-58`). It inventories every file except `.git`, `__pycache__` and similar, rejects credential-like names and symlink escapes, and computes `snapshot_id = sha256(name ‖ filehash ...)`. It copies the folder to `workspace/sources/snapshots/<id>/`, makes it read-only, and writes a manifest with `policy_state: NOT_ACTIVE`. It never executes scripts.
- **`sources check [--upstream URL] [--baseline ID]`** (`core/source_diff.py:22-82`). It allows only `DEFAULT_UPSTREAM_URL = https://github.com/laude-institute/harbor.git` (`:19,36-37`); local paths need the hidden `--allow-local`. It runs `git init --bare` and `git fetch --depth=1 <url> HEAD` (60 s timeout each), then `git archive` and extract into `workspace/upstream/<head>/repository`. It diffs the file hashes against the baseline and writes `report.json` (`added/deleted/modified` with before and after hashes, plus `report_hash`).
- **Baseline precedence:** `--baseline` candidate, then the active `workspace/settings/source-baseline.json`, then the union of the 3 components in `config/source_components.json` with keys prefixed `input_bundle_qc/...` etc. (`:85-118`).
- **Defect: wrong repository.** The default URL is the public Harbor framework repo, not the PL repo that holds `Input_Bundle_QC/`, `Output_Bundle_QC/` and `Input Bundle Generator New/` (that one is the `upstream-review` checkout, see I.1). Against the default baseline the keys can never line up (`input_bundle_qc/structure_qc.py` vs Harbor repo paths), so every file would be reported as added or deleted. This was **not executed**: it would need network. It is inferred from `:57-68` plus `:112-116`, so it is UNVERIFIED at runtime.
- **The diff is bytes only.** No rule-ID, severity, threshold, schema or template diff exists in code. The playbook requires them as agent work ("Report added/removed/changed files, rule IDs and severities, schema/template changes ... Byte facts and semantic interpretations must be separate", `playbooks/upstream.md:17-20`), and "Unknown or changed rules invalidate old dispositions" (`:26-28`) is also prose.

### I.3 Activating and migrating

- **`sources baseline propose` -> `proposals approve` -> `sources baseline apply`** (`core/upstream.py:61-89`). This writes `workspace/settings/source-baseline.json` with `policy_state: ACTIVE`. **Its only reader is `source_diff._baseline`** (`core/source_diff.py:90`). The QC runner keeps using `config/source_components.json` (`core/qc_snapshot.py:30`). So activating a new baseline changes only what later comparisons diff against. It does not change which QC runs.
- **Changing the active checker** needs the `updates` channel (`core/file_updates.py`): propose `TARGET=SOURCE` bytes with `--validation compile|unit-tests`, approve, then apply (base-hash check, byte backup, journal, `updates recover`, `updates rollback` + `rollback-apply`).
  - Allowed targets: `core/ config/ playbooks/ prompts/ tests/` and `generator-use-instruction.md` only. Any path part `qc`, `references` or `workspace` is denied (`core/file_updates.py:24-25,175-193`).
  - Consequence: **new snapshot files under `qc/snapshots/` cannot be installed through any beta command**. Only `config/source_components.json` can be repointed, at a path that must already exist. In practice, an upstream QC upgrade means hand-copying files plus an `updates` proposal for the config.
  - Candidate validation copies the repo while ignoring `qc` (`:225`), so tests that need the snapshot would not run in the candidate (UNVERIFIED).
- **Migrating existing tasks** (Workflow D, `BETA-GENERATOR-HANDBOOK.md:1072-1079`): one QC Repair case per affected task, using "its actual latest approved report producer". Repairs are pinned per case to the snapshot that produced the report (`core/repair_verification.py:64-69`), so old tasks are re-verified against their original producer, not the new one. A cross-version migration therefore needs a fresh report from the new checker.
- **Settings and profile pinning.** Each task stores `profile_hash` (sha256 of `workspace/settings/current.json`) at creation. "later default revisions affect only later tasks" (`core/API.md:84-86`). No code re-evaluates old tasks when settings change.

### I.4 For the 0.24 generator (frequent PL and QC churn)

What to keep:
- content-addressed snapshots with mandatory digest checks before each run (with line-ending normalization);
- per-case pinning of the producer;
- BLOCKED-not-crash behaviour;
- an approval + base-hash + backup + journal path for config changes.

What to fix:
- point `sources check` at the PL repo;
- diff at component and rule level (parse rule IDs and thresholds out of `*_qc.py`);
- give snapshot installation a CLI path;
- make baseline activation actually switch the checker;
- replace the hard-coded `CHECKPOINT`.

## J. Portability to Harbor 0.24

I did not read the Harbor 0.24 task format; it is not in this repository. Classification therefore uses one rule:
- **OBSOLETE**: the idea *is* the 0.23 file layout or schema.
- **ADAPT**: the idea is sound but bound to a 0.23 artifact, such as `task.toml` keys, the `tests/` layout, the `report.json` field names, the weight file or the verifier mode.
- **PORTABLE**: the idea does not depend on the task format.

Which 0.23 features changed in 0.24 is UNVERIFIED.

Totals: PORTABLE 64, ADAPT 10, OBSOLETE 2 (of 76 ideas in `ideas.json`).

| ID | Idea | Class | Reason |
|---|---|---|---|
| B-001 | Solvability invariant | PORTABLE | Format-independent principle. |
| B-002 | Difficulty from documented rule interaction | PORTABLE | Prompt text reusable as-is. |
| B-003 | Complexity-lever triple with independence and isolation-breaker | PORTABLE | Upstream recipe; generalise beyond binary formats. |
| B-004 | Spine weighting | PORTABLE | Decide stance explicitly in v2. |
| B-005 | Partial-solver ceiling < 0.35 | PORTABLE | Arithmetic holds for any weighted-fraction reward; recheck if 0.24 reward formula differs. |
| B-006 | Overgenerate then refine to three finalists | PORTABLE | format-independent |
| B-007 | Shared three-round refinement budget | PORTABLE | Count harden rounds in code in v2. |
| B-008 | Hardening diagnosis taxonomy | PORTABLE | format-independent |
| B-009 | Strict per-run model gate | ADAPT | Score fields come from the 0.23 report.json; thresholds hard-coded rather than read from defaults.json. |
| B-010 | Oracle / nop / stub baseline | ADAPT | Run roles and reward fields are harness-specific. |
| B-011 | Hidden reseeded corpora and delivered-program reruns | PORTABLE | Also the natural place to add data volume. |
| B-012 | Anti-cheat negative test suite | ADAPT | Weight scale and naming tied to 0.23 test_weights.json. |
| B-013 | Structural cheat closure | ADAPT | Mechanism depends on Harbor verifier model. |
| B-014 | Exact deterministic comparison | PORTABLE | format-independent |
| B-015 | Contract matrix validated in both directions | PORTABLE | Wire the validator into a CLI gate in v2. |
| B-016 | Rubric outcome / constraint / conduct classification | ADAPT | Depends on whether 0.24 keeps an LLM-judged rubric channel. |
| B-017 | No double payment and penalty-stacking cap | PORTABLE | format-independent |
| B-018 | Remove-the-restrictive-constraints test | PORTABLE | format-independent |
| B-019 | Deterministic performance gates | PORTABLE | format-independent |
| B-020 | Independent oracle with shared-bug fixture | PORTABLE | format-independent |
| B-021 | Defect budget: focal, drift, trap | PORTABLE | format-independent |
| B-022 | Trigger depth for every rule | PORTABLE | format-independent |
| B-023 | Archetype anti-monotony selection | PORTABLE | Upstream generator code not in snapshot. |
| B-024 | Observed-score difficulty bands | ADAPT | Runs as upstream output QC; trajectory layout is harness-specific. |
| B-025 | Red-team hack trial and trial crux analysis | PORTABLE | Unused gap; strong candidate for v2. |
| B-026 | Mechanism cards | PORTABLE | Not consumed; fingerprint incompatible with idea fingerprints (see B-027). |
| B-027 | Novelty: mechanism variant vs family variant | PORTABLE | Fix fingerprint scheme in v2. |
| B-028 | Offline mutation measures grader sensitivity only | PORTABLE | format-independent |
| B-029 | Repair difficulty-risk choice | PORTABLE | Add test-count and weight regression checks. |
| B-030 | Manual ChatGPT copy/paste loop | PORTABLE | format-independent |
| B-031 | 19-field candidate schema | PORTABLE | format-independent |
| B-032 | Targeted refinement prompt | PORTABLE | format-independent |
| B-033 | Finalist payload with explicit differences | PORTABLE | format-independent |
| B-034 | Eight-axis idea critique | PORTABLE | format-independent |
| B-035 | Strict review envelope | PORTABLE | Strengthen evidence semantics. |
| B-036 | Record rejected ideas and nearest matches | PORTABLE | Implement as a store in v2. |
| B-037 | Pinned content-addressed QC snapshot | PORTABLE | Normalise line endings or add .gitattributes. |
| B-038 | Checker execution hygiene | PORTABLE | format-independent |
| B-039 | Hash-bound receipts with staleness chain | PORTABLE | format-independent |
| B-040 | Scoped waivers and PASS WITH EXCEPTIONS | PORTABLE | format-independent |
| B-041 | Semantic review schema | PORTABLE | IDs depend on QC guide text. |
| B-042 | Report-first QC repair triage | PORTABLE | format-independent |
| B-043 | Repair authorization chain | PORTABLE | format-independent |
| B-044 | Post-repair verification | PORTABLE | Bijection check must follow the 0.24 test layout. |
| B-045 | Three-strike pause per finding | PORTABLE | Counter keyed on quoted text can be reset by rewording. |
| B-046 | Local overlay policy separate from upstream | PORTABLE | Make code read the overlay. |
| B-047 | Upstream QC threshold catalogue | ADAPT | Values follow the PL QC version, which changes often. |
| B-048 | Harbor report ingestion with rubric equality | ADAPT | Field names are 0.23 report.json. |
| B-049 | Policy matrix must equal approved settings | PORTABLE | format-independent |
| B-050 | Evidence status vocabulary | PORTABLE | format-independent |
| B-051 | Feedback five-way classification | PORTABLE | format-independent |
| B-052 | Benchmark stratification | PORTABLE | format-independent |
| B-053 | Licensed asset intake with byte budget | PORTABLE | Connect assets to bundle files in v2. |
| B-054 | Safe archive extraction and SSRF guard | PORTABLE | format-independent |
| B-055 | Data necessity rule | PORTABLE | Keep, but pair with explicit volume targets to fix small data. |
| B-056 | Rich inputs where the agent chooses | PORTABLE | Lever for larger, more varied data. |
| B-057 | Nested trees as one zip input | ADAPT | Depends on whether 0.24 allows nested data. |
| B-058 | Exact bundle layout check | OBSOLETE | 0.23 file layout; reuse only the exact-set technique. |
| B-059 | task.toml 1.1 schema rules | OBSOLETE | Harbor 0.23 task format. |
| B-060 | Weight scale and test/weight bijection | ADAPT | Keep bijection idea; scale depends on 0.24 grading. |
| B-061 | Task-only README and TRUTH generated last | PORTABLE | format-independent |
| B-062 | Folder-only, copy-verified export | PORTABLE | format-independent |
| B-063 | Controller registers, agent authors | PORTABLE | format-independent |
| B-064 | Twelve-mode routing | PORTABLE | format-independent |
| B-065 | Disk-first resume with explicit IDs | PORTABLE | format-independent |
| B-066 | Versioned revisions with profile pinning | PORTABLE | format-independent |
| B-067 | Fresh-session handoff prompts | PORTABLE | format-independent |
| B-068 | Model lanes | PORTABLE | Model names will date. |
| B-069 | Proposal, separate approval, apply | PORTABLE | format-independent |
| B-070 | Transactional record store | PORTABLE | format-independent |
| B-071 | Write allow-lists | PORTABLE | format-independent |
| B-072 | Pasted text is data, not authority | PORTABLE | format-independent |
| B-073 | Immutable inactive source snapshots with byte diff | PORTABLE | Point at the PL repo and diff rule IDs/thresholds in v2. |
| B-074 | Per-case producer pinning | PORTABLE | format-independent |
| B-075 | Archive builder with protected-tree digests | PORTABLE | Replace hard-coded CHECKPOINT; normalise EOL. |
| B-076 | Separate change channels | PORTABLE | Make baseline activation switch the checker. |

**0.23-bound items to re-derive from the 0.24 spec:**
- `task.toml` schema 1.1 and its key order;
- `[verifier] environment_mode = "separate"` plus `tests/Dockerfile`;
- the `artifacts` list;
- the reward file layout `/logs/verifier/{reward.txt,reward.json,ctrf.json}`;
- `report.json` fields `test_weights_percentage`, `rubric_weights_percentage` and `final_reward` (`core/runtime_intake.py:34-38`);
- the 7-key `rubric.json`;
- `test_weights.json` and its scale;
- the exact file sets in `core/package_contracts.py:13-19`;
- the output-QC trajectory layout (`SNAP/Output_Bundle_QC/output_qc.py:99-135`).

All of these sit in a few modules (`package_contracts.py`, `runtime_intake.py`, `repair_dependencies.py` and `qc_semantics._coverage_ids`) plus the pinned snapshot. The foundation (store, proposals, receipts, repair protocol) does not depend on them.

## K. Strengths, weaknesses and gaps

### K.1 Strengths

- **Evidence discipline is enforced in code.** Hash-bound receipts with staleness chains, BLOCKED-not-crash, NOT_RUN/NOT_EVALUATED instead of silent passes, and a release gate that needs all four axes (`core/qc_receipts.py`, `core/verdicts.py`, `core/delivery.py`).
- **The Mode 12 QC Repair protocol is the most complete subsystem.** It has report-first triage, exact quotes and hash anchors, narrow selection, dependency closure, scope-checked diffs, producer pinning, a 3-strike pause and new findings forcing a new selection (F.4, F.5). It also has the best test coverage (5 `tests/test_repair_*.py` files).
- **Honest boundaries.** Advisory approvals are labelled advisory, work orders are not claimed as work, and "harness-score impact unmeasured" is stated outright.
- **Strong hardness doctrine in prose.** The design guide, the harden playbook and the idea prompt fields (D.1), plus the upstream trap recipe and cheat vectors that are pinned locally.
- **Portable, dependency-free foundation.** Stdlib only. All 94 parser paths build (RUN_LOG #9). 169 of 173 tests pass once the CRLF digest issue is removed (RUN_LOG #7-8).

### K.2 Weaknesses

1. **Policy files are not wired to code.**
   - Of the 22 `config/defaults.json` keys, 17 are never read. Only `schema_version`, `profile_id`, `max_tests` (range-checked only), `required_run_matrix` and `download_budget_bytes` are consumed (`limits.json`).
   - `qc/policy/beta.json` is never read (F.1).
   - Changing a threshold through Mode 8 changes the settings hash and nothing else.
2. **The 100-test cap is not automatic.** The cap exception covers rubric rule N1 only, not tests rule A3 (`core/findings.py:59` vs `SNAP/Input_Bundle_QC/tests_qc.py:108-109`).
3. **The pinned snapshot is unusable on LF checkouts** (F.6 #1). Every QC and repair path on macOS/Linux is blocked until it is fixed.
4. **The controller cannot see bundle contents.** `tasks create` writes a 2-file stub. `tasks verify` only hashes. No code checks test count, rubric count, constraint count, data size or formats before `qc verify` runs the upstream scripts. The beta-specific minimums (10 tests, 8 criteria, 5 constraints) are enforced only through upstream QC (10 and 8) or not at all (5 constraints: `contracts.py` is unreachable).
5. **Novelty checking is broken** (fingerprint mismatch, E.1), and accepted-review evidence can be trivial (E.1).
6. **Upstream detection points at the wrong repository** (`laude-institute/harbor.git`) and diffs bytes only. Baseline activation does not switch the QC checker. Snapshots cannot be installed through any command (I.2, I.3).
7. **There is no data generation or data-volume control** (H.4). Assets are not linked to bundle files.
8. **Repair hardness guards are path-based only.** Nothing stops a repair from deleting tests, changing weights or leaking answers (F.5).
9. **The harden and overgenerate commands are identical** except for the stored `mode` string (`core/tasks_cli.py:30-37`). Harden rounds are not counted.

### K.3 Dead code

| Item | Location | Evidence |
|---|---|---|
| `validate_contract_matrix` (full contract-matrix validator) | `core/contracts.py:8` | callers only in `tests/test_contracts.py:55,69,188` |
| `recover_revision_transaction`, `recover_bundle_publication`, `recover_release` (no CLI) | `core/revisions.py:130`, `core/bundle_transactions.py:56`, `core/delivery.py:75` | handbook admits the gap (`BETA-GENERATOR-HANDBOOK.md:429`) |
| `RepairCaseStatus` enum (statuses written as literals; `INTAKE` never set) | `core/repair_models.py:7-18` | g2 grep |
| `ProposalStatus`, `ProposalRecord`, `optional_str`, `string_tuple`, `parse_revision` | `core/models.py:31-35,65-73,95,104,136` | g1 grep |
| `permissions.validate_scope` branches `task:<id>` and `generator` | `core/permissions.py:11-17` | no caller passes them |
| `qc repair-attempt` counter (independent of the Mode 12 counter) | `core/findings.py:96-136` | only `core/qc_cli.py` reaches it |
| idea templates `prompts/idea-<domain>.md` / `prompts/idea.md` | `core/ideas.py:22-24` | files do not exist, so `template_reference` is always null |
| `interrupt_after` fault-injection parameter in production signatures | `core/file_transactions.py:37,82` | test hook |
| two incompatible backup formats (`rollback` vs `updates rollback`) | `core/rollback.py:12` vs `core/file_updates.py:109-111` | g1, inferred |

### K.4 Documented but not implemented, or implemented differently

| Claim | Doc | Reality |
|---|---|---|
| Thresholds and limits "are stored in `config/defaults.json`" (implied to govern) | `core/API.md:345-348`, `playbooks/settings.md:9-12` | stored, but hard-coded elsewhere or unused |
| Local overlay waivers BETA-CAP-100 / BETA-ORACLE-2 | `qc/policy/beta.json:15-29` | file unread; partial hard-coding |
| Checkers run "on an isolated exact copy" | `playbooks/verify.md:19-20` | run in place with a mutation guard (`core/qc_runner.py:37-51`) |
| "Compare generator guidance, Input QC, Output QC separately ... rule IDs and severities" | `playbooks/upstream.md:17-20` | byte-level file diff against the Harbor repo |
| Record rejected ideas and nearest matches | `playbooks/chatgpt-ideas.md:37-38` | not stored |
| Unknown natural prose "returns a structured clarification" | `playbooks/qc-repair.md:71-72` | raises `ambiguous_selection` (exit 2) |
| `references/archive/` evidence library | `README.md:47`, `source-catalog.md:35-50` | git-ignored and absent; `catalog.json` lists 3,202 files |
| "show the 11 modes" / "11-mode menu" | `config/agent_adapters/opencode.md:14`, `claude-code.md:14`, `playbooks/resume.md:26` | stale; 12 modes exist |
| `release recover` | implied by `status.pending_release_recovery` | no CLI (`BETA-GENERATOR-HANDBOOK.md:429`) |
| Generator-side `validate_bundle.py` checks (partial-solver ceiling, visible-only solve, `sample_*.json` rejection) | `SNAP/generator_reference/*.md` | scripts not in the snapshot (`tools/archive_sources.py:229-235` copies only templates, reference and `*.md`) |
| Delivered `task.toml` name `terminal-bench/<id>` | `references/curated/design-guide.md:47-48` | the stub writes `beta/<id>` (RUN_LOG #13); release only checks the last path segment (`core/package_contracts.py:66-69`) |

### K.5 Implemented but undocumented or under-documented

- The stub run must provide `paying_tests == reviewed_tests` plus `judgement_rationale` (`core/runtime_intake.py:240-248`). The playbooks say only "report its score and every paying test".
- The report can declare its own `profile` (`personal` or `upstream`), which selects 2 vs 5 oracle runs (`core/runtime_intake.py:79-81,231`).
- `INFO` from output QC maps to blocking `MINOR` (`core/qc_runner.py:151`). `SKIP` counts as passing in semantic review (`core/qc_semantics.py:153`).
- Repair reconcile ignores waivers and the cap exception (`core/repair_verification.py:157-187`).
- `tasks adopt` skips name validation (`core/revisions.py:89-99`).
- `init` reads defaults from the package and ignores `--root` (`core/cli.py:148`).
- Mechanism evidence status RUNNER_OBSERVED requires a registered QC receipt under `workspace/qc/receipts/` (`core/mechanisms.py:155-192`).

## L. Run evidence

Full command list and exit codes: `RUN_LOG.md`. Everything ran in `/tmp/beta-analysis-20261020T2228/`, never in SOURCE.

| Check | Result |
|---|---|
| Test suite, plain copy, Python 3.14.8 and 3.13.16 | 173 tests: **5 failures, 33 errors** on both versions. 34 of the 38 share one cause: `snapshot_integrity` digest mismatch |
| Pinned digests (`config/source_components.json`) vs snapshot bytes | all 3 MISMATCH as checked out (LF). All 3 MATCH after converting snapshot text files to CRLF, so the pins were computed on a Windows checkout and nothing normalizes line endings |
| Test suite with CRLF-converted snapshot, py3.14 and py3.13 | 173 tests: **3 failures, 1 error (169 pass)**. Remaining: `references/archive/` absent (1 error); test asserts the repo has no commits but HEAD exists (1); macOS `/var` vs `/private/var` path resolution (2) |
| `--help` for root + 93 sub-paths | 94/94 exit 0 |
| `status` -> `init` -> `status` | `needs_init`, then `initialized`, then `ready`; `release_ready: false` throughout |
| `tasks create` / bad name | stub bundle with 2 files / exit 2 `invalid_task_name` |
| `qc verify --kind input` on the stub and on an adopted upstream template | runs the 4 pinned checkers and writes a receipt; verdict FAIL (expected for scaffolds). On the LF copy the verdict is `BLOCKED` with `SNAPSHOT_INTEGRITY` |
| `qc-repair open` on the LF copy | exit 2, `snapshot_integrity` |
| Ideas flow with the prompt's own example envelopes | works. The accepted review passes once the documented evidence file is written; its hash equals the documented `ddf35011…9f11` |
| `release check` on an adopted template | exit 2, `invalid_bundle: package folder does not match the pinned contract` (the template root holds an extra `archetype.toml`, which is outside the exact root set) |
| `host doctor` | claude 2.1.304, opencode 1.19.0, git 2.54.0, python 3.14.8 |
| Not run | `sources check` (network fetch); `assets download` (network); `updates apply` (runs the whole test suite in a copy, no timeout); Harbor or model runs (none exist in the tool) |

Broken in practice:
1. Every QC and repair path on an LF checkout (macOS/Linux).
2. The archive-dependent test.
3. The no-commit assertion.

Probable but unexercised bugs are listed in F.6.

## Not checked

| Item | Why |
|---|---|
| `references/archive/` (3,202 files, 47.6 MB per `references/catalog.json`) | not in the repo (git-ignored); only the catalog was read, as aggregates |
| `qc/snapshots/.../Output_Bundle_QC/output_qc.py` in full (2,574 lines) | read at function and rule level through a subagent (g3 notes); spot-checked lines 1302-1325 and 2507-2510 |
| Upstream `Input_Bundle_QC/*.md` gate guides and `Final_checklist.md` line by line | read by the g3 subagent; spot-checked AL-30 (`05_Alignment_Integrity_QC.md:133-137`) and the `Final_checklist.md:618-624` decision |
| `generator_reference/{ARCHITECTURE_MAP, AUDIT_NOTES, CATEGORIES, README, ARCHETYPE_SELECTION, FORMAT_SPEC}.md` and `frontier-bench/*` | read by the g3 subagent. I read `CHEAT_VECTORS.md` and `GENERATOR_TRAP_RECIPE.md` in full and `FORMAT_SPEC.md:538-592` |
| 8 upstream templates (`templates/*`: 186 files) | inventoried (sizes, extensions, test/rubric counts) by g3 and re-measured by me (data bytes, extensions); test code not read line by line |
| Infra modules `state.py`, `proposals.py`, `file_transactions.py`, `file_updates.py`, `bundle_transactions.py`, `revisions.py`, `contracts.py`, `package_contracts.py`, `delivery.py`, `runtime_intake.py`, `bootstrap.py`, `common.py`, `paths.py`, `permissions.py`, `rollback.py`, `host_adapters.py`, `adapter_recovery.py`, `cli.py` (except `:160-200`), `tasks_cli.py`, `runs_cli.py`, `delivery_cli.py` | read in full by the g1 subagent; I read `models.py`, `settings.py` and `update.py` myself and spot-verified `package_contracts.py:10-45`, `runtime_intake.py:225-250` and `file_updates.py:10-25` |
| QC and repair modules (`qc_runner`, `qc_receipts`, `qc_semantics`, `qc_repair`, `repair_*`, `findings`, `verdicts`, `analysis*`) | read in full by the g2 subagent; I read `qc_snapshot.py` in full and spot-verified `findings.py:50-63`, `qc_runner.py:96-110,154-163`, `repair_verification.py:120-135` and `qc_repair.py:70-76` |
| `tests/*.py` (30 files) | not read individually beyond `test_archives.py` and `test_foundation_common.py:67-77`; executed instead |
| Native Harbor 0.23 / 0.24 behaviour | no Harbor install was used; the 0.24 format was not available |
| Runtime behaviour of `sources check` against the default URL | needs network; conclusion in I.2 is from code only (UNVERIFIED) |
| Output-kind QC Repair end to end, F.6 #2-#3 bugs | not exercised |

