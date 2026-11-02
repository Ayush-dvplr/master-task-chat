# Replay and amendments

cycles.csv contains stream,x,y,modulus,a,b,c,rounds,quantity. Stream identifiers
are unique. The stream's initial pair is x,y, each in zero through modulus minus
one. A round replaces the pair simultaneously: the first new component is the
old y; the second new component is the remainder of a times old x plus b times
old y plus c plus old x times old y, divided by modulus. The pair after rounds
rounds is the settled pair; zero rounds retains the initial pair. A stream's
settled units are quantity times the sum of settled x and modulus times settled y.
There are two permitted stream families. A small stream has modulus at most 127
and arbitrary a,b,c. A large stream has prime modulus 1000000007 and exactly
a=1,b=1,c=0. For a large stream, defining u=x+1 and v=y+1 changes a round to
(u,v) -> (v,u*v), with arithmetic modulo the stream modulus. This identity is
part of the contract; rounds can be as large as 10**18 and must not be simulated.
Stream ordering is ascending text order. A stream is eligible when its settled
units are at least eligibility_threshold, including equality. Eligibility is
defined only for the public view; it does not remove units from the South lane.

fold_records.csv contains record,position,a,b. Record identifiers are text.
Positions are unique integers. A fold visits records in ascending position
order, starting at replay.json initial. Visiting a record replaces the state
with the remainder of a times state plus b, divided by replay.json modulus.
The empty fold retains initial reduced modulo modulus.

Initially, consecutive records in ascending position order are joined by an
undirected edge, forming one path (or an empty graph). A path fold from record U
to record V visits every record on the unique U-to-V path in that direction and
applies its affine transform. If either endpoint is absent or the endpoints are
disconnected, the path is empty and retains replay.json initial modulo modulus.

fold_corrections.csv contains amendment,arrival,record,revision,a,b,action,
cut_left,cut_right,link_left,link_right,query_start,query_end. Amendment
identifiers are unique integers. Process amendments in ascending arrival order,
breaking ties by integer amendment identifier. Each record starts with accepted
revision minus one. An amendment to an absent record is orphan. An amendment
whose revision is at most that record's accepted revision is superseded. Every
other amendment is applied: it replaces both a and b and the accepted revision,
then performs its forest action. Action keep has empty cut and link cells and
leaves the forest unchanged. Action swap_edge first removes the undirected edge
cut_left--cut_right, then adds link_left--link_right. The swap occurs only when
all four records exist, the cut edge exists, and the new edge reconnects the two
resulting trees; otherwise its topology effect is a no-op. The coefficient
replacement is still applied. These are replacements, including a replacement
equal to an earlier state.

After each applied amendment, its state is the path fold from query_start to
query_end after that replacement and forest action. Missing or disconnected
query endpoints give the empty-path state. Orphan and superseded amendments
ignore their action and query cells and keep the previous state. The initial
previous state is the path fold from the least-position record to the
greatest-position record, or initial for no records.
Weighted states is the sum of amendment identifier times that amendment's state,
including orphan and superseded amendments. Revised counts applied amendments.
