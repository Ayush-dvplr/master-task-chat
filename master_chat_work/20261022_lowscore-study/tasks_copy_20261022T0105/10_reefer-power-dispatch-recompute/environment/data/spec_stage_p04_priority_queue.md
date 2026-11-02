# Stage P04, the admission ladder and the dispatch priority queue

This stage sets aside the reefers the yard cannot serve and orders
the rest.

RULE P04.a  The ladder is read in the order
dispatch_admission_ladder.txt prints its rungs. The first rung that
catches a reefer settles it and no lower rung is consulted for that
reefer. The printed order is not the alphabetical order of the rung
codes.

RULE P04.b  DR_UNKNOWN_PLUG catches a reefer whose plug has no
governing row in plug_assignment_register.csv, and a reefer whose
governing plug row carries a plug state other than live.

RULE P04.c  DR_FEEDER_OUT_OF_FORCE catches a reefer whose feeder is
absent from substation_topology.xml. A feeder carrying a capacity
row is out of force when the topology omits it.

RULE P04.d  DR_WINDOW_EMPTY catches a reefer whose lattice holds no
interval.

RULE P04.e  DR_UNKNOWN_POWER_UNIT catches a reefer whose unit state
reads unknown_unit.

RULE P04.f  DR_PLUG_ZONE_REFUSED catches a reefer whose plug zone
and temperature class pairing carries the admission refused in the
governing rows of plug_zone_admission_matrix.csv, unless a zone
waiver notice of this operating day names that reefer.

RULE P04.g  DR_DUPLICATE_CONNECTION is settled among the reefers the
five rungs above left standing. The cluster key is the plug
identifier. The canonical member of a cluster is the lowest reefer
identifier among those standing reefers, and every other standing
member of the cluster is caught. A cluster member an earlier rung
already caught is not a candidate to be canonical.

RULE P04.h  The deadline slack of a queued reefer is the cutoff
interval of its applicable call less the last interval of its
lattice. A reefer whose vessel has no applicable call takes the
absent call slack sentinel priority_precedence_policy.toml names,
an urgency rank of 9, a service group of sg_none and a cutoff
interval of 96.

RULE P04.i  The queue is ordered on the four keys the priority
ordering directive prints, in the key positions it prints them,
every key ascending. The class rank of a temperature class is the
rank the same directive prints.

RULE P04.j  A queued reefer publishes its rank from 1 upward and a
queue state of queued. A reefer a rung caught publishes a rank of
zero, zero on every key and the rung code as its queue state.

## Published document

dispatch_priority_queue.csv.
