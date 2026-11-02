# field dictionary for the replan export set

| field | source role | meaning | inversion |
| --- | --- | --- | --- |
| effective_seq | every register | planning sequence a row becomes effective at | rows above the cutoff are out of scope |
| rev | every register | revision number inside one key | highest revision wins |
| void | every register | row cancelled at source | row is dropped |
| row_uid | every register | stable row identity | binds the lifecycle log |
| units_dz | demand | quantity expressed in dozens | multiply by twelve |
| scale | cost registers | kcents or cents | kcents multiplies by one thousand |
| ccy | cost registers | denomination of the amount | EUR converts at the cutoff rate |
| unit | index registers | bps or pct | pct multiplies by one hundred |
| sign | amendments | charge or credit | credit subtracts |
| amend_id | amendments | logical amendment identity | repeated identity applies once |
| forecast_units | demand | planning forecast column | never used for the plan |
| unit_cost_cents_legacy | cost registers | pre migration copy | never used |
| capacity_units_legacy | capacity registers | pre migration copy | never used |
| status | item and plant registers | lifecycle state | retired and mothballed drop out |
| fiscal_ordinal | period windows | position in the planning horizon | orders the horizon |
| fy_start | period windows | first period of the fiscal year | anchors the horizon |
| committed_volume_units | capital programme | business case volume | values the capital selection |
| capital_budget | capital programme | funded capital envelope | bounds the selection |
| shortfall_penalty_per_unit | penalty schedule | charge for uncovered demand | prices the shortfall |
| holding_rate | penalty schedule | carrying rate in bps | prices carried inventory |
| energy_surcharge | energy memorandum | additive uplift in bps | adds to the period index |
