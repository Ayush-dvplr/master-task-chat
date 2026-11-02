# {{PACKAGE_NAME}}-ctl

This local stdlib-only CLI should create, update, validate, and report a flat
JSON configuration for {{FORMAT_TAG}} {{CONTAINER_NOUN}} processing. It is broken
in several places and must be repaired before use.

Expected commands after repair:

```bash
python3 cli.py init --schema schema.json --out config.json
python3 cli.py set --config config.json --key max_records --value 100
python3 cli.py validate --schema schema.json --config config.json
python3 cli.py export-report --config config.json --out report.json
```
