# Category Taxonomy

The generator accepts 16 CLI category keys and emits a corresponding exact
Title-Case display value in `task.toml`. Each key also retains an internal
Harbor / frontier-bench domain and subcategory from the taxonomy documented in
[frontier-bench/docs/TAXONOMY.md](https://github.com/harbor-framework/frontier-bench/blob/main/docs/TAXONOMY.md).

## Table: CLI category → emitted display value + internal taxonomy

| # | CLI key | emitted display | internal domain | subcategory | notes |
|---|---------|-----------------|-----------------|-------------|-------|
| 1 | software-engineering | Software Engineering | Software | Systems | closest match to the reference bundle |
| 2 | system-admin | System Administration | Software | Systems | ops-style narrative |
| 3 | data-science | Data Science | ML | Evaluation | tabular flavor |
| 4 | security | Security | Security | Reverse engineering | packet/blob narrative |
| 5 | scientific-computing | Scientific Computing | Science | Physics | numeric samples |
| 6 | file-operations | File Operations | Software | Systems | archive/index narrative |
| 7 | debugging | Debugging | Software | Systems | crash-dump narrative |
| 8 | data-processing | Data Processing | Software | Data engineering | ETL container flavor |
| 9 | model-training | Model Training | ML | Training | checkpoint blob flavor |
| 10 | mathematics | Mathematics | Science | Math | symbolic ordering |
| 11 | machine-learning | Machine Learning | ML | Inference | tensor packet flavor |
| 12 | games | Games | Software | Algorithms | save-file / replay flavor |
| 13 | video-processing | Video Processing | Media | Design | frame-packet flavor |
| 14 | data-querying | Data Querying | Software | Databases | index / catalog flavor |
| 15 | optimization | Optimization | Software | Algorithms | schedule blob flavor |
| 16 | personal-assistant | Personal Assistant | Operations | Marketing | reminder store flavor |

## Notes

* `validate_bundle.py` §3 accepts only the 16 emitted display values above.
* The internal domain/subcategory pair remains reviewer context and does not
  control the emitted category field.
* Task structure is selected independently with `--archetype`. The current
  archetypes are `format-recovery` and `build-repair`; each has its own
  instruction, environment data, oracle, tests, rubric, and artifacts.
* Within `format-recovery`, the CLI category customizes:
    * the invented format's `MAGIC` bytes (from a per-category pool),
    * the narrative framing of `instruction.md`,
    * the `[metadata].tags` list,
    * the `[task].description` and `[task].keywords`,
    * the narrative and category-scoped vocabulary.
* Randomness is deterministic for a fixed generator/runtime version: given the
  same `--seed`, category, archetype, and output-directory state, the generator
  produces the same output. Without `--seed`, it draws from
  `secrets.randbits(63)` and prints the chosen seed so an operator can
  reproduce the run.

## How to add a new category

1. Add a new row to the table above.
2. In `generate_bundle.py` add an entry to `_CATEGORIES` with:
    * `display` — one of the exact Title-Case values accepted downstream,
    * `canonical` — one of the 7 internal frontier-bench domains,
   * `subcategory` — a short human string,
   * `magic_pool` — 4-8 candidate `MAGIC` byte-string pools (5 ASCII bytes each),
    * `noun_pool`, `verb_pool`, and `producer_pool` — narrative vocabulary,
   * `keyword_pool` — 8+ keyword tokens that get sampled per generation,
    * `tag_prefix_pool` — 3+ ASCII short prefixes used to synthesize the `--format-tag`.
3. The parser derives its `--category` choices directly from `_CATEGORIES`.
4. Re-run the end-to-end verification (`generate_bundle.py --random --seed N` for N in a small set) and confirm each produces a bundle that passes `validate_bundle.py` and (`test.sh` → `reward == 1.0` when the reference `solve.py` is installed).
