# Replica encodings and the iCalendar content line grammar

## Which encoding a replica uses

A replica file is read by its first octet that is not whitespace: `B` means
iCalendar text (this document), `<` means the XML calendar encoding
(encoding-xcal.md) and `[` means the JSON calendar encoding
(encoding-jcal.md). All three describe the same calendar objects. After
decoding, a component is the same set of properties whatever its encoding, and
every later stage treats it the same way: two stores that differ only in the
encoding of their replicas produce identical reports.

Two values need a common form across encodings. A date time value is compared
and reported in basic form: `YYYYMMDDTHHMMSS` for a wall clock value and the
same followed by `Z` for an absolute instant, so the extended value
`2027-03-10T08:30:00` is the basic value `20270310T083000`. The raw
`RECURRENCE-ID` value used in merge keys and reports is this basic form of the
value as written, so a wall clock identifier stays a wall clock identifier and
a UTC identifier keeps its `Z`.

## Content lines

iCalendar replicas carry UTF-8 text. A long content line is folded by inserting
a line feed followed by a single space or a single horizontal tab. Folding
counts octets rather than characters, so a fold can fall between two octets of
one multi octet character. A line is therefore unfolded on its raw octets, by
deleting every line feed together with the one whitespace octet that follows
it, and only the unfolded line is decoded as UTF-8. Any further whitespace at
the start of a continuation line is content.

Property names and parameter names are case insensitive, and so are the values
of the `ROLE` and `RANGE` parameters. Every other parameter value and every
property value keeps its case.

The property name and parameter list are separated from the value by the first
colon that is not inside a double quoted parameter value. Parameters are
separated by semicolons that are not inside double quoted values. A parameter
value may be double quoted and the quotes are stripped; a quoted value may hold
colons, semicolons and commas. Multi valued parameters use commas outside
quotes.

Text property values use backslash escaping, decoded in one left to right pass
in which a backslash and the single character after it form one escape. The
escape `\n` or `\N` means a line feed, `\,` means a comma, `\;` means a
semicolon and `\\` means a single backslash. Any other escaped character
resolves to the character itself. A character produced by an escape is never
read again as the start of another escape. So `F:\\packs\\nq3` reads as
`F:\packs\nq3`, where the `\n` that remains is a backslash followed by the
letter n.

Components nest with `BEGIN` and `END` lines. The pass reads `VTIMEZONE`,
`STANDARD`, `DAYLIGHT` and `VEVENT` components.

A date time value that ends with `Z` is an absolute UTC instant. A value of
exactly eight digits is a date. Any other value is a floating local wall clock
value whose zone comes from the `TZID` parameter of the same property, read
through the alias table of zone-aliases.md.

## Properties the pass reads

`UID`, `RECURRENCE-ID` (with `TZID` and `RANGE`), `DTSTART`, `DTEND`,
`DURATION`, `RRULE`, `RDATE`, `EXDATE`, `SEQUENCE`, `LAST-MODIFIED`,
`DTSTAMP`, `SUMMARY`, `STATUS`, `ATTENDEE` (with `ROLE` and `X-ATT-ID`),
`X-OFFICE`, `X-SERIES-CLASS` and `X-PINNED`. Every other property is ignored.
A required participant is an `ATTENDEE` whose `ROLE` is `REQ-PARTICIPANT`, a
missing `ROLE` counting as `REQ-PARTICIPANT` and any other role counting as
not required; the identifier of the participant is the first value of its
`X-ATT-ID` parameter, and an `ATTENDEE` without one names nobody.
