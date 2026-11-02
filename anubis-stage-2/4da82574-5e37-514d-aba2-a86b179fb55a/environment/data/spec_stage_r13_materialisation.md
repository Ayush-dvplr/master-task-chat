# Stage r13: Materialisation and the derived index

The published state carries its position, the station balances with
every zero balance dropped, the nested station and programme allotments
with every zero allotment dropped and every station left holding none
dropped with it, every derived counter, the pending queue in queue
order, the applied ledger sorted ascending and the reversed ledger
sorted ascending. The position of a replay's state is the end boundary
of the range the replay was asked for, a position it never replays; the
position of the probe document is the probe position.

The derived index carries one record per surviving station and programme
pair. Each record holds the region and hub the station reports under in
`topology_and_scope.xml`, the station, the programme, the allotment in
credit units and the share that allotment takes of the station total,
as a ratio at twelve places. A station whose allotments cancel to zero
publishes a zero share rather than dividing. The index is ordered by
region, then hub, then station, then programme.

The probe document holds the state after the probe position in a from
scratch forward pass with no re offer round run at all. The bounded
document holds the state a replay of the bounded range reaches, with its
own checkpoint selected against the bounded end boundary.
