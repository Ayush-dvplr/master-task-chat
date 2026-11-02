The Aldermere regional railway compiles its working timetable with an in house
tool called pathcal. The 4.2 build of that tool sits at `/app/repo`, and its
last run over the current timetable period stopped part way through. The tool is
known to disagree with the railway's own rulebook, and nobody has written down
where.

`/app/wtt` holds the extract for that period: twenty seven files carrying the
path register, the recurrence rules, the exception dates, the retired
identifiers, the zone offset history, the section and route tables, the headway
policy, the operator register, the timetable mailbox, two leftovers of the
stopped run, and the documents that govern all of it. Some of those files carry
the same field with different numbers, and the railway's own rules decide which
copy a compile reads. The ten stages and the exact shape of every document are
defined in `/app/wtt/timetable_rulebook.md` and the files it names, among them
`/app/wtt/report_schema.md` for the output shapes and
`/app/wtt/file_role_index.md` for the role each input plays.
`/app/repo/INTERFACE.md` states the layout and the command line the repaired
tool keeps. Work out from the material itself which inputs feed which figure,
and where the tool departs from the rulebook.

Deliver the repaired tool as two files, the command line entry at
`/app/out/ttc.py` and the engine at `/app/out/pathcal.py`, keeping the names and
the split the shipped tool uses. The entry imports the engine from beside it,
and the pair has to run on its own without any other file you write. It must run
as

```bash
python3 /app/out/ttc.py compile <DATA_DIR> <OUT_DIR>
```

and write all eighteen documents into `OUT_DIR`, creating that directory when it
does not exist yet, from the files in `DATA_DIR` alone, so that the same code
compiles an extract it has never seen that follows the same documented rules.
Then run it on this extract so that these files exist:

- `/app/out/identity_resolution.json`
- `/app/out/authority_resolution.json`
- `/app/out/expansion_audit.json`
- `/app/out/exception_merge.json`
- `/app/out/overlay_resolution.json`
- `/app/out/timepoint_materialization.json`
- `/app/out/headway_resolution.json`
- `/app/out/withheld_paths.json`
- `/app/out/compiled_timetable.json`
- `/app/out/canonical_calendars.json`
- `/app/out/timetable_digest.json`
- `/app/out/data_quality.json`
- `/app/out/operator_rollup.tsv`
- `/app/out/section_rollup.psv`
- `/app/out/path_rollup.csv`
- `/app/out/flagged_paths.xml`
- `/app/out/compile_report.md`
- `/app/out/run_status.txt`

Write every document under `/app/out` exactly as named, in the shapes
`report_schema.md` defines. Your documents are compared against the figures the
rulebook defines, both for this extract and for the output of your tool on
freshly generated extracts that use the same file names and the same documented
rules with different identifiers, values and data faults. Each run of your tool
on such an extract has to finish within 600 seconds. The compile is coupled end
to end: one wrong day anywhere moves the running calendar, the admission walk
that consumes it, every rollup and the digest. Rows and figures count only when
they are exact.

The tool must read nothing outside its `DATA_DIR` argument, must write nothing
outside its `OUT_DIR` argument, and must produce identical bytes every time it
runs on the same input. Use Python 3.12 and its standard library only; there is
no network, and anything you try to install will not be there later. Do not edit
or delete anything under `/app/wtt`.

You have 14400 seconds to complete this task. Do not cheat by using online
solutions or hints specific to this task.
