# The JSON calendar encoding

A replica in this encoding is one JSON array:

```json
["vcalendar",
 [["version", {}, "text", "2.0"], ["prodid", {}, "text", "-//EXEC-OPS//Calendar Platform 5.0//EN"]],
 [
  ["vevent",
   [["uid", {}, "text", "HX-ONE-ON-ONE-2027"],
    ["recurrence-id", {"tzid": "/EXEC-OPS/2027/America-Pacific", "range": "THISANDFUTURE"},
     "date-time", "2027-03-10T08:30:00"],
    ["dtstart", {"tzid": "/EXEC-OPS/2027/America-Pacific"}, "date-time", "2027-03-10T07:44:30"],
    ["rrule", {}, "recur", {"freq": "WEEKLY", "byday": ["MO", "WE"], "count": 5}],
    ["exdate", {"tzid": "/EXEC-OPS/2027/America-New-York"}, "date-time",
     "2027-04-21T09:00:00", "2027-04-26T09:00:00"],
    ["rdate", {}, "period", ["2027-04-03T09:00:00", "P1D"]],
    ["sequence", {}, "integer", 4],
    ["attendee", {"role": "REQ-PARTICIPANT", "x-att-id": "ATT-012"}, "cal-address",
     "mailto:claudia.moreau@example.invalid"],
    ["summary", {}, "text", "Operations check in; moved"]],
   []]
 ]
]
```

A component is a three element array: its lower case name, its list of
properties and its list of sub components. A property is an array: the lower
case property name, an object of parameters, the value type, and then one entry
per value. A parameter value is a string, or a list of strings when the
parameter has several values; parameter names are lower case here and are
matched case insensitively as in iCalendar text.

Values are typed:

- `date-time` and `date` values are extended ISO strings, read as basic values
  exactly as encoding-xcal.md describes; a property listing several instants
  carries one string per instant after the type.
- `period` values are two element arrays: the start, then an end or a
  duration.
- `recur` values are one object whose keys are the lower case rule part names.
  A part with one value may be a scalar or a one element list; a part with
  several values is a list. Numbers are JSON numbers and `until` is an extended
  ISO string.
- `integer` values are JSON numbers; `text`, `duration` and `cal-address`
  values are JSON strings.

Text values are JSON strings, so the iCalendar backslash escapes do not apply:
`"Operations check in; moved"` is a summary containing a semicolon. Non ASCII
characters may appear directly or as JSON `\u` escapes.
