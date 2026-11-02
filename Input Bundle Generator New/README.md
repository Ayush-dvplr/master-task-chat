# Input Bundle Generator

Tooling for authoring Harbor-runnable **input bundles** (agentic terminal-task
directories) that conform to a single canonical format.

An **input bundle** is one self-contained task directory that Harbor can drive
end-to-end:

```
harbor run --path /path/to/<bundle-name> --agent oracle --env docker
```

This folder ships:

| File | What it is |
|------|------------|
| `FORMAT_SPEC.md` | The authoritative format spec. Every bundle must match it. |
| `CHEAT_VECTORS.md` | Matrix of known agent cheats and the concrete mitigation the format requires. |
| `AUDIT_NOTES.md` | Where this format sits relative to the upstream `README (2).md` guide and Harbor's binary-reward memo. |
| `ARCHETYPE_SELECTION.md` | How the generator auto-selects an archetype per domain (`auto`/`random`/explicit) so bundles vary in shape. |
| `generate_bundle.py` | Scaffolds a seeded bundle from a selected archetype and its manifest. |
| `validate_bundle.py` | Lints an existing bundle against `FORMAT_SPEC.md`. Zero-warning pass is required before a bundle ships. |
| `templates/` | Per-archetype template trees. Each contains `archetype.toml`, instructions, environment data, oracle, tests, and judge criteria. |

The generator currently provides eight independent archetypes:

- `format-recovery`: infer a seed-generated binary grammar and implement a
  decoder plus byte-exact encoder.
- `build-repair`: repair a broken Python source project and deliver a verified
  source archive plus self-test report.
- `repo-patch`: repair a local source repository and deliver a patched archive.
- `data-pipeline`: implement a reusable deterministic transform over flat data.
- `cli-config`: repair a local command-line configuration workflow.
- `service-interaction`: operate a local service through both CLI and HTTP APIs.
- `performance`: preserve exact behavior while meeting a relative speed target.
- `domain-calculation`: derive an exact domain report from structured records.

When `--archetype` is omitted the generator **auto-selects** a
domain-appropriate archetype at random (deterministic per `seed`+`category`), so
a batch of bundles varies in shape rather than repeating one task type. See
[`ARCHETYPE_SELECTION.md`](ARCHETYPE_SELECTION.md) for the domain→archetype
affinity map and the `auto` / `random` / explicit modes.

---

## Why this exists

Harbor tasks look simple on the surface (`instruction.md`, `task.toml`,
`environment/`, `solution/`, `tests/`) but the details that make a task
train-able, grade-able and cheat-resistant are not surface-level. They are
scattered across:

- The **`README (2).md`** authoring guide (agent visibility rules, prose
  fields, Dockerfile rules).
- The `qtm-format-recovery` bundle (weighted rubric, negative tests, hidden
  eval seed).
- The `telemetry-codec-recovery` bundle (bidirectional recovery, separate
  verifier mode, refined explanations).
- The **`harbor-binary-reward.md`** memo (why binary 0/1 rewards break training
  and how fractional rewards recover the signal).

This folder is the union of those constraints, expressed in one place, with
tooling to keep new bundles in line.

---

## Quick start

### Author a new bundle

```bash
cd "/path/to/Terminal_2.0_Harbor_Harness/Input Bundle Generator"

# Scaffold a bundle. With --archetype omitted the generator auto-selects a
# domain-appropriate archetype at random (see ARCHETYPE_SELECTION.md), so a
# corpus of bundles varies in shape instead of always being format-recovery:
python3 generate_bundle.py \
    --out ../Tasks_INPUT/ \
    --category file-operations \
    --seed 4058222581
# -> [generate_bundle] archetype: data-pipeline (auto)

# Pin a specific archetype instead (deterministic, old behavior):
python3 generate_bundle.py \
    --out ../Tasks_INPUT/ \
    --archetype format-recovery \
    --category file-operations \
    --seed 4058222581 \
    --name my-new-task

# --author is required and repeatable: "Full Name <name@ethara.ai>" (QC FC-S18):
python3 generate_bundle.py \
    --out ../Tasks_INPUT/ \
    --archetype format-recovery \
    --category file-operations \
    --seed 4058222581 \
    --name my-new-task \
    --author "Ram Lakhan <ram.lakhan@ethara.ai>"

# Lint: runs the generator's own checks plus the four Input_Bundle_QC scripts:
python3 validate_bundle.py ../Tasks_INPUT/my-new-task/

# Step 10 (Final_checklist.md): build the tests-only copies, then run harbor 0.24 on them.
python3 ../Input_Bundle_QC/exe_copy.py ../Tasks_INPUT/my-new-task/ /tmp/step10run
python3 ../Input_Bundle_QC/exe_copy.py ../Tasks_INPUT/my-new-task/ /tmp/stubrun --stub
python3 ../Input_Bundle_QC/exe_copy.py ../Tasks_INPUT/my-new-task/ /tmp/ownerrun --owner-only
harbor run --path /tmp/step10run --agent oracle --env docker -y   # five times, exactly 1.000 each
harbor run --path /tmp/step10run --agent nop    --env docker -y   # exactly 0.000
harbor run --path /tmp/ownerrun  --agent oracle --env docker -y   # exactly 1.000 at mode 0600
harbor run --path /tmp/stubrun   --agent oracle --env docker -y   # judge the score
```

The contract is `Input_Bundle_QC/Final_checklist.md`; where this README or
`FORMAT_SPEC.md` disagree with it, the checklist wins. A bundle is ready for the
model gates when `validate_bundle.py` reports no FAIL, the five tests-only oracle
runs read exactly `1.000`, nop reads exactly `0.000`, and the owner-only run
reads exactly `1.000` as well.

The owner-only run matters because `solve.sh` installs its program with `cp`
(mode 0644) while a real agent writes it through an editor that renames a temp
file into place (mode 0600, uid 1000). Harbor preserves those modes, so a check
that runs the program under `setpriv --reuid=nobody` cannot read it and fails on
a correct submission while the plain oracle still reads 1.000. Every template
grants read on the arguments it is about to hand to the unprivileged child, from
inside `_untrusted_command`; keep that helper if you edit a template's checks
(QC rule TS-30, tests_qc H6).

### What every scaffold emits and checks

- `tests/` holds exactly `Dockerfile`, `test.sh`, `test_output.py`, `judge.toml`,
  `reward.toml`. `test_output.py` registers rewardkit `@criterion` checks with
  `criteria.<name>(weight=W)`; `judge.toml` carries the pinned `[judge]` header,
  including `atif-trajectory = "/logs/agent/trajectory.json"`, and at least 8
  `[[criterion]]` tables, each with a `[criterion.annotations]` table of
  exactly `mode`, `type` (the criterion's category), `evaluation_target` and
  `importance` (QC J6/J7).
- `tests/reward.toml` is computed at scaffold time: each channel weighs
  `0.5 / its positive total`. The generator refuses to write a bundle whose
  `judge.toml` header drifts or whose weights in either channel leave the locked
  `{5,3,1,-1,-3,-5}` scale, lack a positive or a negative, or let negatives
  outweigh positives.
- The agent's input lives in one or more input directories next to
  `environment/Dockerfile`, named for what they hold. Each archetype declares them in
  `archetype.toml`, and each must be copied by the Dockerfile to its mount (QC S3/S4):

  ```toml
  datagen_input = "ci"          # where datagen.py writes; default: the first input

  [[inputs]]
  dir = "repo"                  # environment/repo/  -> COPY --chown=1000:1000 repo /app/repo
  mount = "/app/repo"

  [[inputs]]
  dir = "ci"                    # environment/ci/    -> COPY ci /app/ci
  mount = "/app/ci"
  ```

  Without `[[inputs]]` the archetype gets the single `data` -> `/app/data`. The
  generator refuses a bundle whose `environment/` holds anything else, an empty input
  directory, or a missing/mismatched COPY. repo-patch ships `repo/` + `ci/`,
  service-interaction `service/` + `data/`; the others use `data/`.
- Checks that recompute expectations from the shipped input read an embedded copy of
  it, because the verifier container has no input directory: `{{SHIPPED_DATA}}` in
  `test_output.py` becomes the `datagen_input` directory and `{{SHIPPED:<dir>}}` any
  other declared input.
- `environment/Dockerfile` gives uid 1000 ownership of `/app`, because
  `[agent] user = "1000:1000"` runs the agent and the oracle as that uid.
  It also creates that uid 1000 `agent` account with `HOME=/home/agent` (QC S10) and
  pre-bakes the openhands-sdk runtime at `/opt/openhands-sdk-venv`
  (`openhands-sdk`/`openhands-tools` 1.55.1, `litellm` 1.105.0, `fastapi`, plus `tmux`;
  QC S9), so a no-network run can start the agent. The image build takes a few
  minutes longer because of it.
- `tests/judge.toml`'s `[judge]` header is exactly `judge`, `mode`, `timeout`,
  `atif-trajectory`, `weight`; the generator refuses any extra key (QC G2).

- Each archetype's `datagen.py` (never copied into a bundle) writes the seeded input
  files after the templates are copied: tens of thousands of lines across files that
  depend on one another, so no file can be skipped. Embedded data is zlib-compressed.
- `tests/Dockerfile` sets `ENV LITELLM_LOCAL_MODEL_COST_MAP=True` (QC K7); without it
  rewardkit can deadlock at shutdown when the verifier cannot reach GitHub.

### Lint an existing bundle

```bash
python3 validate_bundle.py ../Tasks_INPUT/archive-index-recovery/
```

Exit code `0` means every rule in `FORMAT_SPEC.md` passes. Any non-zero exit
means at least one rule failed; the failing rule is printed with its
`FORMAT_SPEC.md` section reference.

---

## Where things live

```
Input Bundle Generator/
├── README.md
├── FORMAT_SPEC.md
├── CHEAT_VECTORS.md
├── AUDIT_NOTES.md
├── ARCHETYPE_SELECTION.md
├── CATEGORIES.md
├── generate_bundle.py
├── validate_bundle.py
└── templates/
    ├── format-recovery/
    │   ├── archetype.toml
    │   ├── instruction.md
    │   ├── environment/
    │   ├── solution/             includes TRUTH.md; mandatory for every archetype
    │   └── tests/
    ├── build-repair/
        ├── archetype.toml
        ├── instruction.md
        ├── environment/
        ├── solution/              includes TRUTH.md
    │   └── tests/
    └── <additional-archetype>/
        ├── archetype.toml
        ├── instruction.md
        ├── environment/
        ├── solution/              includes TRUTH.md
        └── tests/
```

---

## What a compliant bundle looks like

Full directory shape (every entry is mandatory unless noted `optional`):

```
<bundle-name>/
├── instruction.md              agent-visible task description
├── task.toml                   schema 1.4, the pinned Final_checklist.md template
├── environment/
│   ├── Dockerfile              agent image (digest-pinned public.ecr.aws base, /app owned by uid 1000)
│   └── data/                   archetype input data; no hidden answers
├── solution/
│   ├── solve.sh                oracle dispatcher (chmod +x)
│   ├── solve.py                oracle reference implementation
│   └── TRUTH.md                author-side golden trajectory: the derivation that answers instruction.md
└── tests/
    ├── Dockerfile              verifier image: python:3.12-slim + harbor-rewardkit==0.2.1 litellm==1.105.0
    ├── test.sh                 hardens the verifier, then exec rewardkit; writes no reward itself
    ├── test_output.py          rewardkit @criterion checks + criteria.<name>(weight=W) registrations
    ├── judge.toml              LLM-judged criteria, pinned [judge] header incl. atif-trajectory
    └── reward.toml             0.5 / positive total per channel, generated at scaffold time
```

See `FORMAT_SPEC.md` for the exact contents required in each file.

---

## TRUTH.md — the golden trajectory

Every generated bundle carries a `solution/TRUTH.md`. It is the author-side
companion to `instruction.md`: where `instruction.md` states the task an agent is
given, `TRUTH.md` records the golden trajectory that answers it — what is actually
broken, which deliverables are load-bearing, how the grader scores the work, the
root cause behind the defects, the shape of the reference solution, the ordered
plan a competent solver should follow, and the pitfalls that sink naive attempts.

`TRUTH.md` is **not** shipped to the agent. It is review material: it lets a human
verify that the task is solvable, that the tests grade what the instruction asks
for, and that the reward surface has no shortcut.

### Required sections, in this exact order

| Section | Contents |
|---|---|
| `## Defect` | Prose framing, then a numbered list where each item is labelled `(focal)`, `(drift)` or `(trap)`; then the reference-authoring paragraph; then an `Out of bounds:` paragraph. |
| `## Load-bearing work` | The graded artifact list plus a per-deliverable content contract. |
| `## Verification` | How `tests/test.sh` scores the run, the Channel A weight totals, the positive and negative test lists, and the Channel B rubric. |
| `## Root cause` | Bolded sub-topics explaining the invariants the defects violate. |
| `## Solution shape` | The reference implementation's steps, numbered. |
| `## Ordered plan` | The agent's golden path, numbered, tied to rubric criteria. |
| `## Pitfalls` | Bulleted wrong instincts, each naming the test it fails. |
| `## Provenance` | A fenced `yaml` block with instance identity and solution digests. |

Defect items are classified so a reviewer can see the difficulty budget at a glance:

- **`(focal)`** — a defect the task is genuinely about. Fixing it is the work.
- **`(drift)`** — an experienced instinct that contradicts the spec. The solver has
  to notice that the obvious "improvement" breaks a stated contract.
- **`(trap)`** — a defect that stays invisible on the happy path and only surfaces
  under the grader's edge cases.

`validate_bundle.py` requires at least two `(focal)` items and at least one each of
`(drift)` and `(trap)`.

### How it is generated

`TRUTH.md` is authored once per archetype at
`templates/<archetype>/solution/TRUTH.md` and
rendered in two passes:

1. **First pass** — `scaffold_bundle()` walks the template tree and applies the
   normal `{{...}}` substitutions (`{{BUNDLE_NAME}}`, `{{SEED_HEX}}`,
   `{{EVAL_SEED}}`, and the rest), exactly as it does for `instruction.md`.
2. **Second pass** — `_write_truth_md()` runs after the whole bundle exists on
   disk and resolves the `{{TRUTH_*}}` tokens, which are *derived from the
   generated files themselves* rather than from CLI arguments.

The second pass is what keeps `TRUTH.md` honest: the weight totals, test names,
rubric criteria, artifact list and solution digests it states are read back out of
the bundle that was just written, so they cannot drift away from the files they
describe.

| Token | Source |
|---|---|
| `{{TRUTH_SOLVE_SH_SHA256}}` / `{{TRUTH_SOLVE_PY_SHA256}}` | sha256 of the generated `solution/solve.sh` / `solve.py` |
| `{{TRUTH_SOLVE_PY_LINES}}` | line count of the generated `solution/solve.py` |
| `{{TRUTH_ARTIFACT_COUNT}}` / `{{TRUTH_ARTIFACT_LIST}}` | `[task] artifacts` in the generated `task.toml` |
| `{{TRUTH_DATA_FILE_COUNT}}` / `{{TRUTH_DATA_FILE_LIST}}` | every file of every input directory, at its image path |
| `{{TRUTH_TEST_COUNT}}`, `{{TRUTH_POSITIVE_COUNT}}`, `{{TRUTH_NEGATIVE_COUNT}}` | `criteria.<name>(weight=W)` in `tests/test_output.py` |
| `{{TRUTH_POSITIVE_TOTAL}}`, `{{TRUTH_NEGATIVE_TOTAL}}` | signed weight sums from the `tests/test_output.py` registrations |
| `{{TRUTH_REWARD_FLOOR}}`, `{{TRUTH_REWARD_RANGE}}` | derived from those two totals |
| `{{TRUTH_CHANNEL_A_SUMMARY}}` | one-line summary of the Channel A test split |
| `{{TRUTH_POSITIVE_TEST_LIST}}` / `{{TRUTH_NEGATIVE_TEST_LIST}}` | bulleted test names with their weights |
| `{{TRUTH_RUBRIC_*}}` | counts, totals and criteria text from `tests/judge.toml` |
| `{{TRUTH_PROVENANCE_BLOCK}}` | the whole fenced `yaml` provenance block |

Generation fails loudly rather than silently degrading: if an archetype has no
`TRUTH.md` template, or if any `{{...}}` token survives both passes,
`generate_bundle.py` exits non-zero.

### Adding TRUTH.md to a new archetype

A new archetype under `templates/` **must** ship a `solution/TRUTH.md` or generation will
abort. Copy the closest existing one as a skeleton, then rewrite the prose against
that archetype's real `instruction.md`, `solution/solve.py`, `tests/test_output.py`
and `tests/judge.toml`. Two mechanical rules:

- Multi-line tokens (`{{TRUTH_ARTIFACT_LIST}}`, `{{TRUTH_POSITIVE_TEST_LIST}}`,
  `{{TRUTH_RUBRIC_LIST}}`, `{{TRUTH_PROVENANCE_BLOCK}}`) must sit at column 0 with
  a blank line above and below. Nesting one inside a list item produces broken
  Markdown.
- Only use grammar tokens (`{{MAGIC_ASCII}}`, `{{GRAMMAR_*}}`, `{{FORMAT_EXT}}`,
  `{{CONTAINER_NOUN}}`, `{{PRODUCER_SYSTEM}}`) in `format-recovery`. They are not
  populated for the other archetypes.

`validate_bundle.py` enforces the result under section `§12`.
