# pathcal interface

The compiler is two files and the compile desk runs it as one command. This
document is the interface contract. It does not state what any stage computes;
the rulebook in the extract does that.

## Layout

| file | owns |
|---|---|
| `ttc.py` | argument handling and nothing else |
| `pathcal.py` | every stage of the compile and every document it writes |

`ttc.py` puts its own directory at the front of the import path and then
imports `pathcal`, so the pair runs from whatever directory it is installed in
as long as the two files sit side by side. Nothing else is imported beyond the
Python standard library, and no third file is read at run time.

## Command line

```
python3 ttc.py compile <DATA_DIR> <OUT_DIR>
```

The single subcommand is `compile`. `DATA_DIR` is an extract directory.
`OUT_DIR` is where the documents are written, and the engine creates it when it
does not exist. Any other argument shape prints the usage line to standard
error and exits 2. A successful compile exits 0 and prints nothing.

## Engine entry point

`pathcal.compile_extract(data_dir, out_dir)` is the one public function. It
takes the two directory paths as strings and returns nothing. The engine reads
nothing outside `data_dir`, writes nothing outside `out_dir`, and produces the
same bytes every time it runs on the same extract.

## The reporting helpers

The four helpers at the bottom of `pathcal.py` own the line shapes of the two
text documents the schema does not spell out: `render_report` owns the twelve
lines of the prose report and `render_status` owns the single status line. Both
have been unchanged since build 3.1 and the figures they are handed are the
only thing that moves in them. `render_rows` and `render_flags` own the
delimited and XML shapes the schema does spell out.

## Build history

- 3.1 first build to write the prose report and the status line in their
  current shape.
- 4.0 added the zone offset stage and the admission ladder.
- 4.1 added the variant overlay stage.
- 4.2 current build. Its last run over the shipped extract stopped before the
  digest stage. The desk has never reconciled this build against the rulebook,
  so read the two together rather than trusting either on its own.
