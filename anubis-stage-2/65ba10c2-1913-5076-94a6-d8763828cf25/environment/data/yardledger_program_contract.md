PROGRAM CONTRACT
shift KP-2042-S23

The program published beside the documents is yardledger.py.

SECTION 1  HOW IT IS CALLED

    python3 yardledger.py --data <input directory> --out <output directory>

The two options may be given in either order. The program creates
the output directory when it is absent, writes the whole publication
there and exits with status zero. It writes nothing else into that
directory and it leaves the input directory byte for byte as it
found it.

SECTION 2  WHAT IT MAY DEPEND ON

The Python standard library and nothing else. No package is
installed for it and none may be imported. The workbook, the
memorandum and the directive are read with the standard library.

SECTION 3  WHAT IT MAY HOLD

Nothing about this shift. Every identifier, control value,
threshold, boundary, rung code and vocabulary member is read from
the directory the program is pointed at. A block identifier, a berth
identifier, a damping fraction, a pass budget, a slot length, a
class rank or a rung order written into the program is a defect,
because the same program is run against other shifts whose papers
carry different ones.

SECTION 4  DETERMINISM

Two runs over one input directory produce identical bytes. The same
shift placed under a different directory name produces those bytes
again, so no behaviour may depend on a path, a file modification
time, a clock, a locale, an environment variable or a random source.

SECTION 5  WHAT IT MAY READ

Only the directory it is pointed at. It does not reach for any other
path on the machine, and it does not read the directory the
publication is graded from.

SECTION 6  WHAT SHAPE IT TAKES

The fourteen stages appear in the program as fourteen separately
named steps, in the order terminal_contract_overview.md lists them,
so a reader can put a published figure back to the stage that
derived it. A program that folds the stages into one step meets none
of this section however right its numbers are.
