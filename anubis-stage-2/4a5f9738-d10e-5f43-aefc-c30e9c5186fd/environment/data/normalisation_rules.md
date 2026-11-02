# Normalisation rules

## Holder references

A holder reference in any source becomes a canonical identifier by applying
these steps in order.

| step | rule |
| --- | --- |
| 1 | fold to upper case |
| 2 | drop every character that is not a letter or a digit |
| 3 | drop a leading HL prefix when one is present |
| 4 | when more than six characters remain keep the last six |
| 5 | when fewer than six characters remain pad on the left with zeros to six |

`holder_alias_map.csv` then redirects canonical identifiers. Redirection is
applied until no further redirection applies. A redirection that returns to an
identifier already visited forms a cycle, and every member of that cycle
resolves to the member that sorts first. A row that redirects an identifier to
itself changes nothing. A row whose target is unknown to every registry still
applies; the grant then has no registry entry.

## Effective bounds

| encoding of effective_to | reading |
| --- | --- |
| an empty field | open ended, so the bound is the horizon end |
| the json null value | the committee deferred the bound, so the grant is faulty |
| a stamp equal to effective_from | a closed grant of zero duration |
| any other stamp | the stamp itself |

Both effective bounds are half open, lower inclusive and upper exclusive. The
same convention holds for frequency bounds and for every window in this corpus.

## Frequency bounds

A record carries a lower bound and a width, and may also carry an explicit
upper bound. When both an explicit upper bound and a width are present and they
disagree the explicit upper bound governs. When no explicit upper bound is
present the upper bound is the lower bound plus the width. A lower bound must
be the lower edge of a channel of the raster and an upper bound must be the
upper edge of a channel of the raster, in either case of any band.

A zone office log carries only grants filed in the zone named in the file
name, and every stamp in that file is the local time of that zone. A
coordination minute carries its own offset. A national register extract and a
state event file carry universal time.

`unit_declarations.ini` states the unit and the clock basis of every source
column. A width expressed in hertz that is not a whole number of kilohertz
cannot be converted and makes the grant faulty. A declared unit token outside
the accepted set, or a missing declaration where one is required, also makes
the grant faulty.
