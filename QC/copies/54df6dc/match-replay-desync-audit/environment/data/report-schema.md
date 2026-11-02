# Report schema

Every report this engine emits is a JSON object. This note lists the field names
each report carries, the type each field holds, and the ordering of each array.
It carries no figure derived from any capture, register or schedule.

A field typed `rational` holds a string of the form numerator, solidus,
denominator, in lowest terms, with the denominator written even when it is one.
A field typed `count` holds a JSON integer. A field typed `word` holds a lower
case name. A field typed `cadence` holds one of `peak`, `steady`, `burst` or
`latency`.

## The whole scenario report

Written as `scenario_visible.json`.

| field | type | note |
| --- | --- | --- |
| `capture_count` | count | how many captures the set holds |
| `entry_total` | count | decoded entries across the set |
| `settled_total` | count | entries that survive settlement |
| `units` | array | one object per surviving canonical unit, ascending by `unit` |

Each entry of `units` carries:

| field | type | note |
| --- | --- | --- |
| `unit` | word | the canonical word |
| `charter` | word | the canonical charter |
| `tick_total` | count | settled tick total for the unit |
| `amount_total` | rational | settled amount total for the unit |
| `cadence` | cadence | the class the unit falls in |
| `kind_totals` | array | three rationals, for kind zero, kind one and kind two, in that order |

## The per cadence reports

Written as `scenario_peak.json`, `scenario_steady.json`, `scenario_burst.json`
and `scenario_latency.json`, one file per class.

One report is emitted for each cadence class, whether or not the class holds a
unit. Each carries:

| field | type | note |
| --- | --- | --- |
| `cadence` | cadence | the class this report covers |
| `unit_count` | count | surviving units in the class |
| `amount_total` | rational | settled amount total across the class |
| `units` | array | one object per unit in the class, ascending by `unit` |

Each entry of `units` carries `unit`, `charter`, `tick_total` and
`amount_total`, with the same types as above.

## The settlement report

Written as `perf_report.json`.

| field | type | note |
| --- | --- | --- |
| `charter_stocks` | array | one object per charter, ascending by `charter` |
| `settled_total` | rational | settled amount across the set |
| `decoded_total` | rational | decoded amount across the set |
| `reversal_count` | count | reversal entries the set holds after decoding |
| `promoted_reversal_count` | count | reversals that cancelled nothing |

Each entry of `charter_stocks` carries `charter` as a word and `stock` as a
rational.

## The derivation record

Written as `bottleneck_analysis.json`.

| field | type | note |
| --- | --- | --- |
| `quantities` | array | one object per withheld quantity, in published order |
| `settling_passes` | count | passes the identity register took to stabilise |
| `calibration_table` | array | one object per control figure, in published order |

Each entry of `quantities` carries `name` as the published quantity name,
`value` as a count, `control` as the published control name, and `rejected` as
an array holding one object per rejected candidate in ascending candidate order.
Each entry of `rejected` carries `candidate` as a count and `falsifier` as the
name of the control figure that rejected it.

Each entry of `calibration_table` carries `control` as the published control
name, `published` as the figure the notes publish, and `produced` as the figure
the run reproduced. Both are strings.

## The bench report

Written as `recommendations.json`.

| field | type | note |
| --- | --- | --- |
| `target` | rational | the upkeep target |
| `bench` | array | candidate words, ascending |
| `bench_upkeep` | rational | upkeep the bench carries |
| `residual_after_bench` | rational | target less bench upkeep |

## The quality report

Written as `data_quality.json`.

| field | type | note |
| --- | --- | --- |
| `dropped_retired` | count | entries dropped because the unit had retired |
| `dropped_offwindow` | count | entries dropped because no live window admits them |
| `dropped_amount_total` | rational | amount carried by dropped entries |
| `decoded_amount_total` | rational | amount across every decoded entry |
| `settled_amount_total` | rational | amount across every settled entry |
| `conservation_residual` | rational | decoded less settled less dropped |

## The reusable program

The program is delivered as Python source. It takes the directory holding the
capture set as its first argument and the directory to write into as its second.
It writes every report named above and nothing else.
