# Stage P13, the objective reconciliation

RULE P13.a  The objective is a lexicographic vector compared in this
order: hard violations, unmet mandatory energy, deadline penalty,
peak demand, energy cost, battery cycle, then the tie key. A
schedule with a lower energy cost still loses when an earlier
component is worse.

RULE P13.b  A hard violation is a feeder and interval whose final
load stands above its adjusted capacity plus its battery support,
and every interval whose closing state of charge stands below the
reserve. The hard violation component is the count of both together.

RULE P13.c  The unmet mandatory energy is the sum of the shortfalls
of every queued reefer at the close of the correction.

RULE P13.d  The deadline penalty of a reefer standing short is the
surcharge of the highest rung of the ladder in
dispatch_operations_memo.pdf whose interval figure stands at or
below its shortfall intervals.

RULE P13.e  The energy cost is the sum of the interval charges, the
demand charge and the base service charge the governing workbook
sheet carries.

RULE P13.f  The battery cycle is the sum of every discharge and
every charge in watt hours.

RULE P13.g  The tie key is the first sixteen characters of the
sha256 of the reefer identifiers standing powered anywhere, taken
once each in ascending order and joined by semicolons.

## Published documents

objective_vector.json and constraint_certificate.json.
