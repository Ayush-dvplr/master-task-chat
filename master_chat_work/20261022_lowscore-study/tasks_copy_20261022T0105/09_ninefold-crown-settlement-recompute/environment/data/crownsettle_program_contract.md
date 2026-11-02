# Settlement program contract

The delivered program settles one event from one directory of working
papers. It is the same program for every event: nothing about this event
may sit inside it.

## Interface

It accepts `--data <directory>` and `--out <directory>`, in either order.
It creates the output directory when it is absent, writes every declared
document there, exits zero and writes nothing else anywhere.

## Restrictions

- Python standard library only. No package is installed at run time.
- The three papers that are not plain text are read by the program
  itself. It does not require them to be converted first.
- Exact rational arithmetic throughout. No binary floating point in any
  derivation.
- No value this event carries is held inside the program: no identifier,
  control value, threshold, boundary, unit conversion, rung order,
  applicable or excluded status list, or key order. Each is read from the
  directory the program is pointed at. The vocabulary the specifications
  themselves define, such as state, basis, class, code and key names, is
  not a value of the event.
- The input directory is left exactly as it was found.
- Two runs over one input directory produce identical bytes, and so does
  the same event placed under another directory name.
- The program derives its own answer. It never reads a document from
  beside its input directory and copies it out.

## Failure

A paper the specifications require and the directory does not hold is a
failure: the program exits non zero and writes no document.
