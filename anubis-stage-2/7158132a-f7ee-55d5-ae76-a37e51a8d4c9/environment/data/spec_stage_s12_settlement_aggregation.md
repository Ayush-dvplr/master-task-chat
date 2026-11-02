# S12 settlement aggregation

S12 is projection only. It introduces no new arithmetic beyond addition
of values already frozen, and it reads the canonical ledger rather than
any earlier file.

## mission statements

One row per mission per period, for every mission on the register and
every period, including the pairs with no accepted pass. Those rows
carry zeros rather than being omitted.

won_pass_count is the number of accepted canonical rows. The seconds and
volumes are sums over the same rows. net_mcr is the sum of net_mcr over
the contracts of the mission for that period, from S13, so a mission
with two contracts adds both.

## station statements

One row per station per period, for every station and period. The
utilisation_bp column is the station figure from S11, carried across
rather than recomputed.

## ordering

Mission rows are ordered by mission_id then by period. Station rows by
station_id then by period. Period order is P1, P2, P3 throughout this
pipeline and is never lexicographic on some other column.
