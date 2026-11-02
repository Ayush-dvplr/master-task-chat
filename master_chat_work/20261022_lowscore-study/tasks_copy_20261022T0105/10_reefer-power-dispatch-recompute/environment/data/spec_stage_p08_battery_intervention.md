# Stage P08, the battery intervention

This stage works the yard battery against the reconciled load, one
interval at a time, carrying the state of charge forward.

RULE P08.a  The battery serves the substation its operating policy
names. Its deficit in an interval is the sum, over the feeders of
that substation, of the reconciled load less the adjusted capacity,
counting only the feeders where that difference is above zero. The
published deficit is that watt figure divided by four and floored.

RULE P08.b  The battery is available in an interval when the
telemetry of this operating day reads online for it and no booked
maintenance window against the battery covers it. An unavailable
interval publishes an action of offline and moves nothing.

RULE P08.c  In an available interval carrying a deficit the battery
discharges. The discharge is the least of the deficit watt hours,
the maximum discharge watts divided by four and floored, and the
state of charge above the reserve multiplied by the discharge
efficiency permille and divided by a thousand and floored.

RULE P08.d  A state of charge sitting exactly on the reserve is
lawful. Nothing may be drawn from it there, so the discharge is zero
and the limit reason reads state_of_charge_on_reserve.

RULE P08.e  A discharge of e watt hours lowers the state of charge
by e multiplied by a thousand, divided by the discharge efficiency
permille, taken to the ceiling.

RULE P08.f  In an available interval carrying no deficit whose
tariff band is one of the charge eligible bands the battery charges.
The charge is the least of the maximum charge watts divided by four
and floored, the substation headroom watts divided by four and
floored, and the room left under the capacity. A charge of c watt
hours raises the state of charge by c multiplied by the charge
efficiency permille, divided by a thousand and floored.

RULE P08.g  An available interval carrying no deficit whose tariff
band is not a charge eligible band publishes an action of idle and a
limit reason of band_ineligible.

RULE P08.h  The discharge of an interval supports the feeders of the
substation in ascending feeder identifier order, each taking what
its own deficit needs until the discharge is spent.

RULE P08.i  Every schedule row publishes a limit reason. An
offline interval reads none and an idle interval reads
band_ineligible. A discharging interval reads
state_of_charge_on_reserve when its discharge is zero,
discharge_limit when its discharge equals the maximum discharge
watts divided by four and floored, state_of_charge_limit when its
discharge equals what the state of charge above the reserve
allows, and deficit_met otherwise, the three tested in that
order. A charging interval reads no_room when its charge is zero,
capacity_limit when its charge equals the room left under the
capacity, charge_limit when its charge equals the maximum charge
watts divided by four and floored, and headroom_limit otherwise,
the three tested in that order.

RULE P08.j  The state of charge state reads at_reserve when the
closing charge equals the reserve, below_reserve under it and
above_reserve over it. A closing charge under the reserve is a hard
violation stage P13 counts.

## Published documents

battery_schedule.csv and soc_ledger.psv.
