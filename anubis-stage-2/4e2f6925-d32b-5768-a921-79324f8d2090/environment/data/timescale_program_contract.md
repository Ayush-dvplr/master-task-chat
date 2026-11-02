# The program the desk keeps

The desk keeps one program that recomputes a publication interval from its
working papers. It is published as timescale.py beside the artifacts it
produces, and it is the artifact the desk reuses; the twenty seven documents are
this interval's run of it.

## Interface

    python3 timescale.py --data <input directory> --out <output directory>

Both options default to the directories this interval used. The program reads
nothing outside the directory it is given and writes nothing outside the
directory it is told to write to. It creates the output directory when it does
not exist and it does not remove files it did not write.

## Behaviour

The program holds nothing about this interval inside it. Every identifier,
every count, every threshold and every constant it uses comes from the papers
it is pointed at, including the four control values in the signed memo and the
class ceilings, the node cap and the uncertainty components on the live
workbook sheet. Pointed at a different interval of the same network, with a
different population, a different acquisition profile and different control
values, it produces that interval's twenty seven documents.

It is deterministic. Two runs over the same directory produce the same bytes,
and a run on another machine at another time produces those bytes again.
Everything it needs comes from the directory it is pointed at, so it reads no
clock, draws on no random source, takes nothing from an environment variable,
reaches for nothing outside that directory and uses nothing about the name of
the directory it is given.

That is a property of the delivered program and of nothing else. How the work
gets done is open: read what you like, run what you like, look up whatever
helps.

It reads the workbook and the memo itself. They are a real spreadsheet and a
real document and both are load bearing.

## Failure

An input the papers do not describe is a fault, and the program says which
paper and which field, rather than guessing a value.
