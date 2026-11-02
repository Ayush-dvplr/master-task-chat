# Vendored Reference Material

This directory holds a byte-exact copy of the parts of the
[frontier-bench](https://github.com/harbor-framework/frontier-bench) repository
that the Input Bundle Generator (IBG) uses to calibrate the **complexity** of
the tasks it produces. These files are **NOT** copied into the bundles the
generator emits — the shape of a generated bundle is unchanged. They live here
so that:

1. Template authors editing an archetype's `instruction.md`,
   `tests/rubric.json`, or environment data can consult the exact quality bar
   their output must clear.
2. `validate_bundle.py` and any future rubric-review harness has an in-repo
   ground truth to lint against without a network fetch.
3. The generator's own choice of category, difficulty framing, and
   anti-cheat wording stays consistent with the benchmark the produced tasks
   ultimately target.

## File map

### `frontier-bench/docs/`

| File | Size | Role in IBG |
|---|---|---|
| `task-template.toml` | 1.5K | Canonical `task.toml` shape published by `harbor tasks init --metadata-template`. Each IBG archetype's `task.toml` intentionally uses the same slim field set. Consult this file when the operator asks for an emitted TOML change. |
| `TAXONOMY.md` | 5.0K | The 7-domain × ~40-subdomain frontier-bench taxonomy. **IBG does NOT enforce this taxonomy directly.** The closed generator vocabulary is the 16 Title-Case display values documented in `../../CATEGORIES.md`; the frontier-bench domain/subcategory remains internal reviewer context. |
| `REVIEWING.md` | 9.2K | The manual review order (instruction → tests → solution → environment → task.toml) and the `/review` `/validate` `/run` `/cheat` `/fortify` slash-command pipeline. Use this when tuning the FILE ORDER checks in `validate_bundle.py` and when explaining the review gauntlet to a bundle author. |
| `TASK_REVIEW_AUTOMATION.md` | 36K | Deep dive on the automated review pipeline (what each `/`-command actually runs, artifact layout, expected outputs). Consult when the operator needs to reproduce a specific pipeline stage offline. |
| `spacer.svg` | 77B | Vertical spacer used in the frontier-bench docs; kept here so nothing in `docs/` is missing. Not consumed by IBG. |

### `frontier-bench/rubrics/`

| File | Size | Role in IBG |
|---|---|---|
| `task-proposal.md` | 16K | Phase-1 LLM-judge rubric (6 criteria: Verifiable, Well-specified, Solvable, Difficult, Interesting, Outcome-verified) with reject-examples. **Use this to sanity-check a generated bundle's `instruction.md` and category framing before committing.** If a generated task would score `Reject` on this rubric, the generator's inputs need tightening. |
| `task-implementation.toml` | 59K | Phase-2 LLM-judge rubric (35 criteria). This is the primary reference for every archetype's `tests/rubric.json`; output-state requirements belong in tests while trajectory/process harms belong in the rubric. |
| `hack-trial-prompt.md` | 2.8K | Adversarial red-team prompt used by `/cheat`. Use its attack surface when designing archetype-specific negative tests and process-harm rubric criteria. |
| `trial-analysis.toml` | 5.6K | Post-run 6-criterion failure-mode analysis (`task_specification`, `reward_hacking`, `difficulty_crux`, `near_miss`, `refusals`, `low_timeout`). Consult when you have real agent-trial JSON from a generated bundle and want to know which spec sections + which cheat-vector penalties actually got exercised. |
| `trial-analysis-job.txt` | 1.5K | Aggregation template used by `harbor analyze` to roll trial-level scores up to job-level. Not consumed directly by IBG. |

### `frontier-bench/CONTRIBUTING.md`

Size: 24K. Lists the 6 official "difficulty strategies" (long-horizon, richer environments, dynamic environments, new domains, cross-domain, iterative) plus the "inspiration domains" reading list. **When adding a new archetype, this is the primary source of truth for what a hard task looks like.**

## What the vendored files do **not** cover

- **`checks/*.sh`** and **`checks/rubric_review.py`** from frontier-bench are NOT vendored. They belong in a CI-runner context, not in a generator. If you need to lint a produced bundle against them, run frontier-bench's CI locally: `cd frontier-bench && ./checks/check-task-fields.sh path/to/bundle`.
- **Individual task directories under `frontier-bench/tasks/`** are NOT vendored — they are exemplars, not templates. Reference a specific real bundle (e.g. `frontier-bench/tasks/atrx-vep-crispr/`) directly when doing per-family calibration.

## Sync

The vendored files are pinned. If frontier-bench is updated, re-sync by running:

```bash
FB="/absolute/path/to/frontier-bench"
IBG="$(git rev-parse --show-toplevel)/Input Bundle Generator Old"
rm -rf "$IBG/reference/frontier-bench/docs" "$IBG/reference/frontier-bench/rubrics" "$IBG/reference/frontier-bench/CONTRIBUTING.md"
cp -R "$FB/docs" "$IBG/reference/frontier-bench/docs"
cp -R "$FB/rubrics" "$IBG/reference/frontier-bench/rubrics"
cp "$FB/CONTRIBUTING.md" "$IBG/reference/frontier-bench/CONTRIBUTING.md"
```

Then re-run the end-to-end generator + validator pass to confirm no template edits are needed.
