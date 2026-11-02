# Input Bundle Format Spec (v1)

> **Superseded for Harbor 0.24.** The bundle contract is now
> `Input_Bundle_QC/Final_checklist.md`: schema 1.4 task.toml, rewardkit test channel
> (`criteria.<name>(weight=W)` in `tests/test_output.py`, no `test_weights.json`),
> `tests/judge.toml` instead of `rubric.json`, a generated `tests/reward.toml`, and
> no `README.md` in the bundle. Where this document says otherwise, the checklist wins.

Authoritative specification. `validate_bundle.py` enforces every rule below.

## §0. Provenance

This format is the union of three constraint sources:

1. **`README (2).md`** — the upstream *Agentic Terminal Task Authoring Guide*.
   All of its prose fields, agent-visibility rules, and Dockerfile clauses are
   preserved. Where this format deliberately supersedes a guide clause, the
   deviation is called out with **[deviation]** and rationale.
2. **`qtm-format-recovery`** and **`telemetry-codec-recovery`** — the two
   in-repo bundles that already work end-to-end under `harbor run`. Their
   proven byte-level patterns (reward formula, CTRF structure, RNG choice,
   corpus tiering) are lifted verbatim.
3. **`harbor-binary-reward.md`** — Harbor's memo on why binary 0/1 rewards
   destroy training signal. This format writes fractional rewards and
   preserves per-test detail in CTRF, exactly as that memo prescribes.

## §1. Directory shape

A compliant bundle is a directory whose name matches `^[a-z0-9][a-z0-9-]{2,63}$`
and contains exactly these entries:

```
<bundle-name>/
├── instruction.md              [file, required]
├── task.toml                   [file, required]
├── README.md                   [file, required]
├── environment/
│   ├── Dockerfile              [file, required]
│   └── data/                   [dir,  required, must be non-empty after `python3 tests/test_output.py environment`]
├── solution/
│   ├── solve.sh                [file, required, chmod +x]
│   ├── solve.py                [file, required]
│   └── TRUTH.md                [file, required; author-side golden trajectory, see §15]
└── tests/
    ├── Dockerfile              [file, required]
    ├── test.sh                 [file, required, chmod +x]
    ├── test_output.py          [file, required]
    ├── test_weights.json       [file, required]
    └── rubric.json             [file, required]
```

No other files at the bundle root or under `solution/` or `tests/`, with one
policy exception: a `trajectories/` directory of recorded agent runs at the
bundle root is accepted on delivery. No Dockerfile copies it, so it reaches
neither container and cannot influence a score; `structure_qc.py` warns on the
directory and on the `reward*.json` / `ctrf.json` run records inside it instead
of failing. The generator never emits one, and a `.DS_Store` still fails there
as it does anywhere else. The
generator never emits a `cheat/` overlay; `validate_bundle.py` still tolerates
an author-supplied one for backward compatibility (see §13.1 for the retired
generator flag). `environment/data/` is flat — files only, with no
subdirectories; nothing else at `environment/` root beyond `Dockerfile` and
`data/`.

Every archetype must ship at least `min_inputs` flat files directly under
`environment/data/` and declare at least `min_outputs` paths in
`task.toml.artifacts`. The global floor is 6 inputs / 6 outputs; the
data-science archetypes (`data-pipeline`, `domain-calculation`, and
`performance`) use the 10 inputs / 10 outputs tier. A `source_archives` `.zip`
is counted as one input file and is never expanded for this count. The
per-archetype minimums are top-level `min_inputs` / `min_outputs` keys in
`templates/<archetype>/archetype.toml`.

## §2. `instruction.md` (agent-visible)

- **Audience**: the agent, and only the agent.
- **Length**: < 1500 tokens (roughly < 6000 characters).
- **Every output path the agent must produce**: named as a literal absolute
  path inside backticks (e.g. `` `/app/decode.py` ``). The harness collects
  deliverables by copying from the exact absolute paths declared in
  `task.toml.artifacts`, so every declared artifact must be reachable from the
  instruction wording. This is the one enumeration the instruction still owes.
- **Inputs are NOT enumerated.** The instruction owes nothing about its inputs.
  It **must not** list every file under `environment/data/`, and it need name no
  input file, path, or format at all. It points the agent at `/app/data/` as the
  place the task's materials live and lets the agent discover which files are
  relevant to which part of the work. When the instruction *does* name a concrete
  `/app/data/<name>` path, that path must exist (so a named reference is never a
  dead link), but naming any specific input is optional. Shipping a broad set of
  reference files and making the agent choose which ones a given deliverable needs
  is a feature, not a defect — see §9.
- **What the agent must NOT do at runtime**: enumerated (e.g. "cannot read
  `/app/data/` from the delivered decoder"; "cannot pip-install at run
  time").
- **Time budget**: stated in seconds ("You have 7200 seconds to complete
  this task.").
- **Cheating prohibition**: one sentence forbidding online-solution lookup.
- **What "what" not "how"**: the file describes the required *end state* — the
  behavior and shape of the finished deliverables — never a step-by-step recipe
  for producing them. No spelled-out decode/derivation algorithm, no numbered
  "first do X, then do Y" solving procedure, no easy hints that let a careless
  agent transcribe the instruction into code without understanding the problem.
  Discovering *how* to satisfy the contract from the shipped materials is the
  task. Any procedural hint that IS (part of) the solution is a bug.
- **Withholding vs. unreachability.** Leaving the *how* out of the instruction is
  correct. But whatever the instruction withholds must still be **discoverable
  from the shipped `environment/data/` materials** — the full format
  specification, schema, or reference files. A rule the instruction omits *and*
  that appears nowhere in `environment/data/` is a solvability defect, not
  difficulty (see §9, and the QC solvability gates DS-22 / F0e / AL-F0e).
- **JSON shape**: if the agent must emit JSON, one canonical *shape* example may
  be shown inline as a fenced ` ```json ` block. The example illustrates the
  output schema; it must not be a worked answer to a graded case.

## §3. `task.toml` (slim schema, v2 as of commit `26413d67`)

The file MUST parse as TOML with the following slim shape (aligned with the
frontier-bench canonical template at
`reference/frontier-bench/docs/task-template.toml`):

- **Root:**
  - `schema_version = "1.1"`.
  - `artifacts` — list of absolute paths the verifier will upload from the
    agent container; its length must meet the archetype's `min_outputs`
    minimum.
- **`[task]` table:**
  - `name = "terminal-bench/<slug>"`.
  - `description` — one-sentence description of the task.
  - `keywords` — list of strings.
- **`[metadata]` table:**
  - `difficulty` — `"trivial" | "easy" | "medium" | "hard" | "expert"`.
  - `category` — one of the 16 Title-Case display values in `CATEGORIES.md`
    (e.g. `"Debugging"`, `"Security"`, `"Mathematics"`). The canonical
    frontier-bench domain and subcategory that each user category maps to
    are held internally in `generate_bundle.py` (`_CATEGORIES[<name>].canonical`
    and `.subcategory`) and are NOT emitted to `task.toml`.
  - `tags` — list of strings (defaults to `keywords` if `--tags` is omitted).
  - `estimated_duration_sec` — float, wall-clock estimate of a graded run.
  - `expert_time_estimate_min` — float, minutes.
  - `junior_time_estimate_min` — float, minutes.
- **`[verifier]` table:**
  - `timeout_sec` — float, verifier bound.
- **`[agent]` table:**
  - `timeout_sec` — float, agent bound. `instruction.md`'s trailer sentence
    quotes this value as an integer (`{{AGENT_TIMEOUT_SEC_INT}}`) to satisfy
    frontier-bench `checks/check-instruction-suffix.sh`.
- **`[environment]` table:**
  - `build_timeout_sec` — float, image build bound.
  - `allow_internet` — bool, **always emitted as `true`**. Harbor maps
    `allow_internet = false` to `network_mode = "no-network"`, which Docker
    Desktop on macOS rejects at trial construction, so the generator substitutes
    a literal `true` into `{{ALLOW_INTERNET}}`. Each `archetype.toml` still
    declares an `allow_internet` value and the `--allow-internet` /
    `--no-allow-internet` flag is still accepted, but both are ignored. The
    downstream QC gate (`structure_qc.py` T14) accepts either boolean; gates
    01/02/05 (IN-12, DS-12, AL-17) require the instruction, Dockerfile and
    solution to be consistent with the emitted `true` value.
  - `mcp_servers` — list, empty.

**Verifier isolation, declared *and* structural.** `[verifier]` carries
`environment_mode = "separate"`, matching the frontier-bench canonical
`task-template.toml`; `validate_bundle.py` §3.4 rejects any bundle whose value
is not exactly `"separate"`. The same guarantee is *independently* enforced
structurally — via two Dockerfiles (§5, §7) whose `COPY` clauses do not
overlap, checked by §5.7 (`environment/Dockerfile` may not `COPY solution/`
or `COPY tests/`). The declaration tells the runner which mode to use; the
Dockerfile split makes the isolation true even if a runner ignores the flag.

**Fields deliberately dropped in the v2 slim refactor** (see `AUDIT_NOTES.md`
"v2 slim-schema refactor" for the audit trail): `task_objective`,
`difficulty_explanation`, `solution_explanation`, `verification_explanation`,
`artifact_type`, `expert_time_estimate_hours`, root-level `allow_internet`,
root-level `timeout_sec`, and the `[environment]` sizing fields
(`docker_image`, `cpus`, `memory_mb`, `storage_mb`, `gpus`). Their content
either moved to `README.md` prose (the three explanations) or was subsumed by
an existing `[metadata]`/`[environment]`/`[agent]` field.

`[verifier].environment_mode` was also dropped in that refactor but has since
been **restored** — it is required again and must equal `"separate"`.

## §4. `README.md` (human-visible, task-level)

Contains exactly these H2 headings, in this order:

1. `## Task Metadata` — bullet list of difficulty / category / tags / expert
   time / junior time / agent timeout / CPUs / memory. Every value here is a
   `{{PLACEHOLDER}}` substituted from the CLI args, so this section is the
   single source of truth for the human-readable metadata (task.toml carries
   the machine-readable copies).
2. `## Difficulty explanation` — prose describing why this task is hard
   (owns the content that used to duplicate into `task.toml.difficulty_explanation`).
3. `## Solution explanation` — prose sketch of the reference solution
   (owns what used to duplicate into `task.toml.solution_explanation`).
4. `## Verification explanation` — prose describing the grading strategy
   (owns what used to duplicate into `task.toml.verification_explanation`).
5. `## Measured scores` — literal lines like `oracle: 1.000`, `nop: 0.000`,
   plus any calibration measurements against known baselines.
6. `## Additional Notes` — anything else authors need to remember about
   corpus regeneration, seed choices, etc.

## §5. `environment/Dockerfile` (agent image)

Rules:

1. `FROM` a digest-pinned image under `public.ecr.aws/docker/library/`. The
   canonical base is
   `FROM public.ecr.aws/docker/library/python:3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b`
   (Python 3.12.13-slim-trixie, resolved 2026-08-06). Newer digests are
   fine as long as they are digest-pinned and under the same registry
   namespace.
2. One `apt-get` layer. Must include `apt-get update && apt-get install -y
   --no-install-recommends ...` **and** `&& rm -rf /var/lib/apt/lists/*`
   in the same `RUN`.
3. Baseline apt packages: `xxd file curl bash nodejs npm procps
   ca-certificates`. Additional packages are permitted; version pins on apt
   packages are forbidden (they break arch mirrors).
4. Keep the image agent-neutral. Harbor supplies the selected agent at run time;
   the task image MUST NOT install Claude Code or another agent CLI.
5. `WORKDIR /app`.
6. `RUN mkdir -p /app` (before `COPY`, to guarantee the artifact landing
   dir exists even if `COPY data /app/data` fails).
7. Exactly one `COPY` line at the end: `COPY data /app/data`.
8. **NEVER** `COPY solution/` or `COPY tests/` — those overlays are staged
   by Harbor at run time, not baked in.
9. No file larger than 100 MB inside `data/` (Harbor build-context ceiling).

## §6. `solution/` (oracle-only overlay)

- **`solve.sh`** (executable) is the entry point Harbor runs when
  `--agent oracle`. It MUST:
  - Set `set -euo pipefail`.
  - Copy `/solution/solve.py` into every artifact path declared in
    `task.toml.artifacts` (this is how the delivered files land in `/app/`).
  - Verify that every sample in `/app/data/` decodes to a structurally valid
    document (Phase 1; decoded answer files are forbidden in agent data).
  - Round-trip every sample through the encoder (Phase 2: decode
    then re-encode, expect byte-identical output).
  - Exit non-zero with a descriptive `sys.exit(...)` on any mismatch.
- **`solve.py`** is the reference implementation. When `task.toml.artifacts`
  is a single file, `solve.py` IS that file (renamed on copy). When
  `artifacts` is a list of N distinct paths (typical: `["/app/decode.py",
  "/app/encode.py"]`), `solve.py` is a single file that dispatches on
  argument count: `python3 solve.py <input>` decodes, `python3 solve.py
  <input> <output>` encodes.

## §7. `tests/` (verifier-only overlay)

- **`test_output.py`** MUST be self-contained:
  - Imports only Python stdlib.
  - Uses a fully-specified deterministic RNG (typically `xorshift64` —
    CPython's `random` is not contractually stable across releases).
  - Declares three seeds at module scope: `SAMPLE_SEED`, `CHALLENGE_SEED`,
    `EVAL_SEED`.
  - Contains the encoder that produced the shipped `environment/data/`
    files. Rebuilding with the same seed reproduces the shipped bytes
    exactly.
  - Contains N `test_*` functions, each with a one-line docstring beginning
    `POSITIVE:` or `NEGATIVE:`.
  - Ends with `if __name__ == "__main__": _write_corpus(Path(sys.argv[1]))`
    so `python3 tests/test_output.py environment` regenerates the
    sample+challenge tiers into `environment/data/`.
- **`test_weights.json`** is a JSON object mapping each `test_*` function
  name to a signed integer weight. The legal weight set is
  `{1, 3, 5, -1, -3, -5}`. Positive weights use `1`, `3`, `5`; negative
  weights use `-3` or `-5` by convention (`-1` is permitted but discouraged
  as noise). At least ONE
  negative weight test that closes the hardcoding cheat must exist:
  `test_negative_weight_hardcoded_sample_answers`.
- **`rubric.json`** is a JSON array of objects with EXACTLY these keys:
  `number` (string, `"R1"`, `"R2"`, ...), `criterion` (string, the
  criterion text), `is_positive` (boolean), `type` (one of `"agent
  behavior"`, `"task completion"`, `"factuality and hallucination"`,
  `"tool use"`, `"instruction following"`, `"safety and boundaries"`),
  `evaluation_target` (one of `"trajectory"`, `"final_answer"`, or
  `"user_facing_message"` — see next paragraph re `"state_change"`),
  `importance` (one of `"critically_important"`, `"important"`), `score`
  (integer). At least **three** entries must have
  `type = "instruction following"`; `generate_bundle.py` fails the scaffold
  if a template drifts below that floor.
- **Rubric ↔ test separation of concerns (generator-enforced).** Rubric
  grades **process and response quality** — how the agent reasoned,
  whether it followed the contract, what its final answer said. The
  automated tests in `test_output.py` grade **artifact and state
  correctness** — did the produced files, records, and side effects come
  out right. The two channels MUST NOT grade the same property twice.
  Because `evaluation_target = "state_change"` is by construction the
  artifact/state axis that `test_output.py` already owns, the generator
  refuses to emit any bundle whose `rubric.json` contains a `state_change`
  entry. Use `"trajectory"`, `"final_answer"`, or `"user_facing_message"`
  instead; `validate_bundle.py` still accepts historical bundles that
  contain `state_change` for backward compatibility, but new bundles
  produced by `generate_bundle.py` will never carry one.
- The canonical timeout sentence in `instruction.md` is owned by Harbor's
  `[agent].timeout_sec` enforcement and suffix checker. Rubric criteria and
  artifact tests do not duplicate that harness-owned control.
- **`Dockerfile`** MUST be:
  ```dockerfile
  FROM public.ecr.aws/docker/library/python:3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b
  RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2
  COPY . /tests/
  RUN mkdir -p /app
  ```
  Pytest versions are pinned exactly because the verifier's grading math
  depends on the exact assertion behavior of a specific pytest release.
- **`test.sh`** (executable) MUST implement the standardized reward
  computation. See §8.

## §8. Reward computation (`test.sh`)

The reward formula is **standardized across all bundles** so Harbor can
compare scores task-to-task. It MUST be byte-identical to this:

```python
raw = 0.0
positive_total = 0.0
for name, weight in weights.items():
    weight = float(weight)
    if weight > 0:
        positive_total += weight
    test_fn = getattr(test_output, name, None)
    passed = False
    detail = ""
    if test_fn is not None:
        try:
            test_fn()
            passed = True
        except Exception:
            detail = traceback.format_exc(limit=3).strip().splitlines()[-1]
    if passed:
        raw += weight
    results.append((name, weight, passed, detail))

reward = raw / positive_total if positive_total > 0 else 0.0
reward = max(-1.0, min(1.0, reward))
```

`test.sh` writes three files to `/logs/verifier/`:

1. `reward.json` — `{"reward": <float>}`. This is the single fractional
   number Harbor reads.
2. `reward.txt` — the same float as plain text. Kept for parity with
   Harbor's binary-reward pathway.
3. `ctrf.json` — full per-test CTRF (Common Test Result Format) report
   with `results.tool.name = "grade"`, `results.summary.{tests, passed,
   failed}` counts, and `results.tests[]` = list of
   `{name, status, duration: 0, message}` objects. This is what
   `harbor-binary-reward.md` says is discarded on `main` — the fractional
   reward + this file together restore the training signal.

`test.sh` MUST assert the bijection between `test_weights.json` keys and
`dir(test_output)` `test_*` symbols before running anything. A mismatch is
a `SystemExit`, not a silently-degraded run.

## §9. Corpus policy (and the solvability invariant)

**The solvability invariant (authoritative).** Every graded output must be
derivable from the agent-visible files alone — `instruction.md` plus everything
under `environment/data/` — and nothing else. A hidden seed (`EVAL_SEED`, the
root seed) may randomize *which* concrete bytes the verifier generates, but it
must **never** be a value a solver needs at solve time. If reproducing a graded
answer requires a value that lives only in `tests/`, in an environment variable,
in the network, or in an author's head, the task is **impossible, not hard**, and
must not ship. This invariant is enforced by hand in the QC bundle (DS-22 / F0e /
AL-F0e) and automatically by `validate_bundle.py --semantic` (§10, §12).

Generated bundles ship **no agent-visible capture corpus** and **no decoded
answer files**. `environment/data/` contains the **complete written
specification** (and any other flat, non-answer reference files the task needs).
The agent implements the format from that specification alone — which it can,
because the specification is complete: every rule the hidden corpus exercises is
documented there, with worked byte-level examples.

The verifier owns the capture corpus. `test_output.py` reseeds a
sample / challenge / eval corpus from `SAMPLE_SEED`, `CHALLENGE_SEED`, and
`EVAL_SEED` into a seed-specific temporary directory at grade time, so the
bytes are byte-reproducible without ever being shipped in the agent build
context. The eval tier probes edge cases (record count = 1, edge of int32,
one-past-a-stride, etc.); `EVAL_SEED` lives ONLY in the verifier image and is
never seen by the agent. **The seed decides which concrete values appear; the
shipped spec tells the agent how to decode any of them.** No graded byte depends
on a rule the spec omits.

Because the full format is written out, difficulty comes from the breadth and
interaction of the specified rules (multi-mode records, cross-record state, a
dictionary, seed-varying header/CRC semantics, signed-boundary payloads), **not
from hiding text**. Hiding a derivation does not add difficulty; it removes
solvability. A partial reader that implements only the easy modes still fails the
hidden-corpus tests for the modes it skipped — that is the intended difficulty,
and it survives full documentation.

**Rich inputs, agent chooses.** A task may ship a broad set of reference files so
that only a subset is relevant to any one deliverable and the agent must decide
which materials a given query needs. That breadth is legitimate difficulty. It is
**not** licence to ship pure decoy files: every file under `environment/data/`
must be necessary for at least one graded case, cross-check, or disambiguation
(QC DS-2 / AL-F0b — "delete `environment/data/` and the task must become
unsolvable"). Achieve "the model must choose" through breadth of *relevant*
material, not through junk.

## §10. Local test contract

Two `harbor run` invocations MUST hold:

- `harbor run --path <bundle> --agent oracle --env docker` → reward `1.000`.
- `harbor run --path <bundle> --agent nop    --env docker` → reward
  `0.000`. No negative-weight cheat test may fire on the empty container, so
  the nop reward must net exactly zero.

If oracle ≠ 1.000 or nop ≠ 0.000 (each within a ±0.0005 tolerance), the
bundle is broken and MUST NOT ship.

**The oracle/nop pair is a floor check, not a solvability proof.** Oracle = 1.000
only proves that the reference `solve.py` — which already contains the rule —
reaches full reward; it says nothing about whether an agent that holds only
`instruction.md` and `environment/data/` could reach it. To close that gap,
`validate_bundle.py --semantic` additionally runs a **visible-only solvability
phase**:

1. It runs the reference `solution/solve.sh` in a sandbox that holds **only**
   `instruction.md`, `task.toml`, `environment/data/`, and the writable artifact
   output paths — no `EVAL_SEED`, no root seed, no other `tests/` material, no
   network — and requires the resulting reward to be `1.000`.
2. It runs a **static solution audit** over `solution/solve.py`: the reference
   may read only `/app/data/` and its declared output paths; it may not read
   `os.environ`, reference a seed, open the network, or reach hidden-corpus
   paths, and it may not embed large opaque byte/int/string constants that do not
   appear anywhere in the agent-visible files (which would smuggle in a hidden
   key or seed-derived constant).

A bundle whose reference solver needs a hidden value to reach `1.000` fails this
phase with a message naming the missing input. This is the automated counterpart
to the manual QC solvability gates (DS-22 / F0e / AL-F0e). See §12.

## §11. Cheat vectors (see `CHEAT_VECTORS.md`)

The format's design closes these known cheats. Each is covered by at
least one negative-weight test in `test_weights.json` (or by the
structural two-Dockerfile verifier overlay).

| Cheat | Format mitigation |
|-------|-------------------|
| Answer key baked into delivered decoder | `test_negative_weight_hardcoded_sample_answers` |
| Behavior varies with input filename | `test_negative_weight_filename_dependent_behaviour` |
| Delivered code reads `/app/data/` at runtime | `test_negative_weight_reads_training_corpus_at_runtime` |
| Output is non-deterministic across invocations | `test_negative_weight_nondeterministic_output` |
| Eval corpus leaks via file inspection | Two-Dockerfile design keeps `EVAL_SEED` in `tests/Dockerfile` only (§7); `environment/Dockerfile` never `COPY`s from `solution/` or `tests/` (§5.7) |
| Online-solution lookup | Prohibited in `instruction.md`; task must be sufficiently novel that no lookup exists |
| Monkey-patching or verifier interception | Rubric R9 penalizes mutation of verifier assets; submitted programs also execute as an unprivileged user that cannot read `/tests` |

## §12. What `validate_bundle.py` checks

Every rule above is enforced. See `validate_bundle.py --help` for the
option to print rule references (`--verbose`).

The **static** rules run on every invocation. Two extra phases run only under
`--semantic` (they need Docker):

- **Floor phase** (§10): builds the env and tests images, confirms the empty
  container scores `< 1.000` and the reference `solve.sh` (with full `solution/`
  access) scores `1.000`.
- **Solvability phase** (§9, §10): a **static solution audit** of
  `solution/solve.py` (no reads outside `/app/data/` and declared artifact
  paths; no `os.environ`/seed/network/hidden-corpus access; no large opaque
  constants absent from the agent-visible files) followed by a **visible-only
  solve** — the reference `solve.sh` is run in a sandbox holding only
  `instruction.md`, `task.toml`, `environment/data/`, and the writable artifact
  paths, with `EVAL_SEED`/root-seed/API-key environment variables scrubbed and
  the network disabled, and must still score `1.000`. This is the automated
  enforcement of the §9 solvability invariant. A bundle that fails it is
  impossible for an honest agent and MUST NOT ship, regardless of the floor
  phase.

Exit codes:
- `0` — every rule passes.
- `1` — at least one rule failed. Failing rule prints its `FORMAT_SPEC.md`
  section reference (e.g. `FAIL[§5.1] environment/Dockerfile FROM line is
  not digest-pinned`, or `FAIL[§9] solvability: reference solver needs a value
  absent from agent-visible files`).
- `2` — usage error (bad argument, missing bundle).

## §13. v2 randomization (multi-category, per-seed uniqueness)

Since v2, `generate_bundle.py` accepts `--category` (16 CLI keys whose
Title-Case display values are emitted to `task.toml`) and `--seed` (a 63-bit
integer). All identifying flags
(`--name`, `--title`, `--format-tag`, `--format-ext`, `--description`,
`--keywords`) are OPTIONAL — when omitted they are synthesized from the
`(category, seed)` pair via `random.Random(seed)` sampling from
category-scoped word pools.

Determinism contract:

- **Same seed + same category + same archetype + same output-directory state
  produces the same bundle under the same generator/runtime version.** The
  output-directory state matters only when the generator chooses the next
  numbered name automatically.
- **Different seeds select independently-derived grammar and corpus state.**
  Individual cosmetic values may collide, but the generated structural grammar
  still varies across selector layout, header order, delta encoding, dictionary
  semantics, and CRC coverage.
- `SAMPLE_SEED`, `CHALLENGE_SEED`, `EVAL_SEED` are derived from the
  root seed via `hashlib.blake2b(..., digest_size=8)` so child seeds
  are stable across Python versions and free of hash-randomization
  drift.

Randomized fields (all placeholder-substituted at scaffold time):

| Placeholder | Source | Guarantee |
|-------------|--------|-----------|
| `{{BUNDLE_NAME}}` | explicit `--name`, or a title/category-derived stem plus `_NN` | topic-derived and collision-free within the output directory |
| `{{FORMAT_TAG}}` | category `tag_prefix_pool` sample | matches `^[A-Z][A-Z0-9]{2,7}$` |
| `{{FORMAT_EXT}}` | category `ext_pool` sample | matches `^\.[a-z0-9]{2,8}$` |
| `{{MAGIC_ASCII}}`, `{{MAGIC_HEX}}` | category `magic_pool` sample (5-byte ASCII) | valid Python `b"..."` literal + lowercase hex |
| `{{VERSION_NUM}}`, `{{VERSION_NUM_HEX}}` | `random.Random(seed).randint(1, 5)` | decimal + `0xNN` hex |
| `{{SAMPLE_SEED}}`, `{{CHALLENGE_SEED}}`, `{{EVAL_SEED}}` | BLAKE2b(root_seed, tag) → 63-bit int | stable, independent |
| `{{CATEGORY_CANONICAL}}`, `{{SUBCATEGORY}}` | `_CATEGORIES[cat]` static mapping | internal only; NOT emitted to `task.toml`; surfaced in the generated README for reviewer context |
| `{{CATEGORY}}` | `_CATEGORIES[args.category]["display"]` | one of the 16 exact Title-Case values; emitted to `task.toml.[metadata].category` |

**`task.toml.[metadata].category` in the v2 slim schema is the Title-Case
display value** associated with the CLI key. For example, operators pass
`--category debugging` and the output contains `[metadata].category =
"Debugging"`. The seven-domain canonical/subcategory pair remains internal in
`_CATEGORIES` and is surfaced in the generated README for reviewer context.

### §13.1 Retired cheat-oracle generation

`--with-cheat` / `--no-with-cheat` and the `supports_cheat` archetype flag have
been removed from `generate_bundle.py`. The generator never emits a `cheat/`
overlay under any invocation. `validate_bundle.py` continues to accept
author-supplied `cheat/` directories under the original file-and-sentinel rules
so that historical bundles keep validating, but new bundles produced by this
tool cannot contain one.

### §13.2 Contributor attribution

`generate_bundle.py --author EMAIL[ (NOTE)]` records contributors on the
generated `task.toml` under `[task].authors`. The flag is repeatable, accepts a
short parenthesized note per address (e.g. `"alice@example.com (IB Created)"`),
and rejects duplicates and malformed entries. Omitting it emits
`authors = []`.

Entries are emitted as TOML inline tables, because harbor models
`[task].authors` as `list[Author]` with a required `name` and an optional
`email` — an array of plain strings fails validation, and harbor then discovers
zero tasks and aborts the whole run. The note becomes `name`; a bare email
doubles as its own `name`:

```toml
authors = [{ name = "IB Created", email = "alice@example.com" }, { name = "bob@example.com", email = "bob@example.com" }]
```

## §14. HARDFMT template complexity contract (v3, 2026-08-07)

The template no longer emits a minimal proof-of-concept format. Every generated
bundle exercises the same complexity levers that beat flagship-class agents in
the reference runs `governing-coefficient-recovery-20260807-122208`
(Opus reward 0.154) and `telemetry-codec-recovery-20260806-133521`
(Opus reward 0.419).

**Required complexity levers baked into every generated bundle:**

- **Multi-mode records with a generated packed selector byte.** Each record
  starts with a selector whose two mode-bit positions, wide/long-key flag bits,
  and numeric raw/delta/dictionary IDs are selected from the root seed. Agents
  must recover this bundle's mapping from its evidence.
- **Generated cross-record state.** Delta mode uses either zigzag-uvarint or
  signed LEB128. Dictionary records select resolved or payload values and use
  forward or backward payload indexing. These choices are coherent across the
  generated spec, oracle, corpus builder, and verifier.
- **Generated header and CRC semantics.** The five post-magic header fields are
  seed-ordered, and CRC coverage is either the full prefix or header+records
  region defined by the generated grammar.
- **Sign-extension edge cases.** Raw payload lives in signed `i16`/`i32`.
  Challenge captures include values near `INT16_MAX` and `INT32_MAX` so that
  any decoder that treats the payload as unsigned fails on those tests.
- **Byte-perfect encoder round-trip.** Encoders must preserve every field and
  apply the selected CRC coverage exactly; normalising generated state produces
  mismatching bytes.
- **Complete but dense multi-mode spec.** The shipped
  `{{FORMAT_TAG}}-container-format.md` documents every section in full — `§4`
  (delta mode), `§5` (dictionary mode), and `§6` (state semantics) included —
  with worked byte-level examples. **Every rule the hidden corpus exercises is
  documented here; nothing is redacted.** No capture corpus ships; the hidden
  EVAL_SEED-derived corpus exercises the delta, dictionary, and state material
  a raw-only solver never reaches — but it exercises *only* documented rules, so
  a careful reader of the spec can decode any eval capture (the §9 solvability
  invariant). Difficulty is the breadth and interaction of these documented
  rules, not hidden text.
- **25 tests total** (20 positive summing to 60, five negative summing to
  -23). Theoretical reward range is approximately `[-0.38, 1.00]`.

**Calibration targets:**

| Agent | Expected reward |
|-------|-----------------|
| oracle (reference decoder+encoder) | `1.000` |
| nop | `0.000` |
| labelled-tier-only solver | `~0.30` |
| format-partial solver (raw + one of delta/dict) | `~0.45-0.60` |
| Opus 4.8 target | `< 0.45` |

**Verified end-to-end on real harbor** (2026-08-07):
- Oracle reward = `1.0` (job `hardf-oracle-20260807-182145`).
- Nop reward = `0.0` (job `hardf-nop-20260807-182314`).
- Current validator count may increase as generic safety checks are added; zero
  failures and zero warnings remain the shipping criterion.

## §15. `TRUTH.md` (author-side golden trajectory)

`TRUTH.md` sits in `solution/` beside the oracle it describes and is **required
in every bundle**. It is the author-and-reviewer counterpart to the agent-visible
instruction: `instruction.md` states the task, `TRUTH.md` records the golden
trajectory that answers it.

It is never shipped into the agent container. `environment/Dockerfile` copies
`environment/data/`, not the bundle root, so the file is structurally
unreachable from the agent's filesystem. Its audience is the human reviewing the
bundle before it ships, and it exists to make three questions answerable without
reading the whole `tests/` tree:

1. Is this task actually solvable from agent-visible material alone (§9)?
2. Do the tests grade the thing `instruction.md` asks for?
3. Is there a shortcut that scores well without doing the work?

### §15.1 Size and substance

At least 4000 characters. A bundle whose `TRUTH.md` is a stub fails validation.
Generated bundles land between roughly 25 000 and 30 000 characters.

### §15.2 Title

The first line is exactly:

```
# TRUTH.md - <bundle-name>
```

where `<bundle-name>` is the bundle directory name.

### §15.3 Sections

Exactly these eight `##` headings must be present, in this order:

```
## Defect
## Load-bearing work
## Verification
## Root cause
## Solution shape
## Ordered plan
## Pitfalls
## Provenance
```

- **Defect** — an opening prose paragraph naming what is broken or redacted and
  what the agent must build, then a numbered list of classified defects (§15.4),
  then a paragraph naming the reference language and the two grading channels,
  then an `Out of bounds:` paragraph enumerating the disallowed shortcuts with
  the negative test that catches each one.
- **Load-bearing work** — the graded artifact list followed by a per-deliverable
  content contract, closing with `Out of bounds by design:`.
- **Verification** — how `tests/test.sh` scores the run (§8), the Channel A
  weight totals, the full positive and negative test lists, and the Channel B
  rubric criteria. It must state that the rule combining the two channels
  belongs to the runner harness and must not be transcribed into the bundle.
- **Root cause** — bolded sub-topics explaining the invariants the defects
  violate. The last is always `**Red lines.**`.
- **Solution shape** — the reference implementation's steps, numbered.
- **Ordered plan** — the trajectory a competent solver should follow, numbered,
  each step tied to the rubric criteria it earns.
- **Pitfalls** — bulleted wrong instincts, each naming the test it fails.
- **Provenance** — a fenced `yaml` block (§15.5).

### §15.4 Defect classification

Every item in the `## Defect` numbered list is prefixed with one of three
parenthesised labels. The mix is the task's difficulty budget made legible:

| Label | Meaning |
|---|---|
| `(focal)` | A defect the task is genuinely about. Fixing it is the work. |
| `(drift)` | An experienced instinct that contradicts the spec — the solver must notice that the obvious "improvement" breaks a stated contract. |
| `(trap)` | A defect invisible on the happy path that only surfaces under the grader's edge cases. |

Minimum mix: **at least two `(focal)`**, and at least one each of `(drift)` and
`(trap)`. Shipped archetypes carry three to five focal, one drift, two traps.

Each item should name the test function it defeats, so a reviewer can jump
straight from the claim to the assertion.

### §15.5 Provenance block

The `## Provenance` section is a single fenced ` ```yaml ` block. Required keys:

| Key | Contents |
|---|---|
| `uuid` | Instance UUID, derived from the generator seed. |
| `instance_id` | Must equal the bundle directory name. |
| `task_name` | Must equal `terminal-bench/<bundle-name>` and agree with `task.toml`'s `task.name`. |
| `fix_patch_sha256` | sha256 of the shipped `solution/solve.sh`. |
| `solve_py_sha256` | sha256 of the shipped `solution/solve.py`. |
| `language` | Reference implementation language. |
| `authored_by` | Attribution string. |
| `status` | Lifecycle state of the instance. |

Additional keys (trailer token, measured golden scores, verification notes,
caveats) are permitted. A key whose value is genuinely unknown is written as
`null` with a trailing comment explaining the absence — never as an empty
string.

The two digests are recomputed by the validator against the shipped files, so a
`TRUTH.md` cannot survive its solution being edited underneath it.

### §15.6 Agreement with `tests/`

The prose must not contradict the grader. Specifically:

- The Channel A positive weight total stated in `## Verification` must equal the
  sum of the positive weights in `tests/test_weights.json`.
- Every negative test in `tests/test_weights.json` must be named somewhere in
  the document.

Counts and weights are **generated from** `tests/test_weights.json` and
`tests/rubric.json` at scaffold time rather than typed by hand, which is what
keeps this agreement true by construction.

### §15.7 Generation

`TRUTH.md` is authored once per archetype at
`templates/<archetype>/solution/TRUTH.md`
and rendered in two passes:

1. `scaffold_bundle()` applies the ordinary `{{...}}` substitutions while
   walking the template tree, exactly as for `instruction.md`.
2. `_write_truth_md()` runs after the bundle is fully written and resolves the
   `{{TRUTH_*}}` tokens by reading the *generated* `task.toml`,
   `environment/data/`, `solution/`, `tests/test_weights.json` and
   `tests/rubric.json`.

The second pass is why §15.6 holds: those facts are read back out of the bundle
that was just written.

Second-pass token vocabulary:

```
{{TRUTH_SOLVE_SH_SHA256}}      {{TRUTH_SOLVE_PY_SHA256}}    {{TRUTH_SOLVE_PY_LINES}}
{{TRUTH_ARTIFACT_COUNT}}       {{TRUTH_ARTIFACT_LIST}}
{{TRUTH_DATA_FILE_COUNT}}      {{TRUTH_DATA_FILE_LIST}}
{{TRUTH_TEST_COUNT}}           {{TRUTH_POSITIVE_COUNT}}     {{TRUTH_NEGATIVE_COUNT}}
{{TRUTH_POSITIVE_TOTAL}}       {{TRUTH_NEGATIVE_TOTAL}}
{{TRUTH_REWARD_FLOOR}}         {{TRUTH_REWARD_RANGE}}       {{TRUTH_CHANNEL_A_SUMMARY}}
{{TRUTH_POSITIVE_TEST_LIST}}   {{TRUTH_NEGATIVE_TEST_LIST}}
{{TRUTH_RUBRIC_COUNT}}         {{TRUTH_RUBRIC_POSITIVE_COUNT}}
{{TRUTH_RUBRIC_NEGATIVE_COUNT}} {{TRUTH_RUBRIC_POSITIVE_TOTAL}}
{{TRUTH_RUBRIC_NEGATIVE_TOTAL}} {{TRUTH_RUBRIC_SUMMARY}}    {{TRUTH_RUBRIC_LIST}}
{{TRUTH_PROVENANCE_BLOCK}}
```

Generation fails non-zero rather than degrading silently when an archetype ships
no `TRUTH.md` template, or when any `{{...}}` token survives both passes.

### §15.8 Authoring a new archetype's TRUTH.md

A new archetype under `templates/` must ship a `solution/TRUTH.md` or
`generate_bundle.py`
aborts. Copy the nearest existing one and rewrite the prose against that
archetype's real `instruction.md`, `solution/solve.py`, `tests/test_output.py`
and `tests/rubric.json`. Two mechanical rules:

- Multi-line tokens (`{{TRUTH_ARTIFACT_LIST}}`, `{{TRUTH_POSITIVE_TEST_LIST}}`,
  `{{TRUTH_NEGATIVE_TEST_LIST}}`, `{{TRUTH_RUBRIC_LIST}}`,
  `{{TRUTH_PROVENANCE_BLOCK}}`) must sit at column 0 with a blank line above and
  below. Nesting one inside a list item produces broken Markdown.
- Grammar tokens (`{{MAGIC_ASCII}}`, `{{MAGIC_HEX}}`, `{{VERSION_NUM}}`,
  `{{GRAMMAR_*}}`, `{{FORMAT_EXT}}`, `{{CONTAINER_NOUN}}`,
  `{{PRODUCER_SYSTEM}}`) are populated only for `format-recovery`. Using them
  elsewhere emits empty or non-instance-specific text.

Nothing in `TRUTH.md` may contain a residual marker (`TODO`, `FIXME`, `XXX`,
`PLACEHOLDER`, `<TAG>`, or an unresolved `{{...}}`) — §1 scans every file in the
bundle for these.
