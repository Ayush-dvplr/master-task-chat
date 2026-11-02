# warrant-ctl

Compiles access profiles from a Warrant corpus directory.

```
python3 cli.py resolve-config --data DIR --out config.json
python3 cli.py compile --data DIR --config config.json --profile prod --out profile_prod.json
python3 cli.py audit --data DIR --config config.json --out validation_report.json
python3 cli.py summarize --data DIR --config config.json --out summary.json
```

Modules: `wtime.py` (instants and zones), `corpus.py` (raw loading), `ident.py` (reference normalization), `policy.py` (configuration layers), `engine.py` (evaluation), `audit.py` (report documents), `cli.py` (entry point).

Release 1.4. Maintainers: identity platform team.
