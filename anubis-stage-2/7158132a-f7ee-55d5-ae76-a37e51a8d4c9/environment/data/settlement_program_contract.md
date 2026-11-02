# settlement program contract

The settlement program is a deliverable in its own right and is graded
on directories it has never seen.

## the interface

    python3 /app/out/settle.py --data DIR --out DIR

Both flags are required and both take a directory path. The program
reads the working papers under the data directory, writes all thirty
artifacts into the output directory, creating it when it does not
exist, and exits with status zero.

## what it may do

It imports the Python standard library and nothing else. It reads only
the directory given by the data flag. It writes only into the directory
given by the out flag. It reaches no network, reads no environment
variable that changes a value it emits, and consults no file outside
the two directories.

It produces the same bytes every time it is run against the same data
directory. Nothing it emits depends on a clock, a random source, a
process identifier, a hash seed, or the order a directory listing
happens to return.

## what it may not do

It may not carry values derived from one particular month. A program
that recognises a case by its shape and returns a remembered answer is
not a settlement program, and a program whose output changes when a
file is renamed is not one either. Every figure it writes is derived
from the papers in front of it.

## the papers it will be given

Another month has the same file names, the same columns and the same
rules. Its passes, operating windows, dockets, advisories, campaign
phases, cancellations, journals, overrides, claims, backlog reports
and contract amendments are its own, and so are its rates, its per
contact caps, its aperture period budgets and its credit rates. Which
of the remaining figures a month shares with this one is not
published, so no figure read from these papers may be written into
the program. Every figure it emits is read from the data directory it
was handed on that run.

The artifacts the program writes for a given directory are the same
artifacts the run is graded on. A delivery whose artifacts disagree
with what its own program produces for the same directory is a delivery
that reports one thing and computes another.
