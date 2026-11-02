# Hollowbrand relay cycle RC-2411

You are the release operator for the Hollowbrand package relay. A promotion cycle has to be closed
and nobody wrote down which source wins when two of them disagree.

Every piece of evidence sits in `/app/data`. It holds fifty three files: specification documents, a
configuration layer, and the record tables those documents name. Where a document leaves an instant
or a revision comparison open, `/app/data/boundary_semantics.json` settles it. Begin at
`/app/data/data_index_spec.md`, which names every other file and says what each one governs. The
relay itself sits in `/app/service`. Read those modules before you call them. They are the authority
on what the relay accepts and they stay exactly as shipped, as does everything in `/app/data`.

Settle the whole cycle first. Only then open the first call to the relay.

Each promotion request that governs inside the cycle horizon receives one decision and one reason
code drawn from `/app/data/reason_code_registry.json`. The decision words come from the governance
document. When more than one gate fires for a single request, the registry `order` field settles
which code is reported. A request whose identifier appears more than once contributes once.
Requests whose submission falls outside the horizon contribute nowhere.

Start the relay, apply the admitted promotions through it, and close every channel on the ladder in
ladder order inside one final call that carries nothing else. Fill each earlier call to the
operation limit the operations runbook defines before you open another, and let exactly one call
repeat an earlier identity key so the relay replays its stored answer. Reach the relay on the
loopback port the runbook names, under the actor name it gives. One refused operation costs the
whole call, so no call may be aborted and no operation may be refused.

Write these seven files and nothing else into `/app/out`, each a JSON object:

```
/app/out/report.json
/app/out/summary.json
/app/out/transcript_summary.json
/app/out/final_state.json
/app/out/scenario_alpha.json
/app/out/scenario_beta.json
/app/out/scenario_mode.json
```

`/app/data/artifact_contract_spec.md` fixes the key sets, the field names, the value forms, the row
ordering and the indent for all seven. `/app/data/metrics_definitions_spec.md` fixes the rounding,
the place counts, the share distribution and the digest width for every figure in the summary.
`/app/data/scenario_definitions_spec.md` fixes what the two scenario files and the two comparison
modes change and what they leave alone. Follow those three documents to the letter: an artifact
counts only when every value in it is exact, and a single wrong figure costs that artifact.

`final_state.json` carries the state the relay reports after the last call, not a state you compose
yourself. `report.json` carries the full decision roster and the order in which the admissions were
applied. `transcript_summary.json` carries the call accounting for the session. `summary.json`
carries the cycle totals and metrics, the cover held for rollback across the ladder among them,
together with the depth the revalidation reached. The three scenario files carry the comparison runs.

Beyond the single apply address the artifact contract asks for by name, no artifact may hold a clock
reading, a host name, a file path, a duration, or any other field that would differ on a second run
of the same work. Run the work twice and expect the same bytes.

Close with a message to the operator that reports ten counts the artifacts do not carry. The scope
of three of the counts below is fixed in `/app/data/boundary_semantics.json`.

First, for the edge channel, the seats drawn from the tier one reserve, the seats drawn from the tier
two reserve, the seats drawn from the general pool, and the total seats that channel offered before
revalidation. Second, the same four figures for the canary channel. Third, the seats drawn from each
of the three pools for the staging channel, and the seats offered anywhere on the stable channel.
Fourth, the bound pairs that drew rollback cover in each of the four channels. Fifth, the size of one
rollback hold in each of the four channels. Sixth, the tier two reserve each of the four channels
still held once the cycle settled. Seventh, the general pool each of the four channels still held
once the cycle settled. Eighth, the tier one reserve each of the four channels still held once the
cycle settled. Ninth, the requests refused for want of room to cover them both ways, the requests
refused because the pool they reached was empty, and how the first of those two figures splits
between the canary and the staging channels. Tenth, the holders taken out by the first revalidation
pass, by the second, by the third, and across the whole cycle.

In that same message, say where each figure came from, name any quantity you left unsettled, and
keep it apart from the figures you derived in full.

Work only from what sits under `/app`. Do not look up a solution online and do not consult any
source beyond the loopback relay and the files shipped with this task. Python 3.12 and its standard
library are installed; nothing else is available and nothing can be installed.

You have 10800 seconds to complete this task.
