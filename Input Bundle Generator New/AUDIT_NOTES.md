# Audit Notes

> **Superseded for Harbor 0.24.** The bundle contract is now
> `Input_Bundle_QC/Final_checklist.md`: schema 1.4 task.toml, rewardkit test channel
> (`criteria.<name>(weight=W)` in `tests/test_output.py`, no `test_weights.json`),
> `tests/judge.toml` instead of `rubric.json`, a generated `tests/reward.toml`, and
> no `README.md` in the bundle. Where this document says otherwise, the checklist wins.

Reasoning trail from the three source documents to this format.

## Sources

- `../README (2).md` — the *Agentic Terminal Task Authoring Guide*.
- `../harbor-binary-reward.md` — Harbor's memo on why binary 0/1 rewards
  destroy training signal.
- `../harness/Tasks_INPUT/qtm-format-recovery/` and
  `../harness/Tasks_INPUT/telemetry-codec-recovery/` — the two in-repo
  bundles that already work end-to-end under `harbor run`.

## Prior audit of `qtm-format-recovery` against the guide

An earlier audit compared `qtm-format-recovery` line-for-line against
`README (2).md` and found three literal violations and one deliberate
design divergence:

- **V1**: `tests/Dockerfile` exists → the guide (line 17) forbids a separate
  verifier image.
- **V2**: `task.toml` was missing the guide-required prose fields
  (`difficulty_explanation`, `solution_explanation`,
  `verification_explanation`, `task_objective`, `artifact_type`,
  `expert_time_estimate_hours`). The prose was in the task-level
  `README.md` instead.
- **V3**: `environment/Dockerfile FROM python:3.12-slim` uses Docker Hub
  (not `public.ecr.aws/docker/library/`) and no `@sha256` digest pin.
- **D1** (resolved): early bundles placed 24 decoded answer files under
  `environment/data/`. Current bundles ship capture bytes only; compact worked
  examples live in §9 of the format draft and verifier ground truth is rebuilt
  from private seeds.

## How this format resolves each finding

- **V1 → format uses `environment_mode = "separate"` deliberately.** The
  audit initially framed this as a violation of guide line 17. On
  re-inspection, separate-mode is a strictly stronger guarantee because
  it keeps `EVAL_SEED` — and the `_write_corpus()` function that
  produces the eval bytes — inside the verifier image, which the agent
  never enters. A shared image cannot achieve this: `find /
  -name test_output.py` would surface it. The format therefore treats
  `environment_mode = "separate"` as **required**, not merely allowed.
  See CHEAT_VECTORS.md §5.
- **V2 → format's `task.toml` carries both schemas.** Every guide-required
  prose field appears at TOML root; every Harbor native field appears
  under `[task]`, `[metadata]`, `[verifier]`, `[agent]`, `[environment]`.
  `validate_bundle.py` enforces both sets. See FORMAT_SPEC.md §3.
- **V3 → format's Dockerfiles are digest-pinned.** Both
  `environment/Dockerfile` and `tests/Dockerfile` pin to
  `public.ecr.aws/docker/library/python:3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b`
  (resolved via `docker buildx imagetools inspect
  public.ecr.aws/docker/library/python:3.12-slim` on 2026-08-06). This
  makes the image reproducible across `docker pull` runs regardless of
  when a new upstream `slim` tag is published. See FORMAT_SPEC.md §5.1.
- **D1 → worked examples moved into the specification.** Agent-visible data
  contains sample and field captures but zero decoded answer files. Section §9
  teaches the generated delta and dictionary rules, while the verifier derives
  expected documents independently. See CHEAT_VECTORS.md §1.

## `harbor-binary-reward.md` alignment

The memo names three files that collapse Harbor's rewards to 0/1:

- `src/harbor/mappers/terminal_bench.py:37`
- `src/harbor/cli/template-task/pytest-tests/test.sh:19`
- `src/harbor/utils/pass_at_k.py:44`

The memo also names the remedy that requires no change to `main`:
Harbor's `--ctrf` flag already writes a full per-test breakdown to
`/logs/verifier/ctrf.json`. Post-processing that file recovers a
graded score.

This format applies the remedy directly:

- `test.sh` writes `reward.json` as a **fractional** score (via the
  weighted sum in FORMAT_SPEC.md §8), never as `0` or `1` unless
  every-or-no positive test passes.
- The same `test.sh` also writes `reward.txt` (parity with Harbor's
  binary-reward pathway) and `ctrf.json` (the memo's already-existing
  detail file, preserved rather than discarded).
- Training pipelines can read `reward.json` for the graded signal and
  fall back to `reward.txt` for compatibility with Harbor's original
  binary reader.

The memo's `pass_at_k.py:44` enforcer refuses scores that are not exactly
0 or 1. This format's tasks will therefore have `pass@k` silently drop out
of Harbor's headline stat — that is *expected* and *desired*, because
these tasks are for training signal, not leaderboard rank. Bundles that
also need a pass@k number should round `reward.json` to 0/1 at
post-processing time using a threshold appropriate to the task.

## Files influenced by these decisions

| Decision | File in the format |
|----------|-------------------|
| Separate verifier mode (structural)     | `templates/tests/Dockerfile`, `templates/environment/Dockerfile` (mutual isolation via non-overlapping `COPY` clauses) |
| Slim `task.toml` schema                 | `templates/task.toml`, `validate_bundle.py` |
| Digest-pinned base image                | `templates/environment/Dockerfile`, `templates/tests/Dockerfile`, `validate_bundle.py` |
| Two-tier corpus                         | `templates/tests/test_output.py` (SAMPLE/CHALLENGE/EVAL seeds), `FORMAT_SPEC.md` §9 |
| Fractional reward + CTRF preservation   | `templates/tests/test.sh` (verbatim from qtm+telemetry) |
| Negative-weight cheat tests             | `templates/tests/test_weights.json`, `templates/tests/test_output.py`, `validate_bundle.py` |

## v2 slim-schema refactor — 2026-08-10 (commit `26413d67`)

The v1 audit resolved V2 by adopting a dual-schema `task.toml` — guide-required
prose fields at root, Harbor native fields under `[task]/[metadata]/[verifier]/
[agent]/[environment]`. That decision was reversed in v2 to align with the
frontier-bench canonical shape (see `reference/frontier-bench/docs/task-template.toml`).

**Fields removed at TOML root in v2:**

- `task_objective`, `difficulty_explanation`, `solution_explanation`,
  `verification_explanation`, `artifact_type`, `expert_time_estimate_hours`,
  root-level `allow_internet`, root-level `timeout_sec`.

**Fields removed under `[verifier]`, then restored:**

- `environment_mode = "separate"` was dropped in `26413d67` and has since been
  **restored** as a required field — `validate_bundle.py` §3.4 now rejects any
  bundle whose value is not exactly `"separate"`. The *structural* separation
  via two Dockerfiles was never removed and still stands independently — see
  the table above and `CHEAT_VECTORS.md` §5.

**Environment policy change.** `[environment].allow_internet` is now
**forced to `true`** for every generated bundle. Harbor maps
`allow_internet = false` to `network_mode = "no-network"`, which Docker Desktop
on macOS rejects at trial construction (`network_mode='no-network' is not
supported by EnvironmentType.DOCKER`), yielding a zero-trial run. To guarantee
generated tasks always start, `generate_bundle.py` substitutes a literal `true`
into the `{{ALLOW_INTERNET}}` placeholder carried by `templates/task.toml`. Each
`archetype.toml` still declares an `allow_internet` value and the
`--allow-internet` / `--no-allow-internet` flag is still accepted, but both are
ignored — the emitted value is always `true`. The downstream QC gate
(`structure_qc.py` T14) accepts either boolean, and gates 01/02/05 (IN-12,
DS-12, AL-17) require the instruction, Dockerfile and solution to stay
consistent with the emitted value. (Earlier this field was blanket-hardcoded
`false`; it is now blanket-hardcoded `true`.)

**Rationale.** The upstream `docs/task-template.toml` in
`reference/frontier-bench/docs/` carries only Harbor-native fields. The guide-
required prose (difficulty / solution / verification explanations) is authored
as sibling README.md sections in real frontier-bench tasks (see `atrx-vep-crispr`
as ground truth). Duplicating them into TOML root added no verifier signal and
was the leading cause of drift between `task.toml` and `README.md`.

**Where the removed prose lives now.**

- `difficulty_explanation` → `README.md` §Difficulty explanation.
- `solution_explanation` → `README.md` §Solution explanation.
- `verification_explanation` → `README.md` §Verification explanation.
- `expert_time_estimate_hours` → `[metadata].expert_time_estimate_min`
  (still queryable; multiply by 60 to recover the guide unit).
- `allow_internet` → `[environment].allow_internet` only.
- `timeout_sec` → `[agent].timeout_sec` (and `[verifier].timeout_sec` for the
  verifier bound separately).

**Files influenced by the v2 refactor:**

| Decision | File in the format |
|----------|-------------------|
| Root-only slim shape                    | `templates/<archetype>/task.toml`, `validate_bundle.py` (§3.1-§3.5) |
| Title-Case category in emitted TOML     | `generate_bundle.py` `_build_substitutions()` uses `{{CATEGORY}} = cat["display"]` |
| Frontier-bench sidecar alignment        | `reference/frontier-bench/docs/task-template.toml` (canonical shape reference) |
| Structural verifier isolation           | each archetype's `tests/Dockerfile` and `environment/Dockerfile` |
| Integer-second instruction trailer      | each archetype's `instruction.md` uses `{{AGENT_TIMEOUT_SEC_INT}}` |
| Anti-cheat criteria                     | archetype-specific negative tests plus process-harm rubric criteria |

## Archetype auto-selection (anti-monotony)

**Finding.** With `--archetype` defaulting to `format-recovery`, every bundle
generated without an explicit override was the *same task shape*. A batch of
"different" bundles was really one archetype re-skinned, which is exactly the
sibling-similarity problem the QC F0a/AL-F0a rules warn about.

**Resolution.** When `--archetype` is omitted it now defaults to `auto`: the
generator picks a domain-appropriate archetype from a 16-row
`_DOMAIN_ARCHETYPE_AFFINITY` map, choosing randomly *within* that domain's
fitting set. `--archetype random` picks from all discovered archetypes;
`--archetype <name>` still pins one explicitly.

- Selection is deterministic per `(seed, category)` via a dedicated
  `blake2b(seed, salt="archetype:<category>")` RNG, so it is reproducible but
  varies as the seed varies — variety across a batch comes from varying seeds.
- The dedicated RNG is separate from the content RNG, so a pinned
  `--archetype X` bundle is byte-identical to pre-change output (no regression).
- Only `format-recovery` re-themes its *content* to the category; the other
  seven archetypes are domain-general, so the affinity map optimises framing
  fit and shape-variety rather than deep per-domain content theming.

See `ARCHETYPE_SELECTION.md` for the full affinity table and usage. Code:
`_DOMAIN_ARCHETYPE_AFFINITY`, `_select_archetype()`, and the `# 2b. Archetype
selection` block in `_resolve_args()` (`generate_bundle.py`).
