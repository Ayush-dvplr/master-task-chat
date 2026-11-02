# Stage p01  identifiers, the register in force and the parameter layer

The round opens against one register. `round_header.json` names it in
`register_in_force`. The other copy of the register is the drafting copy the
desk works on between rounds and it settles nothing, however recent its rows
look.

Inside the register in force a job may carry several rows. The row in force is
the row of the greatest revision among the rows whose `state` is `sealed` or
`withdrawn` and whose `sealed_round` is at or below the round index. A row
sealed for a later round is read by a later round and not by this one. A job
whose row in force carries the state `withdrawn` is set aside under
`JOB-WITHDRAWN`. A job with no such row at all, because every row it carries
is a draft or is sealed for a later round, is set aside under `JOB-DRAFTONLY`.
A job whose row in force names a precinct that the live yard topology does not
carry is set aside under `JOB-NOPRECINCT`. A job that is set aside takes no
part in the round and holds no derived cell.

Every job identifier, in whichever paper it stands, is put through
`identifier_crosswalk.tsv` before anything else reads it; for a precedence row
that means both of its ends. A crosswalk row whose status is not `active` maps
nothing.

The parameter layer is assembled here. The class multipliers come from
`class_rate_register.csv`, taking for each class the row of the greatest
`effective_round` at or below the round index whose state is `in_force`. The
licence register is read whole. The precinct list comes from the live yard
topology. The shift length of each precinct and the weight of each pool come
from the parameter workbook, from the sheet whose `sheet_key` cell matches
`workbook_round_cell` in the round header. The deferral rate of each class,
the number of entries the working store retains and the charge above which a
job is reported as implausible come from the board memo, from the sitting the
memo marks as in force for this round. A sitting the memo marks as rescinded
settles nothing.
