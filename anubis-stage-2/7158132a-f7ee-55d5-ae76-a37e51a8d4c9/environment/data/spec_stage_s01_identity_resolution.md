# S01 identity resolution

Three identities have to be settled before anything else can be read.

## missions

mission_register.csv is a revision history. One row per mission per
register_rev. The binding row is the one whose register_state is
current. There is exactly one current row per mission. Every other row
is superseded and its priority_class is historical.

The pass plan does not carry mission identifiers. It carries a
presentation identifier, and mission_alias_crosswalk.csv maps that to a
mission over a half open effective window. The binding row for a pass is
the crosswalk row whose valid_from_s is at or before the pass
scheduled_start_s and whose valid_to_s is strictly after it. The window
that matters is the one containing the scheduled start of the pass, not
the one containing the start of the settlement period.

The crosswalk contains presentation identifiers that repeat across
different effective windows. Two rows may carry the same
presentation_id and resolve in different windows. A pass whose
scheduled_start_s falls in no window for its presentation_id is
unresolved and is rejected at S03 predicate one.

## stations

ground_segment_register.tsv is a facility register. It lists every
element at every station, one row per element. Only the row whose
element_class is accounting_site carries the station tz_offset_min that
the accounting calendar is written against. Every other row carries zero
in that column and means nothing by it.

## apertures

aperture_register.csv is a configuration history. One row per aperture
per config_rev, and the binding row is the one whose config_state is
current. The pass plan names an aperture by station_id and
aperture_label together. The pair resolves against the current
configuration rows only. A label that resolved under an older
configuration and does not resolve under the current one is unknown, and
the pass is rejected at S03 predicate two.

## contracts

A mission may hold more than one contract. settlement_audit_trace.db
carries the contract identity, the mission it belongs to, its half open
validity window and whether carry forward is enabled for it. The station
scope of a contract is in reference_lookups.sqlite, table station_scope,
one row per contract and station in scope.

contract_terms_amendments.tsv is an amendment log, one row per contract
per period per revision_seq. The settled terms for a contract period are
the row with the highest revision_seq whose amendment_status is
executed. A draft or withdrawn amendment binds nothing however late it
sits in the file, and file order is not revision order.
