# Calibration slice and published control figures

## Withheld wire constants

The stall reporter builds nine constants into the wire it writes and does not
print them. The reporter is stable: the same nine constants govern every
journal it writes, the incident window and the calibration population alike.
Their candidate values are these, and no other value is admissible.

| Constant | Candidate values |
|---|---|
| count bias window | 2, 3, 4, 5, 6 |
| interleave stride | 3, 5, 7, 9, 11, 13 |
| chain mask width | 6, 7, 8, 9, 10, 11 |
| depth complement width | 5, 6, 7, 8, 9, 10 |
| owner ring width | 4, 6, 8, 12, 16 |
| coarse spin unit | 32, 64, 128, 256, 512 |
| token rotation offset | 0, 1, 2, 3, 4, 5, 6, 7 |
| hold scale | 1, 2, 4, 5, 8, 10, 16 |
| epoch span | 1048576, 2097152, 4194304, 8388608, 16777216, 33554432, 67108864, 134217728, 268435456, 536870912, 1073741824, 2147483648 |

## The calibration population

A calibration population ships beside the incident window. It is a held out
capture of the same fleet under the same reporter, with its own journal, its
own probe export and its own park export. It is not part of the incident window
and no figure of the incident window counts any of its events.

Eleven control figures were published for that population. Each figure is one
number and each is stated below by what it counts. Exactly one assignment of
the nine constants above reproduces all eleven at once.

| Figure | What it counts |
|---|---|
| CTRL-A | how many events the calibration journal carries |
| CTRL-B | the total of the wait spans of those events |
| CTRL-C | the total of their hold spans |
| CTRL-D | the total of their depths |
| CTRL-E | the total of the numbers that close their owner tags |
| CTRL-F | the total of their spin counts |
| CTRL-G | the total of their wait for tokens read as hexadecimal numbers, taken modulo 1000000007 |
| CTRL-H | the total of their ticks |
| CTRL-I | how many calibration events are counted rather than set aside |
| CTRL-J | how many calibration lock classes are quarantined |
| CTRL-K | the calibration population's byte residual |

Every one of the eleven figures is read over the calibration population alone.
The side tables the incident window uses, the registry, the ladder, the pool
windows, the cell table and the tenant table, are the same tables for both.

## Reach of the calibration slice

The calibration population and these eleven figures ship once, with this
incident window. A later capture arrives as its own journal, its own probe
export and its own park export beside the same side tables, and carries no
calibration population and no control figures of any kind.

The reporter being stable is what makes that workable. The nine constants
settled against this slice are the nine constants of every journal the reporter
writes, so they are settled once and then held. Anything that reads them back
out of a control figure on every run serves this window and no other.

## The labelled sample population

A third population ships as teaching material. Its journal is written with
every flag of the flag word clear, so it exercises the base line shape of the
wire and nothing else. The two figures it produces ship beside it, already
worked out, so the shape those figures take can be read off directly. The
sample population reveals no constant from the table above: none of the nine
constants can be read out of a capture that carries no flags, and the sample
answers were chosen so that they do not move under any candidate value.
