# Lane dispatch

Every admitted work order occupies exactly one lane at the home site of its
governing client. The lane roster lists one row per lane with its site, an optional
class lock, an optional exclusive client, a slot capacity and a rate in micro units
per billable slot.

- A lane that declares a class lock accepts work of that service class alone.
- A lane that names an exclusive client accepts work of that client alone.
- The billable slots resting on a lane may reach the slot capacity of that lane and
  may go no further.
- incompatible_families: thermal|solvent, abrasive|inert
- Two orders whose governing revisions belong to an incompatible pair of process
  families share no lane.
- Every site holds one lane that declares no class lock, names no exclusive client
  and publishes a slot capacity of zero. That lane is relief capacity: it accepts
  any quantity of work of any class from any client at the penalty rate its site
  publishes, and the incompatible family rule is no bar to it.
- The schedule the authority settles is the one whose total of billable slots
  multiplied by lane rate, summed over every admitted order at a site, is smallest.

## Contention

Where two admitted orders contend for the last slots of the cheapest lane both are
eligible for, the order carrying the LARGER remaining slack keeps the lane and the
order carrying the tighter remaining slack yields. This is the settled practice of
this authority and it reverses the habit of favouring the tighter deadline: an
order with room to spare is the one that holds cheap capacity here, and the urgent
order is the one that moves. Where remaining slack is equal the larger billable
slot count keeps the lane, and where that is equal too the order whose identifier
sorts first keeps the lane.
