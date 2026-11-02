You have 5400 seconds for this task.

Our heavy maintenance planning team published the hangar check plan for the season, and then
Maintenance Control sent a disruption notice with base closures and revised aircraft availability.
The plan now has to be redone for the whole fleet across the four bases. Please write the program
that does this replan.

Write a Python 3 program at `/app/out/derive_report.py`. It is run as:

    python3 /app/out/derive_report.py --data <data folder> --out <output folder>

When `--data` is not given it reads `/app/environment/data/`, and when `--out` is not given it writes
to `/app/out/`. The program uses only the Python standard library, reads only the data folder and
the documents, and writes only inside the output folder. One run on one data folder must finish
within 60 seconds.

The rules are in `/app/environment/docs/`. Start with `/app/environment/docs/README.md`, which says
which file governs each topic. The input files are described in
`/app/environment/docs/data_conventions.md` and the output files in
`/app/environment/docs/output_schema.md`. Every number the plan needs comes from the data folder;
nothing is to be typed in by hand.

After writing the program, run it once on `/app/environment/data/` so that the output files for this
season are present under `/app/out/`.

Each output document is compared field by field with the expected document, and only an exact match
of a field counts. Your program will also be run again on other data folders in the same format,
and its output there is compared the same way.
