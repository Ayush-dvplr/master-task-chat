# Command line contract

The compiler is `warrant-ctl`, run as `python3 cli.py` from its extracted archive. It uses the Python standard library only and makes no network call.

| Subcommand | Arguments | Writes |
|---|---|---|
| `resolve-config` | `--data DIR --out FILE` | the configuration |
| `compile` | `--data DIR --config FILE --profile dev\|prod --out FILE` | one profile |
| `audit` | `--data DIR --config FILE --out FILE` | the validation report |
| `summarize` | `--data DIR --config FILE --out FILE` | the summary |

`--data` is a directory laid out as `corpus_index.md` describes; the compiler reads every input from it and from nowhere else. Every setting except the file layout comes from the `--config` file, anchors included, so a configuration resolved from one corpus can be passed back with that corpus. The compiler writes only the `--out` file and never modifies anything under `--data`.

The compiler exits 0 after writing its output. When any file listed in `corpus_manifest.json` is missing, or any other failure stops it, it exits non-zero and writes no output file. Running the same subcommand twice on the same inputs produces byte-identical output, whatever the order of rows inside the input files.
