# dpcc

`dpcc` compiles the configuration release of the data product catalog: one config.json for the shared cluster, one
deployment profile per environment, a validation report of the overrides it refused and a summary.

```
python3 cli.py compile --data /path/to/data --date 2026-01-15 --out /path/to/out
python3 cli.py export-report --out /path/to/out
```

Modules:

- `loaders.py` reads the twelve input files of the data folder;
- `resolve.py` works out product status, teams, accepted overrides and resolved settings;
- `quota.py` splits a cluster quota over the active products;
- `emit.py` builds and writes the documents;
- `cli.py` is the command line.

The tool has open bug reports: users say the compiled documents do not always agree with the data folder's
`config_contract.md`. That contract is the behaviour of record; where this README or the code says otherwise, the
contract wins.
