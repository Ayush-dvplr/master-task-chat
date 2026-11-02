# Glossary and field dictionary

adjusted capacity. The capacity left for reefers on a feeder in an
interval once the standing reserve has been withheld and the
confirmed crane duty has been taken off. Never below zero.

allowance. Energy granted to a reefer beyond its mandatory floor out
of the day headroom of its feeder, settled by the reconciliation
passes and then placed into intervals.

applicable row. The row of a register that governs a key: the row
carries this operating day, its record state is an applicable one,
and among those rows it carries the highest sequence.

base draw. The watt draw of a reefer in an interval, which is the
whole watt figure RULE P03.i stores. It is not four times the stored
watt hour floor of that interval: the floor and the draw are two
separate roundings of the same quantity and neither is derived from
the other.

cluster. The set of reefers naming one plug.

day headroom. The sum over the intervals of a feeder of the adjusted
capacity plus the battery support less the reconciled load.

discretionary energy. The requested energy of a reefer less its
mandatory floor, never below zero.

mandatory floor. The energy a reefer must take to hold its
temperature over the intervals it is connected for.

reserved capacity. The nominal capacity of a feeder in an interval
less its standing reserve, never below zero.

set aside. A row whose record state reads superseded, withdrawn,
cancelled or retired. It is dropped before any sequence is read.

shortfall. The mandatory floor a reefer required at or before its
vessel cutoff less what it was served at or before that cutoff.

spill. The move of a placement out of an interval a reconciliation
removed it from and into the next interval that admits it.

standing reserve. The watts a feeder withholds before any free
capacity is counted.

## Field names

day_id. The operating day a row belongs to.
record_state. current, filed, booked and landed are applicable.
superseded, withdrawn, cancelled and retired are set aside.
revision_seq, declaration_seq, notice_seq, schedule_seq, confirm_seq,
duty_seq, telemetry_seq. The sequence field of a register, named per
register in revision_precedence.toml.
interval. An interval ordinal from 1 to 96.
nameplate_value and nameplate_unit. The quoted running power of a
reefer and the unit it is quoted in.
declared_value and energy_unit. The quoted energy a reefer asks for.
demand_kw. Crane duty demand, quoted in kilowatts.
derate_permille. Parts per thousand of the nominal capacity that a
derating notice leaves standing.
