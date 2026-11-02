# Program contract

The delivered program answers to this contract.

It accepts a --data option and an --out option, in either order,
each followed by a directory path.

It creates the output directory when it is absent, writes every
published document there, exits zero, writes nothing else anywhere,
and leaves its input directory exactly as it found it.

It reads the substation capacity workbook, the dispatch operations
memorandum and the priority ordering directive from the directory it
is pointed at.

It uses the Python standard library and nothing else.

It holds nothing about this operating day inside it. Every
identifier, control value, threshold, boundary and rung code is read
from the directory it is pointed at.

Two runs over one input directory produce identical bytes, and so
does the same operating day placed under another directory name.

It uses exact rational arithmetic and no binary floating point.

It carries the fourteen stages as fourteen separately named steps, in
the stage order terminal_contract_overview.md prints.
