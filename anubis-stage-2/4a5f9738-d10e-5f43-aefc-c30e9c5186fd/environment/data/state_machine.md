# Grant state machine

A grant occupies spectrum only while it is active. Every grant starts active at
its effective start. `state_events_<zone>.csv` carries the dated events of the
zone. Events are read in event order and the same visibility cutoff that
applies to source records applies to events.

| state | event | next state | measurable after |
| --- | --- | --- | --- |
| active | activate | active | yes |
| active | suspend | suspended | no |
| active | restore | active | yes |
| active | terminate | terminated | no |
| suspended | suspend | suspended | no |
| suspended | restore | active | yes |
| suspended | activate | suspended | no |
| suspended | terminate | terminated | no |
| terminated | any | terminated | no |

A `restore` that reaches a grant that is already active is an anomaly. The
event is ignored and the anomaly is counted. An event stamped before the
effective start takes effect at the effective start. An event stamped at or
after the effective end is ignored. Events that share an instant are read in
the order `terminate`, `suspend`, `restore`, `activate`.
