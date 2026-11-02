# Stage P01, unit normalisation

This stage settles which rows of every register govern operating day
AP-2044-D111 and converts every quoted quantity into its base unit.

RULE P01.a  The operating day identifier and the day reference are
the day and reference attributes of substation_topology.xml. Every
row of every register carrying another day identifier is set aside.

RULE P01.b  A row governs only while its record state is one of the
words the applicable list of revision_precedence.toml carries. A row
whose record state reads superseded, withdrawn, cancelled or retired
is set aside, and so is a row whose record state is a word neither
list carries. The set aside test is applied before any sequence is
compared, so a set aside row carrying the highest sequence of its key
settles nothing.

RULE P01.c  Among the rows of a key that survive P01.a and P01.b,
the row carrying the highest value of that register sequence field
governs. revision_precedence.toml names the sequence field of every
register.

RULE P01.d  The feeder of a reefer is the feeder its plug is
assigned to by the governing row of plug_assignment_register.csv.
The substation of a reefer is the substation the governing row of
feeder_capacity_register.csv gives that feeder.

RULE P01.e  The nameplate is converted to watts through the power
entry of unit_register_dictionary.toml the nameplate unit names.
Multiply the quoted value by the entry numerator, divide by the
entry denominator, round half up and store the whole watt figure.

RULE P01.f  A nameplate quoting a unit the power section does not
carry stores a nameplate of zero and a unit state of unknown_unit.
Every other reefer stores a unit state of converted.

RULE P01.g  The declared energy of a reefer is the declared value of
the governing row of energy_declaration_returns.psv converted
through the energy entry its energy unit names, rounded half up to a
whole watt hour.

RULE P01.h  A reefer with no governing return, or whose governing
return carries the not supplied marker as its declared value, stores
the string not_declared. That is a return with no declared energy
and it is not a declaration of zero.

RULE P01.i  The applicable call of a vessel is the governing row of
vessel_call_register.csv under P01.a to P01.c. A vessel whose every
row for this operating day is set aside has no applicable call.

## Published document

normalised_reefers.jsonl, one object per reefer in reefer identifier
order.
