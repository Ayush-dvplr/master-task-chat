# Plan Output Contract

The planner writes plain JSON files (UTF-8, no byte order mark) into its output folder. Key
order inside an object does not matter. Lists are sorted exactly as stated. All byte counts
are exact integers. Dates are ISO `YYYY-MM-DD`.

## 1. Command line

    python3 optimize.py --data <input folder> --out <output folder> [--prior <earlier output folder>]

The planner reads only the input folder (and the prior folder when given), never changes
them, and writes only into the output folder. Output depends on file contents only, never
on the folder names, the clock, or the order in which the file system lists files.

## 2. Status file `perf_report.json`

Always written.

| Key | Value |
|---|---|
| `plan_id` | `plan_id` from `run_control.json`, or `null` if it cannot be read |
| `status` | `PUBLISHED` or `HELD` |
| `reasons` | list of strings, sorted; empty when published |
| `census` | one entry per census file, sorted by `file` |
| `scenarios` | one entry per scenario, sorted by `as_of`; empty when held |
| `media_shares` | written only when the plan is published: an object `{"<cartridge>": int}` with one key per cartridge in the media catalogue, mapping the cartridge name to its reserve as basis points of its native capacity, rounded half to even as in section 5 |

Reason strings are `MISSING:<file>`, `SIZE:<file>`, `SHA256:<file>` and `RECORDS:<file>`. A
missing file gives only its `MISSING` reason. A present file gives a reason for each check it
fails. When `estate_census.toml` itself is missing the only reason is
`MISSING:estate_census.toml`.

A census entry is
`{"file": name, "present": bool, "bytes_ok": bool, "sha256_ok": bool, "records_expected": int or null, "records_seen": int or null}`.
`records_seen` is the count by the rules of the desk brief when the census lists a record
count and the file is present, otherwise `null`. A missing file has `bytes_ok` and
`sha256_ok` false.

A scenario entry is
`{"name": str, "as_of": date, "objects": int, "kept_replicas": int, "released_replicas": int, "volumes": int}`.

When the status is `HELD` the planner writes `perf_report.json` and nothing else.

## 3. Scenario files `scenario_<name>.json`

One file per scenario name in `run_control.json`.

    {
      "plan_id": "...",
      "scenario": "<name>",
      "as_of": "YYYY-MM-DD",
      "objects": [...],
      "replicas": [...],
      "volumes": [...]
    }

`objects`: one entry per planned object, sorted by `digest`:

| Key | Value |
|---|---|
| `digest` | SHA-256, 64 lower case hex characters |
| `rendition` | `master`, `mezzanine` or `proxy` |
| `collections` | current collection ids named by its planned rows, sorted, no repeats |
| `class` | class of the governing collection after amendments, for example `R3B` |
| `required` | required distinct vaults |
| `held` | true when any of its collections is under hold |
| `under_replicated` | true when it sits in fewer distinct vaults than required |
| `kept_vaults` | vault codes of its kept replicas, sorted, no repeats |

`replicas`: one entry per planned row, sorted by `vault` and then `path`:
`{"vault": code, "path": object_path, "digest": hex, "bytes": int, "collection": current id, "rendition": str, "keep": bool}`.

`volumes`: sorted by vault code and, within a vault, in the order of `volume_layout.md`:
`{"label": str, "vault": code, "usable_bytes": int, "used_bytes": int, "fill_bps": int, "members": [[path, footprint], ...]}`.

## 4. Rollups

`bottleneck_analysis.json`:

    {"plan_id": "...", "scenarios": {"<name>": {"under_replicated_objects": int, "held_objects": int,
      "vaults": {"<code>": {"volumes": int, "used_bytes": int, "kept_replicas": int}}}}}

Every vault code appears for every scenario, with zeros when it keeps nothing.

`recommendations.json`:

    {"plan_id": "...", "scenarios": {"<name>": {"release_replicas": int,
      "reclaim_bytes_by_vault": {"<code>": int},
      "reclaim_bytes_by_segment": {"commercial": int, "public": int}}}}

Reclaimed bytes are the exact file sizes of released replicas (not footprints). The segment
of a released replica is the segment of the collection on its own row. Every vault code and
both segments appear, with zeros where nothing is released.

`data_quality.json`:

    {"plan_id": "...", "files": {"<export file>": {"rows": int, "sidecar_rows": int,
      "legacy_collection_rows": int, "duplicate_rows": int}}, "void_node_rows": {"<name>": int}}

`files` has one entry per vault export file (the `.dat` file stands for each Kolhapur
shard). `rows` counts every row; `legacy_collection_rows` counts rows whose collection was
given as a legacy id; `duplicate_rows` counts planned rows that are duplicates in the sense
of charter section 7; `void_node_rows` counts, per scenario, the rows left out under charter
section 9.2.

## 5. Small worked example

Made up numbers, one vault, usable capacity 100, footprints 60, 50, 40, 30 (already in
packing order). 60 opens volume 1; 50 does not fit on volume 1 and opens volume 2; 40 fits on
volume 1 (100); 30 fits on volume 2 (80). Volume 1 has fill 10000 basis points and volume 2
has 8000.

Rounding example: used 123456789, usable 1000000000 gives 1234.56789 basis points, written
as 1235. Used 1 and usable 20000 gives exactly 0.5, written as 0.
