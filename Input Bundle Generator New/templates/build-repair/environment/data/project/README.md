# {{FORMAT_TAG}} build triage package

This small project should provide a package named `{{PACKAGE_NAME}}` for scoring
{{CONTAINER_NOUN}} manifests emitted by {{PRODUCER_SYSTEM}}. It is currently in
included smoke tests do not pass.

Intended public API:

- `__version__`
- `load_manifest(path)`
- `score_entry(entry)`
- `score_batch(entries)`
- `summarize(entries)`
- `render_report(entries)`

Keep the repair stdlib-only.
