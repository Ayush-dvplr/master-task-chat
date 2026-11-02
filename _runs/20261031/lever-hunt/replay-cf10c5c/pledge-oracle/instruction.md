# Close the pledge docket for window W-2026Q2

You keep the settlement desk for a principal who owes pledges to counterparties.
The quarter is over, and the docket has to be settled, filed and sealed.

Everything the desk holds sits in `/app/data`. Begin at
`/app/data/corpus_index.md`, which names every file in the corpus. The rule
documents beside it carry the charter, the output contract, the call protocol,
source precedence, temporal handling, dependency handling, grace allocation,
reason codes, entity resolution and mode selection. They define every term used
below, and they are the only description of desk practice you get. The
settlement interface and its client live in `/app/service`.

A pledge belongs to the docket when its governing due instant falls inside the
settlement window. A governing due instant comes from the governing record for
that pledge, chosen under source precedence and under the retraction and cutoff
tests the rules state. Origin instants never decide membership.

Resolve every holder reference in the corpus to one holder key. Resolve every due
expression in the business zone of its holder. Expand every recurring commitment
into period instances and apply the period actions that reached the desk in time.
Settle the governing due instant of every pledge, and take the docket from those
instants alone.

Then weigh the evidence. Decide, for each docket pledge, whether discharge
evidence, a waiver grant or nothing governs it. Propagate prerequisite readiness
across the whole dependency graph, including prerequisites that sit outside the
settlement window. Give every docket pledge one final state drawn only from
cleared, tempered_clear, breached, waived, blocked, held and lapsed, plus a
reason code list drawn only from the closed set the rules publish.

Settle the governing mode from the layers the rules name, and run the grace round
only when the governing mode calls for it.

Record the settlement through the interface in `/app/service`. Declare the window
before any other call. Register every docket pledge in dependency order. File a
boundary notice for every pledge that misses the settlement window by less than
the boundary band, so that each exclusion is recorded. Move every pledge through
its events in the order the call protocol requires, on the channel the channel
policy assigns to that event. Record granted minutes. Seal the window, then
confirm the seal.

File these seven artifacts:

`/app/out/report.json`
`/app/out/final_state.json`
`/app/out/transcript_summary.json`
`/app/out/scenario_alpha.json`
`/app/out/scenario_beta.json`
`/app/out/scenario_mode.json`
`/app/out/summary.json`

`/app/data/output_contract.md` fixes the key set, the key spelling, the value
vocabulary, the ordering and the instant form of each one. Emit exactly those
keys and nothing besides. The content of `/app/out/final_state.json` is the
sealed state the interface returns.

Three alternative settlements stand beside the filed one. Alpha repeats the
settlement with no grace round at all. Beta repeats it with every due expression
resolved in the zone the principal occupied at the origin instant of the pledge.
Mode sets both tallies side by side with the authority that settled the governing
mode.

The bar is exact. An artifact counts only when every key, every enum value, every
instant and every minute figure matches. A figure that is close is a figure that
is wrong.

Where sources disagree, the rule documents in `/app/data` govern: the charter
governs docket scope, the output contract governs artifact shape, and the call
protocol governs the interface.

Close with a message to the principal. It has to state, as figures that appear
in none of the artifacts: how many docket pledges took their governing due
instant from a counterparty acknowledgement that beat a surviving register
amendment; how many docket pledges belong to a class whose ceiling minutes
changed inside the settlement window; how many retraction notices were
themselves retracted and which record keys those retractions restored; how many
boundary notices you filed before the window opened and how many after it
closed; how many docket pledges entered the grace round; how many docket holders
resolved only once a legal suffix was removed; how many prerequisite edges point
outside the docket; how many live suspensions fall on a recurring series that
this docket draws from; the highest escalation tier carried by a breached pledge
and how many breached pledges carry it; how many docket governing due instants
fall after a zone offset change inside the settlement window.

You have 7200 seconds to complete this task. Work only from the material in
`/app/data` and `/app/service`, and do not search online for solutions or hints
to this task.
