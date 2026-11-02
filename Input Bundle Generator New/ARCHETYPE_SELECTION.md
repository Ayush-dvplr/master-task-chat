# Archetype Selection

How `generate_bundle.py` decides **which archetype** a bundle uses, and how to
control it. The goal is variety: across many generated bundles you should get a
healthy mix of task shapes, not the same archetype every time.

## The problem this solves

Every bundle is scaffolded from one of eight archetypes:

| Archetype | Task shape |
|-----------|------------|
| `format-recovery` | Infer a seed-generated binary grammar; write a decoder + byte-exact encoder. |
| `build-repair` | Repair a broken Python project; deliver a verified source archive + self-test. |
| `repo-patch` | Repair a local source repository; deliver a patched archive. |
| `data-pipeline` | Implement a reusable deterministic transform over flat data. |
| `cli-config` | Repair a local command-line configuration workflow. |
| `service-interaction` | Operate a local service through both CLI and HTTP APIs. |
| `performance` | Preserve exact behavior while meeting a relative speed target. |
| `domain-calculation` | Derive an exact domain report from structured records. |

Historically `--archetype` defaulted to `format-recovery`, so unless the author
overrode it, **every** bundle came out as a format-recovery codec task. That
produces a monotonous corpus: an agent that solves one bundle has effectively
solved them all, and the training signal of N bundles collapses toward the
signal of one.

## The three selection modes

`--archetype` now accepts one of:

| Value | Behavior |
|-------|----------|
| `auto` *(default)* | Pick a **domain-appropriate** archetype at random from the category's affinity list (see table below). |
| `random` | Pick **any** of the eight archetypes at random, ignoring domain affinity. |
| an explicit name (e.g. `format-recovery`) | Use exactly that archetype. No randomness. |

When a bundle's archetype is auto-selected, the generator prints it so the
choice is never silent:

```
[generate_bundle] archetype: service-interaction (auto)
```

An explicitly requested archetype prints without the `(auto)` suffix.

## Domain → archetype affinity

In `auto` mode the archetype is drawn from the category's affinity list. Each
list is a curated subset of archetypes that make sense for that domain, so the
selected archetype is always a plausible fit for the declared
`[metadata].category` — while still varying from bundle to bundle.

| Category (`--category`) | Candidate archetypes (auto mode) |
|-------------------------|----------------------------------|
| `software-engineering` | repo-patch, build-repair, cli-config, performance |
| `system-admin` | cli-config, service-interaction, build-repair, data-pipeline |
| `data-science` | data-pipeline, domain-calculation, performance, format-recovery |
| `security` | format-recovery, repo-patch, cli-config, service-interaction |
| `scientific-computing` | domain-calculation, performance, data-pipeline, format-recovery |
| `file-operations` | format-recovery, data-pipeline, cli-config, build-repair |
| `debugging` | repo-patch, build-repair, performance, format-recovery |
| `data-processing` | data-pipeline, domain-calculation, performance, format-recovery |
| `model-training` | performance, data-pipeline, build-repair, service-interaction |
| `mathematics` | domain-calculation, performance, format-recovery, repo-patch |
| `machine-learning` | performance, service-interaction, data-pipeline, domain-calculation |
| `games` | format-recovery, performance, data-pipeline, service-interaction |
| `video-processing` | format-recovery, performance, data-pipeline, build-repair |
| `data-querying` | domain-calculation, data-pipeline, performance, format-recovery |
| `optimization` | performance, domain-calculation, repo-patch, cli-config |
| `personal-assistant` | cli-config, service-interaction, data-pipeline, format-recovery |

Across the sixteen categories every archetype appears in several lists, so an
author who cycles through categories and seeds gets broad archetype coverage.

> **Note on theming.** Only `format-recovery` re-themes its generated *content*
> to the category (via per-category magic bytes, nouns and producer names). The
> other seven archetypes ship domain-general task content; for them `--category`
> sets the `[metadata].category` label and, where present, the
> `{{CONTAINER_NOUN}}` / `{{PRODUCER_SYSTEM}}` flavor nouns. The affinity table
> therefore optimizes for *framing plausibility + variety*, not deep per-domain
> content specialization.

## Reproducibility

Selection is **deterministic for a given `(seed, category)`** and is computed
from a *dedicated* derived RNG (`blake2b(seed, salt="archetype:<category>")`).
Two consequences:

1. **Reproducible** — regenerating with the same `--seed` and `--category`
   yields the same archetype every time.
2. **Content-safe** — the selection RNG is independent of the content RNG, so a
   bundle scaffolded with an *explicit* `--archetype` is byte-for-byte identical
   to what the old generator produced. Only the *default* behavior changed.

Variety therefore comes from **varying the seed** (or using `--random` for a
fresh seed). Because the salt includes the category, different categories
decorrelate cleanly and no archetype is starved.

## Usage examples

```bash
# Default: domain-appropriate auto-selection.
python3 generate_bundle.py --out ../Tasks_INPUT/ --category games --seed 20260811
# -> [generate_bundle] archetype: performance (auto)

# Force pure-random across all eight archetypes.
python3 generate_bundle.py --out ../Tasks_INPUT/ --category games --seed 6 --archetype random

# Pin an exact archetype (no randomness; old behavior).
python3 generate_bundle.py --out ../Tasks_INPUT/ --category games --seed 20260811 \
    --archetype format-recovery --name save-state-recovery
```

When `--name` is omitted, an auto/random bundle is named after the archetype it
resolved to (`<archetype>-01`, `<archetype>-02`, ...), so the directory name
reflects the actual task shape.

## Where this lives in code

- `_DOMAIN_ARCHETYPE_AFFINITY` — the category → archetype-list map.
- `_select_archetype(category, seed, mode)` — resolves `auto` / `random` to a
  concrete archetype using the dedicated derived RNG.
- `_resolve_args()` — resolves `--archetype auto|random` before the manifest is
  loaded and records whether the choice was auto-selected.

To change a domain's candidate set, edit `_DOMAIN_ARCHETYPE_AFFINITY` and keep
this table in sync.
