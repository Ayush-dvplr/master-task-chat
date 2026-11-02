# Tabular and structured inputs

## Comma, semicolon and tab separated files

The attendee register is tab separated, the handle table and the office
snapshot are comma separated, and the payroll export is semicolon separated.
Each has one header row naming its columns; columns are found by name, not by
position. Values are not quoted.

## The pipe separated outbox

The outbox has a header row and one operation per line. Fields are separated by
the pipe character. Inside a field a backslash escapes the character after it,
so `\|` is a literal pipe that does not separate fields and `\\` is a literal
backslash. A line whose first character is `#` is a comment. Lines may appear
in any order; outbox-replay.md says how operations are ordered.

## JSON lines

The two change log shards hold one JSON object per line. Blank lines carry
nothing.

## The YAML status book

The status book is written in a small YAML subset:

- Structure comes from indentation with spaces. A line `key: value` is a
  mapping entry; a line `key:` opens a nested block on the following, more
  deeply indented lines; a line starting `- ` is a sequence item, and the rest
  of that line starts a mapping that continues on the following lines at the
  indentation of the text after `- `.
- A scalar is plain, single quoted or double quoted. In a single quoted scalar
  `''` is one quote character and nothing else is escaped; in a double quoted
  scalar a backslash escapes the character after it. Quotes are not part of the
  value, so `'"8b9e2f3d6f"'` is the ten characters between the double quotes
  plus the double quotes themselves.
- A `#` that starts a line, or follows whitespace outside quotes, starts a
  comment that runs to the end of the line.
- A revision may be written as a plain number or as a quoted string of digits;
  either way it is the integer those digits spell.

## SQLite databases

The closure database holds a table `closures(office, day, name, revision,
state)` and the busy database a table `periods(source, attendee, fbtype,
start, finish, withdrawn)`. Their meaning is given in attendance.md and
travel-and-busy.md. Rows have no meaningful order.

## The itinerary XML

The itinerary is an XML document whose root holds `leg` elements:

```xml
<leg id="LEG-004" attendee="ATT-003">
  <depart office="SCL" local="20270810T091000"/>
  <arrive local="20270810T173000" office="JFK"/>
  <carrier>LA0532</carrier>
</leg>
```

Attribute order and child order carry no meaning. A leg whose `status`
attribute is present and is not `confirmed` was not flown and takes no part in
any computation; a leg without the attribute is confirmed.
