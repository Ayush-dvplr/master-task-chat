# Stage r02: Identifier resolution and registers

A station or programme may be recorded under a code carried over from
an earlier epoch. `alias_crosswalk.tsv` maps such a code to the
canonical identifier. A crosswalk row is in force when its
`in_force_from_revision` stands at or below the frozen register
revision; among the in force rows for one code and kind the greatest
revision governs. Resolution happens before screening, before ordering
and before any register lookup.

`station_register_frozen.csv` is the station register in force. For each
station the row in force is the one with the greatest revision at or
below the frozen register revision. A station with no such row is absent,
and an event naming it carries `EVT-UNKNOWNSTATION`. A transfer names a
counterparty as well, and an absent or empty counterparty carries the
same code.

`station_register_current.csv` carries later lodges of the same keys
with different classes and regions and governs nothing here.

`programme_register.csv` is read the same way. An event naming a
programme with no in force row carries `EVT-UNKNOWNPROGRAMME`. A
compensating event names no programme of its own and never carries this
code.
