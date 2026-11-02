# The XML calendar encoding

A replica in this encoding is one XML document in the namespace
`urn:ietf:params:xml:ns:icalendar-2.0`. Element names are the lower case
iCalendar names. Each `vevent` element holds one `properties` element, and each
property is one element named after the property:

```xml
<vevent>
  <properties>
    <uid><text>HX-WEEKLY-OPS-2027</text></uid>
    <dtstart>
      <parameters>
        <tzid><text>/EXEC-OPS/2027/America-Pacific</text></tzid>
      </parameters>
      <date-time>2027-01-13T08:15:00</date-time>
    </dtstart>
    <rrule>
      <recur>
        <freq>WEEKLY</freq>
        <interval>3</interval>
        <byday>SU</byday>
        <byday>WE</byday>
        <until>2027-05-26T00:00:00Z</until>
      </recur>
    </rrule>
    <rdate>
      <parameters><tzid><text>/EXEC-OPS/2027/Australia-Central</text></tzid></parameters>
      <period><start>2027-04-03T09:00:00</start><duration>P1D</duration></period>
    </rdate>
    <attendee>
      <parameters>
        <role><text>REQ-PARTICIPANT</text></role>
        <x-att-id><text>ATT-001</text></x-att-id>
      </parameters>
      <cal-address>mailto:dana.okonkwo@example.invalid</cal-address>
    </attendee>
    <summary><text>Quarter review, board pack due</text></summary>
  </properties>
</vevent>
```

A property element may hold one `parameters` element, whose children are the
parameters, each holding one or more `text` elements with its values. Every
other child of a property element is one value, typed by its element name:

- `date-time` and `date` hold extended ISO values such as
  `2027-01-13T08:15:00`, `2027-05-26T00:00:00Z` or `2027-01-13`; they are read
  as the basic values `20270113T081500`, `20270526T000000Z` and `20270113`.
- A property with several values, such as an `EXDATE` listing two instants,
  carries one value element for each.
- `period` holds a `start` and then either an `end` or a `duration`.
- `recur` holds one element per rule part. A part with several values repeats
  its element in order, so two `byday` elements mean `BYDAY=SU,WE`.
- `integer`, `duration`, `cal-address` and `text` hold their value as written.

Text values are plain XML character data: the iCalendar backslash escapes do not
apply, so a comma or a semicolon in a summary is just that character, and the
usual XML entities (`&amp;`, `&lt;`, `&gt;`, `&quot;`) are decoded. Parameter
names and values follow the same rules as in iCalendar text: names are case
insensitive and so are the values of `ROLE` and `RANGE`.
