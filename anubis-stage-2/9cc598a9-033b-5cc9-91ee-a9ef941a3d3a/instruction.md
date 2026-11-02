The storage team has to restore the projects share after the ransomware incident, and the tool that should tell them what to restore, from which backup sets and from which media, is broken. The tool is the `restorekit` project shipped as `/app/data/project.zip`. It no longer installs on Python 3.12, and the plan it produced before it broke was rejected because it did not follow the restore specification. Repair the project and plan the restore with it.

Everything the restore depends on is in `/app/data/`: the restore request, the backup catalog parts, job history, server logs, registers, notices and the documents that govern them. The rules are those of the restore specification revision in force together with the documents it incorporates. Where the shipped code, a file's name or a file's own description disagrees with those rules, the rules win. Leave `/app/data/` unchanged.

Deliver:

- `/app/out/package.zip`: the repaired project as an installable src-layout package with its `pyproject.toml`, `src/restorekit` and the project's own test suite, kept unchanged and passing. It must run as `python -m restorekit restore --feed DIR --out DIR` with `src` on the path, for any restore feed laid out like `/app/data`, and write the five files below into the `--out` directory. It must identify feed files by their content, never by file name, read nothing but the feed directory it is given and its own files, and produce identical bytes on every run. A normal restore run writes nothing to the console. It is installed and run on a plain Python 3.12 that has setuptools and only these distributions: openpyxl 3.1.5, pyarrow 18.1.0, pypdf 5.1.0, PyYAML 6.0.3 and tzdata 2025.2.
- The restore plan for `/app/data`: `/app/out/restore_manifest.csv`, `/app/out/exclusions.csv`, `/app/out/media_pull_list.csv`, `/app/out/restore_chain.json` and `/app/out/reconciliation.json`, in the formats of section 11 of the specification. These five files must be written by your repaired package itself, run with `--feed /app/data --out /app/out`; do not write, copy or edit them with anything else.

Each deliverable is accepted only as an exact match of the specified content: every row, every field, the order and the custody trailer. A plan that is right on most rows is still wrong. Your package is also run on another restore feed with the same structure, for a different share, and its output there must be exact as well.

When you finish, list in your final message the restore rule corrections you made to the shipped project.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
